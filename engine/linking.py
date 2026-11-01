"""Cross-database linking.

Imports record every technosphere input whose supplier is not inside the same database (for example
USLCI processes that point to ecoinvent, or ecoinvent links to datasets missing from the folder).
The user links each missing product once to a dataset in any library database; Cyclia converts units
and adds the exchanges to the matrix.
"""
import units


def groups(store, db_id):
    """Unlinked inputs grouped by product (and unit) with the number of uses."""
    return store.q("SELECT product, unit, COUNT(*) AS uses, SUM(CASE WHEN linked_to IS NULL THEN 0 ELSE 1 END) AS linked, "
                   "MAX(linked_to) AS linked_to, GROUP_CONCAT(DISTINCT location) AS locations FROM unlinked "
                   "WHERE db_id=? GROUP BY product, unit ORDER BY (linked>0), uses DESC", (db_id,))


def suggest(store, db_id, product, unit, limit=6):
    hits = store.search_activities(product, None, None, limit=80)
    out = []
    pn = (product or "").strip().lower()
    for h in hits:
        if store.one("SELECT db_id FROM activities WHERE id=?", (h["id"],))["db_id"] == db_id:
            continue
        fac = units.factor(unit, h["unit"]) if unit else 1.0
        if fac is None:
            continue
        score = (2 if (h["product"] or "").lower() == pn else 0) + (1 if h["kind"] == "market" else 0)
        out.append({**h, "factor": fac, "score": score})
    out.sort(key=lambda r: -r["score"])
    return out[:limit]


def link(store, db_id, product, unit, target_id, factor=None):
    t = store.one("SELECT id, unit, db_id FROM activities WHERE id=?", (target_id,))
    if not t:
        raise ValueError("The chosen dataset does not exist.")
    if t["db_id"] == db_id:
        raise ValueError("Choose a dataset from another database.")
    fac = float(factor) if factor not in (None, "") else units.factor(unit, t["unit"]) if unit else 1.0
    if fac is None:
        raise ValueError(f"'{unit}' cannot be converted to '{t['unit']}'. Enter a conversion factor.")
    rows = store.q("SELECT * FROM unlinked WHERE db_id=? AND product=? AND COALESCE(unit,'')=COALESCE(?, '')",
                   (db_id, product, unit))
    if not rows:
        raise ValueError("Nothing to link for that product.")
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


def unlink(store, db_id, product, unit):
    rows = store.q("SELECT id FROM unlinked WHERE db_id=? AND product=? AND COALESCE(unit,'')=COALESCE(?, '')",
                   (db_id, product, unit))
    ids = [r["id"] for r in rows]
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
    """Link every product that has exactly one exact-name match with a convertible unit in another database."""
    done = 0
    for g in groups(store, db_id):
        if g["linked"]:
            continue
        s = [x for x in suggest(store, db_id, g["product"], g["unit"], limit=20)
             if (x["product"] or "").strip().lower() == (g["product"] or "").strip().lower()]
        markets = [x for x in s if x["kind"] == "market" and (x["location"] or "").upper() in ("GLO", "ROW")]
        pick = markets[0] if len(markets) == 1 else (s[0] if len(s) == 1 else None)
        if pick:
            link(store, db_id, g["product"], g["unit"], pick["id"])
            done += 1
    return {"auto_linked": done}
