"""Standards outputs: EN 15804+A2 EPD, PEF most-relevant analysis, ISO 14067 carbon footprint report,
GHG Protocol Product Standard workbook, and an ISO 14044 critical review checklist."""
import re
import time

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

import calc
import credits as authors
import report

MODULES = ["A1", "A2", "A3", "A4", "A5", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "C1", "C2", "C3", "C4", "D"]
COLUMNS = ["A1-A3", "A4", "A5", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "C1", "C2", "C3", "C4", "D"]
CORE = [  # EN 15804+A2 core environmental impact indicators: (abbreviation, name, keywords that identify the category)
    ("GWP-total", "Climate change, total", [("climate change", "total"), ("climate change",)]),
    ("GWP-fossil", "Climate change, fossil", [("climate change", "fossil")]),
    ("GWP-biogenic", "Climate change, biogenic", [("climate change", "biogenic")]),
    ("GWP-luluc", "Climate change, land use and land use change", [("climate change", "land use")]),
    ("ODP", "Ozone depletion", [("ozone depletion",)]),
    ("AP", "Acidification", [("acidification",)]),
    ("EP-freshwater", "Eutrophication, freshwater", [("eutrophication", "freshwater")]),
    ("EP-marine", "Eutrophication, marine", [("eutrophication", "marine")]),
    ("EP-terrestrial", "Eutrophication, terrestrial", [("eutrophication", "terrestrial")]),
    ("POCP", "Photochemical ozone formation", [("photochemical",)]),
    ("ADP-minerals&metals", "Depletion of abiotic resources, minerals and metals", [("minerals",), ("abiotic", "element")]),
    ("ADP-fossil", "Depletion of abiotic resources, fossil fuels", [("fossils",), ("abiotic", "fossil")]),
    ("WDP", "Water use (deprivation potential)", [("water use",), ("water scarcity",), ("water",)]),
]

CORE_UNITS = {"GWP-total": ("co2",), "GWP-fossil": ("co2",), "GWP-biogenic": ("co2",), "GWP-luluc": ("co2",),
              "ODP": ("cfc",), "AP": ("mol h",), "EP-freshwater": ("p eq", "p-eq", "kg p", "po4"), "EP-marine": ("n eq", "n-eq", "kg n"),
              "EP-terrestrial": ("mol n",), "POCP": ("nmvoc",), "ADP-minerals&metals": ("sb",), "ADP-fossil": ("mj",),
              "WDP": ("m3", "m³")}

# EN 15804+A2 Tables 4 to 6: indicators describing resource use, waste categories and output flows.
# (abbreviation, name, table, test on the lower-case "category indicator" text, expected unit tokens)
def _has(*words):
    return lambda t: all(w in t for w in words)


def _nonren(t):
    return "non-renewable" in t or "non renewable" in t or "nonrenewable" in t


INVENTORY = [
    ("PERE", "Renewable primary energy used as energy carrier", "4",
     lambda t: "renewable primary energy" in t and not _nonren(t) and ("excluding" in t or "energy carrier" in t or "as energy" in t), ("mj",)),
    ("PERM", "Renewable primary energy used as raw material", "4",
     lambda t: "renewable primary energy" in t and not _nonren(t) and ("raw material" in t or "as material" in t), ("mj",)),
    ("PERT", "Total use of renewable primary energy", "4",
     lambda t: "renewable primary energy" in t and not _nonren(t) and "total" in t, ("mj",)),
    ("PENRE", "Non-renewable primary energy used as energy carrier", "4",
     lambda t: "primary energy" in t and _nonren(t) and ("excluding" in t or "energy carrier" in t or "as energy" in t), ("mj",)),
    ("PENRM", "Non-renewable primary energy used as raw material", "4",
     lambda t: "primary energy" in t and _nonren(t) and ("raw material" in t or "as material" in t), ("mj",)),
    ("PENRT", "Total use of non-renewable primary energy", "4",
     lambda t: "primary energy" in t and _nonren(t) and "total" in t, ("mj",)),
    ("SM", "Use of secondary material", "4", _has("secondary material"), ("kg",)),
    ("RSF", "Use of renewable secondary fuels", "4", lambda t: "secondary fuel" in t and not _nonren(t), ("mj",)),
    ("NRSF", "Use of non-renewable secondary fuels", "4", lambda t: "secondary fuel" in t and _nonren(t), ("mj",)),
    ("FW", "Net use of fresh water", "4", lambda t: "fresh water" in t or "freshwater use" in t, ("m3", "m³")),
    ("HWD", "Hazardous waste disposed", "5", lambda t: "hazardous waste" in t and "non-hazardous" not in t and "non hazardous" not in t, ("kg",)),
    ("NHWD", "Non-hazardous waste disposed", "5", lambda t: "non-hazardous waste" in t or "non hazardous waste" in t, ("kg",)),
    ("RWD", "Radioactive waste disposed", "5", _has("radioactive waste"), ("kg",)),
    ("CRU", "Components for re-use", "6", lambda t: "re-use" in t or "reuse" in t, ("kg",)),
    ("MFR", "Materials for recycling", "6", _has("materials for recycling"), ("kg",)),
    ("MER", "Materials for energy recovery", "6", _has("energy recovery"), ("kg",)),
    ("EEE", "Exported energy, electricity", "6", lambda t: "exported energy" in t and "electric" in t, ("mj",)),
    ("EET", "Exported energy, thermal", "6", lambda t: "exported energy" in t and ("thermal" in t or "heat" in t), ("mj",)),
]


def match_inventory(results):
    """Which EN 15804+A2 resource, waste and output indicators are among the selected categories. The abbreviation in
    the name (e.g. 'PERE') identifies an indicator first, the wording otherwise."""
    found = {}
    for k, r in enumerate(results):
        raw = f"{r['category']} {r['indicator']}"
        t = raw.lower()
        hit = next((a for a, *_ in INVENTORY if re.search(r"(?<![A-Za-z])" + re.escape(a) + r"(?![A-Za-z])", raw)), None)
        if hit is None:
            hit = next((a for a, _n, _t, test, _u in INVENTORY if test(t)), None)
        if hit and hit not in found:
            found[hit] = k
    return found


def unit_ok(unit, tokens):
    u = (unit or "").lower().replace(" ", "")
    return any(tok.replace(" ", "") in u for tok in tokens)


def module_of(stage):
    s = str(stage or "").strip().upper()
    if re.match(r"^A1\s*[-–]\s*A3", s):
        return "A1-A3"
    m = re.match(r"^(A[1-5]|B[1-7]|C[1-4]|D)\b", s)
    return m.group(1) if m else None


def by_module(result):
    out = []
    for r in result["results"]:
        row = {c: 0.0 for c in COLUMNS}
        unassigned = 0.0
        for b in r["by_stage"]:
            mod = module_of(b["name"])
            if mod in ("A1", "A2", "A3", "A1-A3"):
                row["A1-A3"] += b["impact"]
            elif mod:
                row[mod] += b["impact"]
            else:
                unassigned += b["impact"]
        out.append({"category": r["category"], "indicator": r["indicator"], "unit": r["unit"], "family": r["family"],
                    "modules": row, "unassigned": unassigned, "total_ac": r["total"]})
    return out


def declared_modules(model, result):
    used = set()
    for l in result["lines"]:
        mod = module_of(l["stage"])
        if mod:
            used.add("A1-A3" if mod in ("A1", "A2", "A3") else mod)
    extra = set((model["scope"].get("epd") or {}).get("declared") or [])
    return [c for c in COLUMNS if c in used or c in extra]


def unassigned_stages(result):
    """Stage names that are not EN 15804 modules, with the lines in them (their impacts would fall outside the
    module table)."""
    out = {}
    for l in result["lines"]:
        if not module_of(l["stage"]):
            out.setdefault(l["stage"] or "Unassigned stage", []).append(l["name"])
    return out


def reconcile(result):
    """Largest relative gap between the module table and the LCA result (A-C total and module D)."""
    gap = 0.0
    for m, r in zip(by_module(result), result["results"]):
        ac = sum(v for c, v in m["modules"].items() if c != "D") + m["unassigned"]
        # relative to the gross size of the contributions: a category whose stages cancel to about zero has a total
        # of 0 (round-off cleaned) and module sums of round-off size; dividing by the near-zero total would turn
        # 1e-17 of round-off into a large gap (1.4.0, seen on macOS once tiny scaling factors were no longer cut)
        gross = sum(abs(b["impact"]) for b in r["by_stage"]) + abs(r.get("module_d") or 0)
        scale = max(abs(r["total"]), abs(r.get("module_d") or 0), gross, 1e-300)
        gap = max(gap, abs(ac - r["total"]) / scale, abs(m["modules"]["D"] - (r.get("module_d") or 0)) / scale)
    return gap


_EF = re.compile(r"\bEF\s*v?(\d+)\.(\d+)", re.I)


def ef_reference(families):
    """True when the methods are the EF reference package 3.0 or later (or Cyclia's EN 15804+A2 IPCC split)."""
    ok = []
    for f in families:
        m = _EF.search(f)
        ok.append(bool(m and (int(m.group(1)), int(m.group(2))) >= (3, 0)) or "EN 15804+A2" in f)
    return bool(ok) and all(ok)


def _match_core(results):
    found = {}
    for abbr, _, keysets in CORE:
        for k, r in enumerate(results):
            text = f"{r['category']} {r['indicator']}".lower()
            if any(all(w in text for w in ks) for ks in keysets):
                if abbr == "GWP-total" and any(w in text for w in ("fossil", "biogenic", "land use")):
                    continue
                found[abbr] = k
                break
    return found


def epd_checklist(model, result, profile=None):
    import epd_profiles
    sc = model["scope"] or {}
    epd = sc.get("epd") or {}
    prof = profile or epd_profiles.get(epd.get("profile"))
    dec = declared_modules(model, result)
    core = _match_core(result["results"])
    fams = {r["family"] for r in result["results"]}
    items = []
    add = lambda ok, text, ref: items.append({"ok": bool(ok), "text": text, "ref": ref})
    add(model.get("unit") and model.get("product"), "Declared or functional unit stated", "EN 15804+A2 6.3.2, 6.3.3")
    add(all(m in dec for m in ("A1-A3", "C1", "C2", "C3", "C4", "D")),
        "Modules A1-A3, C1-C4 and D declared (mandatory unless an exception of 5.2 applies)", "EN 15804+A2 5.2")
    un = unassigned_stages(result)
    add(not un, "Every line is in an EN 15804 module (A1 to D)" + (
        f" (not assigned: {', '.join(sorted(un))})" if un else ""), "EN 15804+A2 5.2, 7.2")
    add("A1-A3" in dec or any(c in dec for c in ("A1", "A2", "A3")), "Product stage A1-A3 declared with inventory lines",
        "EN 15804+A2 5.2")
    gap = reconcile(result)
    add(gap < 1e-6, "Module totals reconcile with the LCA result" + (f" (gap {gap * 100:.2g} %)" if gap >= 1e-6 else ""),
        "EN 15804+A2 7.2")
    add(not [c for c in COLUMNS if c in dec and c.startswith("B")] or epd.get("rsl"),
        "Reference service life given when B modules are declared", "EN 15804+A2 6.3.3")
    add(ef_reference(fams), "Characterisation factors of the EF reference package (EF 3.0 or later) for every indicator",
        "EN 15804+A2 Annex C")
    missing = [a for a, _, _ in CORE if a not in core]
    add(not missing, "All core indicators calculated" + (f" (missing: {', '.join(missing)})" if missing else ""),
        "EN 15804+A2 7.2.3")
    add(sc.get("cutoff"), "Cut-off rules stated (1 % per unit process, 5 % per module)", "EN 15804+A2 6.3.6")
    add(sc.get("allocation") or calc.allocation_share(sc) == 1, "Allocation procedure stated", "EN 15804+A2 6.4.3")
    add(sc.get("period"), "Time representativeness of data stated (data not older than 10 years)", "EN 15804+A2 6.3.8.2")
    add(sc.get("geography"), "Geographical representativeness stated", "EN 15804+A2 6.3.8.2")
    add(epd.get("biogenic_product") not in (None, ""), "Biogenic carbon content of the product declared (kg C)",
        "EN 15804+A2 7.2.5")
    add(epd.get("pcr"), "Product category rules (PCR) named", "ISO 14025:2026, ISO/TS 14027")
    add(epd.get("verification"), "Verification (internal or independent external) described", "EN 15804+A2 Table 1, ISO 14025:2026")
    spec = specific_share(result)
    add(spec is not None and any(l.get("data_type") for l in result["lines"]),
        "Share of the GWP result based on supply-chain-specific (primary) data stated" +
        (f" ({spec * 100:.0f} %)" if spec is not None else ""), "ISO 14025:2026 (EPD types)")
    add(epd.get("specific_months"), "Number of months of specific data behind the LCA stated", "ISO 14025:2026 (EPD types)")
    if (epd.get("audience") or "").upper() == "B2C":
        add("independent" in (epd.get("verification") or "").lower() and epd.get("verifier"),
            "Consumer (B2C) EPD: independent third-party verification with the verifier named", "ISO 14025:2026")
    if epd.get("prospective"):
        u = result.get("uncertainty")
        conv = bool(u) and all(m.get("converged") for m in u["methods"])
        add(conv, "Prospective EPD: uncertainty of the results quantified with a converged Monte Carlo run" +
            ("" if conv else (" (the run has not converged; use more iterations)" if u else " (run Monte Carlo in step 4)")),
            "ISO 14025:2026")
    inv = match_inventory(result["results"])
    for table, label in (("4", "Resource use indicators"), ("5", "Waste category indicators"), ("6", "Output flow indicators")):
        need = [a for a, _n, t, *_ in INVENTORY if t == table]
        miss = [a for a in need if a not in inv]
        add(not miss, f"{label} calculated" + (f" (missing: {', '.join(miss)})" if miss else f" ({', '.join(need)})"),
            f"EN 15804+A2 7.2.4, Table {table}")
    bad_units = [f"{a} in {result['results'][k]['unit'] or 'no unit'}" for a, k in core.items()
                 if not unit_ok(result["results"][k]["unit"], CORE_UNITS[a])]
    exp = {a: u for a, _n, _t, _test, u in INVENTORY}
    bad_units += [f"{a} in {result['results'][k]['unit'] or 'no unit'}" for a, k in inv.items()
                  if not unit_ok(result["results"][k]["unit"], exp[a])]
    addl = epd_profiles.match_additional(result["results"])
    bad_units += [f"{a} in {result['results'][k]['unit'] or 'no unit'}" for a, k in addl.items()
                  if not unit_ok(result["results"][k]["unit"], epd_profiles.ADDITIONAL_UNITS[a])]
    add(not bad_units, "Indicator units as required" + (f" (check: {'; '.join(bad_units)})" if bad_units else ""),
        "EN 15804+A2 Tables 3 to 6")
    nocf = [result["results"][k]["category"] for k in list(core.values()) + list(inv.values())
            if result["results"][k]["cfs_matched"] == 0]
    add(not nocf, "Every declared indicator has characterisation factors for the inventory" +
        (f" (none for: {', '.join(nocf)})" if nocf else ""), "EN 15804+A2 Annex C")
    if prof["id"] != "generic":
        fields = epd.get("fields") or {}
        miss_f = [f["label"] for f in prof["fields"] if f.get("required") and not str(fields.get(f["key"], "") or f.get("default", "") or "").strip()]
        add(not miss_f, f"{prof['name']}: required information given" + (f" (missing: {'; '.join(miss_f)})" if miss_f else ""),
            "Programme profile")
        need = prof.get("required_indicators") or []
        if need:
            have = epd_profiles.match_additional(result["results"])
            miss_i = [a for a in need if a not in have]
            add(not miss_i, f"{prof['name']}: required indicators calculated" + (f" (missing: {', '.join(miss_i)})" if miss_i else
                                                                              f" ({', '.join(need)})"), "Programme profile")
        vy = prof.get("validity_years")
        if vy and epd.get("issued") and epd.get("valid_until"):
            try:
                import datetime as _dt
                a_, b_ = _dt.date.fromisoformat(epd["issued"]), _dt.date.fromisoformat(epd["valid_until"])
                add((b_ - a_).days <= vy * 366 and b_ > a_, f"Validity at most {vy} years from the date of issue", "Programme profile")
            except ValueError:
                add(False, "Dates of issue and validity in the form YYYY-MM-DD", "Programme profile")
        elif vy:
            add(False, f"Date of issue and validity (at most {vy} years) given", "Programme profile")
    add(not [c for c in result["checks"] if c["level"] == "error"], "No errors in the Cyclia checks", "ISO 14044 4.5.3")
    ready = all(i["ok"] for i in items)
    return {"ready": ready, "inventory_found": list(inv), "profile": prof["id"], "items": items, "declared": dec, "core_found": list(core), "core_missing": missing,
            "passed": sum(i["ok"] for i in items), "total": len(items)}


def specific_share(result):
    """Share of the GWP-total (or first climate category) result that comes from supply-chain-specific (primary)
    data, over every level of nested models, with credits and module D left out (from the data quality weights)."""
    k = next((i for i, r in enumerate(result["results"]) if "climate" in r["category"].lower() and
              ("total" in r["category"].lower() or "total" in r["indicator"].lower())), None)
    if k is None:
        k = next((i for i, r in enumerate(result["results"]) if "climate" in r["category"].lower()), None)
    if k is None:
        return None
    r = result["results"][k]
    c = next((c for c in (result.get("data_quality") or {}).get("by_category", [])
              if c["category"] == r["category"] and c["family"] == r["family"]), None)
    return c["primary_share"] if c else None


def _cell(v, declared):
    return report.fmt(v) if declared else "ND"


def _groups(result):
    """Indicator group of every result row: core, additional, resource, waste, output or other."""
    import epd_profiles
    core = _match_core(result["results"])
    inv = match_inventory(result["results"])
    add = epd_profiles.match_additional(result["results"])
    g, abbr = {}, {}
    for a, k in core.items():
        g[k], abbr[k] = "core", a
    tables = {a: t for a, _n, t, *_ in INVENTORY}
    for a, k in inv.items():
        if k not in g:
            g[k], abbr[k] = {"4": "resource", "5": "waste", "6": "output"}[tables[a]], a
    for a, k in add.items():
        if k not in g:
            g[k], abbr[k] = "additional", a
    for k in range(len(result["results"])):
        g.setdefault(k, "other")
    return g, abbr


def epd_word(path, model, result, databases, version="", profile=None, profiles_dir=None):
    """Word EPD laid out by a programme profile (epd_profiles). Blocks the EPD when impacts would be missing from the
    module table; otherwise always writes a draft, marked 'not ready for submission' while requirements are open."""
    import epd_profiles
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.shared import Cm, Pt
    sc = model["scope"] or {}
    epd = sc.get("epd") or {}
    prof = profile or epd_profiles.get(epd.get("profile"), profiles_dir)
    fr = prof.get("language") == "fr"
    T = (lambda x: epd_profiles.UI_FR.get(x, x)) if fr else (lambda x: x)
    mods = by_module(result)
    dec = declared_modules(model, result)
    chk = epd_checklist(model, result, prof)
    un = unassigned_stages(result)
    if un:
        raise ValueError("The EPD cannot be written yet: these stages are not EN 15804 modules, so their impacts would be "
                         "missing from the module table: " + "; ".join(f"'{k}' ({len(v)} line(s))" for k, v in un.items()) +
                         ". Rename the stages in step 3 to A1-A3, A4, A5, B1 to B7, C1 to C4 or D.")
    if not any(c in dec for c in ("A1-A3", "A1", "A2", "A3")):
        raise ValueError("The EPD cannot be written yet: no line is in the product stage A1-A3.")
    if reconcile(result) >= 1e-6:
        raise ValueError("The EPD cannot be written because the module table does not add up to the LCA result. "
                         "Calculate the model again; if this message remains, contact support@niellosoft.com and "
                         "attach the project file.")
    fields = epd.get("fields") or {}
    fval = lambda f: str(fields.get(f["key"], "") or f.get("default", "") or "")
    doc = Document()
    doc.styles["Normal"].font.size = Pt(9.5)
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = sec.page_height, sec.page_width
    for s_ in doc.sections:
        s_.left_margin = s_.right_margin = Cm(1.6)
    spec = specific_share(result)
    groups, abbr = _groups(result)
    cols = list(COLUMNS)

    def cell(v, declared):
        if not declared:
            return "ND"
        if prof.get("zero_shown") and v == 0:
            return "0"
        return report.fmt(v)

    def label(k, m):
        a = abbr.get(k)
        if fr and a in epd_profiles.LABELS_FR:
            return f"{epd_profiles.LABELS_FR[a]} ({a})"
        return f"{m['category']}" + (f" ({a})" if a and a not in m["category"] else "")

    def indicator_table(keys, heading):
        if not keys:
            return
        doc.add_heading(T(heading), 2)
        report._table(doc, [T("Indicator"), T("Unit")] + cols,
                      [[label(k, mods[k]), mods[k]["unit"]] + [cell(mods[k]["modules"][c], c in dec) for c in cols]
                       for k in keys], widths=[4.6, 2.0] + [1.32] * len(cols), size=6.5)

    for part in prof["sections"]:
        if part == "title":
            doc.add_heading(T("Environmental Product Declaration (EPD)"), 0)
            report._note(doc, "According to ISO 14025:2026 and EN 15804+A2. Draft generated by Cyclia for verification; not "
                              "valid until verified and published by a programme operator. Cyclia is not a verified EPD tool "
                              "in the sense of ISO 14025:2026, so each EPD needs its own verification.", italic=True)
            if prof["id"] != "generic":
                report._note(doc, f"Layout: {prof['name']}. {prof.get('status', '')}", italic=True)
        elif part == "readiness":
            open_n = sum(1 for i in chk["items"] if not i["ok"])
            report._note(doc, ("Readiness: all requirements of the checklist at the end are met; the draft can go to "
                               "verification." if chk["ready"] else
                               f"Readiness: NOT READY FOR SUBMISSION. {open_n} of {chk['total']} requirements of the "
                               "checklist at the end are still open."), 10, italic=False)
        elif part == "general":
            doc.add_heading(T("General information"), 1)
            rows = [[k, v] for k, v in (prof.get("fixed") or {}).items()]
            rows += [
                ["Product", model["product"] or model["name"]],
                ["Manufacturer", epd.get("manufacturer", "")], ["Production site(s)", epd.get("site", "")]]
            if prof["id"] == "generic":
                rows += [["Programme operator", epd.get("programme", "")], ["Declaration number", epd.get("number", "")],
                         ["Product category rules", epd.get("pcr", "") + (f", version {epd['pcr_version']}" if epd.get("pcr_version") else "")]]
            rows += [["Date of issue", epd.get("issued", time.strftime("%Y-%m-%d"))], ["Valid until", epd.get("valid_until", "")],
                     ["Declared / functional unit", report.fu_text(model)],
                     ["Reference service life", epd.get("rsl", "") or "not declared"]]
            if prof["id"] == "generic":
                rows += [["Type of EPD", epd.get("type", "cradle to gate with modules C1-C4 and module D")],
                         ["Verification", epd.get("verification", "")], ["Verifier", epd.get("verifier", "")]]
            rows += [[f["label"], fval(f)] for f in prof["fields"] if f.get("type") != "textarea"]
            rows += [
                ["Intended audience", {"B2B": "business-to-business", "B2C": "business-to-consumer"}.get(
                    (epd.get("audience") or "").upper(), epd.get("audience") or "business-to-business")],
                ["Share of GWP-total from supply-chain-specific data", f"{spec * 100:.0f} %" if spec is not None else "not stated"],
                ["Months of specific data", epd.get("specific_months", "") or "not stated"],
                ["Prospective EPD", "yes (product not yet on the market; limited validity, re-evaluation after one year)"
                 if epd.get("prospective") else "no"],
                ["Biogenic carbon content of the product (kg C per unit)", epd.get("biogenic_product", "")],
                ["Biogenic carbon content of the packaging (kg C per unit)", epd.get("biogenic_packaging", "")]]
            report._table(doc, [T("Item"), T("Content")], rows, widths=[7, 17])
        elif part == "programme":
            if epd.get("programme_statements"):
                doc.add_heading("Programme information", 1)
                doc.add_paragraph(epd["programme_statements"])
        elif part == "description":
            doc.add_heading(T("Product description"), 1)
            doc.add_paragraph(epd.get("description") or sc.get("fu_description") or "")
            for f in prof["fields"]:
                if f.get("type") == "textarea" and f["key"] not in ("content_declaration",) and fval(f):
                    doc.add_heading(f["label"], 2)
                    doc.add_paragraph(fval(f))
        elif part == "content":
            f = next((x for x in prof["fields"] if x["key"] == "content_declaration"), None)
            if f:
                doc.add_heading(f["label"], 1)
                doc.add_paragraph(fval(f) or "-")
        elif part == "ibu_product":
            doc.add_heading("2. Product", 1)
            doc.add_heading("2.1 Product description / product definition", 2)
            doc.add_paragraph(epd.get("description") or sc.get("fu_description") or "")
            for f in prof["fields"]:
                if f.get("type") == "textarea" and f["key"] not in ("scope", "interpretation", "evidence") and fval(f):
                    doc.add_heading(f["label"], 2)
                    doc.add_paragraph(fval(f))
            for k in ("svhc", "cmr", "biocides"):
                f = next((x for x in prof["fields"] if x["key"] == k), None)
                if f:
                    doc.add_paragraph(f"{f['label']}: {fval(f) or '-'}")
        elif part == "lca_rules":
            doc.add_heading("3. LCA: Calculation rules", 1)
            report._table(doc, ["Item", "Content"], [
                ["3.1 Declared unit", report.fu_text(model) + (f"; conversion to 1 kg: {fields.get('conversion_kg')}"
                                                              if fields.get("conversion_kg") else "")],
                ["3.2 System boundary", ", ".join(dec)], ["3.4 Cut-off criteria", sc.get("cutoff", "")],
                ["3.5 Background data", "; ".join(sorted({l["db"] for l in result["lines"] if l["kind"] == "activity"}))],
                ["3.6 Data quality", sc.get("dq_requirements", "")], ["3.7 Period under review", sc.get("period", "")],
                ["3.8 Allocation", sc.get("allocation", "") or "none"]], widths=[7, 17])
        elif part == "ibu_interpretation":
            f = next((x for x in prof["fields"] if x["key"] == "interpretation"), None)
            doc.add_heading("6. LCA: Interpretation", 1)
            doc.add_paragraph((fval(f) if f else "") or sc.get("conclusions") or "-")
            f = next((x for x in prof["fields"] if x["key"] == "evidence"), None)
            if f and fval(f):
                doc.add_heading("7. Requisite evidence", 1)
                doc.add_paragraph(fval(f))
        elif part == "fdes_health":
            doc.add_heading(T("Health and comfort"), 1)
            for k in ("indoor_air", "soil_water", "comfort"):
                f = next((x for x in prof["fields"] if x["key"] == k), None)
                if f:
                    doc.add_heading(f["label"], 2)
                    doc.add_paragraph(fval(f) or "-")
        elif part == "modules":
            doc.add_heading(T("System boundary: modules declared"), 1)
            report._table(doc, MODULES, [["X" if (m in dec or (m in ("A1", "A2", "A3") and "A1-A3" in dec)) else "ND"
                                          for m in MODULES]], size=8)
            report._note(doc, "X = module declared; ND = module not declared.", italic=True)
        elif part == "indicators":
            if prof.get("grouped_tables"):
                doc.add_heading(T("Environmental impact indicators per declared unit") if not fr else
                                "Résultats de l'analyse du cycle de vie par unité fonctionnelle", 1)
                for grp, head in (("core", "Core environmental impact indicators"),
                                  ("additional", "Additional environmental impact indicators"),
                                  ("resource", "Resource use"), ("waste", "Waste categories"),
                                  ("output", "Output flows"), ("other", "Other indicators")):
                    indicator_table([k for k in range(len(mods)) if groups[k] == grp], head)
            else:
                doc.add_heading("Environmental impact indicators per declared unit", 1)
                report._table(doc, ["Indicator", "Unit"] + cols,
                              [[m["category"], m["unit"]] + [cell(m["modules"][c], c in dec) for c in cols] for m in mods],
                              widths=[4.6, 2.0] + [1.32] * len(cols), size=6.5)
            if chk["core_missing"]:
                report._note(doc, "Core indicators not calculated with the selected methods: " + ", ".join(chk["core_missing"]) +
                             ". Import the EF 3.1 method (ecoinvent LCIA file or the EF package) to complete the declaration.",
                             italic=True)
        elif part == "uncertainty":
            unc = result.get("uncertainty")
            if unc:
                report._note(doc, f"Uncertainty ({unc['iterations']} Monte Carlo iterations, modules A-C): " + "; ".join(
                    f"{r['category']} 95 % interval {report.fmt(m['p2_5'])} to {report.fmt(m['p97_5'])} {r['unit']}"
                    for r, m in zip(result["results"], unc["methods"])) + ".")
        elif part == "resource_note":
            doc.add_heading("Resource use, waste and output flows", 1)
            miss = [a for a, *_ in INVENTORY if a not in chk["inventory_found"]]
            report._note(doc, ("The resource use, waste and output flow indicators of EN 15804+A2 Tables 4 to 6 are in the "
                               "table above." if not miss else
                               "Missing EN 15804+A2 indicators (Tables 4 to 6): " + ", ".join(miss) + ". Import a method "
                               "package that provides them (for example the EN 15804 indicators in the ecoinvent LCIA file) "
                               "and select them before generating the EPD. Output flows such as CRU, MFR and MER can also "
                               "be entered as inventory indicators of the end-of-life lines."))
        elif part == "lca_info":
            doc.add_heading(T("LCA information"), 1)
            used = sorted({l["db"] for l in result["lines"] if l["kind"] == "activity"})
            report._table(doc, [T("Item"), T("Content")], [
                ["Background data", "; ".join(d["name"] + (f" v{d['version']}" if d.get("version") else "") for d in databases
                                              if d["name"] in used) or "-"],
                ["Characterisation", ", ".join(sorted({r["family"] for r in result["results"]}))],
                ["Cut-off rules", sc.get("cutoff", "")], ["Allocation", sc.get("allocation", "") or "none"],
                ["Time representativeness", sc.get("period", "")], ["Geography", sc.get("geography", "")],
                ["Software", authors.short(version)]], widths=[7, 17])
        elif part == "statements":
            st_ = list(epd.get("statements_override") or prof.get("statements") or [])
            if epd.get("programme_statements") and "programme" not in prof["sections"]:
                st_.append(epd["programme_statements"])
            if st_:
                doc.add_heading(T("Statements"), 1)
                for t in st_:
                    doc.add_paragraph(t, style="List Bullet")
        elif part == "checklist":
            doc.add_heading(T("Verification support checklist"), 1)
            report._table(doc, ["Requirement", "Status", "Reference"],
                          [[i["text"], "met" if i["ok"] else "open", i["ref"]] for i in chk["items"]], widths=[14, 3, 7])
        elif part == "references":
            doc.add_heading(T("References"), 1)
            refs = ["EN 15804:2012+A2:2019 Sustainability of construction works. Environmental product declarations. Core "
                    "rules for the product category of construction products.",
                    "ISO 14025:2026 Environmental statements and programmes for products. Environmental product "
                    "declarations (EPDs).", "ISO 14020:2022 Environmental statements and programmes for products. "
                    "Principles and general requirements.", "ISO 14044:2006 Environmental management. Life cycle "
                    "assessment. Requirements and guidelines."]
            if fr:
                refs.insert(1, "NF EN 15804+A2/CN Complément national à la NF EN 15804+A2.")
            for t in refs:
                report._note(doc, t)
    report._footer(doc, version)
    doc.save(path)
    return path


def epd_excel(path, model, result):
    wb = Workbook()
    ws = wb.active
    ws.title = "Indicators"
    dec = declared_modules(model, result)
    bold = Font(bold=True)
    ws.append(["Indicator", "Indicator detail", "Unit"] + COLUMNS + ["Not in a module", "LCA result A-C", "Module D result"])
    for c in ws[1]:
        c.font = bold
    for m, r in zip(by_module(result), result["results"]):
        ws.append([m["category"], m["indicator"], m["unit"]] + [m["modules"][c] if c in dec else "ND" for c in COLUMNS] +
                  [m["unassigned"], r["total"], r.get("module_d") or 0])
    ws2 = wb.create_sheet("Checklist")
    ws2.append(["Requirement", "Status", "Reference"])
    for i in epd_checklist(model, result)["items"]:
        ws2.append([i["text"], "met" if i["ok"] else "open", i["ref"]])
    ws3 = wb.create_sheet("Inventory")
    ws3.append(["Model", "Level", "Stage", "Line", "Amount per unit of model", "Unit", "Amount per declared unit", "Unit",
                "Avoided", "Data type", "Data year", "Supplier / site", "Reference", "Verified", "Data quality (R,C,T,G,Te)",
                "PEF (TeR,GeR,TiR,P)"])
    for x in result.get("foreground") or []:
        ws3.append([x["model"], x["depth"], x["stage"], x["name"], x["amount"], x["unit"], x["per_fu"], x["per_fu_unit"],
                    "yes" if x["avoided"] else "", x["data_type"], x["data_year"], x["supplier"], x["reference"],
                    "yes" if x["verified"] else "", ",".join(map(str, x["pedigree"])),
                    ",".join(map(str, x["pef"])) if x["pef"] else ""])
    for w in (ws, ws2, ws3):
        w.column_dimensions["A"].width = 46
        w.column_dimensions["B"].width = 30
    wb.save(path)
    return path


# ============================================================================ PEF
def _relevant(items, key="impact", share=0.8):
    tot = sum(abs(i[key]) for i in items)
    if not tot:
        return []
    out, cum = [], 0.0
    for i in sorted(items, key=lambda x: -abs(x[key])):
        out.append(dict(i, share=abs(i[key]) / tot))
        cum += abs(i[key]) / tot
        if cum >= share - 1e-12:
            break
    return out


def pef(result):
    """Most relevant impact categories, life cycle stages, processes and elementary flows (PEF method: cumulative
    contribution of at least 80 %, absolute values)."""
    if not result.get("nw_set"):
        raise ValueError("Choose a normalisation and weighting set in step 4 (for example EF 3.1) and calculate again.")
    cats = [{"category": r["category"], "unit": r["unit"], "total": r["total"], "normalised": r.get("normalised"),
             "weighted": r.get("weighted") or 0.0, "k": k} for k, r in enumerate(result["results"])]
    rel = _relevant(cats, "weighted")
    detail = []
    for c in rel:
        r = result["results"][c["k"]]
        detail.append({"category": c["category"], "unit": c["unit"],
                       "stages": _relevant([{"name": b["name"], "impact": b["impact"]} for b in r["by_stage"]
                                            if not b.get("module_d")]),
                       "processes": _relevant(r["processes"]), "flows": _relevant(r["flows"])})
    return {"nw_set": result["nw_set"], "single_score": result.get("single_score"), "categories": cats,
            "relevant_categories": rel, "detail": detail, "missing": result.get("nw_missing") or [],
            "note": "PEF method (Commission Recommendation (EU) 2021/2279, Annex I 6.3): most relevant impact categories "
                    "together contribute at least 80 % of the weighted single score; within each, the most relevant life "
                    "cycle stages, processes and elementary flows contribute at least 80 % (absolute values). Processes "
                    "and flows are taken from the largest contributors listed by the calculation."}


# ============================================================================ ISO 14067 and GHG Protocol
def ghg_split(result):
    out = {"total": None, "fossil": None, "biogenic": None, "luluc": None}
    for r in result["results"]:
        t = f"{r['category']} {r['indicator']}".lower()
        if "climate" not in t and "gwp" not in t and "global warming" not in t:
            continue
        if "fossil" in t:
            out["fossil"] = r
        elif "biogenic" in t:
            out["biogenic"] = r
        elif "land use" in t:
            out["luluc"] = r
        elif out["total"] is None:
            out["total"] = r
    return out


GHG_STAGES = [("Material acquisition and pre-processing", ("A1", "A2", "RAW", "MATERIAL", "SEED", "FERTILI", "FIELD")),
              ("Production", ("A3", "MANUFACTUR", "PRODUCTION", "PROCESSING", "HARVEST", "DRYING")),
              ("Distribution and storage", ("A4", "A5", "DISTRIBUTION", "TRANSPORT", "STORAGE")),
              ("Use", ("B", "USE")), ("End of life", ("C", "END OF LIFE", "DISPOSAL", "WASTE"))]


def ghg_stage(stage):
    s = str(stage or "").upper()
    if s.startswith("D") and module_of(stage) == "D":
        return "Outside the boundary (module D, reported separately)"
    for name, keys in GHG_STAGES:
        for k in keys:
            if (len(k) <= 2 and re.match(rf"^{k}\d?\b", s)) or (len(k) > 2 and k in s):
                return name
    return "Not assigned to a stage"


def iso14067_word(path, model, result, databases, version=""):
    from docx import Document
    from docx.shared import Pt
    sc = model["scope"] or {}
    g = ghg_split(result)
    if not g["total"]:
        raise ValueError("Select a climate change (GWP100) category, e.g. the Cyclia built-in IPCC 2021 method.")
    doc = Document()
    doc.styles["Normal"].font.size = Pt(10)
    doc.add_heading(f"Carbon footprint of a product (CFP) study: {model['name']}", 0)
    report._note(doc, "Prepared according to ISO 14067:2018. Generated by Cyclia; complete the parts marked for the "
                      "practitioner before disclosure.", italic=True)
    doc.add_heading("1 Goal of the study (ISO 14067 6.3.1)", 1)
    doc.add_paragraph(f"{sc.get('goal', '')} Intended application: {sc.get('application', '')}. Intended audience: "
                      f"{sc.get('audience', '')}. Reasons: {sc.get('reasons', '')}")
    doc.add_heading("2 Scope (ISO 14067 6.3)", 1)
    report._table(doc, ["Item", "Content"], [
        ["Functional or declared unit", report.fu_text(model) + (f" ({sc['fu_description']})" if sc.get("fu_description") else "")],
        ["System boundary", report.BOUNDARY_TEXT.get(sc.get("boundary", ""), sc.get("boundary", ""))],
        ["Life cycle stages", ", ".join(s for s in result["stages"])], ["Cut-off criteria", sc.get("cutoff", "")],
        ["Allocation", sc.get("allocation", "") or "none"], ["Time period", sc.get("period", "")],
        ["Geography", sc.get("geography", "")], ["GWP metric", f"GWP100 ({g['total']['family']})"],
        ["Data quality", "Pedigree matrix scores per inventory line (Annex of this report)"]], widths=[6, 11])
    doc.add_heading("3 Life cycle inventory (ISO 14067 6.4)", 1)
    report._table(doc, ["Stage", "Input or output", "Amount", "Unit", "Source"],
                  [[l["stage"], l["name"], report.fmt(l["input_amount"]), l["input_unit"], l["comment"]] for l in result["lines"]],
                  size=8)
    doc.add_heading("4 Results (ISO 14067 6.5, 7.3)", 1)
    rows = [["CFP (total, excluding offsetting)", report.fmt(g["total"]["total"])]]
    for k, label in (("fossil", "Fossil GHG emissions and removals"), ("biogenic", "Biogenic GHG emissions and removals"),
                     ("luluc", "GHG emissions and removals from direct land use change")):
        rows.append([label, report.fmt(g[k]["total"]) if g[k] else "not separated by the selected method"])
    if g["total"]["module_d"]:
        rows.append(["Benefits beyond the system boundary (reported separately, not included)", report.fmt(g["total"]["module_d"])])
    report._table(doc, ["Quantity", "kg CO2-eq per functional unit"], rows, widths=[11, 6])
    report._note(doc, "Offsetting is not included in the CFP (ISO 14067 3.1.1.1, 6.3.8). Aircraft GHG emissions, if any, are "
                      "included in the transport lines and are not reported separately in this draft.")
    k = result["results"].index(g["total"])
    doc.add_heading("Results per life cycle stage", 2)
    report._table(doc, ["Stage", "kg CO2-eq", "Share"],
                  [[b["name"], report.fmt(b["impact"]), f"{report._share(b['impact'], g['total']['total']):.1f} %"]
                   for b in g["total"]["by_stage"] if not b.get("module_d")], widths=[9, 4, 3])
    doc.add_heading("5 Interpretation (ISO 14067 6.6)", 1)
    top = sorted([b for b in g["total"]["by_input"] if not b.get("module_d")], key=lambda b: -abs(b["impact"]))[:5]
    doc.add_paragraph("Largest contributions: " + "; ".join(f"{b['name']} ({report._share(b['impact'], g['total']['total']):.0f} %)"
                                                          for b in top) + ".")
    sens = g["total"]["sensitivity"][:5]
    if sens:
        doc.add_paragraph(f"Sensitivity: a ±{result['sensitivity_pct']:g} % change of the largest inputs changes the CFP by "
                          + "; ".join(f"{s['name']} ±{abs(report._share(s['high'], g['total']['total'])):.1f} %" for s in sens) + ".")
    unc = result.get("uncertainty")
    if unc:
        m = unc["methods"][k]
        doc.add_paragraph(f"Uncertainty ({unc['iterations']} Monte Carlo iterations): 95 % interval {report.fmt(m['p2_5'])} to "
                          f"{report.fmt(m['p97_5'])} kg CO2-eq.")
    doc.add_paragraph(f"Limitations: {sc.get('limitations', '') or 'to be completed by the practitioner'}")
    doc.add_paragraph(f"Conclusions: {sc.get('conclusions', '') or 'to be completed by the practitioner'}")
    doc.add_heading("Annex: data quality", 1)
    report._table(doc, ["Line", "Reliability", "Completeness", "Time", "Geography", "Technology"],
                  [[l["name"]] + [str(x) for x in l["pedigree"]] for l in result["lines"]], size=8)
    report._note(doc, f"Calculated with {authors.short(version)}.", italic=True)
    report._footer(doc, version)
    doc.save(path)
    return path


GASES = [("Carbon dioxide", "carbon dioxide"), ("Methane", "methane"), ("Nitrous oxide", "dinitrogen monoxide"),
         ("Sulfur hexafluoride", "sulfur hexafluoride"), ("Nitrogen trifluoride", "nitrogen fluoride"),
         ("HFCs", "hfc"), ("PFCs", "r-14"), ("PFCs", "hexafluoro")]


def ghg_protocol_excel(path, model, result):
    g = ghg_split(result)
    if not g["total"]:
        raise ValueError("Select a climate change (GWP100) category first.")
    wb = Workbook()
    ws = wb.active
    ws.title = "By stage"
    bold = Font(bold=True)
    fill = PatternFill("solid", fgColor="E3ECE8")
    ws.append([f"GHG Protocol Product Life Cycle Accounting and Reporting Standard: inventory results for {report.fu_text(model)}"])
    ws.append(["Stage", "Total (kg CO2e)", "Fossil (kg CO2e)", "Biogenic (kg CO2e)", "Land use change (kg CO2e)"])
    for c in ws[2]:
        c.font = bold
        c.fill = fill
    stages = {}
    for key in ("total", "fossil", "biogenic", "luluc"):
        if not g[key]:
            continue
        for b in g[key]["by_stage"]:
            st = ghg_stage(b["name"])
            stages.setdefault(st, {"total": 0.0, "fossil": 0.0, "biogenic": 0.0, "luluc": 0.0})[key] += b["impact"]
    order = [s for s, _ in GHG_STAGES] + ["Not assigned to a stage", "Outside the boundary (module D, reported separately)"]
    for st in order:
        if st in stages:
            v = stages[st]
            ws.append([st, v["total"], v["fossil"] if g["fossil"] else "n/a", v["biogenic"] if g["biogenic"] else "n/a",
                       v["luluc"] if g["luluc"] else "n/a"])
    ws.append(["Total (excluding module D)", g["total"]["total"], g["fossil"]["total"] if g["fossil"] else "n/a",
               g["biogenic"]["total"] if g["biogenic"] else "n/a", g["luluc"]["total"] if g["luluc"] else "n/a"])
    ws[ws.max_row][0].font = bold
    ws2 = wb.create_sheet("By gas")
    ws2.append(["Greenhouse gas", "Elementary flow", "Compartment", "Mass", "Unit"])
    for c in ws2[1]:
        c.font = bold
    for f in result["lci"]:
        n = f["name"].lower()
        for label, key in GASES:
            if key in n and f["context"].startswith("air"):
                ws2.append([label, f["name"], f["context"], f["amount"], f["unit"]])
                break
    ws3 = wb.create_sheet("Methodology")
    sc = model["scope"] or {}
    for k, v in (("Functional unit", report.fu_text(model)), ("Boundary", sc.get("boundary", "")),
                 ("Allocation", sc.get("allocation", "")), ("Cut-off", sc.get("cutoff", "")),
                 ("GWP values", g["total"]["family"]), ("Reporting period", sc.get("period", "")),
                 ("Note", "Removals and biogenic emissions are shown separately as the standard requires; offsets are not "
                          "included.")):
        ws3.append([k, v])
    for w in (ws, ws2, ws3):
        w.column_dimensions["A"].width = 52
        w.column_dimensions["B"].width = 34
    wb.save(path)
    return path


# ============================================================================ critical review (ISO 14044)
REVIEW_ITEMS = [
    ("goal", "4.2.2", "Goal: application, reasons, audience and whether comparative assertions are disclosed"),
    ("fu", "4.2.3.2", "Functional unit defined, measurable and consistent with goal and scope"),
    ("boundary", "4.2.3.3", "System boundary defined; unit processes and life cycle stages included or excluded"),
    ("cutoff", "4.2.3.3.3", "Cut-off criteria for initial inclusion of inputs and outputs stated"),
    ("lcia_choice", "4.2.3.4", "Impact categories, indicators and characterisation models selected and justified"),
    ("data_sources", "4.2.3.5", "Types and sources of data documented for every unit process"),
    ("data_quality", "4.2.3.6", "Data quality requirements stated and assessed (time, geography, technology, precision, "
                                "completeness, representativeness)"),
    ("assumptions", "4.2.3.7", "Assumptions and limitations stated"),
    ("allocation", "4.3.4", "Allocation procedure stated, following the ISO 14044 hierarchy"),
    ("validation", "4.3.3.2", "Data validated (e.g. mass and energy balances)"),
    ("sensitivity_cutoff", "4.3.3.4", "System boundary refined through sensitivity (cut-off) analysis"),
    ("lcia_consistent", "4.4.2", "One consistent characterisation method per indicator; factors cover the inventory"),
    ("nw_public", "4.4.5", "No weighting in comparative assertions disclosed to the public"),
    ("significant", "4.5.2", "Significant issues identified (contribution analysis)"),
    ("completeness", "4.5.3.2", "Completeness check"),
    ("sensitivity", "4.5.3.3", "Sensitivity check of significant inputs and choices"),
    ("uncertainty", "4.5.3.3", "Uncertainty analysis of the results"),
    ("consistency", "4.5.3.4", "Consistency check (data sources, accuracy, age, system models)"),
    ("conclusions", "4.5.4", "Conclusions, limitations and recommendations"),
    ("report", "5.2", "Report contains the elements required for third-party reports"),
    ("panel", "6.3", "Critical review by a panel for comparative assertions disclosed to the public"),
]


def review_auto(model, result):
    sc = model["scope"] or {}
    lines = result["lines"] if result else model["inputs"]
    n = len(lines) or 1
    src = sum(1 for l in lines if (l.get("comment") or "").strip()) / n
    rated = sum(1 for l in lines if list(l["pedigree"]) != [3, 3, 3, 3, 3]) / n
    chk = result["checks"] if result else []
    errs = [c for c in chk if c["level"] == "error"]
    comparative = (sc.get("comparative") or "").startswith("Yes")
    a = {}
    a["goal"] = ("met" if all(sc.get(k) for k in ("goal", "application", "audience", "reasons")) else "open",
                 "Goal, application, audience and reasons " + ("given" if all(sc.get(k) for k in ("goal", "application",
                                                                                                "audience", "reasons")) else "incomplete"))
    a["fu"] = ("met" if model.get("unit") and model.get("product") else "open", report.fu_text(model))
    a["boundary"] = ("met" if sc.get("boundary") else "open", sc.get("boundary") or "not stated")
    a["cutoff"] = ("met" if sc.get("cutoff") else "open", sc.get("cutoff") or "not stated")
    a["lcia_choice"] = ("check" if result else "open", ", ".join(sorted({r["family"] for r in result["results"]})) if result
                        else "not calculated")
    a["data_sources"] = ("met" if src >= 0.999 else "open", f"{src:.0%} of lines have a data source note")
    a["data_quality"] = ("met" if rated >= 0.999 else "check" if rated > 0 else "open",
                         f"{rated:.0%} of lines have their own data-quality scores")
    a["assumptions"] = ("met" if sc.get("assumptions") or sc.get("limitations") else "open", "")
    a["allocation"] = ("met" if sc.get("allocation") or calc.allocation_share(sc) == 1 else "open",
                       sc.get("allocation") or ("no allocation" if calc.allocation_share(sc) == 1 else "share used, text missing"))
    mb = [c for c in chk if "Mass balance" in c["message"]]
    a["validation"] = ("check" if mb else "met" if sc.get("main_mass") else "open",
                       mb[0]["message"] if mb else ("mass balance within 10 %" if sc.get("main_mass") else
                                                    "enter the product mass in step 2 to check the mass balance"))
    a["sensitivity_cutoff"] = ("met" if result else "open", "contribution below 1 % flagged in the checks" if result else "")
    fams = {r["family"] for r in result["results"]} if result else set()
    tox = [t for t in (result or {}).get("toxicity_coverage") or [] if t["n_missing"]]
    a["lcia_consistent"] = ("met" if result and len(fams) == 1 and not tox else "check" if result else "open",
                            f"{len(fams)} method family(ies)" + (f"; {len(tox)} toxicity category(ies) incomplete" if tox else ""))
    a["nw_public"] = ("open" if comparative and result and result.get("nw_set") else "met",
                      "weighting used in a public comparison" if comparative and result and result.get("nw_set") else "")
    a["significant"] = ("met" if result else "open", "contribution analysis available" if result else "")
    a["completeness"] = ("met" if result and not errs else "open", f"{len(errs)} error(s) in the checks" if result else "")
    a["sensitivity"] = ("met" if result else "open", f"±{result['sensitivity_pct']:g} % per input and parameter" if result else "")
    a["uncertainty"] = ("met" if result and result.get("uncertainty") else "open",
                        f"{result['uncertainty']['iterations']} Monte Carlo iterations" if result and result.get("uncertainty")
                        else "run an uncertainty analysis in step 4")
    sm = [c for c in chk if "system models" in c["message"]]
    a["consistency"] = ("open" if sm else "met" if result else "open", sm[0]["message"] if sm else "")
    a["conclusions"] = ("met" if sc.get("conclusions") and sc.get("limitations") else "open", "")
    a["report"] = ("check", "Word report created in step 6 follows ISO 14044 clause 5")
    a["panel"] = (("met" if sc.get("review") else "open") if comparative else "met",
                  ("panel described" if sc.get("review") else "panel review required") if comparative else "not a public comparison")
    return a


def review_checklist(model, result):
    auto = review_auto(model, result)
    saved = (model["scope"] or {}).get("review_items") or {}
    rows = []
    for key, clause, text in REVIEW_ITEMS:
        st, ev = auto[key]
        s = saved.get(key) or {}
        rows.append({"key": key, "clause": clause, "text": text, "auto": st, "evidence": ev,
                     "reviewer_status": s.get("status", ""), "reviewer_comment": s.get("comment", ""),
                     "reviewer": s.get("reviewer", "")})
    return {"items": rows, "met": sum(r["auto"] == "met" for r in rows), "total": len(rows)}


def review_excel(path, model, checklist):
    wb = Workbook()
    ws = wb.active
    ws.title = "Critical review"
    ws.append([f"ISO 14044 critical review checklist: {model['name']}"])
    ws.append(["Clause", "Requirement", "Cyclia check", "Evidence", "Reviewer status", "Reviewer comment", "Reviewer"])
    for c in ws[2]:
        c.font = Font(bold=True)
    for r in checklist["items"]:
        ws.append([r["clause"], r["text"], r["auto"], r["evidence"], r["reviewer_status"], r["reviewer_comment"], r["reviewer"]])
    for col, w in zip("ABCDEFG", (9, 60, 12, 46, 16, 50, 18)):
        ws.column_dimensions[col].width = w
    wb.save(path)
    return path
