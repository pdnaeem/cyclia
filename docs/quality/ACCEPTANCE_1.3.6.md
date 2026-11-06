# Cyclia 1.3.6: audit findings, fixes and tests

This file answers two external audits of 1.3.5 (database import, and scientific modules) and the analysis of the
user's ecoinvent benchmark file (Cyclia 1.3.4, 100 datasets, 25 EF 3.1 categories). Every finding was first
reproduced in the code. Every fix has a regression test in `engine/tests/test_v136.py` (or
`test_features.py::test_v136_database_provenance_and_statuses`) that fails on 1.3.5 and passes on 1.3.6.

Run the tests with `python -m pytest engine/tests` from the repository root (167 tests).

## Database import

| Finding | Confirmed | Fix | Test |
|---|---|---|---|
| P0 SimaPro: two processes with the same product and location merged | Yes. The key was product + location, and `INSERT OR IGNORE` attached the second process's exchanges to the first. The same builder serves ecoSpold1 and ILCD | Key = process identifier (else process name) + product + location. Duplicates are kept as separate datasets and reported | `TestSimaProIdentity` (3 tests) |
| P0 ecoSpold2: input without activityLinkId dropped | Yes. It was counted, then left out without a record | Stored as unresolved, "no supplier link in the dataset". Results are unchanged until the user links it | `TestEcoSpold2KeepsInputs` |
| P1 Linking across locations | Yes. Groups were (product, unit) | Groups and links are per (product, unit, location). Auto-link needs exactly one supplier at the location and never links ambiguous or no-link groups. A dataset of the same database can now be chosen | `TestLinkingGeography` (2 tests) |
| P1 openLCA JSON-LD: first producer used without a defaultProvider | Yes | defaultProvider, else the only producer, else ambiguous with candidates | `TestJsonLdProviders` (2 tests) |
| (found while fixing) Builder used the first producer whenever several produced a product | Yes | Ambiguous inputs are never guessed | `test_input_of_an_ambiguous_product_is_not_guessed` |
| P1 Structured database metadata | Yes, only name, source, version, system model | Added original name, release date, geography, technology, licence, reference period, data reference, source path, SHA-256, importer version and import report. The SHA-256 and importer version are recorded automatically; the rest is editable under Details | `test_v136_database_provenance_and_statuses` |
| P1 Database check verdict misleading | Yes. "Matrix is consistent" was based on the residual alone | Six statuses: matrix, technosphere, flows, units, metadata, LCIA | same test |
| P1 Database explorer | Not present | Toolbox > Database explorer: identity, suppliers, users, unresolved inputs, flows with uncertainty, data quality, navigation | API test in the same test, UI smoke test |
| P1 Staging and rollback | Partly present (failed imports were removed) | An import is all or nothing. An integrity check runs after import (non-finite amounts, dangling links) and removes the database if it fails | `_integrity` in server.py. **Not done: a separate staging database** |
| P1 Streaming imports of very large files | Not changed | Not done | - |

## Scientific modules of 1.3.5

| Finding | Confirmed | Fix | Test |
|---|---|---|---|
| P0 Factor matching false PASS (unresolved flow, wrong units) | Yes, both experiments | PASS only with no open item. Convertible units are converted; non-comparable units are never "same". Open items are listed in the app and in Excel | `TestFactorMatchingVerdict` (4 tests) |
| Factor matching: one external category paired several times | Yes | One-to-one pairing, best score first | `test_pairing_is_one_to_one` |
| P0 AWARE: evaporated water subtracted | Yes, `_water_flow("Water, evaporated", "air/...")` gave -1. Water to soil was also subtracted | Only a release to fresh water is a return. Evaporation, sea and soil are consumption. The water balance is reported | `TestAwareWater` (3 tests) |
| (found while fixing) AWARE non-agricultural factor never used | Yes. Stored as `non-agri`, looked up as `non_agri`, so the unknown factor was used silently | Keys normalised, including old libraries. When the unknown factor is used instead, the result says so | `test_old_non_agri_keys_still_found` |
| AWARE use type from the model setting | Yes | Per process: irrigation agricultural, other processes non-agricultural (option: unknown) | updated `test_v135` AWARE tests |
| P1 Social LCA coverage 100 % | Yes | Process coverage. Worker-hour coverage only with a default row (`*`) that estimates the hours of processes without data. Labelled "risk screening, not a full social LCA" | `TestSocialCoverage` (3 tests) |
| Social LCA: abs(output) of credits | Yes. Credits also reduced the hours of processes shared with the real supply chain | Demand and avoided products are solved separately. Credits are reported, not netted | `test_avoided_products_are_not_added_or_netted` |
| P1 MFA recirculated inflow denominator | Yes. In the audit case Cyclia gave 16.7 % instead of 33.3 % | Recycled input / total input of the production process | `TestMfaCircularity` |
| MFA and MCI unconnected | Yes | MCI per year computed from the MFA (recycled content, collection, recycling efficiency) | `test_mci_comes_from_the_mfa` |
| P1 LANCA units not validated, amounts multiplied directly | Yes | Factor units are validated (occupation per m2*a, transformation per m2; per ha converted). Inventory amounts are converted (ha*a to m2*a) | `TestLancaUnits` (2 tests) |
| LANCA soil organic carbon missing | Yes | Accepted as an indicator | - |
| LANCA SQI computed from a defined method | No | Not done. The EF method publishes SQI factors, which Cyclia uses as imported | - |
| P1 EPD additional indicator units | Yes | Units of PM, IRP, ETP-fw, HTP-c, HTP-nc, SQP and GWP-GHG are checked | `test_units_of_additional_indicators` |
| (found while fixing) EPD HTP-c/HTP-nc not recognised for ecoinvent EF 3.1 | Yes. The names are "carcinogenic", and sub-categories could be picked | Recognises carcinogenic and non-carcinogenic, and excludes the inorganics and organics sub-categories | `test_ef31_names_match_the_total_not_the_sub_category` |

## Land use difference (the user's benchmark file)

What the file shows:
- 96.2 % of 2,500 results agree within 0.1 %.
- Land use (soil quality index): only 30 % of results within 0.1 %, median 0.40 %, maximum 14 %. Cyclia is lower for most datasets.
- The largest gaps are in datasets whose supply chains include hydro reservoirs or offshore oil and gas: container ship operation (-14 %), bulk carrier transport (-9 %), natural gas CHP in DE (-7.6 %), LNG import in KR, electricity in ET, hydro reservoir.
- The land flows without a factor in Cyclia are exactly of that kind: "Occupation, lake, artificial", "Occupation, river, artificial", and seabed occupation and transformation.
- The factor finder could not test them, because it only looked at flows whose names are in the method file.
- One dataset (container operation) deviates in seven categories at once. That points to a missing part of its inventory, for example inputs that 1.3.4 dropped without a record. It is less likely to be a factor problem.

What 1.3.6 does:
- **Every result** shows, per land use category, the share of land occupation and transformation without a factor, with a warning above 0.5 % (`TestLandCoverageCheck`).
- **The benchmark** regresses the gap on the land flows without a factor and reports the factor ecoinvent appears to use for each, with the share of the gap explained (`TestLandUseUncharacterised` recovers known factors exactly). For deviating datasets it notes how many unresolved inputs their supply chain holds.
- **The verdict** no longer says "Validated" when a category disagrees. It now reads "Validated except 1 category: … land use …" (`TestBenchmarkVerdict`).

Status: the cause is narrowed down, not confirmed. Please re-import the ecoinvent release with 1.3.6, so that inputs without a link are recorded, and run the benchmark again. The "Land use reconciliation" sheet will then show whether the lake, river and seabed flows explain the gap. If they do, add their factors from the method's source (EF 3.1 package), never from the implied values.

## Not done in 1.3.6

These items are stated so that nobody mistakes the current state for more:
- native PSILCA or SOCA import, raw-value and reference-scale social assessment;
- AWARE monthly factors and GIS watershed identification;
- an LANCA SQI aggregation method;
- ILCD+EPD machine-readable export, and approval of the EPD profiles by the programme operators;
- a visual MFA builder and a link from MFA to the LCA inventory;
- a separate staging database and streaming import of very large files;
- a published openLCA and Brightway comparison of EF 3.1 (the Brightway export script has not been run here);
- IMPACT World+, official USEtox 2, biodiversity, multi-user, and dynamic characterisation beyond climate.
