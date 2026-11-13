# Data Dictionary

All data is **synthetic** and reproducible (`python scripts/setup_demo.py`, seed 42). No patient-identifiable data exists anywhere. Generated from the SQLAlchemy models.


## `app_meta`
Dataset reference date and label.

| Column | Type | Nullable | Key / constraint |
|---|---|---|---|
| key | VARCHAR(40) | no | PK |
| value | VARCHAR(200) | no |  |

## `audit_log`
Append-only audit trail.

| Column | Type | Nullable | Key / constraint |
|---|---|---|---|
| id | INTEGER | no | PK |
| ts | DATETIME | no |  |
| user | VARCHAR(60) | no |  |
| action | VARCHAR(60) | no |  |
| entity | VARCHAR(60) | no |  |
| entity_id | VARCHAR(40) | no |  |
| details | TEXT | no |  |

## `facilities`
Warehouses and hospitals (synthetic names; coordinates are city-level approximations).

| Column | Type | Nullable | Key / constraint |
|---|---|---|---|
| id | INTEGER | no | PK |
| code | VARCHAR(20) | no | unique |
| name | VARCHAR(120) | no |  |
| type | VARCHAR(20) | no |  |
| city | VARCHAR(60) | no |  |
| lat | FLOAT | no |  |
| lon | FLOAT | no |  |
| priority | INTEGER | no |  |
| parent_id | INTEGER | yes | FK -> facilities.id |
| transfer_capacity | INTEGER | no |  |
| has_cold_storage | BOOLEAN | no |  |
| size_factor | FLOAT | no |  |
| active | BOOLEAN | no |  |

Check constraints: `priority between 1 and 3`; `type in ('Warehouse','Hospital')`

## `suppliers`
Synthetic supplier master.

| Column | Type | Nullable | Key / constraint |
|---|---|---|---|
| id | INTEGER | no | PK |
| code | VARCHAR(20) | no | unique |
| name | VARCHAR(120) | no |  |
| city | VARCHAR(60) | no |  |
| lat | FLOAT | no |  |
| lon | FLOAT | no |  |
| promised_lead_days | INTEGER | no |  |
| active | BOOLEAN | no |  |

## `users`
Users with PBKDF2-SHA256 password hashes and role.

| Column | Type | Nullable | Key / constraint |
|---|---|---|---|
| id | INTEGER | no | PK |
| username | VARCHAR(40) | no | unique |
| full_name | VARCHAR(80) | no |  |
| password_hash | VARCHAR(200) | no |  |
| role | VARCHAR(30) | no |  |
| active | BOOLEAN | no |  |
| created_at | DATETIME | no |  |

Check constraints: `role in ('Administrator','Supply Chain Manager','Warehouse Manager','Viewer')`

## `disruption_events`
Disruption events - all labelled simulated.

| Column | Type | Nullable | Key / constraint |
|---|---|---|---|
| id | INTEGER | no | PK |
| type | VARCHAR(40) | no |  |
| description | TEXT | no |  |
| supplier_id | INTEGER | yes | FK -> suppliers.id |
| facility_id | INTEGER | yes | FK -> facilities.id |
| start_date | DATE | no |  |
| end_date | DATE | yes |  |
| severity | VARCHAR(10) | no |  |
| detected_date | DATE | yes |  |
| is_simulated | BOOLEAN | no |  |

## `medicines`
Essential-medicine master data (synthetic costs and demand parameters).

| Column | Type | Nullable | Key / constraint |
|---|---|---|---|
| id | INTEGER | no | PK |
| code | VARCHAR(20) | no | unique |
| name | VARCHAR(120) | no |  |
| category | VARCHAR(60) | no |  |
| unit | VARCHAR(20) | no |  |
| unit_cost | FLOAT | no |  |
| criticality | INTEGER | no |  |
| cold_chain | BOOLEAN | no |  |
| shelf_life_days | INTEGER | no |  |
| base_daily_demand | FLOAT | no |  |
| season | VARCHAR(20) | no |  |
| primary_supplier_id | INTEGER | yes | FK -> suppliers.id |
| active | BOOLEAN | no |  |

Check constraints: `criticality between 1 and 3`; `unit_cost >= 0`

## `alerts`
Generated alerts with reason, action and status.

| Column | Type | Nullable | Key / constraint |
|---|---|---|---|
| id | INTEGER | no | PK |
| key | VARCHAR(160) | no | unique |
| type | VARCHAR(40) | no |  |
| severity | VARCHAR(10) | no |  |
| medicine_id | INTEGER | yes | FK -> medicines.id |
| facility_id | INTEGER | yes | FK -> facilities.id |
| message | TEXT | no |  |
| reason | TEXT | no |  |
| recommended_action | TEXT | no |  |
| status | VARCHAR(20) | no |  |
| created_at | DATETIME | no |  |
| updated_at | DATETIME | no |  |

## `batches`
Batch-level stock with manufacturing/expiry dates and status.

| Column | Type | Nullable | Key / constraint |
|---|---|---|---|
| id | INTEGER | no | PK |
| medicine_id | INTEGER | no | FK -> medicines.id |
| facility_id | INTEGER | no | FK -> facilities.id |
| supplier_id | INTEGER | yes | FK -> suppliers.id |
| batch_no | VARCHAR(40) | no |  |
| mfg_date | DATE | no |  |
| expiry_date | DATE | no |  |
| quantity | INTEGER | no |  |
| status | VARCHAR(20) | no |  |

Check constraints: `expiry_date > mfg_date`; `status in ('Available','Quarantined')`; `quantity >= 0`

## `consumption`
Historical daily consumption per medicine x hospital (synthetic).

| Column | Type | Nullable | Key / constraint |
|---|---|---|---|
| id | INTEGER | no | PK |
| medicine_id | INTEGER | no | FK -> medicines.id |
| facility_id | INTEGER | no | FK -> facilities.id |
| date | DATE | no |  |
| quantity | INTEGER | no |  |

Check constraints: `quantity >= 0`

## `forecasts`
Stored 30-day forecasts with empirical 10-90% range.

| Column | Type | Nullable | Key / constraint |
|---|---|---|---|
| id | INTEGER | no | PK |
| medicine_id | INTEGER | no | FK -> medicines.id |
| facility_id | INTEGER | no | FK -> facilities.id |
| date | DATE | no |  |
| yhat | FLOAT | no |  |
| lo | FLOAT | no |  |
| hi | FLOAT | no |  |
| model | VARCHAR(40) | no |  |

## `inventory_policy`
Editable min/max stock per medicine x facility.

| Column | Type | Nullable | Key / constraint |
|---|---|---|---|
| id | INTEGER | no | PK |
| medicine_id | INTEGER | no | FK -> medicines.id |
| facility_id | INTEGER | no | FK -> facilities.id |
| min_stock | INTEGER | no |  |
| max_stock | INTEGER | no |  |

Check constraints: `min_stock >= 0`; `max_stock >= min_stock`

## `model_metrics`
Hold-out MAE/RMSE/WAPE per model and series.

| Column | Type | Nullable | Key / constraint |
|---|---|---|---|
| id | INTEGER | no | PK |
| medicine_id | INTEGER | no | FK -> medicines.id |
| facility_id | INTEGER | no | FK -> facilities.id |
| model | VARCHAR(40) | no |  |
| mae | FLOAT | no |  |
| rmse | FLOAT | no |  |
| wape | FLOAT | no |  |
| test_days | INTEGER | no |  |
| selected | BOOLEAN | no |  |
| created_at | DATETIME | no |  |

## `purchase_orders`
Purchase orders incl. promised vs actual delivery.

| Column | Type | Nullable | Key / constraint |
|---|---|---|---|
| id | INTEGER | no | PK |
| po_no | VARCHAR(30) | no | unique |
| supplier_id | INTEGER | no | FK -> suppliers.id |
| medicine_id | INTEGER | no | FK -> medicines.id |
| facility_id | INTEGER | no | FK -> facilities.id |
| quantity | INTEGER | no |  |
| order_date | DATE | no |  |
| promised_date | DATE | no |  |
| actual_date | DATE | yes |  |
| delivered_qty | INTEGER | no |  |
| status | VARCHAR(20) | no |  |

## `recommendations`
Recovery-plan actions with approval state.

| Column | Type | Nullable | Key / constraint |
|---|---|---|---|
| id | INTEGER | no | PK |
| plan_id | VARCHAR(30) | no |  |
| priority | INTEGER | no |  |
| kind | VARCHAR(30) | no |  |
| medicine_id | INTEGER | no | FK -> medicines.id |
| source_id | INTEGER | yes | FK -> facilities.id |
| source_name | VARCHAR(120) | no |  |
| dest_id | INTEGER | yes | FK -> facilities.id |
| quantity | INTEGER | no |  |
| est_cost | FLOAT | no |  |
| eta_days | FLOAT | no |  |
| batches | TEXT | no |  |
| reasoning | TEXT | no |  |
| status | VARCHAR(20) | no |  |
| created_at | DATETIME | no |  |
| decided_by | VARCHAR(60) | yes |  |
| decided_at | DATETIME | yes |  |
| comment | TEXT | yes |  |
| approved_qty | INTEGER | yes |  |

## `shipments`
Shipments (supplier->facility, facility->facility), delay days, status.

| Column | Type | Nullable | Key / constraint |
|---|---|---|---|
| id | INTEGER | no | PK |
| ship_no | VARCHAR(30) | no | unique |
| po_id | INTEGER | yes | FK -> purchase_orders.id |
| supplier_id | INTEGER | yes | FK -> suppliers.id |
| origin_id | INTEGER | yes | FK -> facilities.id |
| origin_name | VARCHAR(120) | no |  |
| destination_id | INTEGER | no | FK -> facilities.id |
| medicine_id | INTEGER | no | FK -> medicines.id |
| quantity | INTEGER | no |  |
| dispatch_date | DATE | no |  |
| expected_arrival | DATE | no |  |
| actual_arrival | DATE | yes |  |
| status | VARCHAR(20) | no |  |
| delay_days | INTEGER | no |  |
| transport_mode | VARCHAR(20) | no |  |
| is_simulated | BOOLEAN | no |  |

## `stock_movements`
Receipts, issues, transfers, adjustments, write-offs.

| Column | Type | Nullable | Key / constraint |
|---|---|---|---|
| id | INTEGER | no | PK |
| date | DATE | no |  |
| medicine_id | INTEGER | no | FK -> medicines.id |
| facility_id | INTEGER | no | FK -> facilities.id |
| batch_id | INTEGER | yes | FK -> batches.id |
| type | VARCHAR(20) | no |  |
| quantity | INTEGER | no |  |
| reference | VARCHAR(60) | no |  |
| user | VARCHAR(60) | no |  |
