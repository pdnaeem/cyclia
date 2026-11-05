# Cyclia 1.3.8

Database integrity release, from the third database audit (of 1.3.6).

## Fixed

- An unresolved input with an amount of Infinity or NaN (for example 1e309 in an openLCA file) was accepted. The
  import check now rejects non-finite amounts of unresolved inputs, non-finite uncertainty parameters, unknown
  uncertainty types, zero or non-finite production and links to missing datasets or flows. The import stops and the
  library is unchanged.
- An openLCA input whose defaultProvider was not in the import was linked to another producer of the same product.
  It now stays unresolved and shows the provider named in the file. If that provider is in another database of your
  library, it is the first suggestion under "Link missing suppliers".
- The Database Check of one database counted the flows of the whole library (a database with one flow that has a
  factor showed 50 % coverage). Flow coverage, units and LCIA compatibility now use the selected database only.
- The Database Explorer's "only datasets with unresolved inputs" missed datasets beyond the first 100 results.

## What is new

- Database Explorer: paging, filters for location, system model, version and elementary flow, and "Export selected
  (Excel)".
- Large imports use much less memory: SimaPro CSV is read one process at a time and exchanges are written in
  batches. A synthetic SimaPro file of 200,000 processes needed 1,117 MB in 1.3.7 and 360 MB in 1.3.8.
- After an import, an integrity report lists what was imported, what was checked and the matrix residual.

## Download

Windows: `Cyclia-Setup-1.3.8.exe` · macOS: `.dmg` · Linux: `.AppImage` or `.deb`.
Installed copies of Cyclia update themselves.

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.3.8)
[Computer software]. https://doi.org/10.5281/zenodo.23853747
