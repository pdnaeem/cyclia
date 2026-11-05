# Cyclia 1.3.4

Cyclia 1.3.4 completes the corrections of an independent audit and adds a second, independent calculation to
check Cyclia's results.

## What is new

- **Independent cross-check** (Toolbox > Validation). Cyclia recalculates your datasets and models with a second
  implementation that rebuilds the matrices and uses a different solver, and shows the difference. On the data
  shipped with Cyclia the two agree to 1e-13. See `docs/CROSS_VALIDATION.md`.
- **Nested models in every check.** Data age, missing years, system models and the modelling approach are now
  checked in every model used inside your model.
- **Complete supply-chain inventory.** Every line of every nested model with its amount per functional unit,
  data type, year, supplier and reference, in the Word report, Excel, the EPD file and the Inventory results tab.
- **Comparisons** compare data quality in every impact category.
- **EPD readiness.** The resource use, waste and output indicators of EN 15804+A2 and the units are checked. A
  draft can always be created, and it says clearly when it is not ready for submission.
- **Physical causality** allocation and an **allocation overview** of the whole project.
- **Land use investigation.** The ecoinvent benchmark now splits land use into occupation and transformation and
  lists flows with missing or conflicting factors, to find the cause of the known land use difference.

## Download

| System | File |
|---|---|
| Windows 10/11 | `Cyclia-Setup-1.3.4.exe` |
| macOS (Apple silicon: M1 or later) | `Cyclia-1.3.4-arm64.dmg` |
| Linux | `Cyclia-1.3.4.AppImage` or `Cyclia-1.3.4.deb` |

Copies of Cyclia 1.3.0 or later on Windows and Linux (AppImage) update themselves. Copies of 1.2.x need to
install this version once by hand.

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.3.4)
[Computer software]. https://doi.org/10.5281/zenodo.23853747

Created by Naeem Ur Rehman. If Cyclia helps your work, you can support it via [PayPal](https://paypal.me/pdnaeem) or [Revolut](https://revolut.me/pdnaeem).
