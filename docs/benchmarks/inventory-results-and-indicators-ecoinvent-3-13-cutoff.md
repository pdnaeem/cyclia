# Inventory results and indicators benchmark: Cyclia against ecoinvent's cumulative LCIA results

Database: ecoinvent (3.13, cutoff)

**Inventory results and indicators**: Validated. 100.00 % of 3,500 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

## What was compared

- Reference: ecoinvent's own cumulative LCIA results for ecoinvent (3.13, cutoff), the file ecoinvent provides to licence holders with the database. Cyclia imported the same database (ecoSpold2) and the method, calculated every sampled dataset with its full supply chain and compared the scores, result by result.
- Results compared: 3,500 (datasets x impact categories).
- Datasets: 100 compared of 27,401 in the results file, matched by 'Activity UUID_Product UUID' (or by name, geography and product).
- The cumulative inventory was compared with ecoinvent's cumulative LCI as well, which separates deviations caused by the inventory from those caused by the factors.
- Software: Cyclia 1.9.2; run on 2026-11-17.

## Deviation per impact category

Deviation = |Cyclia - ecoinvent| / |ecoinvent| x 100, per dataset. Signed median: negative when Cyclia is lower for most datasets.

| Method | Category | Indicator | Unit | Results | Median % | Signed median % | 95th percentile % | Max % | Within 0.1 % | Within 1 % | Within round-off |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Inventory results and indicators | emissions to air | ammonia | kg | 100 | 2.91e-06 | 5.16e-08 | 0.000135 | 0.00335 | 100 % | 100 % | 0 |
| Inventory results and indicators | emissions to air | carbon dioxide, fossil and land use | kg | 100 | 2.28e-07 | 0 | 6.34e-06 | 0.000322 | 100 % | 100 % | 0 |
| Inventory results and indicators | emissions to air | carbon, non-fossil, fixed | kg | 100 | 1.07e-06 | -8.3e-15 | 0.000335 | 0.00789 | 100 % | 100 % | 0 |
| Inventory results and indicators | emissions to air | HAPs | kg | 100 | 5.57e-07 | 0 | 2.32e-05 | 0.000217 | 100 % | 100 % | 0 |
| Inventory results and indicators | emissions to air | lead | kg | 100 | 7.38e-07 | 0 | 2.49e-05 | 0.000423 | 100 % | 100 % | 0 |
| Inventory results and indicators | emissions to air | N2O | kg | 100 | 1.17e-07 | -1.56e-08 | 3.79e-06 | 6.54e-05 | 100 % | 100 % | 0 |
| Inventory results and indicators | emissions to air | NMVOCs | kg | 100 | 6.98e-07 | 1e-07 | 1.8e-05 | 0.000254 | 100 % | 100 % | 0 |
| Inventory results and indicators | emissions to air | NOx | kg | 100 | 2.67e-07 | -8.49e-08 | 5.63e-06 | 0.000142 | 100 % | 100 % | 0 |
| Inventory results and indicators | emissions to air | particulate matter >10 um | kg | 100 | 9.98e-07 | 1.94e-07 | 2.85e-05 | 0.000362 | 100 % | 100 % | 0 |
| Inventory results and indicators | emissions to air | particulate matter, < 2.5 um | kg | 100 | 4.19e-07 | -4.7e-08 | 1.06e-05 | 0.000301 | 100 % | 100 % | 0 |
| Inventory results and indicators | emissions to air | particulate matter, >2.5 um and <10 | kg | 100 | 1.07e-06 | 1.53e-07 | 2.64e-05 | 0.000414 | 100 % | 100 % | 0 |
| Inventory results and indicators | emissions to air | photochemical oxidant formation | kg | 100 | 2.24e-07 | 0 | 4.69e-06 | 0.000106 | 100 % | 100 % | 0 |
| Inventory results and indicators | emissions to air | SOx | kg | 100 | 2.86e-07 | 0 | 7.47e-06 | 0.000509 | 100 % | 100 % | 0 |
| Inventory results and indicators | emissions to air | total carbon monoxide | kg | 100 | 4.1e-07 | 0 | 1.08e-05 | 3.81e-05 | 100 % | 100 % | 0 |
| Inventory results and indicators | emissions to air | total methane | kg | 100 | 2.84e-07 | 0 | 4.13e-06 | 0.000142 | 100 % | 100 % | 0 |
| Inventory results and indicators | emissions to air | total particulate matter | kg | 100 | 6.22e-07 | 1.62e-07 | 1.64e-05 | 0.000354 | 100 % | 100 % | 0 |
| Inventory results and indicators | emissions to air | total radioactive emissions | kg | 100 | 3.34e-07 | 8.29e-10 | 3.06e-05 | 0.000719 | 100 % | 100 % | 0 |
| Inventory results and indicators | emissions to water | total radioactive emissions | kg | 100 | 3.81e-07 | 0 | 2.46e-05 | 0.000647 | 100 % | 100 % | 0 |
| Inventory results and indicators | resources | freshwater extraction, groundwater | m3 | 100 | 5.22e-07 | 6.75e-09 | 1.32e-05 | 0.001 | 100 % | 100 % | 0 |
| Inventory results and indicators | resources | freshwater extraction, surface water | m3 | 100 | 2.5e-07 | 0 | 1.44e-05 | 0.00054 | 100 % | 100 % | 0 |
| Inventory results and indicators | resources | land occupation | m2a | 100 | 4.77e-06 | -6.99e-08 | 6.75e-05 | 0.000369 | 100 % | 100 % | 0 |
| Inventory results and indicators | resources | land occupation by flooding | m2a | 100 | 3.68e-07 | -1.14e-08 | 2.61e-05 | 0.00112 | 100 % | 100 % | 0 |
| Inventory results and indicators | resources | seabed occupation | m2a | 100 | 5.93e-07 | 4.93e-08 | 9.66e-06 | 0.00018 | 100 % | 100 % | 0 |
| Inventory results and indicators | resources | total freshwater extraction | m3 | 100 | 2.99e-07 | 0 | 7.5e-06 | 0.000738 | 100 % | 100 % | 0 |
| Inventory results and indicators | resources | total surface occupation | m2a | 100 | 3.01e-06 | -5.23e-08 | 6.41e-05 | 0.000371 | 100 % | 100 % | 0 |
| Inventory results and indicators | resources | total water extraction | m3 | 100 | 2.38e-07 | 0 | 6.54e-06 | 0.000659 | 100 % | 100 % | 0 |
| Inventory results and indicators | resources | water extraction, saltwater | m3 | 100 | 2.52e-07 | 0 | 8.98e-06 | 0.000815 | 100 % | 100 % | 0 |
| Inventory results and indicators | resources | water extraction, undefined | m3 | 100 | 8.07e-07 | 1.25e-08 | 3.3e-05 | 0.00296 | 100 % | 100 % | 0 |
| Inventory results and indicators | waste disposal | total area for dump sites | m2 | 100 | 4.7e-07 | 0 | 1.37e-05 | 5.18e-05 | 100 % | 100 % | 0 |
| Inventory results and indicators | waste disposal | total mass for dump sites | kg | 100 | 4.85e-07 | 0 | 1.3e-05 | 5.26e-05 | 100 % | 100 % | 0 |
| Inventory results and indicators | waste disposal | total mass for underground deposits | kg | 100 | 2.24e-07 | 1.63e-08 | 1.04e-05 | 0.000312 | 100 % | 100 % | 0 |
| Inventory results and indicators | waste disposal | total mass of radioactive waste | kg | 100 | 7.33e-07 | 4.58e-08 | 2.27e-05 | 0.000796 | 100 % | 100 % | 0 |
| Inventory results and indicators | waste disposal | total mass of waste | kg | 100 | 4.85e-07 | 0 | 1.3e-05 | 5.25e-05 | 100 % | 100 % | 0 |
| Inventory results and indicators | waste disposal | total volume of radioactive waste | m3 | 100 | 7.13e-07 | 3.73e-08 | 3.18e-05 | 0.000786 | 100 % | 100 % | 0 |
| Inventory results and indicators | waste disposal | total volume of underground deposits | m3 | 100 | 2.41e-07 | 1.91e-09 | 8.92e-06 | 0.000304 | 100 % | 100 % | 0 |

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
