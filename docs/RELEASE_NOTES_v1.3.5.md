# Cyclia 1.3.5

Cyclia 1.3.5 adds the features an independent audit asked for in its review of the 1.3.4 roadmap. Each one comes
with its own code, tests, demonstration data and acceptance criteria (`docs/ACCEPTANCE_1.3.5.md`).

## What is new

- **Factor matching validation** (Toolbox > Validation). Compare Cyclia's characterisation factors, flow by flow,
  with an openLCA JSON-LD export, a Brightway export or a CSV. Cyclia shows which flows differ and which are
  characterised by only one tool, and what each difference does to the results of your models. Add the other
  tool's results to see how much of the difference comes from the factors. Try it with the files in
  `docs/examples`.
- **EPD programme layouts** (step 6). Choose the International EPD System, IBU or INIES FDES, and the Word EPD
  follows that programme's sections, fields and statements. The checklist adds the programme's requirements.
  These layouts are drafts built from published EPDs and are not approved by the programme operators. You can
  also export a layout, change it and load your own.
- **Data quality of EF datasets.** The TeR, GeR, TiR and P ratings of ILCD and EF datasets are read on import and
  used in the data quality of your results.
- **Marginal suppliers** for consequential studies (Toolbox > Background scenarios). Cyclia marks suppliers that
  are likely constrained (recycled, by-product, waste-based) and proposes one per market. You confirm the
  choices, and Cyclia makes a consequential scenario from them.
- **Life cycle costing** with cost types, replacement intervals and a study period.
- **AWARE water scarcity and LANCA land use** (Toolbox > Regional methods). Both are calculated per process at its
  own location, with a completeness report. Import the official factor tables; the demo factors only show the
  workflow.
- **Social LCA screening** (Toolbox > Social LCA). Worker hours and risk hours per stakeholder along the supply
  chain, with the processes that cause them. Import your PSILCA, SOCA or own data.
- **Material flows** (Toolbox > Material flows). Dynamic material flow analysis with stocks, lifetimes and
  recycling loops, checked for mass balance every year, plus the Material Circularity Indicator.
- **Grouped results tabs**: the main analyses in front, the rest under "More analyses".

## Fixed

- The macOS installer was not built for 1.3.4: the independent cross-check, which runs before every build,
  reported round-off of a result close to zero as a difference. This is fixed, so the macOS version is available
  again.

## What 1.3.5 does not do

- It ships no AWARE, LANCA, PSILCA or SOCA data, because these must come from their owners.
- IMPACT World+, official USEtox 2 factors, biodiversity, multi-user projects and dynamic characterisation beyond
  climate are not implemented.
- The factor matching validation has not yet been run on a real openLCA or Brightway installation; the
  published comparison will follow.
- The land use difference from ecoinvent's results (up to 5 % for some datasets) is still being investigated.

## Download

| System | File |
|---|---|
| Windows 10/11 | `Cyclia-Setup-1.3.5.exe` |
| macOS (Apple silicon: M1 or later) | `Cyclia-1.3.5-arm64.dmg` |
| Linux | `Cyclia-1.3.5.AppImage` or `Cyclia-1.3.5.deb` |

Copies of Cyclia 1.3.0 or later on Windows and Linux (AppImage) update themselves. Copies of 1.2.x need to
install this version once by hand.

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.3.5)
[Computer software]. https://doi.org/10.5281/zenodo.23853747

Created by Naeem Ur Rehman. If Cyclia helps your work, you can support it via [PayPal](https://paypal.me/pdnaeem) or [Revolut](https://revolut.me/pdnaeem).
