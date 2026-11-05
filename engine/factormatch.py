"""Factor matching validation (Cyclia 1.3.5).

Compares the characterisation factors Cyclia has matched to its elementary flows with the factors another tool
assigns to the same flows, flow by flow, and shows what each difference does to the results of the project's
models.

External sources:
- an openLCA JSON-LD export of the impact method (impact categories with their factors per flow UUID);
- a Brightway factor export written by engine/tools/brightway_export_factors.py (run in a Brightway environment);
- a generic CSV table: category, flow_uuid, flow_name, compartment, subcompartment, unit, cf, location.

Optionally, the external tool's results for the same models (CSV: model, category, value) are compared with
Cyclia's results, and the difference is split into the part explained by the factors (Cyclia's inventory times
the factor differences) and the rest (inventory, linking or solver differences).
"""
import csv
import io
import math
import os
import re

import numpy as np

import calc
from canon import canon

SAME_TOL = 1e-6


# ---------------------------------------------------------------------------------------------- reading
def _num(v):
    try:
        x = float(str(v).replace(",", ".")) if isinstance(v, str) else float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _split_categories(v):
    t = str(v or "").strip().strip("()[]")
    parts = [p.strip().strip("'\"") for p in re.split(r"::|/|,", t) if p.strip().strip("'\"")]
    return (parts[0] if parts else ""), ("/".join(parts[1:]) if len(parts) > 1 else "")


def read_csv_factors(text):
    """Generic or Brightway CSV. Columns (case-insensitive, any order): category (or method), flow_uuid / code,
    flow_name / name, compartment and subcompartment, or categories ('air::urban air close to ground'), unit,
    cf / value / amount, location."""
    rdr = csv.DictReader(io.StringIO(text))
    if not rdr.fieldnames:
        raise ValueError("The CSV file is empty.")
    cols = {c.strip().lower(): c for c in rdr.fieldnames if c}

    def col(*names):
        return next((cols[n] for n in names if n in cols), None)
    c_cat, c_meth = col("category", "impact category", "indicator"), col("method", "method key")
    c_uuid, c_name = col("flow_uuid", "uuid", "code", "flow code"), col("flow_name", "name", "flow")
    c_comp, c_sub, c_cats = col("compartment"), col("subcompartment"), col("categories")
    c_unit, c_cf, c_loc = col("unit", "flow unit"), col("cf", "value", "amount", "factor"), col("location", "geography")
    if not c_cf or not (c_cat or c_meth) or not (c_uuid or c_name):
        raise ValueError("The CSV needs a category (or method) column, a flow (uuid/code or name) column and a cf column.")
    cats = {}
    for r in rdr:
        v = _num(r.get(c_cf))
        if v is None:
            continue
        cat = (r.get(c_cat) if c_cat else "") or (r.get(c_meth) if c_meth else "")
        cat = str(cat).strip()
        if c_cats:
            comp, sub = _split_categories(r.get(c_cats))
        else:
            comp, sub = str(r.get(c_comp) or "").strip() if c_comp else "", str(r.get(c_sub) or "").strip() if c_sub else ""
        cats.setdefault(cat, []).append({"uuid": (str(r.get(c_uuid) or "").strip() or None) if c_uuid else None,
                                         "name": str(r.get(c_name) or "").strip() if c_name else "", "comp": comp,
                                         "sub": sub, "unit": str(r.get(c_unit) or "").strip() if c_unit else "",
                                         "location": str(r.get(c_loc) or "").strip() if c_loc else "", "value": v})
    if not cats:
        raise ValueError("No factor rows with a number were found in the CSV.")
    return [{"method": "", "category": k, "unit": "", "factors": v} for k, v in cats.items()]


def read_external(path):
    if os.path.isdir(path) or path.lower().endswith(".zip"):
        from importers import jsonld
        return jsonld.read_impact_factors(path), "openLCA JSON-LD"
    with open(path, encoding="utf-8-sig") as fh:
        text = fh.read()
    kind = "Brightway export" if "brightway" in text[:400].lower() or "method key" in text[:400].lower() else "CSV table"
    lines = [ln for ln in text.splitlines() if not ln.startswith("#")]
    return read_csv_factors("\n".join(lines)), kind


# ---------------------------------------------------------------------------------------------- pairing
def _tokens(s):
    return {t for t in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(t) > 1 and t not in ("and", "the", "of", "to")}


def pair_categories(methods, ext):
    """Best external category for every Cyclia category by word overlap (Jaccard); a pair needs at least 0.4."""
    pairs = []
    used = set()
    for m in methods:
        variants = [_tokens(m["category"]), _tokens(f"{m['category']} {m['indicator']}")]
        best, score = None, 0.0
        for j, e in enumerate(ext):
            b = _tokens(e["category"])
            for a in variants:
                s = len(a & b) / len(a | b) if a | b else 0.0
                if s > score:
                    best, score = j, s
        if best is not None and score >= 0.4:
            pairs.append((m, ext[best], score))
            used.add(best)
        else:
            pairs.append((m, None, score))
    return pairs, [e["category"] for j, e in enumerate(ext) if j not in used]


# ---------------------------------------------------------------------------------------------- comparison
def _flow_index(store):
    rows = store.q("SELECT id, uuid, name, compartment, subcompartment, unit, c_name, c_comp, c_sub FROM flows")
    by_uuid = {r["uuid"]: r for r in rows if r["uuid"]}
    by_key = {}
    for r in rows:
        by_key.setdefault((r["c_name"] or "", r["c_comp"] or "", r["c_sub"] or ""), []).append(r)
    return rows, by_uuid, by_key


def _resolve(row, by_uuid, by_key):
    if row.get("uuid") and row["uuid"] in by_uuid:
        return [by_uuid[row["uuid"]]], "uuid"
    cn, cc, cs = canon(row["name"], row["comp"], row["sub"])
    hits = by_key.get((cn, cc, cs), [])
    return hits, ("name" if hits else None)


def model_inventories(store, model_ids):
    """Elementary flows per functional unit (flow id -> amount) of every model, excluding module D."""
    mc = calc.get_mc(store)
    ctx = calc.Context(store)
    out = {}
    for mid in model_ids or []:
        m = store.model(int(mid))
        if not m or not m["inputs"] or any(i["missing"] for i in m["inputs"]):
            continue
        acts, flows, fixed = {}, {}, []
        try:
            calc.expand(ctx, int(mid), 1.0, acts, flows, fixed, keep=lambda i, sc=m["scope"]: not calc.is_module_d(sc, i["stage"]))
        except calc.LCAError:
            continue
        f = calc.demand_vector(mc, acts)
        g = mc.B @ mc.solve(f) if f.any() else np.zeros(len(mc.flow_ids))
        g = g + calc.flow_vector(mc, flows)
        out[int(mid)] = {"name": m["name"], "g": {int(mc.flow_ids[i]): float(g[i]) for i in np.nonzero(g)[0]},
                         "fixed": bool(fixed)}
    return out


def read_external_results(path):
    with open(path, encoding="utf-8-sig") as fh:
        rdr = csv.DictReader([ln for ln in fh if not ln.startswith("#")])
        cols = {c.strip().lower(): c for c in rdr.fieldnames or []}
        cm, cc, cv = cols.get("model"), cols.get("category"), cols.get("value") or cols.get("result")
        if not (cm and cc and cv):
            raise ValueError("The results CSV needs the columns model, category and value.")
        out = {}
        for r in rdr:
            v = _num(r.get(cv))
            if v is not None:
                out[(str(r[cm]).strip().lower(), str(r[cc]).strip().lower())] = v
    return out


def compare(store, method_ids, external, source="", model_ids=None, external_results=None, pairs_override=None):
    method_ids = [int(m) for m in method_ids]
    if not method_ids:
        raise ValueError("Pick the impact categories to compare in step 4.")
    methods = [store.one("SELECT id, family, category, indicator, unit FROM methods WHERE id=?", (m,)) for m in method_ids]
    if pairs_override:
        by_name = {e["category"]: e for e in external}
        pairs = [(m, by_name.get(pairs_override.get(str(m["id"])) or ""), 1.0) for m in methods]
        unpaired = [e["category"] for e in external if e["category"] not in set(pairs_override.values())]
    else:
        pairs, unpaired = pair_categories(methods, external)
    rows, by_uuid, by_key = _flow_index(store)
    fmeta = {r["id"]: r for r in rows}
    mc = calc.get_mc(store)
    used = {int(mc.flow_ids[i]) for i in np.unique(mc.b_rows)} if len(mc.b_rows) else set()
    inv = model_inventories(store, model_ids)
    used |= {fid for x in inv.values() for fid in x["g"]}
    cats, flow_rows = [], []
    for m, e, score in pairs:
        cy = {r["flow_id"]: float(r["value"]) for r in store.q("SELECT flow_id, value FROM cfs WHERE method_id=?", (m["id"],))}
        ext_cf, unresolved, unit_issue, ambiguous, conflicts = {}, [], [], 0, 0
        if e:
            for row in e["factors"]:
                if row.get("location") and row["location"].upper() not in ("GLO", "GLOBAL", "WORLD"):
                    continue
                hits, how = _resolve(row, by_uuid, by_key)
                if not hits:
                    unresolved.append(row)
                    continue
                if len(hits) > 1 and how == "name":
                    ambiguous += 1
                for h in hits:
                    if h["id"] in ext_cf:
                        if abs(ext_cf[h["id"]] - row["value"]) > SAME_TOL * max(abs(row["value"]), abs(ext_cf[h["id"]])):
                            conflicts += 1
                        continue
                    ext_cf[h["id"]] = row["value"]
                    if row.get("unit") and h["unit"] and row["unit"].strip().lower() != h["unit"].strip().lower():
                        unit_issue.append((h, row["unit"]))
        relevant = (set(cy) | set(ext_cf)) & used if used else set(cy) | set(ext_cf)
        counts = {"same": 0, "different": 0, "only_cyclia": 0, "only_external": 0}
        maxrel = 0.0
        for fid in relevant:
            a, b = cy.get(fid, 0.0), ext_cf.get(fid, 0.0) if e else None
            if b is None:
                continue
            if a == 0 and b == 0:
                continue
            scale = max(abs(a), abs(b))
            if a != 0 and b == 0 and fid not in ext_cf:
                st = "only_cyclia"
            elif a == 0 and fid not in cy:
                st = "only_external"
            elif abs(a - b) <= SAME_TOL * scale:
                st = "same"
            else:
                st = "different"
                maxrel = max(maxrel, abs(a - b) / scale)
            counts[st] += 1
            if st != "same":
                f = fmeta[fid]
                eff = {x["name"]: x["g"].get(fid, 0.0) * (b - a) for x in inv.values() if x["g"].get(fid)}
                flow_rows.append({"category": m["category"], "indicator": m["indicator"], "external_category": e["category"],
                                  "flow": f["name"], "compartment": "/".join(x for x in (f["compartment"], f["subcompartment"]) if x),
                                  "unit": f["unit"], "uuid": f["uuid"], "status": st, "cyclia": a, "external": b,
                                  "relative_difference": (abs(a - b) / scale) if scale else 0.0,
                                  "effect": eff, "max_effect": max((abs(v) for v in eff.values()), default=0.0)})
        effects = []
        for mid, x in inv.items():
            k = method_ids.index(m["id"])
            if not e:
                continue
            tot_cy = sum(x["g"][fid] * cy.get(fid, 0.0) for fid in x["g"])
            tot_ex = sum(x["g"][fid] * ext_cf.get(fid, 0.0) for fid in x["g"])
            rec = {"model": x["name"], "cyclia": tot_cy, "with_external_factors": tot_ex,
                   "factor_effect_percent": ((tot_ex - tot_cy) / abs(tot_cy) * 100) if abs(tot_cy) > 1e-300 else None,
                   "has_epd_lines": x["fixed"]}
            if external_results:
                ext_total = external_results.get((x["name"].strip().lower(), e["category"].strip().lower()))
                if ext_total is None:
                    ext_total = external_results.get((x["name"].strip().lower(), m["category"].strip().lower()))
                if ext_total is not None:
                    rec["external_result"] = ext_total
                    rec["total_difference"] = ext_total - tot_cy
                    rec["explained_by_factors"] = tot_ex - tot_cy
                    rec["other_differences"] = ext_total - tot_ex
            effects.append(rec)
        cats.append({"method_id": m["id"], "category": m["category"], "indicator": m["indicator"], "family": m["family"],
                     "external_category": e["category"] if e else None, "pairing_score": score, **counts,
                     "unresolved": len(unresolved), "ambiguous": ambiguous, "unit_issues": len(unit_issue),
                     "external_conflicts": conflicts,
                     "max_relative_difference": maxrel, "models": effects,
                     "agreement": (counts["same"] / max(1, sum(counts.values()))) if e else None})
    flow_rows.sort(key=lambda r: (-r["max_effect"], -r["relative_difference"]))
    ok = all(c["external_category"] and c["different"] == 0 and c["only_cyclia"] == 0 and c["only_external"] == 0
             for c in cats)
    return {"source": source, "categories": cats, "flows": flow_rows[:5000], "n_flow_rows": len(flow_rows),
            "unpaired_external": unpaired, "models": [x["name"] for x in inv.values()],
            "passed": ok,
            "verdict": ("Every relevant flow has the same factor in Cyclia and in the external tool." if ok else
                        "Differences found: see the categories and the flow-by-flow list, largest effect on your models first."),
            "scope": f"Flows compared: every flow used by the library or by the project's models that has a factor in "
                     f"either tool, global factors only. 'Same' means a relative difference up to {SAME_TOL:g}."}


def to_excel(path, res, version=""):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(["Factor Matching Validation Report", f"Cyclia {version}"])
    ws.append(["External source", res["source"]])
    ws.append(["Verdict", res["verdict"]])
    ws.append(["Scope", res["scope"]])
    ws.append([])
    head = ["Cyclia category", "Indicator", "Method", "External category", "Pairing score", "Same", "Different",
            "Only in Cyclia", "Only external", "External flows not in the library", "Matched to several flows",
            "Unit differences", "Conflicting external factors", "Largest relative difference", "Agreement"]
    ws.append(head)
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
    for c in res["categories"]:
        ws.append([c["category"], c["indicator"], c["family"], c["external_category"] or "(no match)", c["pairing_score"],
                   c["same"], c["different"], c["only_cyclia"], c["only_external"], c["unresolved"], c["ambiguous"],
                   c["unit_issues"], c["external_conflicts"], c["max_relative_difference"], c["agreement"]])
    w2 = wb.create_sheet("Flow by flow")
    w2.append(["Category", "External category", "Flow", "Compartment", "Unit", "UUID", "Status", "Cyclia factor",
               "External factor", "Relative difference", "Largest effect on a model"])
    for r in res["flows"]:
        w2.append([r["category"], r["external_category"], r["flow"], r["compartment"], r["unit"], r["uuid"], r["status"],
                   r["cyclia"], r["external"], r["relative_difference"], r["max_effect"]])
    w3 = wb.create_sheet("Effect on models")
    w3.append(["Category", "Model", "Cyclia result (global factors)", "Cyclia inventory x external factors",
               "Factor effect %", "External tool result", "Total difference", "Explained by factors", "Other differences"])
    for c in res["categories"]:
        for x in c["models"]:
            w3.append([c["category"], x["model"], x["cyclia"], x["with_external_factors"], x["factor_effect_percent"],
                       x.get("external_result"), x.get("total_difference"), x.get("explained_by_factors"),
                       x.get("other_differences")])
    if res["unpaired_external"]:
        w4 = wb.create_sheet("Unpaired external")
        w4.append(["External categories without a Cyclia counterpart"])
        for n in res["unpaired_external"]:
            w4.append([n])
    wb.save(path)
    return path
