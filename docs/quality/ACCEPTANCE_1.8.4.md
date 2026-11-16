# Cyclia 1.8.4: numerical integrity on every path

This record covers the findings of the audit of 1.8.3, and a review of every other path by which a number reaches
the calculation. Each finding was reproduced, corrected and covered by regression tests in `tests/test_v184.py`.
With Brightway installed, all 367 automated tests pass; without it, 363 pass and the four Brightway tests are
skipped. The validation suite (35 of 35) and the IPCC 2021 check pass. Results of valid data are unchanged.

| Finding (audit of 1.8.3) | Result |
|---|---|
| P1 A. Infinite site-specific factor stored; impact became NaN | Corrected when saved and when calculated |
| P1 B. NaN fixed EPD value accepted by the storage layer | Corrected when saved and when calculated |
| P1 C. Infinite parameter value, distribution GSD and scenario override accepted | Corrected, with distribution type, scenario years and shares |
| P2 D. A line change partly applied; transaction left open | Corrected: checked first, written in one transaction, rolled back on failure |
| 6. Detection of non-finite results | Guards on matrices, factors, fixed values, totals, line contributions and Monte Carlo runs |
| Further paths found in the review | LCIA table import, background scenario rules, optimisation of choices, parameter sweeps and optimisation, scenario year, latitude and longitude, confidence level, circularity inputs |

## Tests

**A. Site-specific factor.**
- ∞, −∞, NaN, "1e309", "nan" and "inf" are refused when saved, and 2.5 is accepted.
- A factor set to ∞ directly in the database makes the calculation stop with an error instead of reporting NaN.

**B. Fixed EPD values.**
- The same six values are refused when a line is added, and NaN when a line is changed.
- A line of 2 units at 3 gives 1.001 + 6.
- NaN written directly into the stored line stops the calculation.

**C. Parameters and scenarios.**
- **Parameters.** These are refused:
  - value ∞ and "nan";
  - lognormal GSD ∞ and "nan", and normal standard deviation ∞;
  - triangular maximum ∞, and uniform minimum −∞;
  - uncertainty types 9 and "x".
- **Scenarios.** The six invalid values are refused as scenario values.
- **Background scenarios.** These are refused:
  - rule factors ∞ and "nan", a yearly factor ∞, and a factor year 2030.5;
  - a NaN supplier share;
  - an infinite exchange amount of a scenario file;
  - base years ∞, "nan" and 1 000 000.

**D. Atomic line change.** Amount 5 with year ∞ is refused, and the amount stays as before. A later valid change
writes only its own field, and no transaction stays open.

**E. Library data.**
- A NaN technosphere amount stops the calculation, naming "tap water"; so does an infinite elementary amount.
- An LCIA table row with ∞ is refused when imported.
- A NaN (stored as NULL) factor stops the calculation, naming the category.

**F. Optimisation and sweeps.** The following are refused:
- an alternative with an infinite amount;
- a NaN cost per unit;
- a NaN limit;
- a sweep bound of ∞.

**G. Last guards.**
- A NaN total, or an infinite line contribution, is never reported.
- Monte Carlo statistics refuse a run with NaN, and 1, 2, 3 still give a mean of 2.

## Not done here, with the reason

The fresh ecoinvent benchmark on the current release and the ReCiPe, CML-IA and IPCC comparisons with ecoinvent's
LCIA results need the ecoinvent licence. The tool and the Benchmark Centre are ready; see ACCEPTANCE_1.8.3.md. The
four Brightway comparisons run in the continuous integration, where Brightway is installed from pinned commits.
