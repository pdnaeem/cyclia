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
11. [Toolbox](#toolbox)
12. [Recipes by sector](#recipes-by-sector)
13. [Publishing with Cyclia](#publishing-with-cyclia)
14. [Troubleshooting](#troubleshooting)
15. [Limitations](#limitations)

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

**Link missing suppliers.** Some databases (USLCI, Agribalyse) refer to products from other databases. After
the import, "Link missing suppliers" lists them; link each product once to a dataset you have. **Check**
tests the database: solvable matrix, missing suppliers, flows without factors.

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
- **Geography** and **time period** the study represents.
- **Cut-off criteria**: what you leave out, for example flows below 1 % of mass and energy.
- **Data quality requirements**: what data you need (primary or secondary, region, year, technology).
- **Key assumptions**.

### Allocation

If your process makes more than one product, say how burdens are shared. Choose **mass**, **economic** or
**energy** and enter the value for your product and for each co-product; Cyclia computes the share. Or enter
a share in % yourself. The text field "Allocation procedure" goes into the report. The alternative, system
expansion, is done in step 3 with an avoided product.

The share applies to every line of the model. If only one process of your system is multi-functional (for
example the cotton gin, which also gives cottonseed), model that process as its own model with the
allocation, and use it as a line in the main model (tab "My models and processes").

### Time

Tick **dynamic GWP** to give each inventory line a year of emission. Step 5 then shows climate impact over
time (Levasseur et al., 2010), useful for long-lived products and biogenic carbon.

### Parameters and scenarios

A **parameter** is a named number you can use in amounts, for example `distance_km = 300`. Formulas use
`+ - * / **`, parentheses and `min`, `max`, `abs`, `round`, `sqrt`, `exp`, `log`, `log10`, `if_(condition,
a, b)`. Parameter names use letters, digits and `_`, start with a letter, and cannot be a reserved word.
Give a parameter a distribution (lognormal, normal, triangular, uniform) to include it in uncertainty and
Sobol analysis. A **scenario** is a named set of parameter values (for example "long distance", "recycled").

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
- **Data source** and **note**: where the number comes from, and comments for co-authors.
- **Replace**: swap the dataset, keep the amount.
- **Remove** and **Undo** (top).

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
  1,000 iterations are usual.

Press **Calculate**.

---

## Step 5: Interpretation

Interpretation (ISO 14044 4.5) answers three questions: what drives the result, how reliable is it, and what
can be concluded.

- **Results per functional unit**: the total per category, with module D separate, 95 % intervals after
  Monte Carlo, and normalised and weighted values when chosen. Click a row to choose the category for the
  tabs below.
- **Contributions**: share of each inventory line, each background process (hotspots) and each elementary
  flow. The top contributors are where better data and improvements matter most.
- **Supply chain**: the tree of where the impact comes from, and a flow chart (Sankey).
- **Stages**: impact per life cycle stage.
- **Sensitivity**: the effect of changing each input by the chosen %, parameter sensitivity, and Sobol
  indices (which uncertain inputs explain the spread).
- **Uncertainty**: histogram and intervals from Monte Carlo.
- **Dynamic climate**: climate impact over time, when dynamic GWP is on.
- **Map**: where impacts occur, by country of the processes.
- **Explore parameters**: sweeps (result as a parameter changes), optimisation (best parameter values under
  constraints) and Pareto fronts between two categories.
- **PEF**: most relevant categories, stages, processes and flows by the PEF 80 % rule.
- **Inventory results**: all elementary flows, flows without a factor, toxicity coverage.
- **Checks**: completeness, consistency and sensitivity checks (ISO 14044 4.5.3). Each check links to the
  step where you fix it. Errors must be fixed; warnings and notes should be explained in the report.
- **Compare**: models side by side (with paired Monte Carlo: the probability that A is lower than B) and
  scenarios of one model.

**A difference is only meaningful when it is larger than the uncertainty.** Use the paired Monte Carlo in
Compare before you claim that one product is better.

---

## Step 6: Report

- **Conclusions, limitations, recommendations** and **critical review**: write them and press **Save
  text**.
- **Create Word report**: a report structured as ISO 14044: goal and scope, inventory with parameters and
  data quality, impact assessment, interpretation with checks and sensitivity, a methods paragraph you can
  paste into a thesis or article, the inventory results and references (including Cyclia).
- **Export results to Excel**: every table.
- **Write methods paragraph**: the methods text alone, to copy.
- **Standards and declarations**: EPD per EN 15804+A2 (modules A1 to D, with a requirements check), an ISO
  14067 carbon footprint report and a GHG Protocol workbook.
- **Critical review checklist**: the ISO 14044 items a reviewer checks, with your notes, exported to Excel.
- **Share, reproduce, exchange**: a reproducibility bundle (models, settings and fingerprints of the
  databases and methods), and exports to Brightway and openLCA.

---

## Toolbox

- **Validation**: the validation suite runs 35 small product systems with exact known answers and saves a
  Word report to attach to a thesis or paper. **Verify a reproducibility bundle** recalculates someone
  else's bundle and checks that data, methods and results are identical.
- **Background scenarios**: edit prospective or consequential versions of the database (scale emissions or
  inputs over years, swap suppliers), import premise or Activity Browser scenario files, find marginal
  suppliers.
- **Chemicals and site factors**: screening toxicity factors for a substance that has none (from its
  properties, with a multimedia fate model), and site-specific factors for your own emissions.
- **Templates**: your saved templates.
- **Python, R and other software**: clients to run Cyclia from scripts, and Brightway import.
- **Teaching**: exercises with automatic checking and an answer key for teachers.

---

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
   life cycle assessment software for researchers* [Computer software]. https://doi.org/10.5281/zenodo.23862359
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

- No social LCA and no life cycle costing.
- Field emission models (fertiliser N2O, pesticide fate) are not built in beyond IPCC Tier 1 in the crop
  template; use "External model emissions" for other models.
- Regionalised impact assessment uses the country of each process; factors per sub-national region are not
  supported.
- The macOS version runs on Apple silicon only and does not update itself until the app is signed.
- A study is only as good as its data: the database must cover your sector and region.
- The tutorial and demo data are illustrative and must never be published.

Questions and ideas: https://github.com/pdnaeem/cyclia/discussions. Private support: support@niellosoft.com.
