# Cyclia roadmap

Version: 1.6.1. Author: Naeem Ur Rehman. This document lists the standards Cyclia follows, its features by LCA
phase, how it compares with other LCA software, and where the plan for future work is. Other programs'
capabilities are listed only where the vendor's own documentation describes them (sources at the end). The
history of earlier releases is in [quality/DEVELOPMENT_HISTORY.md](quality/DEVELOPMENT_HISTORY.md).

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
| ISO 14075 | 2024 | Social LCA: screening of worker and risk hours with PSILCA, SOCA or own data; a full ISO 14075 assessment is planned |
| ISO 59020 | 2024 | Circularity measurement: planned; the Material Circularity Indicator is available |
| ISO 15686-5 | 2017 | Net present cost in life cycle costing |

ISO 14040 and ISO 14044 were last confirmed in 2022 and have no new edition. When the ISO 14067 revision is
published, the carbon footprint report will be updated.

---

## 2. Features by LCA phase

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

## 3. Comparison with other LCA software

"Not documented" means the page reviewed did not describe it, not that the product lacks it.

| Feature | Cyclia 1.6.1 | openLCA 2 | SimaPro Expert | Sphera LCA for Experts | Brightway / Activity Browser |
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
| Validation against reference results | Built-in suite, comparison with Brightway on any database, independent cross-check, ecoinvent benchmark with inventory check, factor matching against openLCA, Brightway or CSV | Not documented | Not documented | Not documented | Not documented |
| Prebuilt models | Sector templates | Not documented | Not documented | 1,000 prebuilt models | Not documented |
| Price | Free, open source | Free, open source | Commercial | Commercial | Free, open source |

---

## 4. Plan

The planned work, in order of priority and with acceptance criteria, is in [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md).
The status of every feature is in [FEATURE_STATUS.md](FEATURE_STATUS.md).

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
