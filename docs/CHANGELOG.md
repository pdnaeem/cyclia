# Changelog

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
