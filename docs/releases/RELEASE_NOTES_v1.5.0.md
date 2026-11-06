# Cyclia 1.5.0

Stage P0 of the development plan: scientific correctness and reliability.

## What is new

- **Compare with Brightway** (Toolbox > Validation). Brightway's calculation library calculates the datasets of
  any installed database, ecoinvent included, and every result is compared with Cyclia's. The report can be saved
  as Excel. Nothing leaves your computer.
- **Clearer comparisons.** The comparative Monte Carlo now concludes per impact category with a chosen confidence
  (90, 95 or 99 %). It takes the sampling error of the probability into account and asks for more iterations
  when the result is not yet certain.
- **Validate every method.** The ecoinvent validation can include ReCiPe 2016, CML-IA, IPCC and every other
  installed method of ecoinvent's results, not only EF 3.1.
- **Material flows.** The collection rate and the recycling efficiency are shown next to the end-of-life
  recycling rate.

## Fixed

- **Social LCA screening.** Waste sent to a treatment process was counted as an avoided product, so its worker
  hours were missing.
- **Material flows.** The end-of-life recycling rate counted production scrap and imported scrap sent to
  recycling.
- **Comparison kit.** Treatment datasets had the opposite sign in the Brightway scripts.

## Please check

Run "Validate only" with "Validate every installed method" ticked and send the report, so that the ReCiPe 2016
and CML-IA results can be published.

## Download

Windows: `Cyclia-Setup-1.5.0.exe` · macOS: `.dmg` · Linux: `.AppImage` or `.deb`.
Installed copies of Cyclia update themselves.

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.5.0)
[Computer software]. https://doi.org/10.5281/zenodo.23853747
