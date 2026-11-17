# ReCiPe benchmark: Cyclia against ecoinvent's cumulative LCIA results

Database: ecoinvent (3.13, cutoff)

**ReCiPe 2016 v1.03, endpoint (E)**: Validated. 100.00 % of 2,500 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**ReCiPe 2016 v1.03, endpoint (E) no LT**: Validated. 100.00 % of 2,500 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**ReCiPe 2016 v1.03, endpoint (H)**: Validated. 100.00 % of 2,500 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**ReCiPe 2016 v1.03, endpoint (H) no LT**: Validated. 100.00 % of 2,500 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**ReCiPe 2016 v1.03, endpoint (I)**: Validated. 100.00 % of 2,400 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**ReCiPe 2016 v1.03, endpoint (I) no LT**: Validated. 100.00 % of 2,400 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**ReCiPe 2016 v1.03, midpoint (E)**: Validated. 100.00 % of 1,800 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**ReCiPe 2016 v1.03, midpoint (E) no LT**: Validated. 100.00 % of 1,800 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**ReCiPe 2016 v1.03, midpoint (H)**: Validated. 100.00 % of 1,800 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**ReCiPe 2016 v1.03, midpoint (H) no LT**: Validated. 100.00 % of 1,800 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**ReCiPe 2016 v1.03, midpoint (I)**: Validated. 100.00 % of 1,800 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**ReCiPe 2016 v1.03, midpoint (I) no LT**: Validated. 100.00 % of 1,800 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

## What was compared

- Reference: ecoinvent's own cumulative LCIA results for ecoinvent (3.13, cutoff), the file ecoinvent provides to licence holders with the database. Cyclia imported the same database (ecoSpold2) and the method, calculated every sampled dataset with its full supply chain and compared the scores, result by result.
- Results compared: 25,600 (datasets x impact categories).
- Datasets: 100 compared of 27,401 in the results file, matched by 'Activity UUID_Product UUID' (or by name, geography and product).
- The cumulative inventory was compared with ecoinvent's cumulative LCI as well, which separates deviations caused by the inventory from those caused by the factors.
- Software: Cyclia 1.9.2; run on 2026-11-17.

## Deviation per impact category

Deviation = |Cyclia - ecoinvent| / |ecoinvent| x 100, per dataset. Signed median: negative when Cyclia is lower for most datasets.

| Method | Category | Indicator | Unit | Results | Median % | Signed median % | 95th percentile % | Max % | Within 0.1 % | Within 1 % | Within round-off |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ReCiPe 2016 v1.03, endpoint (E) | ecosystem quality | acidification: terrestrial | species.yr | 100 | 2.27e-07 | -4.95e-09 | 6.08e-06 | 0.000268 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | ecosystem quality | climate change: freshwater ecosystems | species.yr | 100 | 2.21e-07 | 0 | 5.46e-06 | 0.000317 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | ecosystem quality | climate change: terrestrial ecosystems | species.yr | 100 | 2.21e-07 | 0 | 5.46e-06 | 0.000317 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | ecosystem quality | ecotoxicity: freshwater | species.yr | 100 | 6.36e-07 | 1.19e-08 | 2.76e-05 | 0.00104 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | ecosystem quality | ecotoxicity: marine | species.yr | 100 | 5.64e-07 | 0 | 2.15e-05 | 0.000264 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | ecosystem quality | ecotoxicity: terrestrial | species.yr | 100 | 3.87e-07 | 0 | 1.68e-05 | 0.00026 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | ecosystem quality | eutrophication: freshwater | species.yr | 100 | 4.54e-07 | 0 | 6.98e-06 | 0.000977 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | ecosystem quality | eutrophication: marine | species.yr | 100 | 2.11e-07 | 1.52e-11 | 6.89e-06 | 0.000468 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | ecosystem quality | land use | species.yr | 100 | 4.28e-06 | -3.13e-08 | 0.000108 | 0.00026 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | ecosystem quality | photochemical oxidant formation: terrestrial ecosystems | species.yr | 100 | 2.86e-07 | -2.33e-08 | 4.97e-06 | 0.000134 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | ecosystem quality | water use: aquatic ecosystems | species.yr | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | ecosystem quality | water use: terrestrial ecosystems | species.yr | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | human health | climate change: human health | DALYs | 100 | 2.21e-07 | 0 | 5.46e-06 | 0.000317 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | human health | human toxicity: carcinogenic | DALYs | 100 | 7.14e-07 | 2.86e-08 | 2.11e-05 | 0.000328 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | human health | human toxicity: non-carcinogenic | DALYs | 100 | 6.07e-07 | 0 | 2.08e-05 | 0.000239 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | human health | ionising radiation | DALYs | 100 | 4.99e-07 | 2.76e-09 | 2.79e-05 | 0.000794 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | human health | ozone depletion | DALYs | 100 | 1.11e-07 | -1.58e-08 | 3.36e-06 | 6.89e-05 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | human health | particulate matter formation | DALYs | 100 | 2.87e-07 | -1.88e-08 | 5.56e-06 | 0.000265 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | human health | photochemical oxidant formation: human health | DALYs | 100 | 2.91e-07 | -3.99e-08 | 5.19e-06 | 0.00013 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | human health | water use: human health | DALYs | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | natural resources | energy resources: non-renewable, fossil | USD 2013 | 100 | 3.25e-07 | 2.69e-08 | 8.36e-06 | 0.000198 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | natural resources | material resources: metals/minerals | USD 2013 | 100 | 1.21e-06 | 0 | 6.22e-05 | 0.00309 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | total: ecosystem quality | ecosystem quality | species.yr | 100 | 3.03e-07 | 0 | 8.79e-06 | 0.000247 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | total: human health | human health | DALYs | 100 | 3.54e-07 | 2.9e-09 | 1.68e-05 | 0.00021 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) | total: natural resources | natural resources | USD 2013 | 100 | 3.31e-07 | 2.07e-08 | 7.71e-06 | 0.000206 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | ecosystem quality no LT | acidification: terrestrial no LT | species.yr | 100 | 2.27e-07 | -4.94e-09 | 6.08e-06 | 0.000268 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | ecosystem quality no LT | climate change: freshwater ecosystems no LT | species.yr | 100 | 2.21e-07 | 0 | 5.46e-06 | 0.000317 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | ecosystem quality no LT | climate change: terrestrial ecosystems no LT | species.yr | 100 | 2.21e-07 | 0 | 5.46e-06 | 0.000317 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | ecosystem quality no LT | ecotoxicity: freshwater no LT | species.yr | 100 | 2.44e-07 | 5.49e-09 | 1.24e-05 | 0.000149 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | ecosystem quality no LT | ecotoxicity: marine no LT | species.yr | 100 | 2.72e-07 | 0 | 9.92e-06 | 0.00157 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | ecosystem quality no LT | ecotoxicity: terrestrial no LT | species.yr | 100 | 3.92e-07 | 0 | 1.66e-05 | 0.00026 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | ecosystem quality no LT | eutrophication: freshwater no LT | species.yr | 100 | 3.63e-07 | 0 | 5.43e-06 | 0.000892 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | ecosystem quality no LT | eutrophication: marine no LT | species.yr | 100 | 1.1e-07 | 7.55e-09 | 6.31e-06 | 0.000278 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | ecosystem quality no LT | land use no LT | species.yr | 100 | 4.28e-06 | -3.13e-08 | 0.000108 | 0.00026 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | ecosystem quality no LT | photochemical oxidant formation: terrestrial ecosystems no LT | species.yr | 100 | 2.87e-07 | -2.33e-08 | 4.97e-06 | 0.000134 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | ecosystem quality no LT | water use: aquatic ecosystems no LT | species.yr | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | ecosystem quality no LT | water use: terrestrial ecosystems no LT | species.yr | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | human health no LT | climate change: human health no LT | DALYs | 100 | 2.21e-07 | 0 | 5.46e-06 | 0.000317 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | human health no LT | human toxicity: carcinogenic no LT | DALYs | 100 | 1.34e-06 | 0 | 3.96e-05 | 0.00157 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | human health no LT | human toxicity: non-carcinogenic no LT | DALYs | 100 | 4.07e-07 | 0 | 9.85e-06 | 0.0013 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | human health no LT | ionising radiation no LT | DALYs | 100 | 9.44e-07 | 2.98e-08 | 3.14e-05 | 0.00092 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | human health no LT | ozone depletion no LT | DALYs | 100 | 1.11e-07 | -1.58e-08 | 3.35e-06 | 6.89e-05 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | human health no LT | particulate matter formation no LT | DALYs | 100 | 2.81e-07 | -1.93e-08 | 5.27e-06 | 0.000262 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | human health no LT | photochemical oxidant formation: human health no LT | DALYs | 100 | 2.91e-07 | -3.98e-08 | 5.18e-06 | 0.00013 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | human health no LT | water use: human health no LT | DALYs | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | natural resources no LT | energy resources: non-renewable, fossil no LT | USD 2013 | 100 | 3.25e-07 | 2.69e-08 | 8.36e-06 | 0.000198 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | natural resources no LT | material resources: metals/minerals no LT | USD 2013 | 100 | 1.21e-06 | 0 | 6.22e-05 | 0.00309 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | total: ecosystem quality no LT | ecosystem quality no LT | species.yr | 100 | 1.78e-07 | 7.32e-15 | 3.41e-06 | 0.000276 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | total: human health no LT | human health no LT | DALYs | 100 | 2.28e-07 | 0 | 6.28e-06 | 0.000256 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (E) no LT | total: natural resources no LT | natural resources no LT | USD 2013 | 100 | 3.31e-07 | 2.07e-08 | 7.71e-06 | 0.000206 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | ecosystem quality | acidification: terrestrial | species.yr | 100 | 2.27e-07 | -4.95e-09 | 6.08e-06 | 0.000268 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | ecosystem quality | climate change: freshwater ecosystems | species.yr | 100 | 2.07e-07 | 0 | 5.05e-06 | 0.000285 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | ecosystem quality | climate change: terrestrial ecosystems | species.yr | 100 | 2.07e-07 | 0 | 5.05e-06 | 0.000285 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | ecosystem quality | ecotoxicity: freshwater | species.yr | 100 | 6.44e-07 | 1.19e-08 | 2.83e-05 | 0.00104 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | ecosystem quality | ecotoxicity: marine | species.yr | 100 | 5.66e-07 | 1.09e-08 | 2.77e-05 | 0.00125 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | ecosystem quality | ecotoxicity: terrestrial | species.yr | 100 | 3.88e-07 | 0 | 1.67e-05 | 0.000251 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | ecosystem quality | eutrophication: freshwater | species.yr | 100 | 4.54e-07 | 0 | 6.98e-06 | 0.000977 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | ecosystem quality | eutrophication: marine | species.yr | 100 | 2.11e-07 | 1.52e-11 | 6.89e-06 | 0.000468 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | ecosystem quality | land use | species.yr | 100 | 4.28e-06 | -3.13e-08 | 0.000108 | 0.00026 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | ecosystem quality | photochemical oxidant formation: terrestrial ecosystems | species.yr | 100 | 2.86e-07 | -2.33e-08 | 4.97e-06 | 0.000134 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | ecosystem quality | water use: aquatic ecosystems | species.yr | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | ecosystem quality | water use: terrestrial ecosystems | species.yr | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | human health | climate change: human health | DALYs | 100 | 2.07e-07 | 0 | 5.05e-06 | 0.000285 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | human health | human toxicity: carcinogenic | DALYs | 100 | 7.06e-07 | 2.23e-08 | 2.03e-05 | 0.000221 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | human health | human toxicity: non-carcinogenic | DALYs | 100 | 5.75e-07 | 0 | 1.7e-05 | 0.000331 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | human health | ionising radiation | DALYs | 100 | 3.21e-07 | 0 | 2.81e-05 | 0.000727 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | human health | ozone depletion | DALYs | 100 | 1.08e-07 | -1.42e-08 | 3.23e-06 | 7.06e-05 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | human health | particulate matter formation | DALYs | 100 | 2.87e-07 | -1.88e-08 | 5.56e-06 | 0.000265 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | human health | photochemical oxidant formation: human health | DALYs | 100 | 2.91e-07 | -3.99e-08 | 5.19e-06 | 0.00013 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | human health | water use: human health | DALYs | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | natural resources | energy resources: non-renewable, fossil | USD 2013 | 100 | 3.34e-07 | 2.85e-08 | 8.56e-06 | 0.000197 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | natural resources | material resources: metals/minerals | USD 2013 | 100 | 1.21e-06 | 0 | 6.22e-05 | 0.00309 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | total: ecosystem quality | ecosystem quality | species.yr | 100 | 2.84e-07 | 0 | 5.03e-06 | 0.00026 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | total: human health | human health | DALYs | 100 | 2.57e-07 | 0 | 4.83e-06 | 0.000242 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) | total: natural resources | natural resources | USD 2013 | 100 | 3.37e-07 | 2.31e-08 | 7.87e-06 | 0.000204 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | ecosystem quality no LT | acidification: terrestrial no LT | species.yr | 100 | 2.27e-07 | -4.94e-09 | 6.08e-06 | 0.000268 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | ecosystem quality no LT | climate change: freshwater ecosystems no LT | species.yr | 100 | 2.07e-07 | 0 | 5.05e-06 | 0.000285 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | ecosystem quality no LT | climate change: terrestrial ecosystems no LT | species.yr | 100 | 2.07e-07 | 0 | 5.05e-06 | 0.000285 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | ecosystem quality no LT | ecotoxicity: freshwater no LT | species.yr | 100 | 3.01e-07 | 5.98e-09 | 2.09e-05 | 0.000214 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | ecosystem quality no LT | ecotoxicity: marine no LT | species.yr | 100 | 3.97e-07 | 0 | 1.09e-05 | 0.000502 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | ecosystem quality no LT | ecotoxicity: terrestrial no LT | species.yr | 100 | 3.93e-07 | 0 | 1.65e-05 | 0.000251 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | ecosystem quality no LT | eutrophication: freshwater no LT | species.yr | 100 | 3.63e-07 | 0 | 5.43e-06 | 0.000892 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | ecosystem quality no LT | eutrophication: marine no LT | species.yr | 100 | 1.1e-07 | 7.55e-09 | 6.31e-06 | 0.000278 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | ecosystem quality no LT | land use no LT | species.yr | 100 | 4.28e-06 | -3.13e-08 | 0.000108 | 0.00026 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | ecosystem quality no LT | photochemical oxidant formation: terrestrial ecosystems no LT | species.yr | 100 | 2.87e-07 | -2.33e-08 | 4.97e-06 | 0.000134 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | ecosystem quality no LT | water use: aquatic ecosystems no LT | species.yr | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | ecosystem quality no LT | water use: terrestrial ecosystems no LT | species.yr | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | human health no LT | climate change: human health no LT | DALYs | 100 | 2.07e-07 | 0 | 5.05e-06 | 0.000285 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | human health no LT | human toxicity: carcinogenic no LT | DALYs | 100 | 1.11e-06 | 0 | 2.84e-05 | 0.000289 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | human health no LT | human toxicity: non-carcinogenic no LT | DALYs | 100 | 3.49e-07 | 0 | 1.31e-05 | 0.000425 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | human health no LT | ionising radiation no LT | DALYs | 100 | 6.79e-07 | 2e-09 | 2.8e-05 | 0.000865 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | human health no LT | ozone depletion no LT | DALYs | 100 | 1.08e-07 | -1.42e-08 | 3.23e-06 | 7.06e-05 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | human health no LT | particulate matter formation no LT | DALYs | 100 | 2.81e-07 | -1.93e-08 | 5.27e-06 | 0.000262 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | human health no LT | photochemical oxidant formation: human health no LT | DALYs | 100 | 2.91e-07 | -3.98e-08 | 5.18e-06 | 0.00013 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | human health no LT | water use: human health no LT | DALYs | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | natural resources no LT | energy resources: non-renewable, fossil no LT | USD 2013 | 100 | 3.34e-07 | 2.85e-08 | 8.56e-06 | 0.000197 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | natural resources no LT | material resources: metals/minerals no LT | USD 2013 | 100 | 1.21e-06 | 0 | 6.22e-05 | 0.00309 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | total: ecosystem quality no LT | ecosystem quality no LT | species.yr | 100 | 3.42e-07 | 0 | 6.16e-06 | 0.000251 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | total: human health no LT | human health no LT | DALYs | 100 | 2.05e-07 | 0 | 4.66e-06 | 0.000276 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (H) no LT | total: natural resources no LT | natural resources no LT | USD 2013 | 100 | 3.37e-07 | 2.31e-08 | 7.87e-06 | 0.000204 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | ecosystem quality | acidification: terrestrial | species.yr | 100 | 2.27e-07 | -4.95e-09 | 6.08e-06 | 0.000268 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | ecosystem quality | climate change: freshwater ecosystems | species.yr | 100 | 2.22e-07 | 0 | 5e-06 | 0.000255 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | ecosystem quality | climate change: terrestrial ecosystems | species.yr | 100 | 2.22e-07 | 0 | 5e-06 | 0.000255 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | ecosystem quality | ecotoxicity: freshwater | species.yr | 100 | 6.41e-07 | 1.13e-08 | 2.83e-05 | 0.00102 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | ecosystem quality | ecotoxicity: marine | species.yr | 100 | 5.5e-07 | 8.33e-09 | 2.59e-05 | 0.000944 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | ecosystem quality | ecotoxicity: terrestrial | species.yr | 100 | 3.91e-07 | 0 | 2.07e-05 | 0.000178 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | ecosystem quality | eutrophication: freshwater | species.yr | 100 | 4.54e-07 | 0 | 6.98e-06 | 0.000977 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | ecosystem quality | eutrophication: marine | species.yr | 100 | 2.11e-07 | 1.52e-11 | 6.89e-06 | 0.000468 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | ecosystem quality | land use | species.yr | 100 | 4.28e-06 | -3.13e-08 | 0.000108 | 0.00026 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | ecosystem quality | photochemical oxidant formation: terrestrial ecosystems | species.yr | 100 | 2.86e-07 | -2.32e-08 | 4.98e-06 | 0.000134 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | ecosystem quality | water use: aquatic ecosystems | species.yr | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | human health | climate change: human health | DALYs | 100 | 2.22e-07 | 0 | 5e-06 | 0.000255 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | human health | human toxicity: carcinogenic | DALYs | 100 | 3.98e-07 | -1.22e-10 | 1.4e-05 | 4.35e-05 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | human health | human toxicity: non-carcinogenic | DALYs | 100 | 5.33e-07 | 7.38e-14 | 1.95e-05 | 0.000369 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | human health | ionising radiation | DALYs | 100 | 3.15e-07 | 2.87e-10 | 2.96e-05 | 0.000722 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | human health | ozone depletion | DALYs | 100 | 1.02e-07 | -8.57e-09 | 3.29e-06 | 7.58e-05 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | human health | particulate matter formation | DALYs | 100 | 4.19e-07 | -4.7e-08 | 1.06e-05 | 0.000301 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | human health | photochemical oxidant formation: human health | DALYs | 100 | 2.9e-07 | -3.97e-08 | 5.19e-06 | 0.00013 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | human health | water use: human health | DALYs | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | natural resources | energy resources: non-renewable, fossil | USD 2013 | 100 | 3.34e-07 | 2.85e-08 | 8.56e-06 | 0.000197 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | natural resources | material resources: metals/minerals | USD 2013 | 100 | 1.14e-06 | 0 | 6.18e-05 | 0.00291 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | total: ecosystem quality | ecosystem quality | species.yr | 100 | 4.93e-07 | -8.47e-15 | 8.92e-06 | 0.00024 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | total: human health | human health | DALYs | 100 | 3.15e-07 | -8.18e-09 | 5.4e-06 | 0.00028 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) | total: natural resources | natural resources | USD 2013 | 100 | 3.36e-07 | 2.18e-08 | 8.21e-06 | 0.000201 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | ecosystem quality no LT | acidification: terrestrial no LT | species.yr | 100 | 2.27e-07 | -4.94e-09 | 6.08e-06 | 0.000268 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | ecosystem quality no LT | climate change: freshwater ecosystems no LT | species.yr | 100 | 2.22e-07 | 0 | 5e-06 | 0.000255 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | ecosystem quality no LT | climate change: terrestrial ecosystems no LT | species.yr | 100 | 2.22e-07 | 0 | 5e-06 | 0.000255 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | ecosystem quality no LT | ecotoxicity: freshwater no LT | species.yr | 100 | 3.11e-07 | 1.07e-09 | 2e-05 | 0.000216 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | ecosystem quality no LT | ecotoxicity: marine no LT | species.yr | 100 | 3.44e-07 | 0 | 1.09e-05 | 0.000246 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | ecosystem quality no LT | ecotoxicity: terrestrial no LT | species.yr | 100 | 3.96e-07 | 0 | 2.08e-05 | 0.000178 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | ecosystem quality no LT | eutrophication: freshwater no LT | species.yr | 100 | 3.63e-07 | 0 | 5.43e-06 | 0.000892 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | ecosystem quality no LT | eutrophication: marine no LT | species.yr | 100 | 1.1e-07 | 7.55e-09 | 6.31e-06 | 0.000278 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | ecosystem quality no LT | land use no LT | species.yr | 100 | 4.28e-06 | -3.13e-08 | 0.000108 | 0.00026 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | ecosystem quality no LT | photochemical oxidant formation: terrestrial ecosystems no LT | species.yr | 100 | 2.87e-07 | -2.32e-08 | 4.97e-06 | 0.000134 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | ecosystem quality no LT | water use: aquatic ecosystems no LT | species.yr | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | human health no LT | climate change: human health no LT | DALYs | 100 | 2.22e-07 | 0 | 5e-06 | 0.000255 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | human health no LT | human toxicity: carcinogenic no LT | DALYs | 100 | 4.08e-07 | -4.5e-08 | 1.2e-05 | 8.6e-05 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | human health no LT | human toxicity: non-carcinogenic no LT | DALYs | 100 | 3.48e-07 | 9.52e-14 | 1.84e-05 | 0.0002 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | human health no LT | ionising radiation no LT | DALYs | 100 | 5.32e-07 | 9.51e-09 | 2.88e-05 | 0.000827 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | human health no LT | ozone depletion no LT | DALYs | 100 | 1.02e-07 | -8.57e-09 | 3.29e-06 | 7.58e-05 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | human health no LT | particulate matter formation no LT | DALYs | 100 | 4.13e-07 | -6.08e-08 | 9.36e-06 | 0.000293 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | human health no LT | photochemical oxidant formation: human health no LT | DALYs | 100 | 2.91e-07 | -3.96e-08 | 5.18e-06 | 0.00013 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | human health no LT | water use: human health no LT | DALYs | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | natural resources no LT | energy resources: non-renewable, fossil no LT | USD 2013 | 100 | 3.34e-07 | 2.85e-08 | 8.56e-06 | 0.000197 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | natural resources no LT | material resources: metals/minerals no LT | USD 2013 | 100 | 1.14e-06 | 0 | 6.18e-05 | 0.00291 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | total: ecosystem quality no LT | ecosystem quality no LT | species.yr | 100 | 5.97e-07 | -5.38e-09 | 1.01e-05 | 0.000224 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | total: human health no LT | human health no LT | DALYs | 100 | 2.47e-07 | -7.67e-09 | 6.42e-06 | 0.000271 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, endpoint (I) no LT | total: natural resources no LT | natural resources no LT | USD 2013 | 100 | 3.36e-07 | 2.18e-08 | 8.21e-06 | 0.000201 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) | acidification: terrestrial | terrestrial acidification potential (TAP) | kg SO2-Eq | 100 | 2.27e-07 | -4.94e-09 | 6.08e-06 | 0.000268 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) | climate change | global warming potential (GWP1000) | kg CO2-Eq | 100 | 2.21e-07 | 0 | 5.46e-06 | 0.000317 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) | ecotoxicity: freshwater | freshwater ecotoxicity potential (FETP) | kg 1,4-DCB-Eq | 100 | 6.36e-07 | 1.19e-08 | 2.76e-05 | 0.00104 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) | ecotoxicity: marine | marine ecotoxicity potential (METP) | kg 1,4-DCB-Eq | 100 | 5.64e-07 | 7.21e-15 | 2.15e-05 | 0.000264 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) | ecotoxicity: terrestrial | terrestrial ecotoxicity potential (TETP) | kg 1,4-DCB-Eq | 100 | 3.87e-07 | 0 | 1.68e-05 | 0.00026 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) | energy resources: non-renewable, fossil | fossil fuel potential (FFP) | kg oil-Eq | 100 | 2.28e-07 | 2.24e-08 | 6.98e-06 | 0.000236 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) | eutrophication: freshwater | freshwater eutrophication potential (FEP) | kg P-Eq | 100 | 4.54e-07 | 0 | 6.98e-06 | 0.000977 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) | eutrophication: marine | marine eutrophication potential (MEP) | kg N-Eq | 100 | 2.11e-07 | 1.52e-11 | 6.88e-06 | 0.000468 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) | human toxicity: carcinogenic | human toxicity potential (HTPc) | kg 1,4-DCB-Eq | 100 | 7.14e-07 | 2.86e-08 | 2.11e-05 | 0.000328 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) | human toxicity: non-carcinogenic | human toxicity potential (HTPnc) | kg 1,4-DCB-Eq | 100 | 6.07e-07 | 0 | 2.08e-05 | 0.000239 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) | ionising radiation | ionising radiation potential (IRP) | kBq Co-60-Eq | 100 | 4.98e-07 | 2.78e-09 | 2.79e-05 | 0.000794 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) | land use | agricultural land occupation (LOP) | m2*a crop-Eq | 100 | 4.29e-06 | -3.13e-08 | 0.000108 | 0.00026 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) | material resources: metals/minerals | surplus ore potential (SOP) | kg Cu-Eq | 100 | 1.21e-06 | 0 | 6.22e-05 | 0.00309 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) | ozone depletion | ozone depletion potential (ODPinfinite) | kg CFC-11-Eq | 100 | 1.11e-07 | -1.58e-08 | 3.35e-06 | 6.89e-05 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) | particulate matter formation | particulate matter formation potential (PMFP) | kg PM2.5-Eq | 100 | 2.87e-07 | -1.87e-08 | 5.56e-06 | 0.000265 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) | photochemical oxidant formation: human health | photochemical oxidant formation potential: humans (HOFP) | kg NOx-Eq | 100 | 2.91e-07 | -3.99e-08 | 5.19e-06 | 0.00013 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) | photochemical oxidant formation: terrestrial ecosystems | photochemical oxidant formation potential: ecosystems (EOFP) | kg NOx-Eq | 100 | 2.86e-07 | -2.33e-08 | 4.97e-06 | 0.000134 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) | water use | water consumption potential (WCP) | m3 | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) no LT | acidification: terrestrial no LT | terrestrial acidification potential (TAP) no LT | kg SO2-Eq | 100 | 2.27e-07 | -4.94e-09 | 6.08e-06 | 0.000268 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) no LT | climate change no LT | global warming potential (GWP1000) no LT | kg CO2-Eq | 100 | 2.21e-07 | 0 | 5.46e-06 | 0.000317 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) no LT | ecotoxicity: freshwater no LT | freshwater ecotoxicity potential (FETP) no LT | kg 1,4-DCB-Eq | 100 | 2.45e-07 | 5.49e-09 | 1.25e-05 | 0.00015 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) no LT | ecotoxicity: marine no LT | marine ecotoxicity potential (METP) no LT | kg 1,4-DCB-Eq | 100 | 2.7e-07 | 0 | 9.92e-06 | 0.00157 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) no LT | ecotoxicity: terrestrial no LT | terrestrial ecotoxicity potential (TETP) no LT | kg 1,4-DCB-Eq | 100 | 3.92e-07 | 0 | 1.66e-05 | 0.00026 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) no LT | energy resources: non-renewable, fossil no LT | fossil fuel potential (FFP) no LT | kg oil-Eq | 100 | 2.28e-07 | 2.24e-08 | 6.98e-06 | 0.000236 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) no LT | eutrophication: freshwater no LT | freshwater eutrophication potential (FEP) no LT | kg P-Eq | 100 | 3.63e-07 | 0 | 5.42e-06 | 0.000892 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) no LT | eutrophication: marine no LT | marine eutrophication potential (MEP) no LT | kg N-Eq | 100 | 1.1e-07 | 7.55e-09 | 6.31e-06 | 0.000278 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) no LT | human toxicity: carcinogenic no LT | human toxicity potential (HTPc) no LT | kg 1,4-DCB-Eq | 100 | 1.34e-06 | 0 | 3.96e-05 | 0.00158 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) no LT | human toxicity: non-carcinogenic no LT | human toxicity potential (HTPnc) no LT | kg 1,4-DCB-Eq | 100 | 4.07e-07 | 0 | 9.85e-06 | 0.0013 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) no LT | ionising radiation no LT | ionising radiation potential (IRP) no LT | kBq Co-60-Eq | 100 | 9.44e-07 | 2.98e-08 | 3.14e-05 | 0.000919 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) no LT | land use no LT | agricultural land occupation (LOP) no LT | m2*a crop-Eq | 100 | 4.29e-06 | -3.13e-08 | 0.000108 | 0.00026 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) no LT | material resources: metals/minerals no LT | surplus ore potential (SOP) no LT | kg Cu-Eq | 100 | 1.21e-06 | 0 | 6.22e-05 | 0.00309 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) no LT | ozone depletion no LT | ozone depletion potential (ODPinfinite) no LT | kg CFC-11-Eq | 100 | 1.11e-07 | -1.58e-08 | 3.35e-06 | 6.89e-05 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) no LT | particulate matter formation no LT | particulate matter formation potential (PMFP) no LT | kg PM2.5-Eq | 100 | 2.81e-07 | -1.92e-08 | 5.27e-06 | 0.000262 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) no LT | photochemical oxidant formation: human health no LT | photochemical oxidant formation potential: humans (HOFP) no LT | kg NOx-Eq | 100 | 2.91e-07 | -3.99e-08 | 5.18e-06 | 0.00013 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) no LT | photochemical oxidant formation: terrestrial ecosystems no LT | photochemical oxidant formation potential: ecosystems (EOFP) no LT | kg NOx-Eq | 100 | 2.87e-07 | -2.33e-08 | 4.97e-06 | 0.000134 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (E) no LT | water use no LT | water consumption potential (WCP) no LT | m3 | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) | acidification: terrestrial | terrestrial acidification potential (TAP) | kg SO2-Eq | 100 | 2.27e-07 | -4.94e-09 | 6.08e-06 | 0.000268 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) | climate change | global warming potential (GWP100) | kg CO2-Eq | 100 | 2.07e-07 | 0 | 5.05e-06 | 0.000285 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) | ecotoxicity: freshwater | freshwater ecotoxicity potential (FETP) | kg 1,4-DCB-Eq | 100 | 6.45e-07 | 1.19e-08 | 2.83e-05 | 0.00104 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) | ecotoxicity: marine | marine ecotoxicity potential (METP) | kg 1,4-DCB-Eq | 100 | 5.66e-07 | 1.09e-08 | 2.77e-05 | 0.00125 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) | ecotoxicity: terrestrial | terrestrial ecotoxicity potential (TETP) | kg 1,4-DCB-Eq | 100 | 3.87e-07 | 0 | 1.68e-05 | 0.00025 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) | energy resources: non-renewable, fossil | fossil fuel potential (FFP) | kg oil-Eq | 100 | 2.28e-07 | 2.24e-08 | 6.98e-06 | 0.000236 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) | eutrophication: freshwater | freshwater eutrophication potential (FEP) | kg P-Eq | 100 | 4.54e-07 | 0 | 6.98e-06 | 0.000977 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) | eutrophication: marine | marine eutrophication potential (MEP) | kg N-Eq | 100 | 2.11e-07 | 1.52e-11 | 6.88e-06 | 0.000468 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) | human toxicity: carcinogenic | human toxicity potential (HTPc) | kg 1,4-DCB-Eq | 100 | 7.06e-07 | 2.23e-08 | 2.03e-05 | 0.000221 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) | human toxicity: non-carcinogenic | human toxicity potential (HTPnc) | kg 1,4-DCB-Eq | 100 | 5.75e-07 | 0 | 1.7e-05 | 0.000331 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) | ionising radiation | ionising radiation potential (IRP) | kBq Co-60-Eq | 100 | 3.2e-07 | 8.05e-15 | 2.82e-05 | 0.000727 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) | land use | agricultural land occupation (LOP) | m2*a crop-Eq | 100 | 4.29e-06 | -3.13e-08 | 0.000108 | 0.00026 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) | material resources: metals/minerals | surplus ore potential (SOP) | kg Cu-Eq | 100 | 1.21e-06 | 0 | 6.22e-05 | 0.00309 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) | ozone depletion | ozone depletion potential (ODPinfinite) | kg CFC-11-Eq | 100 | 1.08e-07 | -1.42e-08 | 3.23e-06 | 7.06e-05 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) | particulate matter formation | particulate matter formation potential (PMFP) | kg PM2.5-Eq | 100 | 2.87e-07 | -1.87e-08 | 5.56e-06 | 0.000265 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) | photochemical oxidant formation: human health | photochemical oxidant formation potential: humans (HOFP) | kg NOx-Eq | 100 | 2.91e-07 | -3.99e-08 | 5.19e-06 | 0.00013 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) | photochemical oxidant formation: terrestrial ecosystems | photochemical oxidant formation potential: ecosystems (EOFP) | kg NOx-Eq | 100 | 2.86e-07 | -2.33e-08 | 4.97e-06 | 0.000134 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) | water use | water consumption potential (WCP) | m3 | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) no LT | acidification: terrestrial no LT | terrestrial acidification potential (TAP) no LT | kg SO2-Eq | 100 | 2.27e-07 | -4.94e-09 | 6.08e-06 | 0.000268 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) no LT | climate change no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 2.07e-07 | 0 | 5.05e-06 | 0.000285 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) no LT | ecotoxicity: freshwater no LT | freshwater ecotoxicity potential (FETP) no LT | kg 1,4-DCB-Eq | 100 | 3.01e-07 | 6.01e-09 | 2.09e-05 | 0.000214 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) no LT | ecotoxicity: marine no LT | marine ecotoxicity potential (METP) no LT | kg 1,4-DCB-Eq | 100 | 3.97e-07 | 0 | 1.09e-05 | 0.000502 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) no LT | ecotoxicity: terrestrial no LT | terrestrial ecotoxicity potential (TETP) no LT | kg 1,4-DCB-Eq | 100 | 3.93e-07 | 0 | 1.65e-05 | 0.000251 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) no LT | energy resources: non-renewable, fossil no LT | fossil fuel potential (FFP) no LT | kg oil-Eq | 100 | 2.28e-07 | 2.24e-08 | 6.98e-06 | 0.000236 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) no LT | eutrophication: freshwater no LT | freshwater eutrophication potential (FEP) no LT | kg P-Eq | 100 | 3.63e-07 | 0 | 5.42e-06 | 0.000892 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) no LT | eutrophication: marine no LT | marine eutrophication potential (MEP) no LT | kg N-Eq | 100 | 1.1e-07 | 7.55e-09 | 6.31e-06 | 0.000278 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) no LT | human toxicity: carcinogenic no LT | human toxicity potential (HTPc) no LT | kg 1,4-DCB-Eq | 100 | 1.11e-06 | -4.11e-14 | 2.84e-05 | 0.000288 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) no LT | human toxicity: non-carcinogenic no LT | human toxicity potential (HTPnc) no LT | kg 1,4-DCB-Eq | 100 | 3.49e-07 | 0 | 1.31e-05 | 0.000425 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) no LT | ionising radiation no LT | ionising radiation potential (IRP) no LT | kBq Co-60-Eq | 100 | 6.78e-07 | 2e-09 | 2.8e-05 | 0.000865 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) no LT | land use no LT | agricultural land occupation (LOP) no LT | m2*a crop-Eq | 100 | 4.29e-06 | -3.13e-08 | 0.000108 | 0.00026 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) no LT | material resources: metals/minerals no LT | surplus ore potential (SOP) no LT | kg Cu-Eq | 100 | 1.21e-06 | 0 | 6.22e-05 | 0.00309 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) no LT | ozone depletion no LT | ozone depletion potential (ODPinfinite) no LT | kg CFC-11-Eq | 100 | 1.08e-07 | -1.42e-08 | 3.23e-06 | 7.06e-05 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) no LT | particulate matter formation no LT | particulate matter formation potential (PMFP) no LT | kg PM2.5-Eq | 100 | 2.81e-07 | -1.92e-08 | 5.27e-06 | 0.000262 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) no LT | photochemical oxidant formation: human health no LT | photochemical oxidant formation potential: humans (HOFP) no LT | kg NOx-Eq | 100 | 2.91e-07 | -3.99e-08 | 5.18e-06 | 0.00013 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) no LT | photochemical oxidant formation: terrestrial ecosystems no LT | photochemical oxidant formation potential: ecosystems (EOFP) no LT | kg NOx-Eq | 100 | 2.87e-07 | -2.33e-08 | 4.97e-06 | 0.000134 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (H) no LT | water use no LT | water consumption potential (WCP) no LT | m3 | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) | acidification: terrestrial | terrestrial acidification potential (TAP) | kg SO2-Eq | 100 | 2.27e-07 | -4.94e-09 | 6.08e-06 | 0.000268 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) | climate change | global warming potential (GWP20) | kg CO2-Eq | 100 | 2.22e-07 | 0 | 5e-06 | 0.000255 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) | ecotoxicity: freshwater | freshwater ecotoxicity potential (FETP) | kg 1,4-DCB-Eq | 100 | 6.41e-07 | 1.13e-08 | 2.83e-05 | 0.00102 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) | ecotoxicity: marine | marine ecotoxicity potential (METP) | kg 1,4-DCB-Eq | 100 | 5.49e-07 | 8.32e-09 | 2.59e-05 | 0.000943 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) | ecotoxicity: terrestrial | terrestrial ecotoxicity potential (TETP) | kg 1,4-DCB-Eq | 100 | 3.91e-07 | 0 | 2.07e-05 | 0.000178 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) | energy resources: non-renewable, fossil | fossil fuel potential (FFP) | kg oil-Eq | 100 | 2.28e-07 | 2.24e-08 | 6.98e-06 | 0.000236 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) | eutrophication: freshwater | freshwater eutrophication potential (FEP) | kg P-Eq | 100 | 4.54e-07 | 0 | 6.98e-06 | 0.000977 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) | eutrophication: marine | marine eutrophication potential (MEP) | kg N-Eq | 100 | 2.11e-07 | 1.52e-11 | 6.88e-06 | 0.000468 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) | human toxicity: carcinogenic | human toxicity potential (HTPc) | kg 1,4-DCB-Eq | 100 | 3.99e-07 | -1.23e-10 | 1.4e-05 | 4.35e-05 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) | human toxicity: non-carcinogenic | human toxicity potential (HTPnc) | kg 1,4-DCB-Eq | 100 | 5.33e-07 | 7.77e-14 | 1.95e-05 | 0.000369 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) | ionising radiation | ionising radiation potential (IRP) | kBq Co-60-Eq | 100 | 3.15e-07 | 2.92e-10 | 2.96e-05 | 0.000722 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) | land use | agricultural land occupation (LOP) | m2*a crop-Eq | 100 | 4.29e-06 | -3.13e-08 | 0.000108 | 0.00026 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) | material resources: metals/minerals | surplus ore potential (SOP) | kg Cu-Eq | 100 | 1.13e-06 | 0 | 6.17e-05 | 0.0029 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) | ozone depletion | ozone depletion potential (ODPinfinite) | kg CFC-11-Eq | 100 | 1.02e-07 | -8.59e-09 | 3.3e-06 | 7.58e-05 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) | particulate matter formation | particulate matter formation potential (PMFP) | kg PM2.5-Eq | 100 | 4.19e-07 | -4.7e-08 | 1.06e-05 | 0.000301 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) | photochemical oxidant formation: human health | photochemical oxidant formation potential: humans (HOFP) | kg NOx-Eq | 100 | 2.9e-07 | -3.98e-08 | 5.19e-06 | 0.00013 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) | photochemical oxidant formation: terrestrial ecosystems | photochemical oxidant formation potential: ecosystems (EOFP) | kg NOx-Eq | 100 | 2.86e-07 | -2.32e-08 | 4.98e-06 | 0.000134 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) | water use | water consumption potential (WCP) | m3 | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) no LT | acidification: terrestrial no LT | terrestrial acidification potential (TAP) no LT | kg SO2-Eq | 100 | 2.27e-07 | -4.94e-09 | 6.08e-06 | 0.000268 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) no LT | climate change no LT | global warming potential (GWP20) no LT | kg CO2-Eq | 100 | 2.22e-07 | 0 | 5e-06 | 0.000255 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) no LT | ecotoxicity: freshwater no LT | freshwater ecotoxicity potential (FETP) no LT | kg 1,4-DCB-Eq | 100 | 3.11e-07 | 1.02e-09 | 2e-05 | 0.000216 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) no LT | ecotoxicity: marine no LT | marine ecotoxicity potential (METP) no LT | kg 1,4-DCB-Eq | 100 | 3.44e-07 | 0 | 1.09e-05 | 0.000247 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) no LT | ecotoxicity: terrestrial no LT | terrestrial ecotoxicity potential (TETP) no LT | kg 1,4-DCB-Eq | 100 | 3.96e-07 | 0 | 2.08e-05 | 0.000178 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) no LT | energy resources: non-renewable, fossil no LT | fossil fuel potential (FFP) no LT | kg oil-Eq | 100 | 2.28e-07 | 2.24e-08 | 6.98e-06 | 0.000236 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) no LT | eutrophication: freshwater no LT | freshwater eutrophication potential (FEP) no LT | kg P-Eq | 100 | 3.63e-07 | 0 | 5.42e-06 | 0.000892 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) no LT | eutrophication: marine no LT | marine eutrophication potential (MEP) no LT | kg N-Eq | 100 | 1.1e-07 | 7.55e-09 | 6.31e-06 | 0.000278 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) no LT | human toxicity: carcinogenic no LT | human toxicity potential (HTPc) no LT | kg 1,4-DCB-Eq | 100 | 4.09e-07 | -4.52e-08 | 1.2e-05 | 8.61e-05 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) no LT | human toxicity: non-carcinogenic no LT | human toxicity potential (HTPnc) no LT | kg 1,4-DCB-Eq | 100 | 3.48e-07 | 5.87e-15 | 1.84e-05 | 0.0002 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) no LT | ionising radiation no LT | ionising radiation potential (IRP) no LT | kBq Co-60-Eq | 100 | 5.32e-07 | 9.5e-09 | 2.88e-05 | 0.000827 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) no LT | land use no LT | agricultural land occupation (LOP) no LT | m2*a crop-Eq | 100 | 4.29e-06 | -3.13e-08 | 0.000108 | 0.00026 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) no LT | material resources: metals/minerals no LT | surplus ore potential (SOP) no LT | kg Cu-Eq | 100 | 1.13e-06 | 0 | 6.17e-05 | 0.0029 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) no LT | ozone depletion no LT | ozone depletion potential (ODPinfinite) no LT | kg CFC-11-Eq | 100 | 1.02e-07 | -8.59e-09 | 3.29e-06 | 7.58e-05 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) no LT | particulate matter formation no LT | particulate matter formation potential (PMFP) no LT | kg PM2.5-Eq | 100 | 4.13e-07 | -6.08e-08 | 9.36e-06 | 0.000293 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) no LT | photochemical oxidant formation: human health no LT | photochemical oxidant formation potential: humans (HOFP) no LT | kg NOx-Eq | 100 | 2.91e-07 | -3.97e-08 | 5.18e-06 | 0.00013 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) no LT | photochemical oxidant formation: terrestrial ecosystems no LT | photochemical oxidant formation potential: ecosystems (EOFP) no LT | kg NOx-Eq | 100 | 2.87e-07 | -2.32e-08 | 4.97e-06 | 0.000134 | 100 % | 100 % | 0 |
| ReCiPe 2016 v1.03, midpoint (I) no LT | water use no LT | water consumption potential (WCP) no LT | m3 | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |

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
