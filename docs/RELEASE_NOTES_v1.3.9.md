# Cyclia 1.3.9

## What is new

- "Validate only" (and "Download, connect and validate") can now also compare inventories: Cyclia downloads
  ecoinvent's cumulative LCI with your login and, for every category that deviates, measures how much of the gap
  comes from the inventory and how much from factors. The report names the cause and the flows behind it.

## Fixed

- The benchmark hint "some elementary flows probably have no factor (3,247 flows ...)" was misleading: the same
  number of flows without a factor occurs in categories that agree exactly. The cause is now measured instead.

## For the land use deviation of the 1.3.6 benchmark

Run "Validate only" again with "Compare inventories too" ticked. The sheet "Cause of deviations" then says whether
Cyclia's land flows differ from ecoinvent's inventory (to be fixed in Cyclia) or ecoinvent's published results use
land use factors that are not in its LCIA implementation file. Please send that report.

## Download

Windows: `Cyclia-Setup-1.3.9.exe` · macOS: `.dmg` · Linux: `.AppImage` or `.deb`.
Installed copies of Cyclia update themselves.

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.3.9)
[Computer software]. https://doi.org/10.5281/zenodo.23853747
