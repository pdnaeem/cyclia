# Cyclia 1.3.8: findings of the third database audit (of 1.3.6)

For each finding: what was changed, how it is tested, and what is still not done.
- Tests: `engine/tests/test_v138.py` (12 tests).
- All 196 tests pass.

| Finding | Status |
|---|---|
| P0 A: non-finite amount in an unresolved input accepted | Fixed. Rejected at import, by linking and by the Database Check |
| P0 B: explicit external defaultProvider replaced by an internal producer | Fixed. Kept unresolved with the provider reference |
| P1 C: Database Check of one database counted library-wide flows | Fixed for coverage, units, LCIA compatibility and counts |
| Explorer: unresolved filter after a 100-row limit | Fixed. Every filter is in the query |
| Explorer: paging, filters, export | Done |
| Separate staging database | Done in 1.3.7 |
| Streaming large imports | Done for SimaPro CSV, ecoSpold1, ILCD and JSON-LD (limits below) |
| Full import integrity report | Done |
| Rollback and recovery testing | Done |

## P0 A. Non-finite values

- **Code**:
  - `engine/staging.py` `integrity()` counts every value that makes data unusable, for one database or a whole
    store;
  - `check()` (staging) and `_integrity()` (server, after every import) use it;
  - `engine/linking.py` `link()` refuses inputs with a non-finite or missing amount or parameter;
  - `engine/calc.py` `validate_database()` reports the counts as an error in the matrix status.
- **Checked**:
  - amounts of technosphere and elementary exchanges and of unresolved inputs;
  - uncertainty parameters p1 to p3 of all three;
  - uncertainty types (0 to 4);
  - production (non-finite or zero);
  - links to missing datasets or flows, and unresolved inputs of missing datasets.
- **Tests**:
  - The audit's experiment: an openLCA JSON-LD unresolved input with 1e309. The staged import stops, naming
    "unresolved input amounts", and the database is not in the library.
  - An infinite p1, an uncertainty type 9 and a zero production are each counted once, and the Database Check shows
    an error.
  - Linking an input whose amount is Infinity is refused and adds no exchange.

## P0 B. Explicit openLCA provider

- **Code**: `engine/importers/jsonld.py`; `engine/linking.py` `auto_link()` and `suggest()`.
- **Rule**:
  - If the defaultProvider is in the import, it is the supplier.
  - If a defaultProvider is given but is not in the import, the input stays unresolved. The reason is "default
    provider not in this import: <name>", and the provider id is kept as the link key.
  - If there is no defaultProvider and exactly one producer, that producer is linked.
  - If there are several producers, the input stays unresolved as ambiguous.
- **Tests**:
  - The audit's scenario (an external provider plus one internal producer of the same product): nothing is linked,
    the reason and provider id are kept, and auto-link leaves the input open.
  - A dataset with that key in another database is the first suggestion, marked as the named provider.
  - Without a defaultProvider, the single producer is still linked.

## P1 C. Scope of the Database Check

- **Code**: `engine/calc.py` `validate_database()`.
- **Test**: the audit's experiment. DB A has one CO2 flow with a factor; DB B has one flow with no factor. Checking
  DB A gives 1 flow used, 0 without a factor, 100 % coverage and 1 dataset. Checking the whole library gives 2 flows.

## Database Explorer

- **Code**: `GET /api/explore` and `POST /api/explore/export` in `engine/server.py`; UI in `app/ui/v136.js`.
- **Filters**: text, database, location (exact), system model, version, datasets with unresolved inputs, and
  datasets with an elementary flow (by name). All filters are applied in SQL before paging. Results come 50 per page
  (at most 200) with the total.
- **Export**: the ticked datasets go to Excel with four sheets: datasets, technosphere inputs, elementary flows and
  unresolved inputs.
- **Tests**:
  - 151 datasets, with the one that has an unresolved input last in alphabetical order: the unresolved filter finds
    it (total 1).
  - Paging, location, system model, version and flow filters give the expected totals.
  - The export has one row per dataset and per exchange.

## Streaming imports

- **Code**: `engine/importers/other_formats.py` (`_Builder`, SimaPro, ecoSpold1, ILCD) and
  `engine/importers/jsonld.py`.
- **What changed**:
  - SimaPro CSV is read row by row, one process block at a time. The encoding is detected by reading the file in
    chunks.
  - SimaPro, ecoSpold1 and ILCD write each dataset when it is read, and elementary exchanges in batches of 20,000.
  - ecoSpold1 and ILCD no longer keep the parsed XML of every file.
  - JSON-LD keeps compact product exchanges instead of whole process documents, and writes elementary exchanges in
    batches. (ecoSpold2 already streamed through a temporary table.)
- **Measured**: synthetic SimaPro files, one process with one input and one emission each, on the development
  machine (peak resident memory of the Python process).

  | File | 1.3.7 | 1.3.8 |
  |---|---|---|
  | 50,000 processes, 11 MB | 391 MB | 172 MB |
  | 200,000 processes, 46 MB | 1,117 MB | 360 MB |

- **Test**: 600 SimaPro processes in cp1252 with a non-ASCII name and batches of 50. Every dataset, emission and link
  arrives, and the integrity report passes.
- **Limits**:
  - Technosphere inputs are still held in memory until the end (compact tuples), because a supplier can only be
    chosen once every producer of the import is known.
  - The JSON-LD and ILCD reference-flow maps are also held.
  - Full ecoinvent-size imports were not run here (licensed data).

## Import integrity report

- **Code**: `staging.check(store, report)`. The format import's result gets `integrity_report`, stored in the
  database's import report and shown after the import.
- **Contents**:
  - counts: datasets, technosphere exchanges, elementary exchanges, flows, unresolved inputs, exchanges with
    uncertainty;
  - the list of checks;
  - the largest matrix residual;
  - the result.

## Rollback and recovery

- **Tests**:
  - An importer that fails after writing a dataset leaves no database and no staging folder.
  - A failure inside the merge transaction (forced by a trigger) leaves the library's datasets and databases exactly
    as before. A following import then succeeds.
  - 1.3.7's test of a failed check (NaN emission) still passes.

## Not done (audit P2)

- database comparison dashboard;
- supplier relationship visualisation;
- database update notifications;
- duplicate dataset detection;
- quality filters in the explorer.

The audit's limitation still applies: no licensed full-database import, and no run against real openLCA or Brightway
installations.
