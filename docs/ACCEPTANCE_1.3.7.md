# Cyclia 1.3.7: the seven open items of 1.3.6

For each item: what was built, how it is tested, and what is still not done. Tests:
- `engine/tests/test_v137.py` (16 tests);
- `engine/tests/test_features.py::test_v137_endpoints` (API).

All 184 tests pass. The new screens were checked in the browser (Playwright).

| Item | Status |
|---|---|
| ILCD+EPD XML export | Done. Schema-valid ILCD+EPD 1.2 with authoritative identifiers |
| PSILCA and SOCA native import | Done for the openLCA JSON-LD format. Not tested with the real licensed files |
| AWARE monthly and GIS factors | Done: monthly factors with a use profile, GeoJSON watersheds located by coordinates |
| LANCA SQI aggregation | Done as a method. The normalisation references must be entered |
| Visual MFA builder and MFA linked to LCA | Done |
| Separate staging database | Done for format imports |
| Published openLCA and Brightway comparison | Kit done and verified with numpy and a JSON-LD round trip. Runs in Brightway and openLCA not done here |

## 1. ILCD+EPD export

- **Code**: `engine/ilcd_epd.py`; schemas in `engine/schemas/ilcd_epd` (InData, Apache 2.0); API
  `POST /api/export/ilcd-epd`; UI step 6 > EPD > "ILCD+EPD dataset".
- **Sources used**:
  - the InData format repository (github.com/InDataWG/ILCD-EPD-Data-Format): XSD schemas, sample datasets and the
    identifier lists;
  - EN15804+A2_EF3.1_indicators.csv for the 19 LCIA method UUIDs and the 18 indicator flow UUIDs.
- **Tests**:
  - The demo wall is exported, and the process and flow files validate against the official schemas.
  - The GWP-total epd:amount values equal Cyclia's module table, and the modules are the declared ones.
  - A wrong sub-type is caught by the schema check.
  - The identifiers are checked against the InData list.
- **Found while building**:
  - libxml2 stops with an internal error, not a schema message, when an element constrained by `xs:unique` on
    `@xml:lang` has no language. Cyclia writes the language.
  - The 2024 extension schema does not load in lxml, so Cyclia writes ILCD+EPD 1.2 (extensions 2013 and 2019).
  - The InData sample file uses the ADPF UUID for HTP-c. Cyclia follows the identifier list, not the sample.
- **Not done**:
  - ILCD+EPD 1.3 (2024) elements: product IDs, service life, variability, manufacturers;
  - scenarios, content declaration and contact data sets.
  Add them in the EPD Editor. Upload to ÖKOBAUDAT has not been tried.

## 2. PSILCA and SOCA

- **Code**: `slca.import_olca_social`; API `POST /api/slca/import-olca`; UI Toolbox > Social LCA > "PSILCA or SOCA".
- **Tests**: on a JSON-LD fixture built to the openLCA schema:
  - the social indicators and aspects are read;
  - stakeholders come from the category path;
  - risk levels are mapped, and "no data" is skipped and reported;
  - raw value and unit are kept;
  - a SOCA-style process matches the library dataset of the same name;
  - a PSILCA sector is assigned through the mapping table.
- **Not done**:
  - Not tested with the real licensed PSILCA or SOCA files.
  - Raw indicator values and reference scales are kept but not used: the assessment is still the risk-hour screening.

## 3. AWARE monthly and GIS

- **Code**: `regional.import_factors` (month column), `_month_profile`, `_monthly_cf`, `import_geojson`, `locate`,
  `point_in`; API `/api/regional/geojson`, `/api/regional/locate`; UI Toolbox > Regional methods.
- **Tests**:
  - A June–July profile gives the mean of the June and July factors, and without a profile the annual factor is used.
  - Point-in-polygon respects holes.
  - A GeoJSON with two basins imports polygons and factors, and the site at (25, 25) is found in basin B-2 and gets
    its factor.
- **Not done**:
  - Shapefiles are not read directly; convert them to GeoJSON with QGIS or ogr2ogr.
  - Supply-chain processes have no month and keep the annual factors.

## 4. LANCA SQI

- **Code**: `regional.sqi_aggregate`; API `/api/regional/sqi`; UI Toolbox > Regional methods > "Soil quality index".
- **Tests**:
  - The result equals Σ w·CF/N by hand.
  - Incomplete land use types are skipped.
  - The comparison with an official SQI factor is reported.
  - Missing normalisation references or weights that do not add up to 1 are refused.
- **Not done**:
  - The normalisation references (De Laurentiis et al. 2019) are not shipped: their values could not be checked
    here, so they must be entered from the method version followed.
  - Equal weights are the default and must be stated as an assumption.

## 5. MFA builder and MFA linked to LCA

- **Code**: `mfa.lca`; API `/api/mfa/lca`; UI Toolbox > Material flows: tables, draggable diagram, links to datasets
  or models, "Impacts over time" (`app/ui/v137.js`).
- **Tests**:
  - The impact in a year equals throughput × the dataset's impact per unit, at three years and cumulatively.
  - Linking a model works over the API.
  - An unknown process is refused.
  - UI test: the example loads into 5 processes and 7 flows, a box can be dragged (layout saved), processes can be
    added and removed, and a link and a calculation run.
- **Not done**: MFA flows do not create inventory lines in a model.

## 6. Staging database

- **Code**: `engine/staging.py`; used by every format import (`server._import_job`).
- **Tests**:
  - The merge gives the same results as a direct import, and ambiguous-input candidates are shifted with the
    datasets.
  - A staged import with a non-finite amount is stopped, and the library keeps its datasets.
  - An openLCA import with an impact method is merged and gives the result of the direct-import test.
  - The SimaPro import over the API goes through staging.
- **Not done**: streaming of very large files (an ecoinvent folder is still read file by file into memory batches).

## 7. Comparison with openLCA and Brightway

- **Code**: `engine/compare_kit.py`, `engine/tools/compare_kit/*`; API `/api/export/compare-kit` (refused for ecoinvent);
  UI Toolbox > Validation > "Comparison kit".
- **Tests**:
  - The kit of the tutorial database solved independently with numpy/scipy agrees with Cyclia (largest relative
    difference 1.3e-10).
  - The kit's openLCA JSON-LD imported back into Cyclia reproduces all 132 results.
  - The Brightway and openLCA scripts are present and compile.
- **Not done**: the Brightway and openLCA runs themselves. PyPI and openLCA cannot be reached from the development
  environment.
  - Run `run_brightway.py` and `run_openlca.py` on your computer, then `compare.py`.
  - Add the reports to docs/CROSS_VALIDATION.md with the software versions.
  - Until then no published comparison exists, and none is claimed.
