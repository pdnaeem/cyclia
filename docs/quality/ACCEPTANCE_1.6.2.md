# Cyclia 1.6.2: display corrections

Release 1.6.2 changes only the interface; the calculation engine is the same as in 1.6.1. With Brightway
installed, all 274 automated tests pass. Without it, 270 pass and the four Brightway tests are skipped.

## Findings and checks

**Faint blink every few seconds (reported).**
- Cause: the step header is sticky and had a backdrop blur over scrolling content. Some graphics drivers make
  Chromium re-composite such a layer repeatedly, which shows as a faint blink. With the page idle for 40 seconds
  on the inventory and results steps, the interface itself made no change to the page: no DOM mutation, no
  request, no animation.
- Fix: the header and the welcome overlay no longer use a blur; the header is opaque with a soft shadow.
- No other blur, infinite animation or periodic refresh exists in the interface. The desktop shell checks for
  updates 8 seconds after start and then every 6 hours; that only updates text in the closed Help panel.

**Whole-system check.**
- Automated tests: all of them, with and without Brightway.
- Built-in validation suite: 35 of 35 systems with exact answers pass.
- Every script and engine module compiles.
- No broken relative link in the documentation. Version numbers are consistent.
- Browser sweep at 1000 px (the smallest window) and at 1366 px, on the demo, through:
  - every step and every results tab;
  - every Toolbox tab and every help tab;
  - dark mode.

  The sweep found no script error. It found two places wider than the window at 1000 px, both corrected:
  - a screen-reader label in the inventory table escaped its scroll box;
  - the rule table of the background scenario editor had no scroll box.

The supply chain diagram now ends long names with an ellipsis instead of cutting them mid-word.
