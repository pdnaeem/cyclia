# Cyclia user guide

Cyclia walks you through a life cycle assessment in the order of ISO 14040/44. The six steps on the left
tick themselves when complete, and the bar above them shows how far the study is. The sentence at the top
always shows what your study assesses; dashed parts are still missing.

**Guidance.** At the top of every step a card explains what the step means, gives an example, lists common
mistakes and shows a checklist that ticks itself. "Show me" scrolls to the right field and highlights it.
The bar at the bottom of each step leads to the next one. "Guidance on/off" (top right) hides the cards.

**Welcome screen.** On first start Cyclia asks how much LCA you have done and how you want to start:
"Learn with a first study" prepares a project with the tutorial database and guides you from step 2;
"Explore the full demo" loads seven ready models; "Start my own study" opens an empty project. Help >
About > "Show the welcome screen again" brings it back.

"Help, tutorial and glossary" (bottom left) has a guided tutorial, a feature tour and plain-language
definitions; every "?" opens the matching term. Help > About shows the author, the citation and buttons to
copy it as text, BibTeX or a ready sentence for your methods section.

## First study in 15 minutes

1. **Project & data**: create a project, open "Tutorial database" and add it.
2. **Goal & scope**: functional unit 1 m2 of external wall, goal, boundary cradle-to-gate, stages
   "EN 15804", Save.
3. **Inventory**: search "concrete", select it, type `0.2` with unit `m3`, stage "A1", Add. Add steel and
   a lorry transport the same way.
4. **Impact assessment**: tick "Cyclia built-in: IPCC 2021", choose "Foreground data quality", Calculate.
5. **Interpretation**: look at Contributions, Supply chain and Checks.
6. **Report**: write a conclusion, create the Word report.

## Try everything with the demo

Step 1, "Load the full demo", creates the project "Cyclia feature demo" with an illustrative database and
seven models. Help > Feature tour then takes you to each feature. The demo data must not be cited.

## 1. Project & data

**The library.** Databases and methods are imported once per computer and shared by all projects.
A project file (.lca) holds only your models, so you can e-mail it; the receiver needs the same databases
in their library (Cyclia tells them which) and the lines link themselves.

**Databases.** ecoinvent through your login or an extracted ecoSpold02 folder; openLCA JSON-LD (USLCI,
Agribalyse, ELCD and method packages such as EF 3.1); SimaPro CSV exports; ILCD (Ökobaudat, EF datasets);
ecoSpold1. After an import, "Link missing suppliers" appears if some inputs point to another database
(typical for USLCI or Agribalyse). Link each product once to a dataset in another database.
"Check" tests the matrix (random solves, missing suppliers, flows without factors).

**Methods.** ecoinvent's LCIA Excel file, JSON-LD method packages, any CSV (with optional location for
regional factors such as AWARE), plus the built-in IPCC 2021 method. If a method was written for other
flow names, import a flow mapping file (FEDEFL/GLAD format is read directly).

**One click with your ecoinvent login.** Under "ecoinvent with your licence", log in, pick the version and system
model and press "Download, connect and validate": Cyclia downloads the release and its LCIA methods, imports
them, downloads ecoinvent's own LCIA results and compares Cyclia with them. "Validate only" repeats the
comparison for a release that is already installed.

**Validate against ecoinvent (automatic).** Import ecoinvent and its LCIA file, download the cumulative LCIA
results file of the same version and system model from ecoquery (Files), choose it under "Validate against
ecoinvent" and press Run. Cyclia samples datasets from every group, compares every category, says what to
check where results differ, and saves an Excel report.

**Benchmark.** Before publishing, compare Cyclia with reference results (ecoinvent's LCIA results, an
openLCA or Brightway export) for a set of datasets; the table shows the deviation per row.

## 2. Goal & scope

Functional unit, goal, reasons, application, audience, comparative assertion, boundary, stage system,
geography, period and cut-off are written into the report. **Allocation**: enter a share, or choose
mass / economic / energy and fill this product's value and the co-products; the share is computed.
**Time**: tick dynamic GWP to set a year for each line. **Parameters** (e.g. `thickness`) can be used in
amounts; give them a distribution to include them in uncertainty and Sobol analysis. **Scenarios** are
named sets of parameter values. "Duplicate as alternative" copies a model to build a variant.

## 3. Inventory

Four sources: datasets, direct emissions and resources, your other models (sub-assemblies or editable
processes), and EPD values. Type an amount or a formula (`thickness * 1800`) in any compatible unit.
Set the stage, tick "Avoided product" for credits (module D in EN 15804), rate data quality (1 best,
5 worst) and note the source. "Replace" swaps the dataset of a line, keeping its amount. "Copy as
editable process" makes a dataset editable (e.g. change its electricity mix). Undo reverts the last
change. The flow diagram shows the model by stage. Excel template, import (all rows checked first) and
export help with large inventories.

## 4. Impact assessment

Tick categories (one method family per indicator), optionally a scenario, normalisation set and
sensitivity range, and an uncertainty mode: foreground (seconds) or full Monte Carlo with database
uncertainty (minutes for ecoinvent; runs in the background, cancel any time).

## 5. Interpretation

Results with 95 % intervals and module D; contributions by input, process and flow; the supply chain
tree and flow chart; stages; sensitivity (inputs, parameters, Sobol indices); uncertainty histogram;
dynamic climate; the inventory results and flows without factors; ISO checks with links to the step to
fix; comparisons of models (with paired Monte Carlo) and of scenarios.

## 6. Report

Conclusions, limitations, recommendations and critical review text go into the Word report, which
follows ISO 14044 and ends with a methods paragraph for your manuscript and the inventory results.
Excel exports every table. "Back up project file" saves the .lca file.

## 7. More tools

**Step 2.** "Start from a template" creates a complete model (building element per EN 15804, packaging,
arable crop with IPCC Tier 1 field emissions, solar PV electricity) and links every line to the best dataset
in your library. Save any model as your own template. "Versions and lock": save named versions, compare
two of them line by line, restore one, and lock a reviewed model.

**Step 3.** "From a paper or table" turns a table from a PDF, Word, Excel or pasted text into lines; you
confirm the dataset of every row. "External model emissions" adds the output of a leaching, runoff or
field-emission model (CSV with year, flow, compartment, amount, unit). Comments can be attached to the
model or to one line ("note" in each row).

**Step 4.** "Background database" applies a prospective scenario (with a target year) or a consequential
scenario before calculating.

**Step 5.** "Map" shows where impacts occur; "Explore parameters" runs sweeps, optimisation and Pareto
trade-offs; "PEF" lists the most relevant categories, stages, processes and flows; "Inventory results"
shows toxicity coverage and site-specific factors.

**Step 6.** EPD (EN 15804+A2) with a requirements check, ISO 14067 report, GHG Protocol workbook, the
critical review checklist, a reproducibility bundle, and exports for Brightway and openLCA.

**Toolbox.** Validation suite and bundle verification; background scenario editor and marginal supplier
finder; screening toxicity factors for your own chemicals and site-specific factors; templates; Python and
R clients and Brightway import; teaching exercises with an answer key (teacher view).

## Support

Help > About and support > "Export diagnostics" creates a zip with the error log and system information
(no project data) to send to support@niellosoft.com.
