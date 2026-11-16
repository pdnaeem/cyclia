# Cyclia 1.8.4

A numerical integrity release; the results of valid data are unchanged.

## Fixed

- Infinite or NaN numbers are refused wherever they can be entered or imported. This covers site-specific and
  imported characterisation factors, fixed EPD values, parameters and their uncertainty, scenario values,
  background scenarios, and the inputs of optimisation and sweeps.
- A change to an inventory line is saved completely or not at all.
- If data stored earlier contains such a number, the calculation names the dataset or category instead of showing
  NaN. Monte Carlo runs are checked the same way.

## Download

Windows: `Cyclia-Setup-1.8.4.exe` · macOS: `.dmg` · Linux: `.AppImage` or `.deb`.
Installed copies of Cyclia update themselves.

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.8.4)
[Computer software]. https://doi.org/10.5281/zenodo.23853747
