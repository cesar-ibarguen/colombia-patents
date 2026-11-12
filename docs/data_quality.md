# Data quality report: patent applications in Colombia

Source: Superintendencia de Industria y Comercio (SIC), patent applications 2000–2021,
file `Patentes_presentadas.csv` (46,582 rows, 14 columns).

## Findings and how they were handled

| # | Finding | Treatment |
|---|---|---|
| 1 | `Año Presentación` stored as text with a thousands separator (`"2,017"`) | Compared with the year of the date: **0** differences. Redundant, so it was dropped (use `YEAR(filing_date)`). |
| 2 | `Region` had 6,074 empty values and 5,011 `NOT DEFINED` | Both unified as `NULL`. |
| 3 | `Residente` stored as text | Converted to boolean. Anomaly: **1** application marked as resident with a country other than Colombia (PPR028088 → DE); kept as in the source. |
| 4 | `Sector` empty in 144 applications | Kept as `NULL`. Sector names translated to the five WIPO sectors. |
| 5 | `Naturaleza` fully determines `Trámite` and `Vía` (verified functional dependency) | The three columns moved to the lookup table `application_type`; `application` keeps only `type_id` (3NF). |
| 6 | `Pais` code determines `Pais Nombre` | Stored once in the table `country` (names translated to English). |
| 7 | 7,525 applications have several applicants separated by `;` | Split into the bridge table `application_applicant`. |
| 8 | The applicant's country code is embedded in the name (`COMPANY (US)`) | Extracted to `country_code`. **45** mentions have no code (or an empty `()`). |
| 9 | The same company appears under several spellings (e.g. `BAYER CROPSCIENCE AG`, `BAYER CROPSCIENCE AG.`, `BAYER CROPSCIENCE AKTIENGESELLSCHAFT`) | **Not merged automatically**, to avoid joining different entities by mistake. For analysis by company, group with `LIKE` or build a mapping table. |
| 10 | 33,226 applications (71%) have several inventors (up to 130) | Split into `application_inventor`. 12 repeated inventors and 10 repeated applicants within the same application were removed. 31 applications have no inventor. |

**Limitation:** inventors with the same name are treated as the same person, because the
source has no inventor identifier.

## Resulting tables

| Table | Rows |
|---|---:|
| `country` | 100 |
| `sector` | 5 |
| `application_type` | 5 |
| `application` | 46,582 |
| `applicant` | 16,278 |
| `inventor` | 83,230 |
| `application_applicant` | 50,452 |
| `application_inventor` | 165,859 |

Database `patents`. Table and column names are in English after running `setup/to_english.py`
(the normalization script produces the Spanish names of the source).

## Verification

All 46,582 applications were rebuilt from the normalized tables (applicants, inventors,
date, country and residence) and compared with the original CSV row by row:
**100% match**.
