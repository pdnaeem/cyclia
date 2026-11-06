# Cyclia 1.6.2: scientific reliability

This record lists, for each item of the 1.6.2 plan, what was done, how it was tested and what remains. With
Brightway installed, all 295 automated tests pass. Without it, 291 pass and the four Brightway tests are skipped.
In the validation workflow those four may not be skipped.

| Item | Result |
|---|---|
| Custom factor invalidation | Done (defect corrected) |
| Flow editing and dependency tracking | Done |
| Process versioning, undo and restore | Done |
| Parameter uncertainty | Done, analytic reference test |
| Advanced allocation | Done: physical causality, economic with currency and price year, comparison |
| Scientific Benchmark Centre | Done, with the IPCC 2021 check |
| ReCiPe, CML and IPCC validation | IPCC done; ReCiPe and CML need the ecoinvent licence (tool ready, shown as "Not run") |
| EF 3.1 benchmark on 1.6.2 | Needs the ecoinvent licence; the engine's matrix code is unchanged since the last benchmark, except that parameter sampling adds changes only for custom data |
| Unit and numerical safeguards | Done |
| Recursive LCI provenance | Done |
| Regression and independent integration tests | Done: validation workflow with pinned Brightway |
| Model inventory drawing editor | Done |
| Display: blink and narrow windows | Done |

## Custom factor invalidation

**Defect.** In 1.6.1, the factors of installed methods were matched again when a custom flow changed context, but
the factors the user had given were kept. A factor given for an emission to air stayed in use after the flow was
moved to water.

**Correction.** A change of name, compartment, subcompartment or CAS number puts every factor of the flow under
review:
- the factor is not used and counts as unknown, so the result is marked incomplete;
- the factor table shows the reason, with Confirm and Correct;
- a save that changes only the source keeps the factors.

**Tests**
- A flow moved from air to water: the result drops from 2.70 to 2.65 and is marked incomplete. After Confirm it is
  2.70 again.
- A correction with a new factor clears the review: 2.69.
- An unchanged save keeps the factors.

## Parameter uncertainty

**What was added**
- Parameters take lognormal, normal, triangular or uniform distributions, and the values are checked.
- In the full Monte Carlo the parameters are drawn and the formulas evaluated in every iteration. The change is
  added to the matrices with the unit factor, the allocation share and the sign.
- A database parameter is drawn once per iteration for all its processes.

**Tests (analytic reference).** k is lognormal with median 1 and GSD 1.5; two processes emit 2k and 3k.
- With 4,000 iterations, the median is 5 within 3 %.
- The 2.5 and 97.5 percentiles are 5 x 1.5^(-1.96) and 5 x 1.5^(1.96), within 6 %. This is the full correlation
  of a shared parameter.
- With separate process parameters, the 97.5 percentile is lower: independent draws partly cancel.
- Six invalid distributions are refused.

## Versions, undo, restore and dependencies

**Tests**
- A line changed from 2 to 5 kg is described as "line changed: 2 kg -> 5 kg".
- Undo restores 2.70 and a second undo gives 5.70 again; restoring a version by its history entry also works.
- A deleted process is listed, restored with its lines (result 4.0), and leaves the list.
- A restore whose supplier no longer exists leaves an open input that the check reports, and the result is
  unchanged.
- The dependents of the electricity process are the steel process and the model that uses it.

## Allocation

**Tests (hand calculation)**
- Physical causality by protein content (0.25 and 0.01 kg per kg; 1 kg cheese, 2 kg whey) gives cheese
  10 x 0.25 / 0.27 kg CO2 per kg.
- Economic allocation without a currency, without a year, or with a year that is not a whole number is refused.
- The comparison reproduces:
  - economic 7.5 and 1.25;
  - mass 10/3;
  - the process total of 10.

  It marks physical and energy as unavailable without their values, and refuses a process that uses its own
  co-product.

## Scientific Benchmark Centre

**What was added**
- One table with:
  - the reference and the reference result;
  - Cyclia's result;
  - absolute, relative and maximum differences;
  - missing flows;
  - status, date and Cyclia version.
- Rows for the validation suite, Brightway, the IPCC check, every ecoinvent benchmark by method family, and
  every installed method not yet benchmarked.
- Only runs that passed show "Validated". AWARE, LANCA and USEtox are marked as needing their official packages.
- Excel export.

**Tests**
- Before any run, no row is "Validated".
- Recorded runs show the right status. For example, an EF benchmark with land use at 40 % within 0.1 % is shown
  as "Deviations" and names land use.
- The IPCC check: all 14 gases equal the AR6 values (CO2 1, CH4 fossil 29.8, non-fossil 27.0, N2O 273, SF6
  25,200, and so on) in an empty library.

## Safeguards and provenance

**Tests**
- "0,5" is refused with the hint "0.5".
- 650 kg of flour for 1 kg of bread is reported with its mass ratio.
- A line 20,000 times the reference amount is reported.
- Provenance of 2 kg of steel:
  - three datasets, whose direct contributions add up to 2 x 2.70;
  - the steel process is marked as custom;
  - the incineration amount is -0.4 (0.4 kg treated).

## Validation workflow

`.github/workflows/validation.yml` has three jobs:
- the full test suite on Windows, macOS and Linux;
- the suite with Brightway installed from the commits in `engine/tools/brightway-pins.txt`, with
  `CYCLIA_REQUIRE_BRIGHTWAY=1`;
- the validation suite and the IPCC check.

Locally, with `CYCLIA_REQUIRE_BRIGHTWAY=1` and without Brightway, the Brightway tests fail instead of skipping. With
Brightway they pass.

## Model inventory diagram

**Browser check on the demo**
- A line was dragged to the "new stage" column and named; the table showed the new stage.
- An amount was changed in the diagram from 10 to 7.
- A credit was toggled.
- A formula amount opens the table instead of being overwritten.
- A wide diagram scrolls by itself while a box is dragged to its edge.

## Display corrections (from the earlier 1.6.2 build)

- **Faint blink every few seconds.** The sticky step header had a backdrop blur over scrolling content, which some
  graphics drivers re-composite repeatedly. The header and the welcome overlay no longer use a blur. With the page
  idle for 40 seconds the interface made no change to the page: no DOM mutation, request or animation.
- **Narrow windows.** At 1000 px, a screen-reader label in the inventory table and the rule table of the background
  scenario editor made the page wider than the window. Both are corrected.
- **Whole-system sweep.** Every step, results tab, Toolbox tab and help tab was opened at 1000 and 1366 px and in
  dark mode, with no script error and no overflow.

## Limits

- Parameter distributions of custom data are propagated by the full Monte Carlo, not by the Sobol analysis.
- The comparison of allocation methods covers multi-output custom processes. Model-level allocation is compared by
  saving each choice.
- ReCiPe 2016, CML-IA and the repeated EF 3.1 benchmark need the ecoinvent licence. The openLCA comparison needs
  openLCA 2. The Benchmark Centre shows them as "Not run".
