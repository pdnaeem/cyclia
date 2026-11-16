# Cyclia 1.9.1

Corrections from the audit of 1.9.0, and the first published benchmark of ReCiPe, CML-IA and IPCC against ecoinvent.
Results of valid data are unchanged.

## Published benchmark against ecoinvent 3.13

Cyclia was compared with ecoinvent's own cumulative LCIA results for ecoinvent 3.13 (cut-off): 100 datasets,
46 method families, 614 impact categories, 61,400 results. In 612 categories every result is within 0.1 % of
ecoinvent's value, and the largest deviation is 0.019 %. This covers ReCiPe 2016, CML-IA, IPCC 2013 and 2021,
EF 3.0 and 3.1, TRACI, USEtox, IMPACT World+ and others.

Ecological Scarcity 2021 "biotic resources" is not validated. Its deviating results are very small and mostly of
opposite sign, which points to cancelling contributions; 1.9.1 adds the test that settles this. The reports per
method are in docs/benchmarks.

## Fixed

- LCIA imports accepted a yes/no factor in ecoinvent's LCIA workbook (read as 1). Normalisation, weighting and
  mapping conversion factors of 1e309 were saved as infinity. All of these are now refused with the row named.
- A yes/no value sent as the identifier of a parameter, a scenario or a model was read as 1. Every identifier is now
  checked by the storage layer itself, whoever sends it.
- The ecoinvent benchmark pooled the statistics of methods with the same category names (for example the seven
  "climate change / GWP100" methods). Each method now has its own.

## New

- The benchmark recognises results that are the tiny remainder of contributions that cancel, and compares them
  within the round-off of those contributions.
- Benchmark reports can be written from a benchmark workbook saved earlier.

## Download

Windows: `Cyclia-Setup-1.9.1.exe` · macOS: `.dmg` · Linux: `.AppImage` or `.deb`.
Installed copies of Cyclia update themselves.

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.9.1)
[Computer software]. https://doi.org/10.5281/zenodo.23853747
