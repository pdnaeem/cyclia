# Cyclia 1.3.3

Cyclia 1.3.3 corrects the scientific issues found in an independent expert audit of version 1.3.2. Please
update and recalculate studies that use nested models, Monte Carlo, comparisons, data quality ratings or EPDs.

## Corrected

- **Uncertainty of nested models.** Monte Carlo and Sobol analysis now include every line of every model used
  inside your model, with its own data quality, and their parameter distributions and correlations. Before,
  only the top level was uncertain, so the spread of complex supply chains was too small.
- **Correlations** are now the Spearman rank correlations you enter.
- **Comparisons** are checked before results are shown: different functional units block the comparison, and
  other differences are listed. Without a functional equivalence statement the result is a screening
  comparison, not a comparative assertion. Significance comes from the comparative Monte Carlo, not a fixed 10 %
  rule.
- **Data quality**: credits are left out of the weights, nested models count, and the pedigree-based value is
  called a pedigree indicator. Enter PEF scores per line for a real PEF DQR.
- **Improvement advice** no longer suggests reducing a credit, and different hotspots are no longer called
  burden shifting.
- **EPD**: lines outside the EN 15804 modules block the EPD, A1-A3 is not declared without lines, the module
  table is reconciled with the LCA result, and the service life check is fixed.
- **Data age**: 5 years for producer-specific data, 10 years for other data.
- **Database migration** includes nested models and can be undone at once.
- **Report centre** checks every ISO 14044 report item separately.

Thank you to the reviewer whose audit made these corrections possible.

## Download

| System | File |
|---|---|
| Windows 10/11 | `Cyclia-Setup-1.3.3.exe` |
| macOS (Apple silicon: M1 or later) | `Cyclia-1.3.3-arm64.dmg` |
| Linux | `Cyclia-1.3.3.AppImage` or `Cyclia-1.3.3.deb` |

Copies of Cyclia 1.3.0 or later on Windows and Linux (AppImage) update themselves. Copies of 1.2.x need to
install this version once by hand.

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.3.3)
[Computer software]. https://doi.org/10.5281/zenodo.23853747

Created by Naeem Ur Rehman. If Cyclia helps your work, you can support it via [PayPal](https://paypal.me/pdnaeem) or [Revolut](https://revolut.me/pdnaeem).
