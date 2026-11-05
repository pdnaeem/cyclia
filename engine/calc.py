"""Cyclia calculation core.

Matrix LCA (Heijungs & Suh 2002):  A s = f,  g = B s + d,  h = Q s + C d (+ fixed EPD values)
    A  technosphere matrix (production on the diagonal, inputs negative; ecoSpold2 convention)
    B  biosphere matrix, d direct foreground elementary flows
    C  characterisation matrix (methods x flows); Q = C B, corrected for regional factors
Foreground (Cyclia models)
    * each line = amount per functional unit, in the dataset's unit (entered in any convertible unit,
      or as a formula of parameters)
    * avoided products enter with a negative sign (system expansion)
    * the allocation share of a model (manual %, or from co-product mass/economic/energy values) scales
      all of its burdens
    * EN 15804 stage system: lines in module D are reported separately and not added to the A-C total
"""
import math
import re
import threading
import time

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu

import formula as fm
import units

PEDIGREE_VAR = [  # variances of ln, ecoinvent v3 data quality guideline (Weidema et al. 2013)
    [0.0, 0.0006, 0.002, 0.008, 0.04],
    [0.0, 0.0001, 0.0006, 0.002, 0.008],
    [0.0, 0.0002, 0.002, 0.008, 0.04],
    [0.0, 0.000025, 0.0001, 0.0006, 0.002],
    [0.0, 0.0006, 0.008, 0.04, 0.12],
]
PEDIGREE_LABELS = ["Reliability", "Completeness", "Temporal correlation", "Geographical correlation",
                   "Technological correlation"]
UNASSIGNED = "Unassigned stage"


class LCAError(Exception):
    pass


class Cancelled(Exception):
    pass


# ============================================================================ matrices
class MatrixCache:
    def __init__(self):
        self.lock = threading.Lock()
        self.key = None

    def get(self, store):
        key = (store.library_path, store.lib_version())
        with self.lock:
            if self.key == key:
                return self
            acts = store.q("SELECT id, production, location FROM activities ORDER BY id")
            if not acts:
                raise LCAError("No background database is connected yet. Connect one in step 1.")
            self.act_ids = np.array([a["id"] for a in acts])
            self.act_index = {int(a): i for i, a in enumerate(self.act_ids)}
            self.act_loc = [str(a["location"] or "").upper() for a in acts]
            self.n = len(acts)
            self.diag = np.array([a["production"] if a["production"] else 1.0 for a in acts], dtype=float)
            tech = store.q("SELECT output_id, input_id, amount, utype, p1, p2, p3 FROM tech")
            keep = [t for t in tech if t["input_id"] in self.act_index and t["output_id"] in self.act_index]
            self.t_rows = np.array([self.act_index[t["input_id"]] for t in keep], dtype=np.int64)
            self.t_cols = np.array([self.act_index[t["output_id"]] for t in keep], dtype=np.int64)
            self.t_amt = np.array([t["amount"] for t in keep], dtype=float)
            self.t_unc = _unc_arrays(keep)
            flows = store.q("SELECT id, c_name, c_comp FROM flows ORDER BY id")
            self.flow_ids = np.array([f["id"] for f in flows])
            self.flow_index = {int(f["id"]): i for i, f in enumerate(flows)}
            self.flow_cname = [(f["c_name"] or "", f["c_comp"] or "") for f in flows]
            bio = store.q("SELECT activity_id, flow_id, amount, utype, p1, p2, p3 FROM bio")
            keepb = [b for b in bio if b["flow_id"] in self.flow_index and b["activity_id"] in self.act_index]
            self.b_rows = np.array([self.flow_index[b["flow_id"]] for b in keepb], dtype=np.int64)
            self.b_cols = np.array([self.act_index[b["activity_id"]] for b in keepb], dtype=np.int64)
            self.b_amt = np.array([b["amount"] for b in keepb], dtype=float)
            self.b_unc = _unc_arrays(keepb)
            self.A = self.build_A(self.t_amt)
            self.B = self.build_B(self.b_amt)
            self.lu = factorise(self.A)
            self.unit_cache = {}
            self.key = key
            return self

    def build_A(self, tech_amounts):
        n = self.n
        A = sp.csc_matrix((np.concatenate([self.diag, -tech_amounts]),
                           (np.concatenate([np.arange(n), self.t_rows]), np.concatenate([np.arange(n), self.t_cols]))),
                          shape=(n, n))
        A.sum_duplicates()
        return A

    def build_B(self, bio_amounts):
        B = sp.csr_matrix((bio_amounts, (self.b_rows, self.b_cols)), shape=(len(self.flow_ids), self.n))
        B.sum_duplicates()
        return B

    def solve(self, demand, lu=None):
        s = (lu or self.lu).solve(demand)
        if not np.all(np.isfinite(s)):
            raise LCAError("The calculation produced non-finite numbers. The database may be badly linked.")
        # 1.3.10: no cut-off of small scaling factors. Up to 1.3.9 values below 1e-13 x the largest were set to zero
        # as round-off; that also removed real ones, such as the tiny shares of infrastructure (buildings, mines,
        # platforms, roads) in a supply chain whose largest scaling factor is large, and with them most land
        # transformation and occupation. Found by the inventory check against ecoinvent's cumulative LCI.
        return s


def factorise(A):
    try:
        return splu(A)
    except RuntimeError as e:
        raise LCAError("The technosphere matrix cannot be solved (a product without a producer, or a loop that "
                       f"produces no net output). Run 'Check database' in step 1. Detail: {e}")


def _unc_arrays(rows):
    t = np.array([r["utype"] or 0 for r in rows], dtype=np.int8)
    f = lambda k: np.array([r[k] if r[k] is not None else np.nan for r in rows], dtype=float)
    return {"type": t, "p1": f("p1"), "p2": f("p2"), "p3": f("p3")}


def sample_values(rng, base, unc):
    v = base.copy()
    t = unc["type"]
    m = t == 1
    if m.any():
        v[m] = base[m] * np.exp(rng.standard_normal(m.sum()) * np.nan_to_num(unc["p1"][m]))
    m = t == 2
    if m.any():
        v[m] = base[m] + rng.standard_normal(m.sum()) * np.nan_to_num(unc["p1"][m])
    for typ in (3, 4):
        m = t == typ
        if not m.any():
            continue
        idx = np.where(m)[0]
        lo, a, b = unc["p1"][m], unc["p2"][m], unc["p3"][m]
        if typ == 3:
            ok = np.isfinite(lo) & np.isfinite(a) & np.isfinite(b) & (b > lo) & (lo <= a) & (a <= b)
            if ok.any():
                v[idx[ok]] = rng.triangular(lo[ok], a[ok], b[ok])
        else:
            ok = np.isfinite(lo) & np.isfinite(a) & (a > lo)
            if ok.any():
                v[idx[ok]] = rng.uniform(lo[ok], a[ok])
    return v


_cache = MatrixCache()
_variants = {}
_variants_lock = threading.Lock()


def invalidate():
    _cache.key = None
    with _variants_lock:
        _variants.clear()


def get_mc(store, bg=None):
    """Matrices of the library, or of a background scenario (prospective or consequential) applied to it.
    bg: None or {"id": scenario id, "year": target year}."""
    base = _cache.get(store)
    if not bg or not bg.get("id"):
        return base
    import json
    import science
    sc = store.bg_scenario(int(bg["id"]))
    if not sc:
        raise LCAError("The selected background scenario no longer exists.")
    year = float(bg.get("year") or 0) or None
    key = (base.key, json.dumps(sc["rules"], sort_keys=True), sc["base_year"], year)
    with _variants_lock:
        if key in _variants:
            return _variants[key]
    try:
        v = science.apply_rules(store, base, sc["rules"], sc["base_year"], year)
    except ValueError as e:
        raise LCAError(f"Background scenario '{sc['name']}': {e}")
    v.bg_name = sc["name"] + (f" ({year:g})" if year else "")
    v.bg_kind = sc["kind"]
    v.bg_report = getattr(v, "bg_report", [])
    with _variants_lock:
        if len(_variants) > 4:
            _variants.clear()
        _variants[key] = v
    return v


class Methods:
    """Characterisation data for a list of selected impact categories."""

    def __init__(self, store, mc, method_ids, regional=True):
        self.ids = [int(m) for m in method_ids]
        self.rows = []
        for mid in self.ids:
            m = store.one("SELECT * FROM methods WHERE id=?", (mid,))
            if not m:
                raise LCAError("A selected impact category was removed. Re-select categories in step 4.")
            self.rows.append(m)
        self.keys = [(m["family"], m["category"], m["indicator"]) for m in self.rows]
        k = len(self.ids)
        self.C = np.zeros((k, len(mc.flow_ids)))
        for i, mid in enumerate(self.ids):
            for r in store.q("SELECT flow_id, value FROM cfs WHERE method_id=?", (mid,)):
                j = mc.flow_index.get(r["flow_id"])
                if j is not None:
                    self.C[i, j] += r["value"]
        self.Q = (sp.csr_matrix(self.C) @ mc.B).toarray() if mc.n else np.zeros((k, 0))
        self.regional = 0
        reg = store.q(f"SELECT method_id, flow_id, location, value FROM cfs_regional WHERE method_id IN "
                      f"({','.join('?' * k)})", self.ids) if k and regional else []
        if reg:
            Bc = mc.B.tocsr()
            loc_of = mc.act_loc
            for r in reg:
                i = self.ids.index(r["method_id"])
                f = mc.flow_index.get(r["flow_id"])
                if f is None:
                    continue
                start, end = Bc.indptr[f], Bc.indptr[f + 1]
                for j, b in zip(Bc.indices[start:end], Bc.data[start:end]):
                    if loc_of[j] == str(r["location"]).upper():
                        self.Q[i, j] += (r["value"] - self.C[i, f]) * b
                        self.regional += 1
        for i, m in enumerate(self.rows):
            m["n_matched"] = int(np.count_nonzero(self.C[i]))
        # site-specific factors replace the generic factor for the model's own (foreground) emissions only
        self.Cd = self.C.copy()
        self.site = []
        try:
            site = store.site_cfs()
        except Exception:
            site = []
        if site:
            uu = {r["uuid"]: r["id"] for r in store.q("SELECT id, uuid FROM flows WHERE uuid IN (%s)" %
                                                         ",".join("?" * len(site)), [x["flow_uuid"] for x in site])}
            for x in site:
                key = (x["family"], x["category"], x["indicator"] or x["category"])
                if key in self.keys and x["flow_uuid"] in uu:
                    j = mc.flow_index.get(uu[x["flow_uuid"]])
                    if j is not None:
                        i = self.keys.index(key)
                        self.site.append({"category": x["category"], "flow": x["flow_name"], "generic": float(self.C[i, j]),
                                          "site": float(x["value"]), "note": x["note"]})
                        self.Cd[i, j] = x["value"]

    def fixed_vector(self, fixed):
        """EPD / fixed impact values per unit, matched to the selected categories by method key."""
        vals = {(x.get("family"), x.get("category"), x.get("indicator")): float(x.get("value") or 0)
                for x in (fixed or {}).get("impacts", [])}
        return np.array([vals.get(k, 0.0) for k in self.keys])


def impacts(mc, M, acts, flows, fixed=None, lu=None, B=None, Q=None):
    """Characterised results for a background demand dict, direct flow dict and fixed-value list."""
    s = mc.solve(demand_vector(mc, acts), lu) if acts else np.zeros(mc.n)
    d = flow_vector(mc, flows)
    Bm = mc.B if B is None else B
    g = Bm @ s + d
    h = (M.Q if Q is None else Q) @ s + M.Cd @ d
    for fx, amt in (fixed or []):
        h = h + M.fixed_vector(fx) * amt
    return h, s, g


def demand_vector(mc, acts):
    """Demand for the background. A line amount is always entered as a positive quantity of the dataset's product;
    for a treatment dataset (negative reference amount, ecoSpold2 convention: it 'produces' -1 kg of waste) that
    quantity is the waste sent to treatment, so the demand takes the sign of the reference amount."""
    f = np.zeros(mc.n)
    for aid, amt in acts.items():
        i = mc.act_index.get(aid)
        if i is None:
            raise LCAError("A model input points to a dataset that is no longer in the library. Check step 3.")
        f[i] += amt if mc.diag[i] >= 0 else -amt
    return f


def flow_vector(mc, flows):
    g = np.zeros(len(mc.flow_ids))
    for fid, amt in flows.items():
        i = mc.flow_index.get(fid)
        if i is not None:
            g[i] += amt
    return g


# ============================================================================ foreground model
def is_module_d(scope, stage):
    return str((scope or {}).get("stage_system", "")).startswith("EN 15804") and str(stage or "").strip().upper().startswith("D")


def allocation_share(scope):
    """Share of burdens for the main product: from co-product properties if given, else the manual %."""
    scope = scope or {}
    basis = scope.get("alloc_basis") or ""
    cps = scope.get("coproducts") or []
    if basis in ("mass", "price", "energy", "physical") and cps:
        main = _num(scope.get(f"main_{basis}"))
        others = sum(_num(c.get(basis)) for c in cps)
        if main > 0 and main + others > 0:
            return main / (main + others)
    v = scope.get("alloc_share")
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 1.0
    return v / 100.0 if 0 < v <= 100 else 1.0


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


class Context:
    """Parameter values per model for one calculation (scenario overrides and Monte Carlo samples)."""

    def __init__(self, store, overrides=None, sample=None, base=None, psample=None, msample=None):
        self.store = store
        self.overrides = dict(overrides or {})
        self.sample = dict(sample or {})
        # hierarchical samples: project parameters (psample, by name) and per-model parameters (msample[model id])
        self.psample = dict(psample or {})
        self.msample = {k: dict(v) for k, v in (msample or {}).items()}
        self._params = {}
        self._models = base._models if base is not None else {}
        self.project_params = base.project_params if base is not None else store.parameters(None)

    def model(self, model_id):
        if model_id not in self._models:
            m = self.store.model(model_id)
            if not m:
                raise LCAError(f"Model {model_id} no longer exists.")
            self._models[model_id] = m
        return self._models[model_id]

    def params(self, model_id):
        if model_id not in self._params:
            plist = {p["name"]: p for p in self.project_params}
            for p in self.model(model_id)["parameters"]:
                plist[p["name"]] = p
            ov = {**self.overrides, **{k: v for k, v in self.sample.items() if k in plist}}
            if self.psample or self.msample:
                own = {p["name"] for p in self.model(model_id)["parameters"]}
                ov.update({k: v for k, v in self.psample.items() if k in plist and k not in own})
                ov.update({k: v for k, v in self.msample.get(model_id, {}).items() if k in own})
            try:
                self._params[model_id] = fm.resolve(list(plist.values()), ov)
            except fm.FormulaError as e:
                raise LCAError(f"Parameters of '{self.model(model_id)['name']}': {e}")
        return self._params[model_id]


def line_amount(ctx, model_id, inp):
    """Amount per functional unit in the target's unit (positive)."""
    if inp.get("formula"):
        try:
            v = fm.evaluate(inp["formula"], ctx.params(model_id))
        except fm.FormulaError as e:
            raise LCAError(f"Formula of '{inp['label'] or inp['target']['name']}': {e}")
        if inp["kind"] == "fixed":
            return v
        fac = units.factor(inp["input_unit"], inp["target"]["unit"]) if inp["input_unit"] else 1.0
        if fac is None:
            fac = (inp["amount"] / inp["input_amount"]) if inp["input_amount"] else 1.0
        return v * fac
    return inp["amount"]


def expand(ctx, model_id, factor, acts, flows, fixed, depth=0, keep=None):
    """Flatten a (nested) model into background demand, direct flows and fixed-value lines."""
    if depth > 25:
        raise LCAError("Models are nested more than 25 levels deep.")
    m = ctx.model(model_id)
    f = factor * allocation_share(m["scope"])
    for inp in m["inputs"]:
        if keep is not None and not keep(inp):
            continue
        if inp["missing"]:
            raise LCAError(f"A line of '{m['name']}' points to a dataset that is not in this library"
                           f"{' (database ' + inp['ref_db'] + ')' if inp['ref_db'] else ''}. Import it or remove the line.")
        amt = line_amount(ctx, model_id, inp) * (-1 if inp["avoided"] else 1) * f
        _add(ctx, inp, amt, acts, flows, fixed, depth)


def _add(ctx, inp, amt, acts, flows, fixed, depth):
    if inp["kind"] == "activity":
        acts[inp["ref_id"]] = acts.get(inp["ref_id"], 0.0) + amt
    elif inp["kind"] == "flow":
        flows[inp["ref_id"]] = flows.get(inp["ref_id"], 0.0) + amt
    elif inp["kind"] == "fixed":
        fixed.append((inp["fixed"], amt))
    else:
        sub = ctx.model(inp["ref_id"])
        expand(ctx, inp["ref_id"], amt / (sub["amount"] or 1.0), acts, flows, fixed, depth + 1)


def line_unit_demand(ctx, inp):
    a, fl, fx = {}, {}, []
    _add(ctx, inp, 1.0, a, fl, fx, 1)
    return a, fl, fx


# ============================================================================ uncertainty helpers
def basic_variance(kind, name):
    n = (name or "").lower()
    if kind == "flow":
        return 0.0006 if "carbon dioxide" in n else 0.04
    if "transport" in n:
        return 0.12
    return 0.0006


def pedigree_sigma(pedigree, kind, name):
    var = basic_variance(kind, name)
    for col, score in enumerate(list(pedigree)[:5]):
        var += PEDIGREE_VAR[col][max(1, min(5, int(score))) - 1]
    return math.sqrt(var)


def _stats(col):
    col = np.asarray(col, dtype=float)
    mean = float(col.mean())
    scale = float(np.abs(col).max()) if col.size else 0.0
    if scale == 0 or float(col.std()) <= 1e-12 * scale:
        col = np.full_like(col, float(np.median(col)))
    hist, bins = np.histogram(col, bins=30)
    sd = float(col.std(ddof=1)) if col.size > 1 else 0.0
    n = int(col.size)
    p_lo, p_hi = float(np.percentile(col, 2.5)), float(np.percentile(col, 97.5))
    se = float(100 * sd / math.sqrt(n) / abs(mean)) if (mean and n > 1) else None
    # convergence: standard error of the mean, and stability of the 95 % interval between the first half and all runs
    half = col[: n // 2]
    width = (p_hi - p_lo) or abs(mean) or 1.0
    drift = (max(abs(float(np.percentile(half, 2.5)) - p_lo), abs(float(np.percentile(half, 97.5)) - p_hi)) / width * 100
             if n >= 40 else None)
    # the mean is known to within 1 % of the interval width, and the interval is stable between half and all runs
    se_w = float(sd / math.sqrt(n) / width * 100) if n > 1 else None
    converged = None if se_w is None or drift is None else bool(se_w < 1.0 and drift < 10.0)
    return {"mean": mean, "median": float(np.median(col)), "sd": sd, "n": n,
            "p2_5": p_lo, "p97_5": p_hi,
            "cv_percent": float(100 * sd / abs(mean)) if mean else None,
            "se_mean_percent": se, "se_width_percent": se_w, "interval_drift_percent": drift, "converged": converged,
            "histogram": hist.tolist(), "bins": bins.tolist()}


def sample_param(rng, p, size=None):
    t, p1, p2, p3, v = p["utype"] or 0, p["p1"], p["p2"], p["p3"], float(p["value"] or 0)
    if t == 1:
        return v * np.exp(rng.standard_normal(size) * math.log(p1))
    if t == 2:
        return v + rng.standard_normal(size) * p1
    if t == 3:
        return rng.triangular(p1, p2, p3, size)
    if t == 4:
        return rng.uniform(p1, p2, size)
    return np.full(size, v) if size else v


def _ppf_param(p, u):
    """Inverse CDF of a parameter distribution (for Sobol sampling)."""
    from scipy import stats
    t, p1, p2, p3, v = p["utype"] or 0, p["p1"], p["p2"], p["p3"], float(p["value"] or 0)
    if t == 1:
        return v * np.exp(stats.norm.ppf(u) * math.log(p1))
    if t == 2:
        return v + stats.norm.ppf(u) * p1
    if t == 3:
        c = (p2 - p1) / (p3 - p1)
        return stats.triang.ppf(u, c, loc=p1, scale=p3 - p1)
    if t == 4:
        return p1 + u * (p2 - p1)
    return np.full_like(u, v)


# ============================================================================ dynamic GWP
JOOS = (0.2173, [(0.2240, 394.4), (0.2824, 36.54), (0.2763, 4.304)])  # Joos et al. 2013 CO2 impulse response
GAS = {  # canonical name -> (gas, sign); comp '' = any compartment
    ("carbon dioxide, fossil", "air"): ("CO2", 1), ("carbon dioxide, non-fossil", "air"): ("CO2", 1),
    ("carbon dioxide, biogenic", "air"): ("CO2", 1), ("carbon dioxide, land use change", "air"): ("CO2", 1),
    ("carbon dioxide, from soil or biomass stock", ""): ("CO2", 1),
    ("carbon dioxide, to soil or biomass stock", ""): ("CO2", -1),
    ("carbon dioxide, in air", "natural resource"): ("CO2", -1),
    ("carbon dioxide, biogenic", "natural resource"): ("CO2", -1),
    ("methane, fossil", "air"): ("CH4f", 1), ("methane, non-fossil", "air"): ("CH4b", 1),
    ("methane, biogenic", "air"): ("CH4b", 1), ("methane, from soil or biomass stock", ""): ("CH4f", 1),
    ("methane, land use change", "air"): ("CH4f", 1),
    ("dinitrogen monoxide", "air"): ("N2O", 1), ("nitrous oxide", "air"): ("N2O", 1),
}
GWP100 = {"CH4f": 29.8, "CH4b": 27.0, "N2O": 273.0}
LIFETIME = {"CH4f": 11.8, "CH4b": 11.8, "N2O": 109.0}


def _agwp_co2(h):
    a0, terms = JOOS
    return a0 * h + sum(a * t * (1 - math.exp(-h / t)) for a, t in terms) if h > 0 else 0.0


def dynamic_weight(gas, year, horizon=100.0):
    """CO2-eq weight of a 1 kg pulse emitted 'year' years after the study start, counted to a fixed
    horizon (time-dependent GWP, Levasseur et al. 2010)."""
    left = horizon - year
    if left <= 0:
        return 0.0
    if gas == "CO2":
        return _agwp_co2(left) / _agwp_co2(horizon)
    tau = LIFETIME[gas]
    return GWP100[gas] * (1 - math.exp(-left / tau)) / (1 - math.exp(-horizon / tau))


def gas_index(mc):
    out = []
    for i, (n, c) in enumerate(mc.flow_cname):
        hit = GAS.get((n, c)) or GAS.get((n, ""))
        if hit:
            out.append((i, hit[0], hit[1]))
    return out


# ============================================================================ main calculation
def run(store, model_id, method_ids, top=12, mc_iterations=0, sensitivity_pct=10.0, nw_set=None, seed=42,
        scenario=None, horizon=100.0, bg=None):
    method_ids = [int(m) for m in method_ids or []]
    if not method_ids:
        raise LCAError("Pick at least one impact category in step 4.")
    overrides = _scenario(store, scenario)
    ctx = Context(store, overrides)
    model = ctx.model(model_id)
    if not model["inputs"]:
        raise LCAError("This model has no inputs yet. Add materials, energy, transport or emissions in step 3.")
    mc = get_mc(store, bg)
    M = Methods(store, mc, method_ids)
    sc = model["scope"]
    share = allocation_share(sc)
    keep_ac = lambda inp: not is_module_d(sc, inp["stage"])

    acts, flows, fixed = {}, {}, []
    expand(ctx, model_id, 1.0, acts, flows, fixed, keep=keep_ac)
    total, s, g = impacts(mc, M, acts, flows, fixed)

    gidx = gas_index(mc)
    lines = []
    any_year = any(float(i.get("year") or 0) for i in model["inputs"])
    for inp in model["inputs"]:
        a, fl, fx = line_unit_demand(ctx, inp)
        key = None
        if inp["kind"] == "activity" and not fl and not fx:
            key = (inp["ref_id"], tuple(method_ids), bool(M.site))
        if key and key in mc.unit_cache:
            unit, g_unit = mc.unit_cache[key]
        else:
            unit, _, g_line = impacts(mc, M, a, fl, fx)
            g_unit = {i: g_line[i] for i, _, _ in gidx if g_line[i]}
            if key:
                mc.unit_cache[key] = (unit, g_unit)
        amount = line_amount(ctx, model_id, inp)
        eff = amount * (-1 if inp["avoided"] else 1) * share
        lines.append({
            "input_id": inp["id"], "name": inp["label"] or inp["target"]["name"], "kind": inp["kind"],
            "amount": amount, "effective_amount": eff, "unit": inp["target"]["unit"],
            "input_amount": (amount / (units.factor(inp["input_unit"], inp["target"]["unit"]) or 1.0))
            if inp.get("formula") and inp["kind"] != "fixed" else inp["input_amount"],
            "input_unit": inp["input_unit"], "formula": inp.get("formula"),
            "location": inp["target"].get("location", ""), "db": inp["target"].get("db", ""),
            "stage": inp["stage"] or UNASSIGNED, "module_d": is_module_d(sc, inp["stage"]), "avoided": inp["avoided"],
            "comment": inp["comment"], "pedigree": inp["pedigree"], "year": float(inp.get("year") or 0),
            "data_type": inp.get("data_type") or "", "source_ref": inp.get("source_ref") or "",
            "data_year": inp.get("data_year"), "supplier": inp.get("supplier") or "", "verified": bool(inp.get("verified")),
            "unit_cost": inp.get("unit_cost"), "pef": inp.get("pef"),
            "unit_impact": unit.tolist(), "impact": (unit * eff).tolist(), "_gas": g_unit,
            "sigma": pedigree_sigma(inp["pedigree"], inp["kind"], inp["target"]["name"]),
        })

    per_process = M.Q * s
    d = flow_vector(mc, flows)
    direct = M.Cd @ d
    fixed_total = sum((M.fixed_vector(fx) * amt for fx, amt in fixed), np.zeros(len(method_ids)))
    per_flow = M.C * (g - d) + M.Cd * d
    # results by location of the process where the impact occurs (spatial view)
    locs = np.array(mc.act_loc + [""]) if mc.n else np.array([""])
    fg_loc = str((sc or {}).get("geography") or "Foreground").strip() or "Foreground"
    scale = np.abs(per_process).sum(axis=1) + np.abs(direct) + np.abs(fixed_total) + 1e-300
    total = np.where(np.abs(total) < 1e-10 * scale, 0.0, total)

    names = {}

    def act_name(idx):
        aid = int(mc.act_ids[idx])
        if aid not in names:
            r = store.one("SELECT name, location FROM activities WHERE id=?", (aid,))
            names[aid] = f"{r['name']} [{r['location']}]" if r else str(aid)
        return names[aid]

    fnames = {}

    def flow_label(idx):
        fid = int(mc.flow_ids[idx])
        if fid not in fnames:
            r = store.flow(fid)
            fnames[fid] = (r["name"], "/".join(x for x in (r["compartment"], r["subcompartment"]) if x), r["unit"])
        return fnames[fid]

    stages = sorted({l["stage"] for l in lines}, key=lambda x: (x == UNASSIGNED, x.upper().startswith("D"), x.lower()))
    nw = {}
    if nw_set:
        for r in store.q(f"SELECT * FROM nw WHERE set_name=? AND method_id IN ({','.join('?' * len(method_ids))})",
                         [nw_set] + method_ids):
            nw[r["method_id"]] = r
    pct = float(sensitivity_pct or 10.0)
    results = []
    for k, m in enumerate(M.rows):
        row = per_process[k]
        order = np.argsort(-np.abs(row))[:top]
        procs = [{"name": act_name(i), "impact": float(row[i])} for i in order if abs(row[i]) > 1e-12 * scale[k]]
        if abs(direct[k]) > 1e-12 * scale[k]:
            procs.append({"name": "Direct emissions of the model (foreground)", "impact": float(direct[k])})
        if abs(fixed_total[k]) > 1e-12 * scale[k]:
            procs.append({"name": "EPD / fixed-value lines", "impact": float(fixed_total[k])})
        procs.sort(key=lambda p: -abs(p["impact"]))
        fr = per_flow[k]
        forder = np.argsort(-np.abs(fr))[:top]
        flows_top = []
        for i in forder:
            if abs(fr[i]) > 1e-12 * scale[k]:
                n, ctxt, _ = flow_label(i)
                flows_top.append({"name": f"{n} ({ctxt})", "impact": float(fr[i])})
        ac_lines = [l for l in lines if not l["module_d"]]
        by_input = [{"name": l["name"], "impact": l["impact"][k] if abs(l["impact"][k]) > 1e-12 * scale[k] else 0.0,
                     "stage": l["stage"], "module_d": l["module_d"]} for l in lines]
        by_stage = [{"name": st, "impact": sum(b["impact"] for b in by_input if b["stage"] == st),
                     "module_d": any(b["module_d"] for b in by_input if b["stage"] == st)} for st in stages]
        module_d = sum(l["impact"][k] for l in lines if l["module_d"])
        sens = sorted([{
            "name": l["name"], "low": l["impact"][k] * (-pct / 100.0), "high": l["impact"][k] * (pct / 100.0),
            "ped_low": l["impact"][k] * (math.exp(-1.96 * l["sigma"]) - 1),
            "ped_high": l["impact"][k] * (math.exp(1.96 * l["sigma"]) - 1)} for l in ac_lines],
            key=lambda x: -abs(x["high"]))
        by_loc = {}
        nzp = np.where(np.abs(row) > 0)[0]
        for i in nzp:
            by_loc[mc.act_loc[i] or "unknown"] = by_loc.get(mc.act_loc[i] or "unknown", 0.0) + float(row[i])
        if abs(direct[k]) > 0:
            by_loc[fg_loc] = by_loc.get(fg_loc, 0.0) + float(direct[k])
        if abs(fixed_total[k]) > 0:
            by_loc["EPD values (no location)"] = by_loc.get("EPD values (no location)", 0.0) + float(fixed_total[k])
        by_location = sorted([{"location": l, "impact": v} for l, v in by_loc.items() if abs(v) > 1e-12 * scale[k]],
                             key=lambda x: -abs(x["impact"]))
        res = {"method_id": m["id"], "family": m["family"], "category": m["category"], "indicator": m["indicator"],
               "unit": m["unit"], "total": float(total[k]), "module_d": float(module_d),
               "cfs_matched": m["n_matched"], "processes": procs, "flows": flows_top, "by_input": by_input,
               "by_stage": by_stage, "sensitivity": sens, "by_location": by_location}
        f = nw.get(m["id"])
        if f:
            norm = (total[k] / f["normalisation"]) if f["normalisation"] else None
            res["normalised"] = float(norm) if norm is not None else None
            res["weighted"] = float(norm * f["weighting"]) if (norm is not None and f["weighting"] is not None) else None
        results.append(res)

    # parameter sensitivity (one at a time, +/- pct on each free parameter)
    param_sens = parameter_sensitivity(store, model_id, method_ids, M, mc, overrides, pct, total)
    tox_cov = toxicity_coverage(M, mc, g, flow_label)

    # life cycle inventory and flows that no selected category characterises
    lci, uncharacterised = [], []
    nz = np.where(np.abs(g) > 1e-15 * (np.abs(g).max() or 1))[0]
    raw_names = {r["c_name"] for r in store.q(
        f"SELECT DISTINCT c_name FROM cf_raw WHERE method_id IN ({','.join('?' * len(method_ids))})", method_ids)}
    has_cf = np.any(M.C != 0, axis=0)
    for i in nz[np.argsort(-np.abs(g[nz]))]:
        n, ctxt, u = flow_label(i)
        lci.append({"name": n, "context": ctxt, "unit": u, "amount": float(g[i])})
        if not has_cf[i] and len(uncharacterised) < 40:
            uncharacterised.append({"name": n, "context": ctxt, "unit": u, "amount": float(g[i]),
                                    "mapping_issue": mc.flow_cname[i][0] in raw_names})

    land_cov = land_coverage(M, mc, g, flow_label, results)

    out = {"model": {k: model[k] for k in ("id", "name", "product", "unit", "amount", "scope")},
           "land_coverage": land_cov,
           "results": results, "lines": lines, "stages": stages, "sensitivity_pct": pct, "allocation_share": share,
           "nw_set": nw_set if nw else None, "scenario": scenario, "parameters": ctx.params(model_id),
           "parameter_sensitivity": param_sens, "lci": lci, "uncharacterised": uncharacterised,
           "has_module_d": any(l["module_d"] for l in lines), "regional_factors_used": M.regional,
           "site_factors": M.site, "toxicity_coverage": tox_cov,
           "background": {"name": getattr(mc, "bg_name", None), "kind": getattr(mc, "bg_kind", None),
                          "changes": getattr(mc, "bg_report", [])} if getattr(mc, "bg_name", None) else None}
    if nw:
        w = [r.get("weighted") for r in results if "weighted" in r]
        out["single_score"] = float(sum(w)) if w and all(x is not None for x in w) else None
        out["nw_missing"] = [r["category"] for r in results if "normalised" not in r]
    if any_year or (sc or {}).get("dynamic"):
        out["dynamic_gwp"] = dynamic_gwp(lines, gidx, horizon)
    if mc_iterations:
        out["uncertainty"] = foreground_mc(store, model_id, lines, method_ids, overrides, mc_iterations, seed, mc=mc, M=M)
    out["_bg"] = bg
    import analysis
    out["lcc"] = analysis.lcc(ctx, model_id)
    out["water"] = analysis.water_inventory(lci)
    import hier
    T = hier.build(ctx, model_id, keep=keep_ac)
    leaf_acts = sorted({lf["inp"]["ref_id"] for lf in T["leaves"] if lf["inp"]["kind"] == "activity" and lf["inp"]["ref_id"]})
    ddq = {}
    if leaf_acts:
        try:
            for r in store.q(f"SELECT * FROM activity_dq WHERE activity_id IN ({','.join('?' * len(leaf_acts))})", leaf_acts):
                if all(r[k] is not None for k in ("ter", "ger", "tir", "p")):
                    ddq[r["activity_id"]] = [r["ter"], r["ger"], r["tir"], r["p"]]
        except Exception:
            ddq = {}
    out["_tree"] = {"tree": T, "amounts": hier.path_amounts(ctx, T), "units": hier.leaf_units(ctx, mc, M, T),
                    "dataset_dq": ddq}
    out["foreground"] = hier.foreground_inventory(ctx, T)
    out["nested"] = len(T["models"]) > 1
    out["data_quality"] = data_quality(out)
    out["checks"] = checks(store, model_id, method_ids, out)
    out["findings"] = findings(out)
    out.pop("_bg", None)
    out.pop("_tree", None)
    for l in lines:
        l.pop("_gas", None)
    return out


# ============================================================================ data quality and key findings
PED_NAMES = ["reliability", "completeness", "temporal", "geographical", "technological"]
DATA_TYPE_LABEL = {"primary": "primary (measured or supplier-specific)", "secondary": "secondary (database or literature)",
                   "estimate": "estimate", "": "not stated"}


def dqr_rating(v):
    """Verbal class for a data quality rating on the 1 (best) to 5 scale, using the PEF class limits."""
    if v is None:
        return ""
    return "excellent" if v <= 1.5 else "very good" if v <= 2.0 else "good" if v <= 3.0 else "fair" if v <= 4.0 else "poor"


def data_quality(out):
    """Contribution-weighted data quality per impact category, over every line at every level of nesting.

    Each path from the top-level model down to a dataset, flow or EPD line is weighted by its share of the absolute
    impact of the category. Credits (avoided products) and module D are left out of the weights and reported apart.
    A path takes, per indicator, the worst score along its chain (a number is only as good as the weakest datum it
    depends on).

    Two ratings are given:
    - a pedigree-based indicator (P = reliability, TiR = temporal, GeR = geographical, TeR = technological
      correlation) in the form (TeR + GeR + TiR + P) / 4. It is not a PEF DQR, because pedigree reliability is not
      the PEF precision criterion;
    - the PEF DQR, computed from lines for which the four PEF scores (TeR, GeR, TiR, P) were entered, and from the
      DQR of the datasets they use when the dataset carries one (EF / ILCD datasets), with the share of the impact
      covered (and the part of it that comes from dataset DQRs)."""
    T = out.get("_tree")
    if T is None:
        return {"by_category": [], "lines": [], "priority": [], "default_lines": 0, "credits": [], "note": ""}
    tree, amounts, units_ = T["tree"], T["amounts"], T["units"]
    lines = tree["lines"]
    contrib = amounts[:, None] * units_ if len(tree["leaves"]) else np.zeros((0, len(out["results"])))
    burden = np.array([not lf["credit"] for lf in tree["leaves"]], dtype=bool)
    ped = np.array([[max(lines[li]["inp"]["pedigree"][c] for li in lf["chain"]) for c in range(5)]
                    for lf in tree["leaves"]], dtype=float).reshape(len(tree["leaves"]), 5)

    ddq = T.get("dataset_dq") or {}

    def pef_of(lf):
        vals = [lines[li]["inp"].get("pef") for li in lf["chain"]]
        own, src = vals[-1], "line"
        if not own and lf["inp"]["kind"] == "activity" and lf["inp"]["ref_id"] in ddq:
            own, src = ddq[lf["inp"]["ref_id"]], "dataset"
        if not own:
            return None, None
        rest = [v for v in vals[:-1] if v]
        return [max([own[c]] + [v[c] for v in rest]) for c in range(4)], src
    pq = [pef_of(lf) for lf in tree["leaves"]]
    pefs = [x[0] for x in pq]
    psrc = [x[1] for x in pq]

    def dtype(lf):
        for li in reversed(lf["chain"]):
            t = lines[li]["inp"].get("data_type") or ""
            if t:
                return t
        return ""
    types = [dtype(lf) for lf in tree["leaves"]]
    cats, worst, credits = [], {}, []
    for k, r in enumerate(out["results"]):
        w = np.abs(contrib[:, k]) * burden
        tot = float(w.sum())
        if tot <= 0:
            continue
        sh = w / tot
        wped = (sh[:, None] * ped).sum(axis=0)
        dqi = float((wped[0] + wped[2] + wped[3] + wped[4]) / 4)
        tshare = {t: float(sum(sh[i] for i in range(len(types)) if types[i] == t)) for t in ("primary", "secondary", "estimate", "")}
        cov = float(sum(sh[i] for i in range(len(pefs)) if pefs[i]))
        cov_ds = float(sum(sh[i] for i in range(len(pefs)) if pefs[i] and psrc[i] == "dataset"))
        pef_dqr = None
        if cov > 0:
            idx = [i for i in range(len(pefs)) if pefs[i]]
            ws = np.array([sh[i] for i in idx]) / cov
            sc_ = (ws[:, None] * np.array([pefs[i] for i in idx], dtype=float)).sum(axis=0)
            pef_dqr = float(sc_.mean())
        cw = np.abs(contrib[:, k]) * ~burden
        cats.append({"category": r["category"], "indicator": r["indicator"], "family": r["family"],
                     "dqr": dqi, "rating": dqr_rating(dqi), "pedigree": [float(x) for x in wped],
                     "pef_dqr": pef_dqr, "pef_rating": dqr_rating(pef_dqr) if pef_dqr is not None else "",
                     "pef_coverage": cov, "pef_from_datasets": cov_ds,
                     "primary_share": tshare["primary"], "secondary_share": tshare["secondary"],
                     "estimate_share": tshare["estimate"], "unstated_share": tshare[""],
                     "credit_share": float(cw.sum() / (tot + cw.sum())) if cw.sum() else 0.0})
        for i, lf in enumerate(tree["leaves"]):
            for li in lf["chain"]:
                worst[li] = max(worst.get(li, 0.0), float(sh[i]))
        if cw.sum():
            credits.append({"category": r["category"], "share": float(cw.sum() / (tot + cw.sum()))})
    rows = []
    for li, L in enumerate(lines):
        inp = L["inp"]
        m = float(np.mean(inp["pedigree"]))
        rows.append({"input_id": inp["id"], "name": (inp["label"] or inp["target"]["name"]) +
                     (f" (in {L['owner_name']})" if L["depth"] else ""), "stage": inp["stage"] or UNASSIGNED,
                     "depth": L["depth"], "model_id": L["owner"], "data_type": inp.get("data_type") or "",
                     "pedigree": inp["pedigree"], "pef": inp.get("pef"), "mean_pedigree": m,
                     "default": list(inp["pedigree"]) == [3, 3, 3, 3, 3], "credit": bool(inp["avoided"]),
                     "max_share": worst.get(li, 0.0)})
    rows.sort(key=lambda x: -x["max_share"])
    priority = [x for x in rows if x["max_share"] >= 0.05 and not x["credit"] and
                (x["default"] or x["mean_pedigree"] >= 3 or x["data_type"] in ("", "estimate"))][:6]
    return {"by_category": cats, "lines": rows, "priority": priority, "credits": credits,
            "default_lines": sum(1 for x in rows if x["default"]), "nested": len(tree["models"]) > 1,
            "note": "Weighted by each line's share of the impact, over every level of nested models; credits and module "
                    "D are left out of the weights. The pedigree-based indicator uses the form (TeR + GeR + TiR + P) / 4 "
                    "with pedigree reliability in place of precision, so it is not a PEF DQR. A PEF DQR is shown only "
                    "where the four PEF scores were entered for the lines (Details in step 3), with the share of the "
                    "impact they cover."}


def _pct(x):
    return f"{100 * x:.0f} %" if abs(x) >= 0.01 else f"{100 * x:.1f} %"


def findings(out, max_categories=8):
    """Plain-language key findings for interpretation (ISO 14044 4.5): what drives each result, which hotspots
    differ between categories (risk of burden shifting), how robust the result is, where better data or a design
    change pays off most, and what still has to be fixed. Every number comes from the calculation."""
    res = out["results"]
    fu = f"{out['model']['amount']:g} {out['model']['unit']} of {out['model']['product']}"
    lines = [l for l in out["lines"] if not l["module_d"]]
    found, tops = [], []
    order = list(range(len(res)))
    if out.get("single_score"):
        order.sort(key=lambda k: -abs(res[k].get("weighted") or 0))
        ws = [(res[k]["category"], (res[k].get("weighted") or 0) / out["single_score"]) for k in order[:3]
              if out["single_score"]]
        found.append({"kind": "priority", "title": "Categories that matter most",
                      "text": f"After normalisation and weighting ({out.get('nw_set')}), the largest shares of the single "
                              f"score come from " + ", ".join(f"{c} ({_pct(v)})" for c, v in ws) + "."})
    for k in order[:max_categories]:
        r = res[k]
        pos = sum(abs(l["impact"][k]) for l in lines) or 0.0
        if not pos:
            continue
        ranked = sorted(lines, key=lambda l: -abs(l["impact"][k]))
        top = ranked[0]
        tops.append((r["category"], top["name"]))
        parts = [f"{ranked[i]['name']} ({_pct(abs(ranked[i]['impact'][k]) / pos)})" for i in range(min(3, len(ranked)))
                 if abs(ranked[i]["impact"][k]) / pos >= 0.01]
        st = sorted(r["by_stage"], key=lambda b: -abs(b["impact"]))
        stage = (f" Largest stage: {st[0]['name']} ({_pct(abs(st[0]['impact']) / pos)})."
                 if len(st) > 1 and st[0]["name"] != UNASSIGNED else "")
        txt = (f"{r['total']:.4g} {r['unit']} per {fu}. Largest contributors: " + ", ".join(parts) + "." + stage)
        credit = sum(l["impact"][k] for l in lines if l["avoided"])
        if credit < 0 and abs(r["total"]) > 0:
            txt += f" Credits from avoided products lower the result by {_pct(abs(credit) / (abs(r['total']) + abs(credit)))}."
        if r.get("module_d"):
            txt += f" Module D, reported separately: {r['module_d']:.4g} {r['unit']}."
        unc = (out.get("uncertainty") or {}).get("methods")
        if unc and k < len(unc) and unc[k].get("cv_percent") is not None:
            u = unc[k]
            txt += (f" With uncertainty, 95 % of results lie between {u['p2_5']:.4g} and {u['p97_5']:.4g} "
                    f"(coefficient of variation {u['cv_percent']:.0f} %).")
        found.append({"kind": "result", "title": f"{r['category']} ({r['family']})", "text": txt})
    if len({t for _, t in tops}) > 1:
        groups = {}
        for c, t in tops:
            groups.setdefault(t, []).append(c)
        found.append({"kind": "hotspots", "title": "Different hotspots in different categories",
                      "text": "The main contributor is not the same everywhere: " +
                              "; ".join(f"{t} in {', '.join(cs)}" for t, cs in groups.items()) +
                              ". Different hotspots alone do not show burden shifting. Whether a change moves burdens "
                              "from one category to another is checked with the change itself (below, and in Compare)."})
    if res and lines:
        k = order[0]
        pct = out.get("sensitivity_pct", 10)
        burdens = [l for l in lines if not l["avoided"] and l["impact"][k] > 0]
        gross = sum(l["impact"][k] for l in burdens)
        if burdens and gross > 0:
            top = max(burdens, key=lambda l: l["impact"][k])
            d = -top["impact"][k] * pct / 100
            rel = (f"{_pct(abs(d) / abs(res[k]['total']))} of the result" if abs(res[k]["total"]) > 1e-30 else "")
            txt = (f"In {res[k]['category']}, {top['name']} is the largest burden ({_pct(top['impact'][k] / gross)} of the "
                   f"burdens). Using {pct:g} % less of it lowers the result by {abs(d):.3g} {res[k]['unit']}"
                   + (f" ({rel})" if rel else "") + ".")
            up = [(res[j]["category"], -top["impact"][j] * pct / 100, res[j]["unit"]) for j in range(len(res))
                  if j != k and -top["impact"][j] * pct / 100 > 1e-12 * (abs(res[j]["total"]) or 1)]
            if up:
                txt += (" The same change would raise " + ", ".join(f"{c} by {v:.3g} {u}" for c, v, u in up) +
                        " (burden shifting), because this line gives a credit there.")
            else:
                txt += " It would not raise any other selected category."
            txt += (" This is a screening estimate for a smaller amount of the same input; a substitute material or "
                    "supplier has impacts of its own, so model it as a scenario or a second model and compare.")
            found.append({"kind": "improve", "title": "Where a change pays off most", "text": txt})
        creds = [l for l in lines if l["avoided"] and l["impact"][k] < 0]
        if creds:
            c = min(creds, key=lambda l: l["impact"][k])
            found.append({"kind": "credit", "title": "Credits",
                          "text": f"In {res[k]['category']}, the credit from {c['name']} lowers the result by "
                                  f"{abs(c['impact'][k]):.3g} {res[k]['unit']}. If less is recovered (for example a lower "
                                  f"recycling rate), the result rises: {pct:g} % less credit adds "
                                  f"{abs(c['impact'][k]) * pct / 100:.3g} {res[k]['unit']}. Report results with and "
                                  "without credits."})
    dq = out.get("data_quality") or {}
    if dq.get("priority"):
        found.append({"kind": "data", "title": "Data to improve first",
                      "text": "These lines matter most and have estimated, default or weak data quality: " +
                              ", ".join(f"{x['name']} (up to {_pct(x['max_share'])} of a category)" for x in dq["priority"][:4]) +
                              ". Better data for them strengthen the study more than anything else."})
    cats = dq.get("by_category") or []
    if cats:
        main = res[order[0]] if res else None
        c0 = next((c for c in cats if main and c["category"] == main["category"] and c["family"] == main["family"]), cats[0])
        prim = max(c["primary_share"] for c in cats)
        txt = (f"Contribution-weighted pedigree indicator for {c0['category']}: {c0['dqr']:.1f} on a 1 (best) to 5 scale "
               f"({c0['rating']}; not a PEF DQR).")
        if c0.get("pef_dqr") is not None:
            txt += (f" PEF DQR from the lines with PEF scores: {c0['pef_dqr']:.1f} ({c0['pef_rating']}), covering "
                    f"{_pct(c0['pef_coverage'])} of the impact.")
        if prim == 0:
            txt += " No line is marked as primary data; mark measured or supplier-specific lines in step 3."
        else:
            txt += f" Primary data cover {_pct(c0['primary_share'])} of that impact."
        u = out.get("uncertainty")
        if u:
            nc = [res[k]["category"] for k, m in enumerate(u["methods"]) if m.get("converged") is False]
            if nc:
                txt += (f" The Monte Carlo run ({u['iterations']} iterations) has not converged for {', '.join(nc[:3])}: "
                        "run more iterations before reporting the intervals.")
            elif all(m.get("converged") for m in u["methods"]):
                txt += (f" The Monte Carlo run ({u['iterations']} iterations) has converged (the mean is known to within 1 % of "
                        "the 95 % interval and the interval is stable).")
        found.append({"kind": "quality", "title": "Data quality", "text": txt})
    lc = out.get("lcc")
    if lc and lc["lines"]:
        top_c = next((l for l in lc["lines"] if not l["module_d"]), None)
        if top_c:
            txt = (f"Life cycle cost: {lc['total']:,.2f} {lc['currency']} per functional unit"
                   + (f" ({lc['total_discounted']:,.2f} discounted at {lc['rate_percent']:g} %)" if lc["rate_percent"] else "")
                   + f". Largest cost: {top_c['name']} ({top_c['cost']:,.2f} {lc['currency']}).")
            if res:
                env_top = max((l for l in out["lines"] if not l["module_d"]), key=lambda l: abs(l["impact"][order[0]]),
                              default=None)
                if env_top and env_top["input_id"] != top_c["input_id"]:
                    txt += (f" The largest environmental contributor in {res[order[0]]['category']} is a different line "
                            f"({env_top['name']}): cost and impact hotspots differ.")
                elif env_top:
                    txt += " It is also the largest environmental contributor, so reducing it helps on both."
            if lc["n_uncosted"]:
                txt += f" {lc['n_uncosted']} line(s) have no price yet."
            found.append({"kind": "cost", "title": "Costs", "text": txt})
    errors = [c for c in out.get("checks", []) if c.get("level") == "error"]
    if errors:
        found.append({"kind": "error", "title": "Fix before concluding",
                      "text": f"{len(errors)} check(s) report errors. Results should not be used until they are solved."})
    return found


TOX_WORDS = ("tox",)
# Substances that toxicity methods conventionally leave to other impact categories (climate, acidification,
# particulate matter, eutrophication, resources); they are not reported as missing toxicity factors.
NOT_TOX = ("carbon dioxide", "methane", "dinitrogen monoxide", "nitrous oxide", "water", "oxygen", "nitrogen, atmospheric",
           "sulfur dioxide", "nitrogen oxides", "ammonia", "particulate", "phosphate", "phosphorus", "nitrate", "nitrogen",
           "carbon monoxide", "heat, waste", "sulfur hexafluoride", "hfc", "ethane, ", "methane, ")


def toxicity_coverage(M, mc, g, flow_label, limit=20):
    """For toxicity categories: which emitted substances (air, water, soil) have no factor. Toxicity results are only
    as complete as the factor coverage, so this is reported next to the result."""
    out = []
    emis = [i for i in np.where(np.abs(g) > 0)[0] if mc.flow_cname[i][1] in ("air", "water", "soil")
            and not any(w in mc.flow_cname[i][0] for w in NOT_TOX)]
    if not emis:
        return out
    for k, m in enumerate(M.rows):
        if not any(w in (m["category"] + " " + m["indicator"]).lower() for w in TOX_WORDS):
            continue
        mass = sum(abs(g[i]) for i in emis)
        missing = [i for i in emis if M.C[k, i] == 0 and M.Cd[k, i] == 0]
        covered = mass - sum(abs(g[i]) for i in missing)
        top = sorted(missing, key=lambda i: -abs(g[i]))[:limit]
        rows = []
        for i in top:
            n, ctx, u = flow_label(i)
            rows.append({"name": n, "context": ctx, "unit": u, "amount": float(g[i])})
        out.append({"category": m["category"], "family": m["family"], "n_emitted": len(emis), "n_missing": len(missing),
                    "mass_share_covered": float(covered / mass) if mass else None, "missing": rows})
    return out


def _scenario(store, scenario):
    if not scenario:
        return {}
    r = store.one("SELECT overrides FROM main.scenarios WHERE id=?", (int(scenario),))
    if not r:
        raise LCAError("The selected scenario no longer exists.")
    import json
    return json.loads(r["overrides"] or "{}")


def dynamic_gwp(lines, gidx, horizon=100.0):
    gases = {i: (gas, sign) for i, gas, sign in gidx}
    tot_dyn = tot_static = 0.0
    by_line = []
    for l in lines:
        if l["module_d"]:
            continue
        dyn = stat = 0.0
        for i, amt in l["_gas"].items():
            gas, sign = gases[i]
            mass = amt * l["effective_amount"] * sign
            dyn += mass * dynamic_weight(gas, l["year"], horizon)
            stat += mass * (1.0 if gas == "CO2" else GWP100[gas])
        tot_dyn += dyn
        tot_static += stat
        by_line.append({"name": l["name"], "year": l["year"], "dynamic": dyn, "static": stat})
    return {"horizon": horizon, "dynamic": tot_dyn, "static": tot_static, "by_line": by_line,
            "note": "Time-dependent GWP (Levasseur et al. 2010) with a fixed horizon from the study start, CO2 impulse "
                    "response of Joos et al. (2013), AR6 GWP100 and lifetimes for CH4 (11.8 y) and N2O (109 y). The "
                    "upstream emissions of a line are assumed to occur in that line's year. Covers CO2, CH4 and N2O."}


def parameter_sensitivity(store, model_id, method_ids, M, mc, overrides, pct, base_total):
    ctx0 = Context(store, overrides)
    free = [p for p in ctx0.project_params + ctx0.model(model_id)["parameters"] if not p.get("formula")]
    if not free:
        return []
    out = []
    for p in free:
        row = {"name": p["name"], "value": ctx0.params(model_id).get(p["name"])}
        for sign, key in ((-1, "low"), (1, "high")):
            v = row["value"] * (1 + sign * pct / 100.0) if row["value"] else sign * pct / 100.0
            ctx = Context(store, {**overrides, p["name"]: v}, base=ctx0)
            acts, flows, fixed = {}, {}, []
            sc = ctx.model(model_id)["scope"]
            try:
                expand(ctx, model_id, 1.0, acts, flows, fixed, keep=lambda i: not is_module_d(sc, i["stage"]))
            except LCAError:
                row[key] = None
                continue
            h, _, _ = impacts(mc, M, acts, flows, fixed)
            row[key] = (h - base_total).tolist()
        out.append(row)
    return out


def foreground_mc(store, model_id, lines, method_ids, overrides, iterations=1000, seed=42, mc=None, M=None, bg=None):
    """Foreground Monte Carlo over every level of the model: the data-quality factor of every line of every nested
    model, and every parameter distribution of the project and of each model (with their correlations)."""
    import hier
    iterations = int(max(100, min(int(iterations), 50000)))
    rng = np.random.default_rng(seed)
    mc = mc or get_mc(store, bg)
    M = M or Methods(store, mc, method_ids)
    ctx0 = Context(store, overrides)
    model = ctx0.model(model_id)
    T = hier.build(ctx0, model_id, keep=lambda inp: not is_module_d(model["scope"], inp["stage"]))
    units_ = hier.leaf_units(ctx0, mc, M, T)
    var_list = hier.variables(ctx0, T["models"])
    draws = hier.draw(rng, var_list, iterations, hier.correlation_pairs(ctx0, T["models"], var_list))
    amt = hier.amounts_matrix(store, overrides, ctx0, T, var_list, draws, iterations)
    mult = hier.multipliers(rng, T, iterations)
    samples = (amt * hier.path_multipliers(T, mult)) @ units_ if T["leaves"] else np.zeros((iterations, len(method_ids)))
    nested = len(T["models"]) > 1
    note = "Uncertainty of the foreground amounts (data-quality scores in step 3)"
    note += " of every line, including the lines of nested models," if nested else ""
    note += " and the parameter distributions" if var_list else ""
    note += (f" ({len(T['lines'])} lines, {len(var_list)} parameters"
             f"{', ' + str(len(T['models']) - 1) + ' nested model(s)' if nested else ''}).")
    return {"mode": "foreground", "iterations": iterations,
            "methods": [_stats(samples[:, k]) for k in range(len(method_ids))],
            "n_lines": len(T["lines"]), "n_parameters": len(var_list), "n_models": len(T["models"]),
            "note": note + " Background database uncertainty is not included in this run."}


def full_mc(store, model_ids, method_ids, iterations=200, seed=42, progress=lambda *a: None,
            cancelled=lambda: False, scenario=None, bg=None):
    """Monte Carlo over background exchange uncertainty, the data quality of every foreground line at every level of
    nesting, and all parameter distributions. Compared models share the random background in each iteration, and
    any line or parameter they have in common (e.g. the same sub-model) keeps one draw, so comparisons are paired."""
    import hier
    method_ids = [int(m) for m in method_ids]
    if not method_ids:
        raise LCAError("Pick at least one impact category in step 4.")
    iterations = int(max(20, min(int(iterations), 5000)))
    overrides = _scenario(store, scenario)
    mc = get_mc(store, bg)
    M = Methods(store, mc, method_ids)
    rng = np.random.default_rng(seed)
    frng = np.random.default_rng(seed + 1)
    ctx0 = Context(store, overrides)
    prepared, all_models = [], []
    for mid in model_ids:
        model = ctx0.model(mid)
        if not model["inputs"]:
            raise LCAError("Every model needs at least one input.")
        T = hier.build(ctx0, mid, keep=lambda inp, sc=model["scope"]: not is_module_d(sc, inp["stage"]))
        leaves = []
        for lf in T["leaves"]:
            a, fl, fx = line_unit_demand(ctx0, lf["inp"])
            leaves.append((demand_vector(mc, a), flow_vector(mc, fl), fx))
        prepared.append((model, T, leaves))
        all_models += [m for m in T["models"] if m not in all_models]
    var_list = hier.variables(ctx0, all_models)
    draws = hier.draw(frng, var_list, iterations, hier.correlation_pairs(ctx0, all_models, var_list))
    shared = {}
    pre = []
    for model, T, leaves in prepared:
        amt = hier.amounts_matrix(store, overrides, ctx0, T, var_list, draws, iterations)
        pre.append(amt * hier.path_multipliers(T, hier.multipliers(frng, T, iterations, shared)))
    has_bg = bool((mc.t_unc["type"] > 0).any() or (mc.b_unc["type"] > 0).any())
    res = np.zeros((len(prepared), iterations, len(method_ids)))
    for it in range(iterations):
        if cancelled():
            raise Cancelled()
        if has_bg:
            A = mc.build_A(sample_values(rng, mc.t_amt, mc.t_unc))
            B = mc.build_B(sample_values(rng, mc.b_amt, mc.b_unc))
            try:
                lu = splu(A)
            except RuntimeError:
                lu, B = mc.lu, mc.B
            Q = (sp.csr_matrix(M.C) @ B).toarray() + (M.Q - (sp.csr_matrix(M.C) @ mc.B).toarray() if M.regional else 0)
        else:
            lu, B, Q = mc.lu, mc.B, M.Q
        for p, (model, T, leaves) in enumerate(prepared):
            f = np.zeros(mc.n)
            gd = np.zeros(len(mc.flow_ids))
            fixed_h = np.zeros(len(method_ids))
            for j, (dvec, fvec, fx) in enumerate(leaves):
                amt = pre[p][it, j]
                f += dvec * amt
                gd += fvec * amt
                for x, a in fx:
                    fixed_h += M.fixed_vector(x) * a * amt
            s = lu.solve(f) if f.any() else np.zeros(mc.n)
            res[p, it] = Q @ s + M.Cd @ gd + fixed_h
        if it % max(1, iterations // 100) == 0:
            progress(int(100 * it / iterations), f"Iteration {it + 1:,} of {iterations:,}")
    out = {"mode": "full" if has_bg else "foreground", "iterations": iterations, "background_uncertainty": has_bg,
           "models": [{"id": m["id"], "name": m["name"], "methods": [_stats(res[p, :, k]) for k in range(len(method_ids))]}
                      for p, (m, _, _) in enumerate(prepared)],
           "methods": [{k: r[k] for k in ("id", "family", "category", "indicator", "unit")} for r in M.rows],
           "n_parameters": len(var_list), "n_shared_lines": sum(1 for _ in shared)}
    if len(prepared) > 1:
        def p_lower(a, b):
            scale = max(np.abs(a).max(), np.abs(b).max())
            diff = a - b
            if scale == 0 or np.all(np.abs(diff) <= 1e-9 * scale):
                return None
            return float((diff < 0).mean())
        out["pairs"] = [{"a": prepared[i][0]["name"], "b": prepared[j][0]["name"],
                         "p_a_lower": [p_lower(res[i, :, k], res[j, :, k]) for k in range(len(method_ids))],
                         "diff_p2_5": [float(np.percentile(res[i, :, k] - res[j, :, k], 2.5)) for k in range(len(method_ids))],
                         "diff_p97_5": [float(np.percentile(res[i, :, k] - res[j, :, k], 97.5)) for k in range(len(method_ids))]}
                        for i in range(len(prepared)) for j in range(i + 1, len(prepared))]
    shared_txt = ("Lines and parameters that the models have in common use the same random values; the other "
                  "foreground lines are sampled for each model.")
    out["note"] = (f"Background exchange uncertainty from the database (the same random background for every model in "
                   f"each iteration), foreground data-quality scores of every line including nested models, and "
                   f"parameter distributions, {iterations} iterations. {shared_txt}" if has_bg else
                   "The databases carry no uncertainty information, so only foreground data quality (every line, "
                   f"including nested models) and parameter distributions were propagated. {shared_txt}")
    return out


# ============================================================================ global sensitivity (Sobol)
def sobol(store, model_id, method_ids, n=512, seed=7, scenario=None, bg=None):
    """First-order and total Sobol indices (Saltelli 2010, Jansen 1999) for the uncertain inputs of a model: the
    amount of every line at every level of nesting (lognormal from its data-quality score) and every parameter
    with a distribution (project and models)."""
    import hier
    from scipy import stats
    method_ids = [int(m) for m in method_ids]
    overrides = _scenario(store, scenario)
    mc = get_mc(store, bg)
    M = Methods(store, mc, method_ids)
    ctx0 = Context(store, overrides)
    model = ctx0.model(model_id)
    if not model["inputs"]:
        raise LCAError("This model has no inputs yet.")
    T = hier.build(ctx0, model_id, keep=lambda inp: not is_module_d(model["scope"], inp["stage"]))
    units_ = hier.leaf_units(ctx0, mc, M, T)
    var_list = hier.variables(ctx0, T["models"])
    nl = len(T["lines"])
    d = nl + len(var_list)
    if d == 0:
        raise LCAError("Nothing is uncertain: add lines or parameter distributions first.")
    n = int(max(64, min(n, 4096)))
    rng = np.random.default_rng(seed)
    A, Bm = rng.random((n, d)), rng.random((n, d))
    sig = np.array([L["sigma"] for L in T["lines"]])
    resample = hier.needs_resampling(ctx0, T, var_list)
    base_amt = hier.path_amounts(ctx0, T)
    if hier.correlation_pairs(ctx0, T["models"], var_list):
        note_corr = " Correlations between parameters are not used here: Sobol indices assume independent factors."
    else:
        note_corr = ""

    def evaluate(U):
        mult = np.exp(stats.norm.ppf(np.clip(U[:, :nl], 1e-9, 1 - 1e-9)) * sig)
        if resample:
            vals = {v["key"]: _ppf_param(v["p"], np.clip(U[:, nl + j], 1e-9, 1 - 1e-9)) for j, v in enumerate(var_list)}
            amt = np.zeros((U.shape[0], len(T["leaves"])))
            for r in range(U.shape[0]):
                ctx = hier.context_for(store, overrides, ctx0, {k: float(v[r]) for k, v in vals.items()})
                amt[r] = hier.path_amounts(ctx, T)
        else:
            amt = np.tile(base_amt, (U.shape[0], 1))
        return (amt * hier.path_multipliers(T, mult)) @ units_
    fA, fB = evaluate(A), evaluate(Bm)
    f0 = np.mean(np.vstack([fA, fB]), axis=0)  # centre outputs: the estimators are biased when |mean| >> sd
    fA, fB = fA - f0, fB - f0
    var = np.var(np.vstack([fA, fB]), axis=0)
    S1, ST = np.zeros((d, len(method_ids))), np.zeros((d, len(method_ids)))
    for j in range(d):
        ABj = A.copy()
        ABj[:, j] = Bm[:, j]
        fAB = evaluate(ABj) - f0
        with np.errstate(invalid="ignore", divide="ignore"):
            S1[j] = np.where(var > 0, np.mean(fB * (fAB - fA), axis=0) / var, 0)
            ST[j] = np.where(var > 0, 0.5 * np.mean((fA - fAB) ** 2, axis=0) / var, 0)
    mnames = {mid: ctx0.model(mid)["name"] for mid in T["models"]}
    names = []
    for L in T["lines"]:
        nm = L["inp"]["label"] or L["inp"]["target"]["name"]
        names.append("line: " + nm + (f" (in {mnames[L['owner']]})" if L["depth"] else ""))
    for v in var_list:
        names.append("parameter: " + v["p"]["name"] + (f" (in {mnames.get(v['key'][1], '')})" if v["key"][0] == "m" and
                                                       v["key"][1] != model_id else ""))
    return {"n": n, "factors": names, "methods": [{k: r[k] for k in ("id", "category", "unit")} for r in M.rows],
            "S1": np.clip(S1, 0, 1).tolist(), "ST": np.clip(ST, 0, 1).tolist(),
            "note": f"Sobol indices from {n * (d + 2):,} model evaluations over {nl} lines (all levels) and "
                    f"{len(var_list)} parameters. S1: share of variance from a factor alone; ST: including its "
                    f"interactions. Background uncertainty is held fixed.{note_corr}"}


# ============================================================================ supply chain tree
def tree(store, model_id, method_id, node=None, amount=None, scenario=None, cutoff=0.005, limit=25):
    """Children of a node in the supply chain with their cumulative impact for one category.
    node None = the model's lines; node 'a:<activity id>' = inputs of that dataset."""
    mc = _cache.get(store)
    M = Methods(store, mc, [int(method_id)])
    ctx = Context(store, _scenario(store, scenario))

    def unit_of(aid):
        key = (aid, (int(method_id),), "tree")
        if key not in mc.unit_cache:
            f = np.zeros(mc.n)
            f[mc.act_index[aid]] = 1.0
            mc.unit_cache[key] = float((M.Q @ mc.solve(f))[0])
        return mc.unit_cache[key]

    if node is None:
        model = ctx.model(model_id)
        share = allocation_share(model["scope"])
        out = []
        for inp in model["inputs"]:
            if is_module_d(model["scope"], inp["stage"]):
                continue
            amt = line_amount(ctx, model_id, inp) * (-1 if inp["avoided"] else 1) * share
            a, fl, fx = line_unit_demand(ctx, inp)
            h, _, _ = impacts(mc, M, a, fl, fx)
            out.append({"node": f"a:{inp['ref_id']}" if inp["kind"] == "activity" else None,
                        "name": inp["label"] or inp["target"]["name"], "location": inp["target"].get("location", ""),
                        "amount": amt, "unit": inp["target"]["unit"], "impact": float(h[0] * amt)})
        total = sum(o["impact"] for o in out)
        return {"total": total, "children": sorted(out, key=lambda o: -abs(o["impact"]))}
    aid = int(str(node).split(":")[1])
    amt = float(amount or 1.0)
    j = mc.act_index[aid]
    scale = amt / (mc.diag[j] or 1.0)
    total = unit_of(aid) * amt
    direct = float(M.Q[0, j] * scale)
    kids = []
    for t in store.q("SELECT t.input_id, SUM(t.amount) AS amount, a.name, a.location, a.unit FROM tech t "
                     "JOIN activities a ON a.id=t.input_id WHERE t.output_id=? AND t.input_id!=? GROUP BY t.input_id",
                     (aid, aid)):
        if t["input_id"] not in mc.act_index:
            continue
        camt = t["amount"] * scale
        kids.append({"node": f"a:{t['input_id']}", "name": t["name"], "location": t["location"], "amount": camt,
                     "unit": t["unit"], "impact": unit_of(t["input_id"]) * camt})
    kids.sort(key=lambda o: -abs(o["impact"]))
    shown = [k for k in kids if abs(k["impact"]) >= cutoff * abs(total or 1)][:limit]
    rest = sum(k["impact"] for k in kids) - sum(k["impact"] for k in shown)
    return {"total": total, "direct": direct, "children": shown, "rest": rest,
            "hidden": len(kids) - len(shown)}


# ============================================================================ validation
DB_META_REQUIRED = ("version", "system_model", "source", "licence", "release_date", "source_sha256", "importer_version")


def validate_database(store, db_id=None, sample=25, seed=3):
    """Database check in six separate statuses, because a solvable matrix does not mean a complete database:
    1 matrix consistency, 2 technosphere completeness, 3 elementary-flow coverage, 4 unit consistency,
    5 metadata completeness, 6 LCIA compatibility. Each status is ok, warning or error with its numbers."""
    import units as _units
    mc = _cache.get(store)
    out = {"datasets": mc.n, "exchanges": int(len(mc.t_amt)), "elementary_exchanges": int(len(mc.b_amt))}
    where, args = (" WHERE db_id=?", (db_id,)) if db_id else ("", ())
    ids = [r["id"] for r in store.q("SELECT id FROM activities" + where, args)]
    rng = np.random.default_rng(seed)
    pick = list(rng.choice(ids, size=min(sample, len(ids)), replace=False)) if ids else []
    if db_id:   # counts of the checked database only
        out["datasets"] = len(ids)
        out["exchanges"] = store.one("SELECT COUNT(*) AS n FROM tech t JOIN activities a ON a.id=t.output_id "
                                     "WHERE a.db_id=?", (db_id,))["n"]
        out["elementary_exchanges"] = store.one("SELECT COUNT(*) AS n FROM bio b JOIN activities a ON a.id=b.activity_id "
                                                "WHERE a.db_id=?", (db_id,))["n"]
    import staging as _staging
    integ = _staging.integrity(store, db_id)
    out["integrity_problems"] = integ
    worst, negative = 0.0, 0
    for aid in pick:
        f = np.zeros(mc.n)
        f[mc.act_index[int(aid)]] = 1.0
        s = mc.solve(f)
        r = mc.A @ s - f
        worst = max(worst, float(np.linalg.norm(r) / max(np.linalg.norm(f), 1e-300)))
        negative += int((s < -1e-9 * max(np.abs(s).max(), 1)).any())
    out["max_relative_residual"] = worst
    out["sampled"] = len(pick)
    out["negative_scaling"] = negative
    idset = {mc.act_index[i] for i in ids if i in mc.act_index}
    out["zero_production"] = int(sum(1 for j in idset if mc.diag[j] == 0))
    statuses = []

    def status(key, label, level, message, **numbers):
        statuses.append({"key": key, "label": label, "level": level, "message": message, **numbers})

    # 1 matrix
    m_ok = worst < 1e-8 and out["zero_production"] == 0 and not integ
    status("matrix", "Matrix consistency", "ok" if m_ok else "error",
           (f"Random solves of {len(pick)} datasets reproduce the demand to within {worst:.1e}; "
            f"{out['zero_production']} datasets with zero production." if pick else "No datasets.")
           + ("" if not integ else " Not valid: " + "; ".join(f"{v} {k}" for k, v in integ.items()) + "."),
           residual=worst, zero_production=out["zero_production"], integrity=integ)
    # 2 technosphere completeness
    reasons = store.q("SELECT COALESCE(reason,'no producer') AS reason, COUNT(*) AS n, COUNT(DISTINCT output_id) AS acts "
                      "FROM unlinked WHERE linked_to IS NULL" + (" AND db_id=?" if db_id else "") + " GROUP BY 1", args)
    n_unl = sum(r["n"] for r in reasons)
    out["unlinked_inputs"] = n_unl
    acts_aff = store.one("SELECT COUNT(DISTINCT output_id) AS n FROM unlinked WHERE linked_to IS NULL"
                         + (" AND db_id=?" if db_id else ""), args)["n"]
    share = acts_aff / len(ids) if ids else 0.0
    status("technosphere", "Technosphere completeness", "ok" if not n_unl else "warning",
           ("Every input has a supplier." if not n_unl else
            f"{n_unl} inputs of {acts_aff} datasets ({share * 100:.1f} %) have no single supplier: "
            + ", ".join(f"{r['n']} {r['reason']}" for r in reasons) + ". They add nothing to results until linked."),
           unresolved=n_unl, datasets_affected=acts_aff, by_reason={r["reason"]: r["n"] for r in reasons})
    # 3 elementary-flow coverage: the flows of the checked database only (the whole library when none is chosen)
    if db_id:
        used = {mc.flow_index[r["flow_id"]] for r in store.q(
            "SELECT DISTINCT b.flow_id FROM bio b JOIN activities a ON a.id=b.activity_id WHERE a.db_id=?", (db_id,))
            if r["flow_id"] in mc.flow_index}
    else:
        used = set(mc.b_rows.tolist())
    with_cf = {mc.flow_index[r["flow_id"]] for r in store.q("SELECT DISTINCT flow_id FROM cfs") if r["flow_id"] in mc.flow_index}
    out["flows_used"] = len(used)
    out["flows_without_any_factor"] = len(used - with_cf)
    cov = 1 - out["flows_without_any_factor"] / len(used) if used else 1.0
    status("flows", "Elementary-flow coverage", "ok" if cov >= 0.9 else "warning",
           f"{len(used) - out['flows_without_any_factor']} of {len(used)} elementary flows used by "
           f"{'this database' if db_id else 'the library'} have a "
           f"factor in at least one installed category ({cov * 100:.1f} %). Flows without any factor count as zero in "
           "every category.", coverage=cov)
    # 4 unit consistency
    flows = store.q("SELECT id, name, compartment, subcompartment, unit, c_name, c_comp, c_sub FROM flows")
    unknown_units = sorted({f["unit"] or "(none)" for f in flows if f["id"] in {int(mc.flow_ids[i]) for i in used}
                            and _units.factor(f["unit"] or "", f["unit"] or "") is None})
    used_ids = {int(mc.flow_ids[i]) for i in used}
    by_key = {}
    for f in flows:
        by_key.setdefault((f["c_name"], f["c_comp"], f["c_sub"]), []).append(f)
    # a name/compartment with several units matters only if the checked database uses one of those flows
    mixed = [k for k, v in by_key.items() if len({(f["unit"] or "").strip().lower() for f in v}) > 1
             and any(f["id"] in used_ids for f in v)]
    no_unit = store.one("SELECT COUNT(*) AS n FROM activities" + (" WHERE db_id=? AND" if db_id else " WHERE")
                        + " COALESCE(unit,'')=''", args)["n"]
    u_ok = not unknown_units and not mixed and not no_unit
    status("units", "Unit consistency", "ok" if u_ok else "warning",
           ("Units are known and consistent." if u_ok else
            "; ".join(x for x in (
                f"units Cyclia does not know: {', '.join(unknown_units[:6])}" if unknown_units else "",
                f"{len(mixed)} elementary flows exist with different units under the same name and compartment "
                f"(e.g. {mixed[0][0]}): a factor can only be right for one of them" if mixed else "",
                f"{no_unit} datasets without a unit" if no_unit else "") if x) + "."),
           unknown_units=unknown_units[:20], mixed_unit_flows=len(mixed), datasets_without_unit=no_unit)
    # 5 metadata
    dbs = store.q("SELECT * FROM databases" + (" WHERE id=?" if db_id else ""), args)
    missing = {d["name"]: [k for k in DB_META_REQUIRED if not (d.get(k) or "").strip()] for d in dbs}
    missing = {k: v for k, v in missing.items() if v}
    status("metadata", "Database metadata", "ok" if not missing else "warning",
           ("Version, system model, source, licence, release date, source file fingerprint and importer version are "
            "recorded." if not missing else
            "Missing for reproducibility: " + "; ".join(f"{k}: {', '.join(v)}" for k, v in list(missing.items())[:5])
            + ". Enter them under Database details."), missing=missing)
    # 6 LCIA compatibility
    fam = store.q("SELECT m.family, COUNT(DISTINCT c.flow_id) AS n FROM methods m LEFT JOIN cfs c ON c.method_id=m.id "
                  "GROUP BY m.family")
    fam_cov = []
    for f in fam:
        fl = {mc.flow_index[r["flow_id"]] for r in store.q(
            "SELECT DISTINCT c.flow_id FROM cfs c JOIN methods m ON m.id=c.method_id WHERE m.family=?", (f["family"],))
            if r["flow_id"] in mc.flow_index}
        fam_cov.append({"family": f["family"], "flows_with_factor": len(fl & used),
                        "share_of_used_flows": len(fl & used) / len(used) if used else 0.0})
    fam_cov.sort(key=lambda x: -x["share_of_used_flows"])
    status("lcia", "LCIA compatibility", "ok" if fam_cov and fam_cov[0]["flows_with_factor"] else "warning",
           ("No impact method installed." if not fam_cov else
            "; ".join(f"{x['family']}: {x['flows_with_factor']} flows ({x['share_of_used_flows'] * 100:.1f} % of the "
                      "flows used)" for x in fam_cov[:5])), families=fam_cov)
    out["statuses"] = statuses
    errors = [x["label"] for x in statuses if x["level"] == "error"]
    warns = [x["label"] for x in statuses if x["level"] == "warning"]
    out["verdict"] = ("Errors: " + ", ".join(errors) + "." if errors else
                      ("The matrix can be solved, but check: " + ", ".join(warns) + "." if warns else
                       "All six checks passed: matrix, technosphere, flows, units, metadata and LCIA."))
    if negative:
        out["note"] = (f"{negative} of {len(pick)} sampled datasets have negative scaling factors somewhere in their supply "
                       "chain. This is normal with system expansion or waste treatment, but check it if unexpected.")
    return out


def benchmark(store, rows):
    """Compare Cyclia with reference results. rows: dicts with activity, location, product (optional),
    database (optional), method, category, indicator, value."""
    mc = _cache.get(store)
    out, missing = [], []
    for r in rows:
        sql = "SELECT a.id FROM activities a JOIN databases d ON d.id=a.db_id WHERE lower(a.name)=lower(?)"
        args = [r["activity"]]
        if r.get("location"):
            sql += " AND upper(a.location)=upper(?)"
            args.append(r["location"])
        if r.get("product"):
            sql += " AND lower(a.product)=lower(?)"
            args.append(r["product"])
        if r.get("database"):
            sql += " AND d.name=?"
            args.append(r["database"])
        hit = store.one(sql, args)
        meth = store.one("SELECT id FROM methods WHERE lower(family)=lower(?) AND lower(category)=lower(?) AND "
                         "lower(indicator)=lower(?)", (r["method"], r["category"], r["indicator"] or r["category"]))
        if not hit or not meth:
            missing.append(f"{r['activity']} [{r.get('location', '')}] / {r['category']}: "
                           f"{'dataset' if not hit else 'method'} not found")
            continue
        M = Methods(store, mc, [meth["id"]])
        f = np.zeros(mc.n)
        f[mc.act_index[hit["id"]]] = 1.0
        val = float((M.Q @ mc.solve(f))[0])
        ref = float(r["value"])
        dev = (val - ref) / abs(ref) * 100 if ref else (0.0 if val == 0 else None)
        out.append({"activity": r["activity"], "location": r.get("location", ""), "category": r["category"],
                    "reference": ref, "cyclia": val, "deviation_percent": dev})
    devs = [abs(o["deviation_percent"]) for o in out if o["deviation_percent"] is not None]
    return {"compared": len(out), "missing": missing[:50], "n_missing": len(missing), "rows": out,
            "median_abs_deviation_percent": float(np.median(devs)) if devs else None,
            "max_abs_deviation_percent": float(max(devs)) if devs else None,
            "within_0_1_percent": int(sum(d <= 0.1 for d in devs)), "within_1_percent": int(sum(d <= 1 for d in devs))}


# ============================================================================ compare and checks
def compare(store, model_ids, method_ids, scenario=None, bg=None, equivalence=""):
    """Results of several models side by side, behind a validation gate (ISO 14044 4.2.3.7, 5.3).

    The gate blocks comparisons whose functional units cannot be equivalent (different unit dimension or amount)
    or whose results have errors. Differences in product description, boundary, stage system, allocation,
    approach, geography, period, background system model and data quality are listed as issues. The comparison is
    "valid" only when there are no issues and the user has stated why the alternatives are functionally equivalent;
    otherwise it is a screening comparison and must not be presented as a comparative assertion."""
    if len(model_ids) < 2:
        raise LCAError("Pick at least two models to compare.")
    runs = [run(store, mid, method_ids, top=5, scenario=scenario, bg=bg) for mid in model_ids]
    rows = []
    for r in runs:
        dq = {(c["family"], c["category"], c["indicator"]): c["dqr"]
              for c in (r.get("data_quality") or {}).get("by_category") or []}
        rows.append({"model": r["model"], "totals": [x["total"] for x in r["results"]],
                     "module_d": [x["module_d"] for x in r["results"]],
                     "errors": [c for c in r["checks"] if c["level"] == "error"],
                     "dqr": [dq.get((x["family"], x["category"], x["indicator"])) for x in r["results"]]})
    methods = [store.one("SELECT id, family, category, indicator, unit FROM methods WHERE id=?", (m,)) for m in method_ids]
    blocking, issues = [], []
    m0 = rows[0]["model"]
    for r in rows[1:]:
        m = r["model"]
        fac = units.factor(m["unit"] or "", m0["unit"] or "") if (m["unit"] or "") != (m0["unit"] or "") else 1.0
        if fac is None:
            blocking.append(f"'{m['name']}' has the functional unit {m['amount']:g} {m['unit']}, which cannot be compared with "
                            f"{m0['amount']:g} {m0['unit']} of '{m0['name']}'. Alternatives must fulfil the same function "
                            "in the same unit (ISO 14044 4.2.3.7).")
        elif abs(m["amount"] * fac - m0["amount"]) > 1e-9 * max(abs(m0["amount"]), 1e-30):
            blocking.append(f"'{m['name']}' is calculated for {m['amount']:g} {m['unit']} and '{m0['name']}' for "
                            f"{m0['amount']:g} {m0['unit']}. Use the same functional unit and reference amount.")
    for r in rows:
        if r["errors"]:
            blocking.append(f"'{r['model']['name']}' has {len(r['errors'])} error(s) in its checks; fix them first.")
    if len({(r["model"]["product"] or "").strip().lower() for r in rows}) > 1:
        issues.append("The products are described differently. State why they deliver the same function (performance, "
                      "service life, quality) in the equivalence statement.")

    def differs(key, label, fmt=lambda v: v or "not stated"):
        vals = [(r["model"]["name"], (r["model"]["scope"] or {}).get(key) or "") for r in rows]
        if len({v for _, v in vals}) > 1:
            issues.append(f"Different {label}: " + "; ".join(f"{n}: {fmt(v)}" for n, v in vals) + ".")
    differs("boundary", "system boundaries")
    differs("stage_system", "life cycle stage systems")
    differs("approach", "modelling approaches")
    differs("alloc_basis", "allocation rules", lambda v: {"mass": "mass", "price": "economic", "energy": "energy"}.get(v, "none or manual"))
    differs("geography", "geographical scopes")
    differs("period", "time periods")

    dq_issues = []
    for k, meth in enumerate(methods):
        vals = [(r["model"]["name"], r["dqr"][k]) for r in rows if r["dqr"][k] is not None]
        if len(vals) > 1 and max(v for _, v in vals) - min(v for _, v in vals) >= 1.0:
            dq_issues.append(f"{meth['category']} (" + ", ".join(f"{n}: {v:.1f}" for n, v in vals) + ")")
    if dq_issues:
        issues.append("The data quality differs a lot between the alternatives in " + "; ".join(dq_issues) +
                      " (pedigree indicator, 1 best to 5 worst). ISO 14044 4.2.3.6.3 asks for comparable data quality "
                      "in a comparison; results in these categories are less comparable.")
    sms_n = []
    for r, mid in zip(runs, model_ids):
        seen, todo, sm = set(), [mid], set()
        while todo:
            x = todo.pop()
            if x in seen:
                continue
            seen.add(x)
            for i in store.model(x)["inputs"]:
                if i["kind"] == "activity" and not i["missing"] and i["target"].get("system_model"):
                    sm.add(i["target"]["system_model"])
                elif i["kind"] == "model" and i["ref_id"]:
                    todo.append(i["ref_id"])
        sms_n.append((r["model"]["name"], ", ".join(sorted(sm)) or "-"))
    if len({v for _, v in sms_n}) > 1:
        issues.append("Different background system models (including nested models): " +
                      "; ".join(f"{n}: {v}" for n, v in sms_n) + ".")
    eq = (equivalence or "").strip()
    status = "blocked" if blocking else ("valid" if not issues and len(eq) >= 20 else "screening")
    if blocking:
        for r in rows:
            r["totals"] = [None] * len(r["totals"])
            r["module_d"] = [None] * len(r["module_d"])
    warnings = blocking + issues
    if not blocking and len(eq) < 20:
        warnings.append("No functional equivalence statement yet. Without it, this is a screening comparison, not a "
                        "comparative assertion.")
    return {"models": rows, "methods": methods, "warnings": warnings, "blocking": blocking, "issues": issues,
            "status": status, "equivalence": eq,
            "note": {"valid": "The alternatives passed the comparison checks. Judge differences against the uncertainty "
                              "(comparative Monte Carlo) before concluding; a comparative assertion disclosed to the "
                              "public also needs a critical review panel (ISO 14044 6.4).",
                     "screening": "Screening comparison: the alternatives are not shown to be equivalent. Use it to "
                                  "learn, not to claim that one product is better.",
                     "blocked": "These models cannot be compared until the blocking problems are solved."}[status]}


def compare_scenarios(store, model_id, method_ids, scenario_ids, bg=None):
    rows = []
    for sid in [None] + [int(s) for s in scenario_ids]:
        r = run(store, model_id, method_ids, top=3, scenario=sid, bg=bg)
        name = "Base values" if sid is None else store.one("SELECT name FROM main.scenarios WHERE id=?", (sid,))["name"]
        rows.append({"scenario": name, "totals": [x["total"] for x in r["results"]]})
    methods = [store.one("SELECT id, family, category, indicator, unit FROM methods WHERE id=?", (m,)) for m in method_ids]
    return {"scenarios": rows, "methods": methods}


def land_coverage(M, mc, g, flow_label, results):
    """For land use categories: the share of the inventory's land occupation (m2*a) and transformation (m2) that has
    a factor. The ecoinvent benchmark of 1.3.4 showed Cyclia up to 14 % below ecoinvent's EF 3.1 land use results
    where flows such as 'Occupation, lake, artificial' or seabed flows had no factor: this makes such gaps visible
    in every result."""
    import units as _u
    out = []
    land = []
    for i in np.where(np.abs(g) > 0)[0]:
        n, ctxt, u = flow_label(i)
        nl = (n or "").lower()
        kind = "occupation" if nl.startswith("occupation,") else "transformation" if nl.startswith("transformation,") else None
        if kind:
            conv = _u.factor(u, "m2*a" if kind == "occupation" else "m2") or 1.0
            land.append((i, kind, n, abs(float(g[i])) * conv))
    if not land:
        return out
    for k, r in enumerate(results):
        t = f"{r['category']} {r['indicator']}".lower()
        if not (("land use" in t or "soil quality" in t or "land occupation" in t) and "climate" not in t):
            continue
        for kind in ("occupation", "transformation"):
            items = [x for x in land if x[1] == kind]
            tot = sum(x[3] for x in items)
            if not tot:
                continue
            miss = sorted([x for x in items if M.C[k, x[0]] == 0], key=lambda x: -x[3])
            out.append({"category": r["category"], "kind": kind, "total": tot,
                        "share_without_factor": sum(x[3] for x in miss) / tot,
                        "flows_without_factor": [{"name": x[2], "amount": x[3]} for x in miss[:8]]})
    return out


def checks(store, model_id, method_ids, result=None):
    """Completeness, consistency and data checks (ISO 14044 4.5.3). Levels: error, warning, info."""
    out = []
    add = lambda level, step, msg: out.append({"level": level, "step": step, "message": msg})
    m = store.model(model_id)
    sc = m["scope"] or {}
    if not (m["unit"] and m["product"]):
        add("error", "scope", "The functional unit is incomplete: give amount, unit and product.")
    for key, label in (("goal", "goal of the study"), ("application", "intended application"),
                       ("audience", "intended audience"), ("boundary", "system boundary")):
        if not (sc.get(key) or "").strip():
            add("warning", "scope", f"Goal & scope: the {label} is not stated (ISO 14044 4.2).")
    for key, label in (("geography", "geographical coverage"), ("period", "time period"),
                       ("cutoff", "cut-off criteria"), ("allocation", "allocation procedure"),
                       ("dq_requirements", "data quality requirements")):
        if not (sc.get(key) or "").strip():
            add("info", "scope", f"Goal & scope: {label} not described.")
    if (sc.get("comparative") or "").startswith("Yes"):
        if not (sc.get("review") or "").strip():
            add("warning", "report", "A comparative assertion disclosed to the public needs a critical review panel (ISO 14044 "
                                     "6.3). Describe the review in step 6.")
        elif (sc.get("review_status") or "") not in ("panel", "verified"):
            add("warning", "report", "A comparative assertion disclosed to the public needs a review by a panel of interested "
                                     "parties (ISO 14044 6.4). Set the review status in step 6 when the panel review is done.")
    share = allocation_share(sc)
    if share < 1:
        basis = sc.get("alloc_basis") or ""
        how = {"mass": "mass", "price": "economic value", "energy": "energy content",
               "physical": f"physical causality ({sc.get('alloc_property') or 'a physical property'})"}.get(basis, "a manual share")
        add("info", "scope", f"Allocation: {share * 100:.4g} % of the burdens go to this product, by {how}. ISO 14044 4.3.4.2 "
                             "prefers avoiding allocation (subdivision or system expansion) where possible.")
    inputs = m["inputs"]
    if not inputs:
        add("error", "inventory", "The inventory is empty.")
    missing = [i for i in inputs if i["missing"]]
    if missing:
        add("error", "inventory", f"{len(missing)} line(s) point to datasets that are not in this library"
                                  f"{' (' + ', '.join(sorted({i['ref_db'] for i in missing if i['ref_db']})) + ')' if any(i['ref_db'] for i in missing) else ''}. "
                                  "Import those databases or replace the lines.")
    zero = [i for i in inputs if not i["amount"] and not i.get("formula")]
    if zero:
        add("warning", "inventory", f"{len(zero)} line(s) have an amount of zero: " +
            ", ".join((i["label"] or i["target"]["name"])[:40] for i in zero[:3]))
    neg = [i for i in inputs if i["amount"] < 0]
    if neg:
        add("warning", "inventory", f"{len(neg)} line(s) have a negative amount. For credits use 'avoided product'.")
    no_src = [i for i in inputs if not (i["comment"] or "").strip()]
    if no_src:
        add("info", "inventory", f"{len(no_src)} of {len(inputs)} lines have no data source note.")
    unrated = [i for i in inputs if list(i["pedigree"]) == [3, 3, 3, 3, 3]]
    if unrated:
        add("info", "inventory", f"{len(unrated)} line(s) still have the default data-quality score (3,3,3,3,3).")
    en = str(sc.get("stage_system", "")).startswith("EN 15804")
    if any(i["avoided"] for i in inputs):
        if en and any(i["avoided"] and not is_module_d(sc, i["stage"]) for i in inputs):
            add("warning", "inventory", "EN 15804: credits from avoided products belong in module D. Some avoided "
                                        "products are assigned to another stage.")
        add("info", "inventory", "The model includes avoided products (system expansion). Report results with and without "
                                 "credits and state why expansion was chosen (ISO 14044 4.3.4.2).")
    if en and any(is_module_d(sc, i["stage"]) for i in inputs):
        add("info", "interpretation", "EN 15804: module D is reported separately and is not included in the A-C total.")
    fx = [i for i in inputs if i["kind"] == "fixed"]
    if fx:
        add("info", "inventory", f"{len(fx)} line(s) use fixed values from an EPD. They have no supply chain, no elementary "
                                 "flows and no background uncertainty; check that the EPD follows the same method version.")
    no_stage = [i for i in inputs if not i["stage"]]
    if no_stage and len(no_stage) < len(inputs):
        add("info", "inventory", f"{len(no_stage)} line(s) have no life cycle stage.")
    act_inputs = [i for i in inputs if i["kind"] == "activity" and not i["missing"]]
    # every line of every nested model, once, with the name of the model it belongs to
    tree_inputs = []
    seen_m, seen_i = set(), set()

    def walk(mid, depth):
        if mid in seen_m or depth > 25:
            return
        seen_m.add(mid)
        mm = m if mid == model_id else store.model(mid)
        if not mm:
            return
        for i in mm["inputs"]:
            if i["id"] not in seen_i:
                seen_i.add(i["id"])
                tree_inputs.append((i, mm["name"], depth))
            if i["kind"] == "model" and i["ref_id"]:
                walk(i["ref_id"], depth + 1)
    walk(model_id, 0)
    nested = any(d for _, _, d in tree_inputs)
    all_act = [(i, n) for i, n, _ in tree_inputs if i["kind"] == "activity" and not i["missing"]]
    by_sm = {}
    for i, n in all_act:
        sm = i["target"].get("system_model") or ""
        if sm:
            by_sm.setdefault(sm, set()).add(n)
    if len(by_sm) > 1:
        add("warning", "inventory", "Inputs come from different system models" + (" across the nested models" if nested else "") +
            ": " + "; ".join(f"{sm} (in {', '.join(sorted(ns))})" for sm, ns in sorted(by_sm.items())) +
            ". Mixing system models is inconsistent (ISO 14044 4.2.3.6.2).")
    dbs = {i["target"].get("db") for i, _ in all_act}
    if len(dbs) > 1:
        add("info", "inventory", f"Inputs come from {len(dbs)} databases: {', '.join(sorted(d for d in dbs if d))}. Check "
                                 "their methodological consistency.")
    if any(w in (d or "").lower() for d in dbs for w in ("tutorial", "demo")):
        add("warning", "inventory", "The tutorial or demo database contains illustrative data. Do not publish results based "
                                    "on it.")
    un = store.one("SELECT COUNT(DISTINCT product) AS n FROM unlinked WHERE linked_to IS NULL AND db_id IN "
                   "(SELECT DISTINCT a.db_id FROM activities a WHERE a.id IN (SELECT ref_id FROM main.model_inputs "
                   "WHERE kind='activity'))")
    if un and un["n"]:
        add("warning", "inventory", f"Databases used by this project have {un['n']} products without a linked supplier, so "
                                    "some supply chains are cut short. Link them in step 1.")
    geo = (sc.get("geography") or "").strip().lower()
    if geo and act_inputs:
        far = [i for i in act_inputs if (i["target"].get("location") or "").lower() not in
               ("glo", "row", "rer", "europe", geo) and geo not in (i["target"].get("location") or "").lower()]
        if far:
            add("info", "inventory", f"{len(far)} input(s) use datasets from another region than '{sc['geography']}'.")
    main_mass = _num(sc.get("main_mass"))
    if main_mass > 0:
        mass_in = sum(i["amount"] for i in act_inputs if units.info(i["target"]["unit"]) and
                      units.info(i["target"]["unit"])[0] == "mass" and not i["avoided"] and
                      "treatment" not in (i["target"]["name"] or "").lower()) * 1.0
        mass_out = main_mass + sum(_num(c.get("mass")) for c in sc.get("coproducts") or [])
        if mass_in and abs(mass_in - mass_out) / max(mass_in, mass_out) > 0.1:
            add("info", "inventory", f"Mass balance: material inputs {mass_in:.4g} kg vs products {mass_out:.4g} kg per "
                                     "functional unit. A gap above 10 % may mean missing inputs, wastes or emissions.")
    fams = {store.one("SELECT family FROM methods WHERE id=?", (mid,))["family"] for mid in method_ids
            if store.one("SELECT family FROM methods WHERE id=?", (mid,))}
    if len(fams) > 1:
        add("info", "impact", f"Categories come from {len(fams)} method families. Keep one family per indicator in a paper.")
    if result:
        for t in result.get("toxicity_coverage") or []:
            if t["n_missing"]:
                add("warning", "impact", f"{t['category']}: {t['n_missing']} of {t['n_emitted']} emitted substances have no "
                                         "toxicity factor, so the result is incomplete. See Inventory results > Toxicity "
                                         "coverage; build screening factors in Toolbox > Chemicals if needed.")
        for x in result.get("site_factors") or []:
            add("info", "impact", f"Site-specific factor used for {x['flow']} in {x['category']} ({x['site']:.4g} instead of "
                                  f"the generic {x['generic']:.4g}); it applies to the model's own emissions only.")
        if result.get("background"):
            b = result["background"]
            add("info", "scope", f"Background scenario '{b['name']}' ({b['kind']}) changed the database before calculation. "
                                 "Describe it in the scope of the report.")
        for r in result["results"]:
            if r["cfs_matched"] == 0:
                add("error", "impact", f"'{r['category']}' has no characterisation factor for any flow in your databases, so "
                                       "its result is always zero. Import a matching method or a flow mapping.")
        for lc in result.get("land_coverage") or []:
            if lc["share_without_factor"] > 0.005:
                ex = ", ".join(f["name"] for f in lc["flows_without_factor"][:3])
                add("warning", "impact", f"{lc['category']}: {lc['share_without_factor'] * 100:.1f} % of the land "
                                         f"{lc['kind']} in the inventory has no factor (e.g. {ex}), so the result is "
                                         "probably too low. Check the method file or add the factors from the method's source.")
        mi = [u for u in result.get("uncharacterised", []) if u["mapping_issue"]]
        if mi:
            add("warning", "impact", f"{len(mi)} inventory flow(s) have factors in the selected method under another name or "
                                     f"compartment (e.g. {mi[0]['name']}, {mi[0]['context']}). Import a flow mapping in step 1.")
        for l in result["lines"]:
            if l["kind"] == "flow" and all(abs(u) == 0 for u in l["unit_impact"]):
                add("warning", "impact", f"The direct flow '{l['name']}' has no factor in any selected category, so it adds "
                                         "nothing. Check its compartment.")
            if l["kind"] == "fixed" and any(u == 0 for u in l["unit_impact"]):
                add("warning", "impact", f"The EPD line '{l['name']}' has no value for some selected categories; they count "
                                         "as zero.")
        totals = [r["total"] for r in result["results"]]
        small = []
        for l in result["lines"]:
            shares = [abs(l["impact"][k]) / abs(t) for k, t in enumerate(totals) if t]
            if shares and max(shares) < 0.01:
                small.append(l["name"])
        if small and len(small) < len(result["lines"]):
            add("info", "interpretation", f"{len(small)} line(s) contribute less than 1 % in every category (e.g. "
                                          f"{small[0][:50]}); candidates for the cut-off check.")
        for r in result["results"]:
            ac = [b for b in r["by_input"] if not b["module_d"]]
            if r["total"] and ac:
                top = max(ac, key=lambda b: abs(b["impact"]))
                denom = sum(abs(b["impact"]) for b in ac) or 1
                if abs(top["impact"]) / denom > 0.5:
                    add("info", "interpretation", f"{r['category']}: '{top['name'][:50]}' gives "
                                                  f"{abs(top['impact']) / denom * 100:.0f} % of the impact; its data quality "
                                                  "matters most (sensitivity check).")
    import analysis
    for grp in analysis.method_versions(fams):
        add("warning", "impact", f"Different versions of the same method are mixed ({', '.join(grp)}). Use one version for "
                                 "all categories so that results are consistent.")
    if not (sc.get("approach") or ""):
        add("info", "scope", "Goal & scope: modelling approach (attributional or consequential) not stated (ISO 14044 "
                             "4.2.3.3; ISO/TS 14074 for interpretation).")
    for level, msg in analysis.approach_issues(sc, [i["target"].get("system_model") for i, _ in all_act]):
        add(level, "scope", msg + (" (checked in every nested model)" if nested else ""))
    yr = time.localtime().tm_year
    owner = {i["id"]: n for i, n, d in tree_inputs if d}
    nm = lambda i: (i["label"] or i["target"]["name"])[:50] + (f" in {owner[i['id']]}" if i["id"] in owner else "")
    tin = [i for i, _, _ in tree_inputs]
    old_spec = [i for i in tin if i.get("data_year") and i.get("data_type") == "primary" and yr - float(i["data_year"]) > 5]
    old_gen = [i for i in tin if i.get("data_year") and i.get("data_type") != "primary" and yr - float(i["data_year"]) > 10]
    if old_spec:
        add("warning", "inventory", f"{len(old_spec)} producer-specific (primary) line(s) use data older than 5 years (e.g. "
                                    f"{nm(old_spec[0])}, {int(old_spec[0]['data_year'])}). EN 15804+A2 6.3.8.2 allows at "
                                    "most 5 years for producer-specific data; update them or justify the exception.")
    if old_gen:
        add("warning", "inventory", f"{len(old_gen)} generic line(s) use data older than 10 years (e.g. {nm(old_gen[0])}, "
                                    f"{int(old_gen[0]['data_year'])}). EN 15804+A2 6.3.8.2 allows at most 10 years for "
                                    "generic data; update them or justify the exception.")
    per = [int(y) for y in re.findall(r"\b(19\d\d|20\d\d)\b", sc.get("period") or "")]
    if per:
        lo, hi = min(per), max(per)
        out_p = [i for i in tin if i.get("data_year") and i.get("data_type") == "primary" and
                 not lo - 1 <= float(i["data_year"]) <= hi]
        if out_p:
            add("info", "inventory", f"{len(out_p)} primary line(s) have a data year outside the time period of the study "
                                     f"({sc['period']}), e.g. {nm(out_p[0])} ({int(out_p[0]['data_year'])}).")
    no_year = [i for i in tin if not i.get("data_year") and i["kind"] != "model"]
    if no_year and any(i.get("data_year") for i in tin) or (no_year and (sc.get("epd") or sc.get("stage_system", "").startswith("EN 15804"))):
        add("info", "inventory", f"{len(no_year)} line(s)" + (" of this model and its nested models" if nested else "") +
            f" have no data year (e.g. {nm(no_year[0])}; Details in step 3). The age of data must be stated for EN "
            "15804+A2 and is part of the temporal representativeness.")
    if nested:
        n_unrated = sum(1 for i, _, d in tree_inputs if d and list(i["pedigree"]) == [3, 3, 3, 3, 3])
        if n_unrated:
            add("info", "inventory", f"{n_unrated} line(s) inside nested models still have the default data-quality score "
                                     "(3,3,3,3,3); they count in the uncertainty and the data quality of this result.")
    if result:
        eb = analysis.energy_balance(m, result["lines"])
        if eb and eb["efficiency"] > 1.0 + 1e-6:
            add("info", "inventory", f"Energy balance: the model delivers {eb['output_mj']:.4g} MJ per functional unit but its "
                                     f"energy inputs sum to {eb['input_mj']:.4g} MJ ({eb['efficiency'] * 100:.0f} % "
                                     "efficiency). Above 100 % usually means a missing energy input, unless ambient or "
                                     "solar energy is used.")
        lu = [r["category"] for r in result["results"] if "land use" in f"{r['category']} {r['indicator']}".lower()
              or "land occupation" in r["category"].lower() or "land transformation" in r["category"].lower()]
        if lu and any("ecoinvent" in (i["target"].get("db") or "").lower() for i, _ in all_act):
            add("info", "impact", f"Known limitation for {', '.join(sorted(set(lu)))}: in Cyclia's benchmark against "
                                  "ecoinvent's own LCIA results, land use results of some datasets were up to about 5 % "
                                  "lower (median 0.4 %), while other categories agreed. The cause is being traced (see the "
                                  "roadmap). State this limitation when you report or compare land use results.")
        if result.get("lcc") and result["lcc"]["n_uncosted"] and result["lcc"]["n_costed"]:
            add("info", "inventory", f"Life cycle costing: {result['lcc']['n_uncosted']} line(s) have no price and count as "
                                     "zero cost.")
        if (sc.get("epd") or {}).get("prospective") and not result.get("uncertainty"):
            add("warning", "report", "A prospective EPD must state the quantified uncertainty of its results (ISO 14025:2026). "
                                     "Run the Monte Carlo analysis in step 4.")
    order = {"error": 0, "warning": 1, "info": 2}
    out.sort(key=lambda c: order[c["level"]])
    return out
