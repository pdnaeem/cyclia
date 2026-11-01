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
    return [c for c in COLUMNS if c in used or c in extra or c == "A1-A3"]


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


def epd_checklist(model, result):
    sc = model["scope"] or {}
    epd = sc.get("epd") or {}
    dec = declared_modules(model, result)
    core = _match_core(result["results"])
    fams = {r["family"] for r in result["results"]}
    items = []
    add = lambda ok, text, ref: items.append({"ok": bool(ok), "text": text, "ref": ref})
    add(model.get("unit") and model.get("product"), "Declared or functional unit stated", "EN 15804+A2 6.3.2, 6.3.3")
    add(all(m in dec for m in ("A1-A3", "C1", "C2", "C3", "C4", "D")),
        "Modules A1-A3, C1-C4 and D declared (mandatory unless an exception of 5.2 applies)", "EN 15804+A2 5.2")
    add(not [c for c in COLUMNS if c not in dec and c.startswith("B")] or epd.get("rsl"),
        "Reference service life given when B modules are declared", "EN 15804+A2 6.3.3")
    add(any("EF" in f or "EN 15804" in f for f in fams), "Characterisation factors of the EF reference package (EF 3.1)",
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
    add(epd.get("pcr"), "Product category rules (PCR) named", "ISO 14025 6.7.1")
    add(epd.get("verification"), "Verification (internal or independent external) described", "EN 15804+A2 Table 1, ISO 14025 8")
    add(not [c for c in result["checks"] if c["level"] == "error"], "No errors in the Cyclia checks", "ISO 14044 4.5.3")
    return {"items": items, "declared": dec, "core_found": list(core), "core_missing": missing,
            "passed": sum(i["ok"] for i in items), "total": len(items)}


def _cell(v, declared):
    return report.fmt(v) if declared else "ND"


def epd_word(path, model, result, databases, version=""):
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.shared import Cm, Pt
    sc = model["scope"] or {}
    epd = sc.get("epd") or {}
    mods = by_module(result)
    dec = declared_modules(model, result)
    chk = epd_checklist(model, result)
    doc = Document()
    doc.styles["Normal"].font.size = Pt(9.5)
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = sec.page_height, sec.page_width
    for s in doc.sections:
        s.left_margin = s.right_margin = Cm(1.6)
    doc.add_heading("Environmental Product Declaration", 0)
    report._note(doc, "According to ISO 14025 and EN 15804+A2. Draft generated by Cyclia for verification; not valid until "
                      "verified and published by a programme operator.", italic=True)
    doc.add_heading("General information", 1)
    report._table(doc, ["Item", "Content"], [
        ["Product", model["product"] or model["name"]],
        ["Manufacturer", epd.get("manufacturer", "")], ["Production site(s)", epd.get("site", "")],
        ["Programme operator", epd.get("programme", "")], ["Declaration number", epd.get("number", "")],
        ["Product category rules", epd.get("pcr", "")], ["Date of issue", epd.get("issued", time.strftime("%Y-%m-%d"))],
        ["Valid until", epd.get("valid_until", "")], ["Declared / functional unit", report.fu_text(model)],
        ["Reference service life", epd.get("rsl", "") or "not declared"],
        ["Type of EPD", epd.get("type", "cradle to gate with modules C1-C4 and module D")],
        ["Verification", epd.get("verification", "")], ["Verifier", epd.get("verifier", "")],
        ["Biogenic carbon content of the product (kg C per unit)", epd.get("biogenic_product", "")],
        ["Biogenic carbon content of the packaging (kg C per unit)", epd.get("biogenic_packaging", "")]], widths=[7, 17])
    doc.add_heading("Product description", 1)
    doc.add_paragraph(epd.get("description") or sc.get("fu_description") or "")
    doc.add_heading("System boundary: modules declared", 1)
    report._table(doc, MODULES, [["X" if (m in dec or (m in ("A1", "A2", "A3") and "A1-A3" in dec)) else "ND"
                                  for m in MODULES]], size=8)
    report._note(doc, "X = module declared; ND = module not declared.", italic=True)
    doc.add_heading("Environmental impact indicators per declared unit", 1)
    cols = [c for c in COLUMNS]
    report._table(doc, ["Indicator", "Unit"] + cols,
                  [[m["category"], m["unit"]] + [_cell(m["modules"][c], c in dec) for c in cols] for m in mods],
                  widths=[4.6, 2.0] + [1.32] * len(cols), size=6.5)
    core = _match_core(result["results"])
    if chk["core_missing"]:
        report._note(doc, "Core indicators not calculated with the selected methods: " + ", ".join(chk["core_missing"]) +
                     ". Import the EF 3.1 method (ecoinvent LCIA file or the EF package) to complete the declaration.",
                     italic=True)
    doc.add_heading("Resource use, waste and output flows", 1)
    report._note(doc, "EN 15804+A2 also requires the inventory indicators PERE, PERM, PERT, PENRE, PENRM, PENRT, SM, RSF, "
                      "NRSF, FW, HWD, NHWD, RWD, CRU, MFR, MER, EEE and EET. Import a method package that provides them "
                      "(for example the EN 15804 indicators in the ecoinvent LCIA file) and select them before generating "
                      "the EPD; they then appear in the table above.")
    doc.add_heading("LCA information", 1)
    used = sorted({l["db"] for l in result["lines"] if l["kind"] == "activity"})
    report._table(doc, ["Item", "Content"], [
        ["Background data", "; ".join(d["name"] + (f" v{d['version']}" if d.get("version") else "") for d in databases
                                      if d["name"] in used) or "-"],
        ["Characterisation", ", ".join(sorted({r["family"] for r in result["results"]}))],
        ["Cut-off rules", sc.get("cutoff", "")], ["Allocation", sc.get("allocation", "") or "none"],
        ["Time representativeness", sc.get("period", "")], ["Geography", sc.get("geography", "")],
        ["Software", authors.short(version)]], widths=[7, 17])
    doc.add_heading("Verification support checklist", 1)
    report._table(doc, ["Requirement", "Status", "Reference"],
                  [[i["text"], "met" if i["ok"] else "open", i["ref"]] for i in chk["items"]], widths=[14, 3, 7])
    doc.add_heading("References", 1)
    for t in ("EN 15804:2012+A2:2019 Sustainability of construction works. Environmental product declarations. Core rules "
              "for the product category of construction products.", "ISO 14025:2006 Environmental labels and declarations. "
              "Type III environmental declarations.", "ISO 14044:2006 Environmental management. Life cycle assessment. "
              "Requirements and guidelines."):
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
    ws.append(["Indicator", "Indicator detail", "Unit"] + COLUMNS)
    for c in ws[1]:
        c.font = bold
    for m in by_module(result):
        ws.append([m["category"], m["indicator"], m["unit"]] + [m["modules"][c] if c in dec else "ND" for c in COLUMNS])
    ws2 = wb.create_sheet("Checklist")
    ws2.append(["Requirement", "Status", "Reference"])
    for i in epd_checklist(model, result)["items"]:
        ws2.append([i["text"], "met" if i["ok"] else "open", i["ref"]])
    ws3 = wb.create_sheet("Inventory")
    ws3.append(["Stage", "Line", "Amount", "Unit", "Data source", "Data quality (R,C,T,G,Te)"])
    for l in result["lines"]:
        ws3.append([l["stage"], l["name"], l["input_amount"], l["input_unit"], l["comment"], ",".join(map(str, l["pedigree"]))])
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
