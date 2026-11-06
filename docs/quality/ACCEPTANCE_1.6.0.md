# Cyclia 1.6.0: custom data entry

This record describes the custom data entry, how it was tested and what its limits are. With Brightway installed,
all 249 automated tests pass; without it, 245 pass and the four Brightway tests are skipped. Corrections to this
release are recorded in [ACCEPTANCE_1.6.1.md](ACCEPTANCE_1.6.1.md).

## Requirements and how they are met

| Requirement | Implementation |
|---|---|
| Create a process | Custom databases with processes: reference product and amount, production or waste treatment, location, technology, time period, data type, source, comment |
| Define product flows | Product flows with name, unit, category and source, per custom database |
| Define elementary flows | Name, compartment and subcompartment from the ecoinvent elementary flow list, unit, CAS number, source; library-wide so that every database can use them |
| Units and compartments | Units must be known; amounts and uncertainty parameters are converted to the reference unit only within one dimension; land occupation needs m2*a, land transformation m2; compartments are chosen from the list |
| Custom characterisation factors | Factors for custom flows in any installed method, and custom methods with factors for any flow; a factor per another unit (per g) is converted; a source is required |
| Uncertainty and data quality | Lognormal (GSD), normal, triangular, uniform or pedigree scores per exchange; PEF data quality ratings (TeR, GeR, TiR, P) per process |
| Complete custom supply chain | Inputs from custom processes or library datasets, waste sent to treatment, avoided products, emissions and resources; every calculation, Monte Carlo, report and export works with it |
| Unique ID, provenance, unit validation | UUID version 4, source, author, creation and change time and revision per item; dataset ids stay stable when a process is edited |
| Unsupported factors are not zero | A custom flow without a factor and without a recorded "does not apply" decision marks the category incomplete in the result table, inventory view, Word report and Excel workbook; the checks report an error and the EPD check does not pass |

## Rules that protect the results

- A flow that the library already has (same canonical name and context) is not created again, so the factors of
  installed methods are not lost through a duplicate.
- Factors of installed methods for library flows cannot be changed here. A custom method can give factors to any
  flow.
- Imported databases cannot be edited; only custom databases can.
- A product, flow or process that something else uses (another process, a factor, or a model in any project)
  cannot be deleted until that use is removed.
- A process cannot consume as much of its own product as it makes.
- Non-finite numbers, zero amounts, negative amounts (avoided products are marked as such), data quality ratings
  outside 1 to 5, incomplete rating sets, wrong pedigree lengths, a GSD of 1 or less, and triangular or uniform
  bounds that do not enclose the amount are refused with a message.

## Tests (`engine/tests/test_custom_data.py`, 22 tests)

**Hand-calculated supply chain**, built from an empty library: steel sheet with 2 kg CO2, 10 g solvent X,
3.6 MJ electricity (= 1 kWh), 0.2 kg waste to an incineration process (waste treatment) and 0.1 kWh avoided
electricity; electricity with 0.5 kg CO2 per kWh; incineration with 1 kg CO2 per kg treated. With CO2 = 1 and
solvent X = 0.005 per g (= 5 per kg):

2 + 1 x 0.5 + 0.2 x 1 + 0.01 x 5 - 0.1 x 0.5 = **2.70 kg CO2-eq**, reproduced to 12 decimal places.

Further tests:
- signs of waste treatment and avoided products in the matrix, with mirrored triangular and uniform bounds;
- conversion of amounts (MJ to kWh, g to kg) and of uncertainty parameters; pedigree scores give the same log
  standard deviation as elsewhere in Cyclia;
- Monte Carlo with every uncertainty type;
- a process edited with a new reference amount keeps its dataset id and revision count, and the result halves;
- a library dataset as supplier, with a unit conversion;
- an unknown factor marks the category incomplete and creates an error in the checks; recording "does not apply"
  removes the mark without changing the result;
- a custom flow in an installed method: the library factor of CO2 matches by name and context, solvent X is
  listed until its factor is given; the installed method's own factors stay unchanged;
- a new impact category lists every custom flow without a factor;
- factor unit conversion, and a factor in an incompatible unit is refused;
- a factor needs a source, "does not apply" needs a reason;
- installed factors of library flows cannot be overwritten;
- 19 rejection cases (unknown unit, duplicate product, duplicate library flow, invalid compartment, wrong CAS
  check digit, land flows with wrong units, incompatible exchange unit, negative and non-finite amounts, wrong
  uncertainty input, own product consumed in full, invalid data quality, deletion of used items);
- CAS check digit reference values;
- imported databases cannot be edited;
- unique identifiers and provenance on every item;
- removing a custom database removes its custom data; a deleted process leaves no exchanges behind;
- when a library database used as supplier is removed, the input becomes an unresolved input and the check reports it;
- export to JSON and import into the same library (new identifiers) and into an empty library: same result.

## Interface check

In the browser, on the demo project:
- a custom database with three products, a custom elementary flow and two processes was created;
- the duplicate of "Carbon dioxide, fossil" was refused with a pointer to the existing flow;
- 3.6 MJ was stored as 1 kWh and 10 g as 0.01 kg; an input in kg for a supplier in kWh was refused;
- the database check and the factor status listed the open factor decisions;
- a model with the custom process showed "Incomplete: 1 custom flow(s) without a factor" in every category.
- The page has no horizontal overflow at 1366 px.

## Limits

- Exchanges are entered in tables; the flow diagram does not edit them yet (development plan, stage P1).
- Parameters and formulas are available in models, not inside custom processes.
- Multi-output processes are modelled with one reference product per process; allocation of co-products is done
  in the model (allocation step) or by system expansion with avoided products.
- A JSON export that uses library datasets as suppliers needs the same databases in the target library; they are
  found by dataset key and database name.
