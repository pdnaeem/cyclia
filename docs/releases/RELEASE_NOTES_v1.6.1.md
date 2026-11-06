# Cyclia 1.6.1

## What is new

- **Your own data is easier to find and to learn.** It is the second tab of the Toolbox, and step 1 and step 3
  link to it. Seven steps with ticks show what is done; every step explains itself in plain words with an example.
- **A worked example.** One click creates a small bakery: bread made with flour and electricity, its waste sent to
  landfill, with IPCC AR6 factors. Walk through it before entering your own data.
- **Edit everything.** Products, elementary flows, lines of a process and factors can be edited. Renaming a
  product updates the datasets that make it.
- **Change history.** Every change of a process and its lines is recorded with time and author.
- **One click to use.** Add the selected process to the open model from the Your own data tab.
- **Parameters and formulas.** Write amounts such as `dough / (1 - loss)`; change `loss` once and every amount
  that uses it follows.
- **Several products from one process.** Cheese and whey, flour and bran: list the co-products and choose mass,
  energy, economic or manual allocation. Each product gets its own dataset.
- **Units of your own.** A sack of 50 kg, or a new kind of quantity such as a seat.
- **Draw your supply chain.** Arrange your processes in a diagram, connect a supplier to a process to add an
  input, and click an arrow to edit it.

## Fixed

- In a method you created, a flow without a factor was counted as zero without warning. It is now marked as an
  unknown factor, unless you state that the method's list of factors is complete.
- A factor of zero that you recorded with its source was still reported as missing.

## Download

Windows: `Cyclia-Setup-1.6.1.exe` · macOS: `.dmg` · Linux: `.AppImage` or `.deb`.
Installed copies of Cyclia update themselves.

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version 1.6.1)
[Computer software]. https://doi.org/10.5281/zenodo.23853747
