"""Comparison of Cyclia's results with Brightway's calculation library (bw2calc), inside the app.

Brightway builds its own technosphere, biosphere and characterisation matrices from the exchange lists of the
database (bw_processing datapackages, technosphere inputs flipped as Brightway does), solves them with its own
solver and characterises with its own matrix product. Cyclia's result for the same dataset and category is then
compared. Only the exchange lists and the matched factors are shared, so the comparison checks matrix assembly,
signs, production amounts, the solve and the characterisation step against an independent, widely used program.

It does not check the import or the factor matching (both programs use what Cyclia imported); those are checked by
the ecoinvent benchmark and the factor matching validation.

Brightway is optional: when bw2calc and bw_processing are not installed, available() is False and the tool says so.
"""
import numpy as np

import calc
import compare_kit

TOL = 1e-6   # relative difference below which two results agree
FLOW0 = 10 ** 9


def available():
    try:
        import bw2calc  # noqa: F401
        import bw_processing  # noqa: F401
        return True
    except Exception:
        return False


def versions():
    import bw2calc
    import bw_processing
    return {"bw2calc": str(bw2calc.__version__ if not isinstance(bw2calc.__version__, tuple)
                           else ".".join(map(str, bw2calc.__version__))),
            "bw_processing": str(bw_processing.__version__ if not isinstance(bw_processing.__version__, tuple)
                                 else ".".join(map(str, bw_processing.__version__)))}


def _unit(a):
    return -1.0 if float(a["production"] or 1.0) < 0 else 1.0


def _packages(acts, tech, bio, cfs_by_method):
    import bw_processing as bwp
    col = {a["id"]: i for i, a in enumerate(acts)}
    fl = sorted({b["flow_id"] for b in bio})
    frow = {f: FLOW0 + i for i, f in enumerate(fl)}
    ind = [(col[a["id"]], col[a["id"]]) for a in acts] + [(col[t["input_id"]], col[t["output_id"]]) for t in tech]
    dat = [float(a["production"] or 1.0) for a in acts] + [float(t["amount"]) for t in tech]
    flip = [False] * len(acts) + [True] * len(tech)
    inv = bwp.create_datapackage(sum_intra_duplicates=True, sum_inter_duplicates=False)
    inv.add_persistent_vector(matrix="technosphere_matrix", name="technosphere",
                              indices_array=np.array(ind, dtype=bwp.INDICES_DTYPE), data_array=np.array(dat, dtype=float),
                              flip_array=np.array(flip, dtype=bool))
    inv.add_persistent_vector(matrix="biosphere_matrix", name="biosphere",
                              indices_array=np.array([(frow[b["flow_id"]], col[b["activity_id"]]) for b in bio],
                                                     dtype=bwp.INDICES_DTYPE),
                              data_array=np.array([float(b["amount"]) for b in bio], dtype=float))
    meth = {}
    for mid, cf in cfs_by_method.items():
        items = [(frow[f], v) for f, v in cf.items() if f in frow]
        if not items:
            meth[mid] = None
            continue
        dp = bwp.create_datapackage(sum_intra_duplicates=True, sum_inter_duplicates=False)
        dp.add_persistent_vector(matrix="characterization_matrix", name="characterization", global_index=0,
                                 indices_array=np.array([(r, 0) for r, _ in items], dtype=bwp.INDICES_DTYPE),
                                 data_array=np.array([v for _, v in items], dtype=float))
        meth[mid] = dp
    return inv, meth, col


def compare(store, db_id, method_ids, sample=0, seed=7, progress=lambda *a: None):
    """Results of `sample` datasets (all when 0) of one database, in Cyclia and in Brightway."""
    if not available():
        raise ValueError("Brightway (bw2calc) is not available in this installation.")
    import bw2calc as bc
    acts, tech, bio, flows, methods, cfs = compare_kit.collect(store, int(db_id), method_ids)
    picks = list(range(len(acts)))
    if sample and sample < len(acts):
        picks = sorted(np.random.default_rng(seed).choice(len(acts), size=int(sample), replace=False).tolist())
    progress(10, "Building Brightway's matrices")
    inv, meth, col = _packages(acts, tech, bio, cfs)
    mc = calc.get_mc(store)
    M = calc.Methods(store, mc, [m["id"] for m in methods], regional=False)
    progress(20, "Calculating in Cyclia")
    cy = {}
    for i in picks:
        h, _, _ = calc.impacts(mc, M, {acts[i]["id"]: 1.0}, {}, [])
        for m, v in zip(methods, h):
            cy[(i, m["id"])] = float(v)
    rows = []
    progress(30, "Calculating in Brightway")
    # one Brightway LCA for the inventory, factorised once; Brightway's characterisation matrix of every category
    # is built by a second LCA object on the same inventory datapackage (same biosphere mapping), and the score is
    # its product with Brightway's inventory, as LCA.lcia() does
    main = bc.LCA({col[acts[picks[0]]["id"]]: _unit(acts[picks[0]])}, data_objs=[inv])
    main.lci(factorize=True)
    cmats = {}
    for m in methods:
        dp = meth[m["id"]]
        if dp is None:
            cmats[m["id"]] = None
            continue
        lm = bc.LCA({col[acts[picks[0]]["id"]]: 1.0}, data_objs=[inv, dp])
        lm.load_lci_data()
        lm.load_lcia_data()
        if dict(lm.dicts.biosphere) != dict(main.dicts.biosphere):
            raise ValueError("Brightway built two different biosphere mappings for the same database.")
        cmats[m["id"]] = lm.characterization_matrix
    for n_, i in enumerate(picks):
        # one unit of the reference product; for a treatment dataset (negative production) one unit of waste
        # treated, which in Brightway is a demand of -1 (Cyclia's convention, calc.demand_vector)
        main.lci(demand={col[acts[i]["id"]]: _unit(acts[i])})
        for m in methods:
            C = cmats[m["id"]]
            b = 0.0 if C is None else float((C @ main.inventory).sum())
            rows.append((i, m, cy[(i, m["id"])], b))
        if n_ % 20 == 0:
            progress(30 + 65 * n_ / max(1, len(picks)), f"Calculating in Brightway: dataset {n_ + 1:,} of {len(picks):,}")
    # relative difference; results that cancel to about zero are measured against 1e-9 of the category's largest
    floor = {}
    for i, m, a, b in rows:
        floor[m["id"]] = max(floor.get(m["id"], 0.0), abs(a), abs(b))
    out, cats = [], {}
    for i, m, a, b in rows:
        scale = max(abs(a), abs(b), 1e-9 * floor[m["id"]])
        d = 0.0 if scale == 0 else abs(a - b) / scale
        out.append({"key": acts[i]["key"], "dataset": acts[i]["name"], "location": acts[i]["location"],
                    "category": m["category"], "indicator": m["indicator"], "unit": m["unit"], "cyclia": a,
                    "brightway": b, "relative_difference": d})
        cats.setdefault(m["id"], {"category": m["category"], "indicator": m["indicator"], "unit": m["unit"], "d": []})["d"].append(d)
    by_cat = [{"category": c["category"], "indicator": c["indicator"], "unit": c["unit"], "results": len(c["d"]),
               "median": float(np.median(c["d"])), "max": float(np.max(c["d"])),
               "agree": int(sum(x < TOL for x in c["d"]))} for c in cats.values()]
    worst = max((r["relative_difference"] for r in out), default=0.0)
    n_ok = sum(r["relative_difference"] < TOL for r in out)
    db = store.one("SELECT name, version, system_model FROM databases WHERE id=?", (int(db_id),))
    v = versions()
    verdict = (f"Agreement: all {len(out):,} results of {len(picks):,} datasets and {len(methods)} categories agree with "
               f"Brightway (bw2calc {v['bw2calc']}) within {TOL:g} (largest relative difference {worst:.1e})."
               if n_ok == len(out) else
               f"{len(out) - n_ok:,} of {len(out):,} results differ from Brightway by more than {TOL:g} (largest relative "
               f"difference {worst:.1e}). The table lists them.")
    return {"verdict": verdict, "passed": n_ok == len(out), "database": db["name"], "database_version": db["version"],
            "system_model": db["system_model"], "datasets": len(picks), "datasets_in_database": len(acts),
            "categories": len(methods), "results": len(out), "max_relative_difference": worst, "tolerance": TOL,
            "brightway": v, "by_category": by_cat,
            "rows": sorted(out, key=lambda r: -r["relative_difference"])[:300],
            "scope": "Checks matrix assembly, signs, production amounts, solve and characterisation against Brightway. "
                     "Import and factor matching are checked by the ecoinvent benchmark and the factor matching validation."}


def excel(path, res):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    b = Font(bold=True)
    ws.append(["Cyclia compared with Brightway"])
    ws["A1"].font = b
    for k, v in (("Verdict", res["verdict"]), ("Database", res["database"]), ("Database version", res["database_version"]),
                 ("System model", res["system_model"]), ("Datasets compared", res["datasets"]),
                 ("Datasets in the database", res["datasets_in_database"]), ("Categories", res["categories"]),
                 ("Results compared", res["results"]), ("Largest relative difference", res["max_relative_difference"]),
                 ("Tolerance", res["tolerance"]), ("bw2calc", res["brightway"]["bw2calc"]),
                 ("bw_processing", res["brightway"]["bw_processing"]), ("Scope", res["scope"])):
        ws.append([k, v])
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 100
    w2 = wb.create_sheet("By category")
    w2.append(["Category", "Indicator", "Unit", "Results", "Agree", "Median relative difference", "Largest relative difference"])
    for c in res["by_category"]:
        w2.append([c["category"], c["indicator"], c["unit"], c["results"], c["agree"], c["median"], c["max"]])
    w3 = wb.create_sheet("Results")
    w3.append(["Dataset", "Location", "Key", "Category", "Indicator", "Unit", "Cyclia", "Brightway", "Relative difference"])
    for r in res["rows"]:
        w3.append([r["dataset"], r["location"], r["key"], r["category"], r["indicator"], r["unit"], r["cyclia"],
                   r["brightway"], r["relative_difference"]])
    for s in (w2, w3):
        for c in s[1]:
            c.font = b
    wb.save(path)
    return path
