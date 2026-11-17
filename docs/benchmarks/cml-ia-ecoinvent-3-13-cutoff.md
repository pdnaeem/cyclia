# CML-IA benchmark: Cyclia against ecoinvent's cumulative LCIA results

Database: ecoinvent (3.13, cutoff)

**CML v4.8 2016**: Validated. 100.00 % of 1,100 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**CML v4.8 2016 no LT**: Validated. 100.00 % of 1,100 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

## What was compared

- Reference: ecoinvent's own cumulative LCIA results for ecoinvent (3.13, cutoff), the file ecoinvent provides to licence holders with the database. Cyclia imported the same database (ecoSpold2) and the method, calculated every sampled dataset with its full supply chain and compared the scores, result by result.
- Results compared: 2,200 (datasets x impact categories).
- Datasets: 100 compared of 27,401 in the results file, matched by 'Activity UUID_Product UUID' (or by name, geography and product).
- The cumulative inventory was compared with ecoinvent's cumulative LCI as well, which separates deviations caused by the inventory from those caused by the factors.
- Software: Cyclia 1.9.2; run on 2026-11-17.

## Deviation per impact category

Deviation = |Cyclia - ecoinvent| / |ecoinvent| x 100, per dataset. Signed median: negative when Cyclia is lower for most datasets.

| Method | Category | Indicator | Unit | Results | Median % | Signed median % | 95th percentile % | Max % | Within 0.1 % | Within 1 % | Within round-off |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CML v4.8 2016 | acidification | acidification (incl. fate, average Europe total, A&B) | kg SO2-Eq | 100 | 2.59e-07 | -6.84e-09 | 5.09e-06 | 0.000242 | 100 % | 100 % | 0 |
| CML v4.8 2016 | climate change | global warming potential (GWP100) | kg CO2-Eq | 100 | 2.05e-07 | 0 | 5.06e-06 | 0.000291 | 100 % | 100 % | 0 |
| CML v4.8 2016 | ecotoxicity: freshwater | freshwater aquatic ecotoxicity (FAETP inf) | kg 1,4-DCB-Eq | 100 | 5.87e-07 | 9.34e-09 | 2.03e-05 | 0.000625 | 100 % | 100 % | 0 |
| CML v4.8 2016 | ecotoxicity: marine | marine aquatic ecotoxicity (MAETP inf) | kg 1,4-DCB-Eq | 100 | 4.96e-07 | 0 | 1.08e-05 | 0.000967 | 100 % | 100 % | 0 |
| CML v4.8 2016 | ecotoxicity: terrestrial | terrestrial ecotoxicity (TETP inf) | kg 1,4-DCB-Eq | 100 | 1.27e-06 | 0 | 3.59e-05 | 0.00144 | 100 % | 100 % | 0 |
| CML v4.8 2016 | energy resources: non-renewable | abiotic depletion potential (ADP): fossil fuels | MJ | 100 | 2.3e-07 | 2.27e-08 | 6.97e-06 | 0.000235 | 100 % | 100 % | 0 |
| CML v4.8 2016 | eutrophication | eutrophication (fate not incl.) | kg PO4-Eq | 100 | 2.5e-07 | 0 | 6.61e-06 | 0.00042 | 100 % | 100 % | 0 |
| CML v4.8 2016 | human toxicity | human toxicity (HTP inf) | kg 1,4-DCB-Eq | 100 | 7.32e-07 | 0 | 2.04e-05 | 0.000124 | 100 % | 100 % | 0 |
| CML v4.8 2016 | material resources: metals/minerals | abiotic depletion potential (ADP): elements (ultimate reserves) | kg Sb-Eq | 100 | 1.32e-06 | 6.87e-09 | 8.66e-05 | 0.00186 | 100 % | 100 % | 0 |
| CML v4.8 2016 | ozone depletion | ozone layer depletion (ODP steady state) | kg CFC-11-Eq | 100 | 2.07e-07 | 3.49e-11 | 8.89e-06 | 0.000221 | 100 % | 100 % | 0 |
| CML v4.8 2016 | photochemical oxidant formation | photochemical oxidation (high NOx) | kg ethylene-Eq | 100 | 2.01e-07 | -7.79e-15 | 5.26e-06 | 6.33e-05 | 100 % | 100 % | 0 |
| CML v4.8 2016 no LT | acidification no LT | acidification (incl. fate, average Europe total, A&B) no LT | kg SO2-Eq | 100 | 2.59e-07 | -6.84e-09 | 5.09e-06 | 0.000242 | 100 % | 100 % | 0 |
| CML v4.8 2016 no LT | climate change no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 2.05e-07 | 0 | 5.06e-06 | 0.000291 | 100 % | 100 % | 0 |
| CML v4.8 2016 no LT | ecotoxicity: freshwater no LT | freshwater aquatic ecotoxicity (FAETP inf) no LT | kg 1,4-DCB-Eq | 100 | 2.16e-07 | 4.84e-09 | 6.92e-06 | 0.000124 | 100 % | 100 % | 0 |
| CML v4.8 2016 no LT | ecotoxicity: marine no LT | marine aquatic ecotoxicity (MAETP inf) no LT | kg 1,4-DCB-Eq | 100 | 3.73e-07 | -7.78e-08 | 1.7e-05 | 0.000754 | 100 % | 100 % | 0 |
| CML v4.8 2016 no LT | ecotoxicity: terrestrial no LT | terrestrial ecotoxicity (TETP inf) no LT | kg 1,4-DCB-Eq | 100 | 1.33e-06 | 0 | 3.93e-05 | 0.00144 | 100 % | 100 % | 0 |
| CML v4.8 2016 no LT | energy resources: non-renewable no LT | abiotic depletion potential (ADP): fossil fuels no LT | MJ | 100 | 2.3e-07 | 2.27e-08 | 6.97e-06 | 0.000235 | 100 % | 100 % | 0 |
| CML v4.8 2016 no LT | eutrophication no LT | eutrophication (fate not incl.) no LT | kg PO4-Eq | 100 | 2.62e-07 | 0 | 9.99e-06 | 0.000283 | 100 % | 100 % | 0 |
| CML v4.8 2016 no LT | human toxicity no LT | human toxicity (HTP inf) no LT | kg 1,4-DCB-Eq | 100 | 7.35e-07 | -4.06e-14 | 2.35e-05 | 9.86e-05 | 100 % | 100 % | 0 |
| CML v4.8 2016 no LT | material resources: metals/minerals no LT | abiotic depletion potential (ADP): elements (ultimate reserves) no LT | kg Sb-Eq | 100 | 1.32e-06 | 6.87e-09 | 8.66e-05 | 0.00186 | 100 % | 100 % | 0 |
| CML v4.8 2016 no LT | ozone depletion no LT | ozone layer depletion (ODP steady state) no LT | kg CFC-11-Eq | 100 | 2.07e-07 | 3.49e-11 | 8.89e-06 | 0.000221 | 100 % | 100 % | 0 |
| CML v4.8 2016 no LT | photochemical oxidant formation no LT | photochemical oxidation (high NOx) no LT | kg ethylene-Eq | 100 | 2.01e-07 | 0 | 5.26e-06 | 6.33e-05 | 100 % | 100 % | 0 |

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
