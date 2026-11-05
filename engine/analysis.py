"""Professional analyses added in Cyclia 1.3.2.

- Life cycle costing (LCC) of the foreground, with discounting (ISO 15686-5 style net present cost)
- Water inventory summary (withdrawal, release, consumption), as a basis for ISO 14046 studies
- Circular Footprint Formula (PEF, Commission Recommendation (EU) 2021/2279, Annex C) turned into inventory lines
- Comparison of two databases (e.g. two ecoinvent versions) on the same datasets
- Relinking a model from one database to another (database update)
- Checks: method versions, modelling approach (attributional / consequential), data age, energy balance
- Correlated parameters for Monte Carlo (Gaussian copula)
"""
import math
import re

import numpy as np

import calc
import units

UNASSIGNED = "Unassigned stage"


# ============================================================================ life cycle costing
def _input_amount(ctx, model_id, inp):
    """Amount of a line in the unit the user typed (the unit the cost refers to)."""
    if inp.get("formula") and inp["kind"] != "fixed":
        amount = calc.line_amount(ctx, model_id, inp)
        fac = units.factor(inp["input_unit"], inp["target"]["unit"]) if inp["input_unit"] else 1.0
        return amount / (fac or 1.0)
    if inp.get("formula"):
        return calc.line_amount(ctx, model_id, inp)
    return inp["input_amount"] if inp["input_amount"] is not None else inp["amount"]


def _model_cost(ctx, model_id, rate, depth=0, year0=0.0):
    """Cost per reference amount of a model: (undiscounted, discounted, n_costed, n_uncosted)."""
    if depth > 25:
        raise calc.LCAError("Models are nested more than 25 levels deep.")
    m = ctx.model(model_id)
    share = calc.allocation_share(m["scope"])
    tot = disc = 0.0
    n_c = n_u = 0
    for inp in m["inputs"]:
        sign = -1.0 if inp["avoided"] else 1.0
        year = year0 + float(inp.get("year") or 0)
        if inp.get("unit_cost") is not None:
            c = _input_amount(ctx, model_id, inp) * float(inp["unit_cost"]) * sign * share
            tot += c
            disc += c / (1 + rate) ** year
            n_c += 1
        elif inp["kind"] == "model":
            sub = ctx.model(inp["ref_id"])
            st, sd, sc_, su = _model_cost(ctx, inp["ref_id"], rate, depth + 1, year)
            k = calc.line_amount(ctx, model_id, inp) / (sub["amount"] or 1.0) * sign * share
            tot += st * k
            disc += sd * k
            n_c += sc_
            n_u += su
        else:
            n_u += 1
    return tot, disc, n_c, n_u


def lcc(ctx, model_id):
    """Life cycle cost per functional unit, by line and stage. Returns None when no line has a cost."""
    model = ctx.model(model_id)
    sc = model["scope"] or {}

    def has_cost(mid, depth=0):
        if depth > 25:
            return False
        for i in ctx.model(mid)["inputs"]:
            if i.get("unit_cost") is not None or (i["kind"] == "model" and has_cost(i["ref_id"], depth + 1)):
                return True
        return False

    if not has_cost(model_id):
        return None
    rate = float(sc.get("lcc_rate") or 0) / 100.0
    if rate <= -1:
        raise calc.LCAError("The discount rate must be above -100 %.")
    share = calc.allocation_share(sc)
    rows, n_unc = [], 0
    for inp in model["inputs"]:
        sign = -1.0 if inp["avoided"] else 1.0
        year = float(inp.get("year") or 0)
        name = inp["label"] or inp["target"]["name"]
        stage = inp["stage"] or UNASSIGNED
        if inp.get("unit_cost") is not None:
            c = _input_amount(ctx, model_id, inp) * float(inp["unit_cost"]) * sign * share
            d = c / (1 + rate) ** year
            src = "line"
        elif inp["kind"] == "model":
            sub = ctx.model(inp["ref_id"])
            st, sd, n_c, n_u = _model_cost(ctx, inp["ref_id"], rate, 1, year)
            if not n_c:
                n_unc += 1
                continue
            k = calc.line_amount(ctx, model_id, inp) / (sub["amount"] or 1.0) * sign * share
            c, d, src = st * k, sd * k, "sub-model"
        else:
            n_unc += 1
            continue
        rows.append({"input_id": inp["id"], "name": name, "stage": stage, "year": year, "cost": c, "discounted": d,
                     "module_d": calc.is_module_d(sc, inp["stage"]), "source": src, "revenue": c < 0})
    ac = [r for r in rows if not r["module_d"]]
    stages = []
    for r in ac:
        if r["stage"] not in stages:
            stages.append(r["stage"])
    by_stage = [{"stage": s, "cost": sum(r["cost"] for r in ac if r["stage"] == s),
                 "discounted": sum(r["discounted"] for r in ac if r["stage"] == s)} for s in stages]
    rows.sort(key=lambda r: -abs(r["cost"]))
    return {"currency": (sc.get("lcc_currency") or "EUR").strip() or "EUR", "rate_percent": rate * 100,
            "total": sum(r["cost"] for r in ac), "total_discounted": sum(r["discounted"] for r in ac),
            "beyond_boundary": sum(r["cost"] for r in rows if r["module_d"]), "by_stage": by_stage, "lines": rows,
            "n_costed": len(rows), "n_uncosted": n_unc,
            "note": "Costs per functional unit from the prices entered in step 3 (price per unit of the amount). "
                    "Credit lines with a price count as revenue. Discounted with the rate in step 2 and the year of "
                    "each line (net present cost). Module D lines are reported apart. Only the costs you entered are "
                    "included: lines without a price count as zero."}


# ============================================================================ water inventory
_TURBINE = "turbine use"


def water_inventory(lci):
    """Water withdrawal and release in m3 per functional unit, from the elementary flows."""
    wd = wd_turbine = rel = 0.0
    n = 0
    for f in lci:
        name = (f["name"] or "").lower()
        if not (name == "water" or name.startswith("water,") or name.startswith("water ")):
            continue
        u = (f["unit"] or "").strip()
        k = 1.0 if u in ("m3", "m³") else 0.001 if u in ("kg", "l", "L", "litre", "liter") else None
        if k is None:
            continue
        ctx = (f["context"] or "").lower()
        amt = f["amount"] * k
        if ctx.startswith("natural resource") or ctx.startswith("resource") or "in water" in ctx or "in ground" in ctx:
            wd += amt
            if _TURBINE in name:
                wd_turbine += amt
            n += 1
        elif ctx.startswith("water") or ctx.startswith("air") or ctx.startswith("soil"):
            rel += amt
            n += 1
    if not n:
        return None
    return {"withdrawal": wd, "withdrawal_turbine": wd_turbine, "withdrawal_no_turbine": wd - wd_turbine,
            "release": rel, "consumption": wd - rel,
            "note": "Elementary water flows in m3 per functional unit. Consumption = withdrawal minus water released "
                    "to air, water and soil (evaporated water counts as released to air in ecoinvent, so the "
                    "consumption here is a lower bound when evaporation is reported as a release). Turbine water of "
                    "hydropower is shown apart because most water scarcity methods (e.g. AWARE) exclude it. For an "
                    "ISO 14046 water footprint, characterise with a water scarcity method."}


# ============================================================================ circular footprint formula
CFF_DEFAULTS = {"A": 0.5, "B": 0.0, "Qsin": 1.0, "Qsout": 1.0, "R1": 0.0, "R2": 0.0, "R3": 0.0, "LHV": 0.0,
                "X_heat": 0.0, "X_elec": 0.0}


def cff_lines(p):
    """Inventory lines for 1 unit of material with the PEF Circular Footprint Formula:
    (1-R1) Ev + R1 (A Erec + (1-A) Ev Qsin/Qp) + (1-A) R2 (ErecEoL - E*v Qsout/Qp)
    + (1-B) R3 (EER - LHV X_heat ESE,heat - LHV X_elec ESE,elec) + (1-R2-R3) ED
    Qsin, Qsout are given as the ratios Qsin/Qp and Qsout/Qp. Returns (role, amount, credit, unit) per line,
    where amounts are per unit of material (heat in MJ, electricity in MJ to be converted)."""
    v = {k: float(p.get(k, CFF_DEFAULTS[k]) if p.get(k, "") != "" else CFF_DEFAULTS[k]) for k in CFF_DEFAULTS}
    for k in ("A", "B", "R1", "R2", "R3", "X_heat", "X_elec"):
        if not 0 <= v[k] <= 1:
            raise ValueError(f"{k} must be between 0 and 1.")
    if v["R2"] + v["R3"] > 1 + 1e-9:
        raise ValueError("R2 + R3 cannot be more than 1 (recycled plus energy-recovered share of the waste).")
    for k in ("Qsin", "Qsout"):
        if not 0 <= v[k] <= 1.5:
            raise ValueError(f"{k}/Qp is a quality ratio, normally between 0 and 1.")
    if v["LHV"] < 0:
        raise ValueError("The lower heating value cannot be negative.")
    A, B, R1, R2, R3 = v["A"], v["B"], v["R1"], v["R2"], v["R3"]
    er = (1 - B) * R3
    return [
        ("virgin", (1 - R1) + R1 * (1 - A) * v["Qsin"], False),
        ("recycled", R1 * A, False),
        ("recycling_eol", (1 - A) * R2, False),
        ("avoided_virgin", (1 - A) * R2 * v["Qsout"], True),
        ("energy_recovery", er, False),
        ("avoided_heat", er * v["LHV"] * v["X_heat"], True),
        ("avoided_electricity", er * v["LHV"] * v["X_elec"], True),
        ("disposal", 1 - R2 - R3, False),
    ], v


CFF_LABEL = {"virgin": "virgin material (Ev)", "recycled": "recycled input material (Erecycled)",
             "recycling_eol": "recycling at end of life (ErecyclingEoL)",
             "avoided_virgin": "avoided virgin material (E*v)", "energy_recovery": "energy recovery (EER)",
             "avoided_heat": "avoided heat (ESE,heat)", "avoided_electricity": "avoided electricity (ESE,elec)",
             "disposal": "disposal (ED)"}
CFF_ENERGY = {"avoided_heat", "avoided_electricity"}


def apply_cff(store, model_id, mass, unit, params, datasets, stage_production="", stage_eol=""):
    """Add the CFF lines for `mass` (in `unit`) of a material to a model. `datasets` maps a role to an activity id;
    a role with a zero amount needs no dataset. Returns the lines added and the coefficients."""
    if not mass or float(mass) <= 0:
        raise ValueError("Give the mass of the material (more than zero).")
    lines, v = cff_lines(params)
    plan = []
    for role, coef, credit in lines:
        if coef <= 1e-12:
            continue
        aid = datasets.get(role) or (datasets.get("virgin") if role == "avoided_virgin" else None)
        if not aid:
            raise ValueError(f"Choose a dataset for {CFF_LABEL[role]}.")
        a = store.activity(int(aid))
        if not a:
            raise ValueError(f"The dataset for {CFF_LABEL[role]} is not in the library.")
        if role in CFF_ENERGY:
            in_amt, in_unit = float(mass) * coef, "MJ"
            if (unit or "kg") != "kg":
                fac = units.factor(unit, "kg")
                if fac is None:
                    raise ValueError("Give the material mass in a mass unit when energy recovery is modelled.")
                in_amt *= fac
        else:
            in_amt, in_unit = float(mass) * coef, unit or "kg"
        fac = units.factor(in_unit, a["unit"])
        if fac is None:
            raise ValueError(f"The dataset for {CFF_LABEL[role]} is in {a['unit']}, which cannot be converted from "
                             f"{in_unit}. Pick a dataset per {'MJ or kWh' if role in CFF_ENERGY else in_unit}.")
        plan.append((role, a, in_amt, in_unit, in_amt * fac, credit))
    note = ("CFF: A={A:g}, B={B:g}, R1={R1:g}, R2={R2:g}, R3={R3:g}, Qsin/Qp={Qsin:g}, Qsout/Qp={Qsout:g}"
            .format(**v)) + (f", LHV={v['LHV']:g} MJ/kg, X_heat={v['X_heat']:g}, X_elec={v['X_elec']:g}" if v["R3"] else "")
    store.snapshot(model_id, "Circular Footprint Formula")
    added = []
    for role, a, in_amt, in_unit, amount, credit in plan:
        stage = stage_eol if role not in ("virgin", "recycled") else stage_production
        iid = store.add_input(model_id, "activity", a["id"], amount, label=f"{a['name']} [{CFF_LABEL[role]}]",
                              comment=note, stage=stage, input_amount=in_amt, input_unit=in_unit, avoided=credit)
        added.append({"id": iid, "role": role, "name": a["name"], "amount": in_amt, "unit": in_unit, "credit": credit})
    return {"added": added, "parameters": v, "note": note}


# ============================================================================ database comparison and update
def _norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def match_activities(store, db_a, db_b, act_ids=None):
    """Pairs (id in A, id in B) of the same dataset: same key first, else same name, product and location."""
    where, args = "db_id=?", [db_a]
    if act_ids:
        where += f" AND id IN ({','.join('?' * len(act_ids))})"
        args += list(act_ids)
    a_rows = store.q(f"SELECT id, key, name, product, location, unit FROM activities WHERE {where}", args)
    b_rows = store.q("SELECT id, key, name, product, location, unit FROM activities WHERE db_id=?", (db_b,))
    by_key = {r["key"]: r for r in b_rows if r["key"]}
    by_name = {}
    for r in b_rows:
        by_name.setdefault((_norm(r["name"]), _norm(r["product"]), (r["location"] or "").upper()), r)
    pairs, missing = [], []
    for r in a_rows:
        m = by_key.get(r["key"]) if r["key"] else None
        how = "key"
        if not m:
            m = by_name.get((_norm(r["name"]), _norm(r["product"]), (r["location"] or "").upper()))
            how = "name"
        if m and (m["unit"] or "") == (r["unit"] or ""):
            pairs.append((r, m, how))
        else:
            missing.append(r)
    return pairs, missing


def compare_databases(store, db_a, db_b, method_ids, act_ids=None, sample=100, seed=3, progress=lambda *a: None):
    """Unit impacts of the same datasets in two databases, with the change per impact category."""
    method_ids = [int(m) for m in method_ids]
    if not method_ids:
        raise ValueError("Pick impact categories in step 4 first.")
    if int(db_a) == int(db_b):
        raise ValueError("Choose two different databases.")
    pairs, missing = match_activities(store, int(db_a), int(db_b), act_ids)
    if not pairs:
        raise ValueError("No dataset of the first database was found in the second one (by key, or by name, product "
                         "and location with the same unit).")
    n_pairs = len(pairs)
    if not act_ids and len(pairs) > sample:
        rng = np.random.default_rng(seed)
        pairs = [pairs[i] for i in sorted(rng.choice(len(pairs), int(sample), replace=False))]
    mc = calc.get_mc(store)
    M = calc.Methods(store, mc, method_ids)
    rows = []
    for k, (a, b, how) in enumerate(pairs):
        ha, _, _ = calc.impacts(mc, M, {a["id"]: 1.0}, {}, [])
        hb, _, _ = calc.impacts(mc, M, {b["id"]: 1.0}, {}, [])
        ch = [((float(y) - float(x)) / abs(float(x)) * 100) if abs(float(x)) > 1e-30 else None for x, y in zip(ha, hb)]
        rows.append({"name": a["name"], "product": a["product"], "location": a["location"], "unit": a["unit"],
                     "matched_by": how, "a": [float(x) for x in ha], "b": [float(y) for y in hb], "change_percent": ch})
        if k % 10 == 0:
            progress(int(100 * k / len(pairs)), f"Dataset {k + 1} of {len(pairs)}")
    cats = []
    for j, m in enumerate(M.rows):
        vals = [r["change_percent"][j] for r in rows if r["change_percent"][j] is not None]
        cats.append({"category": m["category"], "family": m["family"], "unit": m["unit"],
                     "median_change_percent": float(np.median(vals)) if vals else None,
                     "share_changed_over_10": (sum(1 for v in vals if abs(v) > 10) / len(vals)) if vals else None})
    rows.sort(key=lambda r: -max((abs(c) for c in r["change_percent"] if c is not None), default=0))
    names = {d["id"]: d["name"] for d in store.databases()}
    return {"db_a": names.get(int(db_a)), "db_b": names.get(int(db_b)), "methods": cats, "rows": rows,
            "n_matched": n_pairs, "n_compared": len(rows), "n_missing": len(missing),
            "missing": [{"name": r["name"], "location": r["location"]} for r in missing[:50]],
            "note": "Each dataset is calculated per unit of its reference product in both databases with the same "
                    "impact methods. Datasets are matched by their key (stable between ecoinvent versions), else by "
                    "name, product, location and unit."}


def relink_plan(store, model_id, db_from, db_to, apply=False):
    """Map every activity line of a model from one database to another. With apply=True the lines are switched
    (one undo step)."""
    m = store.model(int(model_id))
    if not m:
        raise ValueError("Model not found.")
    names = {d["id"]: d["name"] for d in store.databases()}
    src = names.get(int(db_from))
    lines = [i for i in m["inputs"] if i["kind"] == "activity" and (i["target"].get("db") == src or
                                                                    (i["missing"] and i["ref_db"] == src))]
    ids = [i["ref_id"] for i in lines if i["ref_id"] and not i["missing"]]
    pairs, _ = match_activities(store, int(db_from), int(db_to), ids) if ids else ([], [])
    to = {a["id"]: b for a, b, _ in pairs}
    by_key = {}
    if any(i["missing"] for i in lines):
        for r in store.q("SELECT id, key, name, unit FROM activities WHERE db_id=?", (int(db_to),)):
            by_key[r["key"]] = r
    plan = []
    for i in lines:
        b = to.get(i["ref_id"]) if not i["missing"] else by_key.get(i["ref_key"])
        plan.append({"input_id": i["id"], "name": i["label"] or i["target"]["name"], "found": bool(b),
                     "new_id": b["id"] if b else None, "new_name": b["name"] if b else None})
    if apply:
        todo = [p for p in plan if p["found"]]
        if todo:
            store.snapshot(int(model_id), f"relink to {names.get(int(db_to))}")
            for p in todo:
                r = store.one("SELECT a.key, d.name FROM activities a JOIN databases d ON d.id=a.db_id WHERE a.id=?",
                              (p["new_id"],))
                store.update_input(p["input_id"], {"ref_id": p["new_id"], "ref_db": r["name"], "ref_key": r["key"]})
    return {"lines": plan, "n_found": sum(p["found"] for p in plan), "n_missing": sum(not p["found"] for p in plan),
            "applied": bool(apply)}


# ============================================================================ checks
_VER = re.compile(r"\b(v(?:ersion)?\s?)?\d+(\.\d+)+[a-z]?\b|\b(19|20)\d\d\b", re.I)


def method_versions(families):
    """Groups of selected method families that are different versions of the same method."""
    base = {}
    for f in families:
        b = _VER.sub("", f)
        b = re.sub(r"[\s,;:()\-]+", " ", b).strip().lower()
        if b:
            base.setdefault(b, set()).add(f)
    return [sorted(v) for v in base.values() if len(v) > 1]


def approach_issues(sc, used_db_models):
    """Consistency of the modelling approach (ISO 14044 4.2.3.3, 4.3.4.2) with allocation and database system model."""
    out = []
    ap = (sc.get("approach") or "").lower()
    models = {(m or "").lower() for m in used_db_models if m}
    if ap.startswith("conseq"):
        if (sc.get("alloc_basis") or "") in ("mass", "price", "energy"):
            out.append(("warning", "A consequential study should avoid allocation by system expansion (substitution), "
                                   "not divide burdens by mass, price or energy."))
        attr = [m for m in models if "cut" in m or "apos" in m or "allocation" in m or "en15804" in m]
        if attr:
            out.append(("warning", f"The study is consequential but uses attributional background data "
                                   f"({', '.join(sorted(attr))}). Use a consequential system model, or explain why."))
    elif ap.startswith("attr"):
        if any("conseq" in m for m in models):
            out.append(("warning", "The study is attributional but uses consequential background data. Use an "
                                   "attributional system model (e.g. cut-off or APOS) or explain why."))
    return out


def energy_balance(model, lines):
    """Energy delivered vs energy carriers consumed when the functional unit is an amount of energy."""
    fu = (model.get("unit") or "").strip()
    to_mj = units.factor(fu, "MJ")
    if to_mj is None:
        return None
    out_mj = float(model.get("amount") or 0) * to_mj
    in_mj = 0.0
    n = 0
    for l in lines:
        if l["avoided"] or l["module_d"]:
            continue
        f = units.factor(l["input_unit"] or "", "MJ")
        if f is None or l["input_amount"] is None:
            continue
        in_mj += float(l["input_amount"]) * f
        n += 1
    if not n or in_mj <= 0 or out_mj <= 0:
        return None
    return {"output_mj": out_mj, "input_mj": in_mj, "efficiency": out_mj / in_mj}


# ============================================================================ correlated parameters
def correlated_draws(rng, dist, size, correlations):
    """Samples of parameter distributions where some pairs are rank-correlated through a Gaussian copula.
    `correlations` is a list of {"a": name, "b": name, "r": value}. Returns {name: array(size)}."""
    names = [p["name"] for p in dist]
    idx = {n: i for i, n in enumerate(names)}
    pairs = [(c["a"], c["b"], float(c["r"])) for c in correlations or []
             if c.get("a") in idx and c.get("b") in idx and c.get("a") != c.get("b")]
    if not pairs:
        return {p["name"]: calc.sample_param(rng, p, size) for p in dist}
    from scipy import stats
    involved = sorted({n for a, b, _ in pairs for n in (a, b)}, key=lambda n: idx[n])
    k = {n: i for i, n in enumerate(involved)}
    R = np.eye(len(involved))
    for a, b, r in pairs:
        if not -0.999 <= r <= 0.999:
            raise calc.LCAError(f"The correlation between {a} and {b} must be between -1 and 1.")
        R[k[a], k[b]] = R[k[b], k[a]] = r
    try:
        L = np.linalg.cholesky(R)
    except np.linalg.LinAlgError:
        raise calc.LCAError("The parameter correlations are not consistent with each other (the correlation matrix "
                            "is not positive definite). Lower one of them.")
    Z = rng.standard_normal((size, len(involved))) @ L.T
    U = np.clip(stats.norm.cdf(Z), 1e-12, 1 - 1e-12)
    out = {}
    for p in dist:
        if p["name"] in k:
            out[p["name"]] = calc._ppf_param(p, U[:, k[p["name"]]])
        else:
            out[p["name"]] = calc.sample_param(rng, p, size)
    return out
