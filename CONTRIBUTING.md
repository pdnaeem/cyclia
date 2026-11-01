# Contributing to Cyclia

Thank you for helping. Cyclia is research software: correctness comes first, then clarity for users who do
not program.

## Reporting a problem

Open an issue with what you did, what you expected and what happened. Help > About > "Export diagnostics"
creates a zip with the error log and system information (no project data) that you can attach. Never attach
ecoinvent data or other licensed databases.

## Changing code

1. Fork the repository and create a branch.
2. Install the engine requirements: `pip install -r engine/requirements.txt`.
3. Run the tests before and after your change: `python -m unittest discover -s engine/tests`.
4. A change to a calculation needs a test with a hand-calculated or published reference value, and, where it
   applies, a case in the validation suite (`engine/trust.py`).
5. Describe the scientific basis of a new method in `docs/METHODS.md` with references.
6. Open a pull request that explains the change and how it was checked.

## Style

Python: standard library and the packages in `engine/requirements.txt` only; functions documented with the
method and its source. Interface: plain JavaScript, no build step; text written for researchers who are not
software specialists.

## Conduct

Be respectful and constructive. Criticise ideas and code, not people. Maintainers may remove contributions
or comments that are abusive.
