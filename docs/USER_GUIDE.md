# Cyclia user guide

This guide takes you from installing Cyclia to a finished, publishable life cycle assessment (LCA). It
explains the LCA ideas you need on the way, so you can follow it even if this is your first study. The
same guide is inside the app: **Help > User guide**, and the "Guide" link on every step opens the right
section.

**Contents**

1. [LCA in ten minutes](#lca-in-ten-minutes)
2. [Install, start and update](#install-start-and-update)
3. [The screen](#the-screen)
4. [Your first study in 20 minutes](#your-first-study-in-20-minutes)
5. [Step 1: Project and data](#step-1-project-and-data)
6. [Step 2: Goal and scope](#step-2-goal-and-scope)
7. [Step 3: Inventory](#step-3-inventory)
8. [Step 4: Impact assessment](#step-4-impact-assessment)
9. [Step 5: Interpretation](#step-5-interpretation)
10. [Step 6: Report](#step-6-report)
11. [Your own data (custom data entry)](#your-own-data-custom-data-entry)
12. [Toolbox](#toolbox)
13. [Recipes by sector](#recipes-by-sector)
14. [Publishing with Cyclia](#publishing-with-cyclia)
15. [Troubleshooting](#troubleshooting)
16. [Limitations](#limitations)

---

## LCA in ten minutes

A life cycle assessment adds up the environmental impacts of a product or service over its whole life:
raw materials, production, transport, use and end of life. ISO 14040 and ISO 14044 describe how to do it
in four phases. Cyclia follows these phases in six steps.

| ISO 14044 phase | What you do | Cyclia step |
|---|---|---|
| Goal and scope definition | Say what you study, why, and where the system ends | 1 and 2 |
| Life cycle inventory (LCI) | List every input and output per functional unit | 3 |
| Life cycle impact assessment (LCIA) | Turn the inventory into impacts such as climate change | 4 |
| Interpretation | Find what matters, test how reliable it is, conclude | 5 and 6 |

**The words you will meet**

- **Functional unit**: the function you measure, with an amount. "1 kWh of electricity delivered to a
  household", "1 T-shirt worn 50 times", "1 m2 of wall over 50 years". Every number in the study is per
  functional unit. Two products can only be compared when they deliver the same function.
- **Reference flow**: how much product is needed to deliver the functional unit, for example 0.2 kg of
  T-shirt. In Cyclia the amounts you type in step 3 are the reference flows.
- **System boundary**: which life cycle stages are inside the study. Cradle-to-gate stops at the factory
  gate; cradle-to-grave adds use and end of life; gate-to-gate covers one site only.
- **Foreground and background**: the foreground is what you model yourself (your product and its direct
  inputs). The background is everything behind those inputs (electricity grids, materials, fuels, transport),
  which comes from a database such as ecoinvent.
- **Unit process (dataset)**: one activity in a database, such as "cotton fibre production" or
  "electricity, low voltage, market for". It has inputs from other activities, outputs and emissions.
- **Product flow and elementary flow**: a product flow goes between activities (steel, electricity,
  transport). An elementary flow crosses the border with nature: an emission (CO2 to air, nitrate to water)
  or a resource (water from a river, land occupied, crude oil in the ground).
- **Characterisation factor**: how strongly one elementary flow contributes to one impact. 1 kg of fossil
  methane = 29.8 kg CO2-eq in IPCC 2021 GWP100. An impact method is a set of these factors.
- **Normalisation and weighting**: optional steps that express results relative to a reference (for example
  the impact of an average person per year) and combine them into a single score.
- **Allocation**: sharing the burdens of a process between its co-products (cotton fibre and cottonseed).
  System expansion is the alternative: the co-product replaces another product, which you credit.
- **Attributional and consequential**: attributional LCA describes the average share of burdens of your
  product. Consequential LCA describes the change a decision causes (marginal suppliers). ecoinvent offers
  both as system models: cut-off and APOS are attributional, "consequential" is consequential.
- **Uncertainty**: every inventory number is uncertain. Cyclia propagates it with Monte Carlo simulation.

---

## Install, start and update

**Download.** Open https://github.com/pdnaeem/cyclia/releases/latest and download:

- Windows 10 or 11: `Cyclia-Setup-x.y.z.exe`
- macOS on Apple silicon (M1 or later): `Cyclia-x.y.z-arm64.dmg`
- Linux: `Cyclia-x.y.z.AppImage` (make it executable) or `Cyclia-x.y.z.deb`

**Windows warning.** The installer is not yet code-signed, so Windows may show "Windows protected your PC".
Click **More info**, then **Run anyway**. The installer shows the licence, lets you choose the folder and
creates a desktop shortcut.

**macOS warning.** The first time, right-click Cyclia in Applications and choose **Open**. If macOS says the
app is damaged, open Terminal and run `xattr -cr /Applications/Cyclia.app`, then open it again.

**First start.** A short splash screen appears while the calculation engine starts (a few seconds). Then the
welcome screen asks how much LCA you have done and how you want to start:

- **Learn with a first study**: creates the project "My first LCA" with the free tutorial database and takes
  you to step 2. Choose this if you are new.
- **Explore the full demo**: seven ready-made models that use every feature. Nothing to type.
- **Start my own study**: an empty project. Then connect your database.

You can show the welcome screen again under Help > About > "Show the welcome screen again".

**Updates.** On Windows and with the Linux AppImage, Cyclia checks for a new version a few seconds after it
starts and every few hours, downloads it in the background (a message tells you) and asks "Restart now /
Later". With Later, the update installs when you close Cyclia. Your projects and databases are not touched.
Help > About > Updates shows the state and has a **Check for updates** button. On macOS and with the .deb
package, the same place opens the releases page to download the new version.

**Where your data are.** Projects, the database library and settings are stored in your user folder (Help >
About shows the exact path). Nothing is sent anywhere, except when you log in to ecoinvent or when Cyclia
checks for updates.

---

## The screen

- **Left rail**: the six steps in ISO order. A step ticks itself when it is complete. The bar at the top
  shows how many steps are done. **Toolbox** holds advanced tools. At the bottom: Help, the open project,
  the version and the author.
- **Study sentence** (top): "Assessing 1 item of T-shirt..., cradle-to-grave, with ..., using ...". Dashed
  parts are still missing. It is the quickest way to see whether the study is defined.
- **Model** (top right): the product system you are working on. A project can hold many models.
- **Guidance card** (top of each step): what the step means, its ISO clause, an example, common mistakes
  and a checklist that ticks itself. **Show me** scrolls to the field and highlights it. **Guide** opens
  this guide at the right section. **Guidance on/off** (top right) hides or shows the cards.
- **Next bar** (bottom of each step): goes back or on. It tells you how many tasks are left; you can go on
  anyway and come back.
- **"?" buttons**: open the glossary at that term.
- **Messages**: short messages appear at the bottom of the screen. Long jobs (imports, Monte Carlo) show a
  progress box at the bottom left with a Cancel button; you can keep working meanwhile.
- **Dark mode** follows your operating system setting.

---

## Your first study in 20 minutes

This walk-through uses the tutorial database, so it works without any licence. It models a cotton T-shirt.

1. Welcome screen: **I am new to LCA**, then **Learn with a first study**. Step 1 is done for you.
2. **Step 2, Goal and scope.** Amount `1`, unit `item`, product `T-shirt, cotton, worn 50 times`. Model name
   `Cotton T-shirt`. Goal: `Climate impact of a cotton T-shirt over its use`. Intended application:
   `Course assignment`. Audience: `Teachers and students`. Boundary: **Cradle-to-grave**. Press **Save goal
   and scope**.
3. **Step 3, Inventory.** For each line of the table below: type the search word, click the dataset, type
   the amount, choose the unit, type the stage, press **Add to model**.

| Search | Dataset | Amount | Unit | Stage |
|---|---|---|---|---|
| cotton fabric | cotton fabric weaving and dyeing | 0.23 | kg | Materials |
| electricity | electricity production, grid mix | 0.3 | kWh | Manufacturing |
| lorry | transport, freight lorry 16-32t | 1.6 | t*km | Distribution |
| electricity low voltage | electricity, low voltage, distribution | 2 | kWh | Use (washing) |
| incineration | treatment of municipal solid waste, incineration | 0.2 | kg | End of life |

Why these numbers: 0.2 kg of T-shirt needs about 0.23 kg of fabric because of cutting waste; 1.6 t*km is 0.2 kg
carried 8,000 km (0.0002 t x 8,000 km); 50 washes at 0.8 kWh per 4 kg load for a 0.2 kg garment is
50 x 0.8 x 0.2 / 4 = 2 kWh; the worn-out T-shirt (0.2 kg) is incinerated.

4. **Step 4, Impact assessment.** Press **Select climate change**, then **Calculate**.
5. **Step 5, Interpretation.** Read the total. Open **Contributions**: which line causes most of the impact?
   Open **Checks** and **Sensitivity**.
6. **Step 6, Report.** Write a conclusion and a limitation, press **Save text**, then **Create Word report**.

You have done a complete ISO-structured LCA. The tutorial numbers are simplified, so do not publish them.

---

## Step 1: Project and data

### Layout of this step

At the top, the **open project** card shows which project you are working in, how many models it has and
when it was last saved. **Switch project** jumps to your list of projects; **Continue** takes you to the next
step. Below are four tabs: **Projects**, **Databases**, **Impact methods** and **Check the software**. Cyclia
opens the tab of whatever is still missing.

### Projects

A **project** holds your models, parameters, scenarios, comments and versions. Press **New project**, type a
name and press **Create**. Click any project card to open it; the open one is marked **Open**. **Open a
project file** opens a `.lca` file someone sent you. The bin icon deletes a project from this computer (back
it up first). **Back up project file** (step 6) saves a copy.

### The library

Databases and impact methods are imported once per computer into a shared **library** and used by every
project. A project file stays small because it holds only your models. When you send a project to a
colleague, they need the same databases; Cyclia tells them which ones are missing and links the lines
automatically once they import them.

### Adding a database

In the **Databases** tab, press **Add a database** and open one of the sources.

**ecoinvent with your licence** (recommended if you have one)

1. Enter your ecoinvent username and password (the ones you use on ecoquery.ecoinvent.org) and press
   **Show my releases**. The password is not saved.
2. Choose the version (for example 3.11) and the system model (cut-off is the usual choice).
3. Keep "Then validate Cyclia against ecoinvent's own LCIA results" ticked and press **Download, connect and
   validate**. The first time this takes 10 to 30 minutes. Cyclia downloads the release, imports it,
   imports ecoinvent's impact methods and compares its own results with ecoinvent's.

If the login fails: use your ecoinvent username rather than your e-mail address; if you sign in to ecoinvent
through your university, Google or Microsoft, set an ecoinvent password with "Forgot password" first. You can
always use the next option instead.

**ecoinvent folder you already downloaded.** Download the release from ecoquery (Files), extract the .7z
file, choose the folder that contains "datasets", give it a name, version and system model, and press
**Import folder**.

**Other formats.** openLCA JSON-LD (USLCI, Agribalyse, ELCD and many free databases on openLCA Nexus),
SimaPro CSV exports, ILCD (Ökobaudat, EF datasets) and ecoSpold1. Choose the format, give a name, choose the
file or folder and press **Import**.

**Tutorial database.** 33 simplified processes (building materials, food, textiles, plastics, energy, waste
and wastewater) with simple impact methods. For learning only.

**Link missing suppliers.** After an import, "Link missing suppliers" lists every input without a single
supplier, with the reason: produced by no dataset of the import (often a product of another database, as in USLCI
or Agribalyse), produced by several datasets (Cyclia does not guess and shows the candidates), or without a
supplier link in the dataset (ecoSpold2). Each location is its own row, so electricity for France and for Poland
get their own suppliers. "Link automatically" only links rows with exactly one supplier at the same location.
Inputs that the system model cuts off on purpose (recycled content in the ecoinvent cut-off model) must stay
unlinked.

**Details** records the database's original name, version, system model, release date, geography, technology,
licence, reference period and citation, next to the source file's SHA-256 fingerprint and the Cyclia version that
imported it. Enter what you know: it is printed in reports and makes the study reproducible.

Imports of ecoSpold, openLCA, SimaPro and ILCD files go into a separate staging library first and enter your
library only after the checks pass; a failed import leaves the library as it was.

**Check** tests the database in six parts: the matrix (can it be solved), the technosphere (inputs without a
supplier, by reason), elementary-flow coverage, units, metadata and LCIA compatibility. A solvable matrix does
not mean a complete database: read every line.

### Adding impact methods

- **ecoinvent LCIA file**: the "LCIA Implementation" Excel from ecoquery. Contains EF 3.1, ReCiPe 2016,
  CML-IA, IPCC 2021 and more, matched to ecoinvent flows. Imported automatically by the ecoinvent login.
- **Free method packages**: EF 3.1 or ReCiPe for openLCA (JSON-LD zip), imported with "Other formats".
- **Any method from a CSV table**: one row per factor: method, category, indicator, unit, flow name,
  compartment, subcompartment, factor, flow UUID (optional), location (optional, for regional factors such as
  AWARE). "Show the CSV format" shows an example.
- **Flow mapping**: lets a method written for other flow names (EF, FEDEFL) work with your database.
- **Official EF 3.1 normalisation and weighting**: the JRC factors, attached with one click to the EF 3.1
  categories you imported.
- **Factors by CAS number**: USEtox results or any table with a CAS column; substances are matched by CAS
  number, then by name.
- **Normalisation and weighting factors**: your own sets from a CSV.
- **Cyclia built-in: IPCC 2021 GWP100** is always available, split into fossil, biogenic and land use as
  EN 15804+A2 and ISO 14067 require.

### Checking the software

**Validate against ecoinvent (automatic)** compares Cyclia with ecoinvent's own published results for a
sample of datasets from every sector and every category, and saves an Excel report with a diagnosis. Run it
once per database before you publish. **Benchmark against reference results** does the same against any
table (openLCA, Brightway or ecoinvent results).

---

## Step 2: Goal and scope

A **model** is one product system. Press **New model**, fill the form and press **Save goal and scope**.
**Start from a template** creates a complete model in one click (see below). **Duplicate as alternative**
copies a model so you can build a variant to compare.

### Functional unit

Amount, unit and the product or service. Add details of the function in "Functional unit details" (quality,
lifetime, performance). Good functional units name the function, not only the material:

| Sector | Weak | Better |
|---|---|---|
| Buildings | 1 kg insulation | 1 m2 of wall insulated to U = 0.2 W/m2K for 50 years |
| Food | 1 kg of bread | 1 kg of bread at the bakery gate (or: per 1,000 kcal) |
| Textiles | 1 T-shirt | 1 T-shirt worn 50 times |
| Energy | 1 solar panel | 1 kWh of electricity delivered at low voltage |
| Packaging | 1 bottle | packaging for 1 litre of beverage delivered |
| Water | 1 treatment plant | 1 m3 of wastewater treated to the legal limits |

### Goal

The goal of the study, the reasons, the intended application (thesis, article, product development,
marketing), the audience, and whether results will be used in a comparison disclosed to the public. A public
comparison requires a critical review panel (ISO 14044 6.3).

### Scope

- **System boundary**: cradle-to-gate, cradle-to-grave, cradle-to-cradle or gate-to-gate.
- **Life cycle stages**: a stage system for the stage names you will use in step 3 (EN 15804 modules A1 to
  D for construction products, general stages, agriculture).
- **Geography**, **time period** and **technological coverage** the study represents.
- **Modelling approach**: attributional (the share of today's burdens that belongs to your product, with
  average data) or consequential (what changes because of a decision, with marginal suppliers and system
  expansion). Cyclia warns when the database system model or the allocation does not fit the approach.
- **Cut-off criteria**: what you leave out, for example flows below 1 % of mass and energy.
- **Data quality requirements**: what data you need (primary or secondary, region, year, technology).
- **Key assumptions**.

### Allocation

If your process makes more than one product, say how burdens are shared. Choose **mass**, **economic**,
**energy** or **another physical relationship** (name the property, for example nitrogen content) and enter the value for your product and for each co-product; Cyclia computes the share. Or enter
a share in % yourself. The text field "Allocation procedure" goes into the report. The alternative, system
expansion, is done in step 3 with an avoided product.

The share applies to every line of the model. If only one process of your system is multi-functional (for
example the cotton gin, which also gives cottonseed), model that process as its own model with the
allocation, and use it as a line in the main model (tab "My models and processes").

### Time

Tick **dynamic GWP** to give each inventory line a year of emission. Step 5 then shows climate impact over
time (Levasseur et al., 2010), useful for long-lived products and biogenic carbon.

### Costs

To add life cycle costing, give a **currency** and, if you want future costs discounted, a **discount rate**.
Then enter a price on the lines in step 3 (**Details**). The Year column of each line is used for
discounting. Each costed line can have a **cost type** (capital, operating, maintenance, replacement, end of
life) and a **replacement interval** in years: with a **study period** in step 2, the cost is repeated in year
y, y + R, y + 2R ... before the end of the period and each occurrence is discounted. Results show the life cycle
cost per functional unit by line, stage and cost type, and whether the cost hotspot is the same as the
environmental one.

Following ISO 15686-5, Cyclia also handles:

- **Price escalation** (step 2), per cost type, as a real rate in % per year. Write it as
  `maintenance=2, operation=1.5`, or `all=1` for every type.
- **Residual value** (step 2, on by default). If the last replacement still has service life left at the end of the
  study period, that remaining value is credited. Example: an item bought every 25 years in a 60-year study is
  bought in years 0, 25 and 50; the last one still has 15 of its 25 years left, so 15/25 of its price is credited.
- **Price uncertainty** (line Details), as a geometric standard deviation. For example, 1.2 means the price is within
  a factor 1.2, roughly two times in three. The Summary then shows the 95 % range of the net present cost.
- **Cost types** include the ISO 15686-5 categories: construction, operation, maintenance, end of life,
  non-construction, income and externalities.

**Compare allocation choices** (step 2, allocation, when the model has co-products) shows the results under mass,
economic, energy, physical and manual allocation, and without allocation, for the categories of step 4. A choice
whose values are missing is listed with what to fill in.

### Parameters and scenarios

A **parameter** is a named number you can use in amounts, for example `distance_km = 300`. Formulas use
`+ - * / **`, parentheses and `min`, `max`, `abs`, `round`, `sqrt`, `exp`, `log`, `log10`, `if_(condition,
a, b)`. Parameter names use letters, digits and `_`, start with a letter, and cannot be a reserved word.
Give a parameter a distribution (lognormal, normal, triangular, uniform) to include it in uncertainty and
Sobol analysis. When two uncertain parameters move together (fuel use and distance, for example), add a
**correlation** between them under the parameter table; Monte Carlo then samples them together. A **scenario** is a named set of parameter values (for example "long distance", "recycled").

### Templates

**Start from a template** creates a model with goal, scope, parameters and lines, and links each line to the
best dataset in your library. Built-in templates: external wall (EN 15804+A2), beverage packaging (PEF style),
arable crop (IPCC Tier 1 field emissions), rooftop solar electricity, cotton T-shirt, wastewater treatment
and a chemical product at the plant gate. Lines that could not be linked are listed so you can link them.
Save any model as your own template.

### Versions and lock

Save a named version of a model before big changes, compare two versions line by line, and restore one.
**Lock** a model after review so nobody changes it by accident.

---

## Step 3: Inventory

This is the heart of the study. The inventory lists everything that goes into and out of your product
system for one functional unit.

### Plan before you type

1. **Draw the system.** On paper, draw boxes for the processes you control (fabric cutting, sewing,
   washing) and arrows for what goes in and out. The flow diagram in Cyclia (button **Flow diagram**) draws
   it for you once lines are entered.
2. **Collect data per functional unit.** Scale everything to one functional unit. If a factory makes
   10,000 T-shirts with 3,000 kWh, each T-shirt uses 0.3 kWh.
3. **Sort each flow into one of the types below.**

### Which line type for which flow

| What it is | Example | How to enter it |
|---|---|---|
| Material, energy, fuel, service | fabric, electricity, diesel, transport | **Datasets** tab: a dataset, positive amount |
| Transport | lorry, ship, train | **Datasets** tab, unit t*km = tonnes x kilometres |
| Waste you send away | worn T-shirt, packaging waste, wastewater | **Datasets** tab: a treatment dataset (incineration, landfill, recycling, wastewater treatment) with the amount of waste, positive |
| Emission from your own process | CO2 from a boiler on site, N2O from a field, methane from a digester | **Direct emissions and resources** tab: the flow, compartment (air, water, soil) and amount |
| Resource taken from nature by your process | water from a well, land occupied | **Direct emissions and resources** tab |
| A part you modelled yourself | a sub-assembly, your own process | **My models and processes** tab |
| A supplier's EPD | insulation with declared A1-A3 values | **EPD values** tab |
| A co-product | cottonseed, heat sold | Allocation in step 2, or an avoided product (below) |

### Adding a line

1. Type in the search box: a product name and words like `market`, a region, a technology. Examples:
   `cotton fibre`, `electricity low voltage FR`, `lorry 16-32`, `incineration municipal`.
2. **Region**: type a code such as `FR`, `DE`, `CN`, `RER` (Europe), `GLO` (global), `RoW` (rest of world)
   to put matching datasets first.
3. **Market or production?** Choose "market for" datasets unless you know the producer: markets include the
   supply mix, transport and losses. Choose a production dataset when you know the exact supplier.
4. Click the dataset. The panel on the right shows its main inputs and emissions per unit. Check that it
   fits your case.
5. Type the **amount per functional unit** or a formula (`fabric_kg * 1.15`). Choose the **unit**: Cyclia
   converts compatible units (g, kg, t; MJ, kWh; m3, l; t*km, kg*km).
6. Type the **stage** (it is remembered for the next line) and a **data source** (supplier, measurement,
   literature with year).
7. Press **Add to model**. The form stays open for the next line.

**Waste treatment.** ecoinvent describes a treatment as a dataset that "produces" minus 1 kg of waste.
Enter the waste you send as a positive amount; Cyclia counts the treatment burdens. The panel says when a
dataset is a treatment.

**Credits (system expansion and module D).** Tick **Avoided product** for a product your system replaces:
recycled steel replacing primary steel, electricity from waste incineration replacing grid electricity.
The line is subtracted. In an EN 15804 study, put credits in stage `D`; they are reported separately.

**Transport.** Amount in t*km = mass in tonnes x distance in km. 200 g carried 8,000 km = 0.0002 x 8000 =
1.6 t*km. For transport datasets the panel has a **transport helper**: type the mass in kg and the distance
in km and the amount is filled in. Include transport of materials to your site, of the product to the user,
and of waste.

### The inventory table

- **Amount and unit**: edit in place; `f(x)` turns the amount into a formula.
- **Credit**: the avoided-product tick.
- **Data quality** (five scores, 1 best, 5 worst): reliability, completeness, temporal, geographical and
  technological representativeness (pedigree matrix, Weidema et al. 2013). Hover a box to see the meaning.
  Rate at least the lines that matter most; the scores widen the uncertainty in Monte Carlo.
- **Data type** (above the source box): **primary** (measured at the site or given by the supplier),
  **secondary** (database or literature) or **estimate** (your own assumption). Cyclia reports how much of
  each result rests on primary data. Reviewers look at this first for the main contributors.
- **Data source** and **note**: where the number comes from, and comments for co-authors.
- **Details**: the reference or document, the year of the data, the supplier or site, whether it was checked
  by a third party, a price for life cycle costing, and optionally the four **PEF data quality scores** (TeR,
  GeR, TiR, P). These go into the report's data provenance table. Producer-specific (primary) data older than
  5 years and other data older than 10 years raise a warning (EN 15804+A2 6.3.8.2).
- **Replace**: swap the dataset, keep the amount.
- **Remove** and **Undo** (top).

**Recycling (CFF)** in the toolbar of the table applies the Circular Footprint Formula of the EU PEF method
to one material: give its mass, the A, B, R1, R2, R3 and quality values of your PEFCR (or Annex C of the PEF
method) and, for energy recovery, the heating value and efficiencies. Cyclia shows the coefficient of every
term, asks for a dataset for each term that is not zero (virgin material, recycled material, recycling,
energy recovery, avoided heat and electricity, disposal) and adds the lines, with the credits ticked.

**Copy as editable process** (in the dataset panel) makes a copy of a dataset as your own model, so you can
change, for example, the electricity mix of a supplier.

### Faster ways to build an inventory

- **Excel template / Import from Excel / Export to Excel**: columns Type, Database, Dataset or flow name,
  Location or compartment, Amount, Unit, Stage, Avoided product, Source note, Data quality. All rows are
  checked before anything is imported.
- **From a paper or table**: paste a table or open a PDF, Word or Excel file; Cyclia reads the rows and you
  confirm the dataset for each.
- **External model emissions**: add emissions computed by another model (leaching, runoff, field emissions)
  as a CSV with year, flow, compartment, subcompartment, amount and unit.

### Checking the inventory

The problems box above the table lists lines without a dataset and unit issues. In step 5, **Checks**
compares mass in and out (mass balance), flags lines with default data quality and lists lines that are
below 1 % everywhere (cut-off candidates).

---

## Step 4: Impact assessment

### Choosing categories

- **Not sure?** Press **Select climate change** and calculate. Add more later.
- **EF 3.1** (Environmental Footprint) is the EU reference with 16 categories, normalisation and weighting.
  Required for PEF studies.
- **ReCiPe 2016** and **CML-IA** are common in journal articles.
- **IPCC 2021 GWP100** for carbon footprints (ISO 14067, GHG Protocol); the built-in version splits fossil,
  biogenic and land use.
- Use **one method family per indicator**; do not mix two climate change methods in one result table.
- If your goal speaks of "environmental impact" in general, include more than climate change.

A category marked "no matching factors" has no factor for any flow in your library: import a flow mapping
or another method.

### Options

- **Scenario**: parameter values to use.
- **Normalisation and weighting**: for single scores (EF 3.1 official set or your own).
- **Sensitivity check range**: each input is varied by this % for the sensitivity table.
- **Background database**: "as imported", or a prospective scenario (future electricity mixes for a target
  year) or a consequential scenario defined in the Toolbox.
- **Uncertainty analysis**: none; foreground (data quality and parameter distributions, seconds); or full
  Monte Carlo including the database's own uncertainty (minutes for ecoinvent; runs in the background).
  1,000 iterations are usual. Both include every line and every parameter distribution of nested models
  (models used inside your model), each with its own data quality, and the correlations you defined.

Press **Calculate**.

---

## Step 5: Interpretation

Interpretation (ISO 14044 4.5) answers three questions: what drives the result, how reliable is it, and what
can be concluded.

- **Summary** (opens first): key findings computed from your result. For each category it names the largest
  contributors and stage, credits and module D, and the Monte Carlo interval if you ran one. It also says when
  different categories have different hotspots (a risk of burden shifting), which change would lower the
  result most, which important lines still have weak or default data, and what must be fixed first. Below
  the findings, **Data quality of the results** gives, per category, a **pedigree indicator**: the pedigree
  scores of every line (also inside nested models) weighted by its share of the impact, credits left out, in
  the form (TeR + GeR + TiR + P) / 4 from 1 (excellent) to 5 (poor). It is not a PEF DQR, because pedigree
  reliability is not PEF precision. Enter the four PEF scores for your lines (Details in step 3) to get the
  **PEF DQR** and the share of the impact it covers. Lines that use an ILCD or EF dataset without PEF scores of
  their own take the dataset's TeR, GeR, TiR and P from its data quality indicators (read on import); the share
  scored this way is shown as "from datasets". The table also gives the shares of primary, secondary,
  estimated and unstated data. Treat the findings as a draft for
  your interpretation: check each one against the other tabs and add what you know about the system.
  When you entered prices, the Summary also shows the **life cycle cost**; when the inventory has water flows,
  a **water inventory** (withdrawal, release, consumption).
- **Results per functional unit**: the total per category, with module D separate, 95 % intervals after
  Monte Carlo, and normalised and weighted values when chosen. Click a row to choose the category for the
  tabs below.
- **Contributions**: share of each inventory line, each background process (hotspots) and each elementary
  flow. The top contributors are where better data and improvements matter most.
- **Supply chain**: the tree of where the impact comes from, and a flow chart (Sankey).
- **Stages**: impact per life cycle stage.
- **Sensitivity**: the effect of changing each input by the chosen %, parameter sensitivity, and Sobol
  indices (which uncertain inputs explain the spread).
- **Uncertainty**: histogram and intervals from Monte Carlo, and whether the run has **converged** (the mean
  is known to within 1 % of the 95 % interval, and the interval is stable). If not, run more iterations.
- The tabs below are in front: Summary, Contributions, Supply chain, Stages, Sensitivity, Uncertainty,
  Inventory results, Checks and Compare. **More analyses** holds Dynamic climate, Map, Explore parameters and PEF.
- **Dynamic climate**: climate impact over time, when dynamic GWP is on.
- **Map**: where impacts occur, by country of the processes.
- **Explore parameters**: sweeps (result as a parameter changes), optimisation (best parameter values under
  constraints) and Pareto fronts between two categories.
- **PEF**: most relevant categories, stages, processes and flows by the PEF 80 % rule.
- **Inventory results**: the foreground inventory with its provenance, for this model or for the complete supply
  chain of nested models (amount per unit and per functional unit), all elementary flows, flows without a
  factor, toxicity coverage.
- **Checks**: completeness, consistency and sensitivity checks (ISO 14044 4.5.3). Each check links to the
  step where you fix it. Errors must be fixed; warnings and notes should be explained in the report.
- **Compare**: before comparing, write the **functional equivalence**: why the alternatives give the same
  function (performance, service life, quality). Cyclia blocks comparisons whose functional units differ, and
  lists differences in boundary, stages, allocation, approach, geography, period, background data and data
  quality. Only without such differences and with the equivalence statement is it a valid comparison;
  otherwise it is shown as a screening comparison, which you must not present as a comparative assertion.
  Models side by side (with paired Monte Carlo: the probability that A is lower than B) and
  scenarios of one model. Above the chart Cyclia states which alternative is lowest in each category. When
  no alternative is lowest everywhere, choosing one shifts burdens to other categories, and the report must
  show all categories. Whether a difference is real is judged with the **comparative Monte Carlo**: a difference
  counts as robust when one alternative is lower in at least 95 % of the runs. Scenario comparison lists, per
  scenario, which categories go down and which go up.

**A difference is only meaningful when it is larger than the uncertainty.** Use the paired Monte Carlo in
Compare before you claim that one product is better.

---

## Step 6: Report

- **Report centre**: press **Check what each report needs** to see, for every report Cyclia can write, what is
  still missing from your model, and create it from there.

- **Conclusions, limitations, recommendations** and **critical review**: write them and press **Save
  text**.
- **Review and verification status**: draft, internal review, external expert review, review panel (ISO
  14044 6.4) or independently verified (for example by an EPD programme operator). It is printed at the top of
  the report. A comparative assertion disclosed to the public needs a panel review; Cyclia warns until the
  status says so.
- **Create Word report**: a report structured as ISO 14044: goal and scope, inventory with parameters and
  data quality, impact assessment, interpretation with key findings, data quality, checks and sensitivity, a methods paragraph you can
  paste into a thesis or article, the inventory results and references (including Cyclia).
- **Export results to Excel**: every table, including data quality, key findings, costs and water. The
  **Provenance** sheet lists every dataset of the supply chain (also deep in the background) with its database,
  version, system model, identifier, the amount per functional unit and its own direct contribution to each
  category; for your own data also the source, author, revision and data quality. The Word report summarises it in
  an annex with the 25 largest contributions.
- **Executive summary**: two pages for managers: what was assessed, the main results with their largest
  contributor and data quality, key findings, conclusions and review status.
- **Figures for a journal**: the contribution charts as 300 dpi PNG and as SVG in a zip file.
- **Write methods paragraph**: the methods text alone, to copy.
- **Standards and declarations**: EPD per ISO 14025:2026 and EN 15804+A2 (modules A1 to D, with a requirements
  check, the intended audience, the share of the GWP result from supply-chain-specific data, months of
  specific data, and prospective EPDs with their uncertainty). Every line must be in an EN 15804 module (A1-A3,
  A4, A5, B1 to B7, C1 to C4, D); Cyclia does not write the EPD while a stage has another name, and checks that
  the module table adds up to the LCA result. It also checks the resource use, waste and output indicators of EN
  15804+A2 (PERE to EET) and the units. You can always create a draft; it says "not ready for submission" while
  anything is open. Enter the PCR version and your programme operator's mandatory statements in the EPD form.
  **Programme layout**: choose Cyclia generic, the International EPD System, IBU or INIES FDES. The Word file then
  follows that programme's order of sections and statements (INIES in French), the form shows the programme's
  extra fields (required ones marked *), and the requirements check adds the programme's required fields,
  indicators and maximum validity. These profiles are drafts built from EPDs the programmes have published; they
  are not approved by the programme operators, so check them against your programme's current instructions.
  Under **Your own programme profile** you can export a profile as JSON, edit it, and load it.
  **ILCD+EPD dataset** writes the EPD as a machine-readable ILCD+EPD zip (the format of ÖKOBAUDAT and the InData
  network), checked against the official schemas. Open it in the EPD Editor to add contacts and the review before
  upload.
  Then an ISO
  14067 carbon footprint report and a GHG Protocol workbook.
- **Critical review checklist**: the ISO 14044 items a reviewer checks, with your notes, exported to Excel.
- **Share, reproduce, exchange**: a reproducibility bundle (models, settings and fingerprints of the
  databases and methods), and exports to Brightway and openLCA.

---

## Your own data (custom data entry)

Databases such as ecoinvent describe thousands of common processes. Your own process is often not among them:
your factory, your farm, a new material, a pilot plant, a recycling step. **Your own data** (Toolbox > Your own
data) lets you describe such processes yourself. Cyclia then treats them like any other dataset: you add them to a
model, calculate impacts, run Monte Carlo, write reports and EPDs. You can work with an empty library or combine
your processes with installed databases, for example your own baking process with ecoinvent's electricity.

You do not need to know any programming or database format. You fill in tables, step by step, and Cyclia checks
every entry.

### What Cyclia does for you
- **Gives every item an identity.** Each product, flow, process and method gets a unique identifier (UUID), the
  source you give, the author, the date of creation and change, and a revision number. Every change is kept in a
  change history.
- **Checks units.** You enter amounts in the unit you measured. Cyclia converts within the same kind of unit (650
  g becomes 0.65 kg, 1.08 MJ becomes 0.3 kWh) and refuses an amount that cannot be converted (kg for electricity).
- **Avoids duplicates.** If you try to create an emission that the library already has, Cyclia tells you to use
  the existing one, because that one already has its factors in the installed impact methods.
- **Never counts an unknown factor as zero.** If a flow has no characterisation factor in an impact category and
  you have not said why the category does not apply, the result of that category is marked **Incomplete** and the
  flow is listed. Nothing is hidden.

### Words used here
| Word | Meaning | Example |
|---|---|---|
| Product flow | Something made or used that stays in the economy | bread (kg), electricity (kWh), bread waste (kg) |
| Elementary flow | Something taken from or released to nature | carbon dioxide to air, water from a river |
| Process | One activity that makes one product, for a reference amount | bread baking, per 1 kg of bread |
| Exchange (line) | One input, credit, emission or resource of a process | 0.65 kg wheat flour per kg of bread |
| Waste treatment | A process that takes waste in | landfill of bread waste, per 1 kg of waste |
| Avoided product | A product your process makes that replaces production elsewhere | electricity recovered from waste heat |
| Characterisation factor | How much one unit of a flow adds to an impact category | 1 kg non-fossil methane = 27.0 kg CO2-eq |

### Start with the worked example
Press **Create the worked example (bread)** at the top of Your own data. Cyclia creates a small custom database
that shows every step:

- product flows: bread, wheat flour, electricity, bread waste;
- four processes: wheat flour from the mill, electricity from the local grid, landfill of bread waste (a waste
  treatment), and bread baking;
- bread baking uses 650 g of flour, 1.08 MJ of electricity (shown as 0.3 kWh) and sends 0.05 kg of waste to
  landfill, and releases 1 g of flour dust;
- an impact category "Example: climate change" with IPCC AR6 factors (carbon dioxide 1, non-fossil methane 27.0)
  and the decision that climate change does not apply to flour dust.

Per kg of bread the result is 0.65 x 0.4 + 0.3 x 0.5 + 0.05 x 0.02 x 27 = **0.437 kg CO2-eq**. The values are
illustrative and labelled so: use the example to learn, not to publish. Look through steps 1 to 7 with it, then
create your own database. If other impact methods are installed, flour dust shows as "unknown" in their
categories: that is step 6 at work, a decision still to make.

### The seven steps
The top of Your own data shows seven steps with a tick for each one that is done. Click a step to go to it.

### 1. Create a custom database
Give it a clear name ("Plant A, primary data 2025"), the author, the region and the period the data describe.
One database can hold many processes. **Export (JSON)** saves the whole database in one file, to archive it or to
send it to a colleague, who loads it with **Import**.

**Parameters of this database** are named values that amounts can use, such as `loss = 0.2` or
`distance = 120`. A parameter can be a formula of others (`dough_wet = dough * 1.1`). Change a value, save, and
every amount that uses it is recalculated. A change that would make an amount negative, or a formula that cannot
be calculated (an unknown name, a parameter that depends on itself), is refused with a message, and nothing is
changed.

A parameter can also have a **distribution** (lognormal with its GSD, normal, triangular or uniform), for a value
you know only roughly, such as a yield between 0.75 and 0.85. The full Monte Carlo (step 5, Uncertainty, "Full
Monte Carlo") then draws it in every iteration and recalculates every formula that uses it. All processes of the
database share the same draw, so a common assumption moves them together, as it should.

### 2. Product flows
List what your processes make, and the waste they send to treatment, each with the unit you count it in: bread in
kg, electricity in kWh, transport in t*km, a machine in unit. Use **Edit** to correct a name or category later;
the datasets that make the product are updated. The unit of a product that a process already makes cannot be
changed: create a new product instead.

**Units of your own.** If Cyclia does not know your unit, define it under "Units of your own":

- in a known kind of quantity, with its size: a "sack" of 50 kg (mass), a "load" of 8 t*km (transport);
- or as a **new kind of quantity**, which is its own base unit: a "seat", a "meal", a "patient day". Then define
  multiples of it if you need them: a "row" of 20 seats.

Amounts in your units are converted like any other: 2 sacks of flour become 100 kg. A unit in use cannot change
its size, because the amounts entered with it would change meaning; create a new one instead.

### 3. Elementary flows (only if needed)
Most emissions and resources (carbon dioxide, methane, water, land occupation) are already in the library. You
choose them directly in step 5. Create a flow here only for a substance the library does not have, for example a
new solvent:

- **Compartment** says where it goes or comes from: air, water, soil, or natural resource.
- **Subcompartment** gives more detail, such as "urban air close to ground" or "surface water". Choose
  "unspecified" if you do not know.
- **Unit**: kg for substances, m3 for water, m2*a for land occupation, m2 for land transformation, kBq for
  radioactivity.
- **CAS number** if the substance has one. Cyclia checks its check digit.

### 4. Processes
Describe one activity:

- **Name** and **reference product** (from step 2), with the **reference amount**: all lines of step 5 are for
  this amount. Usually 1.
- **Production** or **waste treatment**. A waste treatment process takes waste in, such as landfill or
  incineration; its reference product is the waste.
- **Location** (a code such as FR, PK or GLO for global), **technology**, **time period** and **data type**
  (primary when you measured it, secondary from literature or a database, estimate otherwise).
- **Source** of the data: a measurement campaign, a report, an invoice, a paper.
- **Data quality**: four ratings from 1 (very good) to 5 (very poor) for technology (TeR), geography (GeR), time
  (TiR) and precision (P), as in the EU PEF method.
- **Parameters of this process** (optional): values only this process uses, or that replace a database parameter
  of the same name for this process.

**Co-products and allocation.** Some processes make more than one product: cheese and whey, flour and bran, sawn
wood and sawdust. List the other products under "Co-products and allocation", with their amounts, and choose how
the inputs and emissions are shared:

| Method | Share of each product | Example |
|---|---|---|
| mass | its mass (kg) | 1 kg flour and 0.25 kg bran: 80 % and 20 % |
| energy | its energy content (MJ) | electricity and heat from one plant |
| economic | its amount x price | flour at 0.40 and bran at 0.16 per kg: 90.9 % and 9.1 % |
| manual | your shares, adding up to 1 | from a published study |

For mass and energy, Cyclia uses the unit when it is a mass or energy unit; otherwise give the kg or MJ per unit.
For **economic** allocation give the currency and the year of the prices, because prices change. **Physical
causality** shares by a property that physically causes the burdens, such as protein content for feed or machine
hours for parts: name the property and give its value per unit of each product.

**Compare allocation methods** shows, for the impact categories of step 4, the result per unit of each product
under every method that has its values. The total of the process stays the same; only its division changes.
Use it to show in a report how much your conclusions depend on the choice.
Cyclia then makes one dataset per product, each carrying its share of every line. Other processes, and your
models, can use each product separately. ISO 14044 asks to avoid allocation where possible, for example by
system expansion (an avoided product in step 5); use allocation when that is not possible, and give the source of
the prices or properties and your reason.

### 5. Inputs, waste, credits, emissions and resources
Add the lines of the selected process, per reference amount:

- **Input from a supplier**: from one of your processes, or from a dataset of the library (search it, for example
  "electricity France").
- **Waste to treatment**: choose the treatment process as supplier and enter the amount of waste. Cyclia handles
  the sign.
- **Avoided product (credit)**: a product your process makes that replaces production elsewhere.
- **Emission or resource**: search the library ("carbon dioxide", "water") or choose one of your own flows.

Enter the **amount** in the unit you measured; the reference unit of the supplier or flow is shown next to it.
Instead of a number you can write a **formula** of parameters, such as `dough / (1 - loss)` or `distance * 0.025`.
The table shows both the formula and its current value. Formulas use + - * / and ^ (power), brackets, and
functions such as min, max, sqrt, exp and log.
Then give the **uncertainty** if you know it:

- a **range**: normal (standard deviation), triangular (minimum, most likely, maximum) or uniform (minimum,
  maximum);
- **lognormal** with its geometric standard deviation (1.5 means the true value is within a factor 1.5, roughly
  two times in three);
- or the five **pedigree scores** (reliability, completeness, time, geography, technology, from 1 to 5) when you
  only know how reliable the data are. Cyclia turns them into a lognormal range.

Give the **source** of each line. **Edit** changes a line and counts its revision; **Remove** deletes it. A line
with a formula takes lognormal, normal or pedigree uncertainty, not a triangular or uniform range, because a
fixed range would not follow the formula when a parameter changes.

### The supply chain diagram
Below step 5, the diagram draws your processes and the library datasets they use, with an arrow for every input
(orange for waste sent to treatment, dashed blue for avoided products):

- **drag** a box to arrange the diagram; the position is kept;
- **click** a box to open that process in steps 4 and 5;
- to add an input, press **Connect**, click the supplier, then the process that uses it, and type the amount;
- **click an arrow** to edit that line;
- **Arrange automatically** places suppliers to the left of the processes that use them.

In step 3 of a model (Inventory), press **Diagram** to edit the model by drawing:
- drag a line's box to another stage column to move it there, or to "new stage" to create one;
- click its amount to change it, "credit" to make it an avoided product (or not), and × to remove it;
- click the box to open its row in the table;
- **+ Add a line** goes to the search.

### 6. Characterisation factors
Impact methods do not know the flows you created in step 3. For each of them, and each impact category you use,
choose one of two answers:

- **factor**: the value and its source, per kg or another unit of the same kind (a factor per g is converted to
  per kg). A factor of 0 with its source is a valid answer, for example for a gas with no warming effect.
- **does not apply**: the reason, for example "flour dust is not a greenhouse gas".

**Show factor status** lists every flow and category and marks each open decision; **Decide** fills the form for
it.

If you later change the name, compartment, subcompartment or CAS number of one of your flows, the factors you gave
it are put **under review**: a factor for a solvent emitted to air does not automatically hold for the same solvent
in water. Until you press **Confirm** (the factor still holds) or **Correct** (give the right one), the factor is not
used and results that contain the flow are marked incomplete.

You can also create **your own method** or impact category for an indicator no installed method has. Say what
happens to flows that get no factor in it:

- **unknown** (the default): results are incomplete until each flow in the inventory is decided;
- **no effect**: your list of factors is complete, as in published methods; give the reason.

Factors that installed methods give to library flows are not changed here. In your own method you can give a
factor to any flow.

### 7. Check and use
**Check database** lists errors to correct (an input whose supplier was removed, a process that cannot be
calculated) and what is still missing (sources, data quality, factor decisions). It also warns about entries that
look like a unit slip: material inputs far from the mass of the products (650 kg of flour for 1 kg of bread), or a
line more than 10,000 times the reference amount. If such a value is right, note why in the source.

**Versions and undo.** Every change of a process keeps the state before and after it.
- **Undo last change** reverses the latest change; pressing it again redoes it.
- **Versions of the selected process** lists every change with what changed, and can restore the state before or
  after any of them.
- **Deleted processes** brings back a process you deleted.

A restore that no longer fits (its supplier was deleted since, for example) leaves an open input that the check
reports, rather than failing silently.

**Who depends on a process.** Under the process form, Cyclia lists the processes that use it and the models of
every project that use it or them, so you know which results to recalculate after a change. **Add the selected process to the
open model** puts it in the inventory of the model you have open; set its amount there, in step 3. Your processes
are also found by the normal search of step 3. **Change history** lists every change of the selected process and
its lines, with time and author.

### What the results show
In step 5 (Interpretation), a category whose inventory contains a flow without a known factor shows
**Incomplete: n flow(s) without a known factor**. The Inventory tab lists those flows with their amounts, and the
checks report an error. The Word report and the Excel workbook say the same. The EPD check does not pass until
every factor is decided. Give the factors or record why the category does not apply, and calculate again.

### Questions
- **Can I use my processes together with ecoinvent?** Yes. Inputs can come from any installed dataset, and your
  processes appear in the normal search.
- **Can I change data later?** Yes. Every product, flow, process, line and factor can be edited; dataset
  identifiers stay the same, so your models stay linked. Every change is recorded.
- **Why can I not change the unit of a product?** Processes already use it; a different unit would change every
  amount. Create a new product.
- **A library database I used was removed.** The inputs from it become "inputs without a supplier" and the check
  lists them. Choose a new supplier.
- **Can I make one process with several products?** Yes: add co-products in step 4 and choose the allocation.
  Or model the extra product as an avoided product (system expansion).
- **Do parameters vary in Monte Carlo?** Parameters of your own data are fixed values. Give the uncertainty on
  each line (step 5). Model parameters (step 2) can have their own distributions.

## Toolbox

- **Scientific Benchmark Centre** (top of the Validation tab): one table of all the evidence for Cyclia's
  calculations in your installation. For every check and every installed method it shows:
  - the reference and the reference result;
  - Cyclia's result;
  - the absolute, relative and maximum differences;
  - the missing flows;
  - the status, the date and the Cyclia version.

  Only a check that ran here, with every result within its tolerance, shows **Validated**. "Not run" means it has
  not been run yet; "Not available" means the software it needs (Brightway) is not installed. Neither is
  validation. **Run the IPCC 2021 check** calculates 1 kg of each of 14 greenhouse gases and compares the result
  with the published IPCC AR6 values. The validation suite, the Brightway comparison and the ecoinvent benchmark
  add their results to the table when they finish. **Export (Excel)** saves the table for a report or a reviewer.
  When you import an official AWARE, LANCA or USEtox package, the Centre checks its structure: completeness,
  units, ranges, the world fallback and a named source. It shows "Package checked" or what is missing. Checking the
  factor values themselves needs the package's own reference results, so these rows are never "Validated". The
  Word report includes this table and the ISO 14044 critical review checklist, checked automatically from your
  study, in an annex.
- **Validation**: the validation suite runs 35 small product systems with exact known answers and saves a
  Word report to attach to a thesis or paper. The **independent cross-check** recalculates datasets of your
  library and the models of your project with a second implementation (other solver, matrices rebuilt from the
  tables) and shows the largest difference; save its Excel report for a reviewer. The **comparison kit** exports a
  database you may share, with Cyclia's results and scripts that calculate the same in Brightway and openLCA and
  write a comparison report. **Factor matching** compares
  Cyclia's characterisation factors with another tool's, flow by flow: an openLCA JSON-LD export of the method,
  a Brightway export (script `engine/tools/brightway_export_factors.py`) or a CSV. It lists flows that differ, flows
  only one tool characterises and rows that match no flow, and shows what each difference does to the results of
  your models. Add the other tool's results for the same models (CSV: model, category, value) to split the
  difference into the part caused by the factors and the rest. Try it with
  `factor_matching_demo_factors.csv` and `factor_matching_demo_results.csv` from
  https://github.com/pdnaeem/cyclia/tree/main/docs/examples on the feature demo. **Verify a reproducibility bundle** recalculates someone
  else's bundle and checks that data, methods and results are identical.
- **Background scenarios**: edit prospective or consequential versions of the database (scale emissions or
  inputs over years, swap suppliers), import premise or Activity Browser scenario files. **Marginal suppliers**
  lists every market in the supply chain of the open model with its suppliers, marks the ones that look
  constrained (recycled, by-product, waste-based) and proposes an unconstrained one. Confirm or change each choice
  with what you know about the market, then create a consequential scenario from it.
- **Chemicals and site factors**: screening toxicity factors for a substance that has none (from its
  properties, with a multimedia fate model), and site-specific factors for your own emissions.
- **Regional methods**: **AWARE** water scarcity and **LANCA** land use, calculated with the inventory of every
  process at its own location. Import the official factor tables (**Show template** gives the columns; templates are also in
  https://github.com/pdnaeem/cyclia/tree/main/docs/examples); **Load demo
  factors** only shows the workflow and its results mean nothing. For AWARE, give in the same tab the location
  of your own water use (country, region code such as ES-AN, or watershed) and its type of use; it is saved with
  the model. Each result shows
  how much of the water or land was characterised exactly, with a fallback (country, then world), or not at all.
  Monthly AWARE factors (a month column in the table) are used with a 12-month water use profile of the model;
  watershed polygons (GeoJSON) find the basin from the site's latitude and longitude. The soil quality index can be
  aggregated from the four LANCA indicators with the normalisation references of the method version you follow.
- **Social screening, and the subcategory assessment (Type I).** The lower part of the tab is the assessment
  proper, after the UNEP 2020 guidelines:
  - choose a stakeholder category (workers, local community, value chain actors, consumers, society or children)
    and one of its subcategories;
  - score each organisation of your product system against a performance reference point (the law, ILO
    convention or norm): +2 ideal, +1 progressive, 0 compliant, -1 risky, -2 very poor;
  - give its weight, for example worker hours per functional unit.

  Cyclia reports:
  - per subcategory, the weighted score, the coverage against the total you give, the share of site-specific data
    and the hotspots (scores of -1 or -2);
  - per stakeholder, the lowest score and the subcategories not yet assessed.

  Exclude a subcategory with its reason (one per line) when it does not apply. Scores are not added up into a
  single number. The risk screening above it is a screening, not a social LCA: PSILCA and SOCA data in openLCA JSON-LD are imported
  directly (social aspects, activity values, risk levels, raw values); PSILCA sectors are assigned to your datasets
  with a mapping table. A screening of social risks along the supply chain: worker hours per functional unit and
  risk hours per stakeholder and indicator, with the processes that cause them. Import your licensed PSILCA or
  SOCA extract or your own data with the template; Cyclia ships no social data. Process coverage shows how many
  processes of the supply chain have data; totals are lower bounds. Add a default row (match `*`) to estimate the
  worker hours of processes without data and get a worker-hour coverage. Avoided products are shown separately.
- **Material flows** (Material flows linked to the LCA): charge the production process on its **virgin input
  only**, so recycled material is not counted again as primary material. Give each recycling process a **credit**:
  link the primary material its output replaces, with a substitution ratio (1 replaces it one to one; lower for
  quality losses). The results separate primary supply, production and use, recycling, losses and credits, and give
  the net total per year and cumulatively.
- **Material flows**: build the system in tables and a diagram (drag the boxes), or edit the JSON. **Material flows
  linked to the LCA** links MFA processes to datasets or models and gives the impacts of the material system year by
  year. Dynamic material flow analysis (MFA) of a material system over years: processes, in-use stocks with
  lifetimes, sinks and recycling loops, with stocks, flows, losses, recycling rate and recycled content per
  year and a mass-balance check. Start from **Load example** (aluminium in buildings, invented numbers). The
  **Material Circularity Indicator** of the Ellen MacArthur Foundation is calculated for a product from its
  recycled content, collection and efficiencies.
- **Database explorer**: browse every dataset of the library with its key and UUIDs, inputs and their suppliers,
  the datasets that use it, inputs without a supplier and why, elementary flows with uncertainty, and data
  quality. Click a supplier or a user to move along the supply chain. Tick "only datasets with unresolved inputs"
  to find gaps.
- **Templates**: your saved templates.
- **Python, R and other software**: clients to run Cyclia from scripts, and Brightway import.
- **Teaching**: exercises with automatic checking and an answer key for teachers.
- **Database versions**: compare two databases (for example two ecoinvent versions) on the datasets your
  project uses or on a sample, with the median change per category and the largest changes, and move the open
  model and every model nested in it to the new version in one step, with results before and after and one
  button to undo the whole migration.
- **Allocation**: every model of the project with its allocation rule and share, co-products, avoided products,
  module D, where it is used, and what to check (for example allocation together with system expansion).
- **Project overview**: all models of the project with their inventory size, data quality and review status;
  **Calculate all models** adds their results.

---

### Your own data
Processes, flows and factors that no database has. See [Your own data](#your-own-data-custom-data-entry).

## Recipes by sector

**Construction product or building element (EN 15804+A2)**: template "External wall"; stage system EN 15804;
stages A1-A3, A4, A5, B, C1-C4, D; credits in D; step 6 EPD with requirements check.

**Food and agriculture**: template "Arable crop"; inputs per kg at the farm gate (fertiliser, diesel, seed,
pesticides); field emissions (N2O, NH3, nitrate, phosphate) as direct emissions, using IPCC Tier 1 or a field
model via "External model emissions"; allocation between grain and straw by mass or price.

**Textiles**: template "Cotton T-shirt"; functional unit per use or per item over its life; include the use
phase (washing, drying); fibre, spinning, weaving, dyeing and sewing; end of life.

**Energy**: template "Solar PV electricity"; functional unit 1 kWh delivered; spread manufacturing over
lifetime production with parameters (yield, lifetime, degradation).

**Packaging (PEF)**: template "Beverage packaging"; per litre delivered; recycling credits with an avoided
product; EF 3.1 with normalisation and weighting.

**Water and waste**: template "Wastewater treatment"; per m3 treated; electricity, chemicals, direct N2O and
CH4, sludge treatment.

**Chemicals**: template "Chemical product"; per kg at the plant gate; feedstocks divided by the yield, process
energy and steam, process waste.

---

## Publishing with Cyclia

1. Use a licensed or published database, not the tutorial or demo data.
2. Run **Validate against ecoinvent** (step 1) and the **validation suite** (Toolbox) and keep the reports.
3. Fix every error in **Checks**; explain warnings in the limitations.
4. Run uncertainty and sensitivity, and use paired Monte Carlo for comparisons.
5. Use the methods paragraph of the Word report, and state the software version.
6. Cite Cyclia (Help > About copies the citation and BibTeX): Rehman, N. U. (2026). *Cyclia: open-source
   life cycle assessment software for researchers* [Computer software]. https://doi.org/10.5281/zenodo.23853747
7. For a public comparison, organise a critical review panel (ISO 14044 6.3).

---

## Troubleshooting

| Problem | What to do |
|---|---|
| ecoinvent login: 401 / not accepted | Use your ecoinvent username, not the e-mail; set an ecoinvent password with "Forgot password" if you log in through your university; test the login on ecoquery.ecoinvent.org; or import the downloaded folder instead |
| The search finds nothing | Use fewer or shorter words (`cotton`, not `cotton fibres organic Indian`); check the database filter; try "market" |
| A unit is not offered | The dataset's unit is not convertible (for example kg to m3). Convert with a formula: `volume_m3 * 2400` for concrete in kg |
| A line is marked missing | Its dataset is not in your library (a project from someone else). Import that database, or press Replace |
| Result is negative | An avoided product larger than the burdens, or biogenic carbon uptake in a biogenic category. Check the Credit ticks and the stages |
| A category says "no matching factors" | The method and database use different flow names. Import the method made for your database (ecoinvent LCIA file) or a flow mapping |
| Monte Carlo takes long | Use foreground uncertainty, or fewer iterations; full Monte Carlo can be cancelled |
| "The calculation engine is not responding" | Restart Cyclia. If it repeats, Help > About > Export diagnostics and send the file to support@niellosoft.com |
| Windows says "unknown publisher" | Click More info, then Run anyway (the installer is not yet signed) |

---

## Limitations

Cyclia is honest about what it does not do (yet):

- Social LCA is a risk screening with data you import; Cyclia ships no PSILCA, SOCA, AWARE or LANCA data.
  MFA is a separate workspace and is not linked to the LCA model. Life cycle costing covers the costs you enter
  (with replacements and cost types); it is not a full ISO 15686-5 study.
- The EPD programme profiles are not approved by the programme operators.
- IMPACT World+, official USEtox 2 factors and biodiversity methods are not built in (import them as CSV
  methods where the licence allows); dynamic characterisation covers climate only.
- One user per project file at a time; there is no shared server for teams.
- Field emission models (fertiliser N2O, pesticide fate) are not built in beyond IPCC Tier 1 in the crop
  template; use "External model emissions" for other models.
- Regionalised impact assessment uses the location code of each process. AWARE and LANCA use sub-national
  codes when the dataset has them, else the country, then the world value; the generic regional factors use the
  country.
- The macOS version runs on Apple silicon only and does not update itself until the app is signed.
- A study is only as good as its data: the database must cover your sector and region.
- The tutorial and demo data are illustrative and must never be published.

Questions and ideas: https://github.com/pdnaeem/cyclia/discussions. Private support: support@niellosoft.com.
