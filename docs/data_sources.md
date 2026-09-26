# Data sources

All five sources are public US government data (public domain). None needs a
data use agreement. Row counts are filled in from `rpt_source_row_counts`
after a real run.

| Source | Publisher | Vintage used | Grain | Approx. size | Key fields used |
|---|---|---|---|---|---|
| [Medicare Part D Prescribers - by Provider and Drug](https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/medicare-part-d-prescribers-by-provider-and-drug) | CMS | data year 2021 | NPI x brand x generic | ~25M rows, ~3 GB CSV | `Prscrbr_NPI`, `Prscrbr_Type`, `Brnd_Name`, `Gnrc_Name`, `Tot_30day_Fills`, `Tot_Drug_Cst` |
| [Medicare Part D Prescribers - by Provider](https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/medicare-part-d-prescribers-by-provider) | CMS | data year 2021 | NPI | ~1M rows | totals, `Brnd_Tot_Clms`, `Opioid_*`, `Bene_Avg_Risk_Scre`, `Bene_Dual_Cnt`, `LIS_Tot_Clms` |
| [Open Payments General Payment Data](https://openpaymentsdata.cms.gov/) | CMS | program year 2021 | payment record | ~12M rows, ~6 GB CSV | `Covered_Recipient_NPI`, `Total_Amount_of_Payment_USDollars`, `Nature_of_Payment_or_Transfer_of_Value`, product slots 1-5 |
| [LEIE - List of Excluded Individuals/Entities](https://oig.hhs.gov/exclusions/exclusions_list.asp) | HHS-OIG | snapshot at download | exclusion | ~80K rows | `NPI`, `EXCLTYPE`, `EXCLDATE` |
| [NPPES NPI registry](https://download.cms.gov/nppes/NPI_Files.html) | CMS | monthly file at download | NPI | ~8M rows, ~10 GB CSV | entity type, taxonomy slots, practice state, enumeration / deactivation dates |

Sizes are approximate and vary by release. The loader keeps only the columns
listed in `config/pipeline.yml`, which cuts NPPES from about 330 columns to 45.

## Known quirks and how they are handled

| Quirk | Handling |
|---|---|
| Part D drug rows with fewer than 11 claims are suppressed | Documented. Prescriber brand shares cover only unsuppressed drugs; the cohort needs at least 100 fills to limit the effect |
| Part D prescriber-level cells below 11 are blank | Cast to NULL; controls are median-imputed with a missingness flag |
| File layouts and URLs change between releases | URLs are resolved from catalogs at run time; columns are checked against `config/pipeline.yml` with close-match suggestions |
| LEIE uses `00000000` for "no date" and `0000000000` for "no NPI" | Converted to NULL in `stg_leie__exclusions` |
| LEIE drops reinstated individuals | Documented limitation: excluded-then-reinstated prescribers are not counted as events |
| LEIE code `1160` (8 records in the Sept 2026 file) is not on OIG's exclusion-authorities page | Kept as exclusions with theme `unmapped`; the dbt relationships test warns so it stays visible |
| Part D brand names that differ only in punctuation ("Easy Touch" / "Easy-Touch") collapse to one key | Fills are summed; the uniqueness test warns (4 rows in 2021) |
| Open Payments NPI is blank for teaching hospitals and some recipients | Teaching hospitals are excluded; match rate is reported by `analyses/open_payments_npi_match_rate.sql` |
| Open Payments free text contains embedded newlines and commas | Parsed with pandas' quote-aware reader before loading; raw tables are loaded as Parquet, not CSV |
| Brand/generic is not an explicit field at drug level | Name-based rule, validated against CMS's prescriber-level split ([ADR 0002](decisions/0002-brand-generic-classification.md)) |

## Provenance

Every load writes `partd_raw.load_provenance`: source URL, SHA-256 of the
downloaded file, byte size, download and load timestamps, row count and an
`is_synthetic` flag. `rpt_data_provenance` surfaces it, and the results step
reads it before publishing anything.
