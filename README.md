<p align="center">
  <img src="app/ui/icon.png" alt="Cyclia logo" width="88">
</p>

<h1 align="center">Cyclia: free, open-source life cycle assessment (LCA) software</h1>

<p align="center">
  Desktop LCA software for students, researchers and consultants. Follows ISO 14040/14044 step by step,
  explains every result, writes ISO, EPD (ISO 14025:2026, EN 15804+A2) and carbon footprint reports, needs no
  programming, and works with your own ecoinvent licence.
</p>

<p align="center">
  <a href="https://github.com/pdnaeem/cyclia/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/pdnaeem/cyclia?label=download&color=23574a"></a>
  <a href="LICENSE"><img alt="MIT licence" src="https://img.shields.io/badge/licence-MIT-23574a"></a>
  <img alt="Windows, macOS, Linux" src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-5a6964">
  <a href="https://doi.org/10.5281/zenodo.23853747"><img alt="DOI" src="https://zenodo.org/badge/DOI/10.5281/zenodo.23853747.svg"></a>
  <a href="CITATION.cff"><img alt="Cite Cyclia" src="https://img.shields.io/badge/cite-CITATION.cff-b5821b"></a>
</p>

<p align="center">
  <a href="https://github.com/pdnaeem/cyclia/releases/latest"><b>Download for Windows, macOS or Linux</b></a>
  &nbsp;·&nbsp; <a href="docs/USER_GUIDE.md">User guide</a>
  &nbsp;·&nbsp; <a href="docs/METHODS.md">Methods and validation</a>
  &nbsp;·&nbsp; <a href="docs/ROADMAP.md">Roadmap</a>
  &nbsp;·&nbsp; <a href="#cite-cyclia">Cite</a>
</p>

![Cyclia showing LCA results per functional unit with guidance for the interpretation step](docs/images/results.png)

## What is Cyclia?

Cyclia is a free desktop application for **life cycle assessment (LCA)**: measuring the environmental
impact of a product, material, building or service from raw material extraction to end of life. It is
made for people who need a credible, publishable LCA but are not programmers: master's and PhD students,
researchers, lecturers and small consultancies.

It walks you through the six stages of an ISO 14040/14044 study (goal and scope, life cycle inventory,
life cycle impact assessment, interpretation and reporting), explains each step in plain language, and
writes a structured Word report with a methods paragraph you can paste into a thesis or journal article.

Cyclia ships with no database. You bring your own licence for **ecoinvent** or use free databases such as
USLCI, Agribalyse or ELCD. Your data stays on your computer.

## Features

**A guided LCA workflow**
- Six steps in ISO 14044 order, each with an explanation, an example, common mistakes and a checklist
  that ticks itself
- A welcome screen with three ways to start: a guided first study, a full demo, or your own project
- Plain-language glossary, guided tutorial and a feature tour

**Databases and impact methods**
- ecoinvent: download with your own licence inside the app, or import a release you already have
- openLCA JSON-LD, SimaPro CSV, ILCD (Ökobaudat, EF datasets, with their data quality ratings), ecoSpold1 and
  ecoSpold2
- EF 3.1 (Environmental Footprint) with official JRC normalisation and weighting, ReCiPe 2016, CML-IA,
  IPCC 2021 GWP100 split per EN 15804+A2, or any method from a CSV table
- Flow mapping between databases and methods with different flow names
- Import that never guesses: process identity kept, ambiguous suppliers left for you to choose, linking per
  location, SHA-256 fingerprint and metadata of every database, a six-part database check and a database explorer

**Modelling**
- Parameters, formulas and scenarios; co-product allocation; system expansion and avoided products
- Circular Footprint Formula (EU PEF) for recycled content, recycling and energy recovery
- Primary, secondary or estimated data per line, with reference, year, supplier and verification
- Life cycle costing (LCC) with discounting, cost types and replacements over a study period, next to the
  environmental results
- EN 15804+A2 modules A to D with module D reported separately; biogenic carbon; dynamic GWP
- Background scenarios for prospective and consequential LCA, including premise and Activity Browser
  scenario files
- Inventory from tables in papers and reports (PDF, Word, Excel or pasted text)
- Model templates for buildings, packaging, food and energy
- Marginal supplier guidance for consequential LCA: constrained suppliers excluded, a consequential
  scenario created from your choices

**Interpretation**
- Contribution analysis by input, process and elementary flow; supply chain tree and Sankey diagram
- Sensitivity analysis, Monte Carlo uncertainty with the pedigree matrix, and Sobol indices
- Parameter sweeps, optimisation and Pareto fronts
- Impacts by location on a world map
- AWARE water scarcity and LANCA land use per process location, with completeness (import the official
  factors)
- Social LCA screening: worker hours and risk hours per stakeholder along the supply chain (import PSILCA,
  SOCA or your own data)
- Dynamic material flow analysis with stocks, lifetimes and recycling loops, and the Material Circularity
  Indicator
- Toxicity: screening characterisation factors for your own chemicals (multimedia fate model with
  USEtox-style exposure and effect), import of official factors by CAS number, and a coverage report
- Automatic ISO 14044 completeness, consistency and sensitivity checks
- Key findings in plain language, burden-shifting alerts, and a data quality rating per result (PEF form)
  with the share of primary data
- Hierarchical Monte Carlo and Sobol analysis through every nested model, Spearman-correlated parameters and a
  convergence check; water withdrawal and consumption
- A comparison gate that checks functional equivalence before alternatives are compared
- Database version comparison (e.g. ecoinvent 3.10 vs 3.11) and one-click move of a model to a new version

**Reports and standards**
- Report centre that shows what each report still needs
- ISO 14044-structured Word report, two-page executive summary, Excel results workbook, journal figures
  (300 dpi PNG and SVG), review and verification status
- EPD per ISO 14025:2026 and EN 15804+A2 with checklist and programme layouts (EPD International, IBU, INIES
  FDES drafts, or your own profile), PEF most relevant results, ISO 14067 carbon footprint report,
  GHG Protocol workbook, critical review checklist
- Export to Brightway and openLCA; Python and R clients for scripted work
- Reproducibility bundles with database and method fingerprints

**Teaching**
- Exercises with automatic checking and an answer key, and a demo project that uses every feature

| Guided first start | Impact assessment | Dark mode |
|---|---|---|
| ![Cyclia welcome screen for new LCA users](docs/images/welcome.png) | ![Choosing impact categories in Cyclia](docs/images/impact-assessment.png) | ![Cyclia inventory step in dark mode](docs/images/dark-mode.png) |

## Validated calculations

LCA results only matter if they are right. Cyclia checks itself in five independent ways:

1. **167 automated tests** of the calculation engine (`engine/tests`), each audit finding with a regression test
2. **A validation suite of 35 product systems with exact known answers**: supply chains, loops,
   allocation, system expansion, units, regional and site factors, background scenarios, module D,
   dynamic GWP, Monte Carlo, Sobol and the fate model. Run it in the app (Toolbox > Validation) and
   attach the report to your thesis or paper.
3. **An independent cross-check**: datasets and models recalculated by a second implementation (matrices rebuilt,
   a different solver) inside the app; see [`docs/CROSS_VALIDATION.md`](docs/CROSS_VALIDATION.md).
4. **Automatic comparison with ecoinvent's own LCIA results**: connect your ecoinvent account and
   Cyclia recalculates a sample of datasets and reports the deviation per impact category.
5. **Factor matching validation**: Cyclia's characterisation factors compared flow by flow with an openLCA
   JSON-LD export, a Brightway export or a CSV, with the effect of every difference on your models.

What each feature does, how it is tested and what it does not do yet: [`docs/ACCEPTANCE_1.3.5.md`](docs/ACCEPTANCE_1.3.5.md) and the audit fixes of 1.3.6 in [`docs/ACCEPTANCE_1.3.6.md`](docs/ACCEPTANCE_1.3.6.md).

The calculation method, with references, is documented in [`docs/METHODS.md`](docs/METHODS.md).

## Download and install

1. Open the [latest release](https://github.com/pdnaeem/cyclia/releases/latest).
2. Download `Cyclia-Setup-x.y.z.exe` (Windows), the `.dmg` (macOS on Apple silicon, M1 or later), or the `.AppImage` / `.deb` (Linux).
3. Install and start Cyclia. Choose "Learn with a first study" to try it with the free tutorial database.

Installed copies update themselves when a new release is published.

## Who uses Cyclia?

- **Students** writing an LCA chapter in a master's or PhD thesis
- **Researchers** who need transparent, reproducible LCA results for journal articles
- **Lecturers** teaching life cycle assessment, with exercises and answer keys
- **Architects, engineers and small consultancies** preparing EPD-style or carbon footprint studies
- **Companies** comparing product designs on environmental impact and cost

## Frequently asked questions

**Is Cyclia free?**
Yes. Cyclia is free and open-source software under the MIT licence, for academic and commercial use.

**Do I need an ecoinvent licence?**
Only if you want ecoinvent data. Cyclia also reads free databases (USLCI, Agribalyse, ELCD and others in
openLCA JSON-LD, ILCD or SimaPro CSV format) and has a built-in tutorial database for learning.

**Do I need to know Python?**
No. Everything is done through the interface. Python and R clients are available if you want them.

**How does Cyclia compare to openLCA, SimaPro or Brightway?**
openLCA and Brightway are excellent open-source tools; SimaPro and Sphera are commercial. Cyclia focuses on
guiding users through a complete ISO 14044 study, explaining each result, checking its own calculations, and
producing ready reports, and it can export models to openLCA and Brightway. See the comparison in
[`docs/ROADMAP.md`](docs/ROADMAP.md).

**Which standards does Cyclia follow?**
ISO 14040/14044, ISO 14071:2024 (critical review), ISO/TS 14074:2022, ISO 14067, ISO 14025:2026, EN 15804+A2
and the EU PEF method (EF 3.1). The list with what each is used for is in the roadmap.

**Can I use Cyclia results in a publication?**
Yes, with your own licensed or published database. Run the validation suite, report the software version,
and cite Cyclia. The tutorial and demo data are illustrative only and must not be published.

**Does my data leave my computer?**
No. Projects and databases are stored locally. Cyclia only goes online to download ecoinvent with your
login or to check for updates.

## Cite Cyclia

If Cyclia helps your research, please cite it. Citing is how free scientific software gets credit.

> Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.3.6)
> [Computer software]. https://doi.org/10.5281/zenodo.23853747

GitHub's "Cite this repository" button gives APA and BibTeX from [`CITATION.cff`](CITATION.cff). Inside
the app, Help > About copies the citation, BibTeX or a ready sentence for your methods section.

## Support Cyclia

Cyclia is developed without outside funding. If it saves you time, you can support its maintenance and
validation through [PayPal](https://paypal.me/pdnaeem) or [Revolut](https://revolut.me/pdnaeem).
Starring the repository and citing Cyclia help too.

## Author

Created by **Naeem Ur Rehman**, environmental scientist and founder of NielloSoft (Pvt) Ltd.
[LinkedIn](https://www.linkedin.com/in/pdnaeem/) · [GitHub](https://github.com/pdnaeem) ·
[niellosoft.com](https://niellosoft.com) · support@niellosoft.com

## Contributing

Bug reports, feature requests and pull requests are welcome; see [`CONTRIBUTING.md`](CONTRIBUTING.md).
Third-party components and their licences are listed in [`THIRD_PARTY.md`](THIRD_PARTY.md).

### Build from source

```bash
pip install -r engine/requirements.txt
cd app && npm install && npm start
python -m unittest discover -s engine/tests -v
```

On Windows, `build-windows.bat` runs the tests, builds the engine and produces the installer in
`app\dist`. On macOS and Linux use `build-mac-linux.sh`. Pushing a tag such as `v1.3.6` makes GitHub
Actions build Windows, macOS and Linux installers and publish them as a release.

```
app/                 Electron desktop shell and interface
engine/              Python calculation engine (local API on 127.0.0.1, token protected)
engine/tests/        automated tests
docs/                user guide, methods, release notes, screenshots
credits.json         author information shown in the installer, app and reports
```

## Licence

MIT, copyright (c) 2026 Naeem Ur Rehman and the Cyclia contributors. See [`LICENSE`](LICENSE).
ecoinvent and other databases are not part of Cyclia and keep their own licences.
