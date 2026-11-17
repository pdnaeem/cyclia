# Cumulative Energy Demand (CED) benchmark: Cyclia against ecoinvent's cumulative LCIA results

Database: ecoinvent (3.13, cutoff)

**Cumulative Energy Demand (CED)**: Validated. 100.00 % of 1,200 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

## What was compared

- Reference: ecoinvent's own cumulative LCIA results for ecoinvent (3.13, cutoff), the file ecoinvent provides to licence holders with the database. Cyclia imported the same database (ecoSpold2) and the method, calculated every sampled dataset with its full supply chain and compared the scores, result by result.
- Results compared: 1,200 (datasets x impact categories).
- Datasets: 100 compared of 27,401 in the results file, matched by 'Activity UUID_Product UUID' (or by name, geography and product).
- The cumulative inventory was compared with ecoinvent's cumulative LCI as well, which separates deviations caused by the inventory from those caused by the factors.
- Software: Cyclia 1.9.1; run on 2026-11-16.

## Deviation per impact category

Deviation = |Cyclia - ecoinvent| / |ecoinvent| x 100, per dataset. Signed median: negative when Cyclia is lower for most datasets.

| Method | Category | Indicator | Unit | Results | Median % | Signed median % | 95th percentile % | Max % | Within 0.1 % | Within 1 % | Within round-off |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Cumulative Energy Demand (CED) | energy resources: non-renewable | energy content (HHV) | MJ-Eq | 100 | 2.1e-07 | 1.84e-08 | 6.27e-06 | 0.000243 | 100 % | 100 % | 0 |
| Cumulative Energy Demand (CED) | energy resources: non-renewable, biomass | energy content (HHV) | MJ-Eq | 100 | 1.05e-06 | 7.62e-09 | 2.14e-05 | 3.17e-05 | 100 % | 100 % | 0 |
| Cumulative Energy Demand (CED) | energy resources: non-renewable, fossil | energy content (HHV) | MJ-Eq | 100 | 2.26e-07 | 2.2e-08 | 7.03e-06 | 0.000236 | 100 % | 100 % | 0 |
| Cumulative Energy Demand (CED) | energy resources: non-renewable, nuclear | energy content (HHV) | MJ-Eq | 100 | 3.46e-07 | 1.11e-09 | 2.98e-05 | 0.000716 | 100 % | 100 % | 0 |
| Cumulative Energy Demand (CED) | energy resources: renewable | energy content (HHV) | MJ-Eq | 100 | 5.21e-07 | -1.35e-08 | 1.21e-05 | 0.00159 | 100 % | 100 % | 0 |
| Cumulative Energy Demand (CED) | energy resources: renewable, biomass | energy content (HHV) | MJ-Eq | 100 | 1.33e-06 | -1.89e-07 | 5.08e-05 | 0.00401 | 100 % | 100 % | 0 |
| Cumulative Energy Demand (CED) | energy resources: renewable, geothermal | energy content (HHV) | MJ-Eq | 100 | 1.22e-06 | -9.86e-08 | 3.33e-05 | 0.000732 | 100 % | 100 % | 0 |
| Cumulative Energy Demand (CED) | energy resources: renewable, geothermal, solar, wind | energy content (HHV) | MJ-Eq | 100 | 5.13e-07 | -3.31e-08 | 1.85e-05 | 0.000905 | 100 % | 100 % | 0 |
| Cumulative Energy Demand (CED) | energy resources: renewable, solar | energy content (HHV) | MJ-Eq | 100 | 5.65e-07 | -9.33e-08 | 3.41e-05 | 0.000407 | 100 % | 100 % | 0 |
| Cumulative Energy Demand (CED) | energy resources: renewable, water | energy content (HHV) | MJ-Eq | 100 | 2.49e-07 | 7.6e-10 | 1.94e-05 | 0.00112 | 100 % | 100 % | 0 |
| Cumulative Energy Demand (CED) | energy resources: renewable, wind | energy content (HHV) | MJ-Eq | 100 | 4.1e-07 | -5.12e-09 | 2.31e-05 | 0.00132 | 100 % | 100 % | 0 |
| Cumulative Energy Demand (CED) | total | energy content (HHV) | MJ-Eq | 100 | 1.54e-07 | 8.65e-15 | 4.31e-06 | 0.000263 | 100 % | 100 % | 0 |

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
