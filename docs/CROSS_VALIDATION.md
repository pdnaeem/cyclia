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
precision. Values below 1e-12 of the largest result of a category are treated as zero, because the engine sets
such round-off to zero.

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

- **Factor matching against another tool.** The cross-check uses the factors Cyclia has matched to the flows.
  Whether they are the right factors is checked by the ecoinvent benchmark, which compares with ecoinvent's own
  results. A comparison of the same inventory in openLCA and Brightway (which match factors in their own way) is
  planned; Cyclia's export to Brightway and openLCA (step 6) produces the files for it.
- **Land use.** In the ecoinvent benchmark, land use results of some datasets were up to about 5 % lower than
  ecoinvent's (median 0.4 %); other categories agreed. Since 1.3.4 the benchmark report has a "Land use
  reconciliation" sheet that splits each result into occupation, transformation-from and transformation-to,
  estimates which group's factors explain the gap, lists land flows without a factor, and a "Conflicting factors"
  sheet that lists flows with two different factors in the method file. Running the benchmark with a licensed
  ecoinvent results file will show the cause; until then the limitation is stated in the checks and reports.
