"""Independent check of the kit's data with numpy and scipy only (no LCA software): builds A = diag(production) -
technosphere inputs, B (biosphere) and C (factors) from data/, solves A s = e_j for every dataset and writes
results_matrices.csv in the same layout as cyclia_results.csv.

    python check_matrices.py
"""
import csv
import os

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl

HERE = os.path.dirname(os.path.abspath(__file__))


def rows(name):
    with open(os.path.join(HERE, "data", name), encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


acts = rows("activities.csv")
idx = {a["key"]: i for i, a in enumerate(acts)}
n = len(acts)
A = sp.lil_matrix((n, n))
for i, a in enumerate(acts):
    A[i, i] = float(a["production"] or 1.0)
for t in rows("technosphere.csv"):
    A[idx[t["supplier_key"]], idx[t["consumer_key"]]] -= float(t["amount"])
flows = rows("flows.csv")
fidx = {f["uuid"]: i for i, f in enumerate(flows)}
B = sp.lil_matrix((len(flows), n))
for b in rows("biosphere.csv"):
    B[fidx[b["flow_uuid"]], idx[b["activity_key"]]] += float(b["amount"])
methods = rows("methods.csv")
mk = [(m["category"], m["indicator"]) for m in methods]
C = np.zeros((len(mk), len(flows)))
for f in rows("factors.csv"):
    C[mk.index((f["category"], f["indicator"])), fidx[f["flow_uuid"]]] = float(f["cf"])
lu = spl.splu(A.tocsc())
B = B.tocsr()
with open(os.path.join(HERE, "results_matrices.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["key", "name", "location", "category", "indicator", "value"])
    for j, a in enumerate(acts):
        e = np.zeros(n)
        e[j] = 1.0
        h = C @ (B @ lu.solve(e))
        for (cat, ind), v in zip(mk, h):
            w.writerow([a["key"], a["name"], a["location"], cat, ind, repr(float(v))])
print(f"results_matrices.csv: {n} datasets x {len(mk)} categories")
