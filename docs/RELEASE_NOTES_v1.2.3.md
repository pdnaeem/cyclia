Cyclia 1.2.3 corrects a matching rule introduced in 1.2.2. Please update.

## What changed

- 1.2.2 applied factors given for the subcompartment "unspecified" to other subcompartments. The benchmark against ecoinvent showed that ecoinvent does not do this: long-term emissions and emissions to the ocean keep no factor in EF 3.1. The rule caused large deviations in ecotoxicity, human toxicity and freshwater eutrophication and has been removed.
- The impact factors in your library are rebuilt automatically the first time Cyclia opens a project after the update.
- The factor finder in the ecoinvent benchmark now only suggests flows that the method knows by name.

After updating, run **Validate only** (step 1) again.

## Download

| System | File |
|---|---|
| Windows 10/11 | `Cyclia-Setup-1.2.3.exe` |
| macOS (Apple silicon: M1 or later) | `Cyclia-1.2.3-arm64.dmg` |
| Linux | `Cyclia-1.2.3.AppImage` or `Cyclia-1.2.3.deb` |

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.2.3) [Computer software]. https://doi.org/10.5281/zenodo.23853748
