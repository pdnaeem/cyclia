# USEtox v2.13, midpoint benchmark: Cyclia against ecoinvent's cumulative LCIA results

Database: ecoinvent (3.13, cutoff)

**USEtox v2.13, midpoint**: Validated. 100.00 % of 300 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**USEtox v2.13, midpoint no LT**: Validated. 100.00 % of 300 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

## What was compared

- Reference: ecoinvent's own cumulative LCIA results for ecoinvent (3.13, cutoff), the file ecoinvent provides to licence holders with the database. Cyclia imported the same database (ecoSpold2) and the method, calculated every sampled dataset with its full supply chain and compared the scores, result by result.
- Results compared: 600 (datasets x impact categories).
- Datasets: 100 compared of 27,401 in the results file, matched by 'Activity UUID_Product UUID' (or by name, geography and product).
- The cumulative inventory was compared with ecoinvent's cumulative LCI as well, which separates deviations caused by the inventory from those caused by the factors.
- Software: Cyclia 1.9.1; run on 2026-11-16.

## Deviation per impact category

Deviation = |Cyclia - ecoinvent| / |ecoinvent| x 100, per dataset. Signed median: negative when Cyclia is lower for most datasets.

| Method | Category | Indicator | Unit | Results | Median % | Signed median % | 95th percentile % | Max % | Within 0.1 % | Within 1 % | Within round-off |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| USEtox v2.13, midpoint | ecotoxicity: freshwater | comparative toxic unit for ecosystems (CTUe) | CTUe | 100 | 5.08e-07 | 0 | 2.29e-05 | 0.00149 | 100 % | 100 % | 0 |
| USEtox v2.13, midpoint | human toxicity: carcinogenic | comparative toxic unit for human (CTUh) | CTUh | 100 | 7.05e-07 | 1.56e-08 | 2.1e-05 | 0.000281 | 100 % | 100 % | 0 |
| USEtox v2.13, midpoint | human toxicity: non-carcinogenic | comparative toxic unit for human (CTUh) | CTUh | 100 | 5.08e-07 | 0 | 1.5e-05 | 0.000602 | 100 % | 100 % | 0 |
| USEtox v2.13, midpoint no LT | ecotoxicity: freshwater no LT | comparative toxic unit for ecosystems (CTUe) no LT | CTUe | 100 | 3.66e-07 | 4.05e-08 | 9.54e-06 | 0.000537 | 100 % | 100 % | 0 |
| USEtox v2.13, midpoint no LT | human toxicity: carcinogenic no LT | comparative toxic unit for human (CTUh) no LT | CTUh | 100 | 7.38e-07 | 0 | 1.81e-05 | 0.000857 | 100 % | 100 % | 0 |
| USEtox v2.13, midpoint no LT | human toxicity: non-carcinogenic no LT | comparative toxic unit for human (CTUh) no LT | CTUh | 100 | 3.23e-07 | 7.4e-09 | 1.33e-05 | 0.000472 | 100 % | 100 % | 0 |

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
