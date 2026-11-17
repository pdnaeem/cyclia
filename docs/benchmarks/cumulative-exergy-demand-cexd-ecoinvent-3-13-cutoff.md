# Cumulative Exergy Demand (CExD) benchmark: Cyclia against ecoinvent's cumulative LCIA results

Database: ecoinvent (3.13, cutoff)

**Cumulative Exergy Demand (CExD)**: Validated. 100.00 % of 1,400 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

## What was compared

- Reference: ecoinvent's own cumulative LCIA results for ecoinvent (3.13, cutoff), the file ecoinvent provides to licence holders with the database. Cyclia imported the same database (ecoSpold2) and the method, calculated every sampled dataset with its full supply chain and compared the scores, result by result.
- Results compared: 1,400 (datasets x impact categories).
- Datasets: 100 compared of 27,401 in the results file, matched by 'Activity UUID_Product UUID' (or by name, geography and product).
- The cumulative inventory was compared with ecoinvent's cumulative LCI as well, which separates deviations caused by the inventory from those caused by the factors.
- Software: Cyclia 1.9.2; run on 2026-11-17.

## Deviation per impact category

Deviation = |Cyclia - ecoinvent| / |ecoinvent| x 100, per dataset. Signed median: negative when Cyclia is lower for most datasets.

| Method | Category | Indicator | Unit | Results | Median % | Signed median % | 95th percentile % | Max % | Within 0.1 % | Within 1 % | Within round-off |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Cumulative Exergy Demand (CExD) | energy resources: non-renewable | exergy content | MJ-Eq | 100 | 2.09e-07 | 1.82e-08 | 6.35e-06 | 0.000242 | 100 % | 100 % | 0 |
| Cumulative Exergy Demand (CExD) | energy resources: non-renewable, biomass | exergy content | MJ-Eq | 100 | 1.05e-06 | 7.62e-09 | 2.14e-05 | 3.17e-05 | 100 % | 100 % | 0 |
| Cumulative Exergy Demand (CExD) | energy resources: non-renewable, fossil | exergy content | MJ-Eq | 100 | 2.32e-07 | 2.31e-08 | 6.93e-06 | 0.000235 | 100 % | 100 % | 0 |
| Cumulative Exergy Demand (CExD) | energy resources: non-renewable, nuclear | exergy content | MJ-Eq | 100 | 3.46e-07 | 1.11e-09 | 2.98e-05 | 0.000716 | 100 % | 100 % | 0 |
| Cumulative Exergy Demand (CExD) | energy resources: renewable | exergy content | MJ-Eq | 100 | 5.33e-07 | -6.82e-09 | 1.28e-05 | 0.00165 | 100 % | 100 % | 0 |
| Cumulative Exergy Demand (CExD) | energy resources: renewable, biomass | exergy content | MJ-Eq | 100 | 1.33e-06 | -1.89e-07 | 5.08e-05 | 0.00401 | 100 % | 100 % | 0 |
| Cumulative Exergy Demand (CExD) | energy resources: renewable, solar | exergy content | MJ-Eq | 100 | 5.65e-07 | -9.33e-08 | 3.41e-05 | 0.000407 | 100 % | 100 % | 0 |
| Cumulative Exergy Demand (CExD) | energy resources: renewable, water | exergy content | MJ-Eq | 100 | 2.49e-07 | 7.6e-10 | 1.94e-05 | 0.00112 | 100 % | 100 % | 0 |
| Cumulative Exergy Demand (CExD) | energy resources: renewable, wind | exergy content | MJ-Eq | 100 | 4.1e-07 | -5.12e-09 | 2.31e-05 | 0.00132 | 100 % | 100 % | 0 |
| Cumulative Exergy Demand (CExD) | material resources | exergy content | MJ-Eq | 100 | 2.42e-07 | 0 | 6.4e-06 | 0.000473 | 100 % | 100 % | 0 |
| Cumulative Exergy Demand (CExD) | material resources: metals | exergy content | MJ-Eq | 100 | 1.33e-06 | 2.07e-07 | 5.98e-05 | 0.0011 | 100 % | 100 % | 0 |
| Cumulative Exergy Demand (CExD) | material resources: minerals | exergy content | MJ-Eq | 100 | 7.61e-07 | -3.44e-09 | 2.04e-05 | 0.00033 | 100 % | 100 % | 0 |
| Cumulative Exergy Demand (CExD) | material resources: water | exergy content | MJ-Eq | 100 | 2.44e-07 | 0 | 9.37e-06 | 0.000497 | 100 % | 100 % | 0 |
| Cumulative Exergy Demand (CExD) | total | exergy content | MJ-Eq | 100 | 1.4e-07 | 1.56e-14 | 2.76e-06 | 0.000279 | 100 % | 100 % | 0 |

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
