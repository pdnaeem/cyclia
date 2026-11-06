"""Calculate the kit's database in Brightway and write results_brightway.csv.

    pip install bw2data bw2calc      (Brightway 2.5; Brightway 2.4 also works)
    python run_brightway.py

Builds a project 'cyclia-comparison' with the databases 'cyclia-biosphere' and 'cyclia-technosphere' and one method
per category, then calculates one unit of the reference product of every dataset (one unit of waste treated for treatment datasets,
a demand of -1 in Brightway because their production is negative). Technosphere exchanges are written
with the amounts of data/technosphere.csv (Brightway subtracts technosphere inputs, as Cyclia does) and production
with the dataset's production amount (negative for waste treatment).
"""
import csv
import os

import bw2calc as bc
import bw2data as bd

HERE = os.path.dirname(os.path.abspath(__file__))


def rows(name):
    with open(os.path.join(HERE, "data", name), encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


bd.projects.set_current("cyclia-comparison")
for name in ("cyclia-technosphere", "cyclia-biosphere"):
    if name in bd.databases:
        del bd.databases[name]
flows = rows("flows.csv")
bd.Database("cyclia-biosphere").write({("cyclia-biosphere", f["uuid"]): {
    "name": f["name"], "categories": tuple(x for x in (f["compartment"], f["subcompartment"]) if x),
    "unit": f["unit"], "type": "natural resource" if f["compartment"].lower().startswith("natural resource") else "emission"}
    for f in flows})
acts = rows("activities.csv")
ex = {a["key"]: [{"input": ("cyclia-technosphere", a["key"]), "amount": float(a["production"] or 1.0), "type": "production"}]
      for a in acts}
for t in rows("technosphere.csv"):
    ex[t["consumer_key"]].append({"input": ("cyclia-technosphere", t["supplier_key"]), "amount": float(t["amount"]),
                                  "type": "technosphere"})
for b in rows("biosphere.csv"):
    ex[b["activity_key"]].append({"input": ("cyclia-biosphere", b["flow_uuid"]), "amount": float(b["amount"]), "type": "biosphere"})
bd.Database("cyclia-technosphere").write({("cyclia-technosphere", a["key"]): {
    "name": a["name"], "reference product": a["product"], "location": a["location"] or "GLO", "unit": a["unit"],
    "exchanges": ex[a["key"]]} for a in acts})
methods = rows("methods.csv")
facs = rows("factors.csv")
mkeys = []
for m in methods:
    key = ("cyclia-comparison", m["category"], m["indicator"])
    bd.Method(key).write([(("cyclia-biosphere", f["flow_uuid"]), float(f["cf"])) for f in facs
                          if (f["category"], f["indicator"]) == (m["category"], m["indicator"])])
    mkeys.append((m, key))
db = bd.Database("cyclia-technosphere")
with open(os.path.join(HERE, "results_brightway.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["key", "name", "location", "category", "indicator", "value"])
    for a in acts:
        act = db.get(a["key"])
        # one unit of the reference product; for waste treatment (negative production) one unit treated = -1
        unit = -1 if float(a["production"] or 1.0) < 0 else 1
        for m, key in mkeys:
            try:   # Brightway 2.5
                fu, data_objs, _ = bd.prepare_lca_inputs({act: unit}, method=key)
                lca = bc.LCA(fu, data_objs=data_objs)
            except AttributeError:   # Brightway 2.4
                lca = bc.LCA({act: unit}, key)
            lca.lci()
            lca.lcia()
            w.writerow([a["key"], a["name"], a["location"], m["category"], m["indicator"], repr(float(lca.score))])
print("results_brightway.csv written. Next: python compare.py results_brightway.csv \"Brightway " + bc.__version__.__str__() + "\"")
