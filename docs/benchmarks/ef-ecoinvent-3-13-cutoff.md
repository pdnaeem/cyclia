# EF benchmark: Cyclia against ecoinvent's cumulative LCIA results

Database: ecoinvent (3.13, cutoff)

**EF v3.0**: Validated. 100.00 % of 2,800 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**EF v3.0 no LT**: Validated. 100.00 % of 2,800 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**EF v3.1**: Validated. 100.00 % of 2,500 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**EF v3.1 no LT**: Validated. 100.00 % of 2,500 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

## What was compared

- Reference: ecoinvent's own cumulative LCIA results for ecoinvent (3.13, cutoff), the file ecoinvent provides to licence holders with the database. Cyclia imported the same database (ecoSpold2) and the method, calculated every sampled dataset with its full supply chain and compared the scores, result by result.
- Results compared: 10,600 (datasets x impact categories).
- Datasets: 100 compared of 27,401 in the results file, matched by 'Activity UUID_Product UUID' (or by name, geography and product).
- The cumulative inventory was compared with ecoinvent's cumulative LCI as well, which separates deviations caused by the inventory from those caused by the factors.
- Software: Cyclia 1.9.1; run on 2026-11-16.

## Deviation per impact category

Deviation = |Cyclia - ecoinvent| / |ecoinvent| x 100, per dataset. Signed median: negative when Cyclia is lower for most datasets.

| Method | Category | Indicator | Unit | Results | Median % | Signed median % | 95th percentile % | Max % | Within 0.1 % | Within 1 % | Within round-off |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| EF v3.0 | acidification | accumulated exceedance (AE) | mol H+-Eq | 100 | 2.9e-07 | -1.97e-08 | 5.59e-06 | 0.000227 | 100 % | 100 % | 0 |
| EF v3.0 | climate change | global warming potential (GWP100) | kg CO2-Eq | 100 | 2.07e-07 | 0 | 5.06e-06 | 0.000282 | 100 % | 100 % | 0 |
| EF v3.0 | climate change: biogenic | global warming potential (GWP100) | kg CO2-Eq | 100 | 1.16e-06 | 0 | 5.68e-05 | 0.000466 | 100 % | 100 % | 0 |
| EF v3.0 | climate change: fossil | global warming potential (GWP100) | kg CO2-Eq | 100 | 2.22e-07 | 0 | 5.03e-06 | 0.000293 | 100 % | 100 % | 0 |
| EF v3.0 | climate change: land use and land use change | global warming potential (GWP100) | kg CO2-Eq | 100 | 3.35e-07 | 0 | 1.16e-05 | 0.000105 | 100 % | 100 % | 0 |
| EF v3.0 | ecotoxicity: freshwater | comparative toxic unit for ecosystems (CTUe) | CTUe | 100 | 3.94e-07 | 5.18e-08 | 5.98e-06 | 0.000475 | 100 % | 100 % | 0 |
| EF v3.0 | ecotoxicity: freshwater, inorganics | comparative toxic unit for ecosystems (CTUe) | CTUe | 100 | 4.93e-07 | 0 | 2.1e-05 | 0.000429 | 100 % | 100 % | 0 |
| EF v3.0 | ecotoxicity: freshwater, metals | comparative toxic unit for ecosystems (CTUe) | CTUe | 100 | 4.67e-07 | 3.98e-08 | 7.92e-06 | 0.000488 | 100 % | 100 % | 0 |
| EF v3.0 | ecotoxicity: freshwater, organics | comparative toxic unit for ecosystems (CTUe) | CTUe | 100 | 4.04e-07 | 7.09e-10 | 1.58e-05 | 0.000136 | 100 % | 100 % | 0 |
| EF v3.0 | energy resources: non-renewable | abiotic depletion potential (ADP): fossil fuels | MJ, net calorific value | 100 | 2.09e-07 | 1.87e-08 | 6.32e-06 | 0.000242 | 100 % | 100 % | 0 |
| EF v3.0 | eutrophication: freshwater | fraction of nutrients reaching freshwater end compartment (P) | kg P-Eq | 100 | 4.54e-07 | 0 | 6.99e-06 | 0.000977 | 100 % | 100 % | 0 |
| EF v3.0 | eutrophication: marine | fraction of nutrients reaching marine end compartment (N) | kg N-Eq | 100 | 1.99e-07 | -3.46e-08 | 5.25e-06 | 0.000112 | 100 % | 100 % | 0 |
| EF v3.0 | eutrophication: terrestrial | accumulated exceedance (AE) | mol N-Eq | 100 | 2.55e-07 | -2.67e-08 | 1.08e-05 | 0.000135 | 100 % | 100 % | 0 |
| EF v3.0 | human toxicity: carcinogenic | comparative toxic unit for human (CTUh) | CTUh | 100 | 4.97e-07 | 4.2e-14 | 9.81e-06 | 0.000265 | 100 % | 100 % | 0 |
| EF v3.0 | human toxicity: carcinogenic, inorganics | comparative toxic unit for human (CTUh) | CTUh | 100 | 0 | 0 | 0 | 0 | 100 % | 100 % | 0 |
| EF v3.0 | human toxicity: carcinogenic, metals | comparative toxic unit for human (CTUh) | CTUh | 100 | 5.24e-07 | 3.56e-14 | 1.68e-05 | 0.000488 | 100 % | 100 % | 0 |
| EF v3.0 | human toxicity: carcinogenic, organics | comparative toxic unit for human (CTUh) | CTUh | 100 | 4.42e-07 | 0 | 1.1e-05 | 0.000209 | 100 % | 100 % | 0 |
| EF v3.0 | human toxicity: non-carcinogenic | comparative toxic unit for human (CTUh) | CTUh | 100 | 3.14e-07 | 8.93e-09 | 1.22e-05 | 0.000158 | 100 % | 100 % | 0 |
| EF v3.0 | human toxicity: non-carcinogenic, inorganics | comparative toxic unit for human (CTUh) | CTUh | 100 | 3.45e-07 | 4.56e-09 | 9.15e-06 | 5.55e-05 | 100 % | 100 % | 0 |
| EF v3.0 | human toxicity: non-carcinogenic, metals | comparative toxic unit for human (CTUh) | CTUh | 100 | 4.94e-07 | 6.09e-09 | 1.41e-05 | 0.000523 | 100 % | 100 % | 0 |
| EF v3.0 | human toxicity: non-carcinogenic, organics | comparative toxic unit for human (CTUh) | CTUh | 100 | 4.33e-07 | 2.23e-08 | 1.49e-05 | 0.000183 | 100 % | 100 % | 0 |
| EF v3.0 | ionising radiation: human health | human exposure efficiency relative to u235 | kBq U235-Eq | 100 | 5.01e-07 | 2.87e-09 | 2.79e-05 | 0.000793 | 100 % | 100 % | 0 |
| EF v3.0 | land use | soil quality index | dimensionless | 100 | 6.34e-06 | 0 | 0.000194 | 0.00111 | 100 % | 100 % | 0 |
| EF v3.0 | material resources: metals/minerals | abiotic depletion potential (ADP): elements (ultimate reserves) | kg Sb-Eq | 100 | 1.33e-06 | 9.42e-09 | 6.5e-05 | 0.00183 | 100 % | 100 % | 0 |
| EF v3.0 | ozone depletion | ozone depletion potential (ODP) | kg CFC-11-Eq | 100 | 2.07e-07 | 0 | 8.74e-06 | 0.000206 | 100 % | 100 % | 0 |
| EF v3.0 | particulate matter formation | impact on human health | disease incidence | 100 | 3.79e-07 | 1.04e-14 | 1.02e-05 | 0.000156 | 100 % | 100 % | 0 |
| EF v3.0 | photochemical oxidant formation: human health | tropospheric ozone concentration increase | kg NMVOC-Eq | 100 | 2.71e-07 | 2.11e-08 | 6.82e-06 | 0.00017 | 100 % | 100 % | 0 |
| EF v3.0 | water use | user deprivation potential (deprivation-weighted water consumption) | m3 world Eq deprived | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| EF v3.0 no LT | acidification no LT | accumulated exceedance (AE) no LT | mol H+-Eq | 100 | 2.9e-07 | -1.97e-08 | 5.59e-06 | 0.000227 | 100 % | 100 % | 0 |
| EF v3.0 no LT | climate change no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 2.07e-07 | 0 | 5.06e-06 | 0.000282 | 100 % | 100 % | 0 |
| EF v3.0 no LT | climate change: biogenic no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 1.16e-06 | 0 | 5.68e-05 | 0.000466 | 100 % | 100 % | 0 |
| EF v3.0 no LT | climate change: fossil no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 2.22e-07 | 0 | 5.03e-06 | 0.000293 | 100 % | 100 % | 0 |
| EF v3.0 no LT | climate change: land use and land use change no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 3.35e-07 | 0 | 1.16e-05 | 0.000105 | 100 % | 100 % | 0 |
| EF v3.0 no LT | ecotoxicity: freshwater no LT | comparative toxic unit for ecosystems (CTUe) no LT | CTUe | 100 | 3.94e-07 | 5.18e-08 | 5.98e-06 | 0.000475 | 100 % | 100 % | 0 |
| EF v3.0 no LT | ecotoxicity: freshwater, inorganics no LT | comparative toxic unit for ecosystems (CTUe) no LT | CTUe | 100 | 4.93e-07 | 0 | 2.1e-05 | 0.000429 | 100 % | 100 % | 0 |
| EF v3.0 no LT | ecotoxicity: freshwater, metals no LT | comparative toxic unit for ecosystems (CTUe) no LT | CTUe | 100 | 4.67e-07 | 3.98e-08 | 7.92e-06 | 0.000488 | 100 % | 100 % | 0 |
| EF v3.0 no LT | ecotoxicity: freshwater, organics no LT | comparative toxic unit for ecosystems (CTUe) no LT | CTUe | 100 | 4.04e-07 | 7.09e-10 | 1.58e-05 | 0.000136 | 100 % | 100 % | 0 |
| EF v3.0 no LT | energy resources: non-renewable no LT | abiotic depletion potential (ADP): fossil fuels no LT | MJ, net calorific value | 100 | 2.09e-07 | 1.87e-08 | 6.32e-06 | 0.000242 | 100 % | 100 % | 0 |
| EF v3.0 no LT | eutrophication: freshwater no LT | fraction of nutrients reaching freshwater end compartment (P) no LT | kg P-Eq | 100 | 3.65e-07 | 0 | 5.48e-06 | 0.000893 | 100 % | 100 % | 0 |
| EF v3.0 no LT | eutrophication: marine no LT | fraction of nutrients reaching marine end compartment (N) no LT | kg N-Eq | 100 | 2.02e-07 | -4.16e-08 | 5.34e-06 | 0.000107 | 100 % | 100 % | 0 |
| EF v3.0 no LT | eutrophication: terrestrial no LT | accumulated exceedance (AE) no LT | mol N-Eq | 100 | 2.55e-07 | -2.67e-08 | 1.08e-05 | 0.000135 | 100 % | 100 % | 0 |
| EF v3.0 no LT | human toxicity: carcinogenic no LT | comparative toxic unit for human (CTUh) no LT | CTUh | 100 | 4.97e-07 | 4.2e-14 | 9.81e-06 | 0.000265 | 100 % | 100 % | 0 |
| EF v3.0 no LT | human toxicity: carcinogenic, inorganics no LT | comparative toxic unit for human (CTUh) no LT | CTUh | 100 | 0 | 0 | 0 | 0 | 100 % | 100 % | 0 |
| EF v3.0 no LT | human toxicity: carcinogenic, metals no LT | comparative toxic unit for human (CTUh) no LT | CTUh | 100 | 5.24e-07 | 3.56e-14 | 1.68e-05 | 0.000488 | 100 % | 100 % | 0 |
| EF v3.0 no LT | human toxicity: carcinogenic, organics no LT | comparative toxic unit for human (CTUh) no LT | CTUh | 100 | 4.42e-07 | 0 | 1.1e-05 | 0.000209 | 100 % | 100 % | 0 |
| EF v3.0 no LT | human toxicity: non-carcinogenic no LT | comparative toxic unit for human (CTUh) no LT | CTUh | 100 | 3.14e-07 | 8.93e-09 | 1.22e-05 | 0.000158 | 100 % | 100 % | 0 |
| EF v3.0 no LT | human toxicity: non-carcinogenic, inorganics no LT | comparative toxic unit for human (CTUh) no LT | CTUh | 100 | 3.45e-07 | 4.56e-09 | 9.15e-06 | 5.55e-05 | 100 % | 100 % | 0 |
| EF v3.0 no LT | human toxicity: non-carcinogenic, metals no LT | comparative toxic unit for human (CTUh) no LT | CTUh | 100 | 4.94e-07 | 6.09e-09 | 1.41e-05 | 0.000523 | 100 % | 100 % | 0 |
| EF v3.0 no LT | human toxicity: non-carcinogenic, organics no LT | comparative toxic unit for human (CTUh) no LT | CTUh | 100 | 4.33e-07 | 2.23e-08 | 1.49e-05 | 0.000183 | 100 % | 100 % | 0 |
| EF v3.0 no LT | ionising radiation: human health no LT | human exposure efficiency relative to u235 no LT | kBq U235-Eq | 100 | 9.85e-07 | 3.05e-08 | 3.17e-05 | 0.000921 | 100 % | 100 % | 0 |
| EF v3.0 no LT | land use no LT | soil quality index no LT | dimensionless | 100 | 6.34e-06 | 0 | 0.000194 | 0.00111 | 100 % | 100 % | 0 |
| EF v3.0 no LT | material resources: metals/minerals no LT | abiotic depletion potential (ADP): elements (ultimate reserves) no LT | kg Sb-Eq | 100 | 1.33e-06 | 9.42e-09 | 6.5e-05 | 0.00183 | 100 % | 100 % | 0 |
| EF v3.0 no LT | ozone depletion no LT | ozone depletion potential (ODP) no LT | kg CFC-11-Eq | 100 | 2.07e-07 | 0 | 8.74e-06 | 0.000206 | 100 % | 100 % | 0 |
| EF v3.0 no LT | particulate matter formation no LT | impact on human health no LT | disease incidence | 100 | 3.35e-07 | 4.45e-09 | 8.49e-06 | 0.000144 | 100 % | 100 % | 0 |
| EF v3.0 no LT | photochemical oxidant formation: human health no LT | tropospheric ozone concentration increase no LT | kg NMVOC-Eq | 100 | 2.71e-07 | 2.11e-08 | 6.82e-06 | 0.00017 | 100 % | 100 % | 0 |
| EF v3.0 no LT | water use no LT | user deprivation potential (deprivation-weighted water consumption) no LT | m3 world Eq deprived | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| EF v3.1 | acidification | accumulated exceedance (AE) | mol H+-Eq | 100 | 2.9e-07 | -1.97e-08 | 5.59e-06 | 0.000227 | 100 % | 100 % | 0 |
| EF v3.1 | climate change | global warming potential (GWP100) | kg CO2-Eq | 100 | 2.05e-07 | 0 | 5.06e-06 | 0.00029 | 100 % | 100 % | 0 |
| EF v3.1 | climate change: biogenic | global warming potential (GWP100) | kg CO2-Eq | 100 | 1.16e-06 | 0 | 5.68e-05 | 0.000466 | 100 % | 100 % | 0 |
| EF v3.1 | climate change: fossil | global warming potential (GWP100) | kg CO2-Eq | 100 | 2.25e-07 | 0 | 5.04e-06 | 0.0003 | 100 % | 100 % | 0 |
| EF v3.1 | climate change: land use and land use change | global warming potential (GWP100) | kg CO2-Eq | 100 | 3.35e-07 | 0 | 1.16e-05 | 0.000106 | 100 % | 100 % | 0 |
| EF v3.1 | ecotoxicity: freshwater | comparative toxic unit for ecosystems (CTUe) | CTUe | 100 | 3.15e-07 | 0 | 8.48e-06 | 0.000377 | 100 % | 100 % | 0 |
| EF v3.1 | ecotoxicity: freshwater, inorganics | comparative toxic unit for ecosystems (CTUe) | CTUe | 100 | 4.43e-07 | 0 | 1.04e-05 | 0.000396 | 100 % | 100 % | 0 |
| EF v3.1 | ecotoxicity: freshwater, organics | comparative toxic unit for ecosystems (CTUe) | CTUe | 100 | 3.94e-07 | 2.72e-09 | 1.58e-05 | 0.000125 | 100 % | 100 % | 0 |
| EF v3.1 | energy resources: non-renewable | abiotic depletion potential (ADP): fossil fuels | MJ, net calorific value | 100 | 2.09e-07 | 1.87e-08 | 6.32e-06 | 0.000242 | 100 % | 100 % | 0 |
| EF v3.1 | eutrophication: freshwater | fraction of nutrients reaching freshwater end compartment (P) | kg P-Eq | 100 | 4.54e-07 | 0 | 6.99e-06 | 0.000977 | 100 % | 100 % | 0 |
| EF v3.1 | eutrophication: marine | fraction of nutrients reaching marine end compartment (N) | kg N-Eq | 100 | 1.99e-07 | -3.46e-08 | 5.25e-06 | 0.000112 | 100 % | 100 % | 0 |
| EF v3.1 | eutrophication: terrestrial | accumulated exceedance (AE) | mol N-Eq | 100 | 2.55e-07 | -2.67e-08 | 1.08e-05 | 0.000135 | 100 % | 100 % | 0 |
| EF v3.1 | human toxicity: carcinogenic | comparative toxic unit for human (CTUh) | CTUh | 100 | 4.77e-07 | 6.67e-14 | 9.81e-06 | 0.000265 | 100 % | 100 % | 0 |
| EF v3.1 | human toxicity: carcinogenic, inorganics | comparative toxic unit for human (CTUh) | CTUh | 100 | 5.24e-07 | 3.56e-14 | 1.68e-05 | 0.000488 | 100 % | 100 % | 0 |
| EF v3.1 | human toxicity: carcinogenic, organics | comparative toxic unit for human (CTUh) | CTUh | 100 | 4.26e-07 | 0 | 1.1e-05 | 0.000209 | 100 % | 100 % | 0 |
| EF v3.1 | human toxicity: non-carcinogenic | comparative toxic unit for human (CTUh) | CTUh | 100 | 3.33e-07 | 2.53e-09 | 1.24e-05 | 0.000466 | 100 % | 100 % | 0 |
| EF v3.1 | human toxicity: non-carcinogenic, inorganics | comparative toxic unit for human (CTUh) | CTUh | 100 | 4.44e-07 | 6.01e-09 | 1.41e-05 | 0.000523 | 100 % | 100 % | 0 |
| EF v3.1 | human toxicity: non-carcinogenic, organics | comparative toxic unit for human (CTUh) | CTUh | 100 | 4.33e-07 | 2.23e-08 | 1.49e-05 | 0.000183 | 100 % | 100 % | 0 |
| EF v3.1 | ionising radiation: human health | human exposure efficiency relative to u235 | kBq U235-Eq | 100 | 5.01e-07 | 2.87e-09 | 2.79e-05 | 0.000793 | 100 % | 100 % | 0 |
| EF v3.1 | land use | soil quality index | dimensionless | 100 | 6.34e-06 | 0 | 0.000194 | 0.00111 | 100 % | 100 % | 0 |
| EF v3.1 | material resources: metals/minerals | abiotic depletion potential (ADP): elements (ultimate reserves) | kg Sb-Eq | 100 | 1.33e-06 | 9.42e-09 | 6.5e-05 | 0.00183 | 100 % | 100 % | 0 |
| EF v3.1 | ozone depletion | ozone depletion potential (ODP) | kg CFC-11-Eq | 100 | 2.07e-07 | 0 | 8.74e-06 | 0.000206 | 100 % | 100 % | 0 |
| EF v3.1 | particulate matter formation | impact on human health | disease incidence | 100 | 3.79e-07 | 1.04e-14 | 1.02e-05 | 0.000156 | 100 % | 100 % | 0 |
| EF v3.1 | photochemical oxidant formation: human health | tropospheric ozone concentration increase | kg NMVOC-Eq | 100 | 2.71e-07 | 2.11e-08 | 6.82e-06 | 0.00017 | 100 % | 100 % | 0 |
| EF v3.1 | water use | user deprivation potential (deprivation-weighted water consumption) | m3 world Eq deprived | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| EF v3.1 no LT | acidification no LT | accumulated exceedance (AE) no LT | mol H+-Eq | 100 | 2.9e-07 | -1.97e-08 | 5.59e-06 | 0.000227 | 100 % | 100 % | 0 |
| EF v3.1 no LT | climate change no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 2.05e-07 | 0 | 5.06e-06 | 0.00029 | 100 % | 100 % | 0 |
| EF v3.1 no LT | climate change: biogenic no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 1.16e-06 | 0 | 5.68e-05 | 0.000466 | 100 % | 100 % | 0 |
| EF v3.1 no LT | climate change: fossil no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 2.25e-07 | 0 | 5.04e-06 | 0.0003 | 100 % | 100 % | 0 |
| EF v3.1 no LT | climate change: land use and land use change no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 3.35e-07 | 0 | 1.16e-05 | 0.000106 | 100 % | 100 % | 0 |
| EF v3.1 no LT | ecotoxicity: freshwater no LT | comparative toxic unit for ecosystems (CTUe) no LT | CTUe | 100 | 3.15e-07 | 0 | 8.48e-06 | 0.000377 | 100 % | 100 % | 0 |
| EF v3.1 no LT | ecotoxicity: freshwater, inorganics no LT | comparative toxic unit for ecosystems (CTUe) no LT | CTUe | 100 | 4.43e-07 | 0 | 1.04e-05 | 0.000396 | 100 % | 100 % | 0 |
| EF v3.1 no LT | ecotoxicity: freshwater, organics no LT | comparative toxic unit for ecosystems (CTUe) no LT | CTUe | 100 | 3.94e-07 | 2.72e-09 | 1.58e-05 | 0.000125 | 100 % | 100 % | 0 |
| EF v3.1 no LT | energy resources: non-renewable no LT | abiotic depletion potential (ADP): fossil fuels no LT | MJ, net calorific value | 100 | 2.09e-07 | 1.87e-08 | 6.32e-06 | 0.000242 | 100 % | 100 % | 0 |
| EF v3.1 no LT | eutrophication: freshwater no LT | fraction of nutrients reaching freshwater end compartment (P) no LT | kg P-Eq | 100 | 3.65e-07 | 0 | 5.48e-06 | 0.000893 | 100 % | 100 % | 0 |
| EF v3.1 no LT | eutrophication: marine no LT | fraction of nutrients reaching marine end compartment (N) no LT | kg N-Eq | 100 | 2.02e-07 | -4.16e-08 | 5.34e-06 | 0.000107 | 100 % | 100 % | 0 |
| EF v3.1 no LT | eutrophication: terrestrial no LT | accumulated exceedance (AE) no LT | mol N-Eq | 100 | 2.55e-07 | -2.67e-08 | 1.08e-05 | 0.000135 | 100 % | 100 % | 0 |
| EF v3.1 no LT | human toxicity: carcinogenic no LT | comparative toxic unit for human (CTUh) no LT | CTUh | 100 | 4.77e-07 | 6.67e-14 | 9.81e-06 | 0.000265 | 100 % | 100 % | 0 |
| EF v3.1 no LT | human toxicity: carcinogenic, inorganics no LT | comparative toxic unit for human (CTUh) no LT | CTUh | 100 | 5.24e-07 | 3.56e-14 | 1.68e-05 | 0.000488 | 100 % | 100 % | 0 |
| EF v3.1 no LT | human toxicity: carcinogenic, organics no LT | comparative toxic unit for human (CTUh) no LT | CTUh | 100 | 4.26e-07 | 0 | 1.1e-05 | 0.000209 | 100 % | 100 % | 0 |
| EF v3.1 no LT | human toxicity: non-carcinogenic no LT | comparative toxic unit for human (CTUh) no LT | CTUh | 100 | 3.33e-07 | 2.53e-09 | 1.24e-05 | 0.000466 | 100 % | 100 % | 0 |
| EF v3.1 no LT | human toxicity: non-carcinogenic, inorganics no LT | comparative toxic unit for human (CTUh) no LT | CTUh | 100 | 4.44e-07 | 6.01e-09 | 1.41e-05 | 0.000523 | 100 % | 100 % | 0 |
| EF v3.1 no LT | human toxicity: non-carcinogenic, organics no LT | comparative toxic unit for human (CTUh) no LT | CTUh | 100 | 4.33e-07 | 2.23e-08 | 1.49e-05 | 0.000183 | 100 % | 100 % | 0 |
| EF v3.1 no LT | ionising radiation: human health no LT | human exposure efficiency relative to u235 no LT | kBq U235-Eq | 100 | 9.85e-07 | 3.05e-08 | 3.17e-05 | 0.000921 | 100 % | 100 % | 0 |
| EF v3.1 no LT | land use no LT | soil quality index no LT | dimensionless | 100 | 6.34e-06 | 0 | 0.000194 | 0.00111 | 100 % | 100 % | 0 |
| EF v3.1 no LT | material resources: metals/minerals no LT | abiotic depletion potential (ADP): elements (ultimate reserves) no LT | kg Sb-Eq | 100 | 1.33e-06 | 9.42e-09 | 6.5e-05 | 0.00183 | 100 % | 100 % | 0 |
| EF v3.1 no LT | ozone depletion no LT | ozone depletion potential (ODP) no LT | kg CFC-11-Eq | 100 | 2.07e-07 | 0 | 8.74e-06 | 0.000206 | 100 % | 100 % | 0 |
| EF v3.1 no LT | particulate matter formation no LT | impact on human health no LT | disease incidence | 100 | 3.35e-07 | 4.45e-09 | 8.49e-06 | 0.000144 | 100 % | 100 % | 0 |
| EF v3.1 no LT | photochemical oxidant formation: human health no LT | tropospheric ozone concentration increase no LT | kg NMVOC-Eq | 100 | 2.71e-07 | 2.11e-08 | 6.82e-06 | 0.00017 | 100 % | 100 % | 0 |
| EF v3.1 no LT | water use no LT | user deprivation potential (deprivation-weighted water consumption) no LT | m3 world Eq deprived | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |

## How to read this

- 'Validated' requires that at least 95 % of all results agree within 0.1 % and that every category has at least 95 % of its results within 1 %. A category below that is named above and its results should not be published before the cause is found.
- The benchmark checks Cyclia's matrix calculation, its import of ecoinvent and the matching of the method's factors to ecoinvent's elementary flows. It does not check the method itself: Cyclia uses the factors as published.
- Only the ecoinvent version and system model named were compared. Another version or system model needs its own run.
- 'Within round-off' counts results whose net value is the small remainder of positive and negative contributions that cancel, and where the gap to ecoinvent is below 1e-9 of the sum of the absolute contributions (Cyclia 1.9.1 and later; empty for earlier runs). These count as agreeing.
- From Cyclia 1.9.2, a deviating result that Cyclia's own solver does not determine to 0.1 % (forward, adjoint and refined solutions differ) and that is below 1e-6 of the category's largest result in ecoinvent's file is reported as 'below numerical resolution' and left out of the statistics, with its count.
- No ecoinvent data is reproduced here: the report holds deviation statistics only.

## Reproduce

1. Import the ecoinvent database (ecoSpold2) and the method in Cyclia.
2. Validation > ecoinvent: choose ecoinvent's cumulative LCIA results file for the same version and system model (optionally the cumulative LCI file too) and run the benchmark.
3. Validation > Benchmark Centre > Publish benchmark reports writes this file.
