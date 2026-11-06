Cyclia 1.2.2 improves agreement with ecoinvent's own impact assessment results.

## Download

| System | File |
|---|---|
| Windows 10/11 | `Cyclia-Setup-1.2.2.exe` |
| macOS (Apple silicon: M1 or later) | `Cyclia-1.2.2-arm64.dmg` |
| Linux | `Cyclia-1.2.2.AppImage` or `Cyclia-1.2.2.deb` |

Installed copies of Cyclia update themselves.

## What is new

- Characterisation factors given for the subcompartment "unspecified" now also apply to subcompartments without a factor of their own, as in ecoinvent and SimaPro. This closes gaps for radionuclides emitted to water and similar cases.
- ecoinvent LCIA files with a location column are read with their regional factors.
- The ecoinvent benchmark compares with global factors only, because ecoinvent's published results are not regionalised.
- New **factor finder** in the benchmark: it names the flows whose factor differs from the one ecoinvent uses and shows the factor that fits ecoinvent's results.

**After updating:** the new matching rule is applied to your library automatically the first time Cyclia opens a project. Run "Validate only" (step 1) again to see the effect.

## Notes

- Installers are not code-signed yet. Windows may show "Windows protected your PC": click **More info**, then **Run anyway**.
- macOS: the first time, right-click Cyclia in Applications and choose **Open**. If macOS says the app is damaged, run `xattr -cr /Applications/Cyclia.app` in Terminal.

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.2.2) [Computer software]. https://doi.org/10.5281/zenodo.23853748

Created by Naeem Ur Rehman. If Cyclia helps your work, you can support it via [PayPal](https://paypal.me/pdnaeem) or [Revolut](https://revolut.me/pdnaeem).
