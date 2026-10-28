# NISR census datasets

All figures come from the National Institute of Statistics of Rwanda (NISR), Fifth Rwanda Population and Housing
Census (RPHC5, August 2022) and its 2023–2032 subnational projections. The CSV files in this folder were produced by
`convert_nisr_excel.py` from the Excel workbooks NISR publishes; `python manage.py load_census` imports them.

| CSV | Rows | Built from (NISR workbook, sheet) |
|---|---|---|
| `sector_population_2022.csv` | 416 sectors: resident population by sex and urban/rural | Population size, structure and distribution thematic report — Table D1 |
| `sector_indicators_2022.csv` | 31 indicators × 416 sectors: children, elderly, disability, households and housing, water, electricity, assets, education, poverty, MPI | Children B.1; Elderly 22; Disability D.1; Housing C1.1–C1.4; Education C.35; Non-monetary poverty C.1 & C.10 |
| `area_population_2022.csv` | Rwanda, 5 provinces, 30 districts: population by sex and residence, density, children, youth, women, elderly, disability | Main Indicators Report — Tables 1, 2, 38, 44, 47, 49, 54 |
| `area_indicators_2022.csv` | 16 indicators per country/province/district: urban share, internet use, mobile phones, medical insurance, migration, birth registration, headship, mean/median age… | Main Indicators Report — Tables 2, 21, 25, 28, 32, 39, 40, 45, 47, 48, 50, 54; Population size report Table 4.4 |
| `district_projections_2023_2032.csv` | 30 districts × 10 years: projected population by sex plus age bands (0–17, 16–30, 16–64, 60+, 6–17, 0–4) | Subnational Population Projections (2023–2032), one single-age workbook per district |
| `national_projections_2022_2052.csv` | Rwanda, high/medium/low scenarios | Population Projection thematic report — Table 7 |
| `national_age_groups_2022.csv` | Rwanda by five-year age group | Main Indicators Report — Table 5 |

## Download links (statistics.gov.rw)

Main Indicators: https://statistics.gov.rw/data-sources/censuses/Population-and-Housing-Census/fifth-population-and-housing-census-2022/main-indicators-5th-rwanda-population-and-housing-census-phc
(`PHC5-2022_Main_Indicators.xlsx`, `RPHC5_MainIndicatorsReport_Final.pdf`)

Thematic reports (each page has the PDF and an Excel/CSV "reference document"):
https://statistics.gov.rw/data-sources/censuses/Population-and-Housing-Census/fifth-population-and-housing-census-2022/rphc5-thematic-reports

- Population size, structure and distribution → `Population_size_structure_and_spatial Distribution_Thematic Report.xlsx`
- Socio-economic status of children → `Socio-Economic Status of Children Thematic Report.xlsx`
- Socio-economic status of elderly people → `Socio-Economic status of aged people _Thematic Report.xls`
- Socio-economic status of people with disabilities → `Socio_Economic Status of people with Disability Thematic Report.xlsx`
- Housing and households characteristics → `Housing_and Households Characteristics Thematic_Report.xlsx`
- Educational characteristics → `Education_Thematic_Report.xlsx`
- Non-monetary poverty → `Non Monetary Poverty Thematic Report.xls`
- Population projection → `Population_Projections 2022 Thematic Report.xls`

District projections: https://statistics.gov.rw/fifth-population-and-housing-census-2022/rphc5-district-profiles
(each district's "Subnational Population Projections (2023–2032)" `<District>_single_age.xlsx`).

Also available on the same pages but not yet converted: gender, economic activity, youth, migration, mortality,
fertility, marital status, agriculture and socio-cultural thematic workbooks (district-level tables).

## How cell and village estimates are made

NISR publishes nothing below sector level. The system shares a sector's census population equally among its
villages (from the location import), so a village's estimate is `sector population ÷ villages in the sector` and a
cell's is that share times its number of villages. Leaders with the `manage:census` permission can replace the
estimate with a local count. Every estimate is carried to the current year with the district's NISR projection.
