# Data quality issue registry (Raw layer, Wave 1)

This file is the **Staging check-list**. Every defect below was deliberately introduced in the Raw layer to reproduce what you find in real source-system exports. Staging's job is to fix all of them, and Curated's job is to verify with checks (assertions) that none remain.

Volumes below are for `RANDOM_SEED = 42`. They should match exactly on your machine too: that's a first reproducibility check.

**How to use it:** for each table, check off the defect once it's fixed in Staging and validated in Curated.

---

## Expected volumes after running the Raw scripts

| Raw file | Data rows | Script |
|---|---|---|
| `calendar_export.csv` | 1,826 | `raw_generate_calendar.py` |
| `company_holidays.csv` | 56 | `raw_generate_calendar.py` |
| `vehicle_configs_export.csv` | 13 | `raw_generate_dimensions.py` |
| `crm_clients_export.csv` | 56,284 | `raw_generate_dimensions.py` |
| `crm_sales_team_export.csv` | 90 | `raw_generate_dimensions.py` |
| `plants_export.csv` | 3 | `raw_generate_dimensions.py` |
| `warehouses_export.csv` | 6 | `raw_generate_dimensions.py` |
| `crm_orders_export.csv` | 75,724 | `raw_generate_facts.py` |
| `erp_production_plan_export.csv` | 6,205 | `raw_generate_facts.py` |
| `erp_production_actual_export.csv` | 5,644 | `raw_generate_facts.py` |
| `wms_finished_stock_export.csv` | 11,793 | `raw_generate_facts.py` |

---

## Dim_Calendar

| File | Defect | Expected Staging fix |
|---|---|---|
| `calendar_export.csv` | Two date formats in the same column: US (`MM/DD/YYYY`) before the ERP migration, ISO (`YYYY-MM-DD`) after | Convert to a real date, using `source_system` to pick the format |
| `company_holidays.csv` | The same holiday entered twice with different casing (`New Year's Day` / `NEW YEAR'S DAY`) | Normalize to compare, deduplicate, keep the clean label |

## Dim_Vehicle_Config (`vehicle_configs_export.csv`)

| Defect | Volume | Expected fix |
|---|---|---|
| Duplicated row | 1 | Deduplicate on `config_id` |
| Inconsistent casing/whitespace on `model`, `trim`, `transmission` | ~20% of values | Clean whitespace, normalize casing, keep a clean label for display |
| `list_price_usd` mixes numbers and text (`"$43,900"`) | 5 rows | Strip `$` and commas, convert to a number |
| `end_of_sale_date` blank for configs still on sale | 11 rows | Legitimate blank: keep it as a missing value, don't impute it |

## Dim_Customer (`crm_clients_export.csv`)

| Defect | Volume | Expected fix |
|---|---|---|
| Exact duplicates | 224 | Deduplicate on `customer_id` |
| Country written several different ways (`USA`, `United States`, `US`, `U.S.A.`, `Deutschland`, `Allemagne`...) | 28 distinct values for 13 countries | Mapping table to a single standard label |
| Region with inconsistent casing/whitespace | 22 distinct values for 6 regions | Clean whitespace and casing |
| `customer_segment` missing | 562 | Decision to make and document: label as `Unknown` rather than an arbitrary guess |

## Dim_Salesperson (`crm_sales_team_export.csv`)

| Defect | Volume | Expected fix |
|---|---|---|
| Inconsistent casing/whitespace on salesperson and manager names | ~6% | Clean |
| `sales_manager_id` missing | 2 | Look it up via `sales_manager_name` if possible, otherwise `Unknown` |
| Director name written "First Last" or "LAST, First" | 12 variants for 6 directors | Normalize to "First Last" |

## Dim_Plant (`plants_export.csv`)

| Defect | Volume | Expected fix |
|---|---|---|
| Three date formats in `start_date` (`2019-06-01`, `01-Mar-2020`...) | 3 rows | Parse each format explicitly |
| `models_produced`: several values in one cell, different separators (`,` `;` `\|`) | 3 rows | Split and go to long format (one row per plant/model) |
| Country written `United States` instead of `USA` | 1 row | Align to the standard label |

## Dim_Warehouse (`warehouses_export.csv`)

| Defect | Volume | Expected fix |
|---|---|---|
| `warehouse_type` with different casing and spacing (`Regional hub`, `REGIONAL HUB`, `Regional Hub`...) | 6 rows, 5 variants | Normalize to compare, keep a clean label |

## Fact_Customer_Orders (`crm_orders_export.csv`)

| Defect | Volume | Expected fix |
|---|---|---|
| Exact duplicates (double click) | 376 | Deduplicate (`order_id` must be unique) |
| Inconsistent `order_status` labels (`DELIVERED`, `delivered`...) | ~10% of rows, 16 values for 4 statuses | Normalize to 4 standard statuses |
| `config_id` damaged (casing, whitespace) | ~600 | Clean, then check every value exists in `Dim_Vehicle_Config` |
| Unknown customers (missing from `Dim_Customer`) | 188 | Detect orphans; decision: attach to an `Unknown` customer or isolate in a rejects table |
| `salesperson_id` missing | ~750 | Attach to an `Unknown` salesperson, without dropping the order |
| `production_start_date` earlier than `order_date` | ~140 | Detect the chronological inconsistency; fix or quarantine |
| Production and delivery dates blank for cancelled or not-yet-delivered orders | expected | Legitimate blank: don't impute |
| `order_date` has a time component (`YYYY-MM-DD HH:MM:SS`), the other dates don't | all rows | Convert each column to the right type |

## Fact_Production_Plan (`erp_production_plan_export.csv`)

| Defect | Volume | Expected fix |
|---|---|---|
| Two date formats depending on `source_system` (US before migration, ISO after) | all rows | Parse based on `source_system` |
| Several plan versions for the same week/plant/config (`plan_version` 1 and 2) | ~165 revised rows | Keep the highest version |
| Exact duplicates created by the double load of the first 3 weeks after the migration | ~80 | Deduplicate |
| The week of 12/28/2020 falls before the simulation's start date | 1 week | Weeks are Monday-anchored: decide whether to keep or trim it, and document the choice |

## Fact_Production_Actual (`erp_production_actual_export.csv`)

| Defect | Volume | Expected fix |
|---|---|---|
| Two date formats depending on `source_system` | all rows | Parse based on `source_system` |
| Exact duplicates (same post-migration double load) | 80 | Deduplicate |
| Sparse table: a week with no production has no row | structural | Fill in missing weeks with 0 before comparing to the plan |

## Fact_Finished_Vehicle_Stock (`wms_finished_stock_export.csv`)

| Defect | Volume | Expected fix |
|---|---|---|
| European date format `DD/MM/YYYY` (the project's third format) | all rows | Parse with the right format, never let pandas guess |
| Negative stock values (a movement recorded before receipt) | 35 | Detect; decision: set to 0 or quarantine, and document it |
| Missing weekly snapshots | ~1% of rows | Detect gaps in the week x warehouse x config grid |

---

## Cross-table consistency checks (for Curated)

- Total actual production (86,725 units after deduplication) should reconcile with orders whose production is complete.
- As of 12/31/2025: cumulative deliveries (84,973 units) + vehicles arrived at a hub but not yet handed off (882) + vehicles still in transit to a hub (870) = total production. The last stock snapshot is Sunday 12/28/2025 (793 units), so a few days before that closing date.
- A warehouse's stock can never be negative once data-entry errors are fixed.
- Every `customer_id`, `config_id`, `salesperson_id`, `plant_id`, and `warehouse_id` in the fact tables must exist in its dimension (referential integrity).

## Injected scenario (ground truth)

The events that shape the data's story (semiconductor shortage, Guangzhou lockdown, supplier fire, Ohio strike, ERP migration, demand shocks) are declared in `master_data.py` (`SUPPLY_EVENTS`, `DEMAND_EVENTS`). They will feed `Fact_Diagnosed_Exceptions` and `Ref_Injected_Root_Causes` in Wave 4. This list must **never** be exposed to the AI agent or to Power BI.

## A naming note

Country-name variants injected as messy data (`España`/`Espagne` for Spain, `Brasil`/`Brésil` for Brazil, `Deutschland`/`Allemagne` for Germany) intentionally mix languages, since that's what a real multinational's regional systems tend to produce. This is separate from the project's own code/comments, which are now fully in English. If you'd rather these messy variants stay English-only (typos and abbreviations, no other languages), that's a one-line change in `raw_generate_dimensions.py`'s `COUNTRY_VARIANTS` dictionary.
