"""Cross-database linking.

Imports record every technosphere input whose supplier is not inside the same database (for example
USLCI processes that point to ecoinvent, or ecoinvent links to datasets missing from the folder).
The user links each missing product once to a dataset in any library database; Cyclia converts units
and adds the exchanges to the matrix.
"""
import json
import math

import geography
import numcheck
import units


LOC = "UPPER(COALESCE(location,''))"


def groups(store, db_id):
    """Unlinked inputs grouped by product, unit AND location, with the number of uses, why they are unlinked and,
    for inputs with several producers in the same import, the candidate datasets. Inputs at different locations are
    separate groups, so electricity for France and for Poland are never given the same supplier by one click."""
    rows = store.q(f"SELECT product, unit, {LOC} AS location, COUNT(*) AS uses, "
                   "SUM(CASE WHEN linked_to IS NULL THEN 0 ELSE 1 END) AS linked, MAX(linked_to) AS linked_to, "
                   "GROUP_CONCAT(DISTINCT COALESCE(reason,'no producer')) AS reasons, MAX(candidates) AS candidates "
                   f"FROM unlinked WHERE db_id=? GROUP BY product, unit, {LOC} ORDER BY (linked>0), uses DESC", (db_id,))
    for r in rows:
        r["locations"] = r["location"]          # kept for older clients
        try:
            r["candidates"] = json.loads(r["candidates"]) if r["candidates"] else []
        except ValueError:
            r["candidates"] = []
    return rows


def suggest(store, db_id, product, unit, limit=6, location=None):
    """Datasets that could supply the product: the candidates recorded at import first (several producers of the same
    product in this database), then name matches in any database. Same location scores higher, then a global
    market. A dataset of the same database is allowed (for ambiguous or unlinked inputs it is usually the right one)."""
    pn = (product or "").strip().lower()
    loc = (location or "").strip().upper()
    recorded = set()
    for r in store.q(f"SELECT candidates FROM unlinked WHERE db_id=? AND product=? AND COALESCE(unit,'')=COALESCE(?, '') "
                     + ("" if location is None else f"AND {LOC}=? ") + "AND candidates IS NOT NULL",
                     (db_id, product, unit) + (() if location is None else (loc,))):
        try:
            recorded |= set(json.loads(r["candidates"]))
        except ValueError:
            pass
    hits = store.search_activities(product, None, None, limit=80)
    # a provider named by the dataset itself (openLCA defaultProvider) that exists in another library database
    keys = {r["link_key"] for r in store.q(f"SELECT DISTINCT link_key FROM unlinked WHERE db_id=? AND product=? "
                                           "AND reason LIKE 'default provider not in this import%'", (db_id, product)) if r["link_key"]}
    named = set()
    for k in keys:
        for a in store.q("SELECT a.id FROM activities a WHERE a.key=? AND a.db_id!=?", (k, db_id)):
            named.add(a["id"])
    recorded |= named
    seen = {h["id"] for h in hits}
    for aid in recorded - seen:
        a = store.one("SELECT a.id, a.name, a.product, a.location, a.unit, d.name AS db FROM activities a "
                      "JOIN databases d ON d.id=a.db_id WHERE a.id=?", (aid,))
        if a:
            hits.append({**a, "kind": "market" if a["name"].lower().startswith("market") else "process"})
    out = []
    hits = [h for h in hits if (units.factor(unit, h["unit"]) if unit else 1.0) is not None]
    for h in hits:
        fac = units.factor(unit, h["unit"]) if unit else 1.0
        hl = (h["location"] or "").upper()
        # 1.10: geography by ecoinvent's rules (exact, smallest containing region, RoW, GLO), judged among the
        # suppliers of the same product, because RoW only means "where the others do not supply"
        same = [o["location"] for o in hits if o["id"] != h["id"]
                and (o["product"] or "").strip().lower() == (h["product"] or "").strip().lower()]
        kind, rank, why = geography.relation(loc, h["location"], same)
        geo = _geo_score(kind, rank, loc)
        score = (8 if h["id"] in named else 4 if h["id"] in recorded else 0) + (2 if (h["product"] or "").lower() == pn else 0) \
            + geo + (1 if h["kind"] == "market" else 0)
        out.append({**h, "factor": fac, "score": score, "recorded_candidate": h["id"] in recorded,
                    "named_provider": h["id"] in named, "geography": kind, "geography_rank": rank,
                    "geography_note": why, "same_location": bool(loc) and hl == loc})
    out.sort(key=lambda r: -r["score"])
    return out[:limit]


def _geo_score(kind, rank, loc):
    """Score of a supplier's geography for the input's location (higher is better)."""
    if rank is None:
        return -1.0 if loc and kind in ("other", "inside", "overlaps") else 0.0
    if rank == 0:
        return 3.0                                  # same location
    if rank < 2:
        return 2.5 - (rank - 1) * 0.5               # a region containing it, the smaller the better
    if rank == 2:
        return 1.0                                  # rest of the world, clearly covering it
    if rank < 3:
        return 0.6                                  # rest of the world, partly or not checked
    return 0.5                                      # global


def _rows(store, db_id, product, unit, location):
    q = "SELECT * FROM unlinked WHERE db_id=? AND product=? AND COALESCE(unit,'')=COALESCE(?, '')"
    args = (db_id, product, unit)
    if location is not None:
        q += f" AND {LOC}=?"
        args += ((location or "").strip().upper() if location else "",)
    return store.q(q, args)


def _state(store, rows):
    """[unlinked id, supplier, factor] of each input before a change, so the change can be undone exactly."""
    out = []
    for r in rows:
        f = None
        if r["linked_to"] is not None and r["amount"]:
            t = store.one("SELECT amount FROM tech WHERE src_unlinked=? LIMIT 1", (r["id"],))
            f = t["amount"] / r["amount"] if t else None
        out.append([r["id"], r["linked_to"], f])
    return out


def _log(store, db_id, action, method, product, unit, location, target_id, factor, rule, author, n, before, undo_of=None):
    store.conn.execute("INSERT INTO link_log(db_id,time,action,method,product,unit,location,target_id,factor,rule,author,n,"
                       "before,undo_of) VALUES(?,datetime('now'),?,?,?,?,?,?,?,?,?,?,?,?)",
                       (db_id, action, method, product, unit, location, target_id, factor, rule, author or "", n,
                        json.dumps(before), undo_of))


def link(store, db_id, product, unit, target_id, factor=None, location=None, method="manual", rule="", author=""):
    """Link the unlinked inputs of one product, unit and location (location None: every location, as before 1.3.6).
    The decision is recorded in the linking log with the state before it (1.10), so it can be undone."""
    t = store.one("SELECT id, unit, db_id FROM activities WHERE id=?", (target_id,))
    if not t:
        raise ValueError("The chosen dataset does not exist.")
    fac = numcheck.finite(factor, "The conversion factor", lo=0, lo_open=True) if factor not in (None, "") else units.factor(unit, t["unit"]) if unit else 1.0
    if fac is None:
        raise ValueError(f"'{unit}' cannot be converted to '{t['unit']}'. Enter a conversion factor.")
    rows = _rows(store, db_id, product, unit, location)
    if not rows:
        raise ValueError("Nothing to link for that product.")
    bad = [r for r in rows if r["amount"] is None or not all(v is None or math.isfinite(v) for v in (r["amount"], r["p1"], r["p2"], r["p3"]))]
    if bad or not math.isfinite(fac):
        raise ValueError(f"{len(bad)} of these inputs have an amount or uncertainty parameter that is not a finite number. "
                         "They cannot be linked: correct the source data and import it again.")
    if any(r["output_id"] == target_id for r in rows):
        raise ValueError("A dataset cannot supply itself. Choose another supplier.")
    before = _state(store, rows)
    if not rule:
        t_loc = store.one("SELECT location FROM activities WHERE id=?", (target_id,))["location"]
        rule = geography.relation(location or "", t_loc)[2] if location is not None else "chosen by the user"
    with store.lock:
        c = store.conn
        ids = [r["id"] for r in rows]
        q = ",".join("?" * len(ids))
        _log(store, db_id, "link", method, product, unit, location, target_id, fac, rule, author, len(rows), before)
        c.execute(f"DELETE FROM tech WHERE src_unlinked IN ({q})", ids)
        batch = []
        for r in rows:
            p1, p2, p3 = r["p1"], r["p2"], r["p3"]
            if r["utype"] in (2, 3, 4):  # absolute parameters scale with the unit
                p1, p2, p3 = [(v * fac if v is not None else None) for v in (p1, p2, p3)]
            batch.append((r["output_id"], target_id, r["amount"] * fac, r["utype"], p1, p2, p3, r["id"]))
        c.executemany("INSERT INTO tech(output_id,input_id,amount,utype,p1,p2,p3,src_unlinked) VALUES(?,?,?,?,?,?,?,?)", batch)
        c.execute(f"UPDATE unlinked SET linked_to=? WHERE id IN ({q})", [target_id] + ids)
        store._bump_lib()
        c.commit()
    return {"linked": len(rows), "factor": fac}


def unlink(store, db_id, product, unit, location=None, author=""):
    rows = _rows(store, db_id, product, unit, location)
    ids = [r["id"] for r in rows]
    if not ids:
        return {"unlinked": 0}
    q = ",".join("?" * len(ids))
    before = _state(store, rows)
    with store.lock:
        _log(store, db_id, "unlink", "manual", product, unit, location, None, None, "unlinked by the user", author,
             len(ids), before)
        store.conn.execute(f"DELETE FROM tech WHERE src_unlinked IN ({q})", ids)
        store.conn.execute(f"UPDATE unlinked SET linked_to=NULL WHERE id IN ({q})", ids)
        store._bump_lib()
        store.conn.commit()
    return {"unlinked": len(ids)}


def auto_link(store, db_id, author=""):
    """Link a group only when one supplier is unambiguous: the same product name, a convertible unit (markets first
    when the product has a market), and for an input with a location the supplier ecoinvent's linking rules choose:
    the same location, else the smallest supplier geography containing it, else RoW when no other supplier covers it,
    else GLO (1.10; before, only the same location). A RoW that covers the location only in part, a location unknown
    to the topology, or two equally good suppliers are left for review. An input without a location gets the one
    global market or the only supplier. Inputs with several producers in their own import are never linked
    automatically. Each link is recorded in the linking log with the rule that chose it."""
    done, left, how = 0, [], {}
    for g in groups(store, db_id):
        if g["linked"]:
            continue
        if "ambiguous" in (g["reasons"] or ""):
            left.append({"product": g["product"], "location": g["location"], "why": "several producers in the import"})
            continue
        if "default provider not in this import" in (g["reasons"] or ""):
            left.append({"product": g["product"], "location": g["location"], "why": "the dataset names another provider"})
            continue
        if "no supplier link in the dataset" in (g["reasons"] or ""):
            # may be a deliberate cut-off of the system model: only the user can decide
            left.append({"product": g["product"], "location": g["location"], "why": "no supplier link in the dataset"})
            continue
        s = [x for x in suggest(store, db_id, g["product"], g["unit"], limit=200, location=g["location"])
             if (x["product"] or "").strip().lower() == (g["product"] or "").strip().lower()]
        if any(x["kind"] == "market" for x in s):
            s = [x for x in s if x["kind"] == "market"]
        loc = (g["location"] or "").upper()
        pick, rule = None, ""
        if not s:
            why = "no dataset with this product name and a convertible unit"
        elif loc:
            i, why, rank = geography.best(loc, [x["location"] for x in s])
            if i is not None and rank in (2.5, 2.8):
                why = f"{why}: check it"
            elif i is not None:
                pick, rule = s[i], why
        else:
            markets = [x for x in s if (x["location"] or "").upper() in ("GLO", "ROW")]
            pick = markets[0] if len(markets) == 1 else (s[0] if len(s) == 1 else None)
            rule = "the one global market" if len(markets) == 1 else "the only supplier"
            why = "several possible suppliers"
        if pick:
            link(store, db_id, g["product"], g["unit"], pick["id"], location=g["location"], method="automatic",
                 rule=rule, author=author)
            done += 1
            k = rule.split(" (")[0].split(":")[0]
            key = ("same location" if k.startswith("same location") else "containing region" if " contains " in k
                   else "rest of the world" if k.startswith("rest of the world") else "global" if "global" in k else k)
            how[key] = how.get(key, 0) + 1
        else:
            left.append({"product": g["product"], "location": g["location"], "why": why})
    return {"auto_linked": done, "by_rule": how, "left_for_review": len(left), "review": left[:100]}


def log(store, db_id, limit=500):
    """The linking decisions of a database, latest first."""
    rows = store.q("SELECT l.*, a.name AS target_name, a.location AS target_location FROM link_log l "
                   "LEFT JOIN activities a ON a.id=l.target_id WHERE l.db_id=? ORDER BY l.id DESC LIMIT ?",
                   (db_id, limit))
    for r in rows:
        r.pop("before", None)
        r["can_undo"] = not r["undone"] and r["action"] in ("link", "unlink") and r["method"] != "database deleted"
    return rows


def undo(store, log_id, author=""):
    """Put the inputs of one decision back as they were before it (supplier and conversion factor), if nothing has
    changed them since; the undo is itself recorded."""
    e = store.one("SELECT * FROM link_log WHERE id=?", (numcheck.identifier(log_id, "The decision"),))
    if not e:
        raise ValueError("That decision is not in the log.")
    if e["undone"]:
        raise ValueError("That decision was already undone.")
    if e["action"] not in ("link", "unlink") or e["method"] == "database deleted":
        raise ValueError("This entry records an event, not a decision, and cannot be undone.")
    before = json.loads(e["before"] or "[]")
    ids = [b[0] for b in before]
    if not ids:
        raise ValueError("Nothing to undo.")
    q = ",".join("?" * len(ids))
    now = {r["id"]: r for r in store.q(f"SELECT * FROM unlinked WHERE id IN ({q})", ids)}
    expect = e["target_id"] if e["action"] == "link" else None
    changed = [i for i in ids if i not in now or now[i]["linked_to"] != expect]
    if changed:
        raise ValueError(f"{len(changed)} of these inputs were changed by a later decision. Undo that one first.")
    for _, tgt, f in before:
        if tgt is not None and not store.one("SELECT id FROM activities WHERE id=?", (tgt,)):
            raise ValueError("The supplier these inputs had before no longer exists.")
    with store.lock:
        c = store.conn
        c.execute(f"DELETE FROM tech WHERE src_unlinked IN ({q})", ids)
        batch = []
        for uid, tgt, f in before:
            r = now[uid]
            if tgt is None:
                continue
            f = f if f is not None and math.isfinite(f) else 1.0
            p = [(v * f if v is not None else None) if r["utype"] in (2, 3, 4) else v for v in (r["p1"], r["p2"], r["p3"])]
            batch.append((r["output_id"], tgt, r["amount"] * f, r["utype"], *p, uid))
        c.executemany("INSERT INTO tech(output_id,input_id,amount,utype,p1,p2,p3,src_unlinked) VALUES(?,?,?,?,?,?,?,?)",
                      batch)
        for uid, tgt, _ in before:
            c.execute("UPDATE unlinked SET linked_to=? WHERE id=?", (tgt, uid))
        c.execute("UPDATE link_log SET undone=1 WHERE id=?", (e["id"],))
        targets = {b[1] for b in before}
        _log(store, e["db_id"], "undo", "manual", e["product"], e["unit"], e["location"],
             next(iter(targets)) if len(targets) == 1 else None, None, f"undo of decision {e['id']}", author, len(ids),
             [], undo_of=e["id"])
        store._bump_lib()
        c.commit()
    return {"restored": len(ids)}
