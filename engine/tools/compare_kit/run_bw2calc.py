"""Calculate the kit's database with Brightway's calculation library alone and write results_brightway.csv.

    pip install bw2calc bw_processing      (Brightway 2.5 calculation stack; no project or bw2data needed)
    python run_bw2calc.py

Brightway builds its own technosphere, biosphere and characterisation matrices from the kit's exchange lists
(bw_processing datapackages; technosphere inputs are flipped, as Brightway does for inputs), solves them with its
own solver and characterises with its own matrix product. Only the exchange lists come from Cyclia, so the result
checks Cyclia's matrix assembly, signs, solve and characterisation against Brightway's.
"""
import csv
import os
import sys

import numpy as np
import bw2calc as bc
import bw_processing as bwp

HERE = os.path.dirname(os.path.abspath(__file__))
FLOW0 = 10 ** 7   # flow indices start here, so they never collide with dataset indices


def rows(name):
    with open(os.path.join(HERE, "data", name), encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def inventory_package(acts, tech, bio, flow_index):
    idx = {a["key"]: i for i, a in enumerate(acts)}
    t_ind, t_dat, t_flip = [], [], []
    for a in acts:   # production on the diagonal (negative for waste treatment)
        t_ind.append((idx[a["key"]], idx[a["key"]]))
        t_dat.append(float(a["production"] or 1.0))
        t_flip.append(False)
    for t in tech:   # inputs: positive amounts, flipped by Brightway
        t_ind.append((idx[t["supplier_key"]], idx[t["consumer_key"]]))
        t_dat.append(float(t["amount"]))
        t_flip.append(True)
    dp = bwp.create_datapackage(sum_intra_duplicates=True, sum_inter_duplicates=False)
    dp.add_persistent_vector(matrix="technosphere_matrix", name="technosphere",
                             indices_array=np.array(t_ind, dtype=bwp.INDICES_DTYPE), data_array=np.array(t_dat),
                             flip_array=np.array(t_flip, dtype=bool))
    dp.add_persistent_vector(matrix="biosphere_matrix", name="biosphere",
                             indices_array=np.array([(flow_index[b["flow_uuid"]], idx[b["activity_key"]]) for b in bio],
                                                    dtype=bwp.INDICES_DTYPE),
                             data_array=np.array([float(b["amount"]) for b in bio]))
    return dp, idx


def method_package(facs, flow_index):
    dp = bwp.create_datapackage(sum_intra_duplicates=True, sum_inter_duplicates=False)
    dp.add_persistent_vector(matrix="characterization_matrix", name="characterization", global_index=0,
                             indices_array=np.array([(flow_index[f["flow_uuid"]], 0) for f in facs], dtype=bwp.INDICES_DTYPE),
                             data_array=np.array([float(f["cf"]) for f in facs]))
    return dp


def main():
    acts, tech, bio = rows("activities.csv"), rows("technosphere.csv"), rows("biosphere.csv")
    flows, methods, facs = rows("flows.csv"), rows("methods.csv"), rows("factors.csv")
    flow_index = {f["uuid"]: FLOW0 + i for i, f in enumerate(flows)}
    inv, idx = inventory_package(acts, tech, bio, flow_index)
    out = []
    for m in methods:
        mf = [f for f in facs if (f["category"], f["indicator"]) == (m["category"], m["indicator"])]
        if not mf:   # no factor for any flow of the database: every result is zero
            out += [(a["key"], a["name"], a["location"], m["category"], m["indicator"], 0.0) for a in acts]
            continue
        lca = bc.LCA({idx[acts[0]["key"]]: 1.0}, data_objs=[inv, method_package(mf, flow_index)])
        lca.lci()
        lca.lcia()
        for a in acts:
            # one unit of the reference product; for waste treatment (negative production) one unit treated = -1
            unit = -1.0 if float(a["production"] or 1.0) < 0 else 1.0
            lca.lci(demand={idx[a["key"]]: unit})
            lca.lcia()
            out.append((a["key"], a["name"], a["location"], m["category"], m["indicator"], float(lca.score)))
    with open(os.path.join(HERE, "results_brightway.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["key", "name", "location", "category", "indicator", "value"])
        for r in out:
            w.writerow(list(r[:5]) + [repr(r[5])])
    print(f"results_brightway.csv written with bw2calc {bc.__version__} and bw_processing {bwp.__version__}. "
          f'Next: python compare.py results_brightway.csv "Brightway (bw2calc {bc.__version__})"')


if __name__ == "__main__":
    sys.exit(main())
