"""Compare another tool's results with Cyclia's and write comparison_report.md and comparison.csv.

    python compare.py results_brightway.csv "Brightway 2.5 (bw2calc x.y)"
    python compare.py results_openlca.csv "openLCA 2.x"
    python compare.py results_matrices.csv "numpy/scipy (independent solve)"

Relative difference = |other - cyclia| / max(|other|, |cyclia|), with values below 1e-9 of the largest result of a
category measured against that floor (round-off of results that cancel to about zero). Agreement: below 1e-6.
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOL = 1e-6


def load(path):
    with open(path, encoding="utf-8") as fh:
        return {(r["key"], r["category"], r["indicator"]): float(r["value"]) for r in csv.DictReader(fh)}


def main():
    other_path = sys.argv[1] if len(sys.argv) > 1 else "results_brightway.csv"
    label = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(other_path)
    cy, ot = load(os.path.join(HERE, "cyclia_results.csv")), load(os.path.join(HERE, other_path))
    keys = sorted(set(cy) & set(ot))
    missing = sorted(set(cy) - set(ot))
    floor = {}
    for k in keys:
        c = (k[1], k[2])
        floor[c] = max(floor.get(c, 0.0), abs(cy[k]), abs(ot[k]))
    rows, worst = [], 0.0
    for k in keys:
        a, b = cy[k], ot[k]
        scale = max(abs(a), abs(b), 1e-9 * floor[(k[1], k[2])])
        d = 0.0 if scale == 0 else abs(a - b) / scale
        worst = max(worst, d)
        rows.append(k + (a, b, d))
    with open(os.path.join(HERE, "comparison.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["key", "category", "indicator", "cyclia", "other", "relative_difference"])
        w.writerows(rows)
    cats = sorted({(k[1], k[2]) for k in keys})
    by = []
    for c in cats:
        ds = sorted(r[5] for r in rows if (r[1], r[2]) == c)
        by.append((c, len(ds), ds[len(ds) // 2] if ds else 0.0, ds[-1] if ds else 0.0, sum(1 for x in ds if x < TOL)))
    ok = worst < TOL and not missing
    lines = [f"# Cyclia compared with {label}", "",
             f"Results compared: {len(keys)} (datasets x categories). Missing in the other file: {len(missing)}.",
             f"Largest relative difference: {worst:.2e}. Verdict: {'agreement (below 1e-6)' if ok else 'differences found'}.", "",
             "| Category | Results | Median relative difference | Largest | Within 1e-6 |", "|---|---|---|---|---|"]
    lines += [f"| {c[0]} ({c[1]}) | {n} | {med:.1e} | {mx:.1e} | {win} |" for c, n, med, mx, win in by]
    worst_rows = sorted(rows, key=lambda r: -r[5])[:10]
    lines += ["", "Largest differences:", "", "| Dataset | Category | Cyclia | Other | Relative difference |", "|---|---|---|---|---|"]
    lines += [f"| {r[0]} | {r[1]} | {r[3]:.6g} | {r[4]:.6g} | {r[5]:.1e} |" for r in worst_rows]
    with open(os.path.join(HERE, "comparison_report.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines[:4]))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
