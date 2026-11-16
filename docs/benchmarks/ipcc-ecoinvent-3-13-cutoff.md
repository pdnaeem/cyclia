# IPCC benchmark: Cyclia against ecoinvent's cumulative LCIA results

Database: ecoinvent (3.13, cutoff)

**IPCC 2013**: Validated. 100.00 % of 400 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**IPCC 2013 no LT**: Validated. 100.00 % of 400 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**IPCC 2021**: Validated. 100.00 % of 1,600 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**IPCC 2021 (GHG Protocol mandatory)**: Validated. 100.00 % of 1,100 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**IPCC 2021 (GHG Protocol mandatory) no LT**: Validated. 100.00 % of 1,100 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**IPCC 2021 (incl. biogenic CO2)**: Validated. 100.00 % of 500 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**IPCC 2021 (incl. biogenic CO2) no LT**: Validated. 100.00 % of 500 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

**IPCC 2021 no LT**: Validated. 100.00 % of 1,600 results within 0.1 % of ecoinvent's value, 100.00 % within 1 %.

## What was compared

- Reference: ecoinvent's own cumulative LCIA results for ecoinvent (3.13, cutoff), the file ecoinvent provides to licence holders with the database. Cyclia imported the same database (ecoSpold2) and the method, calculated every sampled dataset with its full supply chain and compared the scores, result by result.
- Results compared: 7,200 (datasets x impact categories).
- Datasets: 100 compared of 27,401 in the results file, matched by 'Activity UUID_Product UUID' (or by name, geography and product).
- The cumulative inventory was compared with ecoinvent's cumulative LCI as well, which separates deviations caused by the inventory from those caused by the factors.
- Software: Cyclia 1.9.0; run on 2026-11-16.

## Deviation per impact category

Deviation = |Cyclia - ecoinvent| / |ecoinvent| x 100, per dataset. Signed median: negative when Cyclia is lower for most datasets.

| Method | Category | Indicator | Unit | Results | Median % | Signed median % | 95th percentile % | Max % | Within 0.1 % | Within 1 % | Within round-off |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| IPCC 2013 | climate change | global temperature change potential (GTP100) | kg CO2-Eq | 100 | 2.16e-07 | 0 | 5.11e-06 | 0.000308 | 100 % | 100 % |  |
| IPCC 2013 | climate change | global temperature change potential (GTP20) | kg CO2-Eq | 100 | 2.15e-07 | 0 | 5.03e-06 | 0.000248 | 100 % | 100 % |  |
| IPCC 2013 | climate change | global warming potential (GWP100) | kg CO2-Eq | 100 | 2.06e-07 | 0 | 5.07e-06 | 0.000278 | 100 % | 100 % |  |
| IPCC 2013 | climate change | global warming potential (GWP20) | kg CO2-Eq | 100 | 2.19e-07 | 0 | 5.03e-06 | 0.000235 | 100 % | 100 % |  |
| IPCC 2013 no LT | climate change no LT | global temperature change potential (GTP100) no LT | kg CO2-Eq | 100 | 2.16e-07 | 0 | 5.11e-06 | 0.000308 | 100 % | 100 % |  |
| IPCC 2013 no LT | climate change no LT | global temperature change potential (GTP20) no LT | kg CO2-Eq | 100 | 2.15e-07 | 0 | 5.03e-06 | 0.000248 | 100 % | 100 % |  |
| IPCC 2013 no LT | climate change no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 2.06e-07 | 0 | 5.07e-06 | 0.000278 | 100 % | 100 % |  |
| IPCC 2013 no LT | climate change no LT | global warming potential (GWP20) no LT | kg CO2-Eq | 100 | 2.19e-07 | 0 | 5.03e-06 | 0.000235 | 100 % | 100 % |  |
| IPCC 2021 | climate change: aircraft emissions | global warming potential (GWP100) | kg CO2-Eq | 100 | 1.85e-06 | 7.36e-07 | 6.8e-05 | 0.00168 | 100 % | 100 % |  |
| IPCC 2021 | climate change: biogenic (excl. CO2) | global warming potential (GWP100) | kg CO2-Eq | 100 | 1.16e-06 | 0 | 5.68e-05 | 0.000466 | 100 % | 100 % |  |
| IPCC 2021 | climate change: biogenic (excl. CO2, incl. SLCFs) | global warming potential (GWP100) | kg CO2-Eq | 100 | 1.12e-06 | 0 | 4.92e-05 | 0.000337 | 100 % | 100 % |  |
| IPCC 2021 | climate change: direct land use change | global warming potential (GWP100) | kg CO2-Eq | 100 | 3.35e-07 | 0 | 1.16e-05 | 0.000106 | 100 % | 100 % |  |
| IPCC 2021 | climate change: direct land use change (incl. SLCFs) | global warming potential (GWP100) | kg CO2-Eq | 100 | 3.36e-07 | 0 | 1.16e-05 | 0.000104 | 100 % | 100 % |  |
| IPCC 2021 | climate change: emissions from direct land use change | global warming potential (GWP100) | kg CO2-Eq | 100 | 3.37e-07 | 0 | 1.14e-05 | 0.000106 | 100 % | 100 % |  |
| IPCC 2021 | climate change: fossil | global warming potential (GWP100) | kg CO2-Eq | 100 | 2.26e-07 | 0 | 5.04e-06 | 0.0003 | 100 % | 100 % |  |
| IPCC 2021 | climate change: fossil (excl. biogenic CO2, incl. SLCFs) | global warming potential (GWP100) | kg CO2-Eq | 100 | 2.26e-07 | 0 | 5.06e-06 | 0.000293 | 100 % | 100 % |  |
| IPCC 2021 | climate change: fossil emissions (excl. aircraft emissions) | global warming potential (GWP100) | kg CO2-Eq | 100 | 2.26e-07 | 0 | 5.04e-06 | 0.0003 | 100 % | 100 % |  |
| IPCC 2021 | climate change: removals from direct land use change | global warming potential (GWP100) | kg CO2-Eq | 100 | 7.89e-07 | 0 | 1.59e-05 | 0.00075 | 100 % | 100 % |  |
| IPCC 2021 | climate change: total (excl. biogenic CO2) | global temperature change potential (GTP100) | kg CO2-Eq | 100 | 2.14e-07 | 0 | 5.08e-06 | 0.000312 | 100 % | 100 % |  |
| IPCC 2021 | climate change: total (excl. biogenic CO2) | global temperature change potential (GTP50) | kg CO2-Eq | 100 | 2.1e-07 | 0 | 5.07e-06 | 0.000305 | 100 % | 100 % |  |
| IPCC 2021 | climate change: total (excl. biogenic CO2) | global warming potential (GWP100) | kg CO2-Eq | 100 | 2.05e-07 | 0 | 5.06e-06 | 0.00029 | 100 % | 100 % |  |
| IPCC 2021 | climate change: total (excl. biogenic CO2) | global warming potential (GWP20) | kg CO2-Eq | 100 | 2.21e-07 | 0 | 5e-06 | 0.000257 | 100 % | 100 % |  |
| IPCC 2021 | climate change: total (excl. biogenic CO2) | global warming potential (GWP500) | kg CO2-Eq | 100 | 2.17e-07 | 0 | 5.1e-06 | 0.000311 | 100 % | 100 % |  |
| IPCC 2021 | climate change: total (excl. biogenic CO2, incl. SLCFs) | global warming potential (GWP100) | kg CO2-Eq | 100 | 2.05e-07 | 0 | 5.07e-06 | 0.000279 | 100 % | 100 % |  |
| IPCC 2021 (GHG Protocol mandatory) | climate change: CH4 | global warming potential (GWP100) | kg CO2-Eq | 100 | 2.95e-07 | 0 | 4.12e-06 | 0.000145 | 100 % | 100 % |  |
| IPCC 2021 (GHG Protocol mandatory) | climate change: CH4, LULUCF | global warming potential (GWP100) | kg CO2-Eq | 100 | 1.08e-06 | 1.09e-10 | 2.47e-05 | 0.000175 | 100 % | 100 % |  |
| IPCC 2021 (GHG Protocol mandatory) | climate change: CO2, fossil | global warming potential (GWP100) | kg CO2-Eq | 100 | 2.4e-07 | 0 | 7.81e-06 | 0.000323 | 100 % | 100 % |  |
| IPCC 2021 (GHG Protocol mandatory) | climate change: CO2, LULUCF | global warming potential (GWP100) | kg CO2-Eq | 100 | 3.35e-07 | 0 | 1.16e-05 | 0.000107 | 100 % | 100 % |  |
| IPCC 2021 (GHG Protocol mandatory) | climate change: CO2, non-fossil | global warming potential (GWP100) | kg CO2-Eq | 100 | 1.63e-06 | 0 | 0.000311 | 0.00224 | 100 % | 100 % |  |
| IPCC 2021 (GHG Protocol mandatory) | climate change: HFC | global warming potential (GWP100) | kg CO2-Eq | 100 | 4.7e-07 | 1.23e-08 | 1.65e-05 | 0.000262 | 100 % | 100 % |  |
| IPCC 2021 (GHG Protocol mandatory) | climate change: N2O | global warming potential (GWP100) | kg CO2-Eq | 100 | 1.17e-07 | -1.56e-08 | 3.79e-06 | 6.54e-05 | 100 % | 100 % |  |
| IPCC 2021 (GHG Protocol mandatory) | climate change: NF3 | global warming potential (GWP100) | kg CO2-Eq | 100 | 3.95e-07 | 0 | 1.91e-05 | 0.000708 | 100 % | 100 % |  |
| IPCC 2021 (GHG Protocol mandatory) | climate change: PFC | global warming potential (GWP100) | kg CO2-Eq | 100 | 5.35e-06 | -7.29e-07 | 0.000176 | 0.00334 | 100 % | 100 % |  |
| IPCC 2021 (GHG Protocol mandatory) | climate change: SF6 | global warming potential (GWP100) | kg CO2-Eq | 100 | 4.87e-07 | -2.35e-08 | 1.85e-05 | 0.000781 | 100 % | 100 % |  |
| IPCC 2021 (GHG Protocol mandatory) | climate change: total mandatory GHGs (excl. biogenic CO2) | global warming potential (GWP100) | kg CO2-Eq | 100 | 2.05e-07 | 0 | 5.06e-06 | 0.00029 | 100 % | 100 % |  |
| IPCC 2021 (GHG Protocol mandatory) no LT | climate change: CH4 no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 2.95e-07 | 0 | 4.12e-06 | 0.000145 | 100 % | 100 % |  |
| IPCC 2021 (GHG Protocol mandatory) no LT | climate change: CH4, LULUCF no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 1.08e-06 | 1.09e-10 | 2.47e-05 | 0.000175 | 100 % | 100 % |  |
| IPCC 2021 (GHG Protocol mandatory) no LT | climate change: CO2, fossil no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 2.4e-07 | 0 | 7.81e-06 | 0.000323 | 100 % | 100 % |  |
| IPCC 2021 (GHG Protocol mandatory) no LT | climate change: CO2, LULUCF no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 3.35e-07 | 0 | 1.16e-05 | 0.000107 | 100 % | 100 % |  |
| IPCC 2021 (GHG Protocol mandatory) no LT | climate change: CO2, non-fossil no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 1.63e-06 | 0 | 0.000311 | 0.00224 | 100 % | 100 % |  |
| IPCC 2021 (GHG Protocol mandatory) no LT | climate change: HFC no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 4.7e-07 | 1.23e-08 | 1.65e-05 | 0.000262 | 100 % | 100 % |  |
| IPCC 2021 (GHG Protocol mandatory) no LT | climate change: N2O no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 1.17e-07 | -1.56e-08 | 3.79e-06 | 6.54e-05 | 100 % | 100 % |  |
| IPCC 2021 (GHG Protocol mandatory) no LT | climate change: NF3 no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 3.95e-07 | 0 | 1.91e-05 | 0.000708 | 100 % | 100 % |  |
| IPCC 2021 (GHG Protocol mandatory) no LT | climate change: PFC no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 5.35e-06 | -7.29e-07 | 0.000176 | 0.00334 | 100 % | 100 % |  |
| IPCC 2021 (GHG Protocol mandatory) no LT | climate change: SF6 no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 4.87e-07 | -2.35e-08 | 1.85e-05 | 0.000781 | 100 % | 100 % |  |
| IPCC 2021 (GHG Protocol mandatory) no LT | climate change: total mandatory GHGs (excl. biogenic CO2) no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 2.05e-07 | 0 | 5.06e-06 | 0.00029 | 100 % | 100 % |  |
| IPCC 2021 (incl. biogenic CO2) | climate change: biogenic (incl. CO2) | global warming potential (GWP100) | kg CO2-Eq | 100 | 6.35e-07 | 0 | 0.000118 | 0.00115 | 100 % | 100 % |  |
| IPCC 2021 (incl. biogenic CO2) | climate change: biogenic emissions (incl. CO2) | global warming potential (GWP100) | kg CO2-Eq | 100 | 5.41e-07 | -1.09e-07 | 1.72e-05 | 0.00044 | 100 % | 100 % |  |
| IPCC 2021 (incl. biogenic CO2) | climate change: biogenic removals (incl. CO2) | global warming potential (GWP100) | kg CO2-Eq | 100 | 9.83e-07 | 2.31e-08 | 2.84e-05 | 0.00219 | 100 % | 100 % |  |
| IPCC 2021 (incl. biogenic CO2) | climate change: total (incl. biogenic CO2) | global warming potential (GWP100) | kg CO2-Eq | 100 | 1.88e-07 | 0 | 7.25e-06 | 0.000281 | 100 % | 100 % |  |
| IPCC 2021 (incl. biogenic CO2) | climate change: total (incl. biogenic CO2, incl. SLCFs) | global warming potential (GWP100) | kg CO2-Eq | 100 | 1.89e-07 | 0 | 7.13e-06 | 0.000267 | 100 % | 100 % |  |
| IPCC 2021 (incl. biogenic CO2) no LT | climate change: biogenic (incl. CO2) no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 6.35e-07 | 0 | 0.000118 | 0.00115 | 100 % | 100 % |  |
| IPCC 2021 (incl. biogenic CO2) no LT | climate change: biogenic emissions (incl. CO2) no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 5.41e-07 | -1.09e-07 | 1.72e-05 | 0.00044 | 100 % | 100 % |  |
| IPCC 2021 (incl. biogenic CO2) no LT | climate change: biogenic removals (incl. CO2) no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 9.83e-07 | 2.31e-08 | 2.84e-05 | 0.00219 | 100 % | 100 % |  |
| IPCC 2021 (incl. biogenic CO2) no LT | climate change: total (incl. biogenic CO2) no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 1.88e-07 | 0 | 7.25e-06 | 0.000281 | 100 % | 100 % |  |
| IPCC 2021 (incl. biogenic CO2) no LT | climate change: total (incl. biogenic CO2, incl. SLCFs) no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 1.89e-07 | 0 | 7.13e-06 | 0.000267 | 100 % | 100 % |  |
| IPCC 2021 no LT | climate change: aircraft emissions no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 1.85e-06 | 7.36e-07 | 6.8e-05 | 0.00168 | 100 % | 100 % |  |
| IPCC 2021 no LT | climate change: biogenic (excl. CO2) no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 1.16e-06 | 0 | 5.68e-05 | 0.000466 | 100 % | 100 % |  |
| IPCC 2021 no LT | climate change: biogenic (excl. CO2, incl. SLCFs) no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 1.12e-06 | 0 | 4.92e-05 | 0.000337 | 100 % | 100 % |  |
| IPCC 2021 no LT | climate change: direct land use change (incl. SLCFs) no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 3.36e-07 | 0 | 1.16e-05 | 0.000104 | 100 % | 100 % |  |
| IPCC 2021 no LT | climate change: direct land use change no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 3.35e-07 | 0 | 1.16e-05 | 0.000106 | 100 % | 100 % |  |
| IPCC 2021 no LT | climate change: emissions from direct land use change no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 3.37e-07 | 0 | 1.14e-05 | 0.000106 | 100 % | 100 % |  |
| IPCC 2021 no LT | climate change: fossil (excl. biogenic CO2, incl. SLCFs) no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 2.26e-07 | 0 | 5.06e-06 | 0.000293 | 100 % | 100 % |  |
| IPCC 2021 no LT | climate change: fossil emissions (excl. aircraft emissions) no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 2.26e-07 | 0 | 5.04e-06 | 0.0003 | 100 % | 100 % |  |
| IPCC 2021 no LT | climate change: fossil no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 2.26e-07 | 0 | 5.04e-06 | 0.0003 | 100 % | 100 % |  |
| IPCC 2021 no LT | climate change: removals from direct land use change no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 7.89e-07 | 0 | 1.59e-05 | 0.00075 | 100 % | 100 % |  |
| IPCC 2021 no LT | climate change: total (excl. biogenic CO2) no LT | global temperature change potential (GTP100) no LT | kg CO2-Eq | 100 | 2.14e-07 | 0 | 5.08e-06 | 0.000312 | 100 % | 100 % |  |
| IPCC 2021 no LT | climate change: total (excl. biogenic CO2) no LT | global temperature change potential (GTP50) no LT | kg CO2-Eq | 100 | 2.1e-07 | 0 | 5.07e-06 | 0.000305 | 100 % | 100 % |  |
| IPCC 2021 no LT | climate change: total (excl. biogenic CO2) no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 2.05e-07 | 0 | 5.06e-06 | 0.00029 | 100 % | 100 % |  |
| IPCC 2021 no LT | climate change: total (excl. biogenic CO2) no LT | global warming potential (GWP20) no LT | kg CO2-Eq | 100 | 2.21e-07 | 0 | 5e-06 | 0.000257 | 100 % | 100 % |  |
| IPCC 2021 no LT | climate change: total (excl. biogenic CO2) no LT | global warming potential (GWP500) no LT | kg CO2-Eq | 100 | 2.17e-07 | 0 | 5.1e-06 | 0.000311 | 100 % | 100 % |  |
| IPCC 2021 no LT | climate change: total (excl. biogenic CO2, incl. SLCFs) no LT | global warming potential (GWP100) no LT | kg CO2-Eq | 100 | 2.05e-07 | 0 | 5.07e-06 | 0.000279 | 100 % | 100 % |  |

## How to read this

- 'Validated' requires that at least 95 % of all results agree within 0.1 % and that every category has at least 95 % of its results within 1 %. A category below that is named above and its results should not be published before the cause is found.
- The benchmark checks Cyclia's matrix calculation, its import of ecoinvent and the matching of the method's factors to ecoinvent's elementary flows. It does not check the method itself: Cyclia uses the factors as published.
- Only the ecoinvent version and system model named were compared. Another version or system model needs its own run.
- 'Within round-off' counts results whose net value is the small remainder of positive and negative contributions that cancel, and where the gap to ecoinvent is below 1e-9 of the sum of the absolute contributions (Cyclia 1.9.1 and later; empty for earlier runs). These count as agreeing.
- No ecoinvent data is reproduced here: the report holds deviation statistics only.

## Reproduce

1. Import the ecoinvent database (ecoSpold2) and the method in Cyclia.
2. Validation > ecoinvent: choose ecoinvent's cumulative LCIA results file for the same version and system model (optionally the cumulative LCI file too) and run the benchmark.
3. Validation > Benchmark Centre > Publish benchmark reports writes this file.
