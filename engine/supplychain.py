"""Supply chain of a dataset as a tree of its suppliers, with the share of each in one impact category (Cyclia 1.10).

For category k, y = A^-T q_k (one transposed solve) gives y_i, the result of one unit of the product of every dataset
i. A node j delivering P units of its product has the scaling s_j = P / a_jj, its own direct contribution s_j q_kj and,
for each input i of amount t_ij per scaling unit, a supplier node with P_i = s_j t_ij units and the result P_i y_i.
These parts add up to the node's result P y_j, so every level of the tree is exact; the tree shows the largest
suppliers and gathers the rest. A loop in the supply chain (a dataset that is its own supplier further up) is not
expanded again.
"""
import numpy as np
import scipy.sparse as sp

import calc
import numcheck


def supply_chain(store, act_id, method_id, depth=3, top=5, min_share=0.005, amount=1.0):
    act_id = numcheck.identifier(act_id, "The dataset")
    method_id = numcheck.identifier(method_id, "The impact category")
    depth = numcheck.integer(depth, "The depth", 1, 8)
    top = numcheck.integer(top, "The number of suppliers per level", 1, 30)
    min_share = numcheck.finite(min_share, "The smallest share shown", 0, 1)
    mc = calc._cache.get(store)
    if act_id not in mc.act_index:
        raise ValueError("That dataset is not in the library.")
    m = store.one("SELECT * FROM methods WHERE id=?", (method_id,))
    if not m:
        raise ValueError("That impact category does not exist.")
    M = calc.Methods(store, mc, [method_id])
    q = np.asarray(M.Q[0]).ravel()
    y = calc.solve_transposed(mc, q)
    T = sp.csc_matrix((mc.t_amt, (mc.t_rows, mc.t_cols)), shape=(mc.n, mc.n))
    T.sum_duplicates()
    info = {}

    def about(i):
        if i not in info:
            a = store.one("SELECT name, location, unit, product FROM activities WHERE id=?", (int(mc.act_ids[i]),)) or {}
            info[i] = a
        return info[i]

    root = mc.act_index[act_id]
    total = float(amount * y[root])
    scale = abs(total) or max(abs(float(amount * y[root])), 1e-300)

    def node(i, prod, level, path):
        a = about(i)
        s = prod / mc.diag[i]
        res = float(prod * y[i])
        out = {"id": int(mc.act_ids[i]), "name": a.get("name"), "location": a.get("location"),
               "product": a.get("product"), "unit": a.get("unit"), "amount": float(prod), "result": res,
               "share": res / scale if scale else 0.0, "direct": float(s * q[i]), "children": [], "rest": 0.0,
               "loop": False}
        if level >= depth:
            return out
        col = T[:, i]
        kids = [(float(s * t * y[r]), int(r), float(s * t)) for r, t in zip(col.indices, col.data) if t]
        kids.sort(key=lambda k: -abs(k[0]))
        shown = 0
        for c, r, p in kids:
            if shown < top and abs(c) >= min_share * scale:
                if r in path:
                    sub = about(r)
                    out["children"].append({"id": int(mc.act_ids[r]), "name": sub.get("name"),
                                            "location": sub.get("location"), "unit": sub.get("unit"), "amount": p,
                                            "result": c, "share": c / scale, "direct": None, "children": [],
                                            "rest": 0.0, "loop": True})
                else:
                    out["children"].append(node(r, p, level + 1, path | {r}))
                shown += 1
            else:
                out["rest"] += c
        return out

    tree = node(root, float(amount), 0, {root})
    return {"method": {k: m[k] for k in ("id", "family", "category", "indicator", "unit")}, "total": total,
            "depth": depth, "top": top, "tree": tree,
            "note": "Each node: its result for the amount it delivers, its own direct part, its largest suppliers, and "
                    "the rest of its suppliers together. The parts of a node add up to its result."}
