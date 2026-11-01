"""Impact assessment methods, flow mapping, normalisation and weighting.

Characterisation factors are first stored as they were given ("raw": canonical name, compartment,
subcompartment, optional location and flow UUID) and then matched to the elementary flows in the
library. Matching is repeated whenever a database or a mapping file is added, so the order of imports
does not matter.

Matching order: flow UUID, then canonical name + compartment + subcompartment, then (for a raw factor
without subcompartment) every subcompartment of that compartment. A flow mapping file adds factors for
flows of another nomenclature (e.g. FEDEFL or EF flows to ecoinvent names) via a conversion factor.
"""
import csv
import io

from openpyxl import load_workbook

from canon import canon, canon_context, canon_name


def _norm(s):
    return str(s).strip().lower() if s is not None else ""


def store_raw(store, method_id, rows):
    """rows: iterable of (name, comp, sub, location, uuid, value). Replaces existing raw factors."""
    batch = []
    for name, comp, sub, loc, uuid, value in rows:
        cn = canon_name(name)
        if comp:
            cc, cs = canon_context(comp, sub or "")
            if not (sub or "").strip() and "/" not in str(comp):
                cs = ""  # no subcompartment given: the factor applies to every subcompartment
        else:
            cc, cs = "", ""
        loc = (loc or "").strip()
        if loc.upper() in ("GLO", "GLOBAL", "WORLD"):
            loc = ""
        batch.append((method_id, cn, cc, cs, loc, (uuid or None), float(value)))
    with store.lock:
        store.conn.executemany("INSERT INTO cf_raw VALUES(?,?,?,?,?,?,?)", batch)
        store.conn.commit()
    return len(batch)


def rematch(store, method_ids=None):
    """(Re)build matched factors from raw factors and mappings. Returns per-method counts."""
    where = ""
    args = []
    if method_ids:
        where = f" AND r.method_id IN ({','.join('?' * len(method_ids))})"
        args = list(method_ids)
    c = store.conn
    with store.lock:
        # 1. exact flow UUID
        c.execute("INSERT OR IGNORE INTO cfs SELECT r.method_id, f.id, r.value FROM cf_raw r JOIN flows f ON f.uuid=r.flow_uuid "
                  "WHERE r.flow_uuid IS NOT NULL AND r.location=''" + where, args)
        # 2. canonical name + context with explicit subcompartment
        c.execute("INSERT OR IGNORE INTO cfs SELECT r.method_id, f.id, r.value FROM cf_raw r JOIN flows f "
                  "ON f.c_name=r.c_name AND (r.c_comp='' OR f.c_comp=r.c_comp) AND f.c_sub=r.c_sub "
                  "WHERE r.c_sub!='' AND r.location=''" + where, args)
        # 3. no subcompartment given: every subcompartment
        c.execute("INSERT OR IGNORE INTO cfs SELECT r.method_id, f.id, r.value FROM cf_raw r JOIN flows f "
                  "ON f.c_name=r.c_name AND (r.c_comp='' OR f.c_comp=r.c_comp) "
                  "WHERE r.c_sub='' AND r.location=''" + where, args)
        # No fallback from "unspecified" to other subcompartments: ecoinvent's own results give no factor to, e.g.,
        # long-term or ocean emissions when the method lists only "unspecified" (checked against ecoinvent 3.x).
        # 4. regional factors
        c.execute("INSERT OR IGNORE INTO cfs_regional SELECT r.method_id, f.id, r.location, r.value FROM cf_raw r JOIN flows f "
                  "ON (f.uuid=r.flow_uuid) OR (r.flow_uuid IS NULL AND f.c_name=r.c_name AND (r.c_comp='' OR f.c_comp=r.c_comp) "
                  "AND (r.c_sub='' OR f.c_sub=r.c_sub)) WHERE r.location!=''" + where, args)
        # 5. mapped flows inherit the target's factor x conversion factor
        mwhere = where.replace("r.method_id", "cf.method_id")
        c.execute("INSERT OR IGNORE INTO cfs SELECT cf.method_id, fs.id, cf.value * m.factor FROM flow_mapping m "
                  "JOIN flows fs ON (m.s_uuid IS NOT NULL AND fs.uuid=m.s_uuid) OR (m.s_uuid IS NULL AND fs.c_name=m.s_name "
                  "AND fs.c_comp=m.s_comp AND (m.s_sub='' OR fs.c_sub=m.s_sub)) "
                  "JOIN flows ft ON (m.t_uuid IS NOT NULL AND ft.uuid=m.t_uuid) OR (m.t_uuid IS NULL AND ft.c_name=m.t_name "
                  "AND ft.c_comp=m.t_comp AND (m.t_sub='' OR ft.c_sub=m.t_sub)) "
                  "JOIN cfs cf ON cf.flow_id=ft.id WHERE fs.id!=ft.id" + mwhere, args)
        # 6. mapped flows whose target exists only in the method (e.g. a FEDEFL name not present in any database)
        rwhere = where
        c.execute("INSERT OR IGNORE INTO cfs SELECT r.method_id, fs.id, r.value * m.factor FROM flow_mapping m "
                  "JOIN flows fs ON (m.s_uuid IS NOT NULL AND fs.uuid=m.s_uuid) OR (m.s_uuid IS NULL AND fs.c_name=m.s_name "
                  "AND fs.c_comp=m.s_comp AND (m.s_sub='' OR fs.c_sub=m.s_sub)) "
                  "JOIN cf_raw r ON ((m.t_uuid IS NOT NULL AND r.flow_uuid=m.t_uuid) OR (r.c_name=m.t_name AND "
                  "(r.c_comp='' OR m.t_comp='' OR r.c_comp=m.t_comp) AND (r.c_sub='' OR m.t_sub='' OR r.c_sub=m.t_sub))) "
                  "WHERE r.location=''" + rwhere, args)
        store._bump_lib()  # characterisation changed: cached results must be recomputed
        c.commit()
    out = {}
    for r in store.q("SELECT r.method_id, COUNT(*) AS n, SUM(CASE WHEN EXISTS(SELECT 1 FROM flows f WHERE "
                     "(f.uuid=r.flow_uuid) OR (f.c_name=r.c_name AND (r.c_comp='' OR f.c_comp=r.c_comp) AND "
                     "(r.c_sub='' OR f.c_sub=r.c_sub))) THEN 0 ELSE 1 END) AS unmatched FROM cf_raw r "
                     "WHERE 1=1" + where + " GROUP BY r.method_id", args):
        out[r["method_id"]] = {"raw": r["n"], "unmatched": r["unmatched"] or 0}
    return out


def rematch_all(store):
    return rematch(store, None)


def _finish(store, method_ids, source_label):
    counts = rematch(store, method_ids)
    raw = sum(v["raw"] for v in counts.values())
    unmatched = sum(v["unmatched"] for v in counts.values())
    warn = []
    if unmatched:
        warn.append(f"{unmatched} of {raw} factors refer to flows that are not (yet) in your databases. That is normal "
                    "for large methods; they are kept and matched automatically when you add databases or a flow mapping.")
    return {"methods": len(method_ids), "factors": raw, "factors_matched": raw - unmatched,
            "factors_unmatched": unmatched, "warnings": warn}


def _rows_to_methods(store, rows, source):
    """rows: dicts with family, category, indicator, unit, name, comp, sub, cf, uuid, location."""
    groups = {}
    for r in rows:
        key = (str(r["family"]).strip(), str(r["category"]).strip(), str(r["indicator"] or r["category"]).strip())
        if key not in groups:
            groups[key] = {"unit": r.get("unit", ""), "rows": []}
        groups[key]["rows"].append((r["name"], r["comp"], r["sub"], r.get("location", ""), r.get("uuid"), float(r["cf"])))
    ids = []
    for (fam, cat, ind), g in groups.items():
        mid = store.get_or_create_method(fam, cat, ind, g["unit"], source)
        store.x("DELETE FROM cf_raw WHERE method_id=?", (mid,))
        store.x("DELETE FROM cfs WHERE method_id=?", (mid,))
        store.x("DELETE FROM cfs_regional WHERE method_id=?", (mid,))
        store_raw(store, mid, g["rows"])
        ids.append(mid)
    return ids


def import_ecoinvent_lcia_xlsx(store, path, progress=lambda *a: None):
    progress(2, "Opening Excel file")
    wb = load_workbook(path, read_only=True, data_only=True)
    sheets = {s.lower(): s for s in wb.sheetnames}
    cf_sheet = next((sheets[k] for k in sheets if k in ("cfs", "cf", "characterization factors")), None)
    if not cf_sheet:
        raise ValueError(f"No 'CFs' sheet found. Sheets in this file: {', '.join(wb.sheetnames)}")
    units = {}
    unit_sheet = next((sheets[k] for k in sheets if k in ("indicators", "units", "impact categories")), None)
    if unit_sheet:
        it = wb[unit_sheet].iter_rows(values_only=True)
        head = [_norm(h) for h in next(it)]
        idx = {n: head.index(n) for n in ("method", "category", "indicator") if n in head}
        iu = next((i for i, h in enumerate(head) if "unit" in h), None)
        if len(idx) == 3 and iu is not None:
            for row in it:
                if row and row[idx["method"]]:
                    units[(str(row[idx["method"]]), str(row[idx["category"]]), str(row[idx["indicator"]]))] = str(row[iu] or "")
    it = wb[cf_sheet].iter_rows(values_only=True)
    head = [_norm(h) for h in next(it)]

    def need(*names):
        for n in names:
            if n in head:
                return head.index(n)
        raise ValueError(f"Column '{names[0]}' missing in the CFs sheet. Found: {head}")
    im, ic, ii = need("method"), need("category"), need("indicator")
    iname, icomp = need("name", "elementary flow", "flow name"), need("compartment")
    isub, icf = need("subcompartment", "sub-compartment"), need("cf", "characterization factor", "factor")
    iloc = next((head.index(n) for n in ("location", "geography", "region", "country") if n in head), None)
    rows = []
    for row in it:
        if not row or row[im] is None or row[icf] is None:
            continue
        try:
            float(row[icf])
        except (TypeError, ValueError):
            continue
        key = (str(row[im]), str(row[ic]), str(row[ii]))
        rows.append({"family": key[0], "category": key[1], "indicator": key[2], "unit": units.get(key, ""),
                     "name": row[iname], "comp": row[icomp], "sub": row[isub] or "", "cf": row[icf],
                     "location": str(row[iloc] or "") if iloc is not None else ""})
        if len(rows) % 50000 == 0:
            progress(min(80, 5 + len(rows) // 10000), f"Reading factors ({len(rows):,})")
    progress(85, "Matching factors to flows")
    res = _finish(store, _rows_to_methods(store, rows, "ecoinvent LCIA implementation"), "xlsx")
    progress(100, "Methods imported")
    return res


CSV_TEMPLATE = ("method,category,indicator,unit,flow_name,compartment,subcompartment,cf,flow_uuid,location\n"
                "My method,climate change,GWP100,kg CO2-eq,\"Carbon dioxide, fossil\",air,,1,,\n")


def _read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        text = fh.read()
    try:
        dialect = csv.Sniffer().sniff(text[:4000], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    fields = {_norm(f): f for f in reader.fieldnames or []}
    return reader, fields, getattr(dialect, "delimiter", ",")


def _num(v, semicolon):
    v = (v or "").strip()
    if semicolon:
        v = v.replace(",", ".")
    return float(v)


def import_cf_csv(store, path, progress=lambda *a: None):
    reader, fields, delim = _read_csv(path)
    for req in ("method", "category", "indicator", "flow_name", "compartment", "cf"):
        if req not in fields:
            raise ValueError(f"CSV is missing column '{req}'. Expected: {CSV_TEMPLATE.splitlines()[0]}")
    rows = []
    for n, r in enumerate(reader, start=2):
        g = lambda k: (r.get(fields.get(k, ""), "") or "").strip()
        if not g("cf"):
            continue
        try:
            cf = _num(g("cf"), delim == ";")
        except ValueError:
            raise ValueError(f"Row {n}: the factor '{g('cf')}' is not a number.")
        rows.append({"family": g("method"), "category": g("category"), "indicator": g("indicator"), "unit": g("unit"),
                     "name": g("flow_name"), "comp": g("compartment"), "sub": g("subcompartment"), "cf": cf,
                     "uuid": g("flow_uuid") or None, "location": g("location")})
    if not rows:
        raise ValueError("The CSV has no factor rows.")
    res = _finish(store, _rows_to_methods(store, rows, "CSV import"), "csv")
    progress(100, "Methods imported")
    return res


NW_TEMPLATE = ("method,category,indicator,set,normalisation,weighting\n"
               "EF v3.1,climate change,global warming potential (GWP100),EF 3.1 (person-year),8.1E+03,0.2106\n")


def import_nw_csv(store, path, progress=lambda *a: None):
    """normalised = result / normalisation ; weighted = normalised x weighting. Either may be empty."""
    reader, fields, delim = _read_csv(path)
    for req in ("method", "category", "set"):
        if req not in fields:
            raise ValueError(f"CSV is missing column '{req}'. Expected: {NW_TEMPLATE.splitlines()[0]}")
    methods = store.q("SELECT id, family, category, indicator FROM methods")
    full = {(_norm(m["family"]), _norm(m["category"]), _norm(m["indicator"])): m["id"] for m in methods}
    by_cat = {}
    for m in methods:
        by_cat.setdefault((_norm(m["family"]), _norm(m["category"])), []).append(m["id"])
    rows, unmatched = [], []
    for r in reader:
        g = lambda k: (r.get(fields.get(k, ""), "") or "").strip()
        key = (_norm(g("method")), _norm(g("category")))
        ind = _norm(g("indicator"))
        ids = [full[key + (ind,)]] if ind and key + (ind,) in full else by_cat.get(key, [])
        if not ids:
            unmatched.append(f"{g('method')} / {g('category')}")
            continue
        try:
            n = _num(g("normalisation"), delim == ";") if g("normalisation") else None
            w = _num(g("weighting"), delim == ";") if g("weighting") else None
        except ValueError:
            raise ValueError(f"Non-numeric factor in the row for {g('category')}.")
        if n == 0:
            raise ValueError(f"The normalisation value for {g('category')} is zero.")
        for mid in ids:
            rows.append((mid, g("set") or "default", n, w))
    with store.lock:
        store.conn.executemany("INSERT OR REPLACE INTO nw VALUES(?,?,?,?)", rows)
        store.conn.commit()
    progress(100, "Factors imported")
    return {"factors": len(rows),
            "warnings": [f"{len(unmatched)} rows match no imported method (first: {unmatched[0]}). Import the method "
                         "first, with the same names."] if unmatched else []}


MAPPING_TEMPLATE = ("source_name,source_compartment,source_subcompartment,source_uuid,target_name,target_compartment,"
                    "target_subcompartment,target_uuid,factor\n"
                    "Carbon dioxide,emission/air,,,\"Carbon dioxide, fossil\",air,unspecified,,1\n")


def _split_context(ctx):
    parts = [p for p in str(ctx or "").replace("\\", "/").split("/") if p]
    if not parts:
        return "", ""
    head = parts[0].lower()
    if head in ("emission", "emissions", "elementary flows") and len(parts) > 1:
        return parts[1], "/".join(parts[2:])
    if head in ("resource", "resources"):
        return "resource", "/".join(parts[1:])
    return parts[0], "/".join(parts[1:])


def import_mapping_csv(store, path, progress=lambda *a: None):
    """Flow mapping: the Cyclia template or the FEDEFL/GLAD mapping format (SourceFlowName, SourceFlowContext,
    SourceFlowUUID, TargetFlowName, TargetFlowContext, TargetFlowUUID, ConversionFactor)."""
    reader, fields, delim = _read_csv(path)
    fedefl = "sourceflowname" in fields
    if not fedefl and not {"source_name", "target_name"} <= set(fields):
        raise ValueError("Unknown mapping format. Use the Cyclia template or a FEDEFL/GLAD mapping file.")
    rows = []
    for r in reader:
        g = lambda k: (r.get(fields.get(k, ""), "") or "").strip()
        if fedefl:
            sc, ss = _split_context(g("sourceflowcontext"))
            tc, ts = _split_context(g("targetflowcontext"))
            sname, suuid, tname, tuuid, fac = (g("sourceflowname"), g("sourceflowuuid"), g("targetflowname"),
                                               g("targetflowuuid"), g("conversionfactor"))
        else:
            sc, ss, tc, ts = g("source_compartment"), g("source_subcompartment"), g("target_compartment"), g("target_subcompartment")
            sname, suuid, tname, tuuid, fac = g("source_name"), g("source_uuid"), g("target_name"), g("target_uuid"), g("factor")
        if not sname or not (tname or tuuid):
            continue
        try:
            fac = _num(fac, delim == ";") if fac else 1.0
        except ValueError:
            raise ValueError(f"Mapping for '{sname}': conversion factor '{fac}' is not a number.")
        s_c = canon(sname, sc, ss)
        t_c = canon(tname, tc, ts)
        rows.append(("fedefl" if fedefl else "csv", s_c[0], s_c[1], s_c[2] if ss else "", suuid or None,
                     t_c[0], t_c[1], t_c[2] if ts else "", tuuid or None, fac))
    if not rows:
        raise ValueError("The mapping file has no usable rows.")
    with store.lock:
        store.conn.executemany("INSERT INTO flow_mapping(source,s_name,s_comp,s_sub,s_uuid,t_name,t_comp,t_sub,t_uuid,factor) "
                               "VALUES(?,?,?,?,?,?,?,?,?,?)", rows)
        store.conn.commit()
    before = store.one("SELECT COUNT(*) AS n FROM cfs")["n"]
    rematch_all(store)
    after = store.one("SELECT COUNT(*) AS n FROM cfs")["n"]
    progress(100, "Mapping applied")
    return {"mappings": len(rows), "factors_added": after - before, "warnings": []}


# ----------------------------------------------------------------------------- built-in method
# IPCC AR6 WG1 (2021) Table 7.15 / 7.SM.7, GWP100. Split following the EN 15804+A2 / EF structure
# (fossil, biogenic, land use and land use change). Covers CO2, CH4, N2O and ten major fluorinated gases.
_AR6 = {"Sulfur hexafluoride": 25200, "Nitrogen fluoride": 17400, "Methane, tetrafluoro-, R-14": 7380,
        "Ethane, hexafluoro-, HFC-116": 12400, "Methane, trifluoro-, HFC-23": 14600, "Methane, difluoro-, HFC-32": 771,
        "Ethane, pentafluoro-, HFC-125": 3740, "Ethane, 1,1,1,2-tetrafluoro-, HFC-134a": 1530,
        "Ethane, 1,1,1-trifluoro-, HFC-143a": 5810, "Ethane, 1,1-difluoro-, HFC-152a": 164}
BUILTIN_FAMILY = "Cyclia built-in: IPCC 2021 GWP100 (EN 15804+A2 split)"
BUILTIN_NOTE = ("GWP100 values from IPCC AR6 WG1 (2021). Includes CO2, CH4 (fossil 29.8, non-fossil 27.0), N2O (273) and "
                "ten fluorinated gases; other halocarbons are not characterised. Biogenic CO2 uptake (-1) and emission (+1) "
                "follow the EN 15804+A2 approach. Use EF 3.1 for formal EPD work.")


def builtin_rows():
    fossil = [("Carbon dioxide, fossil", "air", 1.0), ("carbon dioxide (fossil)", "air", 1.0),
              ("Methane, fossil", "air", 29.8), ("methane (fossil)", "air", 29.8),
              ("Dinitrogen monoxide", "air", 273.0), ("nitrous oxide", "air", 273.0)]
    fossil += [(n, "air", v) for n, v in _AR6.items()]
    biogenic = [("Carbon dioxide, non-fossil", "air", 1.0), ("carbon dioxide (biogenic)", "air", 1.0),
                ("Carbon dioxide, in air", "natural resource", -1.0), ("carbon dioxide (biogenic)", "natural resource", -1.0),
                ("Methane, non-fossil", "air", 27.0), ("methane (biogenic)", "air", 27.0)]
    luluc = [("Carbon dioxide, from soil or biomass stock", "", 1.0), ("carbon dioxide (land use change)", "air", 1.0),
             ("Carbon dioxide, to soil or biomass stock", "", -1.0), ("Methane, from soil or biomass stock", "", 29.8),
             ("methane (land use change)", "air", 29.8)]
    return {"climate change: fossil": fossil, "climate change: biogenic": biogenic,
            "climate change: land use and land use change": luluc, "climate change: total": fossil + biogenic + luluc}


def install_builtin(store):
    ids = []
    for cat, rows in builtin_rows().items():
        mid = store.get_or_create_method(BUILTIN_FAMILY, cat, "GWP100", "kg CO2-eq", "Cyclia built-in", BUILTIN_NOTE)
        store.x("DELETE FROM cf_raw WHERE method_id=?", (mid,))
        store.x("DELETE FROM cfs WHERE method_id=?", (mid,))
        store_raw(store, mid, [(n, c, "", "", None, v) for n, c, v in rows])
        ids.append(mid)
    rematch(store, ids)
    return ids
