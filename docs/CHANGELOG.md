# Changelog

## 1.3.9 (2026-11-05)

Finding the cause of the land use deviation in the ecoinvent benchmark. Details: docs/ACCEPTANCE_1.3.9.md.

- **Inventory check against ecoinvent's cumulative LCI**: validation can also download ecoinvent's cumulative LCI
  (option "Compare inventories too", on by default; or choose the file for a manual benchmark). The gap of every
  result is split into an inventory part (Cyclia's factors times the difference of the cumulative inventories) and a
  factor part (ecoinvent's result minus Cyclia's factors times ecoinvent's own inventory). Each deviating category
  gets a measured cause: inventory (an import or linking difference, with the flows that carry it), factors
  (ecoinvent's results use factors that are not in its LCIA implementation file, with the factors they imply), or
  both. New sheets in the Excel report: "Cause of deviations" and "Inventory check".
- The LCI workbook is read as a stream of XML rows; only the compared datasets are kept.
- **Corrected hint**: "Cyclia is lower ... N flows used by the database have no factor" pointed to the wrong cause.
  Most flows of a database never have a factor in a given category, also in categories that agree exactly (climate
  change: 3,270 such flows and 100 % within 0.1 %). The hint now says which check measures the cause.
- 199 automated tests (3 new).

## 1.3.8 (2026-11-05)

Database integrity release: the findings of the third database audit (of 1.3.6). Details, tests and limits:
docs/ACCEPTANCE_1.3.8.md.

- **Non-finite values are rejected** (audit P0 A): the import check now covers unresolved-input amounts,
  uncertainty parameters p1 to p3, uncertainty types, production amounts and references to missing datasets and
  flows, besides technosphere and elementary amounts. Linking refuses inputs with a non-finite amount. The Database
  Check reports the same problems as an error.
- **An explicit openLCA provider is kept** (audit P0 B): an input whose defaultProvider is not in the import stays
  unresolved with the provider's name and id, and is never linked to another producer of the same product. Auto-link
  leaves it alone; the suggestion list ranks the named provider first when it is in another database of the library.
- **Database Check of one database** (audit P1 C): elementary-flow coverage, unit consistency, LCIA compatibility and
  the counts use the flows and exchanges of the selected database only.
- **Database Explorer**: every filter runs in the database query (unresolved-only no longer misses datasets beyond
  the first 100), paging with the total, filters for location, system model, version and elementary flow, and
  export of selected datasets to Excel (datasets, inputs, elementary flows, unresolved inputs).
- **Streaming imports**: SimaPro CSV is read row by row with one process in memory at a time; SimaPro, ecoSpold1
  and ILCD write datasets as they are read and elementary exchanges in batches; JSON-LD no longer keeps the process
  documents. Measured on a synthetic SimaPro file of 200,000 processes (46 MB): peak memory 1,117 MB in 1.3.7,
  360 MB in 1.3.8.
- **Import integrity report**: after a format import, the counts of the staged database, the checks run and the
  largest matrix residual are shown and stored in the database's import report.
- **Rollback tests**: a failure while reading and a failure inside the merge transaction leave the library as it was.
- 196 automated tests (12 new).

## 1.3.7 (2026-11-05)

The open items of 1.3.6. Details, tests and limits: docs/ACCEPTANCE_1.3.7.md.

- **ILCD+EPD export**: the EPD as an ILCD+EPD 1.2 dataset with the authoritative EN 15804+A2 (EF 3.1) indicator
  identifiers of the InData network, validated against the official XSD schemas (shipped with Cyclia).
- **PSILCA and SOCA**: native import of social data in openLCA JSON-LD (indicators, activity values, risk levels,
  raw values, quality), with a mapping table for PSILCA sectors.
- **AWARE**: monthly factors with a monthly water use profile, and watershed polygons (GeoJSON) located from the
  site's coordinates.
- **LANCA**: soil quality index aggregated from the four LANCA indicators (normalisation references entered by the
  user), compared with official SQI factors.
- **MFA**: visual builder (tables and a diagram with draggable boxes) and MFA linked to the LCA: impacts of the
  material system year by year from linked datasets or models.
- **Staging imports**: format imports go into a separate staging library and are merged into the library only after
  the checks pass, in one transaction.
- **Comparison kit** for Brightway and openLCA: data as tables and JSON-LD, Cyclia's results, scripts for an
  independent numpy solve, Brightway, openLCA 2 (IPC) and a comparison report.
- 184 automated tests (17 new).

Not done: the comparison with real Brightway and openLCA installations still has to be run (the kit is ready); the
SQI normalisation references are not shipped; ILCD+EPD 1.3 (2024) elements are not written.

## 1.3.6 (2026-11-05)

Database integrity and scientific reliability release, after two external audits of 1.3.5 and the user's
ecoinvent benchmark. Every item has a regression test that fails on 1.3.5 (engine/tests/test_v136.py). Details:
docs/ACCEPTANCE_1.3.6.md.

Fixed (results could be wrong)
- SimaPro import merged two processes with the same product and location (two routes became one dataset with
  added emissions). Processes are now identified by process identifier or name; duplicates are kept separate
  and reported (also for ecoSpold1 and ILCD).
- When several datasets of an import produced the same product, the first one was used as supplier. Such inputs
  are now "ambiguous", with the candidates, for the user to choose (SimaPro, ecoSpold1, ILCD, openLCA JSON-LD).
- ecoSpold2 inputs without activityLinkId disappeared without a record. They are kept as unresolved inputs.
- Linking missing suppliers grouped all locations together; one click gave France, Germany and Poland the same
  supplier. Groups and links are now per location; automatic linking needs exactly one supplier at that location.
- Factor matching validation could PASS with unresolved external flows, ambiguous matches, wrong units or
  conflicting factors, and one external category could be paired with several Cyclia categories. PASS now needs
  no open item; pairing is one to one; convertible units are converted.
- AWARE subtracted evaporated water (and water to soil) as if returned. Only releases to fresh water are
  subtracted; evaporation, discharge to the sea and to soil are consumption. The water balance is shown.
- AWARE never found the non-agricultural factor (stored as 'non-agri', looked up as 'non_agri') and used the
  unknown factor. Fixed; supply-chain processes are now classified per process (irrigation agricultural, other
  processes non-agricultural, option unknown).
- Social LCA coverage was always 100 %. Process coverage is reported; worker-hour coverage only with a default
  row that estimates the processes without data. Avoided products no longer reduce the hours of shared processes.
- MFA recirculated inflow share was divided by all external inflows of the system instead of the production
  process input.
- LANCA multiplied amounts and factors without unit check (1 ha*a counted as 1 m2*a). Factor units are validated,
  amounts converted; soil organic carbon accepted.
- EPD: HTP-c and HTP-nc were not recognised under the EF 3.1 names ('carcinogenic'); toxicity sub-categories
  could be taken for the indicator. Units of the additional indicators are checked.
- The ecoinvent benchmark said "Validated" while one category (land use) was up to 14 % off. The verdict now names
  every category that does not agree.

Added
- Database check in six statuses: matrix, technosphere completeness, elementary-flow coverage, units, metadata
  and LCIA compatibility.
- Database provenance: source file SHA-256, importer version, import report and editable metadata (version,
  system model, release date, geography, technology, licence, reference period, citation). Imports are all or
  nothing, with an integrity check after import.
- Database explorer (Toolbox): identity, suppliers, users, unresolved inputs, elementary flows with uncertainty,
  data quality; navigation along the supply chain.
- Land use coverage in every result, with a warning when land flows have no factor; targeted benchmark test of
  land flows without a factor (implied factors and share of the gap explained).
- MCI per year computed from the MFA.

Tests
- 167 automated tests (30 new).

Not done
- Native PSILCA/SOCA import, AWARE monthly and GIS watershed factors, ILCD+EPD XML, visual MFA builder and MFA-LCA
  link, a staging database separate from the library, streaming import of very large files, operator approval of
  the EPD profiles, a published openLCA/Brightway comparison. The cause of the land use difference is narrowed down
  but not confirmed (see docs/ACCEPTANCE_1.3.6.md).

## 1.3.5 (2026-11-05)

New features after a third external audit (of the 1.3.4 roadmap). Acceptance criteria, tests and demonstration
data for each one: docs/ACCEPTANCE_1.3.5.md.

Validation
- **Factor matching validation** (Toolbox > Validation): Cyclia's characterisation factors are compared flow by
  flow with an openLCA JSON-LD export of the method, a Brightway export (`engine/tools/brightway_export_factors.py`)
  or a CSV. Each flow is shown as same, different, only in Cyclia or only in the other tool, with unresolved,
  ambiguous, unit and conflicting rows counted. The report shows the effect of each difference on every model and,
  with the other tool's results, splits the result difference into the factor part and the rest. Excel report.
  Demonstration files in docs/examples.

EPD
- **Programme layouts**: Cyclia generic, the International EPD System (GPI 5), IBU and INIES FDES (in French).
  Each sets the order of sections in the Word EPD, extra fields, mandatory statements, required indicators and
  maximum validity, and the checklist checks them. These are drafts modelled on published EPDs, not approved by
  the programme operators.
- Custom profiles: export a profile as JSON, edit it and load it (step 6 > EPD > Your own programme profile).

Data quality
- The data quality indicators of ILCD and EF datasets (TeR, GeR, TiR, P) are read on import and used for lines
  without PEF scores; the share of the result scored this way is shown.

Consequential modelling
- **Marginal supplier guidance** (Toolbox > Background scenarios): markets of the open model with their
  suppliers, constrained suppliers marked, a proposal, and a consequential scenario made from the choices.

Costs
- Cost types (capital, operating, maintenance, replacement, end of life), replacement intervals and a study
  period; results by cost type.

New methods and tools (factors and data are imported, none are shipped)
- **AWARE** water scarcity per process location with sub-national, country and world fallbacks, agricultural
  use for irrigation, a location and type of use for the model's own water, and completeness.
- **LANCA** land use per process location for occupation and transformation, with five indicators plus the soil
  quality index, and land flows without a factor listed.
- **Social LCA**: risk-hour screening per stakeholder and indicator (UNEP 2020, ISO 14075:2024 categories) with
  hotspots, coverage and processes without data.
- **Material flows**: dynamic MFA with in-use stocks (fixed, normal or Weibull lifetimes), sinks, recycling
  loops and a mass balance every year; recycling rate and recycled content; Material Circularity Indicator.
- A model without water or land flows is reported as having nothing to characterise.

Interface
- Results tabs grouped: the main analyses in front, Dynamic climate, Map, Explore parameters and PEF under
  "More analyses".

Fixed
- The independent cross-check failed on macOS (and the macOS installer was not built) because a model result
  that cancels to about zero turned 1e-14 of round-off into a relative difference of 6e-5. Differences are now
  measured against at least 1e-9 of the largest result of the category, and the iterative solver refines until
  the residual stops improving.

Tests
- 137 automated tests (24 new for 1.3.5, including the shipped demonstration files).

Not in 1.3.5
- IMPACT World+, official USEtox 2 factors, biodiversity, multi-user projects and dynamic characterisation beyond
  climate are not implemented. The factor matching validation has not yet been run on a real openLCA or Brightway
  installation. The land use deviation from ecoinvent is still open.

## 1.3.4 (2026-11-05)

Corrections and additions after a second external audit (of 1.3.3).

Validation
- **Independent cross-check** (Toolbox > Validation): datasets and models are recalculated along a second code path
  (matrices rebuilt from the library tables, LAPACK dense LU or GMRES instead of the engine's SuperLU, separate
  flattening of nested models) and compared; Excel report. Results on the shipped data: docs/CROSS_VALIDATION.md
- **Land use reconciliation** in the ecoinvent benchmark: split into occupation and transformation, the factor
  change per group that explains the gap, and land flows without a factor
- **Conflicting factors**: the benchmark lists flows that have two different factors in the method file

Nested models everywhere
- Data age (5 and 10 years), missing data years, data outside the study period and default data quality are now
  checked in every nested model, with the model named
- System models and the attributional or consequential approach are checked across all nested models
- **Complete foreground inventory**: every line of every nested model with its amount per unit and per
  functional unit, data type, year, supplier, reference, verification and pedigree, in a Word annex, an Excel
  sheet, the EPD Excel file and the Inventory results tab (toggle between this model and the complete supply chain)

Comparisons
- Data quality is compared per impact category, not only for the first category
- Background system models are compared across nested models

EPD
- The resource use, waste and output flow indicators of EN 15804+A2 Tables 4 to 6 (PERE to EET) are recognised
  and checked; units of core and inventory indicators are checked; indicators without factors are listed
- Drafts can always be created, but the EPD shows "not ready for submission" while requirements are open
- PCR version and the mandatory statements of your programme operator can be entered

Allocation
- **Physical causality** as an allocation basis, with the property named
- **Allocation overview** (Toolbox): every model with its rule, share, co-products, avoided products, module D,
  where it is used and what to check

- 113 automated tests

## 1.3.3 (2026-11-05)

Scientific corrections after an external expert audit of 1.3.2. Please recalculate studies that use nested
models, Monte Carlo, comparisons, data quality or EPDs.

Uncertainty
- **Nested models in Monte Carlo and Sobol**: every line of every nested model now has its own data-quality
  uncertainty, and the parameter distributions and correlations of nested models are sampled. Before, only the
  top-level lines and parameters were uncertain, so the spread of complex supply chains was too small
- **Correlations are Spearman rank correlations as stated**: the value is converted for the Gaussian copula
  (2 sin(πρ/6)); before, an entered 0.8 gave about 0.79
- **Paired comparisons**: lines and parameters that compared models share (e.g. the same sub-model) use the same
  random values; the note says exactly what is shared
- Convergence judged against the width of the 95 % interval

Comparisons
- **Comparison gate**: different functional units block the comparison; differences in boundary, stages,
  allocation, approach, geography, period, background data and data quality are listed; without a functional
  equivalence statement the result is labelled a screening comparison, not a comparative assertion
- The fixed 10 % rule is replaced by the comparative Monte Carlo (robust when one alternative is lower in at
  least 95 % of the runs), with the 95 % interval of the difference
- Scenario comparison lists the categories that go up and down (burden shifting)

Data quality
- Credits (avoided products) are no longer part of the data quality weights; their share is shown apart
- Nested models: the data quality of their lines now counts, path by path (weakest link)
- The pedigree-based rating is called a pedigree indicator and is no longer presented as a PEF DQR; a real PEF
  DQR is computed from the four PEF scores (TeR, GeR, TiR, P) you can now enter per line
- Producer-specific data: 5-year limit (other data: 10 years); primary data outside the study period and lines
  without a data year are listed

Interpretation
- Improvement advice no longer proposes reducing a credit (it raised the result); credits get their own finding
- Different hotspots in different categories are no longer called burden shifting; the improvement finding
  shows whether the same change would raise another category

EPD
- Lines whose stage is not an EN 15804 module now block the EPD (their impacts were missing from the table)
- A1-A3 is no longer declared without lines; the module table is reconciled with the LCA result
- Reference service life check fixed (it was inverted); EF reference package checked by version (3.0 or later)
- Prospective EPDs need a converged Monte Carlo run; the specific-data share includes nested models and leaves
  credits out
- EPD Excel shows impacts outside modules and the LCA totals for reconciliation

Other
- **Database migration** now includes all nested models, shows results before and after, and can be undone at
  once
- **Report centre**: the ISO 14044 report checks 18 required and several recommended items one by one
- Land use results calculated with ecoinvent carry the known benchmark limitation in the checks and report
- 100 automated tests

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
