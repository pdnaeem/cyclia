# Cyclia: independent cross-validation

This document reports how Cyclia's results are checked against calculations that do not share its code, and what
each check does and does not cover.

## 1. Independent checks

| Check | What is compared | What it verifies | Where |
|---|---|---|---|
| Validation suite (35 cases) | Cyclia against exact answers worked out by hand | Supply chains, loops, waste treatment, allocation, system expansion, nesting, units, regional and site factors, background scenarios, module D, dynamic GWP, Monte Carlo, Sobol, fate model | Toolbox > Validation |
| Comparison with Brightway | Cyclia against Brightway's calculation library (bw2calc) | Matrix assembly, signs, production amounts, the solve and the characterisation, on any installed database | Toolbox > Validation > Compare with Brightway |
| Independent cross-check | Cyclia against a second implementation inside the app | Matrix assembly from the raw tables, sign conventions, the linear solver, characterisation by flow, and the flattening of nested models with allocation | Toolbox > Validation |
| ecoinvent benchmark | Cyclia against ecoinvent's own published LCIA results and cumulative LCI | The whole chain including import and the matching of characterisation factors to flows | Setup > ecoinvent, needs an ecoinvent licence ([report](VALIDATION_ECOINVENT.md)) |
| Factor matching | Cyclia's factors against an openLCA, Brightway or CSV factor set | Factor by factor, with the effect on the models | Toolbox > Validation |

## 2. Comparison with Brightway

### Method

Brightway's calculation library builds its own technosphere, biosphere and characterisation matrices from the
exchange lists of the database (bw_processing datapackages, with technosphere inputs flipped as Brightway does),
solves them with its own solver and characterises the inventory with its own matrix product. Cyclia's result for
the same dataset and category is then compared. Only the exchange lists and the matched factors are shared, so the
comparison checks Cyclia's calculation against an independent and widely used program.

- One unit of each dataset's reference product is calculated. For a treatment dataset (negative reference amount)
  this is one unit of waste treated, a demand of -1 in Brightway.
- The relative difference is |Cyclia - Brightway| / max(|Cyclia|, |Brightway|). Results that cancel to about zero
  are measured against 1e-9 of the largest result of the category.
- Agreement means a relative difference below 1e-6.
- The comparison does not check the import or the factor matching, because both programs use what Cyclia imported.
  Those are checked by the ecoinvent benchmark and the factor matching validation.

The same comparison runs inside the app on any installed database, ecoinvent included (Toolbox > Validation >
Compare with Brightway, then "Save report (Excel)"). For data that may be shared, the comparison kit exports the
tables and a standalone script (`run_bw2calc.py`) that needs only `pip install bw2calc bw_processing`.

### Results

Run on 6 November 2026 with bw2calc 3.1.0 and bw_processing 1.6 (Brightway's source at brightway2-calc dcfc53c,
bw_processing bdeb837, matrix_utils 25ecb8c, stats_arrays 1a63509).

| Database | Datasets compared | Categories | Results | Largest relative difference | Result |
|---|---|---|---|---|---|
| Cyclia demo database | 35 of 35 | 13 | 455 | 5.6e-14 | agreement |
| Tutorial database | 33 of 33 | 13 | 429 | 1.4e-12 | agreement |
| Synthetic database, 3,000 datasets | 300 (random sample) | 10 | 3,000 | 4.4e-13 | agreement |
| Synthetic database, 10,000 datasets | 300 (random sample) | 10 | 3,000 | 3.2e-13 | agreement |
| Comparison kit of the demo database (standalone script) | 35 of 35 | 9 | 315 | 5.7e-14 | agreement |

The synthetic database (`engine/tests/bench_db.py`, fixed seed) has the structure of a large LCA database:

- markets that mix suppliers of several locations, and supply loops;
- waste treatment with negative production;
- infrastructure entering with amounts of 1e-13 to 1e-9 per unit;
- recycling credits as negative inputs;
- elementary flows of every compartment.

Its numbers describe no real product.

The validation workflow (`.github/workflows/validation.yml`) installs Brightway at the exact commits this
comparison was run with (`engine/tools/brightway-pins.txt`) and runs these tests on every change; there a skipped
Brightway test is a failure, so a comparison that did not run is never reported as passed. The automated tests also
run this comparison on every release build (Windows, macOS and Linux), together with a test
that changes one exchange on Brightway's side and checks that the difference is reported.

### Finding

The first run showed opposite signs for treatment datasets. The cause was the demand convention, not the
calculation. Cyclia calculates "one unit of waste treated", while a demand of +1 in Brightway means one unit of
the (negative) reference output. The comparison and the kit's Brightway scripts now use a demand of -1 for these
datasets. With the same convention, every result agrees.

## 3. Independent cross-check inside the app

The second implementation (`engine/crosscheck.py`) does not use the engine's cached matrices, solver or model
expansion:

1. The technosphere matrix A (production on the diagonal, inputs negative) and the biosphere matrix B are
   assembled again from the library tables.
2. A s = f is solved with one of two solvers. The engine itself uses SuperLU, a sparse direct method.
   - Up to 4,000 datasets: LAPACK's dense LU factorisation.
   - Larger libraries: GMRES (an iterative Krylov method) with an incomplete-LU preconditioner and iterative
     refinement.
3. Characterisation uses the stored factor of each flow, and site-specific factors are rebuilt from their own
   table for the models' direct emissions.
4. Models are flattened by a separate recursive routine (signs of avoided products, allocation shares, nested
   models divided by their reference amount, module D left out).

Agreement means a relative difference below 1e-5. A dense solve agrees to round-off (around 1e-14). An iterative
solve agrees to about the condition number of the matrix times machine precision. Differences are measured
against at least 1e-9 of the largest result of a category. The test suite checks that the cross-check fails when
the engine is made wrong by 0.01 %.

| Solver | Datasets | Models | Categories | Largest relative difference | Result |
|---|---|---|---|---|---|
| Dense LU (LAPACK) | 68 | 7 | 20 | 5.7e-14 | agreement |
| GMRES with ILU preconditioner | 68 | 7 | 20 | 1.3e-7 | agreement |

These are the tutorial and demo databases and every model of the demo project, including nested models,
co-product allocation, avoided products, module D, site-specific factors and EPD lines.

## 4. Not covered yet

- **openLCA.** openLCA is a desktop program and cannot run in the build environment. The comparison kit contains
  the database as openLCA JSON-LD and a script for openLCA 2 (IPC). The openLCA run will be published here when it
  has been made on a computer with openLCA 2.
- **Factor sets from other tools.** The factor matching validation is tested with files built to the openLCA
  schema and with the shipped demonstration files. A published comparison of EF 3.1 exported from real openLCA
  and Brightway installations will be added here.
- **ReCiPe 2016 and CML-IA against published results.** The ecoinvent validation can include every installed
  method of ecoinvent's results file (option "Validate every installed method"). The result of that run will be
  added to [VALIDATION_ECOINVENT.md](VALIDATION_ECOINVENT.md).
