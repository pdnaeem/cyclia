# Cyclia feature status

Status of Cyclia 1.4.2, checked against the source code, the automated tests and the validation records. A feature
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
| Comparison with openLCA and Brightway | Partial | Comparison kit and factor-matching validation exist; a published run with both programs is still to be done |

## LCIA methods

| Method | Status | Evidence and limits |
|---|---|---|
| EF 3.1 with JRC normalisation and weighting | Validated | Factors from ecoinvent's LCIA implementation file or the JRC package; ecoinvent benchmark over 25 categories |
| IPCC 2021 GWP100, EN 15804+A2 split | Implemented | Fossil, biogenic and land use change split tested; no published comparison of results yet |
| ReCiPe 2016, CML-IA | Implemented | Read from the official factor files; no external result comparison published |
| Any method from a CSV table, flow mapping | Implemented | Missing-factor and unit checks per category |
| Dynamic GWP | Validated | Validation system with an exact answer |
| AWARE water scarcity (annual, monthly, GIS) | Partial | Calculation with imported official factors; the factors are not bundled (licence) |
| LANCA land use (SQI aggregation) | Partial | Imported factors with SQI aggregation; the full LANCA indicator package is not validated against its documentation yet |
| Toxicity (fate model, imported USEtox factors) | Partial | Screening factors from a multimedia fate model, clearly labelled; official USEtox 2 factors can be imported by CAS number, but no tests against the USEtox reference results yet |
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
| Duplicate dataset detection, comparison dashboard, supplier graph | Planned | |
| Export to Brightway and openLCA; Python and R clients | Implemented | Brightway round-trip and openLCA JSON-LD export tests |

## Modelling

| Feature | Status | Evidence and limits |
|---|---|---|
| Guided ISO 14044 workflow | Implemented | Six steps with checks |
| Allocation: mass, economic, energy, physical, manual; system expansion; avoided products | Implemented | Allocation overview per project; a side-by-side comparison of allocation choices is planned |
| Circular Footprint Formula (PEF) | Validated | Hand-calculated reference test |
| EN 15804+A2 modules A to D | Validated | Module reconciliation checked before an EPD is written |
| Flow diagram | Partial | Arrangeable diagram of the model; inventories are edited in tables, not by drawing |
| Background scenarios (prospective, consequential) | Implemented | premise and Activity Browser scenario files |

## Uncertainty and sensitivity

| Feature | Status | Evidence and limits |
|---|---|---|
| Monte Carlo, foreground and full, through nested models | Validated | Validation systems with known distributions |
| Pedigree uncertainty, correlated parameters (Gaussian copula), convergence | Implemented | Tests of correlation and convergence statistics |
| Sobol indices | Validated | Reference function with known indices |
| Comparative probabilities | Implemented | Per category from paired Monte Carlo runs |

## Social LCA, MFA and costing

| Feature | Status | Evidence and limits |
|---|---|---|
| Social LCA | Partial | Screening of worker hours and risk hours per stakeholder with imported PSILCA, SOCA or own data; not a full social LCA with performance reference points |
| Material flow analysis | Implemented | Dynamic stocks, lifetimes, recycling loops, Material Circularity Indicator, link to LCA models, visual builder |
| Life cycle costing | Partial | Prices per line, discounting, cost types, replacements; residual value, escalation and cost uncertainty are planned |

## Reports and declarations

| Feature | Status | Evidence and limits |
|---|---|---|
| ISO 14044 report, executive summary, Excel workbook, figures | Implemented | Generated from the calculated result with provenance |
| EPD (ISO 14025:2026, EN 15804+A2) with programme layouts | Partial | EPD International, IBU and INIES layouts are drafts that the programme operators have not reviewed; every EPD is labelled as an unverified draft |
| ILCD+EPD XML export | Validated | Validated against the official ILCD and EPD extension schemas |
| ISO 14067 carbon footprint, GHG Protocol workbook | Implemented | Fossil, biogenic and land use change split |
| Data quality: pedigree indicator and PEF DQR | Implemented | Kept apart: a pedigree score is never shown as a PEF DQR |
| Reproducibility bundle with fingerprints | Implemented | Bundles recalculate to the same result |

## Not available

Multi-user projects, a plugin interface for external methods, and supplier collaboration are not part of
Cyclia yet. The [development plan](DEVELOPMENT_PLAN.md) lists them in order of priority.
