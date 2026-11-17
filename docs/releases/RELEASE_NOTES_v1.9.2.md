# Cyclia 1.9.2

Benchmark diagnostics, after the 1.9.1 run on ecoinvent 3.13 still showed the Ecological Scarcity 2021 "biotic
resources" deviation.

## The benchmark against ecoinvent 3.13

ecoinvent 3.13 (cut-off), 100 datasets, 46 method families, 614 impact categories, 61,400 results. Runs with 1.9.0
and 1.9.1 gave identical values. In 612 categories every result is within 0.1 % of ecoinvent's value, and the largest
deviation is 0.019 %. Ecological Scarcity 2021 "biotic resources" is not validated: 90 of 100 results differ. All of
them are smaller than 1e-5 of the category's largest result, and most have the opposite sign to ecoinvent's. The
reports per method are in docs/benchmarks.

## New

- Every deviating result is checked for numerical resolution: Cyclia computes it in three independent ways and
  reports whether the solver determines it to 0.1 %.
- The benchmark workbook lists the five largest contributions to each deviating result (dataset, exchange, factor),
  and the negative exchanges of the category's flows.

## Fixed

- The inventory comparison called a gap an import or linking difference even when the flows it listed differed only
  below its own precision. It now says so.
- The explanation published with 1.9.1 for the biotic resources deviation ("cancelling contributions") was not
  supported by the 1.9.1 run and is withdrawn.

## Download

Windows: `Cyclia-Setup-1.9.2.exe` · macOS: `.dmg` · Linux: `.AppImage` or `.deb`.

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.9.2)
[Computer software]. https://doi.org/10.5281/zenodo.23853747
