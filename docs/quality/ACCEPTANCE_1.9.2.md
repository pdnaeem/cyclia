# Cyclia 1.9.2: acceptance record

The suite has 415 automated tests. Here, without Brightway, 411 pass and the four Brightway comparisons are skipped.
The regression snapshot, the validation suite (35 of 35) and the IPCC check pass.

## What the 1.9.1 run showed

The run used ecoinvent 3.13 cut-off, 100 datasets and 614 categories. Its values are identical to the 1.9.0 run.

In Ecological Scarcity 2021 "biotic resources", with and without long-term emissions, 90 of 100 results deviate:
- the round-off rule of 1.9.1 applied to none of them: "Results within round-off" is 0;
- the new column "Sum of absolute contributions" shows Cyclia's sum of absolute contributions to be at most 81 times
  its net result (for most datasets about 1.0 to 1.3 times), while the rule needs a ratio near 1e9. Cyclia's values
  are therefore not remainders of cancelling contributions in Cyclia's own calculation. The explanation published
  with 1.9.1 is withdrawn;
- ecoinvent's cumulative LCI with Cyclia's factors reproduces ecoinvent's results to 1e-28, so the gap lies in the
  cumulative amounts of "Fish, demersal, in ocean" and "Fish, pelagic, in ocean";
- the inventory comparison found no dataset in which these amounts differ beyond its precision (1e-12 of the largest
  amount in the dataset's inventory). Its cause text still said "an import or linking difference to fix in Cyclia",
  which its own data did not support.

## Changes

1. **Numerical resolution** (trust.resolution_check).
   - For every deviating result: the adjoint solve (A^T y = q^T, one per category) and one step of iterative
     refinement of the scaling vector.
   - A spread above 0.1 % of the result means the solver does not determine it. With both values below 1e-6 of the
     category's largest value in ecoinvent's file, the result is "below numerical resolution", left out of the
     statistics and counted ("Results below numerical resolution" per category, and in the verdict). Otherwise it
     stays a deviation with the three values.
   - Tests (test_v192):
     - a resolved deviation keeps its deviation;
     - an unresolved, negligible one leaves the statistics;
     - an unresolved one that is not negligible stays;
     - the statistics count the unresolved apart and the verdict names them.
2. **Contributions** of every deviating result: the five largest q_i x_i with the dataset, its scaling, the exchange
   and the factor (sheet Contributions).
3. **Negative exchanges** of the flows of each category that still deviates (sheet Negative exchanges). A flow
   returned to nature can be recorded as a negative amount, and programs can read that differently.
   - Test (test_features): a sign flipped in one exchange shows up in the deviating results' contributions and in
     the list of negative exchanges, and both sheets are in the workbook.
4. **Cause text.** When every flow carrying the inventory part differs only below the comparison's precision, the
   cause says so with the size of the gap, and no longer claims an import or linking difference.
5. **Published reports** in docs/benchmarks are written from the 1.9.1 run. The note on biotic resources gives only
   measured facts, and the category stays not validated.

## Open

The cause of the biotic resources deviation is not known yet. The next run with 1.9.2 settles one of two cases:
- **the solver does not resolve these results:** they are reported as below numerical resolution and counted
  apart;
- **the solver resolves them:** the Contributions and Negative exchanges sheets name the datasets and exchanges that
  carry Cyclia's values. Those exchanges can then be checked against ecoinvent's datasets.

An independent check is also possible now. The Brightway comparison in the Validation tab calculates the same
datasets with Brightway on the same imported database, and shows whether a second program agrees with Cyclia or
with ecoinvent.
