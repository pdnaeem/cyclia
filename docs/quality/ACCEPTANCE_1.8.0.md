# Cyclia 1.8.0: professional platform, first part

This record lists what was done for the 1.8.0 plan (released as 1.8.1 with two corrections, see the changelog), how it was tested, and what remains with the reason. With
Brightway installed, all 328 automated tests pass. Without it, 324 pass and the four Brightway tests are skipped.
The validation suite (35 of 35) and the IPCC 2021 check pass.

| Item | Result |
|---|---|
| Supplier data collaboration | Done as Excel data requests with checked responses (file based, no web portal) |
| Collaborative professional review | Done: comments, answers, merged review files, closing rules, report annex (file based, no shared server) |
| Scenario optimisation | Done for discrete choices (datasets, sub-models, costs); continuous parameters were already covered |
| Sobol indices with parameters of custom data | Done (open item of 1.7.0) |
| Advanced regionalisation | First part: country fallback and coverage of regionalised factors |
| Advanced visual process modelling | Diagram editors of 1.6.2 kept; no new editor |
| Multi-user editing on a shared server | Open: Cyclia has no server; data stay on the user's computer |
| Biodiversity | Open: no established method with an official factor set is available |
| Prospective and dynamic LCA beyond climate change | Open: no established dynamic factors outside climate change |
| Social LCA Type II | Open: no consensus characterisation of impact pathways |
| AWARE 2.0, LANCA, USEtox 2 declared complete | Open: needs the official packages and their reference results |
| openLCA comparison, ReCiPe and CML benchmarks | Open: need openLCA 2 and the ecoinvent licence |

## Sobol indices with parameters of custom data

Tests are in `tests/test_custom_data.py`, `TestSobolCustomParameters`.

**Exactness of the update.** A parameter q sets a technosphere amount (q^2 kg of a supplier that emits 2q kg CO2)
and an emission. The low-rank update gives 0.5 + 2 q^3 for q = 0.5, 2 and 3 within 1e-10.

**Indices.** f = L (2 k1 + 3 k2): L is the line's lognormal factor; k1 and k2 are independent lognormal with
GSD 1.5. The estimates are within 0.04 of the analytic S1 and ST at n = 4096. With one shared database parameter,
the shared parameter's indices are within 0.04 of the analytic ones.

## Supplier data requests

Tests are in `tests/test_supplier.py`.

**Request workbook.** It has five sheets. The identification sheet is hidden. The input sheet is protected, with
only the answer cells open. The process sheet states the reference amount. Current values are not shown unless
the user chooses.

**Response on the reference system.** CO2 1.8 kg (measured), the solvent at 12 000 mg (range 8 000 to 15 000).
Not answered or wrong:
- electricity empty;
- waste 'abc';
- avoided electricity in kg.

Reading writes nothing; the result is unchanged. Applying gives:
- 2 changes, 1 unanswered line, 2 errors and 1 extra item;
- a total of 2.51 kg CO2-eq (hand calculation);
- the solvent at 12 000 mg with a triangular distribution;
- the CO2 line keeping its pedigree scores;
- the supplier and the date in each source, the period of the data on the process, primary data, and the earlier
  source kept.

**Other cases**
- A line changed in Cyclia after the request is reported as a conflict and keeps its value.
- A workbook from elsewhere, or with a changed identifier, is refused.
- Range rules are applied, a decimal comma is read, and 0 is accepted.
- A process without lines cannot be requested.

## Collaborative critical review

Tests are in `tests/test_review.py`.

**Round trip.** Two workspaces exchange the project file:
1. The reviewer raises a critical comment on a line and a minor one on a checklist item.
2. The practitioner merges (2 added, same model) and answers; the critical comment becomes answered.
3. Closing is refused, and the practitioner cannot resolve the comment.
4. The reviewer merges (1 added, 1 updated), resolves the comment and closes the review; 1 minor comment is still
   open.
5. The practitioner merges the closure; the statement is current.

Merging the same file again changes nothing. A later change of the model makes the statement refer to an earlier
state.

**Both sides changed.** The later change wins, and the replaced state is in the history. The test uses fixed
clocks. With a clock that returns the same time twice, as Windows clocks can, changes still get increasing times,
and two sides changed at exactly the same time agree after merging both ways.

**Rules.** The following are refused:
- a practitioner raising a comment;
- an unknown severity;
- a line of another model;
- a comment without an author;
- a foreign file.

**Word report.** It has the closing statement, Annex B3 and the answer.

## Optimisation of discrete choices

Tests are in `tests/test_choices.py`. Hand calculation of six combinations:

| Goal | Limit | Expected |
|---|---|---|
| minimise climate change | toxicity at most 10 | 3.5, toxicity 8, cost 5.4 |
| minimise climate change | toxicity no worse than now | 4.5 |
| minimise cost | climate change at most 5 | cost 5.0 |
| Pareto set over climate change and toxicity | | {(2.5, 20), (3.5, 8), (4.5, 2)} |

- The baseline is 9.0, with a cost of 4.0.
- An alternative in grams is converted to kilograms.
- The saved combination recalculates to 3.5 and 8.0, and the original model is unchanged.
- No feasible combination gives no best combination.
- An incompatible unit, and a cost goal without costs, are refused.

## Regionalised factors

Tests are in `tests/test_regional_v180.py`, on the tutorial library. Tap water uses 1 m3 at its location, and the
electricity uses 0.001 m3 elsewhere. Factors are XX = 10 and generic 1.

| Location of tap water | Total | Coverage |
|---|---|---|
| XX | 10.001 | exact 10/10.001 |
| XX-01 | 10.001 | country 10/10.001, one fallback counted |
| YY | 1.001 | all generic, YY listed with its share |

## Changed behaviour

Up to 1.7.0, a process at a sub-national location whose country had a regional factor used the generic factor.
It now uses the country factor. The coverage table shows the share concerned. The existing test of the exact
location is unchanged.

## Interface check

In the browser, on the demo project:
- **Supplier data.** A request was written for the bread example, filled with a script and read back: one change,
  one error, unanswered lines and one extra item. Applying it updated the line, and the request table shows the
  result.
- **Optimise choices.** A line was added as a choice and an alternative found by search. The best combination and
  the Pareto set appeared, and the combination was saved as a model.
- **Review.**
  - The reviewer added a critical comment, and the practitioner answered.
  - Closing was refused while the comment was unresolved, and succeeded after it was resolved.
  - The review file was written.

No page errors. The 1000 px and 1366 px sweeps show no overflow.
