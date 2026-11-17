# Cyclia 1.10.0: acceptance record

Step 2 of the road to 2.0 (docs/DEVELOPMENT_PLAN.md): database management, and step 3 (modelling).

The suite has 450 automated tests. Here, without Brightway, 446 pass and the four Brightway comparisons are skipped.
The reference regression snapshot passes (at its tolerance of 1e-9, after the refinement step below), as do the
validation suite (35 of 35) and the IPCC check.

## The ecoinvent 3.13 benchmark is complete

The run with 1.9.2 (ecoinvent 3.13 cut-off; 100 datasets, 46 method families, 614 categories) gave:
- **61,220 results:** all within 0.1 %;
- **180 results** of Ecological Scarcity 2021 "biotic resources" (with and without long-term emissions): put apart as
  below numerical resolution. Their values are below 1e-6 of the category's largest result.

For these 180 the workbook holds three solutions per result. The forward LU solution and the adjoint disagreed with
ecoinvent, mostly in sign. The solution after one step of iterative refinement agreed with ecoinvent for all 180:
median deviation 8e-05 %, largest 0.016 %. So the gap was the precision of the plain LU solve for these tiny scaling
factors, not the data.

**Fix.** `MatrixCache.solve` now always adds the refinement step, and `calc.solve_transposed` does the same for
transposed solves (regression snapshot, benchmark adjoint). A factorisation passed in for another matrix (Monte
Carlo samples) is not refined against the library matrix.

Tests (TestIterativeRefinement):
- on a badly scaled chain (solution up to 2.5e51), the solution agrees with the exact rational solution to round-off,
  and forward and refined transposed solves agree;
- with a factorisation off by a relative 1e-7, one refinement step squares the relative error (about 6e-6 to 2e-11)
  for the forward and the transposed solve, compared with exact rational solutions.

The first CI run on macOS failed an earlier form of this test, which compared the absolute residuals of the plain
and refined solutions. Both were at round-off (backward error near 1e-32), so which was smaller depended on the
platform; the test, not the engine, was wrong, and it was replaced by the two above.
- an explicit factorisation of another matrix is used unrefined.

**Published.** docs/benchmarks holds the run's reports. All 61,400 results are within 0.1 % and the largest deviation
is 0.019 %. The 180 results are compared with the run's refined values, and the reports say so. Test:
TestPublicationUsesRefinedValues.

| Plan item | Result |
|---|---|
| Supplier linking with geographical matching | Done: ecoinvent's linking rules on the constructive_geometries topology |
| Linking decisions listed and reversible | Done: log with rule, author, factor and earlier state; exact undo |
| Database quality and completeness dashboard | Done: five more checks (eleven in all), Excel export |
| Complete dataset provenance | Done: database import, source identifier, linking decisions, edit history |
| Streaming imports and transactional rollback | Already present (staging library since 1.3.6, per-file reading); the rollback test now also checks that results are unchanged |
| Database comparison and migration | Already present (1.3.6: comparison, model migration with preview and undo) |
| Imports reproduce the regression snapshot | Tested for openLCA JSON-LD: two imports of one file are bit-identical; a stopped import changes no result |
| Supplier relationship visualisation | Moved to 1.11, with the process graph editor |

## Modelling (step 3)

**End-of-life approaches** (analysis.eol_coefficients, analysis.eol_compare; POST /api/eol/compare; button in the
CFF panel). The formulas are those of Ekvall et al. (2020), IVL report C551, and the PEF method; energy recovery is
left out (R3 = 0).

Tests (tests/test_v1110.py):
- a hand calculation of all four approaches;
- all four agree without recycling;
- the CFF coefficients equal the CFF inventory lines;
- the published worked example of Rickert and Ciroth (2020, GreenDelta, "Application of the Circular Footprint
  Formula in PEF"): PEF Annex C v2.1 values for paper, A = 0.2 and R1 = 0.47, Qsin/Qp = 1, R2 = R3 = 0, give
  coefficients 0.906 (virgin) and 0.094 (recycled), and their virgin and recycled pulp vectors give the published
  ECFF vector for all ten flows (wood −2.718, energy −14.06, residues 4.577 and so on, within the four digits
  published). No worked numerical CFF example with energy recovery (R3) was found in the PEF method or its annexes,
  so the R3 terms rest on the formula and the hand calculation;
- parameters are checked (out of range, yes/no, text, infinity);
- results equal coefficients times the datasets' full supply chain results;
- a missing dataset and a unit that cannot be converted are refused;
- the API.

**Supply chain tree** (supplychain.py; GET /api/activities/<id>/supply-chain; Database explorer). It uses one
transposed solve per category.

Tests:
- for 25 datasets the parts of every node add up to its result, and the root equals the dataset's result;
- limits on depth, number per level and smallest share, and unknown dataset or category, are refused;
- the API.

**Subdivision** (custom_data: the `assign` field of a line, method "subdivision", `_line_outputs` in compile,
allocation_compare, mc_plan; field "Belongs to" in step 5; option "subdivision only" in step 4).

Tests (tests/test_v1110.py, cheese and whey, by hand):
- economic shares 75/25 with lines assigned to each product give 8.5 and 3.25 kg CO2 per kg, together 15 kg;
- an assigned supplier line appears only in its product's dataset, in full;
- the allocation comparison keeps assigned lines: mass gives 10/3 + 1 and (20/3 + 4) / 2; total and assigned
  burden reported;
- "subdivision only" refuses a shared line, both when the process is saved and when a line is added, and changes
  nothing when it refuses; once every line is assigned it gives 11 and 2;
- a line assigned to a product that is not an output, a line assigned in a single-product process, and removing a
  co-product that still has lines, are refused;
- a Monte Carlo parameter draw changes only the dataset the formula line belongs to;
- export and import keep the assignment.

**Named versions** (custom_data.save_version, versions, compare_versions, restore_version, delete_version; table
custom_versions; GET/POST /api/custom/versions, /versions/compare, /versions/restore, /versions/delete; "Named
versions" under the process form). Tests: save, duplicate name refused, changes since, line comparison (changed,
removed, same), restore gives the hand-calculated results back with the same dataset ids, undo reverses the
restore, delete; yes/no, zero, negative, fractional and text version ids refused; the API.

**Suppliers into the diagram** (custom-data.js): library search under the diagram; a result dragged onto a process,
or clicked and then the process, opens the input form with that supplier. Checked in the browser (drag and drop,
click and click, no console errors, no horizontal overflow).

**Multifunctionality as a choice of the model** (calc.multifunctional, line_share, expansion_lines; scope field
`multifunctional` and co-product fields `replaces`, `replaces_amount`; line field `assign`). A model with any number
of co-products is handled by allocation (shared lines by the share; lines that belong to the main product in full,
lines of the co-products not at all), subdivision (every line belongs to one side; a shared line is refused) or
system expansion (all lines, and a credit line per co-product for the product it replaces). One rule, line_share,
is used by the calculation, the contribution lines, Monte Carlo (hier), life cycle costing, the optimisation of
choices, the hotspot tree and the independent cross-check.

Tests (tests/test_v1110.py, a cheese model by hand: milk 10, electricity 2, whey powder 4 kg CO2 per unit; 1 kg milk
shared, 1 kWh for cheese, 0.5 kWh for whey; whey replaces 0.5 kg whey powder):
- mass 1/3: 2 + 10/3; economic 0.75: 9.5; no allocation 13; system expansion 13 − 2 = 11; subdivision with the milk
  given to cheese 12. The comparison of choices gives the same numbers as full calculations under each rule;
- the system expansion credit is a derived line (−2), and the Monte Carlo tree and the independent cross-check
  reproduce 11;
- subdivision with a shared line, system expansion without a replaced product, an unknown rule, a yes/no or
  infinite or negative replacement, and an unknown line assignment are refused;
- the checks report shared lines under subdivision;
- the datasets list of a model applies the allocation share once (10/3 kg CO2 for milk). Before 1.10.0 it applied
  the share twice in that list; totals and contributions were not affected;
- the API (line assignment, scope rule, comparison).

**Supplier relations in the model diagram** (app.js): find a dataset or one of the project's models under the
diagram and drop it onto a line to replace its supplier (same route as "Replace", so units are checked and Undo
reverses it), or onto a stage column, or "new stage", to add it as a line with the amount typed in place. Lines show
and change what they belong to; system expansion credits show in their own column. Checked in the browser: adding
by drop, replacing by drop (a unit mismatch is refused with its message), no console errors, no horizontal
overflow.

## Geography (engine/geography.py)

The topology comes from constructive_geometries 1.0 (commit 3e1aaa9, BSD 3-clause; THIRD_PARTY.md), converted to
engine/data/geographies.json.gz (173 kB). It holds:
- the faces of 541 geographies;
- the area of each face;
- the old names that map to current ones, such as "NPCC, US only" to US-NPCC.

The build includes the file and checks that it is in the bundle.

Tests (TestGeography):
- containment: RER ⊃ FR; CN ⊃ CN-HB; "Europe without Switzerland" ⊃ FR but not CH; old grid names;
- the linking rules:
  - same location first;
  - the smallest containing region ("Europe without Switzerland" before RER for FR);
  - RoW only where no other supplier covers the location;
  - GLO last;
  - no match;
  - partial RoW (RER with suppliers CH, DE and RoW);
  - "inside" and "overlaps" are not matches.

## Linking (engine/linking.py)

- **Suggestions.** Scored by the geography relation. Each carries `geography`, `geography_rank` and
  `geography_note`, and a supplier that does not cover the location scores lower.
- **Automatic linking.**
  - Uses the product name and a convertible unit, markets first, and the linking rules.
  - Leaves to the user: partial RoW, unknown locations, ties, and the three cases it left before (several producers
    in the import, a named provider, no supplier link).
  - Returns the counts by rule.
- **Log.** Table `link_log`, one row per decision:
  - action, method, rule, author and time;
  - product, unit and location;
  - supplier and conversion factor;
  - the earlier supplier and factor of every input.
- **Undo.**
  - Restores supplier, factor and uncertainty parameters for each input, and records an undo entry.
  - Refuses when a later decision changed the inputs, when the decision was already undone, or when it is an event
    rather than a decision.
- **Deleted supplier database.** Its users' inputs are unlinked as before, and now recorded in the log as "database
  deleted".

Tests (tests/test_v1100.py, 9 tests in all; TestGeographicLinking):
- suppliers at DE, RER, "Europe without Switzerland" and RoW, for inputs at FR, DE, CH, BR, RER and XX:
  - FR gets "Europe without Switzerland";
  - DE and RER their own;
  - CH gets RER, because RER contains CH and so RoW does not cover it;
  - BR gets RoW;
  - XX is left for review;
  - MWh to kWh is converted in the matrix;
- the log:
  - decisions logged with author and rule;
  - a manual override and its undo restore the automatic choice with its factor;
  - undo order enforced;
  - unlink undone;
  - deletion of the supplier database recorded;
- the database check flags a manual FR to DE link and the unknown location XX;
- provenance shows the decision;
- the Excel export has its three sheets;
- API routes: automatic linking by rule, the log with author, provenance, the Excel export, undo and its refusals.

The test of 1.3.6 that expected no automatic link for FR, DE and PL with only a global electricity dataset now
expects three links by the global rule. This is the documented change of behaviour.

## Database check (engine/dbquality.py)

calc.validate_database adds five statuses:
- supplier links: by rule, and those whose supplier geography does not cover the input;
- geography: unknown locations, datasets without a location;
- uncertainty and data quality coverage;
- duplicates;
- provenance.

There is no combined score. The UI shows the eleven checks and exports them to Excel (Checks, Details, Linking
decisions). The test of 1.3.6 now expects the eleven keys.

## Provenance

`GET /api/activities/<id>/provenance` returns:
- the dataset and its source identifier;
- its database and the import that created it: file, SHA-256, importer, date, version, system model, licence;
- each input linked across datasets with its supplier and the decision that linked it;
- the edit history of a dataset built in Cyclia;
- its geography in the topology.

The Database explorer shows this.

## Imports reproduce results

TestImportsReproduceTheSnapshot:
- the same JSON-LD file imported into two fresh libraries gives identical regression snapshots, compared with zero
  tolerance;
- an import with an infinite amount is stopped by the staging checks, and the library's snapshot afterwards is
  identical to the one before.

The other formats share the staging path. A per-format round trip needs exporters of whole databases, which Cyclia
does not have; this is noted for 2.0.
