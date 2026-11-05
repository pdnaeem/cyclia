# Validation of Cyclia against ecoinvent

Cyclia's LCIA results were compared with ecoinvent's own published cumulative LCIA results. The comparison uses the
benchmark built into Cyclia (Setup > ecoinvent > "Validate only"), which downloads ecoinvent's results with the
user's licence. No ecoinvent data is part of Cyclia or of this document; only the deviations are reported.

## Result

**100.0 % of 2,500 results agree with ecoinvent within 0.1 %. The median deviation is 3.9e-07 %, and the largest is
0.0018 %.**

| Item | Value |
|---|---|
| Date | 2026-11-05 |
| Cyclia | 1.3.10 (the calculation of 1.4.0 gives the same values; it only sets datasets outside the supply chain to exactly zero) |
| Database | ecoinvent, cut-off system model, installed with "Download, connect and validate" (27,400 datasets) |
| Results file | ecoinvent's cumulative LCIA results of the same release (27,401 datasets) |
| Method | EF v3.1 (factors from ecoinvent's LCIA implementation file), 25 categories |
| Datasets compared | 100, a stratified sample across the groups below (seed 11) |
| Results compared | 2,500 (100 datasets x 25 categories) |
| Within 0.1 % | 100 % |
| Within 1 % | 100 % |
| Inputs without supplier | 0 |
| Inventory check | ecoinvent's cumulative LCI: 3,352 of 3,354 flow columns matched to Cyclia's flows |

## By category

| Category | Unit | Results | Median \|dev\| % | 95th percentile % | Max % |
|---|---|---|---|---|---|
| acidification | mol H+-Eq | 100 | 2.9e-07 | 5.6e-06 | 2.3e-04 |
| climate change | kg CO2-Eq | 100 | 2.1e-07 | 5.1e-06 | 2.9e-04 |
| climate change: biogenic | kg CO2-Eq | 100 | 1.2e-06 | 5.7e-05 | 4.7e-04 |
| climate change: fossil | kg CO2-Eq | 100 | 2.3e-07 | 5.0e-06 | 3.0e-04 |
| climate change: land use and land use change | kg CO2-Eq | 100 | 3.4e-07 | 1.9e-05 | 1.2e-04 |
| ecotoxicity: freshwater | CTUe | 100 | 3.2e-07 | 8.5e-06 | 3.8e-04 |
| ecotoxicity: freshwater, inorganics | CTUe | 100 | 4.4e-07 | 1.0e-05 | 4.0e-04 |
| ecotoxicity: freshwater, organics | CTUe | 100 | 3.9e-07 | 1.6e-05 | 1.2e-04 |
| energy resources: non-renewable | MJ, net calorific value | 100 | 2.1e-07 | 6.3e-06 | 2.4e-04 |
| eutrophication: freshwater | kg P-Eq | 100 | 4.5e-07 | 7.0e-06 | 9.8e-04 |
| eutrophication: marine | kg N-Eq | 100 | 2.0e-07 | 5.2e-06 | 1.1e-04 |
| eutrophication: terrestrial | mol N-Eq | 100 | 2.5e-07 | 1.1e-05 | 1.4e-04 |
| human toxicity: carcinogenic | CTUh | 100 | 4.8e-07 | 9.8e-06 | 2.6e-04 |
| human toxicity: carcinogenic, inorganics | CTUh | 100 | 5.2e-07 | 1.7e-05 | 4.9e-04 |
| human toxicity: carcinogenic, organics | CTUh | 100 | 4.3e-07 | 1.1e-05 | 2.1e-04 |
| human toxicity: non-carcinogenic | CTUh | 100 | 3.3e-07 | 1.2e-05 | 4.7e-04 |
| human toxicity: non-carcinogenic, inorganics | CTUh | 100 | 4.4e-07 | 1.4e-05 | 5.2e-04 |
| human toxicity: non-carcinogenic, organics | CTUh | 100 | 4.3e-07 | 1.5e-05 | 1.8e-04 |
| ionising radiation: human health | kBq U235-Eq | 100 | 5.0e-07 | 2.8e-05 | 7.9e-04 |
| land use | dimensionless | 100 | 6.3e-06 | 1.9e-04 | 1.1e-03 |
| material resources: metals/minerals | kg Sb-Eq | 100 | 1.3e-06 | 6.5e-05 | 1.8e-03 |
| ozone depletion | kg CFC-11-Eq | 100 | 2.1e-07 | 8.7e-06 | 2.1e-04 |
| particulate matter formation | disease incidence | 100 | 3.8e-07 | 1.0e-05 | 1.6e-04 |
| photochemical oxidant formation: human health | kg NMVOC-Eq | 100 | 2.7e-07 | 6.8e-06 | 1.7e-04 |
| water use | m3 world Eq deprived | 100 | 2.2e-07 | 7.6e-06 | 2.3e-04 |

## By group of datasets

| Group of datasets | Results | Max \|dev\| % |
|---|---|---|
| Agriculture and food | 275 | 4.8e-04 |
| Chemicals and plastics | 275 | 6.3e-05 |
| Construction and minerals | 275 | 3.9e-04 |
| Electricity and heat | 275 | 2.2e-04 |
| Markets | 275 | 1.8e-03 |
| Metals | 275 | 1.1e-03 |
| Other | 300 | 2.7e-04 |
| Transport | 275 | 3.0e-05 |
| Waste treatment | 275 | 3.6e-04 |

## How the agreement was reached

The 1.3.6 benchmark agreed in 96.2 % of the results. Land use did not: only 30 % of its results were within
0.1 %, the median deviation was 0.4 % and the largest 14 %. The inventory check added in 1.3.9 compares Cyclia's
cumulative inventory with ecoinvent's cumulative LCI and splits each gap into an inventory part and a factor part
(METHODS 15.5). For land use it measured a 100 % inventory part. ecoinvent's inventory, characterised with Cyclia's
factors, gave ecoinvent's results, so the factors were right.

The flows that differed belonged to infrastructure: industrial area, mineral extraction sites, seabed
infrastructure, and drilling emissions to the ocean. The cause was a cut-off in the matrix solve that set scaling
factors below 1e-13 x the largest one to zero. It was removed in 1.3.10 (METHODS 15.6).

## Reproduce

1. Install Cyclia 1.4.1 or later and connect ecoinvent with your licence (Setup > ecoinvent).
2. Press "Validate only", with "Compare inventories too" ticked.
3. Save the Excel report. From 1.4.1 its Summary sheet also records the database name, version, system model, method
   and file names.

The sample is drawn with a fixed seed. Choose "All datasets" for a complete comparison.
