# Cyclia benchmarks against ecoinvent

Each report compares Cyclia's results with ecoinvent's own cumulative LCIA results, for the method family and the ecoinvent version named. The reports contain deviation statistics only; no ecoinvent value is reproduced. They are produced by Cyclia (Validation > Benchmark Centre > Publish benchmark reports) on a computer with an ecoinvent licence.

| Method | Database | Results compared | Status | Date | Cyclia |
|---|---|---:|---|---|---|
| [CML-IA](cml-ia-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 2,200 | Validated | 2026-11-17 | 1.9.2 |
| [Crustal Scarcity Indicator 2020](crustal-scarcity-indicator-2020-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 100 | Validated | 2026-11-17 | 1.9.2 |
| [Cumulative Energy Demand (CED)](cumulative-energy-demand-ced-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 1,200 | Validated | 2026-11-17 | 1.9.2 |
| [Cumulative Exergy Demand (CExD)](cumulative-exergy-demand-cexd-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 1,400 | Validated | 2026-11-17 | 1.9.2 |
| [EF](ef-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 10,600 | Validated | 2026-11-17 | 1.9.2 |
| [EPS 2020d](eps-2020d-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 1,400 | Validated | 2026-11-17 | 1.9.2 |
| [Ecological Footprint](ecological-footprint-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 400 | Validated | 2026-11-17 | 1.9.2 |
| [Ecological Scarcity 2021](ecological-scarcity-2021-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 4,000 | Validated | 2026-11-17 | 1.9.2 |
| [Ecosystem Damage Potential](ecosystem-damage-potential-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 300 | Validated | 2026-11-17 | 1.9.2 |
| [IMPACT World+ v2.2.1, footprint version](impact-world-v2-2-1-footprint-version-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 500 | Validated | 2026-11-17 | 1.9.2 |
| [IPCC](ipcc-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 7,200 | Validated | 2026-11-17 | 1.9.2 |
| [Inventory results and indicators](inventory-results-and-indicators-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 3,500 | Validated | 2026-11-17 | 1.9.2 |
| [ReCiPe](recipe-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 25,600 | Validated | 2026-11-17 | 1.9.2 |
| [TRACI v2.1](traci-v2-1-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 1,800 | Validated | 2026-11-17 | 1.9.2 |
| [USEtox v2.13, endpoint](usetox-v2-13-endpoint-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 600 | Validated | 2026-11-17 | 1.9.2 |
| [USEtox v2.13, midpoint](usetox-v2-13-midpoint-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 600 | Validated | 2026-11-17 | 1.9.2 |

A method that is not listed here has not been benchmarked against ecoinvent and is not claimed as validated. Status rule: 'Validated' when at least 95 % of all results agree within 0.1 % and every category has at least 95 % of its results within 1 %.
## About this run

- Run with Cyclia 1.9.2 on ecoinvent 3.13 (cut-off): 100 datasets, 46 method families, 614 categories, 61,400
  results. All 61,400 agree with ecoinvent within 0.1 %; the largest deviation is 0.019 %.
- In Ecological Scarcity 2021 "biotic resources" (with and without long-term emissions), 1.9.2 reported 180 results
  as below numerical resolution. Their values are below 1e-6 of the category's largest result. The plain LU solution
  gave them the wrong sign, but the run's refined solution (one step of iterative refinement) matched ecoinvent within
  0.016 % for all 180. Since 1.10.0 every calculation in Cyclia includes that refinement step, and these reports
  compare those 180 results with the refined values.
- The reports were written from the run's workbook with `engine/tools/benchmark_publish.py`, which computes the
  statistics per method from the workbook's results.

## Earlier runs

- The same benchmark with Cyclia 1.9.0 and 1.9.1 gave identical values for the other 612 categories.
- EF 3.1 on ecoinvent (cut-off), Cyclia 1.3.10: 2,500 results (100 datasets, 25 categories), 100 % within 0.1 %
  ([report](../VALIDATION_ECOINVENT.md)).
