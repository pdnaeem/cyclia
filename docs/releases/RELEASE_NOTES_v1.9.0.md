# Cyclia 1.9.0

The first release on the road to Cyclia 2.0. Results of valid data are unchanged: the 1.8.4 engine reproduces the
new regression snapshot bit for bit.

## What is new

- **Full-library regression.** Toolbox > Validation > Full-library regression records the score of every dataset
  in your libraries under every impact category, the result of every model and the factor matching of every
  category. After an update or a re-import, Compare lists every value that changed. Cyclia's own reference
  libraries are checked this way on every change.
- **Benchmark reports.** Toolbox > Validation > Publish benchmark reports writes one report per method family
  (ReCiPe, CML-IA, IPCC, EF) from your ecoinvent benchmarks. The reports hold deviation statistics only, never an
  ecoinvent value, so they can be shared.
- **Scientific release gate.** Installers are built only when the whole test suite passes with Brightway installed
  (a skipped comparison counts as a failure), together with the regression, the 35 validation systems and the IPCC
  2021 check.

## Fixed

- A yes/no value sent in place of a number was read as 1 or 0. For example, a request for model `true` calculated
  model 1. Every number is now read by one validator. Yes/no values, NaN, infinity, text, and fractions where a whole
  number is needed are refused.
- Importers (ecoSpold, SimaPro CSV, ILCD, openLCA JSON-LD) used to replace a number they could not read without a
  word. They now list how many values could not be used, with examples.

## Download

Windows: `Cyclia-Setup-1.9.0.exe` · macOS: `.dmg` · Linux: `.AppImage` or `.deb`.
Installed copies of Cyclia update themselves.

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.9.0)
[Computer software]. https://doi.org/10.5281/zenodo.23853747
