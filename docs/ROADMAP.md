# Cyclia feature assessment and roadmap

Version: 1.3.3. Author: Naeem Ur Rehman. This document lists what Cyclia does, which standards it follows,
what was added in 1.3.2 after a full feature review, what 1.3.3 corrected after an external audit, and what is
still planned. Competitor capabilities are
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

| Feature | Cyclia 1.3.3 | openLCA 2 | SimaPro Expert | Sphera LCA for Experts | Brightway / Activity Browser |
|---|---|---|---|---|---|
| Monte Carlo | Yes, with Sobol, comparative probabilities, correlated parameters, convergence | Yes | Yes | Not documented | Yes, plus global sensitivity analysis |
| Parameters and scenarios | Yes | Yes | Yes | Key parameters through an interface | Yes, with premise scenarios |
| Data quality | Pedigree per line, weighted DQR, primary share, provenance | Custom data quality systems, aggregated in results | Not documented | Not documented | Uncertainty information |
| Regionalisation | Regional factors, map | Regionalised calculation | Not documented | Not documented | Not documented |
| Social LCA | No (planned) | Social aspects with PSILCA or SOCA data | Not documented | Not documented | Not documented |
| Life cycle costing | Yes (entered prices, discounting) | Manual has an LCC chapter | Not documented | Not documented | Not documented |
| EPD | ISO 14025:2026 and EN 15804+A2 draft and checklist | Import and create EPDs | Import scenarios with Report Maker for recurring reports such as EPDs | Used for EPD models (customer case) | Not documented |
| Reports | Report centre, Word, Excel, executive summary, figures | Not documented | Report Maker in Word and Excel | Customisable report templates | Not documented |
| Multi-user | No | Collaboration Server | Multi-user version with central database | Sharing with stakeholders | Not documented |
| Hotspots and burden shifting | Automatic findings | Contribution analysis | Weak-point analysis | Hotspots and burden shifting described | Contribution analysis |
| Database version comparison | Yes | Not documented | Not documented | Not documented | Not documented |
| Validation against reference results | Built-in suite and ecoinvent benchmark | Not documented | Not documented | Not documented | Not documented |
| Prebuilt models | Sector templates | Not documented | Not documented | 1,000 prebuilt models | Not documented |
| Price | Free, open source | Free, open source | Commercial | Commercial | Free, open source |

---

## 5. Still planned

| Item | Priority | How it should work | Complexity |
|---|---|---|---|
| Land use deviation | P0 | Cyclia is up to 5 % lower than ecoinvent's LCIA results for some datasets (median 0.4 %); trace the transformation flows with the benchmark workbook | M |
| Independent numerical cross-check | P0 | The same inventories calculated in openLCA and Brightway, published as a validation report | M |
| EPD programme templates | P1 | Word templates per programme operator (layout and mandatory statements of each programme) | M |
| Consequential guidance | P1 | Marginal supplier finder per market linked to the modelling approach | M |
| Dataset DQR from EF datasets | P2 | Read the TeR, GeR, TiR and P of ILCD/EF datasets and combine them with the foreground PEF scores | M |
| Basin-level water footprint | P2 | Water scarcity by location of the withdrawal (AWARE) on top of the water inventory | M |
| Allocation manager | P1 | One table of every multi-output process in the project with its rule and shares; physical causality by a user-defined property | M |
| Grouped results tabs | P2 | Keep Summary, Contributions, Checks and Compare in front; group the rest under "More analyses" | S |
| Further LCIA methods | P2 | AWARE 2.0 for water scarcity, IMPACT World+, LANCA land use, official USEtox 2 factors, where licences allow redistribution; until then through CSV import | M each |
| Social LCA (ISO 14075:2024) | P3 | Import PSILCA or SOCA data when the user has a licence; risk hotspots per working hour | XL |
| Material flow analysis | P3 | Mass flows per functional unit as a Sankey with stocks and recycling loops; ISO 59020 circularity indicators | L |
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
