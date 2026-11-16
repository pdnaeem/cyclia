# Cyclia 1.8.3: numerical safeguards

This record covers the findings of the audit of 1.8.2. Each finding was reproduced, corrected and covered by
regression tests. With Brightway installed, all 356 automated tests pass; without it, 352 pass and the four
Brightway tests are skipped. The validation suite (35 of 35) and the IPCC 2021 check pass, and the results are
unchanged.

| Finding (audit of 1.8.2) | Result |
|---|---|
| P1 A. Non-finite study period, discount rate, escalation and model amount accepted; possible endless loop | Corrected: every scope number, line number and the functional unit amount checked when saved; the cost checks stored values again and caps purchases |
| P2 B. MFA fractional years silently truncated | Corrected: calendar years must be whole numbers |
| Nested LCC regression tests | Two more: allocation share with two levels of sub-models; replacement interval longer than the period |
| Fresh ecoinvent EF 3.1 benchmark; ReCiPe, CML and IPCC benchmarks against ecoinvent | Not run here: they need the ecoinvent licence (see below) |

## A. Finite numbers in the goal and scope, the lines and the functional unit

**Cause.**
- The JSON reader of the engine refuses the words NaN and Infinity, but `1e309` becomes infinity.
- `save_model` checked only that the amount was positive and the allocation share in range; `update_input` and
  `add_input` converted numbers without checks.
- In the life cycle cost, an infinite period with a replacement interval would never leave the purchase loop. The
  audit did not run that loop, and neither did these tests; they show that it is now refused before it starts.

**Correction.**
- `store.check_scope_numbers` checks:
  - the allocation share, above 0 and up to 100 %;
  - the study period, 0 to 1000 years;
  - the discount rate, above −100 % and up to 1000 %;
  - each escalation rate, above −100 %;
  - the main product and co-product masses, prices, energy contents and physical properties, zero or more;
  - latitude (−90 to 90) and longitude (−180 to 180).
- `save_model` refuses a functional unit amount that is not finite or not above zero; 0 is no longer read as 1.
- Lines must have finite values:
  - amount and input amount, zero or more;
  - year, 0 to 1000;
  - replacement interval, 0.01 to 1000 years;
  - price uncertainty, 1 or more;
  - data year, 1900 to 2100.
- `analysis.lcc` runs the scope check on the stored scope, checks each line's numbers, and stops a cost item at
  10 000 purchases.

**Tests (`tests/test_v183.py`).**
- **Scope numbers.** Each of these is refused when saving:
  - period ∞ (from `1e309`), NaN, the text "1e309", −5 and 5000;
  - discount rate NaN, −100 and ∞;
  - escalation NaN, ∞, −120, and an escalation given as text instead of per cost type;
  - allocation share ∞ and 0;
  - main mass NaN, a co-product mass of ∞ and a negative co-product price;
  - latitude 95 and longitude "x".

  Valid values are stored.
- **Amount of the functional unit.** ∞, NaN, "1e309", 0 and −1 are refused.
- **Lines.** These are refused:
  - an infinite amount when adding;
  - amount ∞ and NaN, input amount −1;
  - year 1e9 and −1;
  - replacement interval 0.001 and ∞;
  - cost NaN, price uncertainty 0.5 and data year 3000.

  A negative cost (revenue) with a valid year and interval is accepted.
- **Stored infinite period.** A scope written directly to the database with an infinite period: the cost
  calculation refuses it within 5 seconds instead of looping.
- **Too many purchases.** A replacement interval of 0.05 years over 1000 years (20 000 purchases) is refused. With
  0.5 years there are 2 000 purchases, and the total is 2 000.

## B. Whole calendar years in MFA

**Cause.** `int()` truncated 2020.5 to 2020.

**Correction.** The first and last year, and the years of inflows, must be whole numbers ("2020", 2020 and 2020.0
are the same year). The following are refused:
- fractional years and infinite years;
- `True` as a year;
- a last year before the first;
- more than 1000 years;
- a single year.

**Tests (`tests/test_v182.py`).**
- [2020.5, 2022.5], [2020, 2030.25], ["2020", "2030.5"], [2020, ∞], [True, 2030], [2030, 2020] and [2020] are
  refused.
- An inflow in "2021.5" is refused.
- The example run with ["2020", 2050.0] gives the same years as with [2020, 2050].

## C. Nested life cycle costing, more regression tests

Tests are in `tests/test_lcc_advanced.py`.
- A grandchild pump replaced every 8 years inside a child bought once, with 50 % allocation to the main product,
  costs 0.5 × (300 − 100 × 4/8) over 20 years. The pump is bought 3 times, and its path is "assembly > child >
  pump".
- A replacement interval of 30 years in a 20-year study costs 100 − 100 × 10/30: one purchase, with 10 of its 30
  years left.

## Not done here, with the reason

- **A fresh EF 3.1 benchmark against ecoinvent on the current release, and ReCiPe 2016, CML-IA and IPCC 2021
  comparisons with ecoinvent's LCIA results.** These need the ecoinvent licence and the cumulative LCIA files,
  which are not available in the development environment.

  The tool runs every installed method family (Toolbox > Validation > Benchmark against ecoinvent), and the
  Benchmark Centre records each run with its date and version. Until such a run is recorded, the website and the
  feature status state that the published benchmark was run with Cyclia 1.3.10.

  The IPCC 2021 GWP100 factors are checked on every release against the AR6 values (Benchmark Centre, "IPCC
  2021").
