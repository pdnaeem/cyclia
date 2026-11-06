# Changelog

## 1.7.0 (2026-11-06)

Advanced environmental LCA, first part. Details, tests and limits: docs/quality/ACCEPTANCE_1.7.0.md.

- **Life cycle costing per ISO 15686-5.** Residual value of the last purchase at the end of the study period (on
  by default; it can be switched off), real price escalation per cost type, price uncertainty per line with a
  Monte Carlo interval of the net present cost, and the ISO 15686-5 cost categories. Results that use a
  replacement interval within a study period now include the residual value; switch it off to reproduce earlier
  results.
- **MFA integrated with LCA.** The production process can be charged on its virgin input only, recycling
  processes on their throughput, and recovered material earns a credit with a substitution ratio. Results by
  role (primary supply, production and use, recycling, losses, credits), gross and net, per year and cumulative.
- **Social LCA subcategory assessment (Type I, UNEP 2020).** Stakeholder categories and subcategories, scores
  against performance reference points from -2 to +2, activity-variable weighting, coverage, share of
  site-specific data, hotspots and missing subcategories. The risk screening stays a screening.
- **Allocation choices of a model, side by side.** Mass, economic, energy, physical, manual and no allocation.
- **Factor package checks.** Imported AWARE, LANCA and USEtox packages are checked for completeness, units, ranges,
  fallbacks and source, and shown in the Benchmark Centre as "Package checked" or with what is missing, never as
  "Validated".
- **Report.** The Word report has an annex with the Benchmark Centre table and the ISO 14044 critical review
  checklist, checked automatically from the study.

## 1.6.2 (2026-11-06)

Scientific reliability release. Details, tests and limits: docs/quality/ACCEPTANCE_1.6.2.md.

- **Corrected: factors carried forward after a flow change.** When a custom flow's compartment (or name,
  subcompartment or CAS number) changed, the factors given for it stayed in use, so a factor for an emission to air
  could apply to water. These factors are now put under review: not used, and the result marked incomplete, until
  they are confirmed or corrected.
- **Parameter uncertainty.** Parameters of your own data can have distributions; the full Monte Carlo draws them
  and recalculates every formula in each iteration, with one shared draw per database parameter.
- **Versions, undo and restore.** Every change of a process keeps the state before and after: undo (and redo),
  restore any version, restore deleted processes. Each process lists the processes and the models of every
  project that depend on it.
- **Allocation.** Physical causality, economic allocation with currency and price year, and a comparison of the
  results per unit of each product under every allocation method.
- **Scientific Benchmark Centre** (Toolbox > Validation): all validation evidence in one table with reference,
  result, differences, missing flows and status. Only checks that ran and passed count. New IPCC 2021 check:
  14 gases reproduce the published AR6 GWP100 values.
- **Model inventory in the diagram.** Move lines between stages (or to a new stage), change amounts, toggle
  credits and remove lines by drawing.
- **Recursive provenance.** The Excel workbook lists every dataset of the supply chain with database, version,
  identifier, amount and direct contribution, and the Word report summarises it.
- **Safeguards.** Mass balance and order-of-magnitude warnings in the database check; a decimal comma is
  recognised and explained.
- **Validation workflow.** On every change the tests run on Windows, macOS and Linux, Brightway is installed at the
  validated commits and its comparison may not be skipped, and the validation suite and the IPCC check must pass.
- The Toolbox tab "Social LCA" is now called "Social screening", which is what it does.

- **Steadier screen.** The sticky header at the top of each step used a background blur. On some graphics drivers
  Chromium re-composited it every few seconds, which looked like a faint blink; the header is now opaque. The
  welcome overlay no longer uses a blur either.
- **Narrow windows.** At the smallest window width (1000 px) the inventory and the background scenario editor
  were wider than the window (a hidden table label and a wide rule table); both now stay inside it.
- In the supply chain diagram, long names end with an ellipsis instead of being cut mid-word.

## 1.6.1 (2026-11-06)

Corrections from the review of 1.6.0, editing, and guidance. Details: docs/quality/ACCEPTANCE_1.6.1.md.

- **Custom methods: missing factors were taken as zero for library flows.** A library flow (for example methane)
  in the inventory without a factor in a custom method was neither counted nor reported. Such a flow is now an
  unknown factor: the result is marked incomplete and the flow is listed, until a factor or a "does not apply"
  decision is recorded. A custom method can instead state, with the reason, that flows without a factor have no
  effect, as published methods do.
- **A factor of zero recorded with its source was reported as missing.** Whether a factor is known now depends on
  the recorded factor or the method's own factor list, not on its value. Zero factors of installed methods count as
  known too.
- **Editing.** Products, elementary flows, lines of a process and factors can be edited in the interface.
  Renaming a product updates the datasets that make it. Editing an elementary flow matches its factors again in
  every method. Library flows cannot be edited.
- **Provenance per line.** Each line of a process records its author and revision. A change history lists every
  creation, change and deletion with time and author.
- **Placement and guidance.** "Your own data" is the second Toolbox tab and is reached from step 1 (Add a
  database) and step 3 (Inventory). The tab shows the seven steps with their status, explains each one in plain
  words with an example, and creates a worked example (bread, 0.437 kg CO2-eq per kg, with IPCC AR6 factors). New
  user guide chapter and glossary entries. A selected process can be added to the open model with one click.
- Custom methods can be deleted. The user guide opens at the right section the first time it is opened from a
  link.
- **Parameters and formulas in your own data.** Database and process parameters (values or formulas of other
  parameters), and amounts written as formulas. A change re-evaluates every formula; a change that breaks a
  formula or makes an amount negative is refused and nothing changes.
- **Processes with several products.** Co-products with mass, energy, economic or manual allocation; one dataset
  per product, each with its share of every exchange and its uncertainty. Other processes can use each co-product.
- **Units of your own.** Units in a known kind of quantity (a sack of 50 kg) or a new kind of quantity (a seat,
  with a row of 20 seats); a unit in use cannot change its size. Units, parameters and co-products are part of
  the JSON export.
- **Supply chain diagram.** Drag processes to arrange them, connect a supplier to a process to add an input, click
  an arrow to edit its line. In a model's flow diagram, clicking a box opens its line in the inventory table.

## 1.6.0 (2026-11-06)

Custom data entry. Details, tests and limits: docs/quality/ACCEPTANCE_1.6.0.md.

- **Custom data** (Toolbox > Custom data): build a complete product system in Cyclia, from an empty library if
  needed. Custom databases, product flows, elementary flows (compartment, subcompartment, unit, CAS number),
  processes (reference product and amount, production or waste treatment, location, technology, time period,
  data type, PEF data quality ratings), and their exchanges: inputs from a custom process or any library dataset,
  avoided products, waste sent to treatment, emissions and resources.
- **Identifiers and provenance**: every item gets a UUID and keeps its source, author, creation and change time
  and revision. Edited processes keep their dataset id, so models stay linked.
- **Unit validation**: units must be known; an amount is converted to the unit of the flow or supplier only
  within the same dimension (3.6 MJ to 1 kWh, 10 g to 0.01 kg), anything else is refused. Land occupation needs
  m2*a and land transformation m2. CAS numbers are checked with their check digit. A flow that the library
  already has is not created again.
- **Uncertainty**: lognormal (GSD), normal, triangular, uniform or pedigree scores, converted with the amount;
  bounds of avoided products and waste treatment are mirrored with the sign.
- **Characterisation factors**: factors for custom flows in any installed method, and custom methods with
  factors for any flow, each with its source; a factor given per another unit (per g) is converted.
- **Unknown factors are not zero**: a custom flow without a factor and without a recorded "does not apply"
  decision makes the category result incomplete. The result table, the inventory view, the Word report, the
  Excel workbook and the checks list these flows, and the EPD check does not pass.
- **Database check**: integrity, inputs without a supplier, solvability, missing sources and data quality, and
  open factor decisions.
- **Export and import** of a custom database as JSON (identifiers, provenance, exchanges, factors).

## 1.5.0 (2026-11-06)

Stage P0 of the development plan: scientific correctness and reliability. Details, tests and limits:
docs/quality/ACCEPTANCE_1.5.0.md.

- **Comparison with Brightway** (Toolbox > Validation): Brightway's calculation library builds, solves and
  characterises its own matrices from any installed database, ecoinvent included, and every result is compared
  with Cyclia's. Demo, tutorial and synthetic databases of 3,000 and 10,000 datasets agree within 1e-6 (largest
  difference 1.4e-12). The release builds include Brightway and run these tests on Windows, macOS and Linux.
- **Comparison kit**: standalone Brightway script `run_bw2calc.py`. Both Brightway scripts now calculate treatment
  datasets for one unit of waste treated (a demand of -1); before, their sign was opposite to Cyclia's.
- **Comparative LCA**: a conclusion per category from the paired Monte Carlo probability and its sampling error
  (Wilson interval) at 90, 95 or 99 % confidence: A lower, B lower, run more iterations, not distinguishable or no
  difference. Replaces a fixed 95 % share without sampling error.
- **Social LCA screening**: waste sent to a treatment dataset was reported as an avoided product and left out of
  the worker hours; corrected. Credits inside the supply chain are reported as avoided. Processes with different
  worker hours per unit in their data rows are listed.
- **MFA**: the end-of-life recycling rate and the collection rate counted production and imported scrap;
  end-of-life material is now traced through collection and sorting. Collection rate and recycling efficiency are
  reported and used in the MCI.
- **AWARE**: the water balance shows which part of the consumption is identified by an output flow; the result
  note describes the monthly and GIS factors correctly.
- **ecoinvent validation**: option to validate every installed method of ecoinvent's results (ReCiPe 2016, CML-IA,
  IPCC and others), not only EF 3.1.
- Reference tests with analytic or hand-calculated values for comparative probabilities, nested uncertainty and
  data quality, AWARE, LANCA and SQI, social screening, MFA rates and MCI; unique interface ids are tested.
- 227 automated tests (24 new).

## 1.4.2 (2026-11-06)

Documentation, website and in-app wording.

- **In-app text**: messages written for the developer were rewritten for users. Version history was removed
  from import warnings, the database details now show "not recorded" for older imports, and support requests say
  what to check first. The calculation is unchanged.
- **Website**: a landing page for GitHub Pages (`docs/index.html`) with search metadata, structured data
  (SoftwareApplication, FAQ), sitemap and robots file.
- **Repository**: README rewritten with a contents list, a validation table and a documentation index;
  documents sorted into `docs/releases`, `docs/quality` and `docs/maintainers`; new feature status
  (`docs/FEATURE_STATUS.md`), development plan (`docs/DEVELOPMENT_PLAN.md`) and a forward-looking roadmap, with the
  release history moved to `docs/quality/DEVELOPMENT_HISTORY.md`.
- **Community files**: code of conduct, security policy, support page, issue forms for feature requests and
  database imports, and links to Discussions.

## 1.4.1 (2026-11-05)

- **Validation against ecoinvent recorded**: docs/VALIDATION_ECOINVENT.md. 100 % of 2,500 results (100 datasets x
  25 EF v3.1 categories, cut-off) agree with ecoinvent's published results within 0.1 %; median deviation 3.9e-07 %,
  largest 0.0018 %. README updated.
- The benchmark report's Summary sheet now records the compared database (name, version, system model), the methods
  and the names of ecoinvent's results and cumulative LCI files, so a report identifies what it validated.

## 1.4.0 (2026-11-05)

First release with the work of 1.3.8 to 1.3.10 that passes the build on every platform. 1.3.10 failed the macOS
build (test_epd: "the module table does not add up to the LCA result").

- **Cause of the macOS failure**: 1.3.10 stopped cutting small scaling factors (the land use fix). The sparse solve
  can leave round-off of about 1e-17 in datasets that are not in the supply chain at all. On macOS this made
  categories that are zero (land use, freshwater eutrophication of the demo wall) tiny non-zero numbers, and the EPD
  check divided their round-off by the near-zero total. Reproduced on Linux by adding 1e-17 noise to the solve.
- **Fix in the solve**: datasets that are not in the supply chain of the demand (graph search over the exchanges,
  independent of the amounts) get exactly zero. Datasets in the supply chain keep their value however small it is,
  so the land use fix of 1.3.10 stays.
- **Fix in the EPD check**: the gap between the module table and the result is measured relative to the gross size
  of the stage contributions, so a category that cancels to about zero is not blocked by round-off. A real gap is
  still found.
- The whole test suite also passes with simulated solver round-off (except the test that checks a 1e-14 scaling
  factor, whose simulated noise is larger than the value).
- 203 automated tests (3 new).

## 1.3.10 (2026-11-05)

Fix of the land use deviation in the ecoinvent benchmark, found by the 1.3.9 inventory check.

- **Small scaling factors are no longer cut**: the matrix solve set every scaling factor below 1e-13 times the
  largest one to zero, as round-off. In ecoinvent, infrastructure (buildings, mines, offshore platforms, roads)
  enters a supply chain with scaling factors of that order, so its land transformation and occupation, and its
  drilling and mining emissions, were left out. The inventory check against ecoinvent's cumulative LCI showed it:
  land use 100 % inventory part and 0 % factor part; "Transformation, from industrial area" 43 % and
  "Transformation, to unspecified" 38 % higher in ecoinvent's inventory (median over about 90 datasets); ocean
  emissions of aluminium, silicon and titanium 17 to 20 % higher; ecoinvent's inventory with Cyclia's factors gave
  ecoinvent's results in 100 % of the cases. The cut-off is removed from the solve and from the Monte Carlo loop.
- All results can change slightly (they become more complete); land use the most.
- 200 automated tests (1 new).

## 1.3.9 (2026-11-05)

Finding the cause of the land use deviation in the ecoinvent benchmark. Details: docs/quality/ACCEPTANCE_1.3.9.md.

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
docs/quality/ACCEPTANCE_1.3.8.md.

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

The open items of 1.3.6. Details, tests and limits: docs/quality/ACCEPTANCE_1.3.7.md.

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
docs/quality/ACCEPTANCE_1.3.6.md.

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
  but not confirmed (see docs/quality/ACCEPTANCE_1.3.6.md).

## 1.3.5 (2026-11-05)

New features after a third external audit (of the 1.3.4 roadmap). Acceptance criteria, tests and demonstration
data for each one: docs/quality/ACCEPTANCE_1.3.5.md.

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
