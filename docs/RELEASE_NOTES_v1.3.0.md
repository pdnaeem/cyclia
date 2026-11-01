Cyclia 1.3.0 brings a complete user guide inside the app, makes Cyclia ready for every sector, gives the interface a calmer look, and corrects how waste treatment datasets are counted. Please update.

## Important correction

In ecoinvent, a waste treatment dataset has a reference amount of -1 kg: it "produces" minus 1 kg of waste. Earlier versions counted a positive amount of waste sent to such a dataset as a **credit** instead of a burden. Version 1.3.0 counts it correctly, and a new case in the validation suite (V35) checks it.

If your models use ecoinvent treatment datasets (incineration, landfill, wastewater treatment, recycling), recalculate them. Models with the tutorial or demo data are not affected.

## Automatic updates fixed

Copies of Cyclia 1.2 did not update themselves on Windows: the updater expected a code-signed installer. From 1.3.0 on, updates download in the background, Help > About shows their state, and a **Check for updates** button checks on demand.

**If you have Cyclia 1.2.x, install 1.3.0 once by hand** (download it below and run it over your current installation; projects and databases are kept). Later versions then arrive automatically.

## What is new

- **User guide inside the app**: Help > User guide covers everything from installation to publishing, with an LCA primer, a 20-minute first study, every step, recipes for each sector, troubleshooting and limitations. It has a search box, and every step has a **Guide** link that opens the right section.
- **For every sector**: the tutorial database now has 33 simplified processes (building materials, food, textiles, plastics, solar electricity, waste and wastewater), new templates for a cotton T-shirt, wastewater treatment and a chemical product, and guidance examples from many sectors.
- **Easier steps**: "Select climate change" for a quick start, main indicators listed before their parts, a notice when a dataset is a waste treatment, a transport helper (kg and km to t*km), and data quality requirements in goal and scope.
- **Clearer first step**: the open project is shown at the top, and projects, databases, impact methods and checks each have their own tab.
- **New look**: softer cards, pill-shaped tabs, a calmer header, smooth page changes and icons on the welcome screen; decorative yellow lines removed.

The tutorial data are illustrative and must not be published.

## Download

| System | File |
|---|---|
| Windows 10/11 | `Cyclia-Setup-1.3.0.exe` |
| macOS (Apple silicon: M1 or later) | `Cyclia-1.3.0-arm64.dmg` |
| Linux | `Cyclia-1.3.0.AppImage` or `Cyclia-1.3.0.deb` |

Installed copies on Windows and Linux (AppImage) update themselves.

## Notes

- Installers are not code-signed yet. Windows may show "Windows protected your PC": click **More info**, then **Run anyway**.
- macOS: the first time, right-click Cyclia in Applications and choose **Open**. If macOS says the app is damaged, run `xattr -cr /Applications/Cyclia.app` in Terminal.

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.3.0) [Computer software]. https://doi.org/10.5281/zenodo.23862359

Created by Naeem Ur Rehman. If Cyclia helps your work, you can support it via [PayPal](https://paypal.me/pdnaeem) or [Revolut](https://revolut.me/pdnaeem).
