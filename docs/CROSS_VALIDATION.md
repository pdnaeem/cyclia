# Cyclia: independent cross-validation

Version 1.3.4. This document reports how Cyclia's results are checked against calculations that do not share
its code, and what each check does and does not cover.

## 1. Three independent checks

| Check | What is compared | What it verifies | Where |
|---|---|---|---|
| Validation suite (35 cases) | Cyclia against exact answers worked out by hand | Supply chains, loops, waste treatment, allocation, system expansion, nesting, units, regional and site factors, background scenarios, module D, dynamic GWP, Monte Carlo, Sobol, fate model | Toolbox > Validation |
| Independent cross-check (new in 1.3.4) | Cyclia against a second implementation inside the app | Matrix assembly from the raw tables, sign conventions, the linear solver, characterisation by flow, and the flattening of nested models with allocation | Toolbox > Validation |
| ecoinvent benchmark | Cyclia against ecoinvent's own published LCIA results | The whole chain including the matching of characterisation factors to flows | Toolbox > Validation, needs an ecoinvent licence |

## 2. How the independent cross-check works

The second implementation (`engine/crosscheck.py`) does not use the engine's cached matrices, solver or model
expansion:

1. The technosphere matrix A (production on the diagonal, inputs negative) and the biosphere matrix B are
   assembled again from the library tables.
2. A s = f is solved with LAPACK's dense LU factorisation for libraries up to 4,000 datasets, or with GMRES
   (an iterative Krylov method) with an incomplete-LU preconditioner and iterative refinement for larger
   libraries. The engine uses SuperLU, a sparse direct method.
3. Characterisation uses the stored factor of each flow, and site-specific factors are rebuilt from their own
   table for the models' direct emissions.
4. Models are flattened by a separate recursive routine (signs of avoided products, allocation shares, nested
   models divided by their reference amount, module D left out).

The comparison is made per dataset (one unit of its reference product) and per model (the functional unit),
for every selected impact category. Agreement means a relative difference below 1e-5. A dense solve agrees to
round-off (around 1e-14); an iterative solve agrees to about the condition number of the matrix times machine
precision. Differences are measured against at least 1e-9 of the largest result of a category, the size of
that round-off for the tutorial library (condition number 4e6). Until 1.3.4 this floor was 1e-12, which made a
model result that cancels to about zero (a credit for avoided steel) fail the check on macOS, where the
numerical libraries round differently: 1e-14 of round-off was reported as a relative difference of 6e-5.

The test suite checks that the cross-check fails when the engine is made wrong by 0.01 %.

## 3. Results on the data shipped with Cyclia

Run in the build environment on 5 November 2026 with the tutorial database (33 datasets), the demo database (35
datasets), every model of the demo project (7 models, including nested models, co-product allocation, avoided
products, module D, site-specific factors and EPD lines) and all 20 impact categories in the library.

| Solver | Datasets | Models | Categories | Largest relative difference | Result |
|---|---|---|---|---|---|
| Dense LU (LAPACK) | 68 | 7 | 20 | 5.7e-14 | agreement |
| GMRES with ILU preconditioner | 68 | 7 | 20 | 1.3e-7 | agreement |

These databases are illustrative. The same check runs on any library, including ecoinvent: Toolbox >
Validation > Independent cross-check, then "Save report (Excel)". The report lists every dataset and model with
both results and the difference, and the software versions used.

## 4. What is not covered yet

- **Factor matching against another tool.** Since 1.3.5, Toolbox > Validation > Factor matching compares
  Cyclia's factors flow by flow with an openLCA JSON-LD export of the method, a Brightway export
  (`engine/tools/brightway_export_factors.py`) or a CSV. It shows the effect of every difference on your models
  and, with the other tool's results, splits the result difference into factors and the rest (method:
  docs/METHODS.md 12.1; tests and demonstration: docs/quality/ACCEPTANCE_1.3.5.md). The tool is tested with files built to
  the openLCA schema and with the shipped demonstration files. A published run of EF 3.1 exported from real
  openLCA and Brightway installations is still to be done; its reports will be added here.
- **Brightway and openLCA calculations.** Since 1.3.7 the comparison kit (Toolbox > Validation) exports a database
  with Cyclia's results and the scripts to calculate it in Brightway and openLCA. On the tutorial database the
  kit's independent numpy/scipy solve agrees with Cyclia to 1.3e-10, and its openLCA JSON-LD imported back into
  Cyclia reproduces all 132 results. The Brightway and openLCA runs are still to be done and published here.
- **Land use.** In the ecoinvent benchmark, land use results of some datasets were up to about 5 % lower than
  ecoinvent's (median 0.4 %); other categories agreed. Since 1.3.4 the benchmark report has a "Land use
  reconciliation" sheet that splits each result into occupation, transformation-from and transformation-to,
  estimates which group's factors explain the gap, lists land flows without a factor, and a "Conflicting factors"
  sheet that lists flows with two different factors in the method file. Running the benchmark with a licensed
  ecoinvent results file will show the cause; until then the limitation is stated in the checks and reports.
