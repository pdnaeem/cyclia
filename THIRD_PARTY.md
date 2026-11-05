# Third-party software and data

Cyclia's own code is under the MIT licence (LICENSE). The installers also contain:

| Component | Use | Licence |
|---|---|---|
| Electron | desktop shell | MIT |
| electron-updater | updates | MIT |
| Python and its standard library | engine runtime | PSF License |
| NumPy, SciPy | matrix calculations | BSD-3-Clause |
| lxml | XML import | BSD-3-Clause |
| openpyxl | Excel files | MIT |
| python-docx | Word reports | MIT |
| matplotlib | charts in reports | Matplotlib License (PSF-based) |
| pypdf, pdfplumber | reading tables from PDF | BSD-3-Clause, MIT |
| ecoinvent_interface (optional) | download with the user's ecoinvent login | see its repository |
| Natural Earth 1:110m countries (downloaded at build time) | results map | public domain |
| ILCD and ILCD+EPD XML schemas and indicator identifiers (InData working group, github.com/InDataWG/ILCD-EPD-Data-Format) | validation and identifiers of the ILCD+EPD export (engine/schemas/ilcd_epd) | Apache License 2.0 |

Built-in reference data:
* EF 3.1 normalisation factors: Andreasi Bassi et al. (2023), JRC130796; weighting factors: Sala et al.
  (2018), JRC106545 (European Commission, reuse authorised).
* IPCC AR6 (2021) GWP100 values.

No life cycle inventory database is included. ecoinvent and other licensed databases are imported by each
user under their own licence and stay on their computer. The tutorial and demo databases contain
illustrative numbers written for Cyclia and must not be cited.

## Fonts

- **Inter** (The Inter Project Authors), SIL Open Font License 1.1. Bundled in `app/ui/fonts/` as a Latin
  subset; licence text in `app/ui/fonts/LICENSE-Inter.txt`.
