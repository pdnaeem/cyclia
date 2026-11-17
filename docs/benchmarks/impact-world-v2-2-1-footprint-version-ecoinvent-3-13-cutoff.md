# IMPACT World+ v2.2.1, footprint version benchmark: Cyclia against ecoinvent's cumulative LCIA results

Database: ecoinvent (3.13, cutoff)

**IMPACT World+ v2.2.1, footprint version**: Validated. 100.00 % of 500 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

## What was compared

- Reference: ecoinvent's own cumulative LCIA results for ecoinvent (3.13, cutoff), the file ecoinvent provides to licence holders with the database. Cyclia imported the same database (ecoSpold2) and the method, calculated every sampled dataset with its full supply chain and compared the scores, result by result.
- Results compared: 500 (datasets x impact categories).
- Datasets: 100 compared of 27,401 in the results file, matched by 'Activity UUID_Product UUID' (or by name, geography and product).
- The cumulative inventory was compared with ecoinvent's cumulative LCI as well, which separates deviations caused by the inventory from those caused by the factors.
- Software: Cyclia 1.9.1; run on 2026-11-16.

## Deviation per impact category

Deviation = |Cyclia - ecoinvent| / |ecoinvent| x 100, per dataset. Signed median: negative when Cyclia is lower for most datasets.

| Method | Category | Indicator | Unit | Results | Median % | Signed median % | 95th percentile % | Max % | Within 0.1 % | Within 1 % | Within round-off |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| IMPACT World+ v2.2.1, footprint version | climate change | carbon footprint | kg CO2-Eq | 100 | 2.06e-07 | 0 | 5.07e-06 | 0.000289 | 100 % | 100 % | 0 |
| IMPACT World+ v2.2.1, footprint version | ecosystem quality | remaining ecosystem quality damage | PDF.m2.yr | 100 | 2.58e-06 | 0 | 7.38e-05 | 0.000148 | 100 % | 100 % | 0 |
| IMPACT World+ v2.2.1, footprint version | energy resources: non-renewable | fossil and nuclear energy use | MJ deprived | 100 | 2.1e-07 | 1.84e-08 | 6.27e-06 | 0.000243 | 100 % | 100 % | 0 |
| IMPACT World+ v2.2.1, footprint version | human health | remaining human health damage | DALYs | 100 | 3.02e-07 | 0 | 6.92e-06 | 0.000265 | 100 % | 100 % | 0 |
| IMPACT World+ v2.2.1, footprint version | water use | water scarcity footprint | m3 world Eq deprived | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % | 0 |

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
