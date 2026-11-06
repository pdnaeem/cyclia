# Cyclia 1.7.0: advanced environmental LCA, first part

This record lists what was done for the 1.7.0 plan, how it was tested, and what remains with the reason. With
Brightway installed, all 305 automated tests pass. Without it, 301 pass and the four Brightway tests are skipped.
The validation suite (35 of 35) and the IPCC 2021 check pass.

| Item | Result |
|---|---|
| Enhanced LCC (ISO 15686-5) | Done: residual value, escalation per cost type, price uncertainty, ISO categories |
| MFA integrated with LCA | Done: virgin input, recycling, losses, credits with substitution, gross and net |
| Full social LCA | Type I subcategory assessment done; Type II impact pathways open |
| Allocation comparison of a model | Done |
| AWARE 2.0, LANCA, USEtox 2 complete | Package structure checks done; declaring them complete needs the official packages and their reference results, which are not available to the project |
| Advanced regionalisation | Open |
| Validation evidence and review checklist in the report | Done |
| openLCA comparison | Open: needs openLCA 2; its engine cannot be built here (its dependencies are not reachable) |
| ReCiPe, CML, EF 3.1 benchmarks | Need the ecoinvent licence; the tool is ready and the Benchmark Centre shows "Not run" |

## Life cycle costing

**Tests (hand calculation, `tests/test_lcc_advanced.py`)**
- Bought in years 0, 10 and 20 of a 25-year period: 300. The last item still has 5 of its 10 years, so a residual
  value of −50 is credited; the total is 250.
- With a 3 % discount rate and 2 % escalation for maintenance:
  - net present cost Σ 100 × 1.02^y / 1.03^y − 100 × 1.02^20 × 0.5 / 1.03^25;
  - undiscounted cost escalated in the same way.
- With the residual value switched off: 300.
- Price uncertainty GSD 1.5: median 100, and 2.5 and 97.5 percentiles of 100 × 1.5^(∓1.96), within the sampling
  error.

**Changed behaviour.** The 1.3.5 test expected 350 for a 60-year study with 25-year replacements (years 0, 25, 50).
It now expects 290, because the last replacement has 15 of its 25 years left: −60. The earlier figure is
reproduced with the residual value switched off, and is tested.

## MFA integrated with LCA

**Test (`tests/test_v137.py`).** The aluminium example has:
- production charged on its virgin input;
- recycling charged at 0.1 × the dataset impact per unit of its throughput;
- a credit for the recovered material with substitution 0.8.

In year 15, every part equals the MFA quantity × factor × unit impact. The virgin input equals the production
input minus the recycled input, and is below the throughput. The net total is the sum of the parts. A virgin-input
basis on a process that is not the production process is refused, and so is a substitution ratio above 1.

## Social LCA, Type I

**Tests (`tests/test_slca_type1.py`)**
- Fair salary has a spinning mill (3 worker hours, score +1, site-specific data) and a sewing factory (1 hour, −2,
  generic data):
  - score (3 × 1 + 1 × −2) / 4 = 0.25;
  - coverage 4 of 8 hours = 50 %, site-specific share 75 %;
  - the sewing factory is a hotspot.
- Working hours has two indicators of one factory (0 and −1): −0.5, one organisation.
- Child labour is listed as missing; the excluded "Ethical treatment of animals" is not.
- Rejected:
  - an unknown subcategory or stakeholder;
  - a score of 3 or 1.5;
  - a weight of zero;
  - an unknown data type;
  - an empty performance reference point.
- Mixed weight units give a warning.

## Allocation choices of a model

**Test.** A cheese model (1 kg cheese, 2 kg whey, prices 3 and 1, 10 kg CO2):
- mass 10/3, economic 7.5 and no allocation 10;
- the economic value equals a full calculation with the economic basis saved;
- energy is unavailable without its values.

## Factor package checks

**Test.** An AWARE table with FR and ES and no source is "Package incomplete", for three reasons:
- there is no GLO fallback;
- ES lacks one of the three uses;
- the package is not named.

With GLO and a named source it is "Package checked". The Benchmark Centre shows it with the note that the values
are not compared with the package's reference results.

## Interface check

In the browser, on the demo project:
- the price escalation was saved and read back;
- a Type I assessment was added and the scope saved, and the result table appeared;
- the MFA link table shows the extra credit row for the recycling process;
- the Benchmark Centre lists its checks.

The allocation comparison button sits in the allocation section, which appears when a model has co-products.
