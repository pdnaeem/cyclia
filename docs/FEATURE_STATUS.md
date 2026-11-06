# Cyclia feature status

Status of Cyclia 1.7.0, checked against the source code, the automated tests and the validation records. A feature
counts as **validated** only when its calculation is compared with independent reference results. Interface
elements alone do not count.

| Status | Meaning |
|---|---|
| **Validated** | Implemented, tested, and compared with an independent reference (published values, hand calculation, another implementation or ecoinvent's own results) |
| **Implemented** | Works end to end with automated tests; no comparison with an external reference yet |
| **Partial** | Usable, with documented limits listed in the table |
| **Planned** | Not available yet; see the [development plan](DEVELOPMENT_PLAN.md) |

## Calculation core

| Feature | Status | Evidence and limits |
|---|---|---|
| Matrix LCA (sparse LU, loops, nested models) | Validated | 35 validation systems with exact answers; independent second implementation ([cross validation](CROSS_VALIDATION.md)); ecoinvent benchmark |
| Agreement with ecoinvent's LCIA results (EF 3.1, cut-off) | Validated | 100 % of 2,500 results within 0.1 %, median 3.9e-07 % ([report](VALIDATION_ECOINVENT.md)) |
| Inventory check against ecoinvent's cumulative LCI | Validated | Splits each deviation into inventory and factor parts; found the land use cause |
| Units and conversions | Validated | Unit families, conversion tests, unknown-unit check in the database check |
| Parameters, formulas, scenarios | Implemented | Tests of formula evaluation and scenario switching |
| Comparison with Brightway | Validated | Brightway's calculation library (bw2calc) builds and solves its own matrices; all results agree within 1e-6 (largest difference 4.4e-13 on a 3,000-dataset test database); runs in the app on any database and in every release build ([cross validation](CROSS_VALIDATION.md)) |
| Scientific Benchmark Centre | Implemented | Every check with reference, result, differences, missing flows and status; not-run and not-available checks are never counted as validated |
| Comparison with openLCA | Partial | Comparison kit with openLCA JSON-LD and an openLCA 2 script; the run with openLCA is still to be published |

## LCIA methods

| Method | Status | Evidence and limits |
|---|---|---|
| EF 3.1 with JRC normalisation and weighting | Validated | Factors from ecoinvent's LCIA implementation file or the JRC package; ecoinvent benchmark over 25 categories |
| IPCC 2021 GWP100, EN 15804+A2 split | Validated | 14 gases reproduce the published IPCC AR6 GWP100 values within 1e-12 in an independent check (Benchmark Centre, automated test); fossil, biogenic and land use change split tested |
| ReCiPe 2016, CML-IA | Implemented | Read from the official factor files; the ecoinvent validation can now include every installed method of ecoinvent's results file; that run is still to be published |
| Any method from a CSV table, flow mapping | Implemented | Missing-factor and unit checks per category |
| Dynamic GWP | Validated | Validation system with an exact answer |
| AWARE water scarcity (annual, monthly, GIS) | Implemented | Consumption = withdrawal minus return to fresh water, with the water balance and the part identified by outputs; hand-calculated reference tests. The factors are not bundled (licence); an imported package is checked for completeness, world fallback, monthly sets, range and source. Not declared complete until checked against the official package's reference results |
| LANCA land use (SQI aggregation) | Partial | Occupation and transformation per indicator, unit checks (per m2 and per ha) and SQI aggregation tested by hand calculation; an imported package is checked for all five indicators per land use, world fallback and source; a check of the values needs the official package |
| Toxicity (fate model, imported USEtox factors) | Partial | Screening factors from a multimedia fate model, clearly labelled; official USEtox 2 factors can be imported by CAS number and are checked for CTUh/CTUe units, signs and compartments; no tests against the USEtox reference results yet |
| IMPACT World+, biodiversity methods | Planned | No factors are invented; added only with official factor packages |

## Databases and interoperability

| Feature | Status | Evidence and limits |
|---|---|---|
| ecoinvent download with the user's licence | Validated | Benchmarked install (27,400 datasets) |
| ecoSpold2, ecoSpold1, openLCA JSON-LD, ILCD, SimaPro CSV import | Implemented | Process identity kept, explicit providers kept, ambiguous suppliers left open, unresolved inputs recorded, non-finite values rejected |
| Staging import with integrity report and rollback | Implemented | Rollback tested for failures while reading and inside the merge |
| Streaming of large imports | Implemented | SimaPro: 200,000 processes in 360 MB; technosphere inputs are still held until linking |
| Database explorer | Implemented | Filters, paging, unresolved-only view, export of selected datasets |
| Database check per database | Implemented | Six-part check: integrity, units, flow coverage, LCIA compatibility, matrix, metadata |
| Database version comparison and model migration | Implemented | Preview and undo |
| Custom data entry (own databases, product and elementary flows, processes, exchanges, factors) | Implemented | Complete product system from an empty library; UUID, source, author and revision per item; unit validation and conversion within one dimension; ecoinvent compartments; CAS check digit; uncertainty and pedigree; custom methods; JSON export and import. Hand-calculated supply chain with waste treatment, avoided product and unit conversions reproduced exactly, worked example (64 tests) |
| Unknown factors | Implemented | Never taken as zero: a custom flow without a known factor, or any flow without one in a custom method (unless its scope says, with the reason, that such flows have no effect), marks the category incomplete in results, report, workbook and checks. Known means a factor exists or was recorded, zero included, or the category was recorded as not applying |
| Editing and change history of custom data | Implemented | Products, flows, lines and factors editable; renames update datasets; flow edits rematch factors; every change logged with time and author |
| Parameters and formulas in custom processes | Implemented | Database and process parameters, formulas in amounts; every change re-evaluated in one transaction and refused as a whole if a formula fails or turns negative; hand-calculated tests |
| Multi-output custom processes | Validated | Mass, energy, economic and manual allocation, one dataset per output with scaled exchanges and uncertainty; hand calculation (economic 75/25 %, mass 1/3, 2/3) and conservation of the process's exchanges tested |
| User-defined units | Implemented | Units in known dimensions or new dimensions with multiples; size locked once in use; kept through restart and export |
| Supply chain diagram for custom data | Implemented | Drag to arrange, connect to add an input, click an arrow to edit |
| Model inventory editing in the diagram | Implemented | Move lines between stages or to a new stage, change amounts, toggle credits, remove lines, open a line |
| Parameter uncertainty of custom data | Validated | Distributions drawn in the full Monte Carlo with formulas re-evaluated; analytic lognormal reference (median, 2.5 and 97.5 percentiles) and the effect of shared and independent draws tested |
| Factor review after a flow change | Implemented | Own factors of a custom flow whose name, context or CAS number changes are not used until confirmed or corrected |
| Versions, undo, restore, dependencies | Implemented | State before and after every change; undo and redo, restore any version or a deleted process; dependent processes and models of every project |
| Physical, economic (currency, price year) allocation and comparison | Validated | Hand-calculated physical causality case; comparison reproduces the economic and mass hand calculations and conserves the process total |
| Plausibility checks | Implemented | Mass balance and order-of-magnitude warnings, decimal comma hint |
| Recursive provenance | Implemented | Every dataset of the supply chain in the Excel workbook and a Word annex; direct contributions add up to the total (tested) |
| Duplicate dataset detection, comparison dashboard, supplier graph | Planned | |
| Export to Brightway and openLCA; Python and R clients | Implemented | Brightway round-trip and openLCA JSON-LD export tests |

## Modelling

| Feature | Status | Evidence and limits |
|---|---|---|
| Guided ISO 14044 workflow | Implemented | Six steps with checks |
| Allocation: mass, economic, energy, physical, manual; system expansion; avoided products | Implemented | Allocation overview per project; a side-by-side comparison of allocation choices is planned |
| Circular Footprint Formula (PEF) | Validated | Hand-calculated reference test |
| EN 15804+A2 modules A to D | Validated | Module reconciliation checked before an EPD is written |
| Flow diagram | Partial | Arrangeable diagram of the model, a click opens the line; custom processes are connected and edited in their own diagram; model inventories are still edited in tables |
| Background scenarios (prospective, consequential) | Implemented | premise and Activity Browser scenario files |

## Uncertainty and sensitivity

| Feature | Status | Evidence and limits |
|---|---|---|
| Monte Carlo, foreground and full, through nested models | Validated | Validation systems with known distributions; a two-level nested chain reproduces the analytic lognormal median and spread |
| Pedigree uncertainty, correlated parameters (Gaussian copula), convergence | Implemented | Tests of correlation and convergence statistics |
| Sobol indices | Validated | Reference function with known indices |
| Comparative LCA | Validated | Comparison checks (functional equivalence, boundaries, allocation, data quality, system models); paired Monte Carlo with a conclusion per category from the probability and its sampling error at 90, 95 or 99 % confidence; tested against the analytic probability of two lognormal alternatives |

## Social LCA, MFA and costing

| Feature | Status | Evidence and limits |
|---|---|---|
| Social LCA screening | Partial | Screening of worker hours and risk hours per stakeholder with imported PSILCA, SOCA or own data, with hand-calculated tests of activity levels, waste treatment, credits and coverage |
| Social LCA subcategory assessment (Type I) | Implemented | UNEP 2020 stakeholder categories and subcategories, performance reference points on the -2 to +2 scale, activity-variable weighting, coverage, site-specific share, hotspots and missing subcategories; hand-calculated tests. Cyclia ships no social data; impact pathways (Type II) are not included |
| Material flow analysis | Implemented | Dynamic stocks, lifetimes, recycling loops, collection rate, recycling efficiency and end-of-life recycling rate, Material Circularity Indicator (reference values of the Ellen MacArthur Foundation methodology), visual builder |
| MFA integrated with LCA | Implemented | Impacts year by year from the MFA quantities: production charged on virgin input, recycling, losses, credits for recovered material with a substitution ratio, gross and net; tests that every part equals quantity x factor x unit impact |
| Life cycle costing | Implemented | ISO 15686-5: prices per line, discounting, cost types including the ISO 15686-5 categories, replacements, residual value at the end of the study period, real price escalation per cost type, price uncertainty with a Monte Carlo interval; hand-calculated tests |
| Allocation choices of a model | Implemented | Results under mass, economic, energy, physical, manual allocation and without allocation, side by side; each equal to a full calculation under that basis (tested) |

## Reports and declarations

| Feature | Status | Evidence and limits |
|---|---|---|
| ISO 14044 report, executive summary, Excel workbook, figures | Implemented | Generated from the calculated result with provenance |
| EPD (ISO 14025:2026, EN 15804+A2) with programme layouts | Partial | EPD International, IBU and INIES layouts are drafts that the programme operators have not reviewed; every EPD is labelled as an unverified draft |
| ILCD+EPD XML export | Validated | Validated against the official ILCD and EPD extension schemas |
| ISO 14067 carbon footprint, GHG Protocol workbook | Implemented | Fossil, biogenic and land use change split |
| Data quality: pedigree indicator and PEF DQR | Validated | Kept apart: a pedigree score is never shown as a PEF DQR; nested aggregation tested against a hand calculation |
| Reproducibility bundle with fingerprints | Implemented | Bundles recalculate to the same result |

## Not available

Multi-user projects, a plugin interface for external methods, and supplier collaboration are not part of
Cyclia yet. The [development plan](DEVELOPMENT_PLAN.md) lists them in order of priority.
