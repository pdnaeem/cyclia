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
| Custom data entry (1.6.0, 1.6.1) | Own databases, flows, processes, exchanges and factors with identifiers, provenance, change history and unit validation; editing; parameters and formulas; co-products with allocation; user-defined units; supply chain diagram; unknown factors (custom flows, and every flow in a custom method unless its scope is declared complete) are reported, never taken as zero |

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
| Allocation manager | Custom co-products (done in 1.6.2) | Done for multi-output custom processes: mass, energy, economic (currency and price year), physical causality and manual shares, compared side by side. Still to do: the same comparison for model-level allocation and system expansion |
| EPD programme profiles | Profiles (drafts) | Requirements checked against the current programme documents (EPD International GPI, IBU PCR Part A, INIES); reviewed by the operators where they agree |
| Life cycle costing | LCC (done) | Residual value, price escalation per cost type, ISO 15686-5 categories, cost uncertainty |
| Process graph editor | Done in 1.6.2 | Custom processes and model inventories are edited in their diagrams (connect, move between stages, amounts, credits, removal) |
| Reports and provenance | Recursive provenance (done in 1.6.2) | Done: every dataset of the supply chain with its database, version, identifier, amount, contribution and custom-data provenance (Excel, Word annex). Still to do: the Benchmark Centre summary and an automatic critical review checklist in the report |

## Release 1.6.2: scientific reliability (done)

| Item | Result |
|---|---|
| Custom factor invalidation | A custom flow whose name, compartment, subcompartment or CAS number changes has its own factors put under review; they are not used, and the result is incomplete, until confirmed or corrected |
| Flow editing and dependencies | Every process shows the processes and the models (in every project) that depend on it |
| Process versions, undo and restore | Every change keeps the state before and after; undo, redo by undoing the undo, restore any version, restore deleted processes |
| Parameter uncertainty | Distributions on parameters of custom data, drawn in the full Monte Carlo; formulas evaluated per iteration; shared draws within a database |
| Advanced allocation | Physical causality, economic with currency and price year, allocation sensitivity comparison |
| Scientific Benchmark Centre | One table of all evidence with status rules; IPCC 2021 numerical check |
| Input safeguards | Mass balance and order-of-magnitude warnings, decimal comma hint |
| Recursive provenance | In the Excel workbook and the Word report |
| Independent integration tests | Validation workflow with Brightway pinned to the validated commits; a skipped comparison fails |

Still open from the P0 list, because they need software or licences that are not available to the project:
- the EF 3.1 benchmark repeated on 1.6.2;
- the ReCiPe 2016 and CML-IA benchmarks (with the ecoinvent licence);
- the comparison with openLCA.

The Benchmark Centre shows them as "Not run" until they are run.

## Release 1.7.0: advanced environmental LCA

Done in 1.7.0:
- Enhanced LCC (ISO 15686-5);
- MFA integrated with LCA (virgin input, recycling, losses, credits with substitution, gross and net);
- Social LCA subcategory assessment, Type I;
- allocation choices of a model side by side;
- structure checks of the AWARE, LANCA and USEtox packages;
- validation evidence and the review checklist in the report.

Still open, with the reason:
- **AWARE 2.0, LANCA and USEtox 2 declared complete.** This needs the official packages and their reference results,
  which are distributed by their authors and are not available to the project. The calculations, imports and
  package checks are ready.
- **Social LCA Type II (impact pathways).**
- **Advanced regionalisation.**
- **Sobol indices with parameters of custom data.** This needs a new solve for every sample; the full Monte Carlo
  already propagates these parameters.

| Item | Acceptance criteria |
|---|---|
| AWARE 2.0 complete | Official factors with basin, country and monthly resolution; regional matching tested against the official package |
| LANCA complete | Every applicable indicator with the official factors; reference results reproduced |
| USEtox 2 | Official human toxicity and freshwater ecotoxicity factors, units and substance matching validated against the USEtox reference results |
| Advanced regionalisation | Regionalised inventories and factors combined, with coverage reporting |
| Full social LCA | Stakeholder categories (workers, local community, consumers, society, value chain actors), subcategories, primary and secondary data, PSILCA and SOCA integration, coverage and missing-data assessment, interpretation per UNEP 2020 and ISO 14075. Until then the module is called a screening |
| Enhanced LCC | Residual value, price escalation per cost type, ISO 15686-5 categories, cost uncertainty |
| MFA integrated with LCA | Inflows, stocks, losses, recycling, recovered and secondary materials and their impacts in one project model, not separate calculators |

These methods are declared complete only when their official factors, units, geographical mapping and
calculations are validated.

## Release 1.8.0: professional platform (planned)

The release will add:
- advanced visual process modelling;
- multi-user collaboration and collaborative professional review;
- a supplier data portal;
- advanced MFA and biodiversity (with an established, documented method);
- prospective and dynamic LCA beyond climate;
- scenario optimisation.

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
