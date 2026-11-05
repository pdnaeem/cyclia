"""openLCA JSON-LD importer (zip or extracted folder).

Covers databases distributed in this format (USLCI / Federal LCA Commons, Agribalyse, ELCD and many
openLCA Nexus packages) and method-only packages (EF 3.1, ReCiPe and others published for openLCA).
Amounts are converted to each flow's reference unit as openLCA does (amount x unitFactor / propertyFactor).
Inputs without a provider in the same package are kept as "unlinked" for cross-database linking.
"""
import json
import math
import os
import zipfile

from importers import lcia


class _Source:
    def __init__(self, path):
        self.zip = zipfile.ZipFile(path) if zipfile.is_zipfile(path) else None
        self.root = path
        if self.zip:
            self.names = [n for n in self.zip.namelist() if n.endswith(".json")]
        else:
            if not os.path.isdir(path):
                raise ValueError("Choose an openLCA JSON-LD .zip file or its extracted folder.")
            self.names = []
            for d, _, files in os.walk(path):
                for f in files:
                    if f.endswith(".json"):
                        self.names.append(os.path.relpath(os.path.join(d, f), path).replace(os.sep, "/"))

    def folder(self, kind):
        return [n for n in self.names if f"/{kind}/" in "/" + n]

    def load(self, name):
        try:
            if self.zip:
                with self.zip.open(name) as fh:
                    return json.load(fh)
            with open(os.path.join(self.root, name), encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None


def _category_parts(flow):
    cat = flow.get("category")
    if isinstance(cat, dict):
        cat = "/".join(filter(None, (cat.get("categoryPath") or []) + [cat.get("name", "")]))
    parts = [p for p in (cat or "").split("/") if p and p.lower() != "elementary flows"]
    return (parts[0] if parts else ""), ("/".join(parts[1:]) if len(parts) > 1 else "")


def _unc(ex, conv):
    """openLCA uncertainty -> (utype, p1, p2, p3) in reference units (conv = reference amount / given amount)."""
    u = ex.get("uncertainty") or {}
    t = (u.get("distributionType") or "").upper()

    def num(k):
        v = u.get(k)
        return v if isinstance(v, (int, float)) and math.isfinite(v) else None
    if t.startswith("LOG_NORMAL"):
        gsd = num("geomSd")
        if gsd and gsd > 1:
            return 1, math.log(gsd), None, None
    elif t.startswith("NORMAL"):
        sd = num("sd")
        if sd and sd > 0:
            return 2, abs(sd * conv), None, None
    elif t.startswith("TRIANGLE"):
        lo, mode, hi = num("minimum"), num("mode"), num("maximum")
        if None not in (lo, mode, hi) and hi > lo:
            v = sorted([lo * conv, mode * conv, hi * conv])
            return 3, v[0], v[1], v[2]
    elif t.startswith("UNIFORM"):
        lo, hi = num("minimum"), num("maximum")
        if None not in (lo, hi) and hi != lo:
            v = sorted([lo * conv, hi * conv])
            return 4, v[0], v[1], None
    return 0, None, None, None


def _negate(unc):
    if unc[0] in (3, 4):
        vals = sorted(-v for v in unc[1:] if v is not None)
        return (unc[0],) + tuple(vals) + ((None,) if unc[0] == 4 else ())
    return unc


def import_jsonld(store, path, name, progress=lambda *a: None):
    src = _Source(path)
    progress(2, "Reading units")
    unit_factor, group_ref_unit = {}, {}
    for n in src.folder("unit_groups"):
        g = src.load(n) or {}
        for u in g.get("units", []):
            unit_factor[u.get("@id")] = float(u.get("conversionFactor", 1.0))
            if u.get("referenceUnit") or u.get("isRefUnit"):
                group_ref_unit[g.get("@id")] = u.get("name")
    prop_group = {}
    for n in src.folder("flow_properties"):
        p = src.load(n) or {}
        prop_group[p.get("@id")] = (p.get("unitGroup") or {}).get("@id")
    progress(5, "Reading flows")
    flows = {}
    for n in src.folder("flows"):
        f = src.load(n)
        if not f:
            continue
        factors, ref_unit = {}, ""
        for fp in f.get("flowProperties", []):
            pid = (fp.get("flowProperty") or {}).get("@id")
            factors[pid] = float(fp.get("conversionFactor", 1.0))
            if fp.get("referenceFlowProperty") or fp.get("isRefFlowProperty"):
                ref_unit = group_ref_unit.get(prop_group.get(pid), "")
        flows[f["@id"]] = {"name": f.get("name", ""), "type": f.get("flowType", ""), "factors": factors,
                           "ref_unit": ref_unit, "cas": f.get("cas", ""), "comp": _category_parts(f)}
    locations = {}
    for n in src.folder("locations"):
        loc = src.load(n) or {}
        locations[loc.get("@id")] = loc.get("code") or loc.get("name", "")

    def ref_amount(ex):
        fl = flows.get((ex.get("flow") or {}).get("@id"), {})
        uf = unit_factor.get((ex.get("unit") or {}).get("@id"), 1.0)
        pid = (ex.get("flowProperty") or {}).get("@id")
        pf = fl.get("factors", {}).get(pid, 1.0) if pid else 1.0
        return float(ex.get("amount", 0.0)) * uf / (pf or 1.0)

    def elementary_id(fuuid):
        f = flows.get(fuuid, {"name": fuuid, "comp": ("", ""), "ref_unit": "", "cas": ""})
        return store.add_flow(fuuid, f["name"], f["comp"][0], f["comp"][1], f["ref_unit"], f.get("cas", ""))

    procs = src.folder("processes")
    result = {"database": None, "activities": 0, "methods": 0, "warnings": []}
    if procs:
        db_id = store.create_database(name, "openLCA JSON-LD")
        try:
            result.update(_processes(store, db_id, src, procs, flows, locations, ref_amount, elementary_id, progress))
        except Exception:
            store.abort_database(db_id)
            raise
        result["database"] = name
    elif not src.folder("lcia_categories"):
        raise ValueError("This file has neither processes nor impact methods. Is it an openLCA JSON-LD export?")

    cats = src.folder("lcia_categories")
    if cats:
        progress(88, "Reading impact methods")
        cat_method = {}
        for n in src.folder("lcia_methods"):
            m = src.load(n) or {}
            for ic in m.get("impactCategories", []):
                cat_method[ic.get("@id")] = m.get("name", "")
        ids = []
        for n in cats:
            cat = src.load(n)
            if not cat:
                continue
            fam = cat_method.get(cat["@id"]) or (name + " methods")
            mid = store.get_or_create_method(fam, cat.get("name", ""), cat.get("name", ""),
                                             cat.get("refUnit") or cat.get("referenceUnitName", ""), "openLCA JSON-LD")
            rows = []
            for f in cat.get("impactFactors", []):
                fuuid = (f.get("flow") or {}).get("@id")
                fl = flows.get(fuuid) or {"name": (f.get("flow") or {}).get("name", ""), "comp": ("", ""), "factors": {}}
                uf = unit_factor.get((f.get("unit") or {}).get("@id"), 1.0)
                pid = (f.get("flowProperty") or {}).get("@id")
                pf = fl.get("factors", {}).get(pid, 1.0) if pid else 1.0
                loc = (f.get("location") or {}).get("code") or locations.get((f.get("location") or {}).get("@id"), "") \
                    if isinstance(f.get("location"), dict) else ""
                rows.append((fl["name"], fl["comp"][0], fl["comp"][1], loc or "", fuuid,
                             float(f.get("value", 0)) * pf / (uf or 1.0)))
            store.x("DELETE FROM cf_raw WHERE method_id=?", (mid,))
            store.x("DELETE FROM cfs WHERE method_id=?", (mid,))
            lcia.store_raw(store, mid, rows)
            ids.append(mid)
        r = lcia._finish(store, ids, "json-ld")
        result["methods"] = len(ids)
        result["warnings"] += r["warnings"]
    if procs:
        lcia.rematch_all(store)
    progress(100, "Done")
    return result


def _processes(store, db_id, src, procs, flows, locations, ref_amount, elementary_id, progress):
    c = store.conn
    providers, pending, bio, unlinked = {}, [], [], []
    co_products = n_ambiguous = 0
    with store.lock:
        loaded = []
        total = len(procs)
        for i, n in enumerate(procs):
            p = src.load(n)
            if not p:
                continue
            exs = p.get("exchanges", [])
            ref = next((e for e in exs if e.get("quantitativeReference") or e.get("isQuantitativeReference")), None)
            if ref is None:
                continue
            rflow = flows.get((ref.get("flow") or {}).get("@id"), {})
            amt = ref_amount(ref)
            production = -amt if ref.get("isInput") else amt  # waste treatment: the reference is an input
            loc = p.get("location") or {}
            loc = (locations.get(loc.get("@id")) or loc.get("code") or loc.get("name", "")) if isinstance(loc, dict) else str(loc)
            cur = c.execute("INSERT OR IGNORE INTO activities(db_id,key,name,product,location,unit,production,comment,"
                            "product_uuid) VALUES(?,?,?,?,?,?,?,?,?)",
                            (db_id, p["@id"], p.get("name", ""), rflow.get("name", ""), loc, rflow.get("ref_unit", ""),
                             production or 1.0, (p.get("description") or "")[:3000], (ref.get("flow") or {}).get("@id")))
            if cur.rowcount == 0:
                continue
            aid = cur.lastrowid
            lst = providers.setdefault((ref.get("flow") or {}).get("@id"), [])
            lst.append(aid)
            loaded.append((aid, p["@id"], exs, ref, loc))
            if i % 200 == 0:
                progress(8 + int(60 * i / max(total, 1)), f"Reading processes {i:,}/{total:,}")
        progress(70, "Linking supply chains")
        keymap = {k: a for a, k, _, _, _ in loaded}
        for aid, _, exs, ref, loc in loaded:
            for e in exs:
                if e is ref:
                    continue
                fuuid = (e.get("flow") or {}).get("@id")
                ftype = (e.get("flow") or {}).get("flowType") or flows.get(fuuid, {}).get("type", "")
                amt = ref_amount(e)
                if amt == 0:
                    continue
                raw = float(e.get("amount", 0.0)) or 1.0
                unc = _unc(e, amt / raw)
                if ftype == "ELEMENTARY_FLOW":
                    bio.append((aid, elementary_id(fuuid), amt) + unc)
                    continue
                is_input = bool(e.get("isInput"))
                if (ftype == "PRODUCT_FLOW" and not is_input) or (ftype == "WASTE_FLOW" and is_input):
                    co_products += 1
                    continue
                sign = 1.0 if ftype == "PRODUCT_FLOW" else -1.0
                eunc = unc if sign > 0 else _negate(unc)
                # provider: the exchange's defaultProvider; else the only process producing the flow. With several
                # producers and no defaultProvider the input stays unresolved (never the first producer found)
                dp = (e.get("defaultProvider") or {}).get("@id")
                prov = keymap.get(dp)
                cands = providers.get(fuuid) or []
                reason = ""
                if prov is None:
                    if len(cands) == 1:
                        prov = cands[0]
                    else:
                        reason = "ambiguous" if cands else ("supplier not in this import" if dp else "no producer")
                if prov is None:
                    fl = flows.get(fuuid, {})
                    n_ambiguous += reason == "ambiguous"
                    unlinked.append((db_id, aid, fl.get("name") or (e.get("flow") or {}).get("name", ""),
                                     fl.get("ref_unit", ""), sign * amt, loc, fuuid) + eunc
                                    + (reason, json.dumps(cands) if len(cands) > 1 else None))
                    continue
                pending.append((aid, prov, sign * amt) + eunc)
        c.executemany("INSERT INTO tech(output_id,input_id,amount,utype,p1,p2,p3) VALUES(?,?,?,?,?,?,?)", pending)
        c.executemany("INSERT INTO bio(activity_id,flow_id,amount,utype,p1,p2,p3) VALUES(?,?,?,?,?,?,?)", bio)
        c.executemany("INSERT INTO unlinked(db_id,output_id,product,unit,amount,location,link_key,utype,p1,p2,p3,reason,"
                      "candidates) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", unlinked)
        c.commit()
    progress(85, "Building search index")
    store.finish_database(db_id)
    n_act = store.one("SELECT n_activities FROM databases WHERE id=?", (db_id,))["n_activities"]
    warnings = []
    if unlinked:
        n_prod = len({u[2] for u in unlinked})
        warnings.append(f"{len(unlinked)} inputs ({n_prod} products) have no supplier in this file, often because they "
                        "point to another database. Link them under 'Link missing suppliers'.")
    if n_ambiguous:
        warnings.append(f"{n_ambiguous} inputs have no default provider and several processes in the file produce their "
                        "product. Cyclia does not pick one: choose the supplier under 'Link missing suppliers'.")
    if co_products:
        warnings.append(f"{co_products} co-product exchanges were ignored; the database should already be allocated.")
    return {"activities": n_act, "warnings": warnings, "unlinked_inputs": len(unlinked), "ambiguous_inputs": n_ambiguous}


def read_impact_factors(path):
    """Impact categories of an openLCA JSON-LD export with their factors, without storing anything:
    [{"method": family, "category": name, "unit": ref unit, "factors": [{uuid, name, comp, sub, unit, location, value}]}].
    Values are converted to the flow's reference unit, exactly as the importer does."""
    src = _Source(path)
    unit_factor, group_ref_unit = {}, {}
    for n in src.folder("unit_groups"):
        g = src.load(n) or {}
        for u in g.get("units", []):
            unit_factor[u.get("@id")] = float(u.get("conversionFactor", 1.0))
            if u.get("referenceUnit") or u.get("isRefUnit"):
                group_ref_unit[g.get("@id")] = u.get("name")
    prop_group = {}
    for n in src.folder("flow_properties"):
        p = src.load(n) or {}
        prop_group[p.get("@id")] = (p.get("unitGroup") or {}).get("@id")
    flows = {}
    for n in src.folder("flows"):
        f = src.load(n)
        if not f:
            continue
        factors, ref_unit = {}, ""
        for fp in f.get("flowProperties", []):
            pid = (fp.get("flowProperty") or {}).get("@id")
            factors[pid] = float(fp.get("conversionFactor", 1.0))
            if fp.get("referenceFlowProperty") or fp.get("isRefFlowProperty"):
                ref_unit = group_ref_unit.get(prop_group.get(pid), "")
        flows[f["@id"]] = {"name": f.get("name", ""), "factors": factors, "ref_unit": ref_unit, "comp": _category_parts(f)}
    locations = {}
    for n in src.folder("locations"):
        loc = src.load(n) or {}
        locations[loc.get("@id")] = loc.get("code") or loc.get("name", "")
    cat_method = {}
    for n in src.folder("lcia_methods"):
        m = src.load(n) or {}
        for ic in m.get("impactCategories", []):
            cat_method[ic.get("@id")] = m.get("name", "")
    out = []
    for n in src.folder("lcia_categories"):
        cat = src.load(n)
        if not cat:
            continue
        rows = []
        for f in cat.get("impactFactors", []):
            fref = f.get("flow") or {}
            fuuid = fref.get("@id")
            fl = flows.get(fuuid) or {"name": fref.get("name", ""), "comp": _category_parts(fref), "factors": {},
                                      "ref_unit": fref.get("refUnit", "")}
            uf = unit_factor.get((f.get("unit") or {}).get("@id"), 1.0)
            pid = (f.get("flowProperty") or {}).get("@id")
            pf = fl.get("factors", {}).get(pid, 1.0) if pid else 1.0
            loc = ""
            if isinstance(f.get("location"), dict):
                loc = f["location"].get("code") or locations.get(f["location"].get("@id"), "")
            rows.append({"uuid": fuuid, "name": fl["name"], "comp": fl["comp"][0], "sub": fl["comp"][1],
                         "unit": fl.get("ref_unit", ""), "location": loc or "",
                         "value": float(f.get("value", 0)) * pf / (uf or 1.0)})
        out.append({"method": cat_method.get(cat.get("@id"), ""), "category": cat.get("name", ""),
                    "unit": cat.get("refUnit") or cat.get("referenceUnitName", ""), "factors": rows})
    if not out:
        raise ValueError("No impact categories in this file. Export the impact method from openLCA as JSON-LD.")
    return out
