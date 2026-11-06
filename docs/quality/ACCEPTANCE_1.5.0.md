# Cyclia 1.5.0: stage P0 of the development plan

This record lists, for each P0 item of the [development plan](../DEVELOPMENT_PLAN.md), what was changed, how it was
tested and what remains. All 227 automated tests pass, with and without Brightway installed. Without it, the four
Brightway tests are skipped.

| Item | Result |
|---|---|
| Comparison with Brightway | Done: real Brightway, in the app and in the release builds |
| Comparison with openLCA | Open: needs openLCA 2 on a desktop computer |
| ReCiPe 2016 and CML-IA validation | Tool done; the run needs the ecoinvent licence |
| Comparative LCA | Done |
| Nested uncertainty and data quality | Done; no defect found |
| AWARE and LANCA calculations | Done; the official factor packages are needed for a final check |
| Social LCA and MFA calculations | Done; two defects corrected |

## Comparison with Brightway

**What changed**
- `engine/brightway_check.py`: Brightway's calculation library builds, solves and characterises its own matrices
  from the database's exchange lists, and every result is compared with Cyclia's.
- The app's version is under Toolbox > Validation > Compare with Brightway. Its Excel report has a summary, a
  table per category and every result.
- The build installs bw2calc and checks that the comparison works in the packaged engine.
- The comparison kit gained the standalone script `run_bw2calc.py`.

**Defect found and corrected.** The kit's Brightway script calculated treatment datasets for +1 unit of their
(negative) reference output, which gives the opposite sign of "one unit of waste treated". Both Brightway scripts
and the in-app comparison now use a demand of -1 for these datasets.

**Results.** These were run with bw2calc 3.1.0 and bw_processing 1.6 ([cross validation](../CROSS_VALIDATION.md)).

| Database | Results | Largest relative difference |
|---|---|---|
| Demo | 455 | 5.6e-14 |
| Tutorial | 429 | 1.4e-12 |
| Synthetic, 3,000 datasets | 3,000 | 4.4e-13 |
| Synthetic, 10,000 datasets | 3,000 | 3.2e-13 |
| Kit of the demo database, standalone script | 315 | 5.7e-14 |

**Tests** (`engine/tests/test_brightway.py`)
- the demo database agrees;
- an 800-dataset synthetic database agrees, with markets, loops, waste treatment, infrastructure at 1e-13 to 1e-9
  and recycling credits;
- one exchange changed on Brightway's side is reported;
- sampling works;
- a clear message appears when Brightway is not installed.

**Performance.** Brightway factorises the technosphere once for all categories: 100 datasets of a 5,000-dataset
database with 10 categories take 6 s.

## Comparison with openLCA

Open. openLCA 2 is a desktop program. The comparison kit contains the database as openLCA JSON-LD and an IPC
script. The run will be published in the cross validation document.

## ReCiPe 2016 and CML-IA

The ecoinvent validation has a new option, "Validate every installed method of ecoinvent's results". With it, every
method of ecoinvent's results file that is installed in Cyclia is compared, not only EF 3.1. The run needs the
user's ecoinvent licence. Its result will be added to [VALIDATION_ECOINVENT.md](../VALIDATION_ECOINVENT.md).

## Comparative LCA

**What changed**
- `calc.compare_conclusion` and `calc.wilson`: each category gets a conclusion from the paired Monte Carlo
  probability and its 95 % Wilson interval, at a chosen confidence of 90, 95 or 99 %.
- The possible conclusions are "A lower", "B lower", "run more iterations", "not distinguishable" and "no
  difference".
- Before, the interface applied a fixed 95 % share without the sampling error, and its explanation spoke of a
  difference interval that did not match the rule.

**Tests** (`engine/tests/test_p0.py`)
- the analytic probability of two lognormal alternatives, Phi(ln 1.25 / sqrt(s_A^2 + s_B^2)), is reproduced within
  four standard errors with 5,000 runs, and lies inside the reported interval;
- the same model on both sides gives "no difference", which shows the runs are paired;
- Wilson interval reference values: 96 of 100 runs gives 90.2 % to 98.4 %, so "run more iterations";
- clear differences, overlapping distributions and invalid confidence levels.

## Nested uncertainty and data quality

No defect found. Tests:
- A two-level chain (Top = 2 x S, S = 1 x X) reproduces the analytic lognormal: median 2, and log standard
  deviation sqrt(s1^2 + s2^2) within 5 %.
- A nested data quality case reproduces the hand calculation: shares 0.75 and 0.25, worst score along each chain,
  pedigree indicator 2.5.

## AWARE and LANCA

**What changed**
- AWARE reports which part of the consumption is identified by an output flow (evaporation, sea, soil) and which
  part has none.
- The result note no longer says that monthly factors and the GIS lookup are unsupported; both are supported
  since 1.3.7.

**Tests**
- AWARE: 10 m3 withdrawn, 2 evaporated, 7 returned and 1 to the ocean give a consumption of 3 m3, an impact of 15
  with a factor of 5, and fully identified consumption.
- AWARE: an unreported output is shown as unidentified, with the global fallback.
- LANCA: occupation and transformation per indicator by hand, factors per hectare converted, a wrong factor unit
  rejected, and the SQI aggregation by hand (0.625).

**Limits.** The official AWARE 2.0 and LANCA factor packages are not available here, so the factor values
themselves are not checked.

## Social LCA and MFA

**Defects corrected**
1. **Social screening, waste sent to treatment.** A treatment dataset has a negative reference amount, so its
   demand is negative. The screening split the demand by its sign and reported the waste treatment as an avoided
   product: its worker hours were missing from the total. The split now uses the sign of the line (avoided or
   not) and of the scaling (the process runs or is avoided). Credits inside the supply chain are now reported as
   avoided instead of being added.
2. **MFA, end-of-life recycling rate and collection rate.** These were computed from all recycled output and all
   input to recycling. Production scrap and imported scrap therefore raised the end-of-life rates, and the
   collection rate could exceed 100 %. The end-of-life material that reaches recycling is now traced through
   collection and sorting with the transfer coefficients. The collection rate and the recycling efficiency are
   reported, and the MCI uses them.

**Also new.** The social screening lists processes whose data rows give different worker hours per unit.

**Tests**
- Social hand calculation (product, material, waste treatment and an avoided material): 0.7 worker hours used,
  0.2 avoided, 2.32 risk hours.
- Inconsistent activity variables are listed.
- MFA hand calculation: collection 0.8 x 0.75 = 60 %, efficiency 90 %, end-of-life recycling rate 54 %, with
  production scrap sent to recycling.
- MCI reference values (Ellen MacArthur Foundation 2015): linear 0.1, circular 1, and a hand-calculated
  intermediate case.

## Interface check

- Element ids in the interface are now tested to be unique (`engine/tests/test_ui_static.py`). The new Brightway
  panel had first reused the id of the "Export for Brightway" button, and the test catches this.
- In the browser, the Brightway comparison ran on the demo database and showed 420 agreeing results.
- In the browser, the comparative Monte Carlo showed the conclusion, probability and interval per category.
