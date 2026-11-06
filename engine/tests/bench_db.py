"""A synthetic database with the structure of a large LCA database, for comparisons with other software.

Markets that mix suppliers of several locations, supply loops, waste treatment with negative production,
infrastructure entering with very small amounts (1e-9 to 1e-13 per unit), recycling credits (negative inputs) and
elementary flows of every compartment. The numbers are random (fixed seed) and describe no real product."""
import numpy as np

from importers import other_formats


def synthetic_database(store, n=2000, flows=300, methods=8, seed=3, name="Synthetic benchmark database"):
    rng = np.random.default_rng(seed)
    b = other_formats._Builder(store, name, "synthetic", version="1", system_model="synthetic")
    kinds = rng.choice(["process", "market", "waste", "infrastructure"], size=n, p=[0.6, 0.2, 0.1, 0.1])
    idx = []
    for i in range(n):
        k = kinds[i]
        prod = -1.0 if k == "waste" else float(rng.choice([1.0, 1.0, 0.5, 2.0, 1000.0]))
        idx.append(b.activity(f"k{i}", f"{k} {i}", f"product {i}", ["GLO", "RER", "CH", "CN", "US"][i % 5],
                              "unit" if k == "infrastructure" else "kg", production=prod))
    comps = [("air", "unspecified"), ("air", "urban air close to ground"), ("water", "surface water"),
             ("soil", "agricultural"), ("natural resource", "in ground"), ("natural resource", "land")]
    fl = [(f"u{j}", f"flow {j}") + comps[j % len(comps)] + ("kg",) for j in range(flows)]
    for i in range(n):
        k = kinds[i]
        n_in = int(rng.integers(3, 8)) if k == "market" else int(rng.integers(1, 6))
        for s in rng.choice(n, size=n_in, replace=False):
            s = int(s)
            if kinds[s] == "infrastructure":
                amt = float(10 ** rng.uniform(-13, -9))
            elif kinds[s] == "waste":
                amt = -float(rng.uniform(0.01, 0.5))   # waste sent to treatment: negative input
            else:
                amt = float(rng.uniform(0.001, 0.3)) * (1 if rng.random() > 0.05 else -1)   # some recycling credits
            b.input(idx[i], f"product {s}", "kg", amt, link=idx[s])
        if k != "market":
            for j in rng.choice(flows, size=int(rng.integers(2, 12)), replace=False):
                u, nm, c, sc, un = fl[int(j)]
                b.emission(idx[i], u, nm, c, sc, un, float(10 ** rng.uniform(-6, 1)))
    b.write(lambda *a: None)
    fids = {r["uuid"]: r["id"] for r in store.q("SELECT id, uuid FROM flows")}
    mids = []
    with store.lock:
        for m in range(methods):
            cur = store.conn.execute("INSERT INTO lib.methods(family,category,indicator,unit,source,note) VALUES(?,?,?,?,?,?)",
                                     ("Synthetic method", f"category {m}", "indicator", "units", "synthetic", ""))
            mids.append(cur.lastrowid)
            chosen = rng.choice(flows, size=flows // 3, replace=False)
            store.conn.executemany("INSERT INTO lib.cfs(method_id, flow_id, value) VALUES(?,?,?)",
                                   [(cur.lastrowid, fids[fl[int(j)][0]], float(rng.uniform(-2, 50))) for j in chosen])
        store.conn.commit()
    calc.invalidate()
    return {"datasets": n, "flows": flows, "method_ids": mids}


import calc  # noqa: E402
