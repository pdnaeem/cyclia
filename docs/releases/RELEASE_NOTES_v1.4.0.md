# Cyclia 1.4.0

## What is in this release

This release brings together 1.3.8, 1.3.9 and 1.3.10 (see their notes) and is the first of them that builds on
Windows, macOS and Linux.

- Land use now agrees with ecoinvent: very small scaling factors (the infrastructure share of a supply chain) are no
  longer set to zero.
- Inventory check against ecoinvent's cumulative LCI: the benchmark measures whether a deviation comes from the
  inventory or from the factors.
- Database integrity: non-finite values rejected, explicit openLCA providers kept, Database Check per database,
  explorer paging and export, streaming imports, import integrity report.

## Fixed

- The macOS build of 1.3.10 failed: an EPD of the demo was blocked ("the module table does not add up to the LCA
  result") by round-off of about 1e-17 in categories that are zero. Datasets outside the supply chain now get exactly
  zero, and the EPD check compares the gap with the size of the contributions.

## Please check

Run "Validate only" again with "Compare inventories too". Land use should agree like the other categories.

## Download

Windows: `Cyclia-Setup-1.4.0.exe` · macOS: `.dmg` · Linux: `.AppImage` or `.deb`.
Installed copies of Cyclia update themselves.

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.4.0)
[Computer software]. https://doi.org/10.5281/zenodo.23853747
