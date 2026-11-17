# TRACI v2.1 benchmark: Cyclia against ecoinvent's cumulative LCIA results

Database: ecoinvent (3.13, cutoff)

**TRACI v2.1**: Validated. 100.00 % of 900 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**TRACI v2.1 no LT**: Validated. 100.00 % of 900 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

## What was compared

- Reference: ecoinvent's own cumulative LCIA results for ecoinvent (3.13, cutoff), the file ecoinvent provides to licence holders with the database. Cyclia imported the same database (ecoSpold2) and the method, calculated every sampled dataset with its full supply chain and compared the scores, result by result.
- Results compared: 1,800 (datasets x impact categories).
- Datasets: 100 compared of 27,401 in the results file, matched by 'Activity UUID_Product UUID' (or by name, geography and product).
- The cumulative inventory was compared with ecoinvent's cumulative LCI as well, which separates deviations caused by the inventory from those caused by the factors.
- Software: Cyclia 1.9.2; run on 2026-11-17.

## Deviation per impact category

Deviation = |Cyclia - ecoinvent| / |ecoinvent| x 100, per dataset. Signed median: negative when Cyclia is lower for most datasets.

| Method | Category | Indicator | Unit | Results | Median % | Signed median % | 95th percentile % | Max % | Within 0.1 % | Within 1 % | Within round-off |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TRACI v2.1 | acidification | acidification potential (AP) | kg SO2-Eq | 100 | 2.74e-07 | -2.59e-08 | 4.96e-06 | 0.000211 | 100 % | 100 % | 0 |
| TRACI v2.1 | climate change | global warming potential (GWP100) | kg CO2-Eq | 100 | 2.04e-07 | 0 | 5.07e-06 | 0.000293 | 100 % | 100 % | 0 |
| TRACI v2.1 | ecotoxicity: freshwater | ecotoxicity: freshwater | CTUe | 100 | 5.55e-07 | 1.16e-08 | 2.36e-05 | 0.000867 | 100 % | 100 % | 0 |
| TRACI v2.1 | eutrophication | eutrophication potential | kg N-Eq | 100 | 2.96e-07 | 0 | 5.39e-06 | 0.000725 | 100 % | 100 % | 0 |
| TRACI v2.1 | human toxicity: carcinogenic | human toxicity: carcinogenic | CTUh | 100 | 7.08e-07 | 2.83e-08 | 2.11e-05 | 0.000315 | 100 % | 100 % | 0 |
| TRACI v2.1 | human toxicity: non-carcinogenic | human toxicity: non-carcinogenic | CTUh | 100 | 5.11e-07 | 0 | 1.48e-05 | 0.000357 | 100 % | 100 % | 0 |
| TRACI v2.1 | ozone depletion | ozone depletion potential (ODP) | kg CFC-11-Eq | 100 | 2.14e-07 | 1.03e-14 | 8.53e-06 | 0.000209 | 100 % | 100 % | 0 |
| TRACI v2.1 | particulate matter formation | particulate matter formation potential (PMFP) | kg PM2.5-Eq | 100 | 3.32e-07 | 0 | 9.27e-06 | 0.000321 | 100 % | 100 % | 0 |
| TRACI v2.1 | photochemical oxidant formation | maximum incremental reactivity (MIR) | kg O3-Eq | 100 | 2.91e-07 | -4.93e-08 | 5.39e-06 | 0.000116 | 100 % | 100 % | 0 |
| TRACI v2.1 no LT | acidification no LT | acidification potential (AP) no LT | kg SO2-Eq | 100 | 2.74e-07 | -2.59e-08 | 4.96e-06 | 0.000211 | 100 % | 100 % | 0 |
| TRACI v2.1 no LT | climate change no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 2.04e-07 | 0 | 5.07e-06 | 0.000293 | 100 % | 100 % | 0 |
| TRACI v2.1 no LT | ecotoxicity: freshwater no LT | ecotoxicity: freshwater no LT | CTUe | 100 | 2.14e-07 | 1.35e-09 | 1.02e-05 | 0.000155 | 100 % | 100 % | 0 |
| TRACI v2.1 no LT | eutrophication no LT | eutrophication potential no LT | kg N-Eq | 100 | 2.35e-07 | 0 | 6.03e-06 | 0.000336 | 100 % | 100 % | 0 |
| TRACI v2.1 no LT | human toxicity: carcinogenic no LT | human toxicity: carcinogenic no LT | CTUh | 100 | 9.58e-07 | 0 | 2.17e-05 | 0.000861 | 100 % | 100 % | 0 |
| TRACI v2.1 no LT | human toxicity: non-carcinogenic no LT | human toxicity: non-carcinogenic no LT | CTUh | 100 | 2.84e-07 | 6.75e-10 | 1.39e-05 | 0.000353 | 100 % | 100 % | 0 |
| TRACI v2.1 no LT | ozone depletion no LT | ozone depletion potential (ODP) no LT | kg CFC-11-Eq | 100 | 2.14e-07 | 1.03e-14 | 8.53e-06 | 0.000209 | 100 % | 100 % | 0 |
| TRACI v2.1 no LT | particulate matter formation no LT | particulate matter formation potential (PMFP) no LT | kg PM2.5-Eq | 100 | 3.54e-07 | -2.23e-10 | 8.22e-06 | 0.000314 | 100 % | 100 % | 0 |
| TRACI v2.1 no LT | photochemical oxidant formation no LT | maximum incremental reactivity (MIR) no LT | kg O3-Eq | 100 | 2.91e-07 | -4.93e-08 | 5.39e-06 | 0.000116 | 100 % | 100 % | 0 |

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
