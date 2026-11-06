# Cyclia 1.3.6

Cyclia 1.3.6 is a reliability release. Two independent audits of 1.3.5 and an ecoinvent benchmark found
errors that could change results, mostly in how databases are imported and linked. They are fixed, and each fix
has a test that fails on 1.3.5. Details: `docs/quality/ACCEPTANCE_1.3.6.md`.

## Fixed: please re-import SimaPro, openLCA and ecoSpold databases

- **SimaPro**: two processes with the same product and location were merged into one dataset. They are now kept
  apart.
- **Suppliers are never guessed**: when several datasets produce the same product, Cyclia asks you to choose
  instead of taking the first one (SimaPro, ecoSpold1, ILCD, openLCA).
- **ecoSpold2**: inputs without a supplier link are kept and shown, not left out.
- **Linking missing suppliers** works per location, so each country gets its own supplier.
- **Factor matching validation** no longer passes when flows could not be compared (unresolved flows, wrong
  units, conflicts).
- **AWARE**: evaporated water counts as consumption, the non-agricultural factor is used, and each process of the
  supply chain gets its own type of use. Results change.
- **Social LCA**: coverage is reported honestly (it showed 100 %), and credits no longer reduce the hours of the
  real supply chain.
- **MFA**: the recirculated inflow share uses the production input.
- **LANCA**: units are checked and converted (hectares).
- **EPD**: the toxicity indicators of EF 3.1 are recognised, and the units of the additional indicators are
  checked.
- **ecoinvent benchmark**: the verdict names every category that does not agree.

## New

- **Database check** in six parts: matrix, missing suppliers, flow coverage, units, metadata and LCIA.
- **Database details**: version, system model, licence, release date, and the source file's SHA-256 fingerprint,
  recorded at import.
- **Database explorer** (Toolbox): every dataset with its suppliers, users, flows and gaps.
- **Land use coverage** in every result, with a warning when land flows have no factor.
- **MCI from the MFA**, year by year.

## Download

| System | File |
|---|---|
| Windows 10/11 | `Cyclia-Setup-1.3.6.exe` |
| macOS (Apple silicon: M1 or later) | `Cyclia-1.3.6-arm64.dmg` |
| Linux | `Cyclia-1.3.6.AppImage` or `Cyclia-1.3.6.deb` |

Copies of Cyclia 1.3.0 or later on Windows and Linux (AppImage) update themselves.

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.3.6)
[Computer software]. https://doi.org/10.5281/zenodo.23853747

Created by Naeem Ur Rehman. If Cyclia helps your work, you can support it via [PayPal](https://paypal.me/pdnaeem) or [Revolut](https://revolut.me/pdnaeem).
