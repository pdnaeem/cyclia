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
  dominant contributors, different versions of one method, modelling approach against allocation and the
  database system model (attributional with cut-off or APOS data; consequential without allocation),
  data older than 10 years (EN 15804+A2 6.3.8.2), and an energy balance when the functional unit is an
  amount of energy (delivered energy above the energy inputs).
- **Data quality of results**: the model is flattened into paths from the top-level model through every nested
  model to a dataset, flow or EPD line. For each category k each path is weighted by its share of the absolute
  impact, w_p = |h_pk| / sum |h_k|; credits (avoided products) and module D are left out of the weights and their
  share is reported apart. A path takes, per indicator, the worst pedigree score along its chain. Two ratings are
  reported: a **pedigree-based indicator** (TeR + GeR + TiR + P) / 4 with P = pedigree reliability, TiR =
  temporal, GeR = geographical and TeR = technological correlation, which is *not* a PEF DQR because pedigree
  reliability is not the PEF precision criterion; and the **PEF DQR**, computed only from lines for which the
  four PEF scores were entered, with the share of the impact they cover. Both use the PEF classes (excellent
  up to 1.5, very good up to 2, good up to 3, fair up to 4, poor above). The shares of primary, secondary,
  estimated and unstated data use the same weights; a path takes the data type of its leaf line, or of the
  nearest line above it that has one.
- **Comparison gate** (ISO 14044 4.2.3.7): a comparison is blocked when functional units differ in unit
  dimension or amount, or a model has errors in its checks. Differences in product description, boundary, stage
  system, approach, allocation, geography, period, background system model, or a pedigree indicator that
  differs by 1 or more, are listed as issues. The comparison is "valid" only without issues and with a written
  functional equivalence statement; otherwise it is labelled a screening comparison.
- **Key findings**: generated from the numbers above: largest contributors and stage per category, credits and
  module D, Monte Carlo interval, different hotspots in different categories (reported as hotspots, not as
  burden shifting), the burden line whose reduction lowers the result most (a credit is never proposed for
  reduction; its effect is reported separately), with the change in every other category for the same
  reduction (an increase is reported as burden shifting), important lines with weak data, costs and check
  errors. Improvement estimates are linear screening estimates for a smaller amount of the same input.
  Model comparison names the alternative with the lowest result per category; whether a difference is larger
  than the uncertainty is judged with the comparative Monte Carlo (one alternative lower in at least 95 % of the
  runs). Scenario comparison lists, per scenario, the categories that go down and those that go up.
- **Water inventory**: elementary water flows in m3 (kg and litres divided by 1000). Withdrawal = resource
  flows; release = water emitted to water, air and soil; consumption = withdrawal minus release. Turbine water
  of hydropower is reported apart.

## 5. Uncertainty

**Data quality**: each line has a pedigree score (reliability, completeness, temporal, geographical,
technological). The variance of ln is the basic variance (0.0006; 0.12 for transport; 0.04 for
emissions other than CO2) plus the pedigree variances of the ecoinvent v3 guideline (Weidema et al.
2013). The line amount is lognormal with this sigma and its median at the entered value.

**Foreground Monte Carlo** (hierarchical): the model is flattened into paths through every nested model. Every
line at every level gets its own lognormal factor from its own pedigree scores (a line that occurs in several
places, such as a sub-model used twice, keeps one draw), and every parameter distribution of the project and of
each model is sampled (a model parameter hides a project parameter of the same name inside that model). The
amount of a path is the product of the line amounts, signs, allocation shares and 1 / reference amount of each
sub-model on the chain; the result is the sum of path amounts times the unit result of each leaf.

**Full Monte Carlo**: in each iteration every exchange of the database with uncertainty information
(ecoSpold2 lognormal with pedigree-widened variance, normal, triangular, uniform; openLCA and SimaPro
equivalents) is sampled, **A** is refactorised, and every compared model is solved on the same random
background, so differences are paired. Foreground lines and parameters that compared models have in common
(for example the same sub-model) use the same draws; the other foreground lines are sampled per model. Reported: mean, median, SD, 2.5 and 97.5 percentiles, CV, and for
comparisons the probability that one option is lower than the other. A singular random draw falls back
to the static matrix for that iteration.

**Correlated parameters**: pairs of parameters with a Spearman rank correlation ρ are sampled with a Gaussian
copula. The latent normal correlation is r = 2 sin(πρ/6) (Pearson 1907), so the sampled rank correlation equals
ρ; correlated standard normals Z = L u (L the Cholesky factor) are turned into uniforms U = Φ(Z) and into each
parameter's own distribution by its inverse CDF. Inconsistent sets of correlations (a matrix that is not
positive definite) are rejected. Sobol indices assume independent factors and ignore correlations.

**Convergence**: each Monte Carlo result reports the standard error of the mean relative to the width of the 95 %
interval (sd / √n / (p97.5 - p2.5)) and how far the 2.5 and 97.5 percentiles of the first half of the runs lie
from those of all runs, relative to the interval width. The run counts as converged when the first is below
1 % and the second below 10 %.

**Global sensitivity**: the factors are every line at every level of nesting and every parameter distribution.
 first-order (Saltelli et al. 2010) and total (Jansen 1999) Sobol indices for the
foreground uncertainty (line amounts and parameter distributions), N (d + 2) evaluations, with outputs
centred before estimation.

## 5a. Life cycle costing and circular footprint

**Life cycle costing**: each line may have a price per unit of the amount typed. The cost of a line is amount
x price x allocation share, negative for a credit (revenue). A line that is another model adds that model's
cost per unit times the amount. With a discount rate r and the line's year t the discounted cost is
c / (1 + r)^t (net present cost, ISO 15686-5). Module D lines are reported apart. Lines without a price count
as zero and are listed.

**Circular Footprint Formula** (Commission Recommendation (EU) 2021/2279, Annex C), per unit of material:

(1 - R1) Ev + R1 (A Erecycled + (1 - A) Ev Qsin/Qp) + (1 - A) R2 (ErecyclingEoL - E*v Qsout/Qp)
+ (1 - B) R3 (EER - LHV X_ER,heat ESE,heat - LHV X_ER,elec ESE,elec) + (1 - R2 - R3) ED

Cyclia writes each term as an inventory line with its coefficient times the material mass; the E*v,
ESE,heat and ESE,elec terms are credits. Energy terms are in MJ and converted to the unit of the chosen
dataset. The validation test recomputes the formula by hand and compares with the model result.

**Data age**: producer-specific (primary) data older than 5 years and other data older than 10 years raise a
warning (EN 15804+A2 6.3.8.2); primary data outside the study period and lines without a data year are listed.
These checks, the default data quality check, the system model check and the approach check cover every line of
the model and of every nested model, and name the model a line belongs to.

**Complete foreground inventory**: for every line of every nested model, the amount per unit of its own model and
the amount per functional unit, which is the product of the line factors along each chain from the top-level
model (amount, sign, allocation share, 1 / reference amount of each sub-model), summed over every place the line
occurs.

**Physical causality**: the allocation share is p_main / (p_main + sum p_coproducts) for a physical property the
user names (ISO 14044 4.3.4.2, step 2), next to mass, energy and economic value.

**Database migration**: the open model and every model nested in it are switched to the new database (matching as
below). Each changed model gets one undo step, and the whole migration can be undone at once; results before and
after are shown.

**Database comparison**: datasets of two databases are paired by key (stable between ecoinvent versions), else
by name, product, location and unit, and each is calculated per unit of its reference product with the same
methods. The change is (B - A) / |A|.

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

* **EPD indicators**: the 13 core indicators and the 18 indicators of EN 15804+A2 Tables 4 to 6 (PERE, PERM, PERT,
  PENRE, PENRM, PENRT, SM, RSF, NRSF, FW, HWD, NHWD, RWD, CRU, MFR, MER, EEE, EET) are identified by their
  abbreviation or wording; missing indicators, units that do not match the standard (kg CO2 eq, kg CFC-11 eq,
  mol H+ eq, kg P eq, kg N eq, mol N eq, kg NMVOC eq, kg Sb eq, MJ, m3, kg) and indicators without factors are
  listed. A draft can always be written; it states "not ready for submission" while any requirement is open.
* **EPD module table**: every line must be in an EN 15804 module; stages with other names block the EPD. A1-A3 is
  declared only when it has lines. The module table must add up to the LCA result (A-C) and module D, otherwise
  the EPD is not written. The reference service life is required when B modules are declared. Every indicator
  must use the EF reference package 3.0 or later (or Cyclia's EN 15804+A2 IPCC split).
* **EPD (ISO 14025:2026)**: the declaration states the intended audience (B2B or B2C), the share of the
  GWP-total result from supply-chain-specific (primary) data, the number of months of specific data and
  whether it is a prospective EPD, which ISO 14025:2026 uses to define EPD types; a B2C EPD needs a named
  independent verifier and a prospective EPD a quantified uncertainty. Cyclia is not a verified EPD tool, so
  every EPD needs its own verification. The share of supply-chain-specific data is taken from the data quality
  weights (all levels of nesting, credits excluded). A prospective EPD needs a converged Monte Carlo run.
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
* **Executive summary**: two pages from the results, data quality and key findings, with conclusions and the
  review status.
* **Critical review**: the ISO 14044 requirements (4.2 to 6.3) with automatic evidence and fields for the
  reviewer's status and comment.

## 11. Validation and reproducibility

**Independent cross-check**: datasets and models are recalculated by a second implementation that rebuilds A and B
from the library tables, solves with LAPACK dense LU (up to 4,000 datasets) or GMRES with an ILU preconditioner
and iterative refinement, applies factors per flow and site factors from their own table, and flattens nested
models separately. Agreement: relative difference below 1e-5, measured against at least 1e-9 of the largest result of
the category (the round-off of solving A s = f is about machine precision times the condition number of A, 1e-9
for the tutorial library; without this floor a result that cancels to about zero turns round-off into a large
relative difference). Details and results: docs/CROSS_VALIDATION.md.

**Land use reconciliation** (ecoinvent benchmark): for each land use category, Cyclia's result of every compared
dataset is split into occupation, transformation-from and transformation-to contributions c_dg; the factor
changes α_g that best explain the gap, (ref_d - cyclia_d) = Σ_g α_g c_dg, are estimated by weighted least squares
(weights 1 / |ref_d|), with the share of the gap variance explained. Land flows of the inventories without a
factor, and raw factors that give one flow two different values, are listed.

`engine/tests` holds 167 automated tests (1.3.6), including: a hand-calculated wall model; agreement with an
independent dense solution to 10⁻⁹; supply loops and waste treatment from ecoSpold2; unit conversion and
waste flows from openLCA JSON-LD; ecoSpold1, SimaPro CSV and ILCD imports against hand calculations;
cross-database linking and unlinking; flow mapping; regional factors; module D; co-product allocation;
parameters, scenarios and formulas; Monte Carlo reproducibility and centring; Sobol consistency;
dynamic GWP limits; reports; project portability; migration of older project files; the HTTP API with
invalid inputs; and every 1.2 feature through the API (background scenarios, site factors, chemicals,
external emissions, literature import, sweeps and optimisation, templates, versions and locks, EPD, PEF,
ISO 14067, GHG Protocol, review, Brightway round trip, openLCA export, Python client, teaching).

The **validation suite** (Toolbox) builds 35 product systems with exact answers in a temporary library and
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

## 12. Added in 1.3.5

### 12.1 Factor matching validation (Toolbox > Validation)

Cyclia's characterisation factors are compared flow by flow with the factors another tool assigns. External
sources: an openLCA JSON-LD export of the method (factors per flow UUID), a Brightway export written by
`engine/tools/brightway_export_factors.py` (run inside a Brightway environment; it writes `bd.Method(key).load()`
rows with the flow keys, names, categories and units), or a CSV with the columns category, flow_uuid, flow_name,
compartment, subcompartment, unit, cf (and location). Lines starting with `#` are comments.

1. **Pairing of categories**: one to one. Every (Cyclia, external) pair is scored by word overlap (Jaccard index,
   on the category name alone and on category plus indicator, the higher counts; an identical name scores
   highest) and pairs are assigned from the highest score down, so an external category is never used twice. A
   pair needs at least 0.4. Pairs can be set by hand.
2. **Resolving flows**: an external factor is attached to a Cyclia flow by UUID; without a UUID, by canonical
   name, compartment and subcompartment. Rows that match no flow of the library are *unresolved*, rows that match
   several flows are *ambiguous*. A factor given per another unit is converted when the units are convertible
   (per g to per kg: divided by 0.001); otherwise the flow is *unit not comparable* and never counted as the same
   factor. External files that give one flow two different factors are counted as *external conflicts*.
3. **Comparison**: over every flow that the library or the project's models use and that has a non-zero factor in
   either tool (global factors only), each flow is *same* (relative difference up to 1e-6), *different*,
   *only in Cyclia* or *only in the external tool*.
4. **Effect on models**: with g the elementary flows per functional unit of a model (module D excluded) and Δc the
   factor differences, the result with the external factors is h_ext = h + Σ_f g_f Δc_f. The table lists
   h, h_ext and the effect in percent, and each flow's largest effect on any model.
5. **External results (optional)**: a CSV with model, category, value. The difference to Cyclia is split into the
   part explained by the factors (h_ext − h) and the rest (inventory, linking, allocation or solver differences).

Excel report: Summary with the open items, Flow by flow, Effect on models, Unresolved external, Unpaired
external categories. **The validation passes only when there is no open item**: every category paired, no
differing factor, no factor in one tool only, no unit that cannot be compared, no unresolved or ambiguous
external row and no conflicting external factor (before 1.3.6 unresolved rows, ambiguous rows, unit differences
and conflicts did not prevent a pass).

### 12.2 EPD programme profiles (step 6)

A profile describes one programme's EPD: the order of sections of the Word file, extra general-information
fields (with required ones marked), the mandatory statements, the required additional indicators, the maximum
validity in years, the language of labels and fixed texts. Built in: Cyclia generic (ISO 14025:2026 and
EN 15804+A2), the International EPD System (GPI 5), IBU and INIES FDES (French labels). The three programme
profiles are drafts modelled on EPDs published by those programmes and are **not approved by the programme
operators**. The checklist adds, per profile: every required field filled, every required indicator calculated,
and validity (valid until minus issued) not above the profile's maximum. Custom profiles are JSON files with the
keys id, name, language, status, based_on, validity_years, fields (key, label, required, type, options),
statements, required_indicators, grouped_tables and sections; the section names must be known to Cyclia. An
example is `docs/examples/epd_profile_example.json`.

### 12.3 Data quality of EF and ILCD datasets

On ILCD/EF import, the `common:dataQualityIndicator` values of each process dataset are read: Very good 1,
Good 2, Fair 3, Poor 4, Very poor 5 (numbers kept as they are; "not evaluated" and "not applicable" skipped).
TeR, GeR, TiR and P are stored per dataset. For lines without PEF scores of their own, the data quality of a
category uses the dataset scores, DQR = (TeR + GeR + TiR + P) / 4 (Commission Recommendation (EU) 2021/2279),
weighted by the line's contribution like the foreground scores; the share of the result scored this way is shown
as "from datasets".

### 12.4 Marginal supplier guidance (Toolbox > Background)

For every market with several suppliers in the supply chain of a model, a supplier is marked as *constrained*
when its name or product contains a word that indicates by-product, recycled or waste-based supply (recycled,
secondary, by-product, co-product, waste, treatment of, scrap, used, reuse, residue, cut-off), after Weidema et al.
(2009). The unconstrained supplier with the largest current share is proposed. The user confirms or changes the
choice with market data (growing, competitive technology), and Cyclia creates a consequential background
scenario with a swap rule per market (the market's supply replaced by the chosen supplier). The proposal is a
starting point, not a marginal-supplier identification.

### 12.5 Life cycle costing: cost types and replacements

Each costed line has a cost type (capital, operating, maintenance, replacement, end of life). With a study period
T (step 2) and a replacement interval R on a line in year y₀, the line's cost occurs in years y₀ + kR for
k = 0, 1, ... while y₀ + kR < T; the net present cost is Σ c / (1 + r)^(y₀ + kR). Results are given by line,
stage and cost type.

### 12.6 AWARE water scarcity (Toolbox > Regional methods)

Water consumption of every process per functional unit, from the engine's scaling vector:
consumption = Σ water taken from nature − Σ water released to fresh water (surface, ground or unspecified water)
at the process location (m³). Water evaporated to air, discharged to the sea or ocean and released to soil is
consumption: it is not an identified return to the watershed and gets no credit (WULCA definition; before 1.3.6
evaporation and releases to soil were wrongly subtracted). The water balance (withdrawn, returned, evaporated, to
the sea, to soil) is reported. AWARE result = Σ_processes consumption × CF(location of the process, type of use).
Type of use per process: agricultural for irrigation processes, non-agricultural for every other supply-chain
process (option: unknown), and the type chosen for the model's own water. When a location has no factor for that
type, the unknown factor is used and shown (before 1.3.6 the non-agricultural factor was stored as 'non-agri' and
never found, so the unknown factor was always used). Monthly factors and GIS watershed lookup are not supported. The model's own
water flows use the model's AWARE location (site or watershed, set in Toolbox > Regional methods), else the
study geography. Location lookup:
exact code, then the country of a sub-national code (CN-HB → CN), then the global value (GLO). Completeness
gives the share of the water consumption characterised exactly, by fallback, or not at all. Factors are imported
from the official AWARE tables (Boulay et al. 2018); Cyclia ships only a labelled demonstration set.

### 12.7 LANCA land use

Land occupation (m²·a), transformation to and transformation from (m²) of every process, times the LANCA factor
for the indicator, kind of intervention, land use type and process location (same fallbacks as AWARE). Factor
units are validated on import (occupation per m²·a, transformation per m²; per ha·a or per ha converted) and
inventory amounts are converted to m²·a and m² (an occupation in ha·a is 10,000 m²·a). Soil organic carbon is
accepted as an indicator. The soil quality index is used as imported (the EF method publishes SQI factors);
Cyclia does not aggregate LANCA indicators into an SQI itself.
Indicators: erosion resistance, mechanical filtration, physicochemical filtration, groundwater regeneration,
biotic production, and the EF soil quality index when its factors are imported. Land flows without a factor
are listed with their area. Factors must come from the LANCA owners (Bos et al. 2016); demo values only show the
workflow.

### 12.8 Social LCA screening (Toolbox > Social LCA)

This is a **risk screening**, not a full social LCA. Activity variable: worker hours per unit of each process's
reference product, with a risk level per social indicator and stakeholder category (UNEP 2020 Guidelines, ISO 14075:2024: workers, local community, society,
consumers, value chain actors, children). Worker hours per functional unit = activity level of each process (|s × the diagonal of A|, with s solved for the
demand alone; avoided products are solved separately, reported separately and neither added nor netted) × worker
hours per unit. Risk hours = hours × factor of the risk level (no risk 0, very low 0.01,
low 0.1, medium 1, high 10, very high 100; editable). Each process takes the most specific data row: the longest
matching name fragment, a row for its location before a row without location. Process coverage = processes with data / processes in the supply chain. Worker hours of processes without data
are unknown, so a worker-hour coverage is only given when the table has a default row (match `*`) that estimates
them: coverage = hours with data / (hours with data + estimated hours). (Before 1.3.6 coverage was divided by
the hours with data only and was always 100 %.) This is a hotspot screening, not a
measurement of social performance. Cyclia ships no social data.

### 12.9 Dynamic material flow analysis and circularity (Toolbox > Material flows)

A system of processes, in-use stocks and sinks connected by transfer coefficients (shares per process summing to
1, sinks excepted). External inflows are interpolated linearly between the given years and kept constant after
the last one. A stock retires its inflow of year t in the following years by a discrete lifetime distribution:
fixed (all at age L ≥ 1); normal with mean μ and standard deviation σ (share retiring at age a = F(a + 0.5) −
F(a − 0.5), with age 1 taking F(1.5), so nothing retires in the year of entry); Weibull with shape k and scale λ
(share at age a = F(a) − F(a − 1), age 1 taking F(1)). Retirements that fall after the last year of the study are
not counted; over a long enough horizon every inflow retires (tested to 1e-9). Flows within a year, including recycling back
to production, are solved as x = (I − Tᵀ)⁻¹ u; a loop with no exit raises an error. Every year is checked for
mass balance (external inflow = change in stocks + flows to sinks). Indicators per year: end-of-life recycling
rate (recycled output / end-of-life outflow), recycled content and recirculated inflow share (both: recycled
input to the production process / total input to the production process; before 1.3.6 the inflow share was
divided by all external inflows of the system), the outflow share recirculated, and the MCI of that year computed
from the MFA (F_R = recycled content, C_R = input to recycling / end-of-life outflow, E_C = recycled output /
input to recycling). In the spirit of ISO 59020:2024, not a complete ISO 59020 assessment.

The **Material Circularity Indicator** (Ellen MacArthur Foundation and Granta Design 2015, technical cycle):
V = M(1 − F_R − F_U); W₀ = M(1 − C_R − C_U); W_C = M(1 − E_C)C_R; W_F = M(1 − E_F)F_R / E_F;
W = W₀ + (W_F + W_C)/2; LFI = (V + W) / (2M + (W_F − W_C)/2); F(X) = 0.9 / X with X = (L/L_av)(U/U_av);
MCI = max(0, 1 − LFI · F(X)).
A fully linear product gives 0.1, a fully circular one 1.

## 13. Corrections and additions in 1.3.6

**Process identity on import.** SimaPro processes are identified by their process identifier (else the process
name) together with product and location. Before 1.3.6 the key was product + location, so two routes of the same
product at one location were merged into one dataset and their exchanges added up. The shared builder of the
ecoSpold1, SimaPro and ILCD importers now keeps any two processes with the same identity separate and reports them.

**No guessed suppliers.** An input is linked inside an import only when one dataset produces its product (most
specific match first: product, location and unit; then product and unit; then product). With several producers
the input is stored as *ambiguous* with the candidates (before 1.3.6 the first producer found was used). openLCA
JSON-LD inputs use the exchange's defaultProvider, else the only producer, else they are ambiguous.

**No dropped inputs.** An ecoSpold2 intermediate input without activityLinkId is stored as unresolved ("no
supplier link in the dataset") instead of being left out without a record. It adds nothing to results until the
user links it, as before; inputs cut off on purpose by the system model must stay unlinked.

**Linking by location.** Missing suppliers are grouped by product, unit and location, and linked per location.
Automatic linking only links a group with exactly one dataset of the same product at the same location (inputs
without a location: one dataset, or one global market), and never ambiguous or unlinked-in-dataset groups.

**Database provenance.** Every import records the source file's SHA-256 (for a folder: of the file names and
contents), the importer version, the import report and the metadata entered (original name, version, system
model, release date, geography, technology, licence, reference period, data reference), editable under Database
details. An import is all or nothing: it is removed again if it fails, or if amounts are not finite or links
point to datasets that do not exist.

**Database check in six statuses**: matrix consistency, technosphere completeness (unresolved inputs by reason),
elementary-flow coverage, unit consistency (unknown units, flows with one name and compartment in several units,
datasets without unit), metadata completeness and LCIA compatibility (share of used flows each method family
characterises). A solvable matrix no longer reads as a complete database.

**Land use coverage.** Every result reports, per land use category, the share of the inventory's land
occupation and transformation without a factor, and warns above 0.5 %. The ecoinvent benchmark adds a targeted
test: the gap is regressed on the land flows without a factor, giving the factor ecoinvent appears to use for
each and the share of the gap they explain. The benchmark verdict names every category with less than 95 % of
results within 1 %, and notes deviating datasets whose supply chain holds unresolved inputs.

**EPD additional indicators.** HTP-c and HTP-nc match the EF 3.1 names 'carcinogenic' and 'non-carcinogenic', the
toxicity sub-categories ', inorganics' and ', organics' are never taken for the indicator, and the units of PM,
IRP, ETP-fw, HTP-c, HTP-nc, SQP and GWP-GHG are checked.

## References

Andreasi Bassi S., Biganzoli F., Ferrara N., Amadei A., Valente A., Sala S., Ardente F. (2023) Updated characterisation and normalisation factors for the Environmental Footprint 3.1 method. JRC130796, Publications Office of the European Union.
Sala S., Cerutti A.K., Pant R. (2018) Development of a weighting approach for the Environmental Footprint. JRC106545, Publications Office of the European Union.
European Commission (2021) Recommendation (EU) 2021/2279 on the use of the Environmental Footprint methods.
EN 15804:2012+A2:2019. ISO 14025:2026. ISO 14020:2022. ISO 14067:2018 (under revision, ISO/WD 14067 in 2026). ISO 14071:2024. ISO/TS 14074:2022. ISO 15686-5:2017 (life cycle costing). WRI/WBCSD (2011) GHG Protocol Product Life Cycle Accounting and Reporting Standard.
Heijungs R., Suh S. (2002) The Computational Structure of Life Cycle Assessment. Kluwer.
Karickhoff S.W. (1981) Semi-empirical estimation of sorption of hydrophobic pollutants on natural sediments and soils. Chemosphere 10, 833-846.
Mackay D., Di Guardo A., Paterson S., Cowan C.E. (1996) Evaluating the environmental fate of a variety of types of chemicals using the EQC model. Environ. Toxicol. Chem. 15, 1627-1637.
McKay M.D., Beckman R.J., Conover W.J. (1979) A comparison of three methods for selecting values of input variables. Technometrics 21, 239-245.
Rosenbaum R.K. et al. (2008) USEtox, the UNEP-SETAC toxicity model. Int. J. Life Cycle Assess. 13, 532-546.
Sacchi R. et al. (2022) PRospective EnvironMental Impact asSEment (premise). Renew. Sustain. Energy Rev. 160, 112311.
Storn R., Price K. (1997) Differential evolution. J. Global Optim. 11, 341-359.
Veith G.D., DeFoe D.L., Bergstedt B.V. (1979) Measuring and estimating the bioconcentration factor of chemicals in fish. J. Fish. Res. Board Can. 36, 1040-1048.
Weidema B.P., Ekvall T., Heijungs R. (2009) Guidelines for application of deepened and broadened LCA. CALCAS D18.
ISO 14040:2006/Amd 1:2020 and ISO 14044:2006/Amd 1:2017, Amd 2:2020.
Jansen M.J.W. (1999) Analysis of variance designs for model output. Comput. Phys. Commun. 117, 35-43.
Joos F. et al. (2013) Carbon dioxide and climate impulse response functions. Atmos. Chem. Phys. 13, 2793-2825.
Levasseur A. et al. (2010) Considering time in LCA: dynamic LCA and its application to global warming impact assessments. Environ. Sci. Technol. 44, 3169-3174.
Saltelli A. et al. (2010) Variance based sensitivity analysis of model output. Comput. Phys. Commun. 181, 259-270.
Weidema B.P. et al. (2013) Data quality guideline for the ecoinvent database version 3. ecoinvent Report 1(v3).
IPCC (2021) Climate Change 2021: The Physical Science Basis, Chapter 7.
