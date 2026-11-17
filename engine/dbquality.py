"""Database quality and completeness: the checks added in Cyclia 1.10 to the database check (calc.validate_database).

Each check reports what it counted, never a combined score:
7  supplier links: every linking decision with its rule, and links whose supplier geography does not cover the input
8  geography: dataset locations that the ecoinvent topology does not know (they cannot be linked by geography)
9  uncertainty and data quality: share of exchanges with an uncertainty distribution, datasets with a data quality
   record
10 duplicates: datasets with the same name, product, location and unit in one database
11 provenance: where the database came from (file, fingerprint, importer, date) and how its datasets are identified
"""
import geography


def statuses(store, db_id, status):
    """Add the 1.10 checks to the database check through its status(key, label, level, message, **numbers)."""
    where, args = (" WHERE db_id=?", (db_id,)) if db_id else ("", ())
    acts = "SELECT id FROM activities" + where
    # 7 supplier links
    log = store.q("SELECT method, action, rule, n FROM link_log" + where + " AND undone=0" if db_id else
                  "SELECT method, action, rule, n FROM link_log WHERE undone=0", args)
    by = {}
    for r in log:
        if r["action"] != "link":
            continue
        rule = r["rule"] or ""
        k = ("same location" if rule.startswith("same location") else "containing region" if " contains " in rule
             else "rest of the world" if rule.startswith("rest of the world") else "global" if "global" in rule
             else "without geography check" if rule in ("", "chosen by the user") else "other location")
        key = f"{r['method']}: {k}"
        by[key] = by.get(key, 0) + (r["n"] or 0)
    links = store.q("SELECT u.location AS want, a.location AS got, COUNT(*) AS n FROM unlinked u "
                    "JOIN activities a ON a.id=u.linked_to WHERE u.linked_to IS NOT NULL"
                    + (" AND u.db_id=?" if db_id else "") + " GROUP BY u.location, a.location", args)
    outside = [r for r in links if (r["want"] or "").strip() and geography.relation(r["want"], r["got"])[0]
               in ("other", "inside", "overlaps")]
    n_out = sum(r["n"] for r in outside)
    n_links = sum(r["n"] for r in links)
    status("links", "Supplier links", "ok" if not n_out else "warning",
           (f"{n_links} inputs linked to a supplier in another dataset group"
            + (": " + ", ".join(f"{v} {k}" for k, v in sorted(by.items())) if by else "")
            + (f". {n_out} of them have a supplier whose geography does not cover the input's location (e.g. "
               f"{outside[0]['want']} supplied from {outside[0]['got']}); check them in the linking decisions."
               if n_out else ".") if n_links else "No input has been linked across datasets."),
           linked=n_links, by_rule=by, outside_geography=n_out,
           outside_examples=[f"{r['want']} -> {r['got']} ({r['n']})" for r in outside[:10]])
    # 8 geography
    locs = store.q("SELECT COALESCE(location,'') AS loc, COUNT(*) AS n FROM activities" + where + " GROUP BY 1", args)
    unknown = sorted(((r["loc"], r["n"]) for r in locs if r["loc"] and not geography.known(r["loc"])),
                     key=lambda t: -t[1])
    none = sum(r["n"] for r in locs if not r["loc"])
    total = sum(r["n"] for r in locs)
    status("geography", "Geography", "ok" if not unknown and not none else "note",
           (f"Every dataset location is in the ecoinvent topology ({len(locs)} locations)." if not unknown and not none
            else "; ".join(x for x in (
                f"{sum(n for _, n in unknown)} datasets at {len(unknown)} locations not in the ecoinvent topology "
                f"(e.g. {', '.join(l for l, _ in unknown[:5])}): suppliers for them are chosen only by exact location"
                if unknown else "",
                f"{none} datasets without a location" if none else "") if x) + "."),
           locations=len(locs), unknown_locations=[{"location": l, "datasets": n} for l, n in unknown[:30]],
           without_location=none, datasets=total)
    # 9 uncertainty and data quality
    t = store.one(f"SELECT COUNT(*) AS n, SUM(CASE WHEN COALESCE(utype,0)>0 THEN 1 ELSE 0 END) AS u FROM tech "
                  f"WHERE output_id IN ({acts})", args)
    b = store.one(f"SELECT COUNT(*) AS n, SUM(CASE WHEN COALESCE(utype,0)>0 THEN 1 ELSE 0 END) AS u FROM bio "
                  f"WHERE activity_id IN ({acts})", args)
    dq = store.one(f"SELECT COUNT(*) AS n FROM activity_dq WHERE activity_id IN ({acts})", args)["n"]
    share_t = (t["u"] or 0) / t["n"] if t["n"] else 0.0
    share_b = (b["u"] or 0) / b["n"] if b["n"] else 0.0
    status("uncertainty", "Uncertainty and data quality", "ok" if (share_t or share_b) else "note",
           f"{share_t * 100:.0f} % of technosphere and {share_b * 100:.0f} % of elementary exchanges carry an uncertainty "
           f"distribution; {dq} of {total} datasets have a data quality record. Exchanges without a distribution are "
           "fixed values in Monte Carlo runs.",
           technosphere_with_uncertainty=share_t, elementary_with_uncertainty=share_b, datasets_with_dq=dq)
    # 10 duplicates
    dup = store.q("SELECT db_id, name, product, COALESCE(location,'') AS location, unit, COUNT(*) AS n FROM activities"
                  + where + " GROUP BY db_id, name, product, location, unit HAVING COUNT(*) > 1 ORDER BY n DESC LIMIT 50",
                  args)
    n_dup = sum(r["n"] for r in dup)
    status("duplicates", "Duplicate datasets", "ok" if not dup else "warning",
           ("No two datasets of a database share name, product, location and unit." if not dup else
            f"{len(dup)} groups of datasets ({n_dup} datasets) share name, product, location and unit, e.g. "
            f"'{dup[0]['name']}' ({dup[0]['location'] or 'no location'}, {dup[0]['n']} times). A search or a link can "
            "pick either; their keys tell them apart."),
           duplicate_groups=len(dup), examples=[{k: r[k] for k in ("name", "product", "location", "n")} for r in dup[:20]])
    # 11 provenance
    dbs = store.q("SELECT * FROM databases" + (" WHERE id=?" if db_id else ""), args)
    prov = [{"database": d["name"], "source": d.get("source") or "", "file": d.get("source_path") or "",
             "sha256": d.get("source_sha256") or "", "importer": d.get("importer_version") or "",
             "imported": d.get("imported_at") or "", "version": d.get("version") or "",
             "system_model": d.get("system_model") or ""} for d in dbs]
    no_key = store.one("SELECT COUNT(*) AS n FROM activities" + (where + " AND" if where else " WHERE")
                       + " COALESCE(key,'')=''", args)["n"]
    lacking = [p["database"] for p in prov if not (p["sha256"] and p["importer"])]
    status("provenance", "Provenance", "ok" if not lacking and not no_key else "warning",
           ("Every database records its source file, SHA-256 fingerprint, importer and import date, and every dataset "
            "keeps its identifier from the source." if not lacking and not no_key else
            "; ".join(x for x in (
                f"no source fingerprint or importer recorded for {', '.join(lacking[:5])} (imported before 1.3 or built "
                "in Cyclia)" if lacking else "",
                f"{no_key} datasets without a source identifier" if no_key else "") if x) + "."),
           databases=prov, datasets_without_key=no_key)


def dataset_provenance(store, act_id):
    """Where one dataset comes from: its database and import, its identifier in the source, the linking decisions
    that gave its inputs a supplier, and its edit history when it was built or changed in Cyclia."""
    a = store.one("SELECT a.*, d.name AS db, d.source, d.version, d.system_model, d.source_path, d.source_sha256, "
                  "d.importer_version, d.imported_at, d.licence FROM activities a JOIN databases d ON d.id=a.db_id "
                  "WHERE a.id=?", (act_id,))
    if not a:
        raise ValueError("That dataset does not exist.")
    links = store.q("SELECT u.product, u.unit, u.location, u.amount, t.name AS supplier, t.location AS supplier_location, "
                    "d.name AS supplier_db FROM unlinked u LEFT JOIN activities t ON t.id=u.linked_to "
                    "LEFT JOIN databases d ON d.id=t.db_id WHERE u.output_id=?", (act_id,))
    for r in links:
        e = store.one("SELECT time, method, rule, author FROM link_log WHERE db_id=? AND product=? AND action='link' "
                      "AND undone=0 AND COALESCE(location,'')=COALESCE(?,'') ORDER BY id DESC LIMIT 1",
                      (a["db_id"], r["product"], r["location"]))
        r["decision"] = e
    hist = []
    item = store.one("SELECT uuid FROM custom_items WHERE ref_id=? AND kind='process'", (act_id,))
    if item:
        hist = store.q("SELECT time, action, author FROM custom_history WHERE item=? ORDER BY id", (item["uuid"],))
    return {"dataset": {k: a[k] for k in ("id", "name", "product", "location", "unit", "key", "product_uuid")},
            "database": {k: a[k] for k in ("db", "source", "version", "system_model", "licence", "source_path",
                                            "source_sha256", "importer_version", "imported_at")},
            "inputs_linked_across": links, "history": hist,
            "geography": geography.name(a["location"]) or ("special" if (a["location"] or "").upper() in
                                                             ("GLO", "ROW", "ROE") else "not in the topology")}


def excel(path, check, decisions):
    """The database check as a workbook: one sheet with every check, one with the numbers, the linking decisions."""
    import json
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Checks"
    ws.append(["Check", "Status", "Result"])
    for x in check.get("statuses", []):
        ws.append([x["label"], x["level"], x["message"]])
    ws.append([])
    ws.append(["Verdict", "", check.get("verdict", "")])
    wn = wb.create_sheet("Details")
    wn.append(["Check", "Number", "Value"])
    for x in check.get("statuses", []):
        for k, v in x.items():
            if k in ("key", "label", "level", "message"):
                continue
            wn.append([x["label"], k, v if isinstance(v, (int, float, str)) or v is None else json.dumps(v, default=str)])
    if decisions:
        wd = wb.create_sheet("Linking decisions")
        wd.append(["Time", "Action", "How", "Product", "Unit", "Location", "Supplier", "Supplier location", "Factor",
                   "Rule", "Author", "Inputs", "Undone"])
        for d in decisions:
            wd.append([d["time"], d["action"], d["method"], d["product"], d["unit"], d["location"], d.get("target_name"),
                       d.get("target_location"), d["factor"], d["rule"], d["author"], d["n"], bool(d["undone"])])
    for sh in wb.worksheets:
        for col, w in zip("ABCDEFGHIJKLM", (34, 14, 90, 30, 10, 12, 40, 14, 10, 50, 14, 8, 8)):
            sh.column_dimensions[col].width = w
    wb.save(path)
