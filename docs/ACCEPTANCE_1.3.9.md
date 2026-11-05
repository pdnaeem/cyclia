# Cyclia 1.3.9: cause of the land use deviation in the ecoinvent benchmark

## The finding

The 1.3.6 benchmark against ecoinvent's cumulative LCIA results:
- 96.2 % of 2,500 results agreed within 0.1 %.
- Land use did not: 30 % of results within 0.1 %, maximum 14 %, and Cyclia was lower in 92 of 100 datasets.

The hint blamed "3,247 flows used by the database without a factor". That number is not evidence:
- Climate change has 3,270 such flows and agrees to 100 %.
- The Diagnosis sheet found no land flow for which the factor file has a factor that Cyclia missed.
- The factors came from ecoinvent's own LCIA implementation file, which the installer downloads.

That leaves two possible causes:
1. Cyclia's cumulative inventory of land flows differs from ecoinvent's (import or linking).
2. ecoinvent's published results use land use factors that are not in its LCIA implementation file. Candidates are
   the uncharacterised flows "Occupation, lake, artificial", river, seabed and inland waterbody.

## What 1.3.9 adds

- **Code**:
  - `engine/lci_check.py`;
  - `trust.benchmark_ecoinvent(..., lci_path)`;
  - `ecoinvent_login.download_cumulative_lci`;
  - the option "Compare inventories too" (setup > ecoinvent), and the optional LCI file in the manual benchmark.
- **What it does**: ecoinvent's cumulative LCI gives ecoinvent's inventory of each compared dataset. The gap
  r_e − Cg is split into:
  - a factor part, r_e − C·g_e;
  - an inventory part, C·(g_e − g).

  Both parts are measured (METHODS 15.5).
- **Report**: the sheet "Cause of deviations" holds the cause per category, the flows that carry the inventory part,
  the factors implied for flows without a factor, and the per-dataset split. The sheet "Inventory check" lists the
  flows whose cumulative amounts differ and the LCI columns that match no Cyclia flow.
- **Reader**: the workbook is streamed. Rows of datasets that are not compared are rejected after their first ten
  cells. Measured on a synthetic 9-million-cell workbook: 13 s, 97 MB peak memory.

## Tests

Tests are in `engine/tests/test_features.py`. All 199 pass.

- **Factor cause**: one factor (zinc, freshwater ecotoxicity) is removed from Cyclia, and both inventories are
  equal.
  - The category's cause is "factors" with a factor part of 100 %.
  - The removed factor is recovered from ecoinvent's results to 0.1 %.
  - Resources written with the opposite sign are detected and converted.
  - In the other categories, ecoinvent's inventory with Cyclia's factors reproduces the results.
- **Inventory cause**: ecoinvent's inventory has 20 % more of the most important climate flow, and the results are
  consistent with that inventory.
  - The cause is "inventory" with an inventory part of 100 %.
  - The flow is named, with the ratio 1.2.
- **Reader**: only the wanted rows are kept, every data row is counted, and every flow column is read.

## Result of the user's run (fixed in 1.3.10)

The inventory check on the real ecoinvent files:
- 100 datasets were compared, and 3,352 of 3,354 flow columns matched Cyclia's flows.
- For land use, the cause was 100 % inventory and 0 % factors. ecoinvent's inventory with Cyclia's factors reproduced
  ecoinvent's results in 100 % of the cases.
- The flows that differ point to infrastructure: industrial area, mineral extraction, seabed infrastructure, and
  drilling emissions to the ocean.

The cause was the cut-off of small scaling factors in the solve. It is removed in 1.3.10 (METHODS 15.6, test
`TestSmallScalingFactors`).

## Not done

- The run against the real ecoinvent files. It needs the user's licence: "Validate only" with "Compare inventories
  too".
- The column layout of ecoinvent's cumulative LCI workbook was not available here. The reader uses the same header
  logic as the LCIA workbook: labels above or below, merged cells, flows matched by UUID or by name and
  compartment. If the layout differs, the inventory check reports an error, and the LCIA comparison is still
  complete.
- No land use factor is added to Cyclia. If the cause is factors, they must come from the method's source.
