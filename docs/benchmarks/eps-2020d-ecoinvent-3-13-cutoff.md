# EPS 2020d benchmark: Cyclia against ecoinvent's cumulative LCIA results

Database: ecoinvent (3.13, cutoff)

**EPS 2020d**: Validated. 100.00 % of 700 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**EPS 2020d no LT**: Validated. 100.00 % of 700 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

## What was compared

- Reference: ecoinvent's own cumulative LCIA results for ecoinvent (3.13, cutoff), the file ecoinvent provides to licence holders with the database. Cyclia imported the same database (ecoSpold2) and the method, calculated every sampled dataset with its full supply chain and compared the scores, result by result.
- Results compared: 1,400 (datasets x impact categories).
- Datasets: 100 compared of 27,401 in the results file, matched by 'Activity UUID_Product UUID' (or by name, geography and product).
- The cumulative inventory was compared with ecoinvent's cumulative LCI as well, which separates deviations caused by the inventory from those caused by the factors.
- Software: Cyclia 1.9.0; run on 2026-11-16.

## Deviation per impact category

Deviation = |Cyclia - ecoinvent| / |ecoinvent| x 100, per dataset. Signed median: negative when Cyclia is lower for most datasets.

| Method | Category | Indicator | Unit | Results | Median % | Signed median % | 95th percentile % | Max % | Within 0.1 % | Within 1 % | Within round-off |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| EPS 2020d | emissions to air | monetary impact value | EUR 2018 | 100 | 2.51e-07 | 6.08e-15 | 1.26e-05 | 0.000335 | 100 % | 100 % |  |
| EPS 2020d | emissions to soil | monetary impact value | EUR 2018 | 100 | 4.98e-07 | 0 | 1.6e-05 | 3.04e-05 | 100 % | 100 % |  |
| EPS 2020d | emissions to water | monetary impact value | EUR 2018 | 100 | 9.1e-07 | 8.24e-15 | 2.86e-05 | 0.00162 | 100 % | 100 % |  |
| EPS 2020d | energy resources: non-renewable, fossil | monetary impact value | EUR 2018 | 100 | 2.39e-07 | 2.62e-08 | 6.88e-06 | 0.000227 | 100 % | 100 % |  |
| EPS 2020d | land use | monetary impact value | EUR 2018 | 100 | 2.25e-05 | -2.82e-08 | 0.000497 | 0.00151 | 100 % | 100 % |  |
| EPS 2020d | material resources: metals | monetary impact value | EUR 2018 | 100 | 9.87e-07 | 1.78e-08 | 5.3e-05 | 0.00142 | 100 % | 100 % |  |
| EPS 2020d | total | monetary impact value | EUR 2018 | 100 | 1.62e-06 | 0 | 4.61e-05 | 0.000498 | 100 % | 100 % |  |
| EPS 2020d no LT | emissions to air no LT | monetary impact value no LT | EUR 2018 | 100 | 2.55e-07 | 8.13e-10 | 1.26e-05 | 0.000332 | 100 % | 100 % |  |
| EPS 2020d no LT | emissions to soil no LT | monetary impact value no LT | EUR 2018 | 100 | 4.98e-07 | 0 | 1.6e-05 | 3.04e-05 | 100 % | 100 % |  |
| EPS 2020d no LT | emissions to water no LT | monetary impact value no LT | EUR 2018 | 100 | 5.83e-07 | 1.01e-09 | 1.63e-05 | 0.0191 | 100 % | 100 % |  |
| EPS 2020d no LT | energy resources: non-renewable, fossil no LT | monetary impact value no LT | EUR 2018 | 100 | 2.39e-07 | 2.62e-08 | 6.88e-06 | 0.000227 | 100 % | 100 % |  |
| EPS 2020d no LT | land use no LT | monetary impact value no LT | EUR 2018 | 100 | 2.25e-05 | -2.82e-08 | 0.000497 | 0.00151 | 100 % | 100 % |  |
| EPS 2020d no LT | material resources: metals no LT | monetary impact value no LT | EUR 2018 | 100 | 9.87e-07 | 1.78e-08 | 5.3e-05 | 0.00142 | 100 % | 100 % |  |
| EPS 2020d no LT | total no LT | monetary impact value no LT | EUR 2018 | 100 | 1.7e-06 | 0 | 4.71e-05 | 0.000479 | 100 % | 100 % |  |

## How to read this

- 'Validated' requires that at least 95 % of all results agree within 0.1 % and that every category has at least 95 % of its results within 1 %. A category below that is named above and its results should not be published before the cause is found.
- The benchmark checks Cyclia's matrix calculation, its import of ecoinvent and the matching of the method's factors to ecoinvent's elementary flows. It does not check the method itself: Cyclia uses the factors as published.
- Only the ecoinvent version and system model named were compared. Another version or system model needs its own run.
- 'Within round-off' counts results whose net value is the small remainder of positive and negative contributions that cancel, and where the gap to ecoinvent is below 1e-9 of the sum of the absolute contributions (Cyclia 1.9.1 and later; empty for earlier runs). These count as agreeing.
- No ecoinvent data is reproduced here: the report holds deviation statistics only.

## Reproduce

1. Import the ecoinvent database (ecoSpold2) and the method in Cyclia.
2. Validation > ecoinvent: choose ecoinvent's cumulative LCIA results file for the same version and system model (optionally the cumulative LCI file too) and run the benchmark.
3. Validation > Benchmark Centre > Publish benchmark reports writes this file.
