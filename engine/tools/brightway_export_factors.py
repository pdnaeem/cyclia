"""Export the characterisation factors of Brightway LCIA methods for Cyclia's factor matching validation.

Run this in YOUR Brightway environment (it is not part of Cyclia's engine and was not run in Cyclia's build
environment, where Brightway is not installed):

    python brightway_export_factors.py "my project" "EF v3.1" factors.csv

The second argument selects the methods whose key contains that text (all methods if empty). Then, in Cyclia:
Toolbox > Validation > Factor matching validation, choose factors.csv.
"""
import csv
import sys

import bw2data as bd


def node(flow):
    if isinstance(flow, (tuple, list)):
        return bd.get_activity(tuple(flow))
    return bd.get_node(id=flow)


def main(project, select, out):
    bd.projects.set_current(project)
    keys = [k for k in bd.methods if not select or select.lower() in " ".join(map(str, k)).lower()]
    if not keys:
        raise SystemExit(f"No method matches '{select}'.")
    n = 0
    with open(out, "w", newline="", encoding="utf-8") as fh:
        fh.write("# Brightway factor export for Cyclia\n")
        w = csv.writer(fh)
        w.writerow(["method key", "category", "code", "name", "categories", "unit", "cf", "location"])
        for key in keys:
            for row in bd.Method(key).load():
                flow, cf = row[0], row[1]
                loc = row[2] if len(row) > 2 else ""
                if isinstance(loc, (tuple, list)):
                    loc = "/".join(map(str, loc))
                act = node(flow)
                cats = act.get("categories") or ()
                w.writerow([" | ".join(map(str, key)), " | ".join(map(str, key[1:])) or str(key[0]), act.get("code", ""),
                            act.get("name", ""), "::".join(cats), act.get("unit", ""), cf,
                            "" if loc in (None, "GLO") else loc])
                n += 1
    print(f"{n} factors of {len(keys)} methods written to {out}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
