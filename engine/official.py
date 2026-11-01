"""Official reference data and imports that replace screening values.

1. EF 3.1 normalisation and weighting factors, as published by the JRC:
   * normalisation: Andreasi Bassi S., Biganzoli F., Ferrara N., Amadei A., Valente A., Sala S., Ardente F. (2023)
     Updated characterisation and normalisation factors for the Environmental Footprint 3.1 method.
     JRC130796, Publications Office of the European Union, Table 10 (global, per person, reference year 2010);
   * weighting: Sala S., Cerutti A.K., Pant R. (2018) Development of a weighting approach for the Environmental
     Footprint. JRC106545, Table 31 (final weighting factors including robustness, scaled to 100), the set used
     by the EF method (Commission Recommendation (EU) 2021/2279).
   They are matched to the categories of an imported EF 3.1 method (ecoinvent LCIA file, openLCA package, CSV).

2. Characterisation factors from any table keyed by CAS number (official USEtox 2.x results, other
   published factor lists): the user maps the columns once, flows are matched by CAS number and compartment,
   then by name.
"""
import csv
import io
import re

from canon import canon_context, canon_name

EF31_SET = "EF 3.1 (JRC, global per person, weighted)"
EF31_SOURCE = ("Normalisation: JRC130796 (Andreasi Bassi et al. 2023), Table 10. Weighting: JRC106545 (Sala et al. 2018), "
               "Table 31, as used in the EF method (Recommendation (EU) 2021/2279).")
# key, normalisation factor per person, weighting factor (%), unit of the normalisation factor, matcher
EF31 = [
    ("Climate change", 7.55e3, 21.06, "kg CO2 eq",
     lambda t: "climate change" in t and not any(w in t for w in ("fossil", "biogenic", "land use", "luluc"))),
    ("Ozone depletion", 5.23e-2, 6.31, "kg CFC-11 eq", lambda t: "ozone depletion" in t),
    ("Human toxicity, cancer", 1.73e-5, 2.13, "CTUh",
     lambda t: "human toxicity" in t and ("cancer" in t or "carcinogenic" in t) and "non" not in t),
    ("Human toxicity, non-cancer", 1.29e-4, 1.84, "CTUh",
     lambda t: "human toxicity" in t and ("non-cancer" in t or "non-carcinogenic" in t or "non cancer" in t)),
    ("Particulate matter", 5.95e-4, 8.96, "disease incidence", lambda t: "particulate" in t),
    ("Ionising radiation, human health", 4.22e3, 5.01, "kBq U235 eq", lambda t: "ionising" in t or "ionizing" in t),
    ("Photochemical ozone formation, human health", 4.09e1, 4.78, "kg NMVOC eq",
     lambda t: "photochemical" in t and ("ozone" in t or "oxidant" in t)),
    ("Acidification", 5.56e1, 6.20, "mol H+ eq", lambda t: "acidification" in t),
    ("Eutrophication, terrestrial", 1.77e2, 3.71, "mol N eq", lambda t: "eutrophication" in t and "terrestrial" in t),
    ("Eutrophication, freshwater", 1.61, 2.80, "kg P eq", lambda t: "eutrophication" in t and "freshwater" in t),
    ("Eutrophication, marine", 1.95e1, 2.96, "kg N eq", lambda t: "eutrophication" in t and "marine" in t),
    ("Ecotoxicity, freshwater", 5.67e4, 1.92, "CTUe", lambda t: "ecotoxicity" in t and "freshwater" in t),
    ("Land use", 8.19e5, 7.94, "pt", lambda t: "land use" in t and "climate" not in t),
    ("Water use", 1.15e4, 8.51, "m3 world eq deprived", lambda t: "water use" in t or "water scarcity" in t),
    ("Resource use, minerals and metals", 6.36e-2, 7.55, "kg Sb eq",
     lambda t: ("minerals" in t or "metals" in t) and ("resource" in t or "material" in t or "depletion" in t)),
    ("Resource use, fossils", 6.50e4, 8.32, "MJ",
     lambda t: ("fossil" in t and ("resource" in t or "energy" in t or "depletion" in t)) or "non-renewable" in t),
]


def ef_families(store):
    return [r["family"] for r in store.q("SELECT DISTINCT family FROM methods WHERE family LIKE '%EF%' "
                                          "OR family LIKE '%Environmental Footprint%' ORDER BY family")]


def install_ef31_nw(store, family):
    """Attach the EF 3.1 normalisation and weighting factors to the categories of one method family."""
    meths = store.q("SELECT id, category, indicator, unit FROM methods WHERE family=?", (family,))
    if not meths:
        raise ValueError(f"No method family '{family}'. Import EF 3.1 first (ecoinvent LCIA file or the EF package).")
    matched, rows = [], []
    for key, nf, wf, unit, fn in EF31:
        cands = []
        for m in meths:
            t = f"{m['category']} {m['indicator']}".lower()
            if not fn(t):
                continue
            if re.search(r"\b(organics|inorganics)\b", t) or re.search(r"toxicity.*\bmetals\b", t):
                continue  # EF 3.1 toxicity sub-indicators are not normalised separately
            cands.append(m)
        if cands:
            m = min(cands, key=lambda x: len(x["category"]) + len(x["indicator"]))
            rows.append((m["id"], EF31_SET, nf, wf / 100.0))
            matched.append({"ef": key, "category": m["category"], "indicator": m["indicator"], "unit": m["unit"],
                            "normalisation": nf, "weighting_percent": wf})
    if not rows:
        raise ValueError(f"None of the EF 3.1 categories was recognised in '{family}'.")
    with store.lock:
        store.conn.execute("DELETE FROM nw WHERE set_name=? AND method_id IN (SELECT id FROM methods WHERE family=?)",
                           (EF31_SET, family))
        store.conn.executemany("INSERT OR REPLACE INTO nw VALUES(?,?,?,?)", rows)
        store.conn.commit()
    missing = [k for k, *_ in EF31 if k not in {x["ef"] for x in matched}]
    return {"set": EF31_SET, "matched": matched, "missing": missing, "source": EF31_SOURCE}


# ============================================================================ factor tables keyed by CAS number
def norm_cas(v):
    """'000124-38-9', '124-38-9' and 124389 all become '124-38-9'; anything else returns ''."""
    if v is None:
        return ""
    s = str(v).strip()
    if re.fullmatch(r"\d+(\.0)?", s):
        s = s.split(".")[0]
        if len(s) < 5:
            return ""
        s = f"{s[:-3]}-{s[-3:-1]}-{s[-1]}"
    m = re.fullmatch(r"0*(\d{1,7})-(\d{2})-(\d)", s)
    if not m:
        return ""
    a, b, c = m.groups()
    digits = (a + b)[::-1]
    if sum((i + 1) * int(d) for i, d in enumerate(digits)) % 10 != int(c):
        return ""  # failed CAS check digit
    return f"{int(a)}-{b}-{c}"


def _sheet_rows(path, sheet=None, limit=None):
    if path.lower().endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb[sheet] if sheet and sheet in wb.sheetnames else wb.worksheets[0]
        out = []
        for r in ws.iter_rows(values_only=True):
            out.append(["" if v is None else v for v in r])
            if limit and len(out) >= limit:
                break
        return wb.sheetnames, ws.title, out
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
        text = fh.read()
    try:
        dialect = csv.Sniffer().sniff(text[:4000], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect=dialect))
    return [], "", rows[:limit] if limit else rows


def _guess_comp(h):
    h = h.lower()
    if "air" in h:
        sub = "urban air close to ground" if "urban" in h else "non-urban air or from high stacks" if (
            "rural" in h or "continental" in h) else "unspecified"
        return "air", sub
    if "sea" in h or "ocean" in h or "marine" in h:
        return "water", "ocean"
    if "water" in h:
        return "water", "surface water"
    if "soil" in h:
        return "soil", "agricultural" if "agri" in h else "unspecified"
    return "", ""


def preview_table(path, sheet=None):
    sheets, title, rows = _sheet_rows(path, sheet, limit=400)
    if not rows:
        raise ValueError("The file is empty.")
    head_i = next((i for i, r in enumerate(rows[:40]) if any("cas" in str(c).lower() for c in r)), 0)
    head = [str(c).strip() for c in rows[head_i]]
    cols = []
    for j, h in enumerate(head):
        sample = [r[j] for r in rows[head_i + 1:head_i + 6] if j < len(r)]
        filled = [v for v in sample if str(v).strip() != ""]
        numeric = sum(1 for v in filled if isinstance(v, (int, float)) or re.fullmatch(r"[-+]?[\d.]+(e[-+]?\d+)?", str(v).strip(), re.I))
        comp, sub = _guess_comp(h)
        cols.append({"index": j, "header": h, "sample": [str(v)[:40] for v in sample[:3]], "numeric": bool(filled) and numeric * 2 >= len(filled),
                     "compartment": comp, "subcompartment": sub})
    cas_col = next((c["index"] for c in cols if "cas" in c["header"].lower()), None)
    name_col = next((c["index"] for c in cols if re.search(r"\bname\b|substance|chemical", c["header"].lower())), None)
    return {"sheets": sheets, "sheet": title, "header_row": head_i + 1, "columns": cols, "cas_col": cas_col,
            "name_col": name_col, "rows_preview": [[str(v)[:30] for v in r[:12]] for r in rows[head_i:head_i + 6]]}


def import_cas_table(store, path, mapping, progress=lambda *a: None):
    """mapping: sheet, header_row (1-based), cas_col, name_col, family, columns: [{index, category, indicator, unit,
    compartment, subcompartment}]. Every factor is matched to library flows with the same CAS number in that
    compartment; without a CAS match the substance name is used (and re-matched when new databases arrive)."""
    from importers import lcia
    _, _, rows = _sheet_rows(path, mapping.get("sheet"))
    h = int(mapping.get("header_row") or 1)
    cas_col, name_col = mapping.get("cas_col"), mapping.get("name_col")
    if cas_col in (None, "") and name_col in (None, ""):
        raise ValueError("Choose the CAS column, the name column, or both.")
    cols = [c for c in mapping.get("columns") or [] if c.get("category") and c.get("compartment")]
    if not cols:
        raise ValueError("Map at least one factor column to an impact category and a compartment.")
    family = str(mapping.get("family") or "").strip()
    if not family:
        raise ValueError("Give the method a name, e.g. USEtox 2.14 (official).")
    by_cas = {}
    for f in store.q("SELECT name, compartment, subcompartment, cas FROM flows WHERE cas IS NOT NULL AND cas!=''"):
        k = norm_cas(f["cas"])
        if k:
            by_cas.setdefault(k, []).append(f)
    groups, stats = {}, {"rows": 0, "by_cas": 0, "by_name": 0, "skipped": 0}
    for n, r in enumerate(rows[h:], start=h + 1):
        cas = norm_cas(r[int(cas_col)]) if cas_col not in (None, "") and int(cas_col) < len(r) else ""
        name = str(r[int(name_col)]).strip() if name_col not in (None, "") and int(name_col) < len(r) else ""
        if not cas and not name:
            continue
        stats["rows"] += 1
        for c in cols:
            j = int(c["index"])
            if j >= len(r) or r[j] in ("", None):
                continue
            try:
                v = float(str(r[j]).replace(",", ".")) if not isinstance(r[j], (int, float)) else float(r[j])
            except ValueError:
                stats["skipped"] += 1
                continue
            comp, sub = canon_context(c["compartment"], c.get("subcompartment") or "")
            key = (family, c["category"], c.get("indicator") or c["category"])
            g = groups.setdefault(key, {"unit": c.get("unit", ""), "rows": []})
            hits = [f for f in by_cas.get(cas, []) if canon_context(f["compartment"], f["subcompartment"])[0] == comp]
            if hits:
                for f in {(f["name"], f["compartment"]) for f in hits}:
                    g["rows"].append((f[0], f[1], c.get("subcompartment") or "", "", None, v))
                stats["by_cas"] += 1
            elif name:
                g["rows"].append((name, comp, c.get("subcompartment") or "", "", None, v))
                stats["by_name"] += 1
        if stats["rows"] % 500 == 0:
            progress(min(80, 5 + stats["rows"] // 100), f"Reading factors ({stats['rows']:,} substances)")
    if not groups:
        raise ValueError("No factors were read. Check the header row and the mapped columns.")
    ids = []
    for (fam, cat, ind), g in groups.items():
        mid = store.get_or_create_method(fam, cat, ind, g["unit"], "factor table (CAS)", mapping.get("note") or "")
        for t in ("cf_raw", "cfs", "cfs_regional"):
            store.x(f"DELETE FROM {t} WHERE method_id=?", (mid,))
        lcia.store_raw(store, mid, g["rows"])
        ids.append(mid)
    progress(85, "Matching factors to flows")
    res = lcia._finish(store, ids, "cas")
    res.update(stats)
    res["warnings"] = [f"{stats['by_cas']:,} factors matched by CAS number, {stats['by_name']:,} by substance name."] + \
        res["warnings"]
    progress(100, "Factors imported")
    return res
