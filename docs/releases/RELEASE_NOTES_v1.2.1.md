Cyclia 1.2.1 adds the macOS installer and shows the DOI in the app and in every report.

## Download

| System | File |
|---|---|
| Windows 10/11 | `Cyclia-Setup-1.2.1.exe` |
| macOS (Apple silicon: M1 or later) | `Cyclia-1.2.1-arm64.dmg` |
| Linux | `Cyclia-1.2.1.AppImage` or `Cyclia-1.2.1.deb` |

Installed copies of Cyclia 1.2.0 on Windows and Linux update themselves.

## What is new

- macOS installer for Apple silicon
- The Zenodo DOI is shown in Help > About, in the copied citation and in the references of every Word report

## Notes

- Installers are not code-signed yet. Windows may show "Windows protected your PC": click **More info**, then **Run anyway**.
- macOS: the first time, right-click Cyclia in Applications and choose **Open**. If macOS says the app is damaged, open Terminal and run `xattr -cr /Applications/Cyclia.app`, then open it again.
- Cyclia includes no database. The tutorial and demo data are illustrative and must not be published.

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.2.1) [Computer software]. https://doi.org/10.5281/zenodo.23853748

Created by Naeem Ur Rehman. If Cyclia helps your work, you can support it via [PayPal](https://paypal.me/pdnaeem) or [Revolut](https://revolut.me/pdnaeem).
