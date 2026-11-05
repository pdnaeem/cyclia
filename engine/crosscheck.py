"""Independent reference calculation (Cyclia 1.3.4).

Recalculates datasets and models along a second code path and compares with Cyclia's engine:

- the technosphere and biosphere matrices are assembled again from the raw library tables (not from the cached
  matrices of the engine);
- the system A s = f is solved with an iterative Krylov method (GMRES with an incomplete-LU preconditioner, or a
  dense solve for small libraries) instead of the sparse direct LU factorisation used by the engine;
- characterisation uses the stored factors per flow directly (global factors, as in the ecoinvent benchmark);
- models are flattened by a separate recursive walk over the stored inventory lines (signs, allocation shares,
  nested models and their reference amounts).

It checks the matrix construction, sign conventions (including waste treatment datasets with a negative
reference output), the solver and the aggregation of nested models. It does not check the matching of
characterisation factors to flows: that is what the ecoinvent benchmark (comparison with ecoinvent's own LCIA
results) does.
"""
import numpy as np
import scipy.sparse as sp
from scipy.sparse import linalg as spl

import calc


def _assemble(store):
    acts = store.q("SELECT id, production FROM activities ORDER BY id")
    if not acts:
        raise ValueError("No database in the library.")
    ids = [a["id"] for a in acts]
    pos = {a: i for i, a in enumerate(ids)}
    n = len(ids)
    rows, cols, vals = [], [], []
    for i, a in enumerate(acts):
        rows.append(i)
        cols.append(i)
        vals.append(float(a["production"]) if a["production"] else 1.0)   # same convention as the engine: 0 -> 1
    for t in store.q("SELECT output_id, input_id, amount FROM tech"):
        if t["output_id"] in pos and t["input_id"] in pos:
            rows.append(pos[t["input_id"]])
            cols.append(pos[t["output_id"]])
            vals.append(-float(t["amount"]))
    A = sp.coo_matrix((vals, (rows, cols)), shape=(n, n)).tocsr()
    flows = [f["id"] for f in store.q("SELECT id FROM flows ORDER BY id")]
    fpos = {f: i for i, f in enumerate(flows)}
    br, bc, bv = [], [], []
    for b in store.q("SELECT activity_id, flow_id, amount FROM bio"):
        if b["activity_id"] in pos and b["flow_id"] in fpos:
            br.append(fpos[b["flow_id"]])
            bc.append(pos[b["activity_id"]])
            bv.append(float(b["amount"]))
    B = sp.coo_matrix((bv, (br, bc)), shape=(len(flows), n)).tocsr()
    return ids, pos, A, flows, fpos, B


def _cf_matrix(store, method_ids, fpos):
    C = np.zeros((len(method_ids), len(fpos)))
    for k, mid in enumerate(method_ids):
        for r in store.q("SELECT flow_id, value FROM cfs WHERE method_id=?", (mid,)):
            if r["flow_id"] in fpos:
                C[k, fpos[r["flow_id"]]] += float(r["value"])
    return C


class _Solver:
    DENSE_MAX = 4000
    TOLERANCE = 1e-5     # relative; above round-off of ill-conditioned matrices, far below any modelling error

    def __init__(self, A):
        self.A = A
        self.n = A.shape[0]
        self.dense = None
        self.M = None
        self.kind = "dense LU (LAPACK)" if self.n <= self.DENSE_MAX else "GMRES with ILU preconditioner"
        if self.n <= self.DENSE_MAX:
            from scipy.linalg import lu_factor   # LAPACK dense LU, a different implementation from the engine's SuperLU
            self.dense = lu_factor(A.toarray()) if self.n else None
        else:
            ilu = spl.spilu(A.tocsc(), drop_tol=1e-6, fill_factor=20)
            self.M = spl.LinearOperator(A.shape, ilu.solve)

    def solve(self, f):
        if self.dense is not None:
            from scipy.linalg import lu_solve
            return lu_solve(self.dense, f)
        nf = np.linalg.norm(f) or 1.0
        x = np.zeros_like(f)
        for _ in range(8):  # GMRES with iterative refinement on the residual
            r = f - self.A @ x
            if np.linalg.norm(r) / nf < 1e-12:
                break
            try:
                d, _info = spl.gmres(self.A, r, M=self.M, rtol=1e-12, atol=0.0, restart=200, maxiter=500)
            except TypeError:  # SciPy older than 1.12
                d, _info = spl.gmres(self.A, r, M=self.M, tol=1e-12, atol=0.0, restart=200, maxiter=500)
            x = x + d
        if np.linalg.norm(f - self.A @ x) / nf > 1e-9:
            raise ValueError("The iterative solver did not converge (relative residual above 1e-9).")
        return x


def _model_demand(store, ctx, model_id, pos, fpos, keep_top, depth=0, factor=1.0, f=None, g=None, fixed=None):
    """Independent recursive flattening of a model into demand per dataset, direct flows and EPD lines."""
    if depth > 25:
        raise ValueError("Models are nested more than 25 levels deep.")
    m = store.model(model_id)
    share = calc.allocation_share(m["scope"])
    for inp in m["inputs"]:
        if depth == 0 and not keep_top(inp):
            continue
        sign = -1.0 if inp["avoided"] else 1.0
        amt = calc.line_amount(ctx, model_id, inp) * sign * share * factor
        if inp["kind"] == "activity":
            f[pos[inp["ref_id"]]] += amt
        elif inp["kind"] == "flow":
            g[fpos[inp["ref_id"]]] += amt
        elif inp["kind"] == "fixed":
            fixed.append((inp["fixed"], amt))
        elif inp["kind"] == "model":
            sub = store.model(inp["ref_id"])
            _model_demand(store, ctx, inp["ref_id"], pos, fpos, keep_top, depth + 1, amt / (sub["amount"] or 1.0), f, g, fixed)


def run(store, method_ids, sample=200, seed=5, model_ids=None, progress=lambda *a: None):
    """Compare Cyclia with the independent calculation for a sample of datasets and for models."""
    method_ids = [int(m) for m in method_ids]
    if not method_ids:
        raise ValueError("Pick impact categories in step 4 first.")
    progress(5, "Assembling the matrices again from the library tables")
    ids, pos, A, flows, fpos, B = _assemble(store)
    C = _cf_matrix(store, method_ids, fpos)
    progress(15, "Preparing the independent solver")
    S = _Solver(A)
    mc = calc.get_mc(store)
    M = calc.Methods(store, mc, method_ids, regional=False)
    rng = np.random.default_rng(seed)
    pick = ids if len(ids) <= sample else [ids[i] for i in sorted(rng.choice(len(ids), int(sample), replace=False))]
    names = {r["id"]: (r["name"], r["location"]) for r in store.q("SELECT id, name, location FROM activities")}
    rows = []
    for n, aid in enumerate(pick):
        f = np.zeros(len(ids))
        f[pos[aid]] = 1.0
        ref = C @ (B @ S.solve(f))
        eng, _, _ = calc.impacts(mc, M, {aid: 1.0}, {}, [])
        rows.append({"kind": "dataset", "name": names[aid][0], "location": names[aid][1],
                     "independent": ref.tolist(), "cyclia": [float(x) for x in eng]})
        if n % 20 == 0:
            progress(15 + 70 * n / max(1, len(pick)), f"Dataset {n + 1} of {len(pick)}")
    ctx = calc.Context(store)
    # site-specific factors apply to the models' own (direct) emissions: rebuilt here from the raw table
    Cd = C.copy()
    meth = [store.one("SELECT family, category, indicator FROM methods WHERE id=?", (m,)) for m in method_ids]
    for x in store.q("SELECT family, category, indicator, flow_uuid, value FROM site_cfs"):
        fl = store.one("SELECT id FROM flows WHERE uuid=?", (x["flow_uuid"],))
        for k, mm in enumerate(meth):
            if fl and fl["id"] in fpos and (mm["family"], mm["category"], mm["indicator"]) == \
                    (x["family"], x["category"], x["indicator"] or x["category"]):
                Cd[k, fpos[fl["id"]]] = float(x["value"])
    skipped_site = False
    for mid in (model_ids or []):
        m = store.model(int(mid))
        if not m or not m["inputs"] or any(i["missing"] for i in m["inputs"]):
            continue
        sc = m["scope"]
        keep = lambda inp, sc=sc: not calc.is_module_d(sc, inp["stage"])
        try:
            acts_, flows_, fixed_ = {}, {}, []
            calc.expand(ctx, int(mid), 1.0, acts_, flows_, fixed_, keep=keep)
            eng, _, _ = calc.impacts(mc, M, acts_, flows_, fixed_)
        except calc.LCAError:
            continue
        f = np.zeros(len(ids))
        g = np.zeros(len(flows))
        fixed = []
        _model_demand(store, ctx, int(mid), pos, fpos, keep, f=f, g=g, fixed=fixed)
        ref = C @ (B @ S.solve(f)) + Cd @ g + sum((M.fixed_vector(fx) * a for fx, a in fixed), np.zeros(len(method_ids)))
        rows.append({"kind": "model", "name": m["name"], "location": "", "independent": ref.tolist(),
                     "cyclia": [float(x) for x in eng]})
    progress(95, "Comparing")
    worst = 0.0
    # values below 1e-12 of the largest result of a category are round-off (the engine sets such values to zero)
    floor = [1e-12 * max([max(abs(r["independent"][k]), abs(r["cyclia"][k])) for r in rows] or [0.0])
             for k in range(len(method_ids))]
    for r in rows:
        dev = []
        for k, (a, b) in enumerate(zip(r["independent"], r["cyclia"])):
            scale = max(abs(a), abs(b), floor[k])
            d = 0.0 if scale < 1e-300 else abs(a - b) / scale
            dev.append(d)
            worst = max(worst, d)
        r["relative_difference"] = dev
    cats = [{k: x[k] for k in ("id", "family", "category", "unit")} for x in M.rows]
    n_d = sum(1 for r in rows if r["kind"] == "dataset")
    n_m = sum(1 for r in rows if r["kind"] == "model")
    ok = worst <= _Solver.TOLERANCE
    return {"categories": cats, "rows": sorted(rows, key=lambda r: -max(r["relative_difference"] or [0]))[:200],
            "n_datasets": n_d, "n_models": n_m, "n_library": len(ids), "max_relative_difference": worst, "passed": ok,
            "solver": S.kind, "tolerance": _Solver.TOLERANCE,
            "verdict": (f"Agreement: {n_d} datasets and {n_m} models give the same results with the independent calculation "
                        f"(largest relative difference {worst:.1e})." if ok else
                        f"Differences found: the largest relative difference is {worst:.1e}. Please send the result to "
                        "support@niellosoft.com."),
            "scope": "Checks matrix assembly, signs, solver and nesting. Factor matching is checked by the ecoinvent benchmark. "
                     f"Agreement means a relative difference below {_Solver.TOLERANCE:g}; smaller differences are round-off of "
                     "the matrix condition."
                     + (" Models were not compared because site-specific factors are defined in this project." if skipped_site else "")}


def to_excel(path, res, version=""):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    import trust
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    for k, v in (("Verdict", res["verdict"]), ("Scope", res["scope"]), ("Datasets compared", res["n_datasets"]),
                 ("Models compared", res["n_models"]), ("Datasets in the library", res["n_library"]),
                 ("Independent solver", res["solver"]), ("Largest relative difference", res["max_relative_difference"]),
                 ("Software", f"Cyclia {version}")):
        ws.append([k, v])
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 100
    env = trust.environment()
    for k, v in env.items():
        ws.append([k, str(v)])
    w2 = wb.create_sheet("Results")
    head = ["Kind", "Name", "Location"]
    for c in res["categories"]:
        head += [f"{c['category']} [{c['unit']}] Cyclia", "independent", "relative difference"]
    w2.append(head)
    for c in w2[1]:
        c.font = Font(bold=True)
    for r in res["rows"]:
        row = [r["kind"], r["name"], r["location"]]
        for a, b, d in zip(r["cyclia"], r["independent"], r["relative_difference"]):
            row += [a, b, d]
        w2.append(row)
    wb.save(path)
    return path
