"""Calculate every process of the kit in openLCA 2 and write results_openlca.csv.

1. In openLCA 2: create an empty database, import openlca/database.zip (File > Import > Linked data, JSON-LD).
2. Start the IPC server: Tools > Developer tools > IPC server, port 8080.
3. pip install olca-ipc olca-schema
4. python run_openlca.py [port]

For every process a product system is built from the default providers (openLCA does this when the calculation
target is a process) and calculated with the kit's impact method, for one unit of the reference product.
"""
import csv
import os
import sys

import olca_ipc as ipc
import olca_schema as o

HERE = os.path.dirname(os.path.abspath(__file__))
port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
client = ipc.Client(port)
with open(os.path.join(HERE, "openlca", "method_id.txt"), encoding="utf-8") as fh:
    method_id = fh.read().strip()
with open(os.path.join(HERE, "data", "process_uuids.csv"), encoding="utf-8") as fh:
    pids = {r["key"]: r["openlca_process_id"] for r in csv.DictReader(fh)}
with open(os.path.join(HERE, "data", "activities.csv"), encoding="utf-8") as fh:
    acts = list(csv.DictReader(fh))
with open(os.path.join(HERE, "data", "methods.csv"), encoding="utf-8") as fh:
    methods = list(csv.DictReader(fh))
name_of = {f"{m['category']} ({m['indicator']})": m for m in methods}
with open(os.path.join(HERE, "results_openlca.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["key", "name", "location", "category", "indicator", "value"])
    for a in acts:
        setup = o.CalculationSetup(target=o.Ref(ref_type=o.RefType.Process, id=pids[a["key"]]),
                                   impact_method=o.Ref(ref_type=o.RefType.ImpactMethod, id=method_id), amount=1.0)
        result = client.calculate(setup)
        result.wait_until_ready()
        for imp in result.get_total_impacts():
            m = name_of.get(imp.impact_category.name)
            if m:
                w.writerow([a["key"], a["name"], a["location"], m["category"], m["indicator"], repr(float(imp.amount))])
        result.dispose()
print('results_openlca.csv written. Next: python compare.py results_openlca.csv "openLCA 2.x"')
