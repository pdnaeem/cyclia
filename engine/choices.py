"""Optimisation of discrete choices (scenario optimisation), Cyclia 1.8.0.

The parameter optimisation of productivity.py moves continuous parameters within bounds; this module chooses among
discrete alternatives.

Decision support over discrete choices: for some lines of a model the user lists alternatives (another dataset or
sub-model, with its amount and, if known, its cost). Cyclia evaluates every combination and returns the best one for
one objective (an impact category or the purchase cost) under limits on other categories, and the Pareto set: the
combinations that no other combination improves in every chosen dimension at once.

Method. A model result is linear in its lines: total = sum over lines of (unit impact x amount x sign x allocation
share). Exchanging the dataset of line j changes the total by u_alt a_alt s_j f - u_j a_j s_j f, independently of the
other lines, so the totals of all combinations follow from one unit-impact calculation per alternative. The search
is exhaustive (exact), limited to 200 000 combinations. The cost dimension is the purchase cost per functional unit
of the chosen lines (amount x cost per unit), available when every alternative of every choice has a cost.

The results are deterministic. A choice between combinations whose totals are close should be checked with the
comparative Monte Carlo (save the combination as a model first).
"""
import itertools

import numpy as np

import calc
import numcheck
import units

MAX_COMBINATIONS = 200_000


class OptimiseError(ValueError):
    pass


def _id(v, what):
    return numcheck.identifier(v, what, err=OptimiseError)


def _fin(v, what):
    return numcheck.finite(v, what, err=OptimiseError)


def _target(store, kind, ref_id):
    if kind == "activity":
        r = store.one("SELECT id, name, unit, location FROM activities WHERE id=?", (_id(ref_id, "ref_id"),))
        if r:
            return {"name": f"{r['name']} [{r['location']}]", "unit": r["unit"]}
    elif kind == "model":
        r = store.one("SELECT id, name, unit FROM main.models WHERE id=?", (_id(ref_id, "ref_id"),))
        if r:
            return {"name": r["name"], "unit": r["unit"]}
    else:
        raise OptimiseError("An alternative is a dataset or a model.")
    raise OptimiseError("An alternative points to a dataset or model that does not exist.")


def _prepare(store, model_id, method_ids, slots, scenario=None, bg=None):
    method_ids = [_id(m, "method_ids") for m in method_ids or []]
    if not method_ids:
        raise OptimiseError("Pick the impact categories in step 4 first.")
    base = calc.run(store, model_id, method_ids, scenario=scenario, bg=bg)
    lines = {l["input_id"]: l for l in base["lines"]} if "lines" in base else None
    if lines is None:
        raise OptimiseError("The model could not be calculated.")
    ctx = calc.Context(store, calc._scenario(store, scenario))
    model = ctx.model(model_id)
    inputs = {i["id"]: i for i in model["inputs"]}
    mc = calc.get_mc(store, bg)
    M = calc.Methods(store, mc, method_ids)
    if not slots:
        raise OptimiseError("Add at least one line with alternatives.")
    prepared = []
    seen = set()
    warnings = []
    for s in slots:
        iid = _id(s.get("input_id"), "input_id")
        if iid not in inputs:
            raise OptimiseError("A choice refers to a line that is not in this model.")
        if iid in seen:
            raise OptimiseError("Each line can be a choice once.")
        seen.add(iid)
        inp, ln = inputs[iid], lines[iid]
        if ln["module_d"]:
            raise OptimiseError(f"'{ln['name']}' is in module D, which is reported apart from the total.")
        if inp["kind"] not in ("activity", "model"):
            raise OptimiseError(f"'{ln['name']}': only dataset and model lines can be exchanged.")
        sign = -1.0 if inp["avoided"] else 1.0
        if inp.get("derived"):
            raise OptimiseError(f"'{ln['name']}' is a system expansion credit; change what it replaces in step 2.")
        share = calc.line_share(model["scope"], inp)
        cur_cost = None
        if inp.get("unit_cost") is not None:
            cur_cost = float(inp["unit_cost"]) * float(ln["input_amount"] if ln["input_amount"] is not None
                                                       else ln["amount"]) * sign * share
        opts = [{"label": "current: " + ln["name"], "current": True, "impact": np.array(ln["impact"], float),
                 "cost": cur_cost, "kind": inp["kind"], "ref_id": inp["ref_id"], "amount": inp["input_amount"],
                 "unit": inp["input_unit"]}]
        alts = s.get("options") or []
        if not alts:
            raise OptimiseError(f"'{ln['name']}': give at least one alternative.")
        if len(alts) > 25:
            raise OptimiseError("At most 25 alternatives per line.")
        for o in alts:
            kind = o.get("kind") or "activity"
            tgt = _target(store, kind, o.get("ref_id"))
            if o.get("amount") in (None, ""):
                raise OptimiseError(f"Give the amount of '{tgt['name']}'.")
            amount = numcheck.finite(o.get("amount"), f"The amount of '{tgt['name']}'", lo=0, err=OptimiseError)
            unit = (o.get("unit") or tgt["unit"] or "").strip()
            fac = units.factor(unit, tgt["unit"]) if unit else 1.0
            if fac is None:
                raise OptimiseError(f"'{unit}' cannot be converted to the unit of '{tgt['name']}' ({tgt['unit']}).")
            a, fl, fx = calc.line_unit_demand(ctx, {"kind": kind, "ref_id": _id(o["ref_id"], "ref_id")})
            u, _, _ = calc.impacts(mc, M, a, fl, fx)
            cost = None
            if o.get("unit_cost") not in (None, ""):
                uc = numcheck.finite(o["unit_cost"], f"The cost per unit of '{tgt['name']}'", err=OptimiseError)
                cost = uc * amount * sign * share
            cur_unit = inp["input_unit"] or inp["target"]["unit"]
            if cur_unit and units.factor(unit, cur_unit) is None:
                warnings.append(f"'{o.get('label') or tgt['name']}' is given in {unit}, the line '{ln['name']}' in "
                                f"{cur_unit}: check that the amount fulfils the same function.")
            opts.append({"label": o.get("label") or tgt["name"], "current": False,
                         "impact": u * amount * fac * sign * share, "cost": cost, "kind": kind,
                         "ref_id": _id(o["ref_id"], "ref_id"), "amount": amount, "unit": unit,
                         "unit_cost": None if cost is None else float(o["unit_cost"])})
        prepared.append({"input_id": iid, "name": ln["name"], "options": opts})
    totals = np.array([r["total"] for r in base["results"]], float)
    base["_warnings"] = warnings
    return base, prepared, totals


def optimise(store, model_id, method_ids, slots, objective, constraints=(), scenario=None, bg=None, pareto=None):
    """objective: {"method_id": id} or {"cost": true}. constraints: [{"method_id" or "cost", "max": value} or
    {..., "max_change_pct": p}] (p relative to the current total; 0 = no worse than now)."""
    base, prepared, totals = _prepare(store, model_id, method_ids, slots, scenario, bg)
    method_ids = [r["method_id"] for r in base["results"]]
    n_comb = 1
    for p in prepared:
        n_comb *= len(p["options"])
    if n_comb > MAX_COMBINATIONS:
        raise OptimiseError(f"{n_comb:,} combinations; the limit is {MAX_COMBINATIONS:,}. Remove alternatives or "
                            "choices.")
    has_cost = all(o["cost"] is not None for p in prepared for o in p["options"])

    def dim(spec):
        if spec.get("cost"):
            if not has_cost:
                raise OptimiseError("The cost needs a cost per unit on every current line and every alternative.")
            return "cost"
        mid = _id(spec.get("method_id"), "method_id")
        if mid not in method_ids:
            raise OptimiseError("An objective or limit refers to a category that is not selected in step 4.")
        return method_ids.index(mid)

    obj = dim(objective or {})
    lims = []
    for c in constraints or ():
        d = dim(c)
        lims.append((d, c))
    # delta tables: options x (categories + cost)
    k = len(method_ids)
    deltas = []
    for p in prepared:
        cur = p["options"][0]
        rows = []
        for o in p["options"]:
            dc = (o["cost"] - cur["cost"]) if has_cost else 0.0
            rows.append(np.concatenate([o["impact"] - cur["impact"], [dc]]))
        deltas.append(np.array(rows))
    base_cost = None
    if has_cost:
        # purchase cost per functional unit of the model's own lines that carry a cost per unit
        model = store.model(_id(model_id, "model_id"))
        lines = {l["input_id"]: l for l in base["lines"]}
        base_cost = 0.0
        for inp in model["inputs"]:
            ln = lines.get(inp["id"])
            if inp.get("unit_cost") is None or not ln or ln["module_d"]:
                continue
            amt = ln["input_amount"] if ln["input_amount"] is not None else ln["amount"]
            base_cost += float(inp["unit_cost"]) * float(amt) * (-1.0 if inp["avoided"] else 1.0) * \
                calc.line_share(model["scope"], inp)
    base_vec = np.concatenate([totals, [base_cost if base_cost is not None else 0.0]])
    combos = np.array(list(itertools.product(*[range(len(p["options"])) for p in prepared])), dtype=np.int64)
    vals = np.tile(base_vec, (len(combos), 1))
    for j, D in enumerate(deltas):
        vals += D[combos[:, j]]
    idx = lambda d: k if d == "cost" else d  # noqa: E731
    ok = np.ones(len(combos), bool)
    lim_out = []
    for d, c in lims:
        col = idx(d)
        if c.get("max") not in (None, ""):
            bound = _fin(c["max"], "A limit")
        elif c.get("max_change_pct") not in (None, ""):
            bound = base_vec[col] + abs(base_vec[col]) * _fin(c["max_change_pct"], "A limit in %") / 100.0
        else:
            raise OptimiseError("A limit needs a maximum or a maximum change in %.")
        ok &= vals[:, col] <= bound + 1e-12 * max(1.0, abs(bound))
        lim_out.append({"dimension": "cost" if d == "cost" else method_ids[d], "max": bound})
    labels = [r["category"] + (f" ({r['indicator']})" if r.get("indicator") else "") for r in base["results"]]
    unitsl = [r["unit"] for r in base["results"]]

    def describe(i):
        ch = [{"input_id": p["input_id"], "line": p["name"], "option": int(combos[i, j]),
               "choice": p["options"][combos[i, j]]["label"], "current": p["options"][combos[i, j]]["current"]}
              for j, p in enumerate(prepared)]
        return {"choices": ch, "totals": vals[i, :k].tolist(), "cost": float(vals[i, k]) if has_cost else None}

    out = {"combinations": int(len(combos)), "feasible": int(ok.sum()), "categories": labels, "units": unitsl,
           "method_ids": method_ids, "baseline": {"totals": totals.tolist(), "cost": base_cost},
           "objective": "cost" if obj == "cost" else method_ids[obj], "limits": lim_out, "has_cost": has_cost,
           "warnings": base["_warnings"],
           "lines": [{"input_id": p["input_id"], "name": p["name"],
                      "options": [{"label": o["label"], "delta": deltas[j][i, :k].tolist(),
                                   "delta_cost": float(deltas[j][i, k]) if has_cost else None}
                                  for i, o in enumerate(p["options"])]} for j, p in enumerate(prepared)]}
    if ok.any():
        col = idx(obj)
        cand = np.where(ok)[0]
        best = cand[np.argmin(vals[cand, col])]
        out["best"] = describe(best)
        # ties: a combination equal in the objective is reported, the choice between them is the user's
        tie = cand[np.abs(vals[cand, col] - vals[best, col]) <= 1e-9 * max(1.0, abs(vals[best, col]))]
        out["ties"] = int(len(tie)) - 1
    else:
        out["best"] = None
    # Pareto set over the objective and the limited dimensions, or over all categories (and cost) without limits.
    # Sorted lexicographically, a later point can never dominate an earlier one, so one pass suffices.
    if lims:
        dims = [idx(obj)] + [d for d in dict.fromkeys(idx(d) for d, _ in lims) if d != idx(obj)]
    else:
        dims = list(range(k)) + ([k] if has_cost else [])
    if pareto:
        dims = [int(d) for d in pareto]
    P = vals[:, dims]
    order = np.lexsort(P.T[::-1])
    F = np.empty((0, len(dims)))
    front = []
    for i in order:
        p = P[i]
        if len(front) and (np.any(np.all(F <= p, axis=1) & np.any(F < p, axis=1)) or np.any(np.all(F == p, axis=1))):
            continue
        front.append(i)
        F = np.vstack([F, p])
        if len(front) >= 2000:
            # every point kept so far is non-dominated (later points cannot dominate earlier ones), so the
            # set found is correct but may be incomplete
            break
    out["pareto_complete"] = len(front) < 2000
    out["pareto_dimensions"] = [("cost" if d == k else method_ids[d]) for d in dims]
    out["pareto_size"] = len(front)
    out["pareto"] = [dict(describe(i), feasible=bool(ok[i])) for i in sorted(front, key=lambda i: vals[i, dims[0]])][:100]
    out["note"] = ("Every combination was evaluated exactly from the unit impacts of the alternatives (the model is "
                   "linear in its lines). Deterministic values: when the best combinations are close, save them as "
                   "models and compare them with the comparative Monte Carlo before concluding.")
    return out


def apply(store, model_id, method_ids, slots, choice, name=None, scenario=None, bg=None):
    """Save a combination as a copy of the model. choice: {input_id: option index} (0 = current)."""
    _, prepared, _ = _prepare(store, model_id, method_ids, slots, scenario, bg)
    m = store.model(_id(model_id, "model_id"))
    nid = store.duplicate_model(_id(model_id, "model_id"), name or (m["name"] + " (optimised)"))
    orig = [i["id"] for i in store.q("SELECT id FROM main.model_inputs WHERE model_id=? ORDER BY position, id",
                                     (_id(model_id, "model_id"),))]
    copy = [i["id"] for i in store.q("SELECT id FROM main.model_inputs WHERE model_id=? ORDER BY position, id", (nid,))]
    mapping = dict(zip(orig, copy))
    for p in prepared:
        j = numcheck.integer((choice or {}).get(str(p["input_id"]), (choice or {}).get(p["input_id"], 0)), "The alternative",
                             0, err=OptimiseError)
        if not 0 <= j < len(p["options"]):
            raise OptimiseError("Unknown alternative.")
        if j == 0:
            continue
        o = p["options"][j]
        old = store.get_input(mapping[p["input_id"]])
        tgt = _target(store, o["kind"], o["ref_id"])
        fac = units.factor(o["unit"], tgt["unit"]) if o["unit"] else 1.0
        new = store.add_input(nid, o["kind"], o["ref_id"], o["amount"] * fac, label=o["label"],
                              comment=f"Chosen by scenario optimisation instead of '{p['name']}'", stage=old["stage"],
                              input_amount=o["amount"], input_unit=o["unit"] or tgt["unit"],
                              avoided=bool(old["avoided"]), pedigree=json_list(old["pedigree"]))
        store.update_input(new, {"unit_cost": o.get("unit_cost"), "cost_type": old["cost_type"]})
        store.x("UPDATE main.model_inputs SET position=? WHERE id=?", (old["position"], new))
        store.delete_input(old["id"])
    return nid


def json_list(v):
    import json
    try:
        return json.loads(v) if isinstance(v, str) else (v or [3, 3, 3, 3, 3])
    except ValueError:
        return [3, 3, 3, 3, 3]
