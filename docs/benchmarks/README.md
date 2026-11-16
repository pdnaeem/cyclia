---
title: Cyclia benchmarks against ecoinvent
description: Per-method benchmark reports of Cyclia against ecoinvent's own cumulative LCIA results, with the status of each method family.
---

# Cyclia benchmarks against ecoinvent

Each report in this folder compares Cyclia's results with ecoinvent's own cumulative LCIA results for one method family
and one ecoinvent version. The reports contain deviation statistics only (how far Cyclia's result is from ecoinvent's,
per impact category). No ecoinvent value is reproduced, so the reports can be published with the source code.

## Status

| Method | Database | Results compared | Status | Cyclia |
|---|---|---:|---|---|
| EF 3.1 | ecoinvent (cut-off) | 2,500 (100 datasets x 25 categories) | 100 % within 0.1 % ([report](../VALIDATION_ECOINVENT.md)) | 1.3.10 |
| ReCiPe 2016 | | | Not run | |
| CML-IA | | | Not run | |
| IPCC 2021 (ecoinvent's implementation) | | | Not run | |

"Not run" means what it says: the method has not been benchmarked against ecoinvent and is not claimed as validated.
The built-in IPCC 2021 GWP100 method is checked on every release against the values published by the IPCC (AR6 WG1,
Table 7.15 and Table 7.SM.7) by the validation suite; that check does not involve ecoinvent.

## How a report is produced

The benchmark needs an ecoinvent licence, so it runs on a licence holder's computer, not on the build servers:

1. Import ecoinvent (ecoSpold2) and the method (ReCiPe, CML-IA, IPCC or EF) in Cyclia.
2. Validation > ecoinvent: choose ecoinvent's cumulative LCIA results file for the same version and system model, tick
   "every installed method", and run the benchmark.
3. Validation > Benchmark Centre > Publish benchmark reports writes one file per method family and a README with the
   status table. Copy them into this folder, replacing this README.

Status rule: "Validated" when at least 95 % of all results agree within 0.1 % and every category has at least 95 % of
its results within 1 %. A category below that is named in its report.
