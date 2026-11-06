# Cyclia development history

What was added and corrected from release 1.3.2 to 1.4.1, including the findings of independent reviews and how
each was resolved. The detailed records, with tests and acceptance criteria, are the ACCEPTANCE files in this
folder. Current status: [FEATURE_STATUS.md](../FEATURE_STATUS.md).

---

## 1.3.2: features added after a full feature review

| Area | Feature | Priority |
|---|---|---|
| Interpretation | Key findings in plain language (contributors, stages, credits, module D, Monte Carlo interval, burden shifting, best improvement lever, data to improve, costs, errors) in a Summary tab and the report | P0 |
| Data quality | Contribution-weighted data quality rating per category (PEF form) with primary, secondary and estimate shares | P0 |
| Inventory | Data type per line: primary, secondary, estimate | P0 |
| Inventory | Provenance per line: reference, data year, supplier or site, third-party checked; report table and data-age check | P1 |
| Reporting | Review and verification status (draft, internal, expert, panel, verified) in report and checks | P0 |
| Reporting | Report centre: every report with what it still needs | P1 |
| Reporting | Executive summary (two pages) | P1 |
| Reporting | Figures as 300 dpi PNG and SVG | P2 |
| Reporting | Excel sheets for data quality, key findings, costs and water | P2 |
| EPD | ISO 14025:2026 items: audience, specific-data share, months of specific data, prospective EPD, verifier check | P1 |
| Goal and scope | Modelling approach (attributional or consequential) with consistency checks against allocation and database system model | P1 |
| Goal and scope | Technological coverage | P1 |
| Impact assessment | Warning when different versions of one method are mixed | P1 |
| Recycling | Circular Footprint Formula calculator that writes the inventory lines | P1 |
| Databases | Comparison of two databases (e.g. ecoinvent versions) on project datasets or a sample | P1 |
| Databases | Move a model to another database version, with preview and undo | P1 |
| Costing | Life cycle costing with prices per line, sub-models, revenue from credits and discounting | P2 |
| Inventory | Water inventory: withdrawal, release, consumption, turbine water apart | P2 |
| Inventory | Energy balance check for energy products | P2 |
| Uncertainty | Correlated parameters (Gaussian copula) | P2 |
| Uncertainty | Monte Carlo convergence: standard error of the mean and stability of the interval | P2 |
| Comparison | Lowest alternative per category, burden-shifting alert, small-difference alert | P0 |
| Project | Project overview of all models with data quality, review status and results | P2 |

Every new calculation has an automated test; the Circular Footprint Formula test recomputes the formula by
hand.

---

## 2a. Corrections in 1.3.3 (external audit of 1.3.2)

| Audit finding | Priority | Status in 1.3.3 |
|---|---|---|
| Nested models: parameter distributions and line uncertainty not propagated in Monte Carlo | P0 | Fixed: hierarchical Monte Carlo and Sobol over every line and parameter of every nested model |
| Comparisons computed despite different functional units | P0 | Fixed: comparison gate (blocked, screening, valid) with a functional equivalence statement |
| Land use deviation from ecoinvent | P0 | Open: the cause needs a licensed benchmark file; the limitation is now stated in checks and reports |
| EPD: unassigned stages, A1-A3 always declared, no reconciliation | P0 | Fixed: unassigned stages block the EPD, A1-A3 only with lines, module table reconciled |
| DQR: credits weighted, reliability used as precision, nested data ignored | P1 | Fixed: credits apart, pedigree indicator renamed, real PEF DQR from PEF scores, nested paths |
| Improvement advice could propose reducing a credit | P1 | Fixed |
| Different hotspots called burden shifting | P1 | Fixed: wording, plus the effect of the change on every category |
| 5-year limit for producer-specific data missing | P1 | Fixed |
| Correlation entered as rank but used as latent | P1 | Fixed: Spearman conversion |
| Database migration not recursive | P1 | Fixed: all nested models, before/after results, undo |
| Report centre checklist too short | P1 | Fixed: 18 required and several recommended ISO 14044 items |
| Fixed 10 % significance rule; "same random values" claim | P1 | Fixed: Monte Carlo based significance; exact description of what is shared |
| EPD RSL check inverted; EF version by text match; prospective EPD without convergence | P1 | Fixed |

100 automated tests (including one regression test per finding) and the 35-case validation suite pass. The
audit was source-based; an independent numerical comparison with openLCA and Brightway on the same inventory is
planned (section 5).

---

## 2b. Corrections in 1.3.4 (second external audit, of 1.3.3)

| Audit finding | Priority | Status in 1.3.4 |
|---|---|---|
| Land use deviation from ecoinvent | P0 | Still open. New diagnostics: occupation and transformation split, factor change per group, uncharacterised land flows, conflicting factors. Needs a run with a licensed ecoinvent results file |
| Independent numerical cross-check | P0 | Done inside the app (second implementation, other solver): agreement 5.7e-14 on the shipped data; openLCA and Brightway comparison of factor matching still planned |
| Data age not checked in nested models | P1 | Fixed: every nested model, model named |
| Comparison data quality only for the first category | P1 | Fixed: every category |
| System model and approach checks not recursive | P1 | Fixed |
| Nested inventory missing from reports | P1 | Fixed: complete foreground inventory in Word, Excel, EPD Excel and the app |
| EPD resource, waste and output indicators not validated | P1 | Fixed: Tables 4 to 6, units, factors; "not ready for submission" status |
| Allocation management | P1 | Added: allocation overview and physical causality |
| Programme-specific EPD templates | P1 | Partly: PCR version and programme statements; layouts per programme still planned |

## 2c. Added in 1.3.5 (third external audit, of the 1.3.4 roadmap)

The acceptance criteria, tests and demonstration data for every item are in docs/quality/ACCEPTANCE_1.3.5.md.

| Requested | Status in 1.3.5 |
|---|---|
| Factor matching validation against openLCA and Brightway | Done: flow-by-flow comparison with openLCA JSON-LD, a Brightway export script and CSV; effect on every model; split of result differences. Not yet run on a real openLCA or Brightway installation |
| Programme-specific EPD templates | Done as profiles (EPD International, IBU, INIES, custom JSON) that set the Word layout, fields, statements and checks. Drafts, not approved by the operators |
| EF dataset DQR | Done for ILCD/EF imports |
| Grouped results tabs | Done |
| Consequential marginal-supplier guidance | Done: constrained suppliers excluded, proposal, consequential scenario in one step |
| More complete LCC | Partly: cost types, replacements within a study period. Residual value and escalation are not done |
| AWARE 2.0 | Done as a regionalised method engine; official factors must be imported |
| LANCA | Done as a regionalised method engine; official factors must be imported |
| Social LCA | Done as a risk-hour screening; PSILCA/SOCA data must be imported |
| MFA | Done: dynamic MFA with stocks, lifetimes, loops and mass balance; MCI |
| IMPACT World+, official USEtox 2, biodiversity, multi-user, dynamic characterisation beyond climate | Not implemented |
| Advanced regionalisation | Partly: sub-national codes with fallbacks in AWARE and LANCA |

---

## 2d. 1.3.6 (audits of 1.3.5)

Database integrity and scientific reliability fixes; every finding, fix and test is in docs/quality/ACCEPTANCE_1.3.6.md.
Still open from those audits: native PSILCA/SOCA import, AWARE monthly and GIS factors, LANCA SQI aggregation,
ILCD+EPD export, visual MFA builder and MFA-LCA link, staging database and streaming import, published
openLCA/Brightway comparison, confirmation of the land use cause with a new benchmark run.

---

## 2e. 1.3.7

The open items of 1.3.6 (docs/quality/ACCEPTANCE_1.3.7.md): ILCD+EPD export, PSILCA/SOCA import, AWARE monthly and GIS,
LANCA SQI aggregation, MFA builder and MFA-LCA link, staging imports, comparison kit. Still open: the Brightway and
openLCA runs with the kit, ILCD+EPD 1.3 elements, MFA flows as inventory lines, streaming of very large imports.

## 2f. 1.3.8

Database integrity release (docs/quality/ACCEPTANCE_1.3.8.md): non-finite values rejected everywhere in an import, explicit
openLCA providers outside the import kept unresolved, Database Check scoped to the selected database, explorer
filters in the query with paging and export, streaming imports, import integrity report, rollback tests. Still open
(audit P2): database comparison dashboard, supplier relationship view, update notifications, duplicate dataset
detection, quality filters in the explorer; a full ecoinvent import benchmark on the user's machine.

## 2g. 1.3.9

Inventory check against ecoinvent's cumulative LCI: each deviation of the benchmark is split into an inventory and a
factor part, so the cause of the land use deviation is measured on the user's machine.

## 2h. 1.3.10

The measured cause (100 % inventory) was the cut-off of small scaling factors in the solve; removed. Open: the
user's re-run of the benchmark.

## 2i. 1.4.0

1.3.8 to 1.3.10 in one release that builds on every platform: the macOS failure of 1.3.10 (solver round-off in
categories that are zero) fixed in the solve and in the EPD check.

## 2j. 1.4.1

Benchmark against ecoinvent recorded: 100 % of 2,500 results within 0.1 % (docs/VALIDATION_ECOINVENT.md). The
land use item of the earlier benchmarks is closed.

---
