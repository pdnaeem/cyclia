"""Cross-database linking.

Imports record every technosphere input whose supplier is not inside the same database (for example
USLCI processes that point to ecoinvent, or ecoinvent links to datasets missing from the folder).
The user links each missing product once to a dataset in any library database; Cyclia converts units
and adds the exchanges to the matrix.
"""
import json

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
    for h in hits:
        fac = units.factor(unit, h["unit"]) if unit else 1.0
        if fac is None:
            continue
        hl = (h["location"] or "").upper()
        score = (8 if h["id"] in named else 4 if h["id"] in recorded else 0) + (2 if (h["product"] or "").lower() == pn else 0) \
            + (2 if loc and hl == loc else 0) + (1 if h["kind"] == "market" else 0) \
            + (0.5 if not loc and hl in ("GLO", "ROW") else 0)
        out.append({**h, "factor": fac, "score": score, "recorded_candidate": h["id"] in recorded,
                    "named_provider": h["id"] in named,
                    "same_location": bool(loc) and hl == loc})
    out.sort(key=lambda r: -r["score"])
    return out[:limit]


def _rows(store, db_id, product, unit, location):
    q = "SELECT * FROM unlinked WHERE db_id=? AND product=? AND COALESCE(unit,'')=COALESCE(?, '')"
    args = (db_id, product, unit)
    if location is not None:
        q += f" AND {LOC}=?"
        args += ((location or "").strip().upper() if location else "",)
    return store.q(q, args)


def link(store, db_id, product, unit, target_id, factor=None, location=None):
    """Link the unlinked inputs of one product, unit and location (location None: every location, as before 1.3.6)."""
    t = store.one("SELECT id, unit, db_id FROM activities WHERE id=?", (target_id,))
    if not t:
        raise ValueError("The chosen dataset does not exist.")
    fac = float(factor) if factor not in (None, "") else units.factor(unit, t["unit"]) if unit else 1.0
    if fac is None:
        raise ValueError(f"'{unit}' cannot be converted to '{t['unit']}'. Enter a conversion factor.")
    rows = _rows(store, db_id, product, unit, location)
    if not rows:
        raise ValueError("Nothing to link for that product.")
    import math
    bad = [r for r in rows if r["amount"] is None or not all(v is None or math.isfinite(v) for v in (r["amount"], r["p1"], r["p2"], r["p3"]))]
    if bad or not math.isfinite(fac):
        raise ValueError(f"{len(bad)} of these inputs have an amount or uncertainty parameter that is not a finite number. "
                         "They cannot be linked: correct the source data and import it again.")
    if any(r["output_id"] == target_id for r in rows):
        raise ValueError("A dataset cannot supply itself. Choose another supplier.")
    with store.lock:
        c = store.conn
        ids = [r["id"] for r in rows]
        q = ",".join("?" * len(ids))
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


def unlink(store, db_id, product, unit, location=None):
    ids = [r["id"] for r in _rows(store, db_id, product, unit, location)]
    if not ids:
        return {"unlinked": 0}
    q = ",".join("?" * len(ids))
    with store.lock:
        store.conn.execute(f"DELETE FROM tech WHERE src_unlinked IN ({q})", ids)
        store.conn.execute(f"UPDATE unlinked SET linked_to=NULL WHERE id IN ({q})", ids)
        store._bump_lib()
        store.conn.commit()
    return {"unlinked": len(ids)}


def auto_link(store, db_id):
    """Link a group only when exactly one supplier is unambiguous: same product name and a convertible unit, and
    - for an input with a location: exactly one such dataset at that location;
    - for an input without a location: exactly one such dataset, or exactly one global (GLO/RoW) market.
    Inputs with several producers in their own import (ambiguous) are never linked automatically."""
    done, left = 0, []
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
        s = [x for x in suggest(store, db_id, g["product"], g["unit"], limit=40, location=g["location"])
             if (x["product"] or "").strip().lower() == (g["product"] or "").strip().lower()]
        loc = (g["location"] or "").upper()
        if loc:
            here = [x for x in s if (x["location"] or "").upper() == loc]
            pick = here[0] if len(here) == 1 else None
            why = "no dataset at this location" if not here else "several datasets at this location"
        else:
            markets = [x for x in s if x["kind"] == "market" and (x["location"] or "").upper() in ("GLO", "ROW")]
            pick = markets[0] if len(markets) == 1 else (s[0] if len(s) == 1 else None)
            why = "no exact match" if not s else "several possible suppliers"
        if pick:
            link(store, db_id, g["product"], g["unit"], pick["id"], location=g["location"])
            done += 1
        else:
            left.append({"product": g["product"], "location": g["location"], "why": why})
    return {"auto_linked": done, "left_for_review": len(left), "review": left[:100]}
