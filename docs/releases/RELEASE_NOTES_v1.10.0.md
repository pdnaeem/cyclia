# Cyclia 1.10.0

Database management and modelling, the second and third steps on the road to Cyclia 2.0.

## The ecoinvent 3.13 benchmark: all 61,400 results within 0.1 %

Cyclia was compared with ecoinvent's own results for ecoinvent 3.13 (cut-off): 100 datasets, 46 method families
(ReCiPe 2016, CML-IA, IPCC, EF, TRACI, USEtox, IMPACT World+ and more) and 614 impact categories. Every result is
within 0.1 % of ecoinvent's value, and the largest deviation is 0.019 %. The last 180 results, very small Ecological
Scarcity values, agree because every calculation now refines its solution once (below). The reports per method are
in docs/benchmarks.

## New

- **More precise solutions.** Every calculation adds one step of iterative refinement. This fixed the sign of very
  small results in long supply chains; results of ordinary size change only at round-off level.

- **Suppliers chosen by geography.** "Link automatically" and "Find supplier" follow ecoinvent's linking rules, on
  the same map of 541 geographies that ecoinvent's linking uses:
  1. a supplier at the same location;
  2. else the smallest region containing it;
  3. else RoW, if no other supplier covers the location;
  4. else GLO.

  Each suggestion says why it fits, for example "RER contains FR". Unclear cases are left to you.
- **Linking decisions with undo.** Every link and unlink, by you or automatic, is listed with its rule, author,
  supplier, conversion factor and time, and can be undone exactly.
- **Database check in eleven parts.** New: supplier links, geography, uncertainty and data quality coverage,
  duplicate datasets and provenance. The whole check, with the linking decisions, exports to Excel.
- **Where a dataset comes from.** The Database explorer shows each dataset's import file and fingerprint, its
  identifier in the source, and the decision behind each input that was linked across datasets.

- **Recycling approaches compared.** One material calculated with cut-off, end-of-life recycling, 50:50 and the
  Circular Footprint Formula, side by side.
  The Circular Footprint Formula reproduces a published worked example that uses the PEF default values for paper.
- **Supply chain tree.** In the Database explorer, a dataset's suppliers per impact category, with each one's share.
- **Subdivision before allocation.** In your own processes with co-products, a line that only one product causes
  goes wholly to that product; only the shared lines are allocated. Or subdivide the whole process and allocate
  nothing.
- **Named versions.** Keep a process as "as reviewed" or "supplier data 2025", compare it with today's state line by
  line, and go back to it.
- **Allocation, subdivision or system expansion for each model.** Choose in step 2 how a model's co-products are
  handled. With system expansion, name the product each co-product replaces and Cyclia credits it. Every line can
  belong to the product, to the co-products, or be shared. Compare all choices side by side.
- **Edit supplier relations in the model diagram.** Drop a dataset or one of your models on a line to change its
  supplier, or on a stage to add it.
- **Drag a supplier into the diagram.** Search the library from the diagram of your own data and drop a dataset onto
  the process that uses it.

## Changed

The list of datasets in a model's supply chain applied the allocation share twice; it now applies it once. Totals
were not affected.


An input at a location with only a global supplier is now linked to it automatically, as ecoinvent does. Before, it
was left open. The message after automatic linking says how many rows each rule linked, and each one can be undone.

## Download

Windows: `Cyclia-Setup-1.10.0.exe` · macOS: `.dmg` · Linux: `.AppImage` or `.deb`.

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.10.0)
[Computer software]. https://doi.org/10.5281/zenodo.23853747
