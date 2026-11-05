"""Hierarchical foreground model for uncertainty, data quality and sensitivity (Cyclia 1.3.3).

A model is flattened into *paths*: chains of inventory lines from the top-level model through nested models down
to a leaf line (a dataset, an elementary flow or fixed EPD values). Each path has a deterministic amount per
functional unit (the product of the line amounts, signs, allocation shares and 1 / reference amount of every
sub-model on the way), and a unit result (impact per unit of the leaf).

Uncertainty is then propagated at every level:
- every line of every model, nested or not, gets its own lognormal factor from its own pedigree scores (a line
  that appears in several places, e.g. a sub-model used twice, keeps one draw, because it is one piece of data);
- every parameter distribution of every model and of the project is sampled, with the correlations each model
  defines (Spearman rank correlations through a Gaussian copula).
"""
import math

import numpy as np

import calc
import formula as fm


# ---------------------------------------------------------------------------------------------- structure
def build(ctx, model_id, keep=None):
    """Lines and leaf paths of a model. keep filters the top-level lines (e.g. module D out)."""
    out = {"lines": [], "index": {}, "leaves": [], "models": []}

    def walk(mid, chain, depth):
        if depth > 25:
            raise calc.LCAError("Models are nested more than 25 levels deep.")
        m = ctx.model(mid)
        if mid not in out["models"]:
            out["models"].append(mid)
        for inp in m["inputs"]:
            if depth == 0 and keep is not None and not keep(inp):
                continue
            if inp["missing"]:
                raise calc.LCAError(f"A line of '{m['name']}' points to a dataset that is not in this library"
                                    f"{' (database ' + inp['ref_db'] + ')' if inp['ref_db'] else ''}. Import it or remove "
                                    "the line.")
            if inp["id"] not in out["index"]:
                out["index"][inp["id"]] = len(out["lines"])
                out["lines"].append({"inp": inp, "owner": mid, "owner_name": m["name"], "depth": depth, "occ": [],
                                     "sigma": calc.pedigree_sigma(inp["pedigree"], inp["kind"], inp["target"]["name"])})
            out["lines"][out["index"][inp["id"]]]["occ"].append(chain)
            ch = chain + (out["index"][inp["id"]],)
            if inp["kind"] == "model":
                walk(inp["ref_id"], ch, depth + 1)
            else:
                out["leaves"].append({"chain": ch, "inp": inp})
    walk(model_id, (), 0)
    for lf in out["leaves"]:
        lf["credit"] = sum(1 for li in lf["chain"] if out["lines"][li]["inp"]["avoided"]) % 2 == 1
        lf["name"] = " > ".join((out["lines"][li]["inp"]["label"] or out["lines"][li]["inp"]["target"]["name"])
                                for li in lf["chain"])
    return out


def line_factor(ctx, T, li):
    """Signed amount of one line per unit of its owner, times the owner's allocation share, and divided by the
    reference amount of the sub-model it points to (so that the chain product is per functional unit)."""
    L = T["lines"][li]
    inp, owner = L["inp"], L["owner"]
    a = calc.line_amount(ctx, owner, inp) * (-1.0 if inp["avoided"] else 1.0)
    a *= calc.allocation_share(ctx.model(owner)["scope"])
    if inp["kind"] == "model":
        a /= (ctx.model(inp["ref_id"])["amount"] or 1.0)
    return a


def path_amounts(ctx, T):
    fac = [line_factor(ctx, T, li) for li in range(len(T["lines"]))]
    return np.array([math.prod(fac[li] for li in lf["chain"]) for lf in T["leaves"]], dtype=float)


def leaf_units(ctx, mc, M, T):
    """Impact per unit of each leaf (rows) for every method (columns)."""
    rows = []
    for lf in T["leaves"]:
        inp = lf["inp"]
        key = (inp["ref_id"], tuple(r["id"] for r in M.rows), bool(M.site)) if inp["kind"] == "activity" else None
        if key and key in mc.unit_cache:
            rows.append(mc.unit_cache[key][0])
            continue
        a, fl, fx = calc.line_unit_demand(ctx, inp)
        u, _, _ = calc.impacts(mc, M, a, fl, fx)
        rows.append(u)
    return np.array(rows, dtype=float).reshape(len(T["leaves"]), len(M.rows))


def needs_resampling(ctx, T, variables):
    """Amounts depend on sampled parameters when a line in the tree has a formula, or when a parameter with a
    distribution feeds the amount of a sub-model (via its formula)."""
    return bool(variables) and any(T["lines"][li]["inp"].get("formula") for li in range(len(T["lines"])))


# ---------------------------------------------------------------------------------------------- parameters
def variables(ctx, model_ids):
    """Every parameter with a distribution, once: ('p', name) for project parameters, ('m', model id, name) for
    model parameters. A model parameter hides a project parameter of the same name inside that model."""
    out, seen = [], set()
    for p in ctx.project_params:
        if (p["utype"] or 0) > 0 and not p.get("formula"):
            out.append({"key": ("p", p["name"]), "p": p})
            seen.add(("p", p["name"]))
    for mid in model_ids:
        for p in ctx.model(mid)["parameters"]:
            k = ("m", mid, p["name"])
            if (p["utype"] or 0) > 0 and not p.get("formula") and k not in seen:
                out.append({"key": k, "p": p})
                seen.add(k)
    return out


def _resolve(ctx, mid, name, keys):
    if ("m", mid, name) in keys:
        return ("m", mid, name)
    if ("p", name) in keys and name not in {p["name"] for p in ctx.model(mid)["parameters"]}:
        return ("p", name)
    return None


def correlation_pairs(ctx, model_ids, var_list):
    keys = {v["key"] for v in var_list}
    pairs = []
    for mid in model_ids:
        for c in (ctx.model(mid)["scope"] or {}).get("correlations") or []:
            a, b = _resolve(ctx, mid, c.get("a"), keys), _resolve(ctx, mid, c.get("b"), keys)
            if a and b and a != b:
                pairs.append((a, b, float(c.get("r") or 0)))
    return pairs


def spearman_to_pearson(rho):
    """Latent normal correlation that gives the Spearman rank correlation rho (Pearson 1907): r = 2 sin(pi rho / 6)."""
    return 2.0 * math.sin(math.pi * rho / 6.0)


def draw(rng, var_list, size, pairs=()):
    """Samples {key: array(size)}; correlated pairs through a Gaussian copula with the Spearman correlation given."""
    if not var_list:
        return {}
    if not pairs:
        return {v["key"]: calc.sample_param(rng, v["p"], size) for v in var_list}
    from scipy import stats
    idx = {v["key"]: i for i, v in enumerate(var_list)}
    involved = sorted({k for a, b, _ in pairs for k in (a, b)}, key=lambda k: idx[k])
    pos = {k: i for i, k in enumerate(involved)}
    R = np.eye(len(involved))
    for a, b, rho in pairs:
        if not -0.99 <= rho <= 0.99:
            raise calc.LCAError(f"The correlation between {a[-1]} and {b[-1]} must be between -0.99 and 0.99.")
        R[pos[a], pos[b]] = R[pos[b], pos[a]] = spearman_to_pearson(rho)
    try:
        L = np.linalg.cholesky(R)
    except np.linalg.LinAlgError:
        raise calc.LCAError("The parameter correlations are not consistent with each other (the correlation matrix is "
                            "not positive definite). Lower one of them.")
    Z = rng.standard_normal((size, len(involved))) @ L.T
    U = np.clip(stats.norm.cdf(Z), 1e-12, 1 - 1e-12)
    out = {}
    for v in var_list:
        if v["key"] in pos:
            out[v["key"]] = calc._ppf_param(v["p"], U[:, pos[v["key"]]])
        else:
            out[v["key"]] = calc.sample_param(rng, v["p"], size)
    return out


def context_for(store, overrides, base, sample_row):
    """Context whose parameters take one row of samples: project values for every model that does not define the
    name itself, model values only for their own model."""
    psample = {k[1]: v for k, v in sample_row.items() if k[0] == "p"}
    msample = {}
    for k, v in sample_row.items():
        if k[0] == "m":
            msample.setdefault(k[1], {})[k[2]] = v
    return calc.Context(store, overrides, base=base, psample=psample, msample=msample)


# ---------------------------------------------------------------------------------------------- Monte Carlo
def amounts_matrix(store, overrides, ctx0, T, var_list, draws, n):
    """Deterministic path amounts for every iteration (n x leaves)."""
    if not needs_resampling(ctx0, T, var_list):
        return np.tile(path_amounts(ctx0, T), (n, 1))
    out = np.zeros((n, len(T["leaves"])))
    for it in range(n):
        ctx = context_for(store, overrides, ctx0, {k: float(v[it]) for k, v in draws.items()})
        out[it] = path_amounts(ctx, T)
    return out


def multipliers(rng, T, n, shared=None):
    """Lognormal factor per line (n x lines). `shared` maps an input id to an existing column so that the same line
    in several compared models uses one draw."""
    sig = np.array([L["sigma"] for L in T["lines"]])
    if shared is None:
        return np.exp(rng.standard_normal((n, len(T["lines"]))) * sig)
    cols = []
    for L in T["lines"]:
        iid = L["inp"]["id"]
        if iid not in shared:
            shared[iid] = np.exp(rng.standard_normal(n) * L["sigma"])
        cols.append(shared[iid])
    return np.column_stack(cols) if cols else np.zeros((n, 0))


def path_multipliers(T, mult):
    """Product of the line factors along each path (n x leaves)."""
    if not T["leaves"]:
        return np.zeros((mult.shape[0], 0))
    logm = np.log(mult)
    return np.exp(np.column_stack([logm[:, list(lf["chain"])].sum(axis=1) for lf in T["leaves"]]))


def foreground_inventory(ctx, T):
    """Every line of the model and of all nested models, with its amount per unit of its own model and per
    functional unit (summed over every place it occurs), for the complete inventory and provenance annex."""
    fac = [line_factor(ctx, T, li) for li in range(len(T["lines"]))]
    rows = []
    for li, L in enumerate(T["lines"]):
        inp = L["inp"]
        own = fac[li] * ((ctx.model(inp["ref_id"])["amount"] or 1.0) if inp["kind"] == "model" else 1.0)
        per_fu = sum(math.prod(fac[p] for p in prefix) * own for prefix in L["occ"])
        path = [T["lines"][prefix[-1]]["owner_name"] for prefix in L["occ"] if prefix] if L["depth"] else []
        rows.append({"input_id": inp["id"], "model": L["owner_name"], "depth": L["depth"],
                     "name": inp["label"] or inp["target"]["name"], "kind": inp["kind"],
                     "dataset_db": inp["target"].get("db", ""), "location": inp["target"].get("location", ""),
                     "stage": inp["stage"] or "", "amount": inp["input_amount"] if inp["input_amount"] is not None else inp["amount"],
                     "unit": inp["input_unit"] or inp["target"]["unit"], "per_fu": per_fu, "per_fu_unit": inp["target"]["unit"],
                     "avoided": bool(inp["avoided"]), "data_type": inp.get("data_type") or "",
                     "data_year": inp.get("data_year"), "supplier": inp.get("supplier") or "",
                     "reference": inp.get("source_ref") or inp.get("comment") or "", "verified": bool(inp.get("verified")),
                     "pedigree": list(inp["pedigree"]), "pef": inp.get("pef"), "formula": inp.get("formula") or "",
                     "occurrences": len(L["occ"])})
    return rows
