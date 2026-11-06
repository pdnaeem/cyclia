# Cyclia comparison kit

This folder holds one database and one impact method in neutral formats, Cyclia's results for every dataset, and
scripts that calculate the same results in Brightway and openLCA and compare them. It is meant to produce a
published, repeatable comparison (for docs/CROSS_VALIDATION.md or a paper).

| File | What it is |
|---|---|
| `data/*.csv` | Datasets, technosphere and biosphere exchanges, elementary flows, categories and factors |
| `openlca/database.zip` | The same database and method as openLCA JSON-LD |
| `cyclia_results.csv` | Cyclia's result of one unit of every dataset's reference product in every category |
| `check_matrices.py` | Independent solve with numpy/scipy only |
| `run_bw2calc.py` | Brightway calculation with the calculation library only (bw2calc, bw_processing; no project needed) |
| `run_brightway.py` | Brightway calculation through a Brightway project (bw2data, bw2calc) |
| `run_openlca.py` | openLCA 2 calculation through the IPC server (olca-ipc) |
| `compare.py` | Comparison and report (comparison_report.md, comparison.csv) |

Steps:

1. `python check_matrices.py` then `python compare.py results_matrices.csv "numpy/scipy"`.
2. `pip install bw2calc bw_processing`, `python run_bw2calc.py`, then `python compare.py results_brightway.csv "Brightway <version>"`.
   With a Brightway project instead: `pip install bw2data bw2calc` and `python run_brightway.py`.
3. Import `openlca/database.zip` in openLCA 2, start the IPC server, `pip install olca-ipc olca-schema`,
   `python run_openlca.py`, then `python compare.py results_openlca.csv "openLCA <version>"`.
4. Publish the three comparison_report.md files with the software versions, the kit.json and the date.

Treatment datasets (negative reference amount) are calculated for one unit of waste treated, a demand of -1 in
Brightway; both Brightway scripts do this.

Agreement means a relative difference below 1e-6 for every result (values that cancel to about zero are measured
against 1e-9 of the largest result of their category). A difference shows a problem in one of the tools or in the
export: please report it at https://github.com/pdnaeem/cyclia/issues with the comparison.csv.

Only share a kit built from data you may share. Never share a kit built from ecoinvent or another licensed database.
