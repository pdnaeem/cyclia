# Cyclia 1.8.2: scientific reliability

This record covers the findings of the audit of 1.8.1. Each finding was reproduced, corrected and covered by a
regression test. With Brightway installed, all 343 automated tests pass; without it, 339 pass and the four
Brightway tests are skipped. The suite runs without warnings. The validation suite (35 of 35) and the IPCC 2021
check pass. The calculations of the life cycle assessment are unchanged.

| Finding (audit of 1.8.1) | Result |
|---|---|
| P1 A. Nested life cycle costing incomplete | Corrected: replacements, escalation, residual value and price uncertainty at every level |
| P1 B. MFA accepts NaN, Infinity and negative inflows | Corrected: finite, non-negative inflows; finite coefficients, lifetimes and factors |
| P1 C. Social LCA accepts infinite weights; mixes weight units | Corrected: finite weights; conversion within one kind; no score otherwise |
| Excel warning (sheet title over 31 characters) | Test workbook named as Excel does; the reader matches cut sheet names |
| Documentation: allocation comparison, flow diagram, development history | Corrected |
| ecoinvent benchmark shown as current | Marked as the run with Cyclia 1.3.10, not repeated on the current release |
| Provenance in supplier workflow | One history entry per applied response (request, file, lines changed) |

## A. Life cycle costing through sub-models

**Cause.** `_model_cost` added the prices of a sub-model once, at the year of the line that uses it. Replacement
intervals, escalation, residual value and price uncertainty below the top model were not applied.

**Correction.** Every priced line, at every level, becomes a cost item with its purchase times. A sub-model is in
use during windows: one per purchase of the line that uses it, ending at its replacement or at the end of the
study. The line rules of ISO 15686-5 apply inside each window, with the study period, discount rate and escalation
rates of the study. The service life of a purchase ends at its own replacement or when its sub-model is replaced.
The residual value at the end of the period is linear over that life. Price uncertainty is one lognormal draw per
priced line, shared wherever the line is used.

**Tests (`tests/test_lcc_advanced.py`, `TestNestedLCC`).** Hand calculation; the child line costs 100:

| Case | Expected |
|---|---|
| child replaced every 5 years, study 20 years | 400, 3 replacements |
| every 6 years | 400 − 100 × 4/6, residual value −66.67 |
| maintenance escalation 2 %, discount rate 3 % | Σ 100 × 1.02^y and Σ 100 × 1.02^y / 1.03^y, y = 0, 5, 10, 15 |
| sub-model replaced every 10 years, its pump every 4 years | 600 over 20 years; 800 − 75 over 25 years |
| same child used twice, price GSD 2 | one draw; p97.5 / median ≈ 2^1.96 and p2.5 / median ≈ 2^−1.96 |
| no study period | 100 (one purchase) |

The tests of the top-level rules (1.3.5, 1.7.0) are unchanged and pass.

## B. MFA inputs

**Cause.** `validate` did not check the values of inflows. A negative inflow reduced the losses and the mass
balance closed.

**Correction.** The following are refused:
- inflows that are NaN, Infinity, negative, not a number, or given for a year that is not a whole number;
- transfer coefficients that are not finite;
- lifetime parameters and link factors that are not finite or are negative;
- years that are not numbers.

Zero inflows remain valid.

**Tests (`tests/test_v182.py`).** Each of NaN, Infinity, −Infinity, −10, text and an empty value is refused for an
inflow. So are a year "year two", a NaN coefficient, an infinite lifetime and a year "later". The example system
still balances.

## C. Social subcategory assessment

**Cause.** `float('inf') > 0` passed the check, and the score became NaN. Rows with different weight units were
averaged after a warning.

**Correction.**
- Weights and the total must be finite and positive.
- Weights are put on one activity variable (the unit of the scope, or of the first row), and units of the same
  kind are converted.
- A subcategory with a weight that cannot be converted gets no score, with the reason. So does an organisation with
  two different weights in one subcategory.
- Stakeholder means use the scored subcategories only.

**Tests (`tests/test_slca_type1.py`).**
- Infinity, NaN and "Infinity" are refused as weights, and so are an infinite total and a zero or negative total.
- Worker hours with euros give no score for that subcategory, and the other subcategory is unaffected.
- 2 h at +1 with 60 min at −2 gives 0 and a coverage of 50 % of 6 h.
- Two weights for one organisation give no score.

**Every request.** The engine's JSON reader refuses NaN and Infinity (`tests/test_v182.py`).

## Interface check

In the browser, on the demo project:
- **Life cycle cost.** The summary lists the priced lines inside sub-models.
- **Social assessment.** A subcategory without a score shows the reason in place of the score.
- No page errors in the 1000 px and 1366 px sweeps.

## Not done here, with the reason

- **A fresh ecoinvent benchmark on 1.8.2, and the ReCiPe and CML comparisons.** These need the user's ecoinvent
  licence. The tool runs them and the Benchmark Centre records them (corrected in 1.8.1).
- **An openLCA run.** openLCA 2 cannot be built in the development environment.
- **AWARE 2.0, LANCA and USEtox 2 reference validation.** This needs the official packages and their reference
  results.
