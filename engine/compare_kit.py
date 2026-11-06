"""Comparison kit (Cyclia 1.3.7): everything needed to compare Cyclia with Brightway and openLCA on the same data.

The kit is a zip with:
- data/: the database and the impact method as plain tables (activities, technosphere, biosphere, flows, factors);
- openlca/database.zip: the same database and method as openLCA JSON-LD (unit groups, flow properties, flows,
  processes with default providers, impact method and categories);
- cyclia_results.csv: Cyclia's result of every dataset (one unit of its reference product) in every category;
- run_brightway.py: builds a Brightway project from data/ and writes results_brightway.csv (bw2data and bw2calc);
- run_openlca.py: calculates every process in openLCA 2 through its IPC server and writes results_openlca.csv;
- check_matrices.py: an independent numpy/scipy solve of data/ (no LCA software needed);
- compare.py: compares any results file with cyclia_results.csv and writes comparison_report.md and .csv;
- README.md: the steps.

Only export databases whose licence allows it (the tutorial or the demo database, your own data, free databases).
Never share a kit built from ecoinvent or another licensed database.
"""
import csv
import io
import json
import os
import uuid
import zipfile

import numpy as np

import calc

NS = uuid.UUID("6a1f0e5c-9d47-4c1e-9a54-0c7c1a5e1a36")


def _uid(*parts):
    return str(uuid.uuid5(NS, "|".join(str(p) for p in parts)))


def _csv(rows, header):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def collect(store, db_id, method_ids):
    acts = store.q("SELECT id, key, name, product, location, unit, production FROM activities WHERE db_id=? ORDER BY id", (db_id,))
    if not acts:
        raise ValueError("The database has no datasets.")
    ids = {a["id"] for a in acts}
    tech = store.q(f"SELECT t.output_id, t.input_id, t.amount FROM tech t JOIN activities a ON a.id=t.output_id WHERE a.db_id=?", (db_id,))
    outside = [t for t in tech if t["input_id"] not in ids]
    if outside:
        raise ValueError(f"{len(outside)} exchanges link to datasets of other databases. Build the kit from a database that "
                         "is complete on its own (or unlink those suppliers first).")
    bio = store.q("SELECT b.activity_id, b.flow_id, b.amount FROM bio b JOIN activities a ON a.id=b.activity_id WHERE a.db_id=?", (db_id,))
    fids = sorted({b["flow_id"] for b in bio})
    flows = {f["id"]: f for f in store.q(f"SELECT id, uuid, name, compartment, subcompartment, unit FROM flows WHERE id IN ({','.join(map(str, fids)) or '0'})")}
    methods = [store.one("SELECT id, family, category, indicator, unit FROM methods WHERE id=?", (int(m),)) for m in method_ids]
    if not methods or None in methods:
        raise ValueError("Pick the impact categories to compare in step 4.")
    cfs = {m["id"]: {r["flow_id"]: r["value"] for r in store.q("SELECT flow_id, value FROM cfs WHERE method_id=?", (m["id"],))
                     if r["flow_id"] in flows} for m in methods}
    return acts, tech, bio, flows, methods, cfs


def cyclia_results(store, acts, methods):
    mc = calc.get_mc(store)
    M = calc.Methods(store, mc, [m["id"] for m in methods], regional=False)
    rows = []
    for a in acts:
        h, _, _ = calc.impacts(mc, M, {a["id"]: 1.0}, {}, [])
        for m, v in zip(methods, h):
            rows.append((a["key"], a["name"], a["location"], m["category"], m["indicator"], float(v)))
    return rows


def _jsonld(acts, tech, bio, flows, methods, cfs):
    files = {}
    units = sorted({(a["unit"] or "unit") for a in acts} | {(f["unit"] or "unit") for f in flows.values()})
    ug, fp, un = {}, {}, {}
    for u in units:
        ug[u], fp[u], un[u] = _uid("ug", u), _uid("fp", u), _uid("unit", u)
        files[f"unit_groups/{ug[u]}.json"] = {"@type": "UnitGroup", "@id": ug[u], "name": f"Units of {u}",
                                             "units": [{"@type": "Unit", "@id": un[u], "name": u, "conversionFactor": 1.0,
                                                        "isRefUnit": True}]}
        files[f"flow_properties/{fp[u]}.json"] = {"@type": "FlowProperty", "@id": fp[u], "name": f"Quantity in {u}",
                                                 "flowPropertyType": "PHYSICAL_QUANTITY",
                                                 "unitGroup": {"@type": "UnitGroup", "@id": ug[u]}}
    locs = sorted({a["location"] or "GLO" for a in acts})
    lid = {l: _uid("loc", l) for l in locs}
    for l in locs:
        files[f"locations/{lid[l]}.json"] = {"@type": "Location", "@id": lid[l], "name": l, "code": l}

    def fprops(u):
        return [{"@type": "FlowPropertyFactor", "flowProperty": {"@type": "FlowProperty", "@id": fp[u]}, "conversionFactor": 1.0,
                 "isRefFlowProperty": True}]
    pid = {a["id"]: _uid("process", a["key"]) for a in acts}
    prod_flow = {a["id"]: _uid("product", a["key"]) for a in acts}
    waste = {a["id"]: (a["production"] or 1.0) < 0 for a in acts}
    for a in acts:
        u = a["unit"] or "unit"
        files[f"flows/{prod_flow[a['id']]}.json"] = {"@type": "Flow", "@id": prod_flow[a["id"]], "name": a["product"] or a["name"],
                                                     "flowType": "WASTE_FLOW" if waste[a["id"]] else "PRODUCT_FLOW",
                                                     "flowProperties": fprops(u)}
    for f in flows.values():
        u = f["unit"] or "unit"
        files[f"flows/{f['uuid']}.json"] = {"@type": "Flow", "@id": f["uuid"], "name": f["name"], "flowType": "ELEMENTARY_FLOW",
                                           "category": "/".join(x for x in ("Elementary flows", f["compartment"], f["subcompartment"]) if x),
                                           "flowProperties": fprops(u)}
    tby, bby = {}, {}
    for t in tech:
        tby.setdefault(t["output_id"], []).append(t)
    for b in bio:
        bby.setdefault(b["activity_id"], []).append(b)
    byid = {a["id"]: a for a in acts}
    for a in acts:
        u = a["unit"] or "unit"
        exs = [{"@type": "Exchange", "internalId": 1, "isInput": waste[a["id"]], "isQuantitativeReference": True,
                "amount": abs(a["production"] or 1.0), "flow": {"@type": "Flow", "@id": prod_flow[a["id"]]},
                "unit": {"@type": "Unit", "@id": un[u]}, "flowProperty": {"@type": "FlowProperty", "@id": fp[u]}}]
        n = 2
        for t in tby.get(a["id"], []):
            sup = byid[t["input_id"]]
            su = sup["unit"] or "unit"
            if waste[sup["id"]]:   # waste to treatment: an output of the waste flow, provided by the treatment process
                e = {"isInput": False, "amount": -t["amount"]}
            else:
                e = {"isInput": True, "amount": t["amount"]}
            e.update({"@type": "Exchange", "internalId": n, "isQuantitativeReference": False,
                      "flow": {"@type": "Flow", "@id": prod_flow[sup["id"]]}, "unit": {"@type": "Unit", "@id": un[su]},
                      "flowProperty": {"@type": "FlowProperty", "@id": fp[su]},
                      "defaultProvider": {"@type": "Process", "@id": pid[sup["id"]]}})
            exs.append(e)
            n += 1
        for b in bby.get(a["id"], []):
            f = flows[b["flow_id"]]
            fu = f["unit"] or "unit"
            resource = (f["compartment"] or "").lower().startswith(("natural resource", "resource"))
            exs.append({"@type": "Exchange", "internalId": n, "isInput": resource, "isQuantitativeReference": False,
                        "amount": b["amount"], "flow": {"@type": "Flow", "@id": f["uuid"]}, "unit": {"@type": "Unit", "@id": un[fu]},
                        "flowProperty": {"@type": "FlowProperty", "@id": fp[fu]}})
            n += 1
        files[f"processes/{pid[a['id']]}.json"] = {"@type": "Process", "@id": pid[a["id"]], "name": a["name"],
                                                   "processType": "UNIT_PROCESS",
                                                   "location": {"@type": "Location", "@id": lid[a["location"] or "GLO"]},
                                                   "exchanges": exs}
    mid = _uid("method", ",".join(str(m["id"]) for m in methods))
    cats = []
    for m in methods:
        cid = _uid("category", m["family"], m["category"], m["indicator"])
        cats.append({"@type": "ImpactCategory", "@id": cid})
        facs = []
        for fid_, v in cfs[m["id"]].items():
            f = flows[fid_]
            fu = f["unit"] or "unit"
            facs.append({"@type": "ImpactFactor", "flow": {"@type": "Flow", "@id": f["uuid"]}, "value": v,
                         "unit": {"@type": "Unit", "@id": un[fu]}, "flowProperty": {"@type": "FlowProperty", "@id": fp[fu]}})
        files[f"lcia_categories/{cid}.json"] = {"@type": "ImpactCategory", "@id": cid, "name": f"{m['category']} ({m['indicator']})",
                                               "refUnit": m["unit"], "impactFactors": facs}
    files[f"lcia_methods/{mid}.json"] = {"@type": "ImpactMethod", "@id": mid, "name": "Cyclia comparison method",
                                        "impactCategories": cats}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for k, v in files.items():
            z.writestr(k, json.dumps(v, indent=1))
    return buf.getvalue(), {"method": mid, "processes": pid}


def build(store, db_id, method_ids, path, version=""):
    acts, tech, bio, flows, methods, cfs = collect(store, int(db_id), method_ids)
    db = store.one("SELECT name, version, system_model FROM databases WHERE id=?", (int(db_id),))
    res = cyclia_results(store, acts, methods)
    jl, ids = _jsonld(acts, tech, bio, flows, methods, cfs)
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "compare_kit")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("data/activities.csv", _csv([(a["key"], a["name"], a["product"], a["location"], a["unit"], a["production"])
                                                for a in acts], ["key", "name", "product", "location", "unit", "production"]))
        key = {a["id"]: a["key"] for a in acts}
        z.writestr("data/technosphere.csv", _csv([(key[t["output_id"]], key[t["input_id"]], t["amount"]) for t in tech],
                                                 ["consumer_key", "supplier_key", "amount"]))
        z.writestr("data/flows.csv", _csv([(f["uuid"], f["name"], f["compartment"], f["subcompartment"], f["unit"])
                                           for f in flows.values()], ["uuid", "name", "compartment", "subcompartment", "unit"]))
        z.writestr("data/biosphere.csv", _csv([(key[b["activity_id"]], flows[b["flow_id"]]["uuid"], b["amount"]) for b in bio],
                                              ["activity_key", "flow_uuid", "amount"]))
        z.writestr("data/methods.csv", _csv([(m["category"], m["indicator"], m["unit"]) for m in methods],
                                            ["category", "indicator", "unit"]))
        z.writestr("data/factors.csv", _csv([(m["category"], m["indicator"], flows[f]["uuid"], v) for m in methods
                                             for f, v in cfs[m["id"]].items()], ["category", "indicator", "flow_uuid", "cf"]))
        z.writestr("data/process_uuids.csv", _csv([(a["key"], ids["processes"][a["id"]]) for a in acts], ["key", "openlca_process_id"]))
        z.writestr("cyclia_results.csv", _csv(res, ["key", "name", "location", "category", "indicator", "value"]))
        z.writestr("openlca/database.zip", jl)
        z.writestr("openlca/method_id.txt", ids["method"])
        for fn in ("run_brightway.py", "run_bw2calc.py", "run_openlca.py", "check_matrices.py", "compare.py", "README.md"):
            with open(os.path.join(here, fn), encoding="utf-8") as fh:
                z.writestr(fn, fh.read())
        z.writestr("kit.json", json.dumps({"cyclia": version, "database": db["name"], "database_version": db["version"],
                                           "system_model": db["system_model"], "datasets": len(acts),
                                           "categories": [m["category"] for m in methods]}, indent=1))
    return {"path": path, "file": os.path.basename(path), "datasets": len(acts), "categories": len(methods),
            "results": len(res)}
