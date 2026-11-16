"""Full-library regression (Cyclia 1.9.0): every dataset under every impact category, every model, and the factor
matching of every category, recorded once and compared later.

A snapshot holds:
- for each impact category: the number of factors as given by the method file, the number of library flows they were
  matched to, the number of elementary flows with exchanges in the library that have no factor (uncharacterised), and
  a fingerprint of the matched factors (flow and value), so a change in matching shows even when the counts agree;
- for each dataset (database and dataset key): its score for one unit of its reference product in every category,
  from the full supply chain, computed as h = Q A^-1 by one transposed solve per category (A^T y = q^T), which gives
  every dataset at once;
- for each model of the project: the result in every category (calc.run, the path the user sees).

compare() reports what was added or removed and every value whose difference exceeds the tolerance
|a - b| <= rtol * max(|a|, |b|) + atol, where atol is a small share of the largest score of the category, so values that
are zero up to round-off do not fail.

The snapshot of the reference libraries shipped with Cyclia (tutorial, demo with its project, built-in methods) is
committed in tests/data and checked by the test suite; for an installed library (ecoinvent with its methods, which
cannot be distributed) the user records a snapshot with engine/tools/regression.py and compares later versions with it.
"""
import datetime as _dt
import gzip
import hashlib
import json
import math

import numpy as np
import scipy.sparse as sp

import calc

FORMAT = "cyclia-regression"
FORMAT_VERSION = 1


def _version():
    """The version in server.py, without importing the server."""
    import os
    import re
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py"), encoding="utf-8") as fh:
            m = re.search(r'^VERSION = "([^"]+)"', fh.read(), re.M)
        return m.group(1) if m else ""
    except OSError:
        return ""


def _key(m):
    return f"{m['family']} | {m['category']} | {m['indicator'] or m['category']}"


def _round(x):
    """17 significant digits: a float written and read back is the same float."""
    return float(f"{x:.17g}")


def _matching(store, method_ids, mc):
    """Factor matching of each category."""
    used = set(mc.flow_ids[i] for i in np.unique(mc.B.tocoo().row)) if mc.n and mc.B.nnz else set()
    out = {}
    for mid in method_ids:
        m = store.one("SELECT * FROM methods WHERE id=?", (mid,))
        raw = store.one("SELECT COUNT(*) n FROM cf_raw WHERE method_id=?", (mid,))["n"]
        rows = store.q("SELECT f.uuid, c.flow_id, c.value FROM cfs c JOIN flows f ON f.id=c.flow_id WHERE c.method_id=? "
                       "ORDER BY f.uuid", (mid,))
        h = hashlib.sha256()
        for r in rows:
            h.update(f"{r['uuid']}={_round(r['value']) if r['value'] is not None else 'NULL'};".encode())
        reg = store.one("SELECT COUNT(*) n FROM cfs_regional WHERE method_id=?", (mid,))["n"]
        out[_key(m)] = {"unit": m["unit"] or "", "factors_given": raw, "flows_matched": len(rows),
                        "regional_factors": reg,
                        "used_flows_without_factor": len(used - {r["flow_id"] for r in rows}),
                        "fingerprint": h.hexdigest()[:20]}
    return out


def dataset_scores(store, method_ids, mc=None, db_ids=None):
    """{(database, key): (name, location, product, unit, [score per category])} for one unit of every dataset."""
    mc = mc or calc._cache.get(store)
    M = calc.Methods(store, mc, method_ids)
    if not mc.n:
        return {}, M
    acts = store.q("SELECT a.id, a.key, a.name, a.location, a.product, a.unit, d.name db FROM activities a "
                   "JOIN databases d ON d.id=a.db_id" + (f" WHERE a.db_id IN ({','.join('?' * len(db_ids))})"
                                                        if db_ids else ""), list(db_ids or []))
    Y = np.vstack([mc.lu.solve(np.ascontiguousarray(M.Q[i], dtype=float), trans="T") for i in range(len(M.ids))]) \
        if len(M.ids) else np.zeros((0, mc.n))
    if not np.isfinite(Y).all():
        raise calc.LCAError("The scores of the datasets are not finite numbers. Run 'Check database' in step 1.")
    # as in calc.solve: a dataset whose supply chain reaches no characterised exchange scores exactly zero (the
    # transposed solve can leave round-off of about 1e-17 there)
    # rows of the exchange pattern are suppliers, columns their users: a user reaches what its suppliers reach
    PT = sp.csr_matrix((np.ones(len(mc.t_rows), dtype=np.int32), (mc.t_cols, mc.t_rows)), shape=(mc.n, mc.n))
    for i in range(Y.shape[0]):
        r = M.Q[i] != 0
        while True:
            nr = r | (PT @ r.astype(np.int32) > 0)
            if np.array_equal(nr, r):
                break
            r = nr
        Y[i, ~r] = 0.0
    out = {}
    for a in acts:
        j = mc.act_index.get(a["id"])
        if j is None:
            continue
        out[(a["db"], a["key"])] = (a["name"], a["location"] or "", a["product"] or "", a["unit"] or "",
                                    [_round(v) for v in Y[:, j]])
    return out, M


def snapshot(store, method_ids=None, db_ids=None, models=True, label="", progress=lambda *a: None):
    """A regression snapshot of the open project (see the module text)."""
    import trust
    mc = calc._cache.get(store)
    if method_ids is None:
        method_ids = [r["id"] for r in store.q("SELECT id FROM methods ORDER BY family, category, indicator")]
    method_ids = [int(m) for m in method_ids]
    progress(5, "Factor matching")
    matching = _matching(store, method_ids, mc)
    progress(20, "Dataset scores")
    scores, M = dataset_scores(store, method_ids, mc, db_ids)
    keys = [_key(m) for m in M.rows]
    datasets = {f"{db} | {k}": {"name": v[0], "location": v[1], "product": v[2], "unit": v[3],
                                "scores": dict(zip(keys, v[4]))} for (db, k), v in sorted(scores.items())}
    res_models = {}
    if models:
        ms = store.models()
        for i, m in enumerate(ms):
            progress(60 + 35 * i / max(1, len(ms)), f"Model {m['name']}")
            try:
                r = calc.run(store, m["id"], method_ids, top=1)
            except calc.LCAError as e:
                res_models[m["name"]] = {"error": str(e)}
                continue
            res_models[m["name"]] = {_key(x): _round(x["total"]) for x in r["results"]}
    dbs = [{"name": d["name"], "version": d.get("version") or "", "system_model": d.get("system_model") or "",
            "activities": d.get("n_activities")} for d in store.databases()
           if not db_ids or d["id"] in db_ids]
    return {"format": FORMAT, "format_version": FORMAT_VERSION, "label": label,
            "created": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            "software": dict(trust.environment(), cyclia=trust.APP_VERSION or _version()),
            "library": {"databases": dbs, "datasets": int(mc.n), "elementary_flows": len(mc.flow_ids),
                        "technosphere_exchanges": int(mc.A.nnz),
                        "categories": len(method_ids)},
            "matching": matching, "datasets": datasets, "models": res_models}


def save(snap, path):
    data = json.dumps(snap, indent=1, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    if path.endswith(".gz"):
        with open(path, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as fh:
            fh.write(data)
    else:
        with open(path, "wb") as fh:
            fh.write(data)


def load(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rb") as fh:
        snap = json.loads(fh.read().decode())
    if snap.get("format") != FORMAT:
        raise ValueError("This file is not a Cyclia regression snapshot.")
    if snap.get("format_version", 0) > FORMAT_VERSION:
        raise ValueError("This snapshot was written by a later version of Cyclia.")
    return snap


def _close(a, b, rtol, atol):
    return abs(a - b) <= rtol * max(abs(a), abs(b)) + atol


def compare(ref, new, rtol=1e-9, atol_share=1e-12, limit=50):
    """Differences between two snapshots. Returns a report with "passed" (bool), counts and the largest differences."""
    rep = {"rtol": rtol, "atol_share": atol_share, "reference": ref.get("label") or ref.get("created"),
           "new": new.get("label") or new.get("created"), "matching": [], "datasets_missing": [], "datasets_added": [],
           "categories_missing": [], "categories_added": [], "values_compared": 0, "values_different": 0,
           "differences": [], "models": [], "models_missing": []}
    rm, nm = ref.get("matching", {}), new.get("matching", {})
    rep["categories_missing"] = sorted(set(rm) - set(nm))
    rep["categories_added"] = sorted(set(nm) - set(rm))
    for k in sorted(set(rm) & set(nm)):
        a, b = rm[k], nm[k]
        ch = {f: (a.get(f), b.get(f)) for f in ("factors_given", "flows_matched", "regional_factors",
                                                 "used_flows_without_factor", "fingerprint") if a.get(f) != b.get(f)}
        if ch:
            rep["matching"].append({"category": k, "changes": ch})
    rd, nd = ref.get("datasets", {}), new.get("datasets", {})
    rep["datasets_missing"] = sorted(set(rd) - set(nd))[:limit]
    rep["n_datasets_missing"] = len(set(rd) - set(nd))
    rep["datasets_added"] = sorted(set(nd) - set(rd))[:limit]
    rep["n_datasets_added"] = len(set(nd) - set(rd))
    cats = sorted(set(rm) & set(nm)) if rm and nm else sorted({c for d in rd.values() for c in d["scores"]})
    scale = {}
    for c in cats:
        vals = [abs(d["scores"][c]) for d in rd.values() if c in d["scores"]]
        scale[c] = max(vals) if vals else 0.0
    diffs = []
    for k in set(rd) & set(nd):
        for c in cats:
            a, b = rd[k]["scores"].get(c), nd[k]["scores"].get(c)
            if a is None or b is None:
                continue
            rep["values_compared"] += 1
            if not (math.isfinite(b) and _close(a, b, rtol, atol_share * scale[c])):
                rep["values_different"] += 1
                rel = (b - a) / abs(a) * 100 if a else None
                diffs.append({"dataset": k, "category": c, "reference": a, "new": b, "change_percent": rel,
                              "_order": abs(b - a) / (scale[c] or 1.0)})
    diffs.sort(key=lambda d: -d["_order"])
    for d in diffs[:limit]:
        d.pop("_order")
    rep["differences"] = diffs[:limit]
    rmod, nmod = ref.get("models", {}), new.get("models", {})
    rep["models_missing"] = sorted(set(rmod) - set(nmod))
    for name in sorted(set(rmod) & set(nmod)):
        a, b = rmod[name], nmod[name]
        if "error" in a or "error" in b:
            if a.get("error") != b.get("error"):
                rep["models"].append({"model": name, "reference": a.get("error", "result"),
                                      "new": b.get("error", "result")})
            continue
        for c in sorted(set(a) & set(b)):
            rep["values_compared"] += 1
            if not _close(a[c], b[c], rtol, atol_share * max(abs(a[c]), 1e-300)):
                rep["values_different"] += 1
                rep["models"].append({"model": name, "category": c, "reference": a[c], "new": b[c],
                                      "change_percent": (b[c] - a[c]) / abs(a[c]) * 100 if a[c] else None})
    rep["passed"] = not (rep["matching"] or rep["n_datasets_missing"] or rep["categories_missing"]
                         or rep["values_different"] or rep["models_missing"] or rep["models"])
    return rep


def report_text(rep):
    """A plain-text summary of compare()."""
    lines = [f"Regression: {'PASSED' if rep['passed'] else 'DIFFERENCES FOUND'}",
             f"Reference: {rep['reference']}   New: {rep['new']}",
             f"Values compared: {rep['values_compared']}, outside tolerance: {rep['values_different']} "
             f"(relative {rep['rtol']:g}, absolute {rep['atol_share']:g} x largest score of the category)"]
    if rep["categories_missing"]:
        lines.append("Categories missing: " + "; ".join(rep["categories_missing"]))
    if rep["categories_added"]:
        lines.append("Categories added (not compared): " + "; ".join(rep["categories_added"]))
    if rep["n_datasets_missing"]:
        lines.append(f"Datasets missing: {rep['n_datasets_missing']} (e.g. {', '.join(rep['datasets_missing'][:3])})")
    if rep["n_datasets_added"]:
        lines.append(f"Datasets added (not compared): {rep['n_datasets_added']}")
    for m in rep["matching"]:
        lines.append(f"Factor matching changed, {m['category']}: "
                     + ", ".join(f"{f} {a} -> {b}" for f, (a, b) in m["changes"].items()))
    for d in rep["differences"]:
        pc = f"{d['change_percent']:+.6g} %" if d["change_percent"] is not None else "from zero"
        lines.append(f"  {d['dataset']} / {d['category']}: {d['reference']:.10g} -> {d['new']:.10g} ({pc})")
    for m in rep["models"]:
        if "category" in m:
            lines.append(f"  model {m['model']} / {m['category']}: {m['reference']:.10g} -> {m['new']:.10g}")
        else:
            lines.append(f"  model {m['model']}: {m['reference']} -> {m['new']}")
    return "\n".join(lines)


def build_reference(store, progress=lambda *a: None):
    """The reference libraries shipped with Cyclia, in an empty project: the tutorial database, the demo database with
    its project (models of every kind) and the built-in methods. Their snapshot is tests/data/reference_regression."""
    from importers import demo, tutorial
    tutorial.install(store)
    demo.install_database(store)
    demo.build_project(store, author="Regression")
    calc.invalidate()
