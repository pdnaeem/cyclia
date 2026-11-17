# Cyclia benchmarks against ecoinvent

Each report compares Cyclia's results with ecoinvent's own cumulative LCIA results, for the method family and the ecoinvent version named. The reports contain deviation statistics only; no ecoinvent value is reproduced. They are produced by Cyclia (Validation > Benchmark Centre > Publish benchmark reports) on a computer with an ecoinvent licence.

| Method | Database | Results compared | Status | Date | Cyclia |
|---|---|---:|---|---|---|
| [CML-IA](cml-ia-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 2,200 | Validated | 2026-11-16 | 1.9.1 |
| [Crustal Scarcity Indicator 2020](crustal-scarcity-indicator-2020-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 100 | Validated | 2026-11-16 | 1.9.1 |
| [Cumulative Energy Demand (CED)](cumulative-energy-demand-ced-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 1,200 | Validated | 2026-11-16 | 1.9.1 |
| [Cumulative Exergy Demand (CExD)](cumulative-exergy-demand-cexd-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 1,400 | Validated | 2026-11-16 | 1.9.1 |
| [EF](ef-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 10,600 | Validated | 2026-11-16 | 1.9.1 |
| [EPS 2020d](eps-2020d-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 1,400 | Validated | 2026-11-16 | 1.9.1 |
| [Ecological Footprint](ecological-footprint-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 400 | Validated | 2026-11-16 | 1.9.1 |
| [Ecological Scarcity 2021](ecological-scarcity-2021-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 4,000 | Validated except some categories | 2026-11-16 | 1.9.1 |
| [Ecosystem Damage Potential](ecosystem-damage-potential-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 300 | Validated | 2026-11-16 | 1.9.1 |
| [IMPACT World+ v2.2.1, footprint version](impact-world-v2-2-1-footprint-version-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 500 | Validated | 2026-11-16 | 1.9.1 |
| [IPCC](ipcc-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 7,200 | Validated | 2026-11-16 | 1.9.1 |
| [Inventory results and indicators](inventory-results-and-indicators-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 3,500 | Validated | 2026-11-16 | 1.9.1 |
| [ReCiPe](recipe-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 25,600 | Validated | 2026-11-16 | 1.9.1 |
| [TRACI v2.1](traci-v2-1-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 1,800 | Validated | 2026-11-16 | 1.9.1 |
| [USEtox v2.13, endpoint](usetox-v2-13-endpoint-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 600 | Validated | 2026-11-16 | 1.9.1 |
| [USEtox v2.13, midpoint](usetox-v2-13-midpoint-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 600 | Validated | 2026-11-16 | 1.9.1 |

A method that is not listed here has not been benchmarked against ecoinvent and is not claimed as validated. Status rule: 'Validated' when at least 95 % of all results agree within 0.1 % and every category has at least 95 % of its results within 1 %.
## Earlier runs

- The same benchmark with Cyclia 1.9.0 gave identical values.
- EF 3.1 on ecoinvent (cut-off), Cyclia 1.3.10: 2,500 results (100 datasets, 25 categories), 100 % within 0.1 %
  ([report](../VALIDATION_ECOINVENT.md)).

## Open: Ecological Scarcity 2021, biotic resources

In 90 of 100 datasets Cyclia's and ecoinvent's results for this category differ, though both results are smaller
than 1e-5 of the category's largest result. Most have opposite signs. ecoinvent's own cumulative inventory with
Cyclia's factors reproduces ecoinvent's results, so the gap lies in the cumulative amounts of the two fish flows
("Fish, demersal, in ocean" and "Fish, pelagic, in ocean"). Those amounts differ only below 1e-12 of the largest amount
of each dataset's inventory. Cyclia 1.9.2 adds the checks that settle the cause in the next run:
- whether the solver resolves each of these results (forward, adjoint and refined solutions);
- the datasets and exchanges that carry them;
- the negative exchanges of the category's flows.

The category is not validated until then.
