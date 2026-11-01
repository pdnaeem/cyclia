# Cyclia: calculation methods

This document describes how Cyclia 1.1 computes results, so that a study can be reproduced and reviewed.
Cite the software as: *Cyclia v1.1 (NielloSoft, 2026). Life cycle assessment software.*

## 1. Inventory model

Background databases are stored as a technosphere matrix **A** (products x processes) and a biosphere
matrix **B** (elementary flows x processes), following the ecoSpold2 sign convention:

- the reference product amount of each process is on the diagonal of **A** (negative for waste treatment,
  whose reference flow is an input);
- technosphere inputs enter **A** with a negative sign;
- elementary exchanges enter **B** as given; resources and emissions are both positive, and the
  characterisation factor carries the sign of the effect (e.g. -1 for biogenic CO2 uptake).

For a demand vector **f**, the scaling vector is **s** = **A**⁻¹ **f** (sparse LU factorisation, SuperLU),
the inventory is **g** = **B s** + **d**, where **d** holds the direct elementary flows of the foreground
model, and the characterised result is **h** = **Q s** + **C d** + Σ EPD values, with **Q** = **C B**.
Values below 10⁻¹³ of the largest scaling factor are set to zero to remove round-off.

## 2. Foreground models

A model is a product system with a functional unit. Each line is an amount per functional unit, in any
unit convertible to the dataset's unit (mass, energy, volume, area, length, transport, time, land
occupation; conversion factors in `engine/units.py`). Lines can be:

| Line type | Contribution |
|---|---|
| Dataset | adds its amount to **f** |
| Elementary flow | adds its amount to **d** |
| Sub-model | expanded recursively, scaled by amount / functional-unit amount of the sub-model |
| EPD values | adds amount x declared value per category; no supply chain and no inventory |

**Avoided products** enter with a negative amount (system expansion, ISO 14044 4.3.4.2).
**Allocation**: all burdens of a model are multiplied by its allocation share, given directly in %, or
computed from co-product properties as *main / (main + Σ co-products)* by mass, economic value or energy.
**EN 15804 module D**: when the EN 15804 stage system is chosen, lines whose stage starts with "D" are
calculated but reported separately; the reported total covers modules A to C.

**Parameters and formulas**: an amount may be a formula of named parameters (safe parser; operators
+ − × ÷ ^, comparisons, `min max abs round sqrt exp log log10 sin cos tan if_`). Project parameters
apply to all models, model parameters override them, and scenarios override values by name. Circular
definitions are rejected.

## 3. Impact assessment

Characterisation factors are stored as given and matched to library flows by, in order: flow UUID;
canonical name + compartment + subcompartment; canonical name + compartment (when the factor has no
subcompartment). A factor for the subcompartment "unspecified" applies to that subcompartment only, as in
ecoinvent's own results (long-term and ocean emissions keep no factor when the method gives none). Canonical names are lower case with "x (y)" read as "x, y"; compartments from ILCD,
openLCA, FEDEFL and SimaPro vocabularies are mapped to the ecoinvent terms *air, water, soil,
natural resource* and their subcompartments (`engine/canon.py`). Flow mapping files (FEDEFL/GLAD
format or the Cyclia template) add factors for flows of another nomenclature, multiplied by the
conversion factor. Matching is repeated after every import, so the order of imports does not matter.
Factors that match no flow are kept and listed.

**Regional factors** (a location column) replace the global factor for processes located there:
**Q**[k, j] += (CF_reg − CF_glob) × **B**[f, j] for each process *j* in that location. The ecoinvent
benchmark switches regional factors off, because ecoinvent's published LCIA results are not regionalised.

**Normalisation and weighting** (optional): normalised = result / reference; weighted = normalised x weight;
single score = Σ weighted, reported only when every selected category has a weight.

**Built-in method** "IPCC 2021 GWP100 (EN 15804+A2 split)": GWP100 from IPCC AR6 WG1 Table 7.15 for
CO2 (1), CH4 fossil (29.8), CH4 non-fossil (27.0), N2O (273) and ten fluorinated gases. Biogenic CO2 is
counted −1 at uptake and +1 at release; land use change CO2 and CH4 form a separate category; the total
is the sum. Other halocarbons are not characterised; use EF 3.1 for formal EPD work.

## 4. Interpretation

- **Contribution analysis**: by model line (unit result x amount), by process (**Q**[k, j] s_j), by
  elementary flow (C_k,i g_i), by life cycle stage.
- **Supply chain tree**: cumulative impact of each input and, recursively, of its suppliers
  (amount x unit result of the supplier), plus the direct emissions of each node.
- **Sensitivity check**: each line ±x % (linear), each line over the 95 % range of its data-quality
  lognormal, each free parameter ±x % (full recalculation).
- **Completeness and consistency checks** (ISO 14044 4.5.3): missing goal and scope elements, empty or
  zero lines, missing sources, unrated data quality, mixed system models and databases, unlinked
  suppliers, regional mismatch, mass balance (when the product mass is given), categories with no
  matching factors, flows characterised under another name, contributors below 1 % (cut-off candidates),
  dominant contributors.

## 5. Uncertainty

**Data quality**: each line has a pedigree score (reliability, completeness, temporal, geographical,
technological). The variance of ln is the basic variance (0.0006; 0.12 for transport; 0.04 for
emissions other than CO2) plus the pedigree variances of the ecoinvent v3 guideline (Weidema et al.
2013). The line amount is lognormal with this sigma and its median at the entered value.

**Foreground Monte Carlo**: line amounts and parameter distributions (lognormal by GSD, normal,
triangular, uniform) are sampled; results are recomputed from the unit results of each line.

**Full Monte Carlo**: in each iteration every exchange of the database with uncertainty information
(ecoSpold2 lognormal with pedigree-widened variance, normal, triangular, uniform; openLCA and SimaPro
equivalents) is sampled, **A** is refactorised, and every compared model is solved on the same random
background, so differences are paired. Reported: mean, median, SD, 2.5 and 97.5 percentiles, CV, and for
comparisons the probability that one option is lower than the other. A singular random draw falls back
to the static matrix for that iteration.

**Global sensitivity**: first-order (Saltelli et al. 2010) and total (Jansen 1999) Sobol indices for the
foreground uncertainty (line amounts and parameter distributions), N (d + 2) evaluations, with outputs
centred before estimation.

## 6. Dynamic climate impact

Optional time-dependent GWP (Levasseur et al. 2010) with a fixed horizon H (default 100 years) from the
study start. A pulse of gas *i* in year *t* is weighted by AGWP_i(H − t) / AGWP_CO2(H). CO2 uses the
impulse response function of Joos et al. (2013); CH4 (lifetime 11.8 years) and N2O (109 years) use single
exponential decay scaled to their AR6 GWP100. All upstream emissions of a line are assigned to that line's
year. The static equivalent is reported alongside.

## 7. Background scenarios (prospective and consequential)

A background scenario is a list of rules applied to the exchanges of the library before the matrix is
factorised; the stored database is never changed. Datasets are selected by name (with optional location)
or by explicit choice.

* *Scale an emission*: every biosphere exchange of the selected datasets whose canonical flow name
  contains the given text is multiplied by a factor.
* *Scale an input*: every technosphere input of the selected datasets from a dataset whose name or product
  contains the given text is multiplied by a factor.
* *Replace suppliers*: in the selected datasets, the inputs of a product are summed and redistributed to
  new suppliers with shares that add up to one. With a single marginal supplier this is the consequential
  substitution of the average market mix (Weidema et al. 2009).

Factors are a number or a set of (year, factor) pairs; at a target year *y* the factor is interpolated
linearly between factor 1 at the base year and the given years, and held constant after the last year.
This follows the idea of prospective background databases (Sacchi et al. 2022) in a transparent, rule-based
form; databases generated with premise can also be imported directly (e.g. as SimaPro CSV). The rules
that were applied and the number of exchanges changed are reported with every result. Supply chain trees
are drawn from the unmodified database.

**Scenario files.** Scenario difference files in the Activity Browser superstructure format, which premise
also writes from integrated assessment model pathways (e.g. REMIND, IMAGE), are read row by row: the consumer
("to") and supplier ("from") are matched to library datasets by name, reference product and location (then
name and location), and elementary flows by canonical name and compartment. Each scenario column becomes a
background scenario whose exchanges are set to the given amounts; missing technosphere and biosphere
exchanges are added. Rows that cannot be matched are counted and reported.

## 8. Site-specific factors and toxicity

**Site-specific factors** replace the generic factor *C_kf* of a flow *f* in category *k* for the model's
direct (foreground) emissions only: h = Q s + C_d d, where C_d equals C except for the overridden entries.
Background emissions keep the generic factors. Every override is listed in the results and the checks.

**Toxicity coverage.** For categories whose name contains "tox", Cyclia lists the emitted substances (air,
water, soil) without a factor, excluding substances conventionally covered by other categories
(greenhouse gases, SO2, NOx, NH3, particles, nutrients, water). Results are then lower bounds.

**Screening factors for own chemicals.** For chemicals without official USEtox factors:

* Fate: steady-state Level III multimedia model with air, freshwater, soil and sediment and the EQC
  standard environment of Mackay et al. (1996): fugacity capacities Z (air 1/RT, water 1/H, solids
  Koc·foc·ρ·Z_w/1000, aerosol 6×10⁶/P_L·Z_air), D values for air-water and air-soil exchange (two-film
  diffusion, rain dissolution, wet and dry particle deposition), soil runoff, water-sediment diffusion,
  deposition, resuspension and burial, degradation (ln 2 / half-life) and advection. Koc defaults to
  0.41·Kow (Karickhoff 1981); BCF to log BCF = 0.85 log Kow − 0.70 (Veith et al. 1979). The fate factor
  FF_ij (days) is the mass in compartment *j* at steady state per kg/day emitted to *i*; the mass balance
  is checked (removal = emission) and reported.
* Freshwater ecotoxicity (CTUe/kg): FF_i,w · XF_w · EF_w with XF_w the dissolved fraction (suspended solids
  and DOC with K_DOC = 0.08·Kow) and EF_w = 0.5/HC50 (Rosenbaum et al. 2008).
* Human toxicity (CTUh/kg): intake fraction from inhalation (13 m³/day), drinking water (2 L/day) and fish
  (30 g/day, BCF) for the population of the model region, times EF = 0.5/(ED50 · 70 kg · 70 years · 365 days).

These are screening estimates on a generic landscape, not official USEtox factors; report them as such.

**Official toxicity factors by CAS number.** Any factor table with a CAS column (the USEtox 2.x results, other
published lists) can be imported after mapping its columns once (category, unit, compartment). CAS numbers
are normalised (leading zeros, numbers without hyphens) and verified with the CAS check digit; each factor is
attached to the library flows with the same CAS number in that compartment, otherwise to the substance name,
which is re-matched whenever databases are added.

**External model emissions.** Time series from another model (leaching, runoff, field emissions, a fate
model) are read as (year, flow, compartment, amount, unit) and become direct flows per functional unit,
one per flow and year (feeding the dynamic GWP) or summed per flow.

## 9. Exploring parameters

A sweep evaluates the full model (h = Q s + C_d d + fixed values) on a grid of one or two parameters.
Optimisation minimises one category over parameter bounds with differential evolution (Storn and Price
1997; scipy), with upper limits on other categories as penalties; feasibility of the optimum is reported.
For two categories, a Latin hypercube sample of the parameter space (McKay et al. 1979) is evaluated and
its non-dominated points form the Pareto front.

## 10. Standards outputs

* **EN 15804+A2 EPD**: results per module from the life cycle stages (A1-A3 aggregated, A4 to D), "ND"
  for modules not declared, and a checklist of the main requirements (mandatory modules, EF reference
  package, core indicators, cut-off, allocation, data age, biogenic carbon content, PCR, verification).
* **EF 3.1 normalisation and weighting** are built in: normalisation factors per person (global, reference
  year 2010) from Andreasi Bassi et al. (2023, JRC130796, Table 10) and the final weighting factors including
  robustness from Sala et al. (2018, JRC106545, Table 31), which sum to 100 %. They are attached by name to
  the sixteen categories of an imported EF 3.1 method; toxicity sub-indicators (organics, inorganics, metals)
  and the climate change sub-indicators are not normalised separately.
* **PEF**: most relevant impact categories are those that together contribute at least 80 % of the
  weighted single score; within each, the most relevant stages, processes and elementary flows reach 80 %
  (absolute values), following Commission Recommendation (EU) 2021/2279.
* **ISO 14067**: CFP with fossil, biogenic and land use change contributions reported separately (built-in
  IPCC AR6 method), per stage, with sensitivity and uncertainty; offsetting is excluded.
* **GHG Protocol Product Standard**: results per life cycle stage of the standard and per gas.
* **Critical review**: the ISO 14044 requirements (4.2 to 6.3) with automatic evidence and fields for the
  reviewer's status and comment.

## 11. Validation and reproducibility

`engine/tests` holds 64 automated tests, including: a hand-calculated wall model; agreement with an
independent dense solution to 10⁻⁹; supply loops and waste treatment from ecoSpold2; unit conversion and
waste flows from openLCA JSON-LD; ecoSpold1, SimaPro CSV and ILCD imports against hand calculations;
cross-database linking and unlinking; flow mapping; regional factors; module D; co-product allocation;
parameters, scenarios and formulas; Monte Carlo reproducibility and centring; Sobol consistency;
dynamic GWP limits; reports; project portability; migration of older project files; the HTTP API with
invalid inputs; and every 1.2 feature through the API (background scenarios, site factors, chemicals,
external emissions, literature import, sweeps and optimisation, templates, versions and locks, EPD, PEF,
ISO 14067, GHG Protocol, review, Brightway round trip, openLCA export, Python client, teaching).

The **validation suite** (Toolbox) builds 34 product systems with exact answers in a temporary library and
reports expected value, Cyclia's value and the error: linear chains, production amounts other than one,
loops, units, system expansion, mass and economic allocation, nesting, formulas and scenarios, module D,
direct flows, regional and site-specific factors, prospective interpolation, consequential substitution, exchanges set from a scenario file,
dynamic GWP limits, lognormal Monte Carlo moments, Sobol indices of an additive model (S1 = Var_i/ΣVar_j,
ST = S1) and the fate model's mass balance and residence time.

A **reproducibility bundle** stores the project file, the settings, SHA-256 fingerprints of every database
(all exchanges keyed by dataset keys and flow UUIDs) and method (all factors), and the results. Verifying
it recalculates every model and reports whether data, methods and results are identical.

The **benchmark tool** (step 1) compares Cyclia with reference results for any list of datasets and
categories (e.g. ecoinvent's published LCIA results or an openLCA export). Run it on your database before
publishing. When results deviate, two diagnoses run automatically. The first lists, for the worst
datasets, elementary flows without a factor although the method has one under the same name. The
second, the factor finder, uses all compared datasets at once: with **g**_d the inventory of dataset *d*
and gap_d its difference to the reference, it selects a few flows *f* and factor corrections Δ_f by
orthogonal matching pursuit on gap_d / |ref_d| = Σ_f g_df Δ_f / |ref_d| and reports the factor the
reference appears to use (CF + Δ_f), the share of the deviation it explains, and the factors the method
file holds for that flow name.

## References

Andreasi Bassi S., Biganzoli F., Ferrara N., Amadei A., Valente A., Sala S., Ardente F. (2023) Updated characterisation and normalisation factors for the Environmental Footprint 3.1 method. JRC130796, Publications Office of the European Union.
Sala S., Cerutti A.K., Pant R. (2018) Development of a weighting approach for the Environmental Footprint. JRC106545, Publications Office of the European Union.
European Commission (2021) Recommendation (EU) 2021/2279 on the use of the Environmental Footprint methods.
EN 15804:2012+A2:2019. ISO 14025:2006. ISO 14067:2018. WRI/WBCSD (2011) GHG Protocol Product Life Cycle Accounting and Reporting Standard.
Heijungs R., Suh S. (2002) The Computational Structure of Life Cycle Assessment. Kluwer.
Karickhoff S.W. (1981) Semi-empirical estimation of sorption of hydrophobic pollutants on natural sediments and soils. Chemosphere 10, 833-846.
Mackay D., Di Guardo A., Paterson S., Cowan C.E. (1996) Evaluating the environmental fate of a variety of types of chemicals using the EQC model. Environ. Toxicol. Chem. 15, 1627-1637.
McKay M.D., Beckman R.J., Conover W.J. (1979) A comparison of three methods for selecting values of input variables. Technometrics 21, 239-245.
Rosenbaum R.K. et al. (2008) USEtox, the UNEP-SETAC toxicity model. Int. J. Life Cycle Assess. 13, 532-546.
Sacchi R. et al. (2022) PRospective EnvironMental Impact asSEment (premise). Renew. Sustain. Energy Rev. 160, 112311.
Storn R., Price K. (1997) Differential evolution. J. Global Optim. 11, 341-359.
Veith G.D., DeFoe D.L., Bergstedt B.V. (1979) Measuring and estimating the bioconcentration factor of chemicals in fish. J. Fish. Res. Board Can. 36, 1040-1048.
Weidema B.P., Ekvall T., Heijungs R. (2009) Guidelines for application of deepened and broadened LCA. CALCAS D18.
ISO 14040:2006 and ISO 14044:2006.
Jansen M.J.W. (1999) Analysis of variance designs for model output. Comput. Phys. Commun. 117, 35-43.
Joos F. et al. (2013) Carbon dioxide and climate impulse response functions. Atmos. Chem. Phys. 13, 2793-2825.
Levasseur A. et al. (2010) Considering time in LCA: dynamic LCA and its application to global warming impact assessments. Environ. Sci. Technol. 44, 3169-3174.
Saltelli A. et al. (2010) Variance based sensitivity analysis of model output. Comput. Phys. Commun. 181, 259-270.
Weidema B.P. et al. (2013) Data quality guideline for the ecoinvent database version 3. ecoinvent Report 1(v3).
IPCC (2021) Climate Change 2021: The Physical Science Basis, Chapter 7.
