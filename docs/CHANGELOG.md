# Changelog

## 1.3.2 (2026-11-05)

Interpretation and data quality
- **Key findings** after every calculation: largest contributors and stage, credits and module D, Monte Carlo
  interval, burden shifting between categories, the change that lowers the result most, data to improve
  first, costs, and errors to fix. New Summary tab (opens first) and report section 4.1
- **Data quality of the results**: contribution-weighted pedigree with a data quality rating per category in
  the PEF form, and the share of primary, secondary and estimated data
- Inventory lines can be marked **primary, secondary or estimate**, and have **details**: reference, data year,
  supplier or site, third-party checked, price. Data older than 10 years raise a warning
- **Compare** names the lowest alternative per category and flags burden shifting and small differences

New analyses
- **Life cycle costing**: prices per line, costs of sub-models, revenue from credits, discount rate and net
  present cost; cost hotspot compared with the environmental hotspot
- **Circular Footprint Formula** (PEF): enter A, B, R1, R2, R3, Q and energy recovery values; Cyclia writes the
  virgin, recycled, recycling, energy recovery, credit and disposal lines
- **Water inventory**: withdrawal, release and consumption, with hydropower turbine water apart
- **Correlated parameters** in Monte Carlo, and a **convergence** check of every run
- **Database versions** (Toolbox): compare two databases on the datasets of your project or a sample, and move
  a model to the new version with preview and undo
- **Project overview** (Toolbox): all models with data quality, review status and results

Goal, scope and checks
- Modelling approach (attributional or consequential) with checks against allocation and the database system
  model; technological coverage
- Warning when different versions of the same impact method are mixed; energy balance check

Reports and standards
- **Report centre** in step 6: every report with what it still needs
- **Executive summary** (Word, two pages) and **figures for journals** (300 dpi PNG and SVG)
- **Review and verification status** in the report; public comparative assertions need a panel review
  (ISO 14044 6.4, ISO 14071:2024)
- **EPD updated to ISO 14025:2026**: intended audience, share of the GWP result from supply-chain-specific
  data, months of specific data, prospective EPDs with quantified uncertainty, named verifier for B2C EPDs
- Excel export: data quality, key findings, costs and water sheets
- References updated (ISO 14025:2026, ISO 14020:2022, ISO 14071:2024, ISO/TS 14074:2022)
- DOI for all versions: 10.5281/zenodo.23853747
- docs/ROADMAP.md: standards, feature status, competitor comparison and plan
- 85 automated tests

## 1.3.1 (2026-11-01)

- Step 1 redesigned: an "open project" card at the top, then tabs for projects, databases, impact methods and
  checks; projects as cards with the open one clearly marked; databases and methods as cards with chips;
  the list of sources appears only after "Add a database" / "Add methods"
- A finished step folds its guidance card away, so the work area comes first
- The project list shows the number of models and when each project was last saved
- Citation and DOI updated to 10.5281/zenodo.23853747 in the app and the reports

## 1.3.0 (2026-11-01)

- **Automatic updates fixed on Windows**: the build no longer asks the updater to verify a code signature
  that unsigned installers cannot have. Help > About shows the update state with "Check for updates";
  checks run at start and every six hours. Copies of 1.2.x must install 1.3.0 once by hand
- **Correction: waste treatment datasets.** In ecoinvent a treatment dataset has a reference amount of -1 kg
  (it "produces" minus 1 kg of waste). A positive amount of waste sent to such a dataset was counted as a
  credit instead of a burden. It is now counted correctly. New validation case V35 checks it. Please
  recalculate models that use ecoinvent waste treatment datasets.
- Complete user guide (docs/USER_GUIDE.md), also inside the app: Help > User guide, with search, and a
  "Guide" link on every step that opens the right section
- Impact assessment: "Select climate change" for a quick start; main indicators listed before their parts
  (total before biogenic and fossil)
- Inventory: notice when a dataset is a waste treatment; transport helper (kg and km to t*km)
- Goal and scope: data quality requirements (ISO 14044 4.2.3.6), in the report and the checks
- Tutorial database extended from 16 to 33 processes: building materials, food (fertiliser, wheat, flour,
  bread), textiles (cotton to T-shirt), plastics (PE, PET, bottle), energy (PV, low-voltage electricity) and
  waste and water (incineration, landfill, wastewater treatment)
- New templates: cotton T-shirt, wastewater treatment per m3, chemical product at the plant gate
- Guidance examples now come from different sectors, not only buildings
- Design: softer cards, pill tabs, calmer header, subtle page transitions, icons on the welcome screen;
  decorative yellow lines removed from the app, splash and installer

## 1.2.3 (2026-11-01)

- Reverted the 1.2.2 rule that applied "unspecified" factors to other subcompartments. The benchmark showed
  that ecoinvent does not do this (long-term and ocean emissions keep no factor), and it caused large
  deviations in the toxicity and freshwater eutrophication categories
- Matched factors are rebuilt once after the update, so nothing from the 1.2.2 rule stays in the library
- Factor finder considers only flows the method knows by name, which removes implausible suggestions

## 1.2.2 (2026-11-01)

- Impact assessment: a factor for the subcompartment "unspecified" now also applies to the other
  subcompartments of that compartment that have no factor of their own (ecoinvent and SimaPro convention).
  This closes gaps to ecoinvent for, among others, radionuclides emitted to water
- ecoinvent LCIA files with a location column are read with their regional factors
- ecoinvent benchmark: compares with global factors only, as ecoinvent's published results are not regionalised
- Benchmark: new factor finder that names the flows whose factor differs from the one ecoinvent uses,
  with the factor that fits ecoinvent's results ("Factor finder" sheet in the Excel report)

## 1.2.1 (2026-11-01)

- macOS installer (Apple silicon) now builds and is published with each release
- DOI shown in the app, the citation and every report
- Release tooling: `engine/tools/new_version.py`

## 1.2.0 (2026-11-01)

A full feature demo (Step 1, "Load the full demo"); a validation suite with 34 exact reference cases and a
Word report; reproducibility bundles with database and method fingerprints; prospective and consequential
background scenarios with a marginal supplier finder; screening toxicity factors for own chemicals (Level
III fate model with USEtox-style exposure and effect); site-specific factors; toxicity coverage; emissions
from external models; a map of impacts by location; inventory from papers and tables (PDF, Word, Excel,
pasted text); parameter sweeps, optimisation and Pareto fronts; model templates (building, packaging,
food, energy) and own templates; comments, named versions with differences, and model locks; EN 15804+A2
EPD with checklist; PEF most relevant results; ISO 14067 report; GHG Protocol workbook; ISO 14044 critical
review checklist; Brightway export and import; openLCA JSON-LD export; Python and R clients; teaching mode
with exercises and an answer key. Official EF 3.1 normalisation and weighting factors (JRC); import of
official USEtox and other factor tables by CAS number; premise and Activity Browser scenario files as
background scenarios; openLCA export with the source database's product flow identifiers and providers;
real country outlines on the results map (downloaded from Natural Earth during the build).

Interface: welcome screen with guided first study, step-by-step guidance with checklists on every step,
progress indicator, new visual design with bundled Inter font, dark mode, new logo, start-up splash.
Open source under the MIT licence; author credits and citation in the installer, the app and every report.

## 1.1.0

Shared database library and portable project files; cross-database linking of missing suppliers; flow
mapping and automatic re-matching of factors; method packages (EF 3.1, ReCiPe) from JSON-LD; built-in
IPCC 2021 GWP100 split per EN 15804+A2; regional factors; SimaPro CSV, ILCD and ecoSpold1 imports;
parameters, formulas and scenarios; editable copies of datasets and dataset replacement; co-product
allocation; EPD lines; EN 15804 module D; biogenic carbon; dynamic GWP; LCI results and flows without
factors; supply chain tree and flow chart; flow diagram; Sobol indices; parameter sensitivity and
parameter Monte Carlo; scenario comparison; database check and benchmark tool; mass-balance check; undo;
help, glossary and guided tutorial; diagnostics export; auto-update; signing and notarization setup.
