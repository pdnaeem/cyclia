# Cyclia development plan

This plan sets the order of work for Cyclia. Scientific correctness comes before new features. Each stage
starts only when the previous one passes its tests and validation.

The current state of every feature is in [FEATURE_STATUS.md](FEATURE_STATUS.md), and the changes of each
release are in the [changelog](CHANGELOG.md).

## Rules for every stage

1. Work on the existing architecture and keep every working feature.
2. Never invent characterisation factors or methods. Use official factor packages and documented equations.
3. Each new or changed calculation comes with:
   - its scientific method;
   - a test dataset and the expected numerical result;
   - an automated test;
   - acceptance criteria;
   - documentation in [METHODS.md](METHODS.md).
4. Never report an external comparison that was not actually run with the external software and its reference data.
5. Imports never discard data silently and never fill gaps with values that change environmental results.
6. Each release lists what changed, how it was tested, the validation results and the known limits.

## Completed foundations

| Area | Result |
|---|---|
| Agreement with ecoinvent | 100 % of 2,500 results within 0.1 % (EF 3.1, cut-off). The land use deviation of earlier releases was traced to a solver cut-off and removed |
| Inventory reconciliation | Each deviation is split into an inventory and a factor part, using ecoinvent's cumulative LCI |
| Database integrity | Staging import, integrity report, rollback, non-finite values rejected, explicit providers kept, per-database check |
| Factor matching | Flow-by-flow comparison with openLCA, Brightway or CSV factor sets, with the effect on results |
| EPD module consistency | The module table must match the LCA result before an EPD is written |
| Custom data entry (1.6.0) | Own databases, flows, processes, exchanges and factors with identifiers, provenance and unit validation; unknown factors of custom flows are reported, never taken as zero |

## Stage P0: scientific correctness and reliability

Status after release 1.5.0. Items marked "open" need software or data that only the user has (openLCA, licensed
factor packages); the tools for them are in the app.

| Item | Status | Result and what remains |
|---|---|---|
| Comparison with Brightway | Done | Real Brightway (bw2calc) in the app and in every release build; all results agree within 1e-6 ([cross validation](CROSS_VALIDATION.md)) |
| Comparison with openLCA | Open | Kit with openLCA JSON-LD and an openLCA 2 script; the run needs openLCA 2 on a desktop computer |
| Validation of ReCiPe 2016 and CML-IA | Open | The ecoinvent validation now covers every installed method of ecoinvent's results file; the run needs the ecoinvent licence |
| Comparative LCA validation | Done | Conclusions per category from the paired Monte Carlo probability and its sampling error at a chosen confidence; analytic reference test |
| Nested uncertainty and data quality | Done | Analytic two-level lognormal and hand-calculated nested DQR tests; no defect found |
| Water and land use calculations | Done, factors open | AWARE water balance with identified and unidentified consumption; LANCA and SQI by hand calculation. A check against the official LANCA and AWARE packages needs those packages |
| Social LCA and MFA calculations | Done | Two defects corrected: waste sent to treatment was counted as an avoided product in the social screening, and the end-of-life recycling and collection rates counted production and imported scrap. Hand-calculated tests, MCI reference values |

## Stage P1: professional LCA maturity

| Item | Depends on | Acceptance criteria |
|---|---|---|
| Database explorer, complete | Explorer (done) | Characterisation factors, data quality, uncertainty and UUIDs per dataset; duplicate detection; supplier relationships |
| Allocation manager | Allocation overview (done) | Side-by-side results for mass, economic, energy and system expansion, with the calculation shown |
| EPD programme profiles | Profiles (drafts) | Requirements checked against the current programme documents (EPD International GPI, IBU PCR Part A, INIES); reviewed by the operators where they agree |
| Life cycle costing | LCC (done) | Residual value, price escalation per cost type, ISO 15686-5 categories, cost uncertainty |
| Process graph editor | Flow diagram (done) | Inventory edited from the diagram, for foreground, background, co-products and avoided products |
| Reports and provenance | Report centre (done) | Every report states method versions, database versions, validation status, assumptions and limits, with a recursive provenance annex |

## Stage P2: advanced environmental and sustainability assessment

| Item | Depends on | Acceptance criteria |
|---|---|---|
| USEtox 2 | Toxicity import (done) | Official factors; results for the USEtox reference substances reproduced |
| IMPACT World+ | Licence of the factor package | Official factors, regionalised where provided; reference results reproduced |
| Full social LCA | PSILCA and SOCA import (done) | Stakeholder categories, indicators, risk and performance assessment per UNEP 2020 guidelines and ISO 14075 |
| Biodiversity | Licensed method | Only with an official, documented factor set |
| Plugin interface for methods and data packages | Stable method API | Methods and data added without changes to the calculation engine, with signature and test requirements |

## Stage P3: future work

Prospective LCA beyond background scenarios, dynamic characterisation for categories other than climate,
multi-user projects, supplier data collaboration, circularity measurement per ISO 59020, and optimisation for
decision support.
