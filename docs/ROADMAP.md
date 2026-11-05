# Cyclia feature assessment and roadmap

Version: 1.3.10. Author: Naeem Ur Rehman. This document lists what Cyclia does, which standards it follows,
what was added in 1.3.2 after a full feature review, what 1.3.3 and 1.3.4 corrected after two external audits,
what 1.3.5 added after a third audit, and what is still planned. Competitor capabilities are
only listed where the vendor's own documentation describes them (sources at the end).

Priority classes: **P0** needed for a scientifically reliable study; **P1** needed for consulting and
industrial work; **P2** better analysis and user experience; **P3** future features that would make Cyclia
distinctive. Complexity: S (days), M (weeks), L (a month), XL (several months).

---

## 1. Standards Cyclia follows (status November 2026)

| Standard | Edition in force | How Cyclia uses it |
|---|---|---|
| ISO 14040 | 2006 + Amd 1:2020 | Workflow, terms, phases |
| ISO 14044 | 2006 + Amd 1:2017, Amd 2:2020 | Goal and scope fields, allocation hierarchy, data quality requirements, checks, interpretation, report structure, critical review |
| ISO 14071 | 2024 | Critical review process and reviewer competences (review status, review checklist) |
| ISO/TS 14074 | 2022 | Normalisation, weighting and interpretation (optional elements kept apart from characterised results) |
| ISO 14067 | 2018 (revision at working draft stage in 2026) | Carbon footprint report with fossil, biogenic and land use change split |
| ISO 14025 | **2026** (second edition, replaces 2006) | EPD draft: EPD type information (share of GWP from supply-chain-specific data, months of specific data), intended audience, prospective EPDs with quantified uncertainty, named third-party verifier for B2C, and a statement that Cyclia is not a verified EPD tool |
| ISO 14020 | 2022 | General principles for environmental statements (referenced by ISO 14025:2026) |
| EN 15804 | 2012+A2:2019 | Modules A1 to D, core indicators, data age, biogenic carbon |
| PEF method | Commission Recommendation (EU) 2021/2279, EF 3.1 | Normalisation and weighting, most relevant results, Circular Footprint Formula, DQR form |
| ISO 14046 | 2014 | Water inventory as the basis of a water footprint |
| ISO 14075 | 2024 | Social LCA: planned (P3) |
| ISO 59020 | 2024 | Circularity measurement: planned (P3) |
| ISO 15686-5 | 2017 | Net present cost in life cycle costing |

ISO 14040 and ISO 14044 were last confirmed in 2022 and have no new edition. When the ISO 14067 revision is
published, the carbon footprint report will be updated.

---

## 2. What was added in 1.3.2

| Area | Feature | Priority |
|---|---|---|
| Interpretation | Key findings in plain language (contributors, stages, credits, module D, Monte Carlo interval, burden shifting, best improvement lever, data to improve, costs, errors) in a Summary tab and the report | P0 |
| Data quality | Contribution-weighted data quality rating per category (PEF form) with primary, secondary and estimate shares | P0 |
| Inventory | Data type per line: primary, secondary, estimate | P0 |
| Inventory | Provenance per line: reference, data year, supplier or site, third-party checked; report table and data-age check | P1 |
| Reporting | Review and verification status (draft, internal, expert, panel, verified) in report and checks | P0 |
| Reporting | Report centre: every report with what it still needs | P1 |
| Reporting | Executive summary (two pages) | P1 |
| Reporting | Figures as 300 dpi PNG and SVG | P2 |
| Reporting | Excel sheets for data quality, key findings, costs and water | P2 |
| EPD | ISO 14025:2026 items: audience, specific-data share, months of specific data, prospective EPD, verifier check | P1 |
| Goal and scope | Modelling approach (attributional or consequential) with consistency checks against allocation and database system model | P1 |
| Goal and scope | Technological coverage | P1 |
| Impact assessment | Warning when different versions of one method are mixed | P1 |
| Recycling | Circular Footprint Formula calculator that writes the inventory lines | P1 |
| Databases | Comparison of two databases (e.g. ecoinvent versions) on project datasets or a sample | P1 |
| Databases | Move a model to another database version, with preview and undo | P1 |
| Costing | Life cycle costing with prices per line, sub-models, revenue from credits and discounting | P2 |
| Inventory | Water inventory: withdrawal, release, consumption, turbine water apart | P2 |
| Inventory | Energy balance check for energy products | P2 |
| Uncertainty | Correlated parameters (Gaussian copula) | P2 |
| Uncertainty | Monte Carlo convergence: standard error of the mean and stability of the interval | P2 |
| Comparison | Lowest alternative per category, burden-shifting alert, small-difference alert | P0 |
| Project | Project overview of all models with data quality, review status and results | P2 |

Every new calculation has an automated test; the Circular Footprint Formula test recomputes the formula by
hand.

---

## 2a. Corrections in 1.3.3 (external audit of 1.3.2)

| Audit finding | Priority | Status in 1.3.3 |
|---|---|---|
| Nested models: parameter distributions and line uncertainty not propagated in Monte Carlo | P0 | Fixed: hierarchical Monte Carlo and Sobol over every line and parameter of every nested model |
| Comparisons computed despite different functional units | P0 | Fixed: comparison gate (blocked, screening, valid) with a functional equivalence statement |
| Land use deviation from ecoinvent | P0 | Open: the cause needs a licensed benchmark file; the limitation is now stated in checks and reports |
| EPD: unassigned stages, A1-A3 always declared, no reconciliation | P0 | Fixed: unassigned stages block the EPD, A1-A3 only with lines, module table reconciled |
| DQR: credits weighted, reliability used as precision, nested data ignored | P1 | Fixed: credits apart, pedigree indicator renamed, real PEF DQR from PEF scores, nested paths |
| Improvement advice could propose reducing a credit | P1 | Fixed |
| Different hotspots called burden shifting | P1 | Fixed: wording, plus the effect of the change on every category |
| 5-year limit for producer-specific data missing | P1 | Fixed |
| Correlation entered as rank but used as latent | P1 | Fixed: Spearman conversion |
| Database migration not recursive | P1 | Fixed: all nested models, before/after results, undo |
| Report centre checklist too short | P1 | Fixed: 18 required and several recommended ISO 14044 items |
| Fixed 10 % significance rule; "same random values" claim | P1 | Fixed: Monte Carlo based significance; exact description of what is shared |
| EPD RSL check inverted; EF version by text match; prospective EPD without convergence | P1 | Fixed |

100 automated tests (including one regression test per finding) and the 35-case validation suite pass. The
audit was source-based; an independent numerical comparison with openLCA and Brightway on the same inventory is
planned (section 5).

---

## 2b. Corrections in 1.3.4 (second external audit, of 1.3.3)

| Audit finding | Priority | Status in 1.3.4 |
|---|---|---|
| Land use deviation from ecoinvent | P0 | Still open. New diagnostics: occupation and transformation split, factor change per group, uncharacterised land flows, conflicting factors. Needs a run with a licensed ecoinvent results file |
| Independent numerical cross-check | P0 | Done inside the app (second implementation, other solver): agreement 5.7e-14 on the shipped data; openLCA and Brightway comparison of factor matching still planned |
| Data age not checked in nested models | P1 | Fixed: every nested model, model named |
| Comparison data quality only for the first category | P1 | Fixed: every category |
| System model and approach checks not recursive | P1 | Fixed |
| Nested inventory missing from reports | P1 | Fixed: complete foreground inventory in Word, Excel, EPD Excel and the app |
| EPD resource, waste and output indicators not validated | P1 | Fixed: Tables 4 to 6, units, factors; "not ready for submission" status |
| Allocation management | P1 | Added: allocation overview and physical causality |
| Programme-specific EPD templates | P1 | Partly: PCR version and programme statements; layouts per programme still planned |

## 2c. Added in 1.3.5 (third external audit, of the 1.3.4 roadmap)

The acceptance criteria, tests and demonstration data for every item are in docs/ACCEPTANCE_1.3.5.md.

| Requested | Status in 1.3.5 |
|---|---|
| Factor matching validation against openLCA and Brightway | Done: flow-by-flow comparison with openLCA JSON-LD, a Brightway export script and CSV; effect on every model; split of result differences. Not yet run on a real openLCA or Brightway installation |
| Programme-specific EPD templates | Done as profiles (EPD International, IBU, INIES, custom JSON) that set the Word layout, fields, statements and checks. Drafts, not approved by the operators |
| EF dataset DQR | Done for ILCD/EF imports |
| Grouped results tabs | Done |
| Consequential marginal-supplier guidance | Done: constrained suppliers excluded, proposal, consequential scenario in one step |
| More complete LCC | Partly: cost types, replacements within a study period. Residual value and escalation are not done |
| AWARE 2.0 | Done as a regionalised method engine; official factors must be imported |
| LANCA | Done as a regionalised method engine; official factors must be imported |
| Social LCA | Done as a risk-hour screening; PSILCA/SOCA data must be imported |
| MFA | Done: dynamic MFA with stocks, lifetimes, loops and mass balance; MCI |
| IMPACT World+, official USEtox 2, biodiversity, multi-user, dynamic characterisation beyond climate | Not implemented |
| Advanced regionalisation | Partly: sub-national codes with fallbacks in AWARE and LANCA |

---

## 2d. 1.3.6 (audits of 1.3.5)

Database integrity and scientific reliability fixes; every finding, fix and test is in docs/ACCEPTANCE_1.3.6.md.
Still open from those audits: native PSILCA/SOCA import, AWARE monthly and GIS factors, LANCA SQI aggregation,
ILCD+EPD export, visual MFA builder and MFA-LCA link, staging database and streaming import, published
openLCA/Brightway comparison, confirmation of the land use cause with a new benchmark run.

---

## 2e. 1.3.7

The open items of 1.3.6 (docs/ACCEPTANCE_1.3.7.md): ILCD+EPD export, PSILCA/SOCA import, AWARE monthly and GIS,
LANCA SQI aggregation, MFA builder and MFA-LCA link, staging imports, comparison kit. Still open: the Brightway and
openLCA runs with the kit, ILCD+EPD 1.3 elements, MFA flows as inventory lines, streaming of very large imports.

## 2f. 1.3.8

Database integrity release (docs/ACCEPTANCE_1.3.8.md): non-finite values rejected everywhere in an import, explicit
openLCA providers outside the import kept unresolved, Database Check scoped to the selected database, explorer
filters in the query with paging and export, streaming imports, import integrity report, rollback tests. Still open
(audit P2): database comparison dashboard, supplier relationship view, update notifications, duplicate dataset
detection, quality filters in the explorer; a full ecoinvent import benchmark on the user's machine.

## 2g. 1.3.9

Inventory check against ecoinvent's cumulative LCI: each deviation of the benchmark is split into an inventory and a
factor part, so the cause of the land use deviation is measured on the user's machine.

## 2h. 1.3.10

The measured cause (100 % inventory) was the cut-off of small scaling factors in the solve; removed. Open: the
user's re-run of the benchmark with 1.3.10.

---

## 3. Existing features by LCA phase

**Goal and scope**: functional unit and reference flow, boundary (gate-to-gate, cradle-to-gate, -grave,
-cradle), stage systems (EN 15804, general, agriculture), geography, period, technology, approach, cut-off,
allocation (mass, economic, energy, manual), data quality requirements, assumptions, comparative assertion,
review status, templates for several sectors.

**Inventory**: datasets, elementary flows, other models (nested), EPD values; units with conversion;
formulas and parameters; avoided products; module D; year of emission; pedigree, data type, provenance and
price per line; import from papers, Word, PDF and Excel; external model emissions; Circular Footprint Formula;
flow diagram; comments; versions, undo and lock; mass and energy balance checks.

**Impact assessment**: EF 3.1 with JRC normalisation and weighting, ReCiPe 2016, CML-IA, IPCC 2021 split per
EN 15804+A2, any CSV method, flow mapping, regional and site factors, toxicity screening factors and coverage,
dynamic GWP, background scenarios (prospective and consequential, premise and Activity Browser files).

**Interpretation**: Summary with findings and data quality, contributions by line, process, flow and stage,
supply-chain tree and Sankey, sensitivity (lines, pedigree ranges, parameters, Sobol), Monte Carlo (foreground
or full, comparative, convergence, correlated parameters), map, parameter sweeps, optimisation and Pareto
fronts, PEF most relevant results, inventory results, water and costs, ISO 14044 checks, model and scenario
comparison.

**Reporting**: ISO 14044 Word report, executive summary, Excel workbook, methods paragraph, figures, EPD,
ISO 14067, GHG Protocol, critical review checklist, reproducibility bundle, export to Brightway and openLCA.

**Trust**: validation suite with exact answers, benchmark against ecoinvent's own LCIA results, factor finder,
database and method fingerprints.

---

## 4. Competitor comparison

"Not documented" means the page reviewed did not describe it, not that the product lacks it.

| Feature | Cyclia 1.3.10 | openLCA 2 | SimaPro Expert | Sphera LCA for Experts | Brightway / Activity Browser |
|---|---|---|---|---|---|
| Monte Carlo | Yes, with Sobol, comparative probabilities, correlated parameters, convergence | Yes | Yes | Not documented | Yes, plus global sensitivity analysis |
| Parameters and scenarios | Yes | Yes | Yes | Key parameters through an interface | Yes, with premise scenarios |
| Data quality | Pedigree per line, weighted DQR, primary share, provenance | Custom data quality systems, aggregated in results | Not documented | Not documented | Uncertainty information |
| Regionalisation | Regional factors, map, AWARE and LANCA per process location (factors imported) | Regionalised calculation | Not documented | Not documented | Not documented |
| Social LCA | Risk-hour screening with imported data | Social aspects with PSILCA or SOCA data | Not documented | Not documented | Not documented |
| Life cycle costing | Yes (entered prices, discounting, cost types, replacements) | Manual has an LCC chapter | Not documented | Not documented | Not documented |
| EPD | ISO 14025:2026 and EN 15804+A2 draft and checklist; programme profiles (EPD International, IBU, INIES drafts) | Import and create EPDs | Import scenarios with Report Maker for recurring reports such as EPDs | Used for EPD models (customer case) | Not documented |
| Reports | Report centre, Word, Excel, executive summary, figures | Not documented | Report Maker in Word and Excel | Customisable report templates | Not documented |
| Multi-user | No | Collaboration Server | Multi-user version with central database | Sharing with stakeholders | Not documented |
| Hotspots and burden shifting | Automatic findings | Contribution analysis | Weak-point analysis | Hotspots and burden shifting described | Contribution analysis |
| Database version comparison | Yes | Not documented | Not documented | Not documented | Not documented |
| Validation against reference results | Built-in suite, independent cross-check, ecoinvent benchmark, factor matching against openLCA, Brightway or CSV | Not documented | Not documented | Not documented | Not documented |
| Prebuilt models | Sector templates | Not documented | Not documented | 1,000 prebuilt models | Not documented |
| Price | Free, open source | Free, open source | Commercial | Commercial | Free, open source |

---

## 5. Still planned

| Item | Priority | How it should work | Complexity |
|---|---|---|---|
| Land use deviation | P0 | Cyclia is up to 5 % lower than ecoinvent's LCIA results for some datasets (median 0.4 %); run the land use reconciliation with a licensed ecoinvent results file | M |
| Published openLCA and Brightway comparison | P0 | Export EF 3.1 from openLCA and Brightway, run the factor matching validation, publish the reports in docs/CROSS_VALIDATION.md | S |
| Operator review of EPD profiles | P1 | Ask EPD International, IBU and the FDES-INIES programme to review the profiles; ILCD+EPD XML export | M |
| LCC residual value and escalation | P2 | Residual value at the end of the study period, price escalation per cost type, ISO 15686-5 cost categories | S |
| IMPACT World+ | P2 | Native method with regionalised factors where the licence allows | M |
| Official USEtox 2 | P2 | Official USEtox 2.x factors, tested against the USEtox reference results | M |
| MFA linked to LCA | P2 | MFA flows as inventory lines of a model; cohorts per product type; parameter uncertainty | M |
| Social LCA formats | P3 | Read the PSILCA database format directly; reference-scale methods | M |
| Multi-user projects | P3 | Shared project server with roles and review comments | XL |
| Dynamic characterisation beyond climate | P3 | Time-dependent factors for other categories | L |
| Biodiversity | P3 | Species-loss methods where licences allow | M |
| Code signing | P1 | Signed installers when funding allows (removes the SmartScreen warning) | S |

---

## Sources

- ISO 14025:2026: https://www.iso.org/standard/87610.html
- ISO 14025:2026 changes (EPD International): https://www.environdec.com/news/iso-140252026-is-published
- ISO 14025:2026 changes (Smart EPD): https://smartepd.com/news/iso-140252026-is-here/
- ISO 14044:2006 status: https://www.iso.org/standard/38498.html
- ISO/WD 14067 revision: https://committee.iso.org/standard/90578.html
- ISO/TC 207/SC 5 standards: https://www.isotc207.org/subcomittees-iso/tc-207/sc-5
- openLCA 2 features: https://greendelta.github.io/openLCA2-manual/introduction/openLCA2_features.html
- openLCA data quality: https://greendelta.github.io/openLCA2-manual/advanced_top/data_quality
- openLCA social aspects: https://greendelta.github.io/openLCA2-manual/processes/tab_slca.html
- SimaPro Expert feature sheet: https://simapro.com/wp-content/uploads/2024/05/SimaPro-Expert-31Dec2024.pdf
- Sphera LCA for Experts: https://sphera.com/product-sustainability-software/
- Activity Browser: https://github.com/LCA-ActivityBrowser/activity-browser
- PEF method: Commission Recommendation (EU) 2021/2279
- AWARE: Boulay A.-M. et al. (2018) Int. J. Life Cycle Assess. 23, 368-378
- LANCA: Bos U. et al. (2016) LANCA Characterization Factors for Life Cycle Impact Assessment, Version 2.0. Fraunhofer
- UNEP (2020) Guidelines for Social Life Cycle Assessment of Products and Organizations
- Ellen MacArthur Foundation (2015) Circularity Indicators: methodology
- EPD International GPI 5: https://environdec.com/news/gpi_500
- IBU PCR Part A: https://ibu-epd.com/wp-content/uploads/2026/08/260702_ENG-PCR-Part-AA2_v.1.5.pdf
