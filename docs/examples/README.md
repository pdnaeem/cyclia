# Demonstration files for Cyclia 1.3.5

Every file here is used by an automated test (`engine/tests/test_v135.py`) and by the acceptance criteria in
`docs/quality/ACCEPTANCE_1.3.5.md`. All numbers are invented for the demonstration; none of them is an official factor or
dataset value.

| File | Feature | How to use it |
|---|---|---|
| `factor_matching_demo_factors.csv` | Factor matching validation | Start the feature demo. In Toolbox > Validation > Factor matching, choose this file and the categories climate change and acidification of the "Demo EF-style method". Expected result: methane differs, N2O is only in Cyclia, SF6 is unresolved, and acidification is identical |
| `factor_matching_demo_results.csv` | Factor matching validation | Add it as the other tool's results. Expected: for climate change the whole difference is explained by the factors; for the concrete wall's acidification, 2 % is an "other" difference |
| `epd_profile_example.json` | EPD programme profiles | Step 6 > EPD > Your own programme profile > Load profile |
| `ilcd_process_with_dqr.xml` | Data quality of EF datasets | A fragment of an ILCD process dataset. Its data quality indicators give TeR 2, GeR 1, TiR 3, P 2, DQR 2.0 |
| `aware_factors_template.csv` | AWARE | The columns of the AWARE factor table. Replace the example row with the official AWARE 2.0 country and watershed values |
| `lanca_factors_template.csv` | LANCA | The columns of the LANCA factor table. Replace the example row with the official LANCA factors |
| `social_data_template.csv` | Social LCA | The columns of the social data table (match, location, worker_hours, stakeholder, indicator, risk, source) |
| `mfa_aluminium_example.json` | Material flows | The aluminium example of Toolbox > Material flows (also "Load example"). Expected: the mass balance closes in every year from 2020 to 2060 |
