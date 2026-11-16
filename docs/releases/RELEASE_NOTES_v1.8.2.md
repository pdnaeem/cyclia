# Cyclia 1.8.2

A reliability release: the life cycle assessment results are unchanged.

## Fixed

- **Costs inside sub-models.** Replacements, price escalation, residual value and price uncertainty of priced lines
  inside sub-models are now counted, at every level. Before, a sub-model's prices counted once. The results list each
  priced line inside sub-models.
- **Material flows.** Negative, infinite or missing inflows are refused. Before, a negative inflow could hide a mass
  balance error.
- **Social assessment.** Weights must be finite numbers on one activity variable (hours and minutes are
  converted). A subcategory that mixes variables shows "No score" with the reason, instead of an average across
  units.
- Supplier responses leave one entry in the process history. ecoinvent results files with long sheet names are
  read correctly.

## Changed

- Life cycle costs of models with priced, replaced or escalated lines inside sub-models now include them.

## Download

Windows: `Cyclia-Setup-1.8.2.exe` · macOS: `.dmg` · Linux: `.AppImage` or `.deb`.
Installed copies of Cyclia update themselves.

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.8.2)
[Computer software]. https://doi.org/10.5281/zenodo.23853747
