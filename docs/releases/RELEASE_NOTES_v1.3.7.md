# Cyclia 1.3.7

## What is new

- **ILCD+EPD export** (step 6 > EPD). The EPD as a machine-readable ILCD+EPD dataset with the official EN 15804+A2
  indicator identifiers of the InData network, checked against the official schemas, ready for the EPD Editor and
  ÖKOBAUDAT.
- **PSILCA and SOCA** (Toolbox > Social LCA). Import social data directly from openLCA JSON-LD; PSILCA sectors are
  assigned to your datasets with a mapping table.
- **AWARE monthly and watershed factors** (Toolbox > Regional methods). Monthly factors with a water use profile,
  and the watershed of your site found from its coordinates (GeoJSON polygons).
- **Soil quality index from LANCA**, aggregated from the four LANCA indicators.
- **Material flows**: a visual builder with a diagram you can arrange, and the material system linked to the LCA:
  impacts year by year.
- **Safer imports**: every database is imported into a staging library first and reaches your library only after
  it passes the checks.
- **Comparison kit** (Toolbox > Validation). Export a database you may share, with Cyclia's results and scripts
  for Brightway and openLCA, to publish a comparison of the three tools.

## Not yet

- The Brightway and openLCA comparison itself has to be run with the kit; results will be published in
  docs/CROSS_VALIDATION.md.
- The SQI normalisation references are entered by you; ILCD+EPD 1.3 elements are added in the EPD Editor.

## Download

| System | File |
|---|---|
| Windows 10/11 | `Cyclia-Setup-1.3.7.exe` |
| macOS (Apple silicon: M1 or later) | `Cyclia-1.3.7-arm64.dmg` |
| Linux | `Cyclia-1.3.7.AppImage` or `Cyclia-1.3.7.deb` |

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.3.7)
[Computer software]. https://doi.org/10.5281/zenodo.23853747

Created by Naeem Ur Rehman. If Cyclia helps your work, you can support it via [PayPal](https://paypal.me/pdnaeem) or [Revolut](https://revolut.me/pdnaeem).
