# Cyclia 1.8.0

## What is new

- **Ask your suppliers for data.** Cyclia writes an Excel file with the lines of your process. The supplier fills
  it in. You see every change before it is applied, and the supplier and date become the source of each value.
- **Critical review between two computers.** The reviewer comments and you answer. You exchange review files, and
  each side merges the other's, so nothing is lost or counted twice. The review closes when nothing critical is
  left, and the report shows the statement and every comment.
- **Optimise choices.** Give alternative materials, suppliers or energy sources for some lines. Cyclia finds the
  best combination within your limits and the trade-offs between categories (and costs), and saves any
  combination as a model.
- **Sensitivity with your own parameters.** The Sobol indices now include the uncertain parameters of your own
  data.
- **Regional factors.** A process in a region takes its country's factor when the method has no factor for the
  region, and the results show how much of each regionalised result used the exact location, the country or the
  generic factor.

## Changed

- With regionalised factors, processes at a sub-national location now use their country's factor where one exists
  instead of the generic factor.

## Fixed

- macOS installer builds no longer hang for hours when the disk image tool gets stuck.

## Download

Windows: `Cyclia-Setup-1.8.0.exe` · macOS: `.dmg` · Linux: `.AppImage` or `.deb`.
Installed copies of Cyclia update themselves.

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.8.0)
[Computer software]. https://doi.org/10.5281/zenodo.23853747
