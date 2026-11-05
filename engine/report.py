"""Report generation: ISO 14044-structured Word report and Excel results workbook."""
import datetime
import io
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.shared import Cm, Pt, RGBColor  # noqa: E402
from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Font, PatternFill  # noqa: E402

from calc import PEDIGREE_LABELS  # noqa: E402
import credits as authors  # noqa: E402

APP = "Cyclia"
APPROACH_TEXT = {"": "-", "attributional": "attributional", "consequential": "consequential"}
REVIEW_TEXT = {"": "not reviewed (draft)", "internal": "internal review", "external": "external critical review by an expert",
               "panel": "critical review by a panel of interested parties (ISO 14044 6.4, ISO 14071)",
               "verified": "independently verified (e.g. EPD programme operator)"}
BOUNDARY_TEXT = {
    "cradle-to-gate": "cradle-to-gate (raw material extraction up to the factory gate)",
    "cradle-to-grave": "cradle-to-grave (raw material extraction, production, use and end of life)",
    "cradle-to-cradle": "cradle-to-cradle (including recycling back into production)",
    "gate-to-gate": "gate-to-gate (only the processes inside the studied facility)",
}
PALETTE = ["#2f5d50", "#b8861f", "#3d7ab8", "#8a6fb0", "#b0556f", "#5f8f3a", "#7a7a7a", "#c46a2b",
           "#4f9a94", "#9c8a4a", "#6b5b95", "#88a65e"]


def fmt(x):
    if x is None:
        return "-"
    if x == 0:
        return "0"
    a = abs(x)
    if a >= 1e4 or a < 0.01:
        return f"{x:.3e}"
    return f"{x:.4g}"


def _share(part, total):
    return 100.0 * part / total if total else 0.0


def fu_text(model):
    return f"{fmt(model['amount'])} {model['unit']} of {model['product'] or model['name']}".strip()


def methods_paragraph(model, result, databases, version=""):
    s = model["scope"] or {}
    used = {l["db"] for l in result["lines"] if l["kind"] == "activity"}
    dbs = "; ".join(
        d["name"] + (f" v{d['version']}" if d.get("version") else "") +
        (f", {d['system_model']} system model" if d.get("system_model") else "")
        for d in databases if d["name"] in used) or "no background database"
    fams = sorted({r["family"] for r in result["results"]})
    cats = ", ".join(r["category"] for r in result["results"])
    boundary = BOUNDARY_TEXT.get(s.get("boundary", ""), s.get("boundary") or "as defined by the authors")
    txt = (f"A life cycle assessment was carried out following ISO 14040:2006 and ISO 14044:2006. "
           f"The functional unit was {fu_text(model)}"
           f"{' (' + s['fu_description'] + ')' if s.get('fu_description') else ''}. "
           f"The system boundary was {boundary}. ")
    if s.get("geography") or s.get("period"):
        txt += (f"The study represents {s.get('geography') or 'the stated geography'}"
                f"{' for ' + s['period'] if s.get('period') else ''}. ")
    stages = [st for st in result.get("stages", []) if st != "Unassigned stage"]
    txt += (f"Foreground inventory data were compiled for {len(result['lines'])} flows"
            f"{' across the stages ' + ', '.join(stages) if stages else ''}; background processes were "
            f"modelled with {dbs}. ")
    if s.get("allocation"):
        txt += f"Multi-functionality was handled as follows: {s['allocation']}. "
    if result.get("allocation_share", 1) < 1:
        txt += f"{result['allocation_share'] * 100:g} % of the system burdens were allocated to the studied product. "
    if any(l["avoided"] for l in result["lines"]):
        txt += "Avoided products were credited by system expansion. "
    if s.get("cutoff"):
        txt += f"Cut-off criteria: {s['cutoff']}. "
    txt += f"Life cycle impact assessment used {', '.join(fams)} for the categories {cats}. "
    if result.get("nw_set"):
        txt += f"Normalisation and weighting used the factor set '{result['nw_set']}'. "
    txt += (f"Calculations used the matrix method (Heijungs and Suh, 2002) in the open-source software {authors.short(version)}. "
            "Data quality was scored with the pedigree matrix (Weidema et al., 2013). ")
    unc = result.get("uncertainty")
    if unc:
        if unc.get("mode") == "full":
            txt += (f"Uncertainty of background exchanges and foreground data was propagated by Monte Carlo simulation "
                    f"with {unc['iterations']} iterations. ")
        else:
            txt += f"Foreground data uncertainty was propagated by Monte Carlo simulation with {unc['iterations']} iterations. "
    txt += (f"A sensitivity check varied each input by ±{result.get('sensitivity_pct', 10):g} %, and completeness and "
            "consistency checks followed ISO 14044 section 4.5.3.")
    return txt


def _chart(result, by="input", fmt_="png", dpi=None):
    res = result["results"]
    if by == "stage":
        names = result["stages"]
        get = lambda r, j: next((b["impact"] for b in r["by_stage"] if b["name"] == names[j]), 0.0)
    else:
        names = [l["name"] for l in result["lines"]]
        get = lambda r, j: r["by_input"][j]["impact"]
    labels = [f"{r['category']}\n({r['unit']})" for r in res]
    fig, ax = plt.subplots(figsize=(7.2, max(2.6, 0.62 * len(res) + 1.6)), dpi=170)
    left_pos, left_neg = [0.0] * len(res), [0.0] * len(res)
    for j, name in enumerate(names):
        vals = []
        for r in res:
            denom = sum(abs(get(r, x)) for x in range(len(names))) or 1.0
            vals.append(100 * get(r, j) / denom)
        lefts = [left_pos[i] if v >= 0 else left_neg[i] for i, v in enumerate(vals)]
        ax.barh(range(len(res)), vals, left=lefts, color=PALETTE[j % len(PALETTE)], label=name[:48],
                edgecolor="white", linewidth=0.5)
        for i, v in enumerate(vals):
            if v >= 0:
                left_pos[i] += v
            else:
                left_neg[i] += v
    ax.set_yticks(range(len(res)))
    ax.set_yticklabels(labels, fontsize=7)
    ax.invert_yaxis()
    ax.axvline(0, color="black", linewidth=0.6)
    ax.set_xlabel("Share of total absolute impact (%)", fontsize=8)
    ax.tick_params(axis="x", labelsize=7)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, frameon=False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format=fmt_, bbox_inches="tight", **({"dpi": dpi} if dpi else {}))
    plt.close(fig)
    buf.seek(0)
    return buf


def _table(doc, header, rows, widths=None, size=8.5):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(header):
        cell = t.rows[0].cells[i]
        cell.text = h
        cell.paragraphs[0].runs[0].font.bold = True
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = str(v)
    for row in t.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(size)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    return t


def _note(doc, text, size=8.5, italic=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.italic = italic
    return p


def _footer(doc, version=""):
    """Small credit line in the page footer of every section."""
    for sec in doc.sections:
        p = sec.footer.paragraphs[0] if sec.footer.paragraphs else sec.footer.add_paragraph()
        if p.text:
            continue
        r = p.add_run(f"Calculated with {authors.short(version)}, free and open-source LCA software by "
                      f"{authors.CREDITS['display_name']}.")
        r.font.size = Pt(8)
        r.font.color.rgb = RGBColor(0x88, 0x88, 0x88)


def word_report(path, model, result, databases, version=""):
    s = model["scope"] or {}
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10.5)
    for sec in doc.sections:
        sec.left_margin = sec.right_margin = Cm(2.2)

    h = doc.add_heading(f"Life Cycle Assessment: {model['name']}", 0)
    h.alignment = WD_ALIGN_PARAGRAPH.LEFT
    meta = doc.add_paragraph()
    meta.add_run(f"Prepared by: {s.get('author') or '-'}    Date: {datetime.date.today().isoformat()}    "
                 f"Review status: {REVIEW_TEXT.get(s.get('review_status') or '', s.get('review_status'))}").italic = True
    meta.add_run(f"\nStructured according to ISO 14040/14044. Calculated with {authors.short(version)}.").font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    _footer(doc, version)

    doc.add_heading("1. Goal and scope", 1)
    _table(doc, ["Item", "Description"], [
        ["Goal of the study", s.get("goal") or "-"],
        ["Reasons for carrying out the study", s.get("reasons") or "-"],
        ["Intended application", s.get("application") or "-"],
        ["Intended audience", s.get("audience") or "-"],
        ["Comparative assertion disclosed to the public", s.get("comparative") or "No"],
        ["Functional unit", fu_text(model) + (f" ({s['fu_description']})" if s.get("fu_description") else "")],
        ["System boundary", BOUNDARY_TEXT.get(s.get("boundary", ""), s.get("boundary") or "-")],
        ["Modelling approach", APPROACH_TEXT.get(s.get("approach") or "", s.get("approach") or "-")],
        ["Geography / time period", f"{s.get('geography') or '-'} / {s.get('period') or '-'}"],
        ["Technological coverage", s.get("technology") or "-"],
        ["Allocation", (s.get("allocation") or "-") + (f"; {result['allocation_share'] * 100:.4g} % of burdens allocated "
                                                       "to this product" + ({"mass": " by mass", "price": " by economic value",
                                                       "energy": " by energy content"}.get(s.get("alloc_basis"), ""))
                                                       if result.get("allocation_share", 1) < 1 else "")],
        ["Stage system", s.get("stage_system") or "-"],
        ["Cut-off criteria", s.get("cutoff") or "-"],
        ["Data quality requirements", s.get("dq_requirements") or "-"],
        ["Review and verification status", REVIEW_TEXT.get(s.get("review_status") or "", s.get("review_status"))],
        ["Key assumptions", s.get("assumptions") or "-"],
    ], widths=[5, 11.5])

    doc.add_heading("2. Life cycle inventory", 1)
    used = {l["db"] for l in result["lines"] if l["kind"] == "activity"}
    doc.add_paragraph("Background databases used:")
    for d in databases:
        if d["name"] not in used:
            continue
        doc.add_paragraph(d["name"] + (f", version {d['version']}" if d.get("version") else "") +
                          (f", system model: {d['system_model']}" if d.get("system_model") else "") +
                          f" ({d['n_activities']:,} datasets)", style="List Bullet")
    doc.add_paragraph(f"Foreground inventory per functional unit ({len(result['lines'])} entries):")
    rows = []
    for l in result["lines"]:
        amt = f"{fmt(l['input_amount'])} {l['input_unit']}"
        if (l["input_unit"] or "") != (l["unit"] or ""):
            amt += f" (= {fmt(l['amount'])} {l['unit']})"
        rows.append([l["stage"] if l["stage"] != "Unassigned stage" else "-",
                     l["name"] + (" [avoided]" if l["avoided"] else ""), l.get("location") or "", amt,
                     l.get("db", ""), "(" + ",".join(map(str, l["pedigree"])) + ")", l.get("comment") or ""])
    _table(doc, ["Stage", "Input / output", "Location", "Amount", "Source dataset", "Pedigree", "Data source"], rows,
           widths=[2.2, 4.4, 1.5, 2.6, 2.4, 1.6, 2.6], size=8)
    _note(doc, "Pedigree scores: " + ", ".join(PEDIGREE_LABELS) + " (1 = best, 5 = worst; Weidema et al. 2013).")
    if result.get("parameters"):
        doc.add_paragraph("Parameters" + (f" (scenario: {result['scenario_name']})" if result.get("scenario_name") else "") + ":")
        _table(doc, ["Parameter", "Value"], [[k, fmt(v)] for k, v in result["parameters"].items()], widths=[6, 4])
        formulas = [l for l in result["lines"] if l.get("formula")]
        if formulas:
            _note(doc, "Amounts given by formulas: " + "; ".join(f"{l['name']} = {l['formula']}" for l in formulas) + ".")
    if result["lines"]:
        means = [sum(l["pedigree"][i] for l in result["lines"]) / len(result["lines"]) for i in range(5)]
        _note(doc, "Average data quality: " + "; ".join(f"{lab} {m:.1f}" for lab, m in zip(PEDIGREE_LABELS, means)) + ".")
    prov = [l for l in result["lines"] if l.get("source_ref") or l.get("data_year") or l.get("supplier") or l.get("verified")
            or l.get("data_type")]
    if prov:
        doc.add_paragraph("Data provenance (ISO 14044 4.2.3.6.3):")
        _table(doc, ["Input / output", "Data type", "Reference", "Year", "Supplier / site", "Verified"],
               [[l["name"][:60], l.get("data_type") or "-", l.get("source_ref") or l.get("comment") or "-",
                 f"{l['data_year']:.0f}" if l.get("data_year") else "-", l.get("supplier") or "-",
                 "yes" if l.get("verified") else "-"] for l in prov], widths=[4.5, 2, 4, 1.3, 3, 1.5], size=8)
    w = result.get("water")
    if w:
        doc.add_paragraph(f"Water inventory per functional unit: withdrawal {fmt(w['withdrawal'])} m3 (of which "
                          f"{fmt(w['withdrawal_turbine'])} m3 turbine water), release {fmt(w['release'])} m3, consumption "
                          f"{fmt(w['consumption'])} m3. {w['note']}")

    doc.add_heading("3. Life cycle impact assessment", 1)
    fams = sorted({r["family"] for r in result["results"]})
    doc.add_paragraph("Impact assessment method(s): " + "; ".join(fams) +
                      ". Classification and characterisation follow the method developers' factors.")
    unc = result.get("uncertainty")
    credits = any(l["avoided"] and not l.get("module_d") for l in result["lines"])
    has_d = result.get("has_module_d")
    head = ["Impact category", "Indicator", "Total A-C" if has_d else "Result", "Unit"]
    if credits:
        head.insert(3, "Without credits")
    if has_d:
        head.insert(3 + (1 if credits else 0), "Module D")
    if unc:
        head.append("95 % interval")
    rows = []
    for k, r in enumerate(result["results"]):
        row = [r["category"], r["indicator"], fmt(r["total"]), r["unit"]]
        if credits:
            no_credit = r["total"] - sum(b["impact"] for b, l in zip(r["by_input"], result["lines"])
                                         if l["avoided"] and not l.get("module_d"))
            row.insert(3, fmt(no_credit))
        if has_d:
            row.insert(3 + (1 if credits else 0), fmt(r.get("module_d", 0)))
        if unc:
            u = unc["methods"][k]
            row.append(f"{fmt(u['p2_5'])} to {fmt(u['p97_5'])}")
        rows.append(row)
    _table(doc, head, rows)
    if unc:
        _note(doc, unc["note"])
    if result.get("nw_set"):
        doc.add_heading("Normalisation and weighting (optional elements, ISO 14044 4.4.3)", 2)
        _table(doc, ["Impact category", "Normalised", "Weighted"],
               [[r["category"], fmt(r.get("normalised")), fmt(r.get("weighted"))] for r in result["results"]])
        if result.get("single_score") is not None:
            _note(doc, f"Single score (sum of weighted results): {fmt(result['single_score'])}.")
        _note(doc, f"Factor set: {result['nw_set']}. Weighting is based on value choices and is not scientifically "
                   "based; ISO 14044 does not allow it for comparative assertions disclosed to the public.")

    doc.add_heading("4. Interpretation", 1)
    doc.add_heading("4.1 Identification of significant issues", 2)
    multi_stage = len([x for x in result.get("stages", []) if x != "Unassigned stage"]) > 1
    doc.add_picture(_chart(result, "stage" if multi_stage else "input"), width=Cm(16))
    _note(doc, f"Figure 1. Contribution of each {'life cycle stage' if multi_stage else 'foreground input'} to every "
               "impact category.", 9, italic=True)
    if multi_stage:
        head = ["Stage"] + [f"{r['category']} [{r['unit']}]" for r in result["results"]]
        rows = [[stg] + [fmt(next(b["impact"] for b in r["by_stage"] if b["name"] == stg)) for r in result["results"]]
                for stg in result["stages"]]
        _table(doc, head, rows, size=8)
    for r in result["results"]:
        if not r["total"]:
            continue
        top = sorted(r["by_input"], key=lambda b: -abs(b["impact"]))[:3]
        parts = [f"{t['name']} ({_share(t['impact'], r['total']):.0f} %)" for t in top if t["impact"]]
        procs = r["processes"][:3]
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(f"{r['category'][:1].upper() + r['category'][1:]}: ").bold = True
        p.add_run(f"{fmt(r['total'])} {r['unit']}. Largest contributors: {', '.join(parts)}.")
        if procs:
            p.add_run(" Supply-chain hotspots: " + "; ".join(
                f"{x['name']} ({_share(x['impact'], r['total']):.0f} %)" for x in procs) + ".")

    fnd = [f for f in (result.get("findings") or []) if f.get("kind") != "error"]
    if fnd:
        doc.add_paragraph("Key findings (computed from the results above):")
        for f in fnd:
            p = doc.add_paragraph(style="List Bullet")
            p.add_run(f"{f['title']}: ").bold = True
            p.add_run(f["text"])

    doc.add_heading("4.2 Evaluation", 2)
    dq = result.get("data_quality") or {}
    if dq.get("by_category"):
        doc.add_paragraph("Data quality of the results (contribution-weighted):")
        _table(doc, ["Category", "DQR", "Rating", "Primary", "Secondary", "Estimate", "Not stated"],
               [[c["category"], f"{c['dqr']:.2f}", c["rating"]] +
                [f"{100 * c[k]:.0f} %" for k in ("primary_share", "secondary_share", "estimate_share", "unstated_share")]
                for c in dq["by_category"]], widths=[5, 1.5, 2, 2, 2, 2, 2], size=8)
        _note(doc, dq.get("note", ""))
        if dq.get("priority"):
            doc.add_paragraph("Inputs where better data would improve the study most:")
            for x in dq["priority"]:
                doc.add_paragraph(f"{x['name']} ({x['stage']}): up to {100 * x['max_share']:.0f} % of a category, pedigree "
                                  f"({','.join(map(str, x['pedigree']))}), data type "
                                  f"{x['data_type'] or 'not stated'}{', default scores' if x['default'] else ''}.",
                                  style="List Bullet")
    doc.add_paragraph("Completeness and consistency checks:")
    chk = result.get("checks") or []
    if chk:
        for c in chk:
            doc.add_paragraph(f"[{c['level']}] {c['message']}", style="List Bullet")
    else:
        doc.add_paragraph("No issues found.", style="List Bullet")
    pct = result.get("sensitivity_pct", 10)
    doc.add_paragraph(f"Sensitivity check: change of each category result when one input changes by ±{pct:g} %, and "
                      "the range implied by its data-quality score (95 % of a lognormal distribution).")
    rows = []
    for r in result["results"]:
        for x in r["sensitivity"][:3]:
            if not r["total"] or not x["high"]:
                continue
            lo, hi = sorted((_share(x["ped_low"], r["total"]), _share(x["ped_high"], r["total"])))
            rows.append([r["category"], x["name"][:60], f"±{abs(_share(x['high'], r['total'])):.1f} %",
                         f"{lo:+.1f} % to {hi:+.1f} %"])
    if rows:
        _table(doc, ["Category", "Input", f"±{pct:g} % input", "Data-quality range"], rows, size=8)

    unc_flows = result.get("uncharacterised") or []
    if unc_flows:
        doc.add_paragraph("Inventory flows without a characterisation factor in the selected categories (largest first):")
        _table(doc, ["Flow", "Compartment", "Amount", "Note"],
               [[u["name"], u["context"], f"{fmt(u['amount'])} {u['unit']}",
                 "factor exists under another name/compartment" if u["mapping_issue"] else ""] for u in unc_flows[:15]], size=8)
    ps = result.get("parameter_sensitivity") or []
    if ps:
        doc.add_paragraph(f"Parameter sensitivity: change of each category when one parameter changes by ±{pct:g} %.")
        rows = []
        for p in ps:
            for k, r in enumerate(result["results"]):
                if p.get("high") is None or not r["total"]:
                    continue
                rows.append([p["name"], r["category"], f"{_share(p['low'][k], r['total']):+.2f} %",
                             f"{_share(p['high'][k], r['total']):+.2f} %"])
        if rows:
            _table(doc, ["Parameter", "Category", f"-{pct:g} %", f"+{pct:g} %"], rows, size=8)
    lc = result.get("lcc")
    if lc:
        doc.add_heading("Life cycle costing", 3)
        doc.add_paragraph(f"Life cycle cost per functional unit: {lc['total']:,.2f} {lc['currency']}"
                          + (f"; net present cost {lc['total_discounted']:,.2f} {lc['currency']} at a discount rate of "
                             f"{lc['rate_percent']:g} %" if lc["rate_percent"] else "") + ".")
        _table(doc, ["Stage", f"Cost [{lc['currency']}]", f"Discounted [{lc['currency']}]"],
               [[b["stage"], f"{b['cost']:,.2f}", f"{b['discounted']:,.2f}"] for b in lc["by_stage"]], widths=[6, 4, 4])
        _note(doc, lc["note"])
    dyn = result.get("dynamic_gwp")
    if dyn:
        doc.add_heading("Time-dependent climate impact", 3)
        doc.add_paragraph(f"Dynamic GWP over a {dyn['horizon']:g}-year horizon: {fmt(dyn['dynamic'])} kg CO2-eq, compared with "
                          f"{fmt(dyn['static'])} kg CO2-eq when all emissions are counted at year 0. {dyn['note']}")
    doc.add_heading("4.3 Conclusions, limitations and recommendations", 2)
    doc.add_paragraph(s.get("conclusions") or "State the conclusions here.")
    doc.add_paragraph("Limitations: " + (s.get("limitations") or "state the limitations of data and method here."))
    doc.add_paragraph("Recommendations: " + (s.get("recommendations") or "state the recommendations here."))

    if s.get("review") or (s.get("comparative") or "").startswith("Yes"):
        doc.add_heading("5. Critical review", 1)
        doc.add_paragraph(s.get("review") or "A critical review is required (ISO 14044 6.3) but not yet documented.")

    doc.add_heading("Annex A. Methods text for a manuscript", 1)
    doc.add_paragraph(methods_paragraph(model, result, databases, version))
    if result.get("lci"):
        doc.add_heading("Annex B. Life cycle inventory results (largest 60 flows)", 1)
        _table(doc, ["Elementary flow", "Compartment", "Amount", "Unit"],
               [[x["name"], x["context"], fmt(x["amount"]), x["unit"]] for x in result["lci"][:60]], size=8)
        _note(doc, "The complete inventory is in the Excel export.")
    doc.add_heading("Annex C. References", 1)
    for ref in (authors.reference(version),"ISO 14040:2006 Environmental management. Life cycle assessment. Principles and framework.",
                "ISO 14044:2006 Environmental management. Life cycle assessment. Requirements and guidelines. Amd 1:2017, "
                "Amd 2:2020.",
                "ISO 14071:2024 Environmental management. Life cycle assessment. Critical review processes and reviewer "
                "competencies.",
                "ISO/TS 14074:2022 Environmental management. Life cycle assessment. Principles, requirements and guidelines "
                "for normalization, weighting and interpretation.",
                "Heijungs R., Suh S. (2002). The Computational Structure of Life Cycle Assessment. Kluwer.",
                "Weidema B.P., Bauer C., Hischier R., et al. (2013). Overview and methodology. Data quality guideline "
                "for the ecoinvent database version 3. ecoinvent Report 1(v3). St. Gallen: ecoinvent Centre.",
                "Levasseur A., Lesage P., Margni M., Deschenes L., Samson R. (2010). Considering time in LCA: dynamic LCA and its "
                "application to global warming impact assessments. Environ. Sci. Technol. 44, 3169-3174.",
                "Saltelli A., Annoni P., Azzini I., et al. (2010). Variance based sensitivity analysis of model output. Design and "
                "estimator for the total sensitivity index. Comput. Phys. Commun. 181, 259-270."):
        _note(doc, ref, 9)
    doc.save(path)
    return path


def executive_summary(path, model, result, version=""):
    """Two-page summary for decision makers, built from the key findings and data quality."""
    from docx import Document
    from docx.shared import Pt, Cm
    s = model["scope"] or {}
    doc = Document()
    doc.styles["Normal"].font.size = Pt(10)
    for sec in doc.sections:
        sec.left_margin = sec.right_margin = Cm(2.2)
    doc.add_heading(f"Executive summary: {model['name']}", 0)
    meta = doc.add_paragraph()
    meta.add_run(f"{datetime.date.today().isoformat()}  ·  Review status: "
                 f"{REVIEW_TEXT.get(s.get('review_status') or '', s.get('review_status'))}  ·  {authors.short(version)}").italic = True
    doc.add_heading("What was assessed", 1)
    doc.add_paragraph(f"{s.get('goal') or 'Life cycle assessment'}. Functional unit: {fu_text(model)}. System boundary: "
                      f"{BOUNDARY_TEXT.get(s.get('boundary', ''), s.get('boundary') or '-')}. Geography: "
                      f"{s.get('geography') or '-'}; period: {s.get('period') or '-'}.")
    doc.add_heading("Main results", 1)
    dq = {(c["family"], c["category"]): c for c in (result.get("data_quality") or {}).get("by_category", [])}
    rows = []
    for r in result["results"][:12]:
        top = max((b for b in r["by_input"] if not b["module_d"]), key=lambda b: abs(b["impact"]), default=None)
        c = dq.get((r["family"], r["category"]))
        rows.append([r["category"], f"{fmt(r['total'])} {r['unit']}",
                     f"{top['name'][:40]} ({_share(top['impact'], r['total']):.0f} %)" if top and r["total"] else "-",
                     f"{c['dqr']:.1f} ({c['rating']})" if c else "-"])
    _table(doc, ["Impact category", "Result", "Largest contributor", "Data quality"], rows, widths=[4.5, 3.4, 5.5, 3], size=9)
    lc = result.get("lcc")
    if lc:
        doc.add_paragraph(f"Life cycle cost: {lc['total']:,.2f} {lc['currency']} per functional unit.")
    doc.add_heading("Key findings", 1)
    for f in (result.get("findings") or []):
        if f["kind"] in ("result",):
            continue
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(f"{f['title']}: ").bold = True
        p.add_run(f["text"])
    doc.add_heading("Conclusions and limitations", 1)
    doc.add_paragraph(s.get("conclusions") or "Conclusions not yet written (step 6).")
    if s.get("limitations"):
        doc.add_paragraph("Limitations: " + s["limitations"])
    if s.get("recommendations"):
        doc.add_paragraph("Recommendations: " + s["recommendations"])
    errs = [c for c in result.get("checks") or [] if c["level"] == "error"]
    _note(doc, ("This summary is based on an LCA that still has open errors in its checks; do not use it for decisions. "
                if errs else "") + "The full ISO 14044 report gives the inventory, methods and all checks. Comparative "
          "claims disclosed to the public need a critical review panel (ISO 14044 6.4).", italic=True)
    _footer(doc, version)
    doc.save(path)
    return path


def figures(folder, result):
    """Contribution and stage charts as 300 dpi PNG and as SVG (for journals)."""
    os.makedirs(folder, exist_ok=True)
    out = []
    kinds = ["input"] + (["stage"] if len([x for x in result.get("stages", []) if x != "Unassigned stage"]) > 1 else [])
    for by in kinds:
        for fmt_ in ("png", "svg"):
            name = os.path.join(folder, f"contribution_by_{by}.{fmt_}")
            with open(name, "wb") as fh:
                fh.write(_chart(result, by, fmt_, 300 if fmt_ == "png" else None).read())
            out.append(name)
    return out


def excel_results(path, model, result, version=""):
    wb = Workbook()
    hdr = Font(bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="2F5D50")

    def header(ws, cols):
        ws.append(cols)
        for c in ws[ws.max_row]:
            c.font, c.fill = hdr, fill

    ws = wb.active
    ws.title = "Results"
    ws.append([f"Model: {model['name']}", f"Functional unit: {fu_text(model)}"])
    cols = ["Method", "Category", "Indicator", "Total", "Unit"]
    if result.get("nw_set"):
        cols += ["Normalised", "Weighted"]
    header(ws, cols)
    for r in result["results"]:
        row = [r["family"], r["category"], r["indicator"], r["total"], r["unit"]]
        if result.get("nw_set"):
            row += [r.get("normalised"), r.get("weighted")]
        ws.append(row)

    ws = wb.create_sheet("By input")
    header(ws, ["Stage", "Input", "Avoided", "Amount", "Unit"] + [f"{r['category']} [{r['unit']}]" for r in result["results"]])
    for j, l in enumerate(result["lines"]):
        ws.append([l["stage"], l["name"], "yes" if l["avoided"] else "", l["amount"], l["unit"]] +
                  [r["by_input"][j]["impact"] for r in result["results"]])

    ws = wb.create_sheet("By stage")
    header(ws, ["Stage"] + [f"{r['category']} [{r['unit']}]" for r in result["results"]])
    for stg in result["stages"]:
        ws.append([stg] + [next(b["impact"] for b in r["by_stage"] if b["name"] == stg) for r in result["results"]])

    ws = wb.create_sheet("LCI")
    header(ws, ["Elementary flow", "Compartment", "Amount", "Unit"])
    for x in result.get("lci", []):
        ws.append([x["name"], x["context"], x["amount"], x["unit"]])

    if result.get("has_module_d"):
        ws = wb.create_sheet("Module D")
        header(ws, ["Category", "Total A-C", "Module D", "Unit"])
        for r in result["results"]:
            ws.append([r["category"], r["total"], r.get("module_d", 0), r["unit"]])

    dq = result.get("data_quality") or {}
    if dq.get("by_category"):
        ws = wb.create_sheet("Data quality")
        header(ws, ["Category", "DQR", "Rating", "Primary share", "Secondary share", "Estimate share", "Not stated",
                    "Reliability", "Completeness", "Temporal", "Geographical", "Technological"])
        for c in dq["by_category"]:
            ws.append([c["category"], c["dqr"], c["rating"], c["primary_share"], c["secondary_share"], c["estimate_share"],
                       c["unstated_share"]] + c["pedigree"])
        ws.append([])
        header(ws, ["Input", "Stage", "Data type", "Reference", "Data year", "Supplier / site", "Verified", "Pedigree",
                    "Largest share of a category"])
        for x in dq["lines"]:
            l = next((y for y in result["lines"] if y["input_id"] == x["input_id"]), {})
            ws.append([x["name"], x["stage"], x["data_type"], l.get("source_ref") or l.get("comment") or "",
                       l.get("data_year"), l.get("supplier") or "", "yes" if l.get("verified") else "",
                       ",".join(map(str, x["pedigree"])), x["max_share"]])
    if result.get("findings"):
        ws = wb.create_sheet("Key findings")
        header(ws, ["Kind", "Finding", "Text"])
        for f in result["findings"]:
            ws.append([f["kind"], f["title"], f["text"]])
    lc = result.get("lcc")
    if lc:
        ws = wb.create_sheet("LCC")
        ws.append([f"Life cycle cost per functional unit [{lc['currency']}]", lc["total"], "Discounted", lc["total_discounted"],
                   "Rate %", lc["rate_percent"]])
        header(ws, ["Line", "Stage", "Year", f"Cost [{lc['currency']}]", f"Discounted [{lc['currency']}]", "Module D"])
        for l in lc["lines"]:
            ws.append([l["name"], l["stage"], l["year"], l["cost"], l["discounted"], "yes" if l["module_d"] else ""])
    w = result.get("water")
    if w:
        ws = wb.create_sheet("Water")
        header(ws, ["Item", "m3 per functional unit"])
        for k, lab in (("withdrawal", "Withdrawal"), ("withdrawal_turbine", "of which turbine water"),
                       ("release", "Release"), ("consumption", "Consumption")):
            ws.append([lab, w[k]])
        ws.append([w["note"]])

    ws = wb.create_sheet("Hotspots")
    header(ws, ["Category", "Process", "Impact", "Share %"])
    for r in result["results"]:
        for p in r["processes"]:
            ws.append([r["category"], p["name"], p["impact"], _share(p["impact"], r["total"])])

    ws = wb.create_sheet("Elementary flows")
    header(ws, ["Category", "Flow", "Impact", "Share %"])
    for r in result["results"]:
        for f in r["flows"]:
            ws.append([r["category"], f["name"], f["impact"], _share(f["impact"], r["total"])])

    ws = wb.create_sheet("Sensitivity")
    header(ws, ["Category", "Input", f"-{result['sensitivity_pct']:g} %", f"+{result['sensitivity_pct']:g} %",
                "Data-quality low", "Data-quality high"])
    for r in result["results"]:
        for x in r["sensitivity"]:
            ws.append([r["category"], x["name"], x["low"], x["high"], x["ped_low"], x["ped_high"]])

    if result.get("uncertainty"):
        ws = wb.create_sheet("Uncertainty")
        header(ws, ["Category", "Mean", "Median", "SD", "2.5 %", "97.5 %", "CV %"])
        for r, u in zip(result["results"], result["uncertainty"]["methods"]):
            ws.append([r["category"], u["mean"], u["median"], u["sd"], u["p2_5"], u["p97_5"], u["cv_percent"]])

    ws = wb.create_sheet("Checks")
    header(ws, ["Level", "Step", "Message"])
    for c in result.get("checks", []):
        ws.append([c["level"], c["step"], c["message"]])
    for w in wb.worksheets:
        for col in w.columns:
            w.column_dimensions[col[0].column_letter].width = min(60, max(12, max(len(str(c.value or "")) for c in col) + 2))
    ws = wb.create_sheet("About")
    ws.append([f"Calculated with {authors.short(version)}"])
    ws.append([authors.byline()])
    ws.append(["Please cite: " + authors.reference(version)])
    ws.column_dimensions["A"].width = 120
    wb.save(path)
    return path
