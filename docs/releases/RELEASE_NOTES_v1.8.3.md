# Cyclia 1.8.3

A safeguards release; the results are unchanged.

## Fixed

- Every number of the goal and scope and of the model lines must be finite and in range: the study period, discount
  and escalation rates, allocation shares, co-product values, years and replacement intervals. A study period
  written as 1e309 could make the life cycle cost run without end.
- Material flow analysis refuses fractional years such as 2020.5 instead of cutting them to whole years.

## Changed

- A functional unit amount of 0 is refused (it used to be read as 1).

## Download

Windows: `Cyclia-Setup-1.8.3.exe` · macOS: `.dmg` · Linux: `.AppImage` or `.deb`.
Installed copies of Cyclia update themselves.

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.8.3)
[Computer software]. https://doi.org/10.5281/zenodo.23853747
