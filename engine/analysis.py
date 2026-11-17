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
import numcheck
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


def _cost_items(ctx, model_id, mult, windows, path, depth, out, uncosted):
    """Every priced line of a model and its sub-models, as cost items with their purchase times.

    windows: the periods in which this model is in use, as (start, end, life_end). The top model has one window
    (0, study period or None, None). A sub-model line bought every R years opens one window per purchase,
    (t, min(t + R, end), t + R): its own lines are bought (and replaced) within that window only, and their service
    life ends at the latest when the sub-model is replaced."""
    if depth > 25:
        raise calc.LCAError("Models are nested more than 25 levels deep.")
    m = ctx.model(model_id)
    for inp in m["inputs"]:
        sign = -1.0 if inp["avoided"] else 1.0
        share = calc.line_share(m["scope"], inp)
        name = inp["label"] or inp["target"]["name"]
        y = float(inp.get("year") or 0)
        R = float(inp.get("replace_every") or 0)
        for v, what in ((y, "year"), (R, "replacement interval"), (inp.get("unit_cost") or 0, "cost per unit"),
                        (inp.get("cost_gsd") or 1, "price uncertainty")):
            if not math.isfinite(float(v)):
                raise calc.LCAError(f"'{name}': the {what} must be a finite number.")
        if y < 0 or R < 0:
            raise calc.LCAError(f"'{name}': years and replacement intervals cannot be negative.")
        if inp.get("unit_cost") is not None:
            c1 = _input_amount(ctx, model_id, inp) * float(inp["unit_cost"]) * sign * share * mult
            purchases = []
            for start, end, life in windows:
                t = start + y
                while end is None or t < end - 1e-9:
                    if len(purchases) >= MAX_PURCHASES:
                        raise calc.LCAError(f"'{name}' would be bought more than {MAX_PURCHASES:,} times in the study "
                                            "period: check its replacement interval.")
                    own = t + R if R > 0 else None
                    ends = [x for x in (own, life) if x is not None]
                    purchases.append((t, min(ends) if ends else None))
                    if R <= 0 or end is None:
                        break
                    t += R
            out.append({"model_id": model_id, "input_id": inp["id"], "path": path + [name], "c1": c1,
                        "purchases": purchases, "cost_type": inp.get("cost_type") or "",
                        "gsd": float(inp["cost_gsd"]) if inp.get("cost_gsd") else None, "R": R})
        elif inp["kind"] == "model":
            sub = ctx.model(inp["ref_id"])
            k = calc.line_amount(ctx, model_id, inp) / (sub["amount"] or 1.0) * sign * share
            sw = []
            for start, end, life in windows:
                t = start + y
                while end is None or t < end - 1e-9:
                    if len(sw) >= MAX_PURCHASES:
                        raise calc.LCAError(f"'{name}' would be bought more than {MAX_PURCHASES:,} times in the study "
                                            "period: check its replacement interval.")
                    if R > 0 and end is not None:
                        sw.append((t, min(t + R, end), min(t + R, life) if life is not None else t + R))
                        t += R
                    else:
                        sw.append((t, end, life))
                        break
            _cost_items(ctx, inp["ref_id"], mult * k, sw, path + [name], depth + 1, out, uncosted)
        else:
            uncosted.append(path + [name])


MAX_PURCHASES = 10_000     # per cost item: a guard against a replacement interval far shorter than the period


class _OneLine:
    """A view of the context in which one model has only the given line (to cost one line with its sub-models)."""

    def __init__(self, ctx, model_id, model):
        self._ctx, self._id, self._m = ctx, model_id, model

    def model(self, mid):
        return self._m if mid == self._id else self._ctx.model(mid)

    def __getattr__(self, k):
        return getattr(self._ctx, k)


ISO_15686_5 = ("construction", "operation", "maintenance", "end of life", "non-construction", "income",
               "externalities")


def lcc(ctx, model_id, iterations=2000, seed=42):
    """Life cycle cost per functional unit (ISO 15686-5), by line, stage and cost type. Returns None when no line has
    a cost.

    Per line with a price: purchases in the line's year and, with a replacement interval R, every R years within
    the study period. Each purchase in year y costs c x (1 + e)^y, with e the real price escalation of the line's
    cost type (step 2), and is discounted by (1 + r)^y. With a study period, the residual value of the last purchase
    (its remaining service life, depreciated linearly) is credited at the end of the period. Lines with a price
    uncertainty (geometric standard deviation) are sampled in a Monte Carlo of the discounted total."""
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
    # scopes saved before 1.8.3 may hold any number: check them here too
    import store as store_mod
    try:
        store_mod.check_scope_numbers(sc)
    except ValueError as e:
        raise calc.LCAError(str(e) + " Correct it in Goal & scope, life cycle cost.")
    rate = float(sc.get("lcc_rate") or 0) / 100.0
    period = float(sc.get("lcc_period") or 0)
    if rate <= -1:
        raise calc.LCAError("The discount rate must be above -100 %.")
    esc = {}
    for k, v in (sc.get("lcc_escalation") or {}).items():
        try:
            esc[k] = float(v) / 100.0
        except (TypeError, ValueError):
            raise calc.LCAError(f"The price escalation of '{k}' must be a number (percent per year).")
        if esc[k] <= -1:
            raise calc.LCAError("A price escalation must be above -100 % per year.")
    residual_on = sc.get("lcc_residual", True) is not False
    T = period if period > 0 else None

    def value(it):
        """Purchases, residual value and their discounted values of one cost item."""
        e = esc.get(it["cost_type"] or "not classified", esc.get("all", 0.0))
        c = d = res = res_d = 0.0
        for t, life_end in it["purchases"]:
            ct = it["c1"] * (1 + e) ** t
            c += ct
            d += ct / (1 + rate) ** t
            # linear depreciation over the service life actually used; credited at the end of the study period
            if residual_on and T is not None and life_end is not None and t < T < life_end - 1e-12:
                r = -ct * (life_end - T) / (life_end - t)
                res += r
                res_d += r / (1 + rate) ** T
        return c, d, res, res_d, e

    rows, n_unc, sampled, details = [], 0, [], []
    for inp in model["inputs"]:
        name = inp["label"] or inp["target"]["name"]
        stage = inp["stage"] or UNASSIGNED
        items, unc = [], []
        if inp.get("unit_cost") is None and inp["kind"] != "model":
            n_unc += 1
            continue
        # the line itself, or its sub-model with every level below, through the same purchase rules
        one = dict(model, inputs=[inp])
        ctx_one = _OneLine(ctx, model_id, one)
        _cost_items(ctx_one, model_id, 1.0, [(0.0, T, None)], [], 0, items, unc)
        if not items:
            n_unc += 1
            continue
        c = d = residual = residual_d = 0.0
        e_line = None
        for it in items:
            ci, di, ri, rdi, e = value(it)
            c += ci
            d += di
            residual += ri
            residual_d += rdi
            e_line = e if e_line is None else e_line
            if it["gsd"]:
                sampled.append(((it["model_id"], it["input_id"]), it["gsd"], len(rows), di + rdi))
            if inp["kind"] == "model":
                details.append({"line": name, "path": " > ".join(it["path"]), "purchases": len(it["purchases"]),
                                "first_year": it["purchases"][0][0] if it["purchases"] else None,
                                "cost": ci + ri, "discounted": di + rdi, "residual_value": ri,
                                "escalation_percent": e * 100, "cost_type": it["cost_type"] or "not classified",
                                "cost_gsd": it["gsd"]})
        src = "line" if inp["kind"] != "model" or inp.get("unit_cost") is not None else "sub-model"
        rows.append({"input_id": inp["id"], "name": name, "stage": stage, "year": float(inp.get("year") or 0),
                     "cost": c + residual, "discounted": d + residual_d, "purchases": c, "residual_value": residual,
                     "residual_discounted": residual_d,
                     "escalation_percent": (e_line or 0.0) * 100 if src == "line" else None,
                     "cost_type": inp.get("cost_type") or "",
                     "replacements": sum(len(it["purchases"]) for it in items) - len(items),
                     "cost_gsd": inp.get("cost_gsd"), "module_d": calc.is_module_d(sc, inp["stage"]), "source": src,
                     "priced_lines": len(items), "unpriced_lines_below": len(unc), "revenue": c + residual < 0})
    ac = [r for r in rows if not r["module_d"]]
    stages = []
    for r in ac:
        if r["stage"] not in stages:
            stages.append(r["stage"])
    by_stage = [{"stage": s, "cost": sum(r["cost"] for r in ac if r["stage"] == s),
                 "discounted": sum(r["discounted"] for r in ac if r["stage"] == s)} for s in stages]
    by_type = {}
    for r in ac:
        t = r["cost_type"] or "not classified"
        by_type.setdefault(t, {"type": t, "cost": 0.0, "discounted": 0.0})
        by_type[t]["cost"] += r["cost"]
        by_type[t]["discounted"] += r["discounted"]
    total_d = sum(r["discounted"] for r in ac)
    unc = None
    samp = [(key, g, i, v) for key, g, i, v in sampled if not rows[i]["module_d"]]
    if samp:
        rng = np.random.default_rng(seed)
        n = int(max(200, min(iterations, 20000)))
        tot = np.full(n, total_d)
        draws = {}
        for key, g, i, v in samp:
            # a price known within a factor g: lognormal multiplier with median 1 on every cost of that priced line,
            # the same draw wherever the line is used (one price)
            if key not in draws:
                draws[key] = np.exp(rng.standard_normal(n) * math.log(g))
            tot += v * (draws[key] - 1.0)
        unc = {"iterations": n, "lines": len(draws), "median": float(np.median(tot)), "mean": float(tot.mean()),
               "p2_5": float(np.percentile(tot, 2.5)), "p97_5": float(np.percentile(tot, 97.5))}
    rows.sort(key=lambda r: -abs(r["cost"]))
    return {"currency": (sc.get("lcc_currency") or "EUR").strip() or "EUR", "rate_percent": rate * 100,
            "total": sum(r["cost"] for r in ac), "total_discounted": total_d,
            "residual_value": sum(r["residual_value"] for r in ac),
            "residual_value_discounted": sum(r["residual_discounted"] for r in ac),
            "escalation": {k: v * 100 for k, v in esc.items()}, "uncertainty": unc,
            "beyond_boundary": sum(r["cost"] for r in rows if r["module_d"]), "by_stage": by_stage,
            "by_type": list(by_type.values()), "study_period": period, "lines": rows,
            "n_costed": len(rows), "n_uncosted": n_unc, "iso_categories": list(ISO_15686_5),
            "sub_model_items": details,
            "note": "Costs per functional unit from the prices entered in step 3 (price per unit of the amount). "
                    "Credit lines with a price count as revenue. Each purchase is escalated with the real price "
                    "escalation of its cost type and discounted with the rate in step 2 and its year (net present cost, "
                    "ISO 15686-5). A line with a replacement interval is bought again every interval within the study "
                    "period, and the remaining service life of its last purchase is credited at the end of the period "
                    "(residual value, linear). Sub-models follow the same rules at every level: their priced lines are bought "
                    "with the sub-model, replaced within it, escalated by their own cost type and sampled with their own "
                    "price uncertainty; a sub-model replaced every R years buys its lines again each time. Module D "
                    "lines are reported apart. Only the costs you entered are included: lines without a price count as "
                    "zero."}


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
    v = {k: numcheck.finite(p.get(k) if p.get(k) not in (None, "") else CFF_DEFAULTS[k], k) for k in CFF_DEFAULTS}
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
    if mass in (None, ""):
        raise ValueError("Give the mass of the material (more than zero).")
    mass = numcheck.finite(mass, "The mass of the material", lo=0, lo_open=True)
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


# ============================================================================ end-of-life approaches side by side
EOL_APPROACHES = ("cut-off", "end-of-life recycling", "50:50", "Circular Footprint Formula")
EOL_ROLES = ("virgin", "recycled", "recycling_eol", "avoided_virgin", "disposal")


def eol_coefficients(p):
    """Amount of each role per unit of material under four ways of modelling recycling, for recycled content R1 and
    end-of-life recycling rate R2 (Ekvall et al. 2020, IVL report C551, equations for the cut-off, end-of-life recycling
    in its consequential form, 50/50 and the Circular Footprint Formula; energy recovery is left out of the
    comparison, R3 = 0):
      cut-off                 (1-R1) Ev + R1 ERin + (1-R2) ED
      end-of-life recycling   Ev + R2 (ERout - E*v) + (1-R2) ED
      50:50                   0.5 [(1-R1) + (1-R2)] (Ev + ED) + 0.5 (R1 ERin + R2 ERout)
      CFF                     (1-R1) Ev + R1 [A ERin + (1-A) Ev Qsin/Qp] + (1-A) R2 [ERout - E*v Qsout/Qp] + (1-R2) ED
    Roles: virgin Ev, recycled ERin, recycling_eol ERout, avoided_virgin E*v (a credit, negative), disposal ED."""
    lines, v = cff_lines(dict(p or {}, R3=0, B=0, LHV=0, X_heat=0, X_elec=0))
    R1, R2, A, qi, qo = v["R1"], v["R2"], v["A"], v["Qsin"], v["Qsout"]
    half = 0.5 * ((1 - R1) + (1 - R2))
    co = {
        "cut-off": {"virgin": 1 - R1, "recycled": R1, "recycling_eol": 0.0, "avoided_virgin": 0.0, "disposal": 1 - R2},
        "end-of-life recycling": {"virgin": 1.0, "recycled": 0.0, "recycling_eol": R2, "avoided_virgin": -R2,
                                  "disposal": 1 - R2},
        "50:50": {"virgin": half, "recycled": 0.5 * R1, "recycling_eol": 0.5 * R2, "avoided_virgin": 0.0,
                  "disposal": half},
        "Circular Footprint Formula": {"virgin": (1 - R1) + R1 * (1 - A) * qi, "recycled": R1 * A,
                                       "recycling_eol": (1 - A) * R2, "avoided_virgin": -(1 - A) * R2 * qo,
                                       "disposal": 1 - R2},
    }
    return co, v


def eol_compare(store, params, datasets, method_ids, mass=1.0, unit="kg"):
    """Results of `mass` of a material under the four approaches, for each impact category, with the share of each
    role. `datasets` maps a role to a dataset id (avoided_virgin: the virgin dataset when not given); a role with a
    zero coefficient in every approach needs no dataset."""
    co, v = eol_coefficients(params)
    mass = numcheck.finite(mass, "The mass of the material", lo=0, lo_open=True)
    method_ids = [numcheck.identifier(m, "method_ids") for m in method_ids or []]
    if not method_ids:
        raise ValueError("Choose at least one impact category.")
    need = [r for r in EOL_ROLES if any(abs(co[a][r]) > 1e-12 for a in co)]
    mc = calc._cache.get(store)
    M = calc.Methods(store, mc, method_ids)
    score, used = {}, {}
    for role in need:
        aid = datasets.get(role) or (datasets.get("virgin") if role == "avoided_virgin" else None)
        if not aid:
            raise ValueError(f"Choose a dataset for {CFF_LABEL[role]}.")
        a = store.activity(numcheck.identifier(aid, f"The dataset for {CFF_LABEL[role]}"))
        if not a:
            raise ValueError(f"The dataset for {CFF_LABEL[role]} is not in the library.")
        fac = units.factor(unit or "kg", a["unit"])
        if fac is None:
            raise ValueError(f"The dataset for {CFF_LABEL[role]} is in {a['unit']}, which cannot be converted from "
                             f"{unit}. Pick a dataset per unit of mass.")
        j = mc.act_index[a["id"]]
        f = np.zeros(mc.n)
        f[j] = 1.0 if mc.diag[j] >= 0 else -1.0
        score[role] = (M.Q @ mc.solve(f)) * fac * mass        # result of `mass` of material through this dataset
        used[role] = {"id": a["id"], "name": a["name"], "location": a["location"], "unit": a["unit"],
                      "amount_per_unit_material": fac}
    rows = []
    for k, m in enumerate(M.rows):
        r = {"method_id": m["id"], "family": m["family"], "category": m["category"], "indicator": m["indicator"],
             "unit": m["unit"], "approaches": {}}
        for ap in EOL_APPROACHES:
            parts = {role: float(co[ap][role] * score[role][k]) for role in need}
            r["approaches"][ap] = {"total": float(sum(parts.values())), "parts": parts}
        rows.append(r)
    return {"approaches": list(EOL_APPROACHES), "coefficients": co, "parameters": {k: v[k] for k in
                                                                                  ("A", "R1", "R2", "Qsin", "Qsout")},
            "datasets": used, "mass": mass, "unit": unit, "results": rows,
            "note": "Energy recovery is not part of this comparison (R3 = 0). Formulas: Ekvall et al. (2020), "
                    "'Modeling recycling in life cycle assessment', IVL report C551, and the PEF Circular Footprint "
                    "Formula (Commission Recommendation (EU) 2021/2279, Annex C)."}


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


def _model_tree(store, model_id, seen=None):
    """The model and every model nested in it (depth first, each once)."""
    seen = seen if seen is not None else []
    if model_id in seen:
        return seen
    seen.append(model_id)
    m = store.model(model_id)
    for i in (m or {}).get("inputs", []):
        if i["kind"] == "model" and i["ref_id"]:
            _model_tree(store, i["ref_id"], seen)
    return seen


MIGRATION_LABEL = "database migration"


def relink_plan(store, model_id, db_from, db_to, apply=False, method_ids=None):
    """Map every activity line of a model and of all models nested in it from one database to another. With
    apply=True the lines are switched; each changed model gets one undo step, and `undo_migration` reverses all of
    them. With method_ids, the results before and after are returned."""
    import calc
    m = store.model(int(model_id))
    if not m:
        raise ValueError("Model not found.")
    if int(db_from) == int(db_to):
        raise ValueError("Choose two different databases.")
    names = {d["id"]: d["name"] for d in store.databases()}
    src, dst = names.get(int(db_from)), names.get(int(db_to))
    if not src or not dst:
        raise ValueError("Database not found.")
    plan, by_model = [], {}
    for mid in _model_tree(store, int(model_id)):
        mm = store.model(mid)
        lines = [i for i in mm["inputs"] if i["kind"] == "activity" and (i["target"].get("db") == src or
                                                                          (i["missing"] and i["ref_db"] == src))]
        if not lines:
            continue
        ids = [i["ref_id"] for i in lines if i["ref_id"] and not i["missing"]]
        pairs, _ = match_activities(store, int(db_from), int(db_to), ids) if ids else ([], [])
        to = {a["id"]: b for a, b, _ in pairs}
        by_key = {}
        if any(i["missing"] for i in lines):
            by_key = {r["key"]: r for r in store.q("SELECT id, key, name, unit FROM activities WHERE db_id=?", (int(db_to),))}
        for i in lines:
            b = to.get(i["ref_id"]) if not i["missing"] else by_key.get(i["ref_key"])
            row = {"model_id": mid, "model": mm["name"], "input_id": i["id"], "name": i["label"] or i["target"]["name"],
                   "found": bool(b), "new_id": b["id"] if b else None, "new_name": b["name"] if b else None}
            plan.append(row)
            by_model.setdefault(mid, []).append(row)
    out = {"lines": plan, "n_found": sum(p["found"] for p in plan), "n_missing": sum(not p["found"] for p in plan),
           "models": [{"id": mid, "name": store.model(mid)["name"], "n_lines": len(rows)} for mid, rows in by_model.items()],
           "applied": False, "changed_models": []}
    if not apply:
        return out
    before = None
    if method_ids:
        try:
            before = [x["total"] for x in calc.run(store, int(model_id), method_ids, top=1)["results"]]
        except calc.LCAError:
            before = None
    for mid, rows in by_model.items():
        todo = [p for p in rows if p["found"]]
        if not todo:
            continue
        store.snapshot(mid, f"{MIGRATION_LABEL} to {dst}")
        for p in todo:
            r = store.one("SELECT a.key, d.name FROM activities a JOIN databases d ON d.id=a.db_id WHERE a.id=?",
                          (p["new_id"],))
            store.update_input(p["input_id"], {"ref_id": p["new_id"], "ref_db": r["name"], "ref_key": r["key"]})
        out["changed_models"].append(mid)
    out["applied"] = True
    if method_ids and out["changed_models"]:
        try:
            r = calc.run(store, int(model_id), method_ids, top=1)
            after = [x["total"] for x in r["results"]]
            out["results"] = [{"category": x["category"], "unit": x["unit"], "before": b, "after": a,
                               "change_percent": ((a - b) / abs(b) * 100) if (b is not None and abs(b) > 1e-30) else None}
                              for x, a, b in zip(r["results"], after, before or [None] * len(after))]
        except calc.LCAError as e:
            out["results_error"] = str(e)
    return out


def undo_migration(store, model_ids):
    """Reverse a migration in every model it changed. Refuses a model whose last change is not the migration."""
    done, skipped = [], []
    for mid in model_ids:
        h = store.one("SELECT label FROM main.history WHERE model_id=? ORDER BY id DESC LIMIT 1", (int(mid),))
        if h and (h["label"] or "").startswith(MIGRATION_LABEL):
            store.undo(int(mid))
            done.append(int(mid))
        else:
            skipped.append(int(mid))
    return {"undone": done, "skipped": skipped}


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
    """Samples of parameter distributions where some pairs have a given Spearman rank correlation (Gaussian copula,
    latent correlation 2 sin(pi rho / 6)). `correlations` is a list of {"a": name, "b": name, "r": rho}."""
    import hier
    var_list = [{"key": ("p", p["name"]), "p": p} for p in dist]
    keys = {v["key"] for v in var_list}
    pairs = [(("p", c["a"]), ("p", c["b"]), numcheck.finite(c.get("r"), f"The correlation of {c.get('a')} and {c.get('b')}",
                                                            -1, 1)) for c in correlations or []
             if ("p", c.get("a")) in keys and ("p", c.get("b")) in keys and c.get("a") != c.get("b")]
    d = hier.draw(rng, var_list, size, pairs)
    return {k[1]: v for k, v in d.items()}


# ============================================================================ consequential: marginal suppliers
CONSTRAINED_WORDS = ("recycled", "recycling", "secondary", "by-product", "byproduct", "co-product", "coproduct", "waste",
                     "treatment of", "scrap", "used ", "reuse", "re-use", "residue", "cut-off")


def constrained_reason(name, product):
    t = f"{name or ''} {product or ''}".lower()
    hit = next((w.strip() for w in CONSTRAINED_WORDS if w in t), None)
    return (f"'{hit}' in the name: a by-product, recycled or waste-based supply is usually constrained (its output "
            "does not follow demand)") if hit else ""


def marginal_guidance(store, model_id):
    """For every market in the supply chain of a model: its suppliers, which are likely constrained (by-products,
    recycled or waste-based supply, Weidema et al. 2009), and a proposed marginal supplier among the unconstrained
    ones. The proposal is a starting point only: the marginal supplier is the one whose output changes when demand
    changes, normally the most competitive unconstrained technology in a growing market, which needs market data."""
    import science
    out = []
    for m in science.markets(store, model_id):
        sup = []
        for x in m["suppliers"]:
            reason = constrained_reason(x["name"], x.get("product"))
            sup.append({"id": x["id"], "name": x["name"], "location": x["location"], "share": x["share"],
                        "constrained": bool(reason), "reason": reason})
        free = [x for x in sup if not x["constrained"]]
        prop = max(free, key=lambda x: x["share"]) if free else None
        rule = None
        if prop:
            rule = {"type": "swap", "activity_ids": [m["market"]["id"]], "product": m["product_root"],
                    "to": [{"id": prop["id"], "share": 1.0}],
                    "note": f"marginal supplier of {m['product_root']} in {m['market']['name']}"}
        out.append({"market": {k: m["market"][k] for k in ("id", "name", "location", "product")},
                    "product": m["product_root"], "suppliers": sup, "proposal": prop, "rule": rule,
                    "all_constrained": not free})
    return {"markets": out,
            "guidance": "ISO 14044 4.3.4.2 and the consequential approach (Weidema et al. 2009): for each market, the "
                        "marginal supplier is the unconstrained supplier that would respond to a change in demand. "
                        "Cyclia excludes suppliers that look constrained (by-products, recycled, waste-based) and "
                        "proposes the unconstrained supplier with the largest current share as a starting point. "
                        "Confirm or change it with market trends (which technology is growing and competitive), then "
                        "create a consequential background scenario from the chosen suppliers."}
