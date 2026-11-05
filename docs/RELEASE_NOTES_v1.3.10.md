# Cyclia 1.3.10

## Fixed

- Land use (and, much less, a few other categories) was lower than ecoinvent's results: up to 14 %, median 0.4 %.
  Cause: the calculation set very small scaling factors to zero. These are the shares of infrastructure such as
  buildings, mines and platforms, which carry most land transformation. They are now kept.
- Found with the inventory check of 1.3.9: Cyclia's factors times ecoinvent's own cumulative inventory gave
  ecoinvent's results exactly, so the factors were right and the inventory was short.

## Please check

Run "Validate only" again (with "Compare inventories too"). Land use should now agree like the other categories.

## Download

Windows: `Cyclia-Setup-1.3.10.exe` · macOS: `.dmg` · Linux: `.AppImage` or `.deb`.
Installed copies of Cyclia update themselves.

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.3.10)
[Computer software]. https://doi.org/10.5281/zenodo.23853747
