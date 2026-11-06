# Cyclia 1.6.1: corrections and completion of custom data entry

This record covers two things:
- the findings of the review of 1.6.0, what was changed and how it was tested;
- the items that 1.6.0 listed as limits, which are now done: parameters and formulas, multi-output processes,
  units of your own, and a diagram editor.

With Brightway installed, all 274 automated tests pass. Without it, 270 pass and the four Brightway tests are
skipped. The custom data tests are in `engine/tests/test_custom_data.py` (47 tests).

## Review findings

| Finding | Severity | Result |
|---|---|---|
| In a custom method, a library flow without a factor was counted as zero and not reported | P0 | Corrected |
| A factor of zero recorded with its source was reported as missing | P1 | Corrected |
| Products, elementary flows and lines could not be edited in the interface; renaming a product did not update its datasets | P1 | Corrected |
| The acceptance record of 1.6.0 gave 249 passing tests without saying that four are skipped when Brightway is not installed | Documentation | Corrected |

### 1. Unknown factors in custom methods

**Cause.** In 1.6.0 only custom flows were checked for unknown factors. A custom method lists only the factors
its author entered, so a library flow without a factor was neither characterised nor reported.

**Correction.** A custom method has a scope for flows without a factor:
- **unknown** (the default): such a flow is an unknown factor. The category is marked incomplete and the flow is
  listed until a factor or a "does not apply" decision is recorded.
- **no effect**: the method's list of factors is complete, as in published methods. A reason is required.

Custom flows stay unknown in every method until they are decided. The database check reports library flows of
the database without a decision in a custom method.

**Tests**
- 1 kg methane (a library flow) in a custom method without its factor is listed as unknown; the total excludes
  it. With the factor 29.8 the result becomes 2.70 + 29.8.
- "No effect" needs a reason, removes the gap for library flows, and keeps custom flows unknown.

### 2. Zero factors

**Cause.** The check for unknown factors looked at the numerical value of the characterisation matrix, so a
factor of 0 counted as missing.

**Correction.** A factor is known when the method has one for the flow, whatever its value, or a factor was
recorded in Cyclia (zero included), or the category was recorded as not applying. The numerical value plays no
part.

**Tests**
- A recorded factor 0 with its source: no gap, status "factor 0" in the factor table, no warning in the check.
- A factor 0 of an installed method for a custom flow: no gap.

### 3. Editing

**Correction**
- Products, elementary flows, lines of a process and factors have Edit buttons. A line keeps its identifier and
  counts its revision and author.
- A product rename rewrites the datasets that make it.
- An edited elementary flow loses its matched factors and is matched again in every method that could
  characterise it.
- Library flows cannot be edited.
- Custom methods can be deleted.
- A change history records every creation, change and deletion with time, author and content.

**Tests**
- A rename appears in the dataset.
- A flow moved from air to water loses the air factor of an installed method and becomes unknown there.
- Editing a library flow is refused.
- An edited line keeps its id, has revision 2 and the new author, and the result changes from 2.70 to 3.70.
- The history lists the change and the creation.
- A method scope is kept through export, and a deleted method is gone.

## Placement and guidance

- "Your own data" is the second Toolbox tab, and the Toolbox entry names it.
- Step 1 (Add a database) has a card for it and step 3 (Inventory) links to it.
- The welcome screen and the step guidance mention it.
- The tab opens with a plain-language introduction and seven numbered steps that show what is done. Each step
  explains what to enter, with an example. "Key ideas in plain words" defines the terms.
- **Worked example**: one click creates a bakery with four processes (flour, electricity, landfill as a waste
  treatment, bread baking), uncertainty of every type and IPCC AR6 factors. The result for 1 kg of bread is
  0.65 x 0.4 + 0.3 x 0.5 + 0.05 x 0.02 x 27 = 0.437 kg CO2-eq, reproduced to 12 decimal places by a test. The
  values are labelled as illustrative.
- **Add the selected process to the open model**: one button.
- User guide chapter "Your own data (custom data entry)", in the app and on GitHub. It covers what Cyclia does for
  the user, the terms, the example, each of the seven steps, the results and common questions. The tab's guide
  button opens it at that chapter.
- Seven new glossary entries.

## Interface check

In the browser, on the demo project:
- the link in step 3 opened the tab;
- the example was created, and six of the seven steps were ticked. Factors stayed open because flour dust has
  no factor in the installed demo methods, which is correct;
- a product was renamed;
- a line was edited from 1 g to 700 g and shown with revision 2, and the history listed the change;
- the factor table offered "Decide" for every open decision;
- the process was added to the open model and appeared in its inventory;
- the guide opened at the chapter;
- there is no horizontal overflow at 1366 px.

## Parameters and formulas

**What was added**
- Parameters at two levels: the database, and each process. A process's own parameter replaces a database
  parameter with the same name.
- A parameter is a value or a formula of other parameters.
- An amount can be a formula. It is evaluated by the restricted formula evaluator that model parameters already
  use.
- Every change re-evaluates all formulas of the database in one transaction. When a formula fails, or gives a
  negative or non-finite amount, the whole change is refused and the previous state is kept.

**Tests**
- dough / (1 - loss) with a database parameter loss = 0.2 gives 0.8125 kg of flour (entered in g as
  flour_in x 1000), and 0.325 kg CO2-eq.
- Changing loss recalculates the result.
- A process parameter overrides the database parameter.
- Five invalid parameter sets are refused, and the earlier values and result stay: a negative amount, a parameter
  that depends on itself, a formula that does not parse, an invalid name, and a duplicate name.
- A process change that leaves a formula without its parameter is refused.
- On a line with a formula, a triangular range, an unknown name and a negative result are refused, and a formula
  equal to zero is allowed.

## Multi-output processes

**What was added**
- Co-products with mass, energy, economic or manual allocation.
- One dataset per output. Each one carries its share of every exchange, with the uncertainty scaled to match.
- Other processes can use each co-product.
- A co-product that something uses cannot be removed; when a co-product is removed, its dataset goes with it.
- Treatment processes take no co-products: recovered products are avoided products there.

**Tests (hand calculation).** A dairy makes 1 kg cheese at a price of 3 and 2 kg whey at 0.5, and emits
10 kg CO2.
- Economic allocation: cheese 75 %, 7.5 kg CO2 per kg; whey 1.25 kg CO2 per kg. The whey's standard deviation
  is 0.25.
- Mass allocation, taken from the kg units: 10/3 kg CO2 per kg of each product.
- The allocated datasets together carry exactly the 10 kg.
- Feed made with 500 g of whey: 0.625 kg CO2.
- Rejected:
  - manual shares that do not add up to 1, with nothing left behind;
  - a missing method;
  - co-products on a treatment process;
  - a duplicate output;
  - mass allocation without kg for an MJ product.

## Units of your own

**What was added**
- A unit in a known dimension with its factor (a sack of 50 kg), or the base unit of a new dimension (a seat),
  with multiples (a row of 20 seats).
- Units are loaded when the library opens and travel with the JSON export.
- A unit in use cannot change its size or be deleted.

**Tests**
- 0.004 bags of 25 kg give 0.1 kg CO2.
- 10 rows of 20 seats at 5 kg each give 1,000 kg.
- An input in kg for a supplier counted in seats is refused.
- Refused: resizing or deleting a unit in use, a built-in name, a negative size, and deleting a base unit that
  has multiples.
- Units survive a restart.

## Diagram editor

**What was added**
- The supply chain diagram of a custom database.
- Drag a box to arrange it; the position is stored without a new revision.
- Click a box to open its process.
- Press Connect, click a supplier, then a process, and enter the amount: this creates the input.
- Click an arrow to edit its line.
- Arrange automatically.
- In a model's flow diagram, a click opens the line in the inventory table.

**Browser check.** On the worked example:
- a sack unit was created;
- a database parameter was saved;
- the flour line was changed to 0.52 / (1 - loss), which gives 0.65 kg;
- bran was added as a co-product with economic allocation, which gives 90.9 % and 9.1 %;
- electricity was connected to the mill in the diagram, the unit was set to kWh, and the new arrow appeared;
- a box was dragged, and an arrow opened its line for editing.

## Round trip

A database was exported and imported into an empty library. It had:
- a unit of its own;
- a database parameter and a process parameter;
- a formula;
- a co-product with mass allocation;
- a process that uses the co-product;
- a custom method.

The result after import is identical (2 x 6 x 25/26).

## Limits

- Parameters of custom data are fixed values; Monte Carlo samples the uncertainty of each line. Model parameters
  keep their own distributions.
- Model inventories are edited in tables; the drawing editor covers custom processes. Drawing model inventories
  is planned in the [development plan](../DEVELOPMENT_PLAN.md).
