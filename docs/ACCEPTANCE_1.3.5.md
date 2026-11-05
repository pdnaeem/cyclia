# Cyclia 1.3.5: acceptance criteria and status per feature

This file answers the third external audit (of 1.3.4). For each requested feature it gives the code, the tests,
the demonstration data and the acceptance criteria, and says plainly what is not done. A feature is "Done" only
when it has its own code, its own tests and a demonstration that can be repeated. Importing numbers through a
generic CSV or typing them into a free-text field does not count as an implementation.

Run the tests with `python -m pytest engine/tests` (Python 3.11 or later, from the repository root). The 1.3.5
acceptance tests are in `engine/tests/test_v135.py`, and the API tests are in
`engine/tests/test_features.py::test_v135_endpoints`. Demonstration files are in `docs/examples/`.

| Feature | Status |
|---|---|
| 1. Factor matching validation against openLCA and Brightway | Done. Not yet run against a real openLCA or Brightway installation (see limits) |
| 2. Programme-specific EPD templates (EPD International, IBU, INIES) | Done as an architecture with three draft profiles, not approved by the operators |
| 3. Data quality (DQR) of EF datasets | Done for ILCD/EF imports |
| 4. Grouped results tabs | Done |
| 5. Consequential marginal-supplier guidance | Done (heuristic, user confirms) |
| 6. LCC: cost types, replacements, study period | Done. Residual value and other parts of ISO 15686-5 are not done |
| 7. AWARE water scarcity | Done (method engine). Official factors are not shipped |
| 8. LANCA land use | Done (method engine). Official factors are not shipped |
| 9. Social LCA | Done (risk screening engine). No social data is shipped |
| 10. Dynamic material flow analysis and MCI | Done |
| 11. IMPACT World+ native | Not implemented |
| 12. Official USEtox 2 native | Not implemented |
| 13. Biodiversity | Not implemented |
| 14. Multi-user projects | Not implemented |
| 15. Dynamic characterisation beyond climate | Not implemented |
| 16. Advanced regionalisation | Partly: AWARE and LANCA use sub-national codes with fallbacks; generic regional factors are still by country |

---

## 1. Factor matching validation

- **Code**: `engine/factormatch.py`; `engine/importers/jsonld.py::read_impact_factors`;
  `engine/tools/brightway_export_factors.py`; API `POST /api/factor-match`, `POST /api/export/factor-match`;
  UI Toolbox > Validation > Factor matching (`app/ui/v135.js`).
- **Tests**: `TestFactorMatching` (4 tests).
  - `test_csv_flow_by_flow_and_effect`: the computed effect equals Σ g·Δc by hand to 1e-10, and Cyclia's model
    result equals `calc.run` to 1e-9.
  - `test_identical_factors_pass_and_external_results_split`: identical factors give 0 differences; a 2 % result
    difference goes entirely to "other differences".
  - `test_openlca_jsonld`: a JSON-LD zip (ImpactMethod and ImpactCategory with impactFactors) is read and paired.
  - `test_shipped_demonstration_files`: the demonstration below.
- **Demonstration**: start the feature demo, then in Toolbox > Validation choose
  `docs/examples/factor_matching_demo_factors.csv` and the categories climate change and acidification of the
  "Demo EF-style method". Optionally add `factor_matching_demo_results.csv`.
- **Acceptance criteria and results on the demonstration**:

| Criterion | Expected | Result |
|---|---|---|
| Climate change: same / different / only in Cyclia / unresolved | 1 / 1 / 1 / 1 (CO2 fossil same; methane fossil 29.7 vs 29.8; N2O missing; SF6 not in the library) | as expected |
| Acidification (ammonia given without UUID, matched by name) | 3 same, 0 different | as expected |
| Flow list | exactly Methane fossil "different" and Dinitrogen monoxide "only in Cyclia" | as expected |
| Overall verdict | not passed | not passed |
| Concrete wall, climate change, with external results | whole difference explained by factors (other differences 0) | -0.0891 kg CO2-eq explained, 0 other |
| Concrete wall, acidification, external result 2 % higher | explained 0, other differences 2.000 % | as expected |
| Excel report | sheets Summary, Flow by flow, Effect on models, Unpaired external | present |

- **Limits**: the Brightway export script has not been run here, because Brightway could not be installed in the
  development environment. The JSON-LD reader has been tested with files built to the openLCA schema, not with an
  export from a real openLCA installation. Publishing an openLCA and Brightway comparison of EF 3.1 is the next
  step: export the method from both tools, run this validation and add the reports to `docs/CROSS_VALIDATION.md`.

## 2. EPD programme profiles

- **Code**: `engine/epd_profiles.py` (profiles, validation, custom profiles); `engine/standards.py::epd_word`
  (Word EPD rendered section by section from the profile) and `epd_checklist` (programme requirements); API
  `GET/POST /api/epd/profiles`, `POST /api/export/epd-profile`, profile fields in `POST /api/models/{id}/epd-info`;
  UI step 6 > EPD > Programme layout and "Your own programme profile".
- **Tests**: `TestEpdProfiles` (4 tests) and `test_v135_endpoints`.
  - Each profile writes its own Word EPD. The test looks for text that only that programme's layout contains:
    "The International EPD System", IBU's section "2. Product", and the French title of the FDES. It also checks
    the "not ready for submission" banner and the "not approved" notice (French for INIES).
  - Required fields and required indicators are checked, and so is the maximum validity: a 7-year IBU EPD fails
    "Validity at most 5 years".
  - A custom profile round-trips. A built-in id cannot be replaced, and an unknown section is rejected.
  - Additional indicators are matched (PM, IRP, ETP-fw, HTP-c, HTP-nc, SQP, GWP-GHG).
  - Over the API, the IBU profile is exported as JSON and loaded as "ibu-copy", then used for a model.
- **Demonstration**:
  - Feature demo > step 6 > EPD: choose "The International EPD System" and fill the 14 programme fields. Check
    the requirements, then create the Word EPD.
  - Example custom profile: `docs/examples/epd_profile_example.json`.
- **Acceptance criteria**:

| Criterion | Result |
|---|---|
| Four profiles listed (generic, international-epd-system, ibu, inies-fdes) | yes |
| The Word EPD's sections and statements follow the chosen profile | yes (test checks programme-specific text, not the order of every section) |
| Programme requirements appear in the checklist (fields, indicators, validity) | yes (test; UI shows "15 of 26 requirements met" on the demo with the EPD International profile) |
| A custom profile can be exported, edited, loaded and selected | yes (API test) |
| Each profile states its sources and that it is not approved | yes |

- **Limits**: the three programme profiles are drafts built from EPDs the programmes have published (sources
  are in each profile and below). They are not approved by EPD International, IBU or the FDES-INIES programme.
  Before submission, check each profile against the current General Programme Instructions, the PCR and the
  operator's own template. Cyclia writes Word, not the ILCD+EPD XML or the INIES online declaration format.

## 3. Data quality of EF datasets

- **Code**: `engine/importers/other_formats.py::dataset_dqr` (ILCD import stores the values in `activity_dq`);
  `engine/calc.py` (dataset scores are used for lines without PEF scores; `pef_from_datasets`).
- **Tests**: `TestDatasetDqr::test_ilcd_dqi_parsing_and_use`, `TestShippedExamples`.
- **Demonstration**: `docs/examples/ilcd_process_with_dqr.xml`.
- **Acceptance criteria**: Good / Very good / Fair / Good are read as TeR 2, GeR 1, TiR 3, P 2. "Not evaluated" is
  skipped. DQR = 2.0. A model line using the dataset gets PEF DQR 2.0, with 100 % "from datasets". Result: yes.
- **Limits**: ecoSpold2 datasets have no PEF DQR fields. For them the pedigree indicator stays in use.

## 4. Grouped results tabs

- **Code**: `app/ui/index.html` (tab-more), `app/ui/v135.js`.
- **Acceptance**: the Summary, Contributions, Supply chain, Stages, Sensitivity, Uncertainty, Inventory results,
  Checks and Compare tabs stay in front. Dynamic climate, Map, Explore parameters and PEF are under "More
  analyses". Verified in the UI smoke test (Playwright).

## 5. Marginal-supplier guidance

- **Code**: `engine/analysis.py::marginal_guidance`, `constrained_reason`; API `GET /api/models/{id}/marginal`; UI
  Toolbox > Background scenarios > Marginal suppliers.
- **Tests**: `TestMarginal::test_constrained_suppliers_excluded`. The test builds a market of 70 % "steel
  production, from recycled scrap" and 30 % primary steel. The recycled supplier is marked constrained and the
  primary one is proposed. Saved as a consequential scenario, the swap rule makes the market's result equal to
  1 kg of primary steel, to 1e-9, and different from the result before.
- **Demonstration**: feature demo, Concrete wall. Cyclia finds the demo electricity market (FR) and proposes the
  nuclear supplier (largest unconstrained share). "Create consequential scenario" then creates the scenario.
  Verified in the UI.
- **Acceptance**: no supplier named recycled, secondary, by-product, waste, scrap and so on is proposed. If every
  supplier is constrained, Cyclia says so and proposes nothing. The user can change each choice.
- **Limits**: the method is a heuristic based on names and current shares. Identifying the true marginal supplier
  needs market trend data (Weidema et al. 2009), which the user must supply by changing the choice.

## 6. Life cycle costing

- **Code**: `engine/analysis.py::lcc`; `cost_type` and `replace_every` per line and `lcc_period` per model
  (`engine/store.py`, `engine/server.py`); UI step 3 Details and step 2 Costs.
- **Tests**: `TestLccExtended::test_replacements_and_cost_types`.
  - A line costing 100 in year 0, replaced every 25 years over a 60-year study, occurs in years 0, 25 and 50: 300
    undiscounted, and 100 × (1 + 1.03⁻²⁵ + 1.03⁻⁵⁰) at 3 %.
  - Results by cost type: replacement 300, capital 50.
- **Limits**: residual value at the end of the study period, price escalation per cost type, and the ISO 15686-5
  whole-life-cost categories are not implemented.

## 7. AWARE water scarcity

- **Code**: `engine/regional.py::aware`, `import_factors`, `_lookup`; API `/api/regional/*`; UI Toolbox > Regional
  methods.
- **Tests**:
  - `TestRegional::test_aware_by_location_and_fallbacks`: per-process consumption times the factor of the process
    location, equal to a hand calculation to 1e-10; exact (FR), country (FR-IDF → FR) and global (DE → GLO)
    fallbacks; out-of-range factors (500) rejected.
  - `test_aware_irrigation_uses_the_agricultural_factor`: a process named irrigation takes the agricultural
    factor, and the others take the type of use of the model.
  - A model without water or land flows is reported as empty, not as 0 % complete (in the LANCA test).
  - `test_demo_is_labelled`.
  - `TestShippedExamples` (template import: 1 location gives 3 factors).
- **Demonstration**: "Load demo factors", then "AWARE". The feature demo concrete wall gives 1.033 m³ world-eq
  from 0.0664 m³ consumed, with completeness shown. The result says "Demo factors: not AWARE 2.0 values".
- **Acceptance**: the result equals Σ consumption × CF by hand (test). Completeness shares add up to 1. The demo
  is always labelled.
- **Limits**: Cyclia ships no AWARE 2.0 factors. Import the official country and watershed tables with
  `docs/examples/aware_factors_template.csv`. Watershed-level results need process locations or a model location
  given as a watershed code that is present in the imported table.

## 8. LANCA land use

- **Code**: `engine/regional.py::lanca`, `land_flow`.
- **Tests**: `TestRegional::test_lanca_occupation_and_transformation`.
  - Erosion resistance with an occupation factor of 2 equals 2 × the land occupation result of the land use
    category, to 1e-9.
  - Completeness adds up to 1, and unknown indicators are rejected.
  - Flow names are parsed into a kind and a land use type ("Transformation, to urban, discontinuously built").
- **Demonstration**: "Load demo factors", then "LANCA" on the Hempcrete wall (demo). The demo set has three
  indicators (erosion resistance 51.2, groundwater regeneration 25.6, biotic production 102.4 demo units), with
  92 % of the land area exact and 8 % by the global fallback. The engine accepts all six indicators (the five
  LANCA ones and the soil quality index). On a model without land flows, such as the Concrete wall, Cyclia says
  there is nothing to characterise.
- **Limits**: no official LANCA factors are shipped. Import them with `docs/examples/lanca_factors_template.csv`.

## 9. Social LCA

- **Code**: `engine/slca.py`; API `/api/slca/*`; UI Toolbox > Social LCA.
- **Tests**: `TestSocial::test_worker_hours_and_risk_hours`.
  - Worker hours equal Σ output × hours per unit, by hand.
  - Risk hours use the level factors.
  - The most specific match wins, and a location row is preferred.
  - Coverage and processes without data are reported.
  - A table with invalid rows only (an unknown stakeholder) is rejected; invalid rows in a valid table are
    listed with their reason.
- **Demonstration**: "Load demo data", then "Assess". The concrete wall gives 0.2571 worker hours per functional
  unit; 16 of 24 processes have no data and are listed. The result says "Demo data: the results mean nothing".
- **Limits**: no PSILCA or SOCA data is shipped, and Cyclia does not read the PSILCA database format directly. Use
  the template (`docs/examples/social_data_template.csv`). The result is a hotspot screening, not a measure of
  social performance. Reference-scale and performance-reference-point methods are not implemented.

## 10. Dynamic MFA and the Material Circularity Indicator

- **Code**: `engine/mfa.py`; API `/api/mfa/example`, `/api/mfa/run`, `/api/mfa/mci`; UI Toolbox > Material flows
  (editor, chart and table).
- **Tests**: `TestMfa`, 5 tests:
  - a fixed lifetime retires exactly at age L;
  - a recycling loop is solved within the year, and the recycling rate equals 0.85 × 0.95;
  - invalid shares and closed loops are rejected;
  - normal and Weibull lifetimes retire 100 % to 1e-9;
  - MCI is 0.1 when linear, 1 when circular, and 0.55 at twice the lifetime.
- **Demonstration**: `docs/examples/mfa_aluminium_example.json` (also "Load example"). The mass balance closes in
  every year from 2020 to 2060, and the stock is 4,761 in 2060.
- **Acceptance**: the mass-balance error is below 1e-9 in every year (checked on every run and shown).
- **Limits**: the MFA is not linked to the LCA model: its flows do not create inventory lines. Stocks have one
  lifetime distribution each, without cohorts by product type. There is no uncertainty in MFA parameters.

## 11 to 16. Not implemented in 1.3.5

These are not done and are not claimed. A generic CSV method import can carry factors from these methods, but
that is not an implementation of them.

| Feature | What would make it done |
|---|---|
| IMPACT World+ | Native method with its midpoint and damage structure, regionalised factors per location, and the official factor files with their licence; tests against published results |
| USEtox 2 (official) | Official USEtox 2.x characterisation factors (the screening fate model in Cyclia is not USEtox); a test against the USEtox reference results |
| Biodiversity | A species-loss method, such as the LC-IMPACT or GLAM biodiversity indicators, with regionalised land and water factors; licence check |
| Multi-user | A project server with accounts, roles, locking and review comments; Cyclia is one user per project file |
| Dynamic characterisation beyond climate | Time-dependent factors for other categories; today only dynamic GWP (Levasseur et al. 2010) |
| Advanced regionalisation | Sub-national and watershed factors in the generic regional method; spatial units other than location codes |

## Sources for the EPD profiles

- EPD International, General Programme Instructions 5: https://environdec.com/news/gpi_500
- EPD published under GPI 5 (EPD International): https://mannigroup.b-cdn.net/2026/06/EPD-portoni-sezionali-EN-light.pdf
- IBU EPD: https://ibu-epd.com/wp-content/uploads/2017/12/Textile-covered-acoustic-frame-systems.pdf
- IBU PCR Part A: https://ibu-epd.com/wp-content/uploads/2026/08/260702_ENG-PCR-Part-AA2_v.1.5.pdf
- INIES FDES: https://forbo.blob.core.windows.net/forbodocuments/578270/EVEA%20pour%20FORBO_FDES%20Tapis_EN%2015804%20A2_vF.pdf
