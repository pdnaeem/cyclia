"""Faster modelling: tables from papers to inventory lines, parameter sweeps and optimisation (with Pareto fronts),
model templates, and comparisons between saved versions of a model."""
import csv
import io
import json
import math
import os
import re

import numpy as np

import calc
import units

# ============================================================================ literature tables
UNIT_ALIASES = {"tkm": "t*km", "t.km": "t*km", "tonne-km": "t*km", "kgkm": "kg*km", "m³": "m3", "m²": "m2",
                "litre": "l", "liter": "l", "litres": "l", "liters": "l", "kwh": "kWh", "mwh": "MWh", "gj": "GJ",
                "mj": "MJ", "kj": "kJ", "tonnes": "t", "tonne": "t", "tons": "t", "ton": "t", "kgs": "kg", "pcs": "unit",
                "pieces": "unit", "piece": "unit", "p": "unit", "ha": "ha", "m2a": "m2*year", "m2*a": "m2*year",
                "ml": "ml", "mg": "mg", "µg": "ug", "ug": "ug", "kwh/kwh": "kWh"}
NUM = r"[-+]?(?:\d{1,3}(?:\.\d{3})+,\d+|\d{1,3}(?:[ ,]\d{3})+(?:\.\d+)?|\d+(?:[.,]\d+)?)(?:[eE][-+]?\d+)?"
EMISSION_WORDS = ("emission", "to air", "to water", "to soil", "co2", "carbon dioxide", "methane", "ch4", "n2o",
                  "dinitrogen", "nitrous", "ammonia", "nh3", "nox", "nitrogen oxides", "so2", "sulfur dioxide",
                  "particulate", "pm2.5", "pm10", "nitrate", "phosphate", "leach", "runoff")
STOP = {"of", "for", "the", "and", "a", "an", "in", "per", "from", "to", "with", "at", "on", "use", "used", "input",
        "inputs", "consumption", "total", "amount"}


def _num(tok):
    t = tok.strip().replace("−", "-").replace(" ", "")
    if re.fullmatch(r"[-+]?\d{1,3}(,\d{3})+(\.\d+)?", t):
        t = t.replace(",", "")
    elif re.fullmatch(r"[-+]?\d{1,3}(\.\d{3})+,\d+", t):
        t = t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", ".")
    return float(t)


def _unit(tok):
    t = tok.strip().strip("()[]").replace("·", "*").replace(" ", "")
    t = UNIT_ALIASES.get(t.lower(), t)
    if units.info(t):
        return t
    for cand in (t.lower(), t.upper(), t.capitalize()):
        if units.info(cand):
            return cand
    return None


def parse_table(text):
    """Rows of (name, amount, unit, stage) from pasted text, CSV or text extracted from a PDF/Word file.
    Columns may be separated by tabs, semicolons, commas or two or more spaces."""
    rows, skipped = [], []
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line or not re.search(r"\d", line) or re.match(r"^(table|tab\.|fig\.?|figure|source|note)\b", line, re.I):
            continue
        if "\t" in line:
            cols = [c.strip() for c in line.split("\t")]
        elif ";" in line:
            cols = [c.strip() for c in line.split(";")]
        elif re.search(r"\s{2,}", line):
            cols = [c.strip() for c in re.split(r"\s{2,}", line)]
        else:
            cols = None
        name = amount = unit = stage = None
        if cols and len(cols) >= 2:
            num_idx = [i for i, c in enumerate(cols) if re.fullmatch(NUM, c.replace("−", "-").strip())]
            unit_idx = [i for i, c in enumerate(cols) if _unit(c)]
            if num_idx:
                ai = num_idx[0]
                amount = _num(cols[ai])
                ui = next((i for i in unit_idx if i != ai), None)
                unit = _unit(cols[ui]) if ui is not None else None
                texts = [c for i, c in enumerate(cols) if i not in (ai, ui) and c and not re.fullmatch(NUM, c)]
                if texts:
                    name = max(texts, key=len)
                    rest = [t for t in texts if t != name]
                    stage = next((t for t in rest if re.match(r"^(A\d|B\d|C\d|D\b|A1-A3|stage|module)", t, re.I)), None)
        if name is None:
            m = re.search(rf"({NUM})\s*([A-Za-z³²µ\*\./]+)?", line)
            if not m:
                skipped.append(raw)
                continue
            try:
                amount = _num(m.group(1))
            except ValueError:
                skipped.append(raw)
                continue
            unit = _unit(m.group(2) or "") if m.group(2) else None
            name = (line[:m.start()] + " " + line[m.end():]).strip(" :-,|\t")
            if unit is None and m.group(2):
                name = (line[:m.start()] + " " + m.group(2) + " " + line[m.end():]).strip(" :-,|\t")
        if not name or not re.search(r"[A-Za-z]", name):
            skipped.append(raw)
            continue
        if unit is None and amount is not None and float(amount).is_integer() and 1900 <= amount <= 2100:
            skipped.append(raw)  # most likely a year in a caption or reference
            continue
        rows.append({"name": re.sub(r"\s+", " ", name)[:200], "amount": amount, "unit": unit, "stage": stage or "",
                     "source_line": raw.strip()[:300]})
    return rows, skipped


def read_document(path):
    """Text of a table-like document: CSV/TXT, Excel, Word (tables), or PDF (tables if found, else text)."""
    low = path.lower()
    if low.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True, data_only=True)
        out = []
        for ws in wb.worksheets:
            for r in ws.iter_rows(values_only=True):
                if r and any(v not in (None, "") for v in r):
                    out.append("\t".join("" if v is None else str(v) for v in r))
        return "\n".join(out)
    if low.endswith(".docx"):
        from docx import Document
        d = Document(path)
        out = ["\t".join(c.text.strip() for c in row.cells) for t in d.tables for row in t.rows]
        return "\n".join(out) or "\n".join(p.text for p in d.paragraphs)
    if low.endswith(".pdf"):
        try:
            import pdfplumber
            out = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages[:60]:
                    for t in page.extract_tables() or []:
                        out += ["\t".join("" if c is None else str(c).replace("\n", " ") for c in row) for row in t]
            if out:
                return "\n".join(out)
        except Exception:
            pass
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ValueError("Reading PDF files needs the 'pypdf' package. Copy the table and paste it instead.")
        return "\n".join((p.extract_text() or "") for p in PdfReader(path).pages[:60])
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        return fh.read()


def _query(name):
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z\-]+", name.lower()) if w not in STOP and len(w) > 1]
    return " ".join(words[:4])


def match_rows(store, rows, location=""):
    """Suggest datasets (or elementary flows for emissions) for each parsed row; unit compatibility is required."""
    out = []
    for r in rows:
        is_em = any(w in r["name"].lower() for w in EMISSION_WORDS)
        cands = []
        q = _query(r["name"])
        if q:
            if not is_em:
                for a in store.search_activities(q, location=location, limit=30):
                    fac = units.factor(r["unit"], a["unit"]) if r["unit"] else 1.0
                    if r["unit"] and fac is None:
                        continue
                    cands.append({"kind": "activity", "id": a["id"], "name": a["name"], "location": a["location"],
                                  "unit": a["unit"], "db": a["db"], "factor": fac})
                    if len(cands) >= 5:
                        break
            if is_em or not cands:
                low = r["name"].lower()
                comp = next((c for c in ("air", "water", "soil") if c in low), None)
                fq = " ".join(w for w in q.split() if w not in ("emission", "emissions", "air", "water", "soil", "direct",
                                                                 "leaching", "runoff", "field"))
                for f in store.search_flows(fq or q, limit=40):
                    if f["compartment"] == "natural resource" and is_em:
                        continue
                    if comp and f["compartment"] != comp:
                        continue
                    fac = units.factor(r["unit"], f["unit"]) if r["unit"] else 1.0
                    if r["unit"] and fac is None:
                        continue
                    cands.append({"kind": "flow", "id": f["id"], "name": f["name"],
                                  "location": "/".join(x for x in (f["compartment"], f["subcompartment"]) if x),
                                  "unit": f["unit"], "db": "elementary flow", "factor": fac})
                    if len(cands) >= 8:
                        break
        out.append(dict(r, candidates=cands, pick=0 if cands else None))
    return out


def add_rows(store, model_id, rows, source=""):
    """rows: dicts with kind, ref_id, amount, unit, stage, avoided, name. All rows are checked before any is added."""
    problems, ready = [], []
    for n, r in enumerate(rows, 1):
        kind = r.get("kind")
        if kind not in ("activity", "flow"):
            problems.append(f"Row {n}: choose a dataset or flow.")
            continue
        table = "activities" if kind == "activity" else "flows"
        t = store.one(f"SELECT id, unit FROM {table} WHERE id=?", (int(r["ref_id"]),))
        if not t:
            problems.append(f"Row {n}: the chosen {kind} no longer exists.")
            continue
        try:
            amt = float(r["amount"])
        except (TypeError, ValueError):
            problems.append(f"Row {n}: amount is not a number.")
            continue
        unit = r.get("unit") or t["unit"]
        fac = units.factor(unit, t["unit"])
        if fac is None:
            problems.append(f"Row {n}: '{unit}' cannot be converted to '{t['unit']}'.")
            continue
        ready.append((kind, t["id"], abs(amt) * fac, abs(amt), unit, r))
    if problems:
        return {"added": 0, "problems": problems}
    store.snapshot(model_id, "literature import")
    for kind, rid, conv, amt, unit, r in ready:
        store.add_input(model_id, kind, rid, conv, label=r.get("name", "") if kind == "flow" else "",
                        comment=("literature: " + source if source else "literature") + (f"; '{r.get('source_line', '')[:80]}'"
                                                                                       if r.get("source_line") else ""),
                        stage=r.get("stage", ""), input_amount=amt, input_unit=unit,
                        avoided=bool(r.get("avoided")) or (float(r["amount"]) < 0), pedigree=[2, 3, 3, 3, 3])
    return {"added": len(ready), "problems": []}


# ============================================================================ sweeps and optimisation
class Evaluator:
    """Totals of a model for given parameter values, reusing matrices and characterisation."""

    def __init__(self, store, model_id, method_ids, scenario=None, bg=None):
        self.store, self.model_id = store, model_id
        self.method_ids = [int(m) for m in method_ids]
        self.overrides = calc._scenario(store, scenario)
        self.mc = calc.get_mc(store, bg)
        self.M = calc.Methods(store, self.mc, self.method_ids)
        self.ctx0 = calc.Context(store, self.overrides)
        self.model = self.ctx0.model(model_id)
        self.free = {p["name"]: p for p in self.ctx0.project_params + self.model["parameters"] if not p.get("formula")}
        self.n = 0

    def __call__(self, values):
        ctx = calc.Context(self.store, {**self.overrides, **values}, base=self.ctx0)
        acts, flows, fixed = {}, {}, []
        sc = self.model["scope"]
        calc.expand(ctx, self.model_id, 1.0, acts, flows, fixed, keep=lambda i: not calc.is_module_d(sc, i["stage"]))
        h, _, _ = calc.impacts(self.mc, self.M, acts, flows, fixed)
        self.n += 1
        return h


def _check_params(ev, params):
    out = []
    for p in params:
        name = str(p.get("name") or "")
        if name not in ev.free:
            raise ValueError(f"'{name}' is not a free parameter of this model (parameters defined by a formula cannot be "
                             "varied directly).")
        lo, hi = float(p["lo"]), float(p["hi"])
        if not hi > lo:
            raise ValueError(f"{name}: the upper bound must be above the lower bound.")
        out.append((name, lo, hi, int(p.get("n") or 11)))
    if not out:
        raise ValueError("Choose at least one parameter.")
    return out


def sweep(store, model_id, method_ids, params, scenario=None, bg=None):
    ev = Evaluator(store, model_id, method_ids, scenario, bg)
    ps = _check_params(ev, params)[:2]
    if len(ps) == 1:
        name, lo, hi, n = ps[0]
        xs = np.linspace(lo, hi, max(2, min(n, 101)))
        vals = [ev({name: float(x)}).tolist() for x in xs]
        return {"params": [name], "x": xs.tolist(), "values": vals, "methods": _meth(ev), "evaluations": ev.n}
    (n1, lo1, hi1, k1), (n2, lo2, hi2, k2) = ps
    xs, ys = np.linspace(lo1, hi1, max(2, min(k1, 41))), np.linspace(lo2, hi2, max(2, min(k2, 41)))
    grid = [[ev({n1: float(x), n2: float(y)}).tolist() for x in xs] for y in ys]
    return {"params": [n1, n2], "x": xs.tolist(), "y": ys.tolist(), "grid": grid, "methods": _meth(ev), "evaluations": ev.n}


def _meth(ev):
    return [{"id": m["id"], "category": m["category"], "unit": m["unit"], "family": m["family"]} for m in ev.M.rows]


def optimise(store, model_id, method_ids, params, objective=0, constraints=None, second_objective=None,
             samples=400, scenario=None, bg=None, seed=1):
    """Minimise one category over parameter bounds, with optional upper limits on other categories. With a second
    objective, also return the Pareto front of the two categories from a space-filling sample."""
    from scipy.optimize import differential_evolution
    from scipy.stats import qmc
    ev = Evaluator(store, model_id, method_ids, scenario, bg)
    ps = _check_params(ev, params)[:6]
    names = [p[0] for p in ps]
    bounds = [(p[1], p[2]) for p in ps]
    cons = [(int(c["index"]), float(c["max"])) for c in (constraints or []) if c.get("max") not in (None, "")]
    k = len(ev.method_ids)
    if not 0 <= int(objective) < k:
        raise ValueError("Choose the category to minimise.")
    base_vals = {n: float(ev.free[n]["value"] or 0) for n in names}
    base = ev(base_vals)
    scale = max(abs(base[int(objective)]), 1e-12)

    def penalised(x):
        h = ev(dict(zip(names, map(float, x))))
        pen = sum(max(0.0, h[i] - lim) / max(abs(lim), 1e-12) for i, lim in cons)
        return h[int(objective)] / scale + 1e3 * pen
    res = differential_evolution(penalised, bounds, seed=seed, maxiter=60, popsize=12, tol=1e-8, polish=True)
    best = dict(zip(names, map(float, res.x)))
    hb = ev(best)
    feasible = all(hb[i] <= lim * (1 + 1e-6) + 1e-12 for i, lim in cons)
    out = {"params": names, "bounds": bounds, "methods": _meth(ev), "objective": int(objective),
           "baseline": {"values": base_vals, "totals": base.tolist()},
           "optimum": {"values": best, "totals": hb.tolist(), "feasible": feasible},
           "improvement_percent": float(100 * (base[int(objective)] - hb[int(objective)]) / abs(base[int(objective)]))
           if base[int(objective)] else None,
           "constraints": [{"index": i, "max": lim, "value": float(hb[i]), "met": hb[i] <= lim * (1 + 1e-6) + 1e-12}
                           for i, lim in cons]}
    if second_objective is not None and second_objective != "" and int(second_objective) != int(objective):
        j = int(second_objective)
        n = int(max(50, min(int(samples or 400), 3000)))
        smp = qmc.LatinHypercube(d=len(names), seed=seed).random(n)
        X = qmc.scale(smp, [b[0] for b in bounds], [b[1] for b in bounds])
        pts = []
        for x in X:
            h = ev(dict(zip(names, map(float, x))))
            if all(h[i] <= lim for i, lim in cons):
                pts.append((float(h[int(objective)]), float(h[j]), [float(v) for v in x]))
        pts.append((float(hb[int(objective)]), float(hb[j]), [best[nm] for nm in names]))
        order = sorted(range(len(pts)), key=lambda i: (pts[i][0], pts[i][1]))
        front, best_y = [], math.inf
        for i in order:
            if pts[i][1] < best_y - 1e-15:
                front.append(i)
                best_y = pts[i][1]
        out["pareto"] = {"x_index": int(objective), "y_index": j,
                         "points": [[p[0], p[1]] for p in pts],
                         "front": [{"x": pts[i][0], "y": pts[i][1], "values": dict(zip(names, pts[i][2]))} for i in front]}
    out["evaluations"] = ev.n
    return out


# ============================================================================ templates
BUILTIN_TEMPLATES = [
    {"id": "wall-en15804", "name": "External wall, 1 m2 (EN 15804+A2)", "category": "Building element",
     "standard": "EN 15804+A2 / ISO 21930", "product": "external wall, load-bearing", "unit": "m2", "amount": 1,
     "description": "Cradle-to-grave wall with A1-A3, A4, C3/C4 and module D. Edit thickness, steel and distances.",
     "scope": {"boundary": "cradle-to-grave", "stage_system": "EN 15804 (construction products)",
               "goal": "Environmental performance of an external wall per m2 over its reference service life",
               "cutoff": "EN 15804+A2: at most 1 % of energy and mass per unit process, at most 5 % in total per module",
               "allocation": "EN 15804+A2 6.4.3: polluter pays for waste; recycling benefits in module D"},
     "parameters": [{"name": "thickness", "value": 0.2, "unit": "m", "utype": 4, "p1": 0.18, "p2": 0.25},
                    {"name": "steel_kg", "value": 12, "unit": "kg/m2", "utype": 2, "p1": 1.5},
                    {"name": "transport_km", "value": 50, "unit": "km", "utype": 3, "p1": 20, "p2": 50, "p3": 120}],
     "lines": [{"search": "concrete", "unit": "m3", "formula": "thickness", "stage": "A1 Raw material supply"},
               {"search": "reinforcing steel", "unit": "kg", "formula": "steel_kg", "stage": "A1 Raw material supply"},
               {"search": "transport lorry", "unit": "t*km", "formula": "(thickness * 2400 + steel_kg) / 1000 * transport_km",
                "stage": "A4 Transport to site"},
               {"search": "landfill inert", "unit": "kg", "formula": "thickness * 2400", "stage": "C4 Disposal"},
               {"search": "reinforcing steel", "unit": "kg", "formula": "steel_kg * 0.85", "stage":
                "D Benefits and loads beyond the system boundary", "avoided": True}]},
    {"id": "packaging-pef", "name": "Beverage bottle, per 1 L delivered (PEF-style)", "category": "Packaging",
     "standard": "PEF / Circular Footprint Formula (simplified)", "product": "packaging for 1 L of beverage", "unit": "l",
     "amount": 1, "description": "Bottle material, converting, distribution and end of life with a recycling credit.",
     "scope": {"boundary": "cradle-to-grave", "stage_system": "General",
               "goal": "Packaging footprint per litre of beverage delivered to the consumer",
               "allocation": "End of life with recycling credit (simplified Circular Footprint Formula, A = 0.5)"},
     "parameters": [{"name": "bottle_g", "value": 25, "unit": "g", "utype": 2, "p1": 2},
                    {"name": "recycling_rate", "value": 0.5, "unit": "-", "utype": 4, "p1": 0.3, "p2": 0.8},
                    {"name": "distance_km", "value": 300, "unit": "km"}],
     "lines": [{"search": "polyethylene terephthalate granulate", "unit": "kg", "formula": "bottle_g / 1000", "stage": "Raw materials"},
               {"search": "stretch blow moulding", "unit": "kg", "formula": "bottle_g / 1000", "stage": "Manufacturing"},
               {"search": "transport lorry", "unit": "t*km", "formula": "(1 + bottle_g / 1000) / 1000 * distance_km",
                "stage": "Distribution"},
               {"search": "municipal solid waste incineration", "unit": "kg",
                "formula": "bottle_g / 1000 * (1 - recycling_rate)", "stage": "End of life"},
               {"search": "polyethylene terephthalate granulate", "unit": "kg",
                "formula": "bottle_g / 1000 * recycling_rate * 0.5", "stage": "End of life", "avoided": True}]},
    {"id": "food-crop", "name": "Arable crop, 1 kg at farm gate (IPCC Tier 1 field emissions)", "category": "Food and agriculture",
     "standard": "ISO 14067 / IPCC 2019 Tier 1", "product": "grain, at farm gate", "unit": "kg", "amount": 1,
     "description": "Fertiliser, diesel and seed per kg with direct N2O and NH3 from the applied nitrogen.",
     "scope": {"boundary": "cradle-to-gate", "stage_system": "Agriculture",
               "goal": "Carbon footprint of an arable crop per kg at the farm gate",
               "assumptions": "Direct N2O = N x 0.01 x 44/28; NH3 = N x 0.11 x 17/14 (IPCC 2019 Tier 1 defaults for "
                              "synthetic fertiliser). Replace with measured or country values where available."},
     "parameters": [{"name": "yield_kg_ha", "value": 7000, "unit": "kg/ha", "utype": 2, "p1": 900},
                    {"name": "n_kg_ha", "value": 170, "unit": "kg N/ha", "utype": 2, "p1": 20},
                    {"name": "diesel_l_ha", "value": 90, "unit": "l/ha"}],
     "lines": [{"search": "ammonium nitrate", "unit": "kg", "formula": "n_kg_ha / yield_kg_ha",
                "stage": "Fertiliser and field emissions"},
               {"search": "diesel burned", "unit": "MJ", "formula": "diesel_l_ha * 36 / yield_kg_ha", "stage": "Field operations"},
               {"flow": "Dinitrogen monoxide", "compartment": "air", "unit": "kg",
                "formula": "n_kg_ha * 0.01 * 44 / 28 / yield_kg_ha", "stage": "Fertiliser and field emissions"},
               {"flow": "Ammonia", "compartment": "air", "unit": "kg",
                "formula": "n_kg_ha * 0.11 * 17 / 14 / yield_kg_ha", "stage": "Fertiliser and field emissions"}]},
    {"id": "energy-pv", "name": "Solar PV electricity, 1 kWh (rooftop)", "category": "Energy",
     "standard": "IEA PVPS Task 12 methodology guidelines (structure)", "product": "electricity, low voltage, from PV",
     "unit": "kWh", "amount": 1, "description": "Panel, inverter and mounting spread over the lifetime production.",
     "scope": {"boundary": "cradle-to-grave", "stage_system": "General",
               "goal": "Life cycle impact of rooftop PV electricity per kWh",
               "assumptions": "Lifetime production = yield x lifetime x (1 - degradation x lifetime / 2)"},
     "parameters": [{"name": "yield_kwh_kwp", "value": 1000, "unit": "kWh/kWp/year", "utype": 2, "p1": 100},
                    {"name": "lifetime", "value": 30, "unit": "years", "utype": 4, "p1": 25, "p2": 35},
                    {"name": "m2_per_kwp", "value": 5, "unit": "m2/kWp"}, {"name": "degradation", "value": 0.007, "unit": "1/year"}],
     "lines": [{"search": "photovoltaic panel", "unit": "m2",
                "formula": "m2_per_kwp / (yield_kwh_kwp * lifetime * (1 - degradation * lifetime / 2))", "stage": "Manufacturing"},
               {"search": "inverter", "unit": "unit",
                "formula": "2 / (yield_kwh_kwp * lifetime * (1 - degradation * lifetime / 2)) / 3", "stage": "Manufacturing"},
               {"search": "transport lorry", "unit": "t*km",
                "formula": "m2_per_kwp * 0.012 * 500 / (yield_kwh_kwp * lifetime * (1 - degradation * lifetime / 2))",
                "stage": "Distribution"}]},
]


def templates(store):
    user = store.user_templates()
    return [dict(t, builtin=True) for t in BUILTIN_TEMPLATES] + \
        [dict(t["spec"], id=f"user-{t['id']}", db_id=t["id"], builtin=False, name=t["name"], category=t["category"],
              description=t["description"]) for t in user]


def _find_line(store, ln, location=""):
    if ln.get("flow"):
        rows = store.q("SELECT id, name, unit, compartment, subcompartment FROM flows WHERE lower(name)=lower(?) "
                       "AND lower(compartment)=lower(?) ORDER BY subcompartment='unspecified' DESC, subcompartment",
                       (ln["flow"], ln.get("compartment") or "air"))
        rows = [r for r in rows if units.factor(ln.get("unit") or r["unit"], r["unit"]) is not None]
        return ("flow", rows[0]) if rows else (None, None)
    for a in store.search_activities(ln["search"], location=location, limit=40):
        if units.factor(ln.get("unit") or a["unit"], a["unit"]) is not None:
            return "activity", a
    return None, None


def apply_template(store, tpl, name=None, location=""):
    """Create a model from a template, linking each line to the best dataset in the library (unit-compatible)."""
    mid = store.save_model({"name": name or tpl["name"], "product": tpl.get("product", ""), "unit": tpl.get("unit", ""),
                            "amount": tpl.get("amount", 1),
                            "scope": dict(tpl.get("scope") or {}, template=tpl.get("name"), standard=tpl.get("standard", ""))})
    for p in tpl.get("parameters") or []:
        store.save_parameter(dict(p, model_id=mid))
    import formula as fm
    vals = calc.Context(store).params(mid)
    linked, missing = [], []
    for ln in tpl.get("lines") or []:
        kind, t = _find_line(store, ln, location)
        if not kind:
            missing.append(ln.get("search") or ln.get("flow"))
            continue
        unit = ln.get("unit") or t["unit"]
        amt = fm.evaluate(ln["formula"], vals) if ln.get("formula") else float(ln.get("amount") or 0)
        fac = units.factor(unit, t["unit"])
        store.add_input(mid, kind, t["id"], abs(amt) * fac, label=t["name"] if kind == "flow" else "",
                        comment=f"from template '{tpl['name']}'; check the dataset choice", stage=ln.get("stage", ""),
                        input_amount=abs(amt), input_unit=unit, avoided=bool(ln.get("avoided")),
                        formula=ln.get("formula"))
        linked.append({"line": ln.get("search") or ln.get("flow"), "dataset": t["name"],
                       "location": t.get("location") or t.get("compartment", "")})
    return {"model_id": mid, "linked": linked, "missing": missing}


def template_from_model(store, model_id):
    m = store.model(model_id)
    if not m:
        raise ValueError("Model not found.")
    lines = []
    for i in m["inputs"]:
        if i["kind"] == "activity":
            ln = {"search": " ".join((i["target"].get("product") or i["target"]["name"]).split(",")[:2]), "unit": i["input_unit"]}
        elif i["kind"] == "flow":
            f = store.one("SELECT name, compartment FROM flows WHERE id=?", (i["ref_id"],))
            ln = {"flow": f["name"], "compartment": f["compartment"], "unit": i["input_unit"]}
        else:
            continue
        ln.update({"stage": i["stage"], "avoided": i["avoided"]})
        if i["formula"]:
            ln["formula"] = i["formula"]
        else:
            ln["amount"] = i["input_amount"]
        lines.append(ln)
    keep = ("boundary", "stage_system", "goal", "cutoff", "allocation", "assumptions", "fu_description")
    return {"product": m["product"], "unit": m["unit"], "amount": m["amount"],
            "scope": {k: m["scope"].get(k) for k in keep if m["scope"].get(k)},
            "parameters": [{k: p[k] for k in ("name", "value", "formula", "unit", "utype", "p1", "p2", "p3")}
                           for p in m["parameters"]], "lines": lines}


# ============================================================================ version comparison
def _line_rows(store, snap):
    out = []
    for r in snap["inputs"]:
        if r["kind"] == "activity":
            t = store.one("SELECT name, location FROM activities WHERE id=?", (r["ref_id"],)) if r["ref_id"] else None
            name = f"{t['name']} [{t['location']}]" if t else f"(dataset {r.get('ref_key') or r['ref_id']})"
        elif r["kind"] == "flow":
            t = store.one("SELECT name, compartment FROM flows WHERE id=?", (r["ref_id"],)) if r["ref_id"] else None
            name = f"{t['name']} ({t['compartment']})" if t else r.get("label") or "flow"
        elif r["kind"] == "model":
            t = store.one("SELECT name FROM main.models WHERE id=?", (r["ref_id"],))
            name = t["name"] if t else "model"
        else:
            name = r.get("label") or "EPD line"
        out.append({"key": (r["kind"], r.get("ref_key") or r.get("ref_id") or r.get("label"), r.get("stage") or "",
                            int(r.get("avoided") or 0)), "name": r.get("label") or name,
                    "amount": r.get("input_amount") if r.get("input_amount") is not None else r["amount"],
                    "unit": r.get("input_unit") or "", "formula": r.get("formula") or "", "stage": r.get("stage") or "",
                    "pedigree": r.get("pedigree"), "comment": r.get("comment") or "", "avoided": bool(r.get("avoided"))})
    return out


def diff_snapshots(store, a, b, label_a="A", label_b="B"):
    sa, sb = json.loads(a["model"]["scope"] or "{}"), json.loads(b["model"]["scope"] or "{}")
    scope = []
    for k in ("name", "product", "unit", "amount"):
        if a["model"][k] != b["model"][k]:
            scope.append({"field": k, "a": a["model"][k], "b": b["model"][k]})
    for k in sorted(set(sa) | set(sb)):
        if k in ("locked",):
            continue
        if sa.get(k) != sb.get(k):
            scope.append({"field": k, "a": sa.get(k), "b": sb.get(k)})
    la, lb = _line_rows(store, a), _line_rows(store, b)

    def index(rows):
        d = {}
        for r in rows:
            k = r["key"]
            n = 0
            while (k, n) in d:
                n += 1
            d[(k, n)] = r
        return d
    ia, ib = index(la), index(lb)
    added = [ib[k] for k in ib if k not in ia]
    removed = [ia[k] for k in ia if k not in ib]
    changed = []
    for k in ia:
        if k in ib:
            for f in ("amount", "unit", "formula", "pedigree", "comment", "name"):
                if ia[k][f] != ib[k][f]:
                    changed.append({"line": ib[k]["name"], "field": f, "a": ia[k][f], "b": ib[k][f]})
    pa = {p["name"]: p for p in a.get("parameters", [])}
    pb = {p["name"]: p for p in b.get("parameters", [])}
    params = []
    for n in sorted(set(pa) | set(pb)):
        x, y = pa.get(n), pb.get(n)
        fx = (x["value"], x["formula"], x["utype"]) if x else None
        fy = (y["value"], y["formula"], y["utype"]) if y else None
        if fx != fy:
            params.append({"name": n, "a": None if not x else (x["formula"] or x["value"]),
                           "b": None if not y else (y["formula"] or y["value"])})
    for r in added + removed:
        r.pop("key", None)
    return {"a": label_a, "b": label_b, "scope": scope, "added": added, "removed": removed, "changed": changed,
            "parameters": params, "identical": not (scope or added or removed or changed or params)}
