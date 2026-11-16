# Cyclia 1.9.1: acceptance record

Response to the source-code audit of 1.9.0 (8.6 / 10) and to the ecoinvent 3.13 benchmark run with 1.9.0.

The suite has 410 automated tests. Here, without Brightway, 406 pass and the four Brightway comparisons are skipped.
The reference regression snapshot passes unchanged. The validation suite (35 of 35) and the IPCC 2021 check pass.

| Audit item | Result |
|---|---|
| P0: yes/no factor in ecoinvent's LCIA workbook read as 1.0 | Fixed: refused with the row named; NaN, inf and 1e309 too; notes such as "n.a." left out and reported |
| P0: 1e309 normalisation and weighting stored as infinity | Fixed: normalisation positive and finite, weighting zero or more |
| P0: 1e309 mapping conversion factor accepted, inherited factors infinite | Fixed: positive and finite; legacy rows left out of matching |
| P0: every LCIA import through the common validator | Done: `store_raw` and every CSV path use numcheck |
| P1: parameter `model_id` / `id` as yes/no | Fixed in the API and in the storage layer; missing records refused |
| P1: scenario identifiers | Fixed: `scenario`, `bg_id`, `scenario_ids`, scenario and background scenario ids |
| P1: every storage endpoint validates identifiers independently | Done: every public method of the storage layer with an identifier argument |
| P1: regression tests for these paths | tests/test_v191.py (16 tests) and one benchmark test in test_features |
| P2: benchmark status, 1.3.10 history, validation report | docs/benchmarks (ecoinvent 3.13 run), README, website, feature status |

## 1. LCIA imports (importers/lcia.py)

Reproduced on 1.9.0, as in the audit:
- `True` in the CF column of ecoinvent's LCIA workbook was imported as 1.0;
- `1e309` in a normalisation and weighting CSV was stored as infinity;
- `1e309` as a mapping conversion factor made the inherited factor infinite.

Now:
- `store_raw` reads every factor with `numcheck.finite`. Every importer that stores factors goes through it:
  workbook, CSV, JSON-LD, official packages, scenario rules and custom factors.
- **Workbook.** A cell meant as a number (also "1e309", "inf", "nan") that is not a finite number stops the import,
  with the row, flow and category named. A yes/no cell does the same. Other text, such as "n.a.", is left out and
  counted in the warnings, as such rows were skipped before (silently).
- **Normalisation and weighting CSV.** The normalisation reference must be above zero and finite: results are
  divided by it. The weight must be zero or more and finite.
- **Flow mapping CSV.** The conversion factor must be above zero and finite. Matching leaves out mapping rows whose
  factor is not a positive finite number, which covers rows saved by an earlier version.

Tests (TestLciaImports):
- the workbook with True, False, "1e309", "inf" and "NaN" is refused, with no method left behind; "n.a." is left
  out with a warning;
- `store_raw` refuses yes/no, infinity, NaN, text and None;
- the factor CSV refuses "1e309", "true", "nan" and "-inf", and reads "1,5" in a semicolon file;
- the normalisation CSV refuses seven bad pairs and stores nothing;
- the mapping CSV refuses "1e309", 0, -1, "true" and "nan"; a legacy infinite mapping row produces no infinite
  factor.

## 2. Identifiers

Reproduced on 1.9.0: `{"model_id": true, "name": "bool_scope", "value": 2}` attached the parameter to model 1, and
`{"id": true, "name": "renamed", "value": 2}` updated parameter 1.

Now:
- **Storage layer.** Every public method of ProjectStore with an identifier argument checks it on entry, whoever
  calls it. The argument names are `db_id`, `act_id`, `flow_id`, `model_id`, `input_id`, `ref_id`, `pid`, `sid`,
  `cid`, `vid`, `tid` and `activity_id`. A yes/no value, 0, a negative number, a fraction or text is refused; digit
  strings from URL paths are read as numbers.
  - None stays allowed where the method has it as default, for an EPD line's `ref_id` and for a comment on the whole
    model.
  - `save_model`, `save_parameter`, `save_scenario` and `save_bg_scenario` check `id` and `model_id`, and refuse
    an update of a record that does not exist. Before, a missing id updated nothing and reported success.
- **API.**
  - `/api/parameters` checks `model_id` and `id` before anything else.
  - `scenario` and `bg_id` are optional identifiers: absent or empty means none, anything else must be a whole number
    of at least 1. Before, `false` meant none and `true` meant 1.
  - `scenario_ids` is checked as a list of identifiers.
- **Modules.**
  - Custom data: methods, databases, exchanges, history.
  - Critical review: model.
  - Optimisation of choices: model, lines, alternatives, targets, method of each objective.
  - MFA: linked datasets, methods.

Tests:
- TestIdentifiers covers parameters (seven bad records, nothing saved), scenarios, and 15 storage methods called
  with seven bad values each. Digit strings and None still work where they should.
- TestIdentifiers.test_modules covers custom factor, review comment, choices model and method.
- TestApi covers the audit's two requests and `model_id: false` (status 400, nothing saved), and yes/no scenario,
  background scenario and scenario list.

## 3. Benchmark against ecoinvent

The user's run with 1.9.0 on ecoinvent 3.13 cut-off covered 100 datasets, 46 method families, 614 categories and
61,400 results.

**Pooling.** Reading the run's workbook showed that statistics were grouped by category and indicator name.
Methods with the same names were therefore pooled: the seven "climate change / GWP100" rows each showed 700 results.
The factor finder, the cause of deviations and the land use reconciliation did the same. They also applied one
method's factors to the results of all methods with the same names. This explains the 15 % in the "ecoinvent LCI x
Cyclia factors" column for climate change in that run.

Results now carry their method's identifier, and every statistic and diagnosis uses it.

Test (test_features, test_benchmark_keeps_methods_apart): a second family with the same names and doubled factors.
Each family has its own row, each counts its own results, and all agree.

**Cancelling results.** In the two deviating categories (Ecological Scarcity 2021 biotic resources, with and
without long-term emissions):
- 90 of 100 results deviate;
- every deviating result is at most 1e-5 of the category's largest result in the sample;
- in 83 the two programs give opposite signs.

That pattern belongs to results that are remainders of contributions of both signs. The benchmark now computes for
each result the sum of the absolute contributions g = |Q_k| |x|. A result outside 0.1 % agrees when the gap is below
1e-9 g. The relative difference before the rule and g are kept for every result. Each category reports how many
results the rule applied to, in the workbook and in the published reports.

The rule never hides an ordinary deviation. Tests (TestBenchmarkRoundOff):
- the run's own values pass with contributions of 1;
- the same values with contributions of 1e-2 do not pass;
- a 1 % deviation with contributions of 10^6 stays 1 %;
- a 0.01 % deviation keeps its value.

Whether the 90 results pass depends on their contributions, which only a new run on ecoinvent can measure. Until
then the category is "not validated" in every document.

**LCI label column.** The column "Exchange Name / Compartment / Subcompartment / Reference Product Amount" of
ecoinvent's cumulative LCI file was read as a flow; it was listed as "not among Cyclia's flows" for all 100
datasets. It is now skipped, judged on its own cells: empty cells of real flow columns take labels from the left.
Test: TestBenchmarkRoundOff.test_lci_label_column_is_not_a_flow.

## 4. Published benchmark

docs/benchmarks holds 16 reports, one per method family group, written from the run's workbook by
`engine/tools/benchmark_publish.py`. The statistics are computed again per method from the All results sheet: each
dataset's 614 rows follow the order of the By category sheet, which the tool checks before using them. The sum over
the reports is 61,400 results, the run's total.

- 612 of 614 categories: every result within 0.1 %; largest deviation 0.019 %; median of the category medians
  3.4e-07 %.
- Ecological Scarcity 2021 biotic resources (2 categories): reported as measured (10 % within 0.1 %) with the
  analysis above, and not claimed as validated.

The reports contain statistics and ratios only, never an ecoinvent or Cyclia result. Test:
TestPublicationFromWorkbook checks that no value of the workbook appears in the reports, that the statistics are
per method, and that a workbook whose rows do not align reports the pooled statistics with a note.

The earlier EF 3.1 benchmark with 1.3.10 is kept as history (docs/VALIDATION_ECOINVENT.md).
