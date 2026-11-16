# Ecological Scarcity 2021 benchmark: Cyclia against ecoinvent's cumulative LCIA results

Database: ecoinvent (3.13, cutoff)

**Ecological Scarcity 2021**: Validated except some categories. 95.50 % of 2,000 results within 0.1 % of ecoinvent's value, 95.50 % within 1 %. Categories with less than 95 % of results within 1 %: natural resources.

**Ecological Scarcity 2021 no LT**: Validated except some categories. 95.50 % of 2,000 results within 0.1 % of ecoinvent's value, 95.50 % within 1 %. Categories with less than 95 % of results within 1 %: natural resources no LT.

## What was compared

- Reference: ecoinvent's own cumulative LCIA results for ecoinvent (3.13, cutoff), the file ecoinvent provides to licence holders with the database. Cyclia imported the same database (ecoSpold2) and the method, calculated every sampled dataset with its full supply chain and compared the scores, result by result.
- Results compared: 4,000 (datasets x impact categories).
- Datasets: 100 compared of 27,401 in the results file, matched by 'Activity UUID_Product UUID' (or by name, geography and product).
- The cumulative inventory was compared with ecoinvent's cumulative LCI as well, which separates deviations caused by the inventory from those caused by the factors.
- Software: Cyclia 1.9.0; run on 2026-11-16.

## Deviation per impact category

Deviation = |Cyclia - ecoinvent| / |ecoinvent| x 100, per dataset. Signed median: negative when Cyclia is lower for most datasets.

| Method | Category | Indicator | Unit | Results | Median % | Signed median % | 95th percentile % | Max % | Within 0.1 % | Within 1 % | Within round-off |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Ecological Scarcity 2021 | climate change | global warming potential (GWP100) | UBP | 100 | 2.12e-07 | 0 | 5.07e-06 | 0.000287 | 100 % | 100 % |  |
| Ecological Scarcity 2021 | emissions to air | air pollutants and PM | UBP | 100 | 4.04e-07 | 0 | 7.44e-06 | 0.000236 | 100 % | 100 % |  |
| Ecological Scarcity 2021 | emissions to air | carcinogenic substances into air | UBP | 100 | 1.2e-06 | 2.12e-09 | 2.98e-05 | 0.000353 | 100 % | 100 % |  |
| Ecological Scarcity 2021 | emissions to air | heavy metals into air | UBP | 100 | 5.14e-07 | 2.97e-09 | 1.88e-05 | 0.00041 | 100 % | 100 % |  |
| Ecological Scarcity 2021 | emissions to air | radioactive substances into air | UBP | 100 | 4.71e-07 | 1.04e-09 | 3.15e-05 | 0.000755 | 100 % | 100 % |  |
| Ecological Scarcity 2021 | emissions to soil | heavy metals into soil | UBP | 100 | 3.57e-07 | -7.96e-15 | 1.48e-05 | 0.000329 | 100 % | 100 % |  |
| Ecological Scarcity 2021 | emissions to soil | pesticides into soil | UBP | 100 | 4.75e-07 | 0 | 1.44e-05 | 3.41e-05 | 100 % | 100 % |  |
| Ecological Scarcity 2021 | emissions to water | heavy metals into water | UBP | 100 | 1.08e-06 | 1.51e-14 | 4.34e-05 | 0.00475 | 100 % | 100 % |  |
| Ecological Scarcity 2021 | emissions to water | POP into water | UBP | 100 | 1.08e-06 | 1.65e-08 | 6.24e-05 | 0.000675 | 100 % | 100 % |  |
| Ecological Scarcity 2021 | emissions to water | radioactive substances into water | UBP | 100 | 3.69e-07 | 3.68e-10 | 2.95e-05 | 0.000735 | 100 % | 100 % |  |
| Ecological Scarcity 2021 | emissions to water | water pollutants | UBP | 100 | 2.72e-07 | 3.25e-08 | 8.73e-06 | 0.000193 | 100 % | 100 % |  |
| Ecological Scarcity 2021 | energy resources | energy resources | UBP | 100 | 1.78e-07 | 6.52e-09 | 4.21e-06 | 0.00025 | 100 % | 100 % |  |
| Ecological Scarcity 2021 | land use | land use | UBP | 100 | 4.96e-06 | -6.56e-08 | 7.43e-05 | 0.000353 | 100 % | 100 % |  |
| Ecological Scarcity 2021 | mineral resources | mineral resources | UBP | 100 | 9.23e-07 | 4.59e-08 | 5.59e-05 | 0.00534 | 100 % | 100 % |  |
| Ecological Scarcity 2021 | natural resources | biotic resources | UBP | 100 | 4.86e+03 | -4.52e+03 | 3.08e+04 | 2.11e+05 | 10 % | 10 % |  |
| Ecological Scarcity 2021 | ozone depletion | ozone depletion | UBP | 100 | 2.2e-07 | 0 | 1.02e-05 | 0.000239 | 100 % | 100 % |  |
| Ecological Scarcity 2021 | total | UBP | UBP | 100 | 2.23e-07 | 0 | 4.73e-06 | 0.000212 | 100 % | 100 % |  |
| Ecological Scarcity 2021 | waste disposal | radioactive waste to deposit | UBP | 100 | 1.16e-06 | 6.08e-09 | 3.82e-05 | 0.000859 | 100 % | 100 % |  |
| Ecological Scarcity 2021 | waste disposal | waste, non radioactive | UBP | 100 | 9.64e-07 | -8.28e-11 | 3.26e-05 | 5.93e-05 | 100 % | 100 % |  |
| Ecological Scarcity 2021 | water use | water resources, evaporated | UBP | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % |  |
| Ecological Scarcity 2021 no LT | climate change no LT | global warming potential (GWP100) no LT | UBP | 100 | 2.12e-07 | 0 | 5.07e-06 | 0.000287 | 100 % | 100 % |  |
| Ecological Scarcity 2021 no LT | emissions to air no LT | air pollutants and PM no LT | UBP | 100 | 3.91e-07 | 0 | 7.23e-06 | 0.000231 | 100 % | 100 % |  |
| Ecological Scarcity 2021 no LT | emissions to air no LT | carcinogenic substances into air no LT | UBP | 100 | 1.2e-06 | 2.12e-09 | 2.98e-05 | 0.000353 | 100 % | 100 % |  |
| Ecological Scarcity 2021 no LT | emissions to air no LT | heavy metals into air no LT | UBP | 100 | 5.18e-07 | 7.36e-09 | 1.89e-05 | 0.00041 | 100 % | 100 % |  |
| Ecological Scarcity 2021 no LT | emissions to air no LT | radioactive substances into air no LT | UBP | 100 | 1.07e-06 | 3.2e-09 | 3.63e-05 | 0.000824 | 100 % | 100 % |  |
| Ecological Scarcity 2021 no LT | emissions to soil no LT | heavy metals into soil no LT | UBP | 100 | 3.57e-07 | -7.96e-15 | 1.48e-05 | 0.000329 | 100 % | 100 % |  |
| Ecological Scarcity 2021 no LT | emissions to soil no LT | pesticides into soil no LT | UBP | 100 | 4.75e-07 | 0 | 1.44e-05 | 3.41e-05 | 100 % | 100 % |  |
| Ecological Scarcity 2021 no LT | emissions to water no LT | heavy metals into water no LT | UBP | 100 | 1.08e-06 | 1.51e-14 | 4.34e-05 | 0.00475 | 100 % | 100 % |  |
| Ecological Scarcity 2021 no LT | emissions to water no LT | POP into water no LT | UBP | 100 | 1.08e-06 | 1.65e-08 | 6.24e-05 | 0.000675 | 100 % | 100 % |  |
| Ecological Scarcity 2021 no LT | emissions to water no LT | radioactive substances into water no LT | UBP | 100 | 3.69e-07 | 3.68e-10 | 2.95e-05 | 0.000735 | 100 % | 100 % |  |
| Ecological Scarcity 2021 no LT | emissions to water no LT | water pollutants no LT | UBP | 100 | 2.72e-07 | 3.25e-08 | 8.73e-06 | 0.000193 | 100 % | 100 % |  |
| Ecological Scarcity 2021 no LT | energy resources no LT | energy resources no LT | UBP | 100 | 1.78e-07 | 6.52e-09 | 4.21e-06 | 0.00025 | 100 % | 100 % |  |
| Ecological Scarcity 2021 no LT | land use no LT | land use no LT | UBP | 100 | 4.96e-06 | -6.56e-08 | 7.43e-05 | 0.000353 | 100 % | 100 % |  |
| Ecological Scarcity 2021 no LT | mineral resources no LT | mineral resources no LT | UBP | 100 | 9.23e-07 | 4.59e-08 | 5.59e-05 | 0.00534 | 100 % | 100 % |  |
| Ecological Scarcity 2021 no LT | natural resources no LT | biotic resources no LT | UBP | 100 | 4.86e+03 | -4.52e+03 | 3.08e+04 | 2.11e+05 | 10 % | 10 % |  |
| Ecological Scarcity 2021 no LT | ozone depletion no LT | ozone depletion no LT | UBP | 100 | 2.2e-07 | 0 | 1.02e-05 | 0.000239 | 100 % | 100 % |  |
| Ecological Scarcity 2021 no LT | total no LT | UBP no LT | UBP | 100 | 2.27e-07 | 0 | 4.53e-06 | 0.000204 | 100 % | 100 % |  |
| Ecological Scarcity 2021 no LT | waste disposal no LT | radioactive waste to deposit no LT | UBP | 100 | 1.16e-06 | 6.08e-09 | 3.82e-05 | 0.000859 | 100 % | 100 % |  |
| Ecological Scarcity 2021 no LT | waste disposal no LT | waste, non radioactive no LT | UBP | 100 | 5.83e-07 | 0 | 1.99e-05 | 4.67e-05 | 100 % | 100 % |  |
| Ecological Scarcity 2021 no LT | water use no LT | water resources, evaporated no LT | UBP | 100 | 2.13e-07 | 1.29e-09 | 7.57e-06 | 0.000227 | 100 % | 100 % |  |

## Notes

- Ecological Scarcity 2021, natural resources (biotic resources): 90 of 100 results deviate by more than 0.1 %. In each of them both results are at most 1e-05 of the largest result of the category in the sample, and in 83 the two results have opposite signs. A result that small next to others of the same category, with a sign that differs between the two programs, is most likely the remainder of contributions of both signs that cancel, where the relative deviation measures round-off rather than a difference in the inventory or the factors. Cyclia 1.9.1 tests this per result (gap below 1e-9 of the sum of the absolute contributions). This run was made before that test, so the category is reported as measured and is not claimed as validated.
- Ecological Scarcity 2021 no LT, natural resources no LT (biotic resources no LT): 90 of 100 results deviate by more than 0.1 %. In each of them both results are at most 1e-05 of the largest result of the category in the sample, and in 83 the two results have opposite signs. A result that small next to others of the same category, with a sign that differs between the two programs, is most likely the remainder of contributions of both signs that cancel, where the relative deviation measures round-off rather than a difference in the inventory or the factors. Cyclia 1.9.1 tests this per result (gap below 1e-9 of the sum of the absolute contributions). This run was made before that test, so the category is reported as measured and is not claimed as validated.

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
