# Cyclia 1.9.0: acceptance record

First release of the road to Cyclia 2.0 (docs/DEVELOPMENT_PLAN.md, "Road to 2.0"). It covers four tasks:
- reject yes/no values given as numbers, with one validator on every importer and API path;
- run regression tests on the whole database and the LCIA results;
- prepare published benchmarks for ReCiPe, CML-IA and IPCC;
- make the Brightway tests mandatory for a release.

The suite has 393 automated tests. Here, without Brightway, 389 pass and the four Brightway comparisons are skipped.
On GitHub the release gate runs all 393 with Brightway installed. The gate passes here in its local mode
(`--no-brightway`); in the required mode without Brightway it fails, as it must. The validation suite (35 of 35)
and the IPCC 2021 check pass.

| Task | Result |
|---|---|
| Yes/no values refused as numbers | Done: engine/numcheck.py on the API, storage, modules and importers |
| One finite-number validator on every importer and API path | Done; importers count and report the values they cannot use |
| Full database and LCIA regression tests | Done for the reference libraries (committed snapshot, every test run); the tool for installed libraries is in the app and on the command line |
| Published ReCiPe, CML-IA and IPCC benchmarks | Report generator done. The runs need ecoinvent's results and a licence, so they are listed as "Not run" in docs/benchmarks until a licence holder runs them |
| Brightway tests mandatory in the release | Done: the installer build needs the release gate, which fails on a skipped Brightway test |

## 1. Yes/no values and the common validator

Python reads `True` as 1 and `False` as 0, and JSON's `true` and `false` become those values. Before 1.9.0, a yes/no
sent in place of a number therefore passed every check that only asked for a finite number. Reproduced on 1.8.4:
- `{"model_id": true}` sent to /api/calculate calculated model 1;
- `{"amount": true}` gave an amount of 1;
- a scenario rule factor `true` scaled by 1;
- `int(2.5)` read a count of 2.5 as 2.

engine/numcheck.py now refuses booleans (numpy booleans too), NaN, infinity (1e309 included), text, lists, and
fractions where a whole number is needed. Every path uses it:
- **API.** `_need` checks every identifier field (`*_id`, `*_ids`, `db_a`, `db_b`, `db_from`, `db_to`) where the
  request is read, and `_num`, `_int` and `_ids` use the validator. A request with `{"model_id": true}` gets
  "model_id must be a number, not a yes/no value (True)."
- **Storage.** Functional unit, line fields, scope numbers, parameters, scenarios, site factors and background
  scenarios.
- **Modules.** Supplier responses, custom data, choices, MFA, Type I social weights, scenario rules (factors,
  factor years, shares, scenario file amounts), sweeps and optimisation (bounds, steps, limits, objectives, samples),
  the Circular Footprint Formula and its mass, rank correlations, regional methods (months, coordinates,
  normalisation, SQI weights, factor tables), social screening (worker hours, activity values), teaching answers,
  the inventory template (amounts, data quality scores), the Brightway exchange file, linking factors.
- **Importers.**
  - ecoSpold 1 and 2, SimaPro CSV and ILCD read every number through `numcheck.read`. An unusable value is counted,
    and the import result gives a warning with the count and examples, plus `unusable_numbers`.
  - openLCA JSON-LD does the same for uncertainty values, conversion factors and LCIA factors (an unusable factor is
    left out, not set to 0). An exchange amount that is not a finite number stops the import with the flow named,
    because replacing it would change results.

Tests (tests/test_v190_numbers.py, 14 tests):
- the validator on booleans, numpy booleans, NaN, infinity, "1e309", text, lists, decimal commas, fractions,
  identifiers and years, and the counting reader;
- the storage layer: functional unit, line amount, parameter value, line year and amount;
- scenario rules, CFF and correlations, regional months, numbers and coordinates, inventory data quality and
  teaching answers;
- the importers: a JSON-LD amount `true` refuses the import and leaves no database; an uncertainty `true` is
  reported and does not invent a distribution;
- the API: amount, ref_id, model_id and method_ids given as yes/no, a fractional model_id, `1e309` and `NaN` in the
  request text. Each is refused with status 400 and nothing is stored.

The test of 1.3.8 for an infinite openLCA amount now expects the earlier refusal (while reading, with the flow
named) instead of the later one (during staging).

## 2. Full-library regression

engine/regression.py records:
- for every dataset, its score under every impact category (one unit of reference product, full supply chain);
- for every model of the project, its result in every category through the normal calculation;
- for every category, the factor matching: factors given, flows matched, regional factors, flows used by the library
  without a factor, and a fingerprint of the matched factors.

All dataset scores of a category come from one transposed solve (A^T y = q^T). As in the normal calculation, a
dataset whose supply chain reaches no characterised exchange is exactly zero (METHODS section 20).

The reference snapshot (engine/tests/data/reference_regression.json.gz, 10 kB) covers:
- the tutorial and demo databases, 68 datasets;
- 20 impact categories;
- the 7 demo models (template models included);
- 1,500 values in all.

The engine of 1.8.4 reproduces it bit for bit, so 1.9.0 changes no result of valid data.

Tests (tests/test_regression.py, 10 tests):
- the reference libraries match the committed snapshot; all 1,500 values are compared;
- the transposed solve equals one solve per dataset to a relative 1e-10, with identical zeros;
- model values are those of calc.run;
- a snapshot survives saving and loading; a foreign file is refused;
- detection:
  - a factor changed by one part in a million changes the fingerprint and the values;
  - an exchange changed by 0.1 % is found with its size;
  - a removed factor shows as one flow less matched;
  - round-off of one part in 10^12 is not a difference;
- the command line tool returns 0, 1 or 2 (pass, differences, error);
- the API records a snapshot, finds no difference against it, finds a changed exchange, and refuses a missing file.

For an installed library (ecoinvent with its methods): Toolbox > Validation > Full-library regression >
Record snapshot, and later Compare; or `python engine/tools/regression.py record|compare|check`. A snapshot of
ecoinvent holds ecoinvent results, so .gitignore excludes `*ecoinvent*.json` and `*ecoinvent*.json.gz`.

## 3. Benchmark publication (ReCiPe, CML-IA, IPCC, EF)

- Benchmarks against ecoinvent's cumulative LCIA results now keep statistics per category. These are:
  - the median, signed median, 95th percentile and maximum deviation;
  - the share of results within 0.1 % and within 1 %;
  - the number of datasets compared and in the file;
  - whether the inventories were compared.
  No ecoinvent value is kept.
- Toolbox > Validation > Publish benchmark reports writes one Markdown report per method family group and
  ecoinvent version, with a README holding the status table. Families are grouped as ReCiPe, CML-IA, IPCC and EF;
  any other family keeps its own name.
- docs/benchmarks/README.md states the current status honestly:
  - EF 3.1: run with 1.3.10;
  - ReCiPe, CML-IA and ecoinvent's IPCC implementation: not run.
  The built-in IPCC 2021 GWP100 is checked on every release against the IPCC's published values, which is not an
  ecoinvent benchmark.

Tests (tests/test_benchmark.py):
- nothing is published before a run;
- four families give four reports and a README with the right statuses;
- a category below the rule is named with its hint;
- the stored record holds no reference or Cyclia values;
- the grouping of family names.

**Open, external.** The runs themselves: they need ecoinvent's cumulative LCIA results file with a licence.

## 4. Brightway mandatory for release builds

engine/tools/release_gate.py runs in order:
- the whole suite with `CYCLIA_REQUIRE_BRIGHTWAY=1`; a skipped test of any kind fails the gate, and so does a
  Brightway comparison that did not run;
- the regression;
- the validation suite;
- the IPCC check.

.github/workflows/build.yml has a `scientific-gate` job that installs the pinned Brightway
(engine/tools/brightway-pins.txt) and runs the gate. The `build` job declares `needs: scientific-gate`, so no
installer is built or published when the gate fails. The validation workflow runs the same gate on every push.

Checked here:
- without Brightway and `--no-brightway`, the gate passes (393 tests run, 4 skipped);
- without Brightway in the required mode, it fails, naming the import error and the missing comparison.
The pinned Brightway cannot be installed in this environment (no access to PyPI), so the passing run with Brightway
takes place on GitHub.
