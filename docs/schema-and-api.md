# Tracefront: current schema and API

Updated 2026-10-18 for durable analyses and stored lot investigations. Earlier examples below are abbreviated; trace responses now contain additional fields documented in section 5. The backend integration tests use an isolated database; ML sample examples use trained models.

There are two services:

| Service | Code | Port | Where it runs now |
|---|---|---|---|
| **Backend** (database, uploads, trace) | `backend/` | 8000 | LinuxONE, always on (`tracefront-backend` service, PostgreSQL 16) |
| **ML service** (pathogen models) | `food-risk-ml/` | 8100 | `tracefront-ml` on LinuxONE after combined deployment; local command: `uvicorn src.api.app:app --port 8100` |

Reach the server's backend with `ssh -L 8000:127.0.0.1:8000 linux1@148.100.77.171`, then use `http://localhost:8000`. Interactive docs are at `/docs` on both services.

---

## 1. Database schema (backend)

The tables are created from `backend/app/models.py` when the backend starts. Existing tables are never altered.

```
organizations ──< batches ──< batch_relationships >── batches
      │              │   (parent = ingredient, child = product made from it)
      │              ├──< lab_results
      │              └──< shipments ──< sensor_readings
      └──────────────────────┘ (from_org_id, to_org_id)
```

PostgreSQL enforces all 8 foreign keys. A row that points to a missing parent is rejected.

### organizations
| Column | Type | Null | Notes |
|---|---|---|---|
| `organization_id` | integer | PK | |
| `name` | text | no | |
| `type` | text | no | intended values `supplier` / `factory` / `warehouse` / `store`; not enforced |

### batches
An ingredient batch or a finished-product batch.

| Column | Type | Null | Notes |
|---|---|---|---|
| `batch_id` | integer | PK | the caller chooses it (not auto-numbered) |
| `product_name` | text | no | free text |
| `organization_id` | integer | no | FK → organizations, the producer |
| `produced_at` | timestamp (no time zone) | no | |
| `status` | text | no | default `normal`; free text |

### batch_relationships
One row for each ingredient batch used in a product batch.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | integer | PK | auto |
| `parent_batch_id` | integer | no | FK → batches (the ingredient) |
| `child_batch_id` | integer | no | FK → batches (the product) |
| `quantity_used` | float | no | no unit stored |

### shipments
One batch moving from one organization to another.

| Column | Type | Null | Notes |
|---|---|---|---|
| `shipment_id` | integer | PK | |
| `batch_id` | integer | no | FK → batches (exactly one batch per shipment) |
| `from_org_id` | integer | no | FK → organizations |
| `to_org_id` | integer | no | FK → organizations |
| `quantity` | float | no | no unit stored |
| `status` | text | no | default `pending`; free text |
| `departed_at` | timestamp | yes | |
| `eta` | timestamp | yes | |

### sensor_readings
| Column | Type | Null | Notes |
|---|---|---|---|
| `reading_id` | integer | PK | auto |
| `shipment_id` | integer | no | FK → shipments |
| `timestamp` | timestamp | no | |
| `temperature` | float | yes | °C |
| `humidity` | float | yes | % RH |

### lab_results
| Column | Type | Null | Notes |
|---|---|---|---|
| `lab_result_id` | integer | PK | auto |
| `batch_id` | integer | no | FK → batches |
| `tested_at` | timestamp | no | |
| `contaminant` | text | yes | e.g. `Salmonella` |
| `result` | text | no | intended values `positive` / `negative`; not enforced |

**Additional tables:** `analyses` stores immutable findings/distribution JSON documents, dataset ID and creation time; `batch_lots` maps integer batch IDs to external lot codes unique per producer; `shipment_manifests` maps shipment IDs to external codes unique per origin and explicit quantity units; `synthetic_batches` records demo provenance so simulated lots stay labelled after refresh. All are additive; no existing table is dropped or altered. Raw uploaded bytes and pathogen-model predictions are not stored.

---

## 2. Backend API (port 8000)

| # | Method | Path | What it does |
|---|---|---|---|
| 2.1 | GET | `/api/health` | Is the backend up |
| 2.2 | GET | `/api/batches` | List all batches |
| 2.3 | POST | `/api/batches` | Create a batch |
| 2.4 | POST | `/api/sensor-readings` | Store a temperature/humidity reading for a shipment |
| 2.5 | POST | `/api/lab-results` | Store a lab result for a batch |
| 2.6 | GET | `/api/batches/{batch_id}/trace` | Ingredient batches upstream, product batches downstream |
| 2.7 | GET | `/api/shipments/{shipment_id}/risk` | Rule-based temperature score for a shipment |
| 2.8 | POST | `/api/analyses` | Upload a shipment file and analyse it |
| 2.9 | GET | `/api/analyses/{analysis_id}/findings` | Findings for an upload |
| 2.10 | GET | `/api/analyses/{analysis_id}/distribution` | Distributor → route → batch → recipient graph for an upload |

**Errors:**
- **Wrong or missing JSON fields** return **422**, with one entry per problem:
  ```json
  {"detail": [{"type": "missing", "loc": ["body", "organization_id"], "msg": "Field required", "input": {"batch_id": 7, "product_name": "x"}}]}
  ```
- **Other errors** return `{"detail": "<message>"}` with the status listed for each endpoint.
- **Missing referenced parents** return **404**. Duplicate IDs or scoped codes return **409**. Ingredient self-links/cycles return **400**. SQLite connections also enforce foreign keys for local verification.

### 2.1 GET /api/health
No parameters. Checks database connectivity and returns `200`:
```json
{"status": "ok", "analysis_storage": "database"}
```

### 2.2 GET /api/batches
No parameters. Returns `200` with an array of batches in the same shape as 2.3's response, or `[]`.

### 2.3 POST /api/batches
JSON body:

| Field | Type | Required | Notes |
|---|---|---|---|
| `batch_id` | integer | yes | must be unique |
| `product_name` | string | yes | |
| `organization_id` | integer | yes | must already exist in `organizations` |
| `produced_at` | datetime (ISO 8601) | yes | |
| `status` | string | no | default `normal` |

```json
{"batch_id": 42, "product_name": "Chicken Wrap CW-42", "organization_id": 2, "produced_at": "2026-10-16T09:00:00"}
```
Returns `201`:
```json
{"batch_id": 42, "product_name": "Chicken Wrap CW-42", "organization_id": 2, "produced_at": "2026-10-16T09:00:00", "status": "normal"}
```

### 2.4 POST /api/sensor-readings
| Field | Type | Required | Notes |
|---|---|---|---|
| `shipment_id` | integer | yes | must already exist in `shipments` |
| `timestamp` | datetime | yes | |
| `temperature` | number | no | °C |
| `humidity` | number | no | % RH |

```json
{"shipment_id": 17, "timestamp": "2026-10-17T06:30:00", "temperature": 13.2, "humidity": 70}
```
Returns `200` with the stored row and its new `reading_id`:
```json
{"shipment_id": 17, "timestamp": "2026-10-17T06:30:00", "temperature": 13.2, "humidity": 70.0, "reading_id": 1}
```

### 2.5 POST /api/lab-results
| Field | Type | Required | Notes |
|---|---|---|---|
| `batch_id` | integer | yes | must already exist |
| `tested_at` | datetime | yes | |
| `contaminant` | string | no | |
| `result` | string | yes | `positive` / `negative` by convention |

```json
{"batch_id": 42, "tested_at": "2026-10-17T12:00:00", "contaminant": "Salmonella", "result": "positive"}
```
Returns `200`:
```json
{"batch_id": 42, "tested_at": "2026-10-17T12:00:00", "contaminant": "Salmonella", "result": "positive", "lab_result_id": 1}
```

### 2.6 GET /api/batches/{batch_id}/trace
Path parameter: `batch_id` (integer). It follows `batch_relationships` only, so shipments and organizations aren't included. It returns batch IDs only.

Example data: lettuce `102` is an ingredient of wrap `42`. `GET /api/batches/42/trace` returns `200`:
```json
{"batch_id": 42, "upstream": [102], "downstream": []}
```
`GET /api/batches/102/trace`:
```json
{"batch_id": 102, "upstream": [], "downstream": [42]}
```
An unknown batch returns `404` `{"detail": "batch not found"}`.

### 2.7 GET /api/shipments/{shipment_id}/risk
Path parameter: `shipment_id` (integer). This is a transparent score, not a probability:
- **Readings above 7 °C:** +15 points each, up to 60.
- **A peak above 12 °C:** +25 points.
- **Level:** `HIGH` from 70, `MEDIUM` from 35, otherwise `LOW`.

Returns `200`:
```json
{"shipment_id": 17, "score": 55, "level": "MEDIUM", "reasons": ["2 temperature excursion(s) above 7.0°C", "peak temperature 13.2°C"]}
```
A shipment with no readings, including one that doesn't exist, returns `200`, not 404:
```json
{"shipment_id": 999, "score": 0, "level": "UNKNOWN", "reasons": ["no sensor data"]}
```

### 2.8 POST /api/analyses
Upload a shipment file as **multipart form data**, field name `file`. It accepts `.csv`, `.xlsx` or `.json` (an array of records), up to 10 MB.

Each row is one sensor reading or event. Shipment-level columns may repeat on every row; the first filled value is used. Headers are matched loosely, so `Batch ID` is read as `batch_id`.

| Column | Required | Meaning |
|---|---|---|
| `shipment_id` | yes | string |
| `batch_id` | yes | string; exactly one batch per shipment |
| `record_id` | no | row ID used as evidence (default `row-N`) |
| `product`, `route`, `distributor` | no | labels for the distribution graph |
| `profile` | no | temperature rule: `poultry_chilled` (4 °C), `red_meat_chilled` (7 °C), `offal_chilled` (3 °C), `tcs_food_us` (5 °C, the default), `frozen` (−18 °C) |
| `destination`, `delivered_to` | no | planned and actual recipient |
| `reading_time` | if there is a temperature | ISO datetime |
| `temperature_c` (or `temperature`) | no | °C |
| `humidity_pct` (or `humidity`) | no | % RH |
| `planned_arrival`, `actual_arrival` | no | ISO datetime |
| `dispatched_qty`, `received_qty` | no | numbers |

```
curl -F "file=@frontend/public/supplier_shipments.csv" http://localhost:8000/api/analyses
```
Returns `201`:
```json
{"analysis_id": "analysis-1b56473c67a3", "dataset_id": "supplier_shipments.csv", "rows": 41, "shipments": 8, "batches": 7, "findings": 6}
```

**Errors:**
- **400** for a bad file, with a specific message. For example `{"detail": "missing column(s): batch_id"}`, `{"detail": "file must be .csv, .xlsx or .json"}`, an invalid value in a named row, or an unknown `profile`.
- **413** if the file is over 10 MB.

Results are committed to the `analyses` table before the upload succeeds. Findings and distribution documents survive API restarts/redeployment and are shared between workers. Existing IDs and response shapes remain valid. Raw file bytes are not retained.

### 2.9 GET /api/analyses/{analysis_id}/findings
Returns `200`, following `contracts/ml-findings.schema.json`:
```json
{
 "schema_version": "1.0",
 "analysis_id": "analysis-1b56473c67a3",
 "dataset_id": "supplier_shipments.csv",
 "generated_at": "2026-10-17T17:14:59.619484+00:00",
 "model_version": "cold-chain-rules-1",
 "findings": [
  {
   "finding_id": "finding-001",
   "batch_id": "RM-402",
   "shipment_id": "SHIP-017",
   "anomaly_type": "temperature_excursion",
   "severity": "medium",
   "priority_score": null,
   "summary": "Peak temperature 8.4 °C; the poultry_chilled limit is 4 °C (Regulation (EC) No 853/2004, ...).",
   "evidence": [
    {"source_record_id": "rec-0005", "field": "temperature_c", "observed_value": 8.4, "threshold_value": 4.0, "unit": "C", "observed_at": "2026-10-17T06:40:00+00:00"}
   ]
  },
  "... 5 more"
 ]
}
```
- **`anomaly_type`:** `temperature_excursion` · `sensor_gap` (a reading gap over 15 min) · `humidity_excursion` (over 75 %) · `shipment_delay` (over 30 min late) · `quantity_mismatch` · `destination_mismatch` (the contract also allows `other`).
- **`severity`:** `high` (time in the temperature danger zone exceeded) · `medium` · `low`. The list is sorted with high first.
- **`priority_score`:** always `null`, because these are rules, not a model.
- **`checks`:** one row per check (`temperature`, `humidity`, `delay`, `quantity`, `destination`) with `label`, the `fields` it needs, `shipments_checked` and `shipments_total`. A check with `shipments_checked: 0` did not run, so zero findings from it is not a clearance. Analyses stored before this field existed omit it.

An unknown ID returns `404` `{"detail": "analysis not found"}`.

### 2.10 GET /api/analyses/{analysis_id}/distribution
Returns `200`:
```json
{
 "analysis_id": "analysis-1b56473c67a3",
 "nodes": [
  {"id": "root:Food Processing", "kind": "root", "label": "Food Processing", "detail": "Distributor", "flagged": false},
  {"id": "route:Protein cold-chain", "kind": "route", "label": "Protein cold-chain", "detail": null, "flagged": false},
  {"id": "batch:RM-402", "kind": "batch", "label": "RM-402 · Marinated chicken", "detail": null, "flagged": true},
  "... 17 more"
 ],
 "edges": [["root:Food Processing", "route:Protein cold-chain"], ["route:Protein cold-chain", "batch:RM-402"], ["batch:RM-402", "shipment:SHIP-017"], "... 16 more"]
}
```
- **Node IDs:** `root:<distributor>`, `route:<route>`, `batch:<batch_id>` and `shipment:<shipment_id>`. Shipment nodes have kind `recipient`; their label is the destination and their `detail` is the shipment ID.
- **`flagged`:** true when that shipment or batch has a finding.

An unknown ID returns `404`.

---

## 3. ML service (food-risk-ml, port 8100)

| # | Method | Path | What it does |
|---|---|---|---|
| 3.1 | GET | `/health` | Is the single default model loaded |
| 3.2 | POST | `/predict` | One sample → the default model (Salmonella, poultry) |
| 3.3 | GET | `/models` | Product families, their models, and valid values for each field |
| 3.4 | POST | `/models/spin` | Pick a real past sample and run every model for its product |
| 3.5 | POST | `/models/predict` | One sample → every model for its product |

**Product families:**

| Family key | Name | Models (each reported separately, never combined) |
|---|---|---|
| `poultry` | Raw poultry | `salmonella`, `campylobacter` |
| `beef` | Raw beef | `beef_salmonella`, `beef_stec` |
| `rte` | Ready-to-eat products | `rte_listeria` |

The chemical (imidacloprid) model has no endpoint.

### Sample (request body for 3.2 and 3.5)
Extra fields are rejected with `422`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `sample_date` | date `YYYY-MM-DD` | yes | |
| `product_category` | string | no | FSIS programme code, e.g. `EXP_CH_MSK01`; it decides the family |
| `establishment_id` | string | no | enables the establishment-history features |
| `metadata` | object | no | only fields the model declares: `meta_cat_sample_source_name`, `meta_cat_product_type`, `meta_cat_production_alternative`, `meta_cat_establishment_state` (varies by family; see `GET /models`) |

```json
{"sample_date": "2023-06-08", "product_category": "EXP_CH_MSK01", "establishment_id": "127044",
 "metadata": {"meta_cat_establishment_state": "AR", "meta_cat_product_type": "__unknown__",
              "meta_cat_sample_source_name": "Product-Raw-Ground, Comminuted or Otherwise Nonintact-Chicken"}}
```

### Prediction object (used by 3.2, 3.4 and 3.5)
| Field | Meaning |
|---|---|
| `model_version` | e.g. `salmonella-xgboost-20261017T062839Z` |
| `pathogen` | e.g. `Salmonella` |
| `probability_positive` | 0–1, the estimated chance that a lab sample like this tests positive |
| `risk_band` | `high` / `medium` / `low`, from per-model cut-offs |
| `threshold` | the model's decision threshold |
| `explanation` | the top 5 contributions `{feature, source_feature, input_value, contribution}`, or `null` |
| `explanation_units` | `log-odds` |
| `trained_on_synthetic_data` | `false` for the current models |
| `disclaimer` | text that must accompany the number |

### 3.1 GET /health
Returns `200`:
```json
{"status": "ok", "model_version": "salmonella-xgboost-20261017T062839Z", "pathogen": "Salmonella", "detail": null}
```
If no model loaded, `status` is `no_model` and `detail` gives the reason.

### 3.2 POST /predict
Body: a Sample. Returns `200` with one prediction object:
```json
{
 "model_version": "salmonella-xgboost-20261017T062839Z",
 "pathogen": "Salmonella",
 "probability_positive": 0.7609540820121765,
 "risk_band": "high",
 "threshold": 0.06050295755267143,
 "explanation": [
  {"feature": "product_category_EXP_CH_MSK01", "source_feature": "product_category", "input_value": "EXP_CH_MSK01", "contribution": 2.1800122261047363},
  "... 4 more"
 ],
 "explanation_units": "log-odds",
 "trained_on_synthetic_data": false,
 "disclaimer": "Estimated probability that a laboratory sample with these characteristics tests positive for the named pathogen, ..."
}
```
- **`422`:** an extra field, or metadata the model doesn't accept.
- **`503`:** no model loaded.

### 3.3 GET /models
No parameters. Returns `200`:
```json
{
 "families": [
  {
   "key": "poultry",
   "name": "Raw poultry",
   "models": [{"key": "salmonella", "pathogen": "Salmonella"}, {"key": "campylobacter", "pathogen": "Campylobacter"}],
   "fields": [
    {"name": "sample_date", "label": "Sample date", "options": ["2023-02-22", "2023-02-23", "... 501 more"]},
    {"name": "product_category", "label": "FSIS programme", "options": ["EXP_CH_MSK01", "EXP_CPT_QH01", "... 9 more"]},
    {"name": "establishment_id", "label": "Establishment", "options": ["10", "100", "... 641 more"]},
    "... 3 more"
   ]
  },
  "... beef, rte"
 ],
 "labels": {"sample_date": "Sample date", "product_category": "FSIS programme", "...": "..."},
 "unavailable": {}
}
```
`unavailable` maps a family key to the error that stopped it loading.

### 3.4 POST /models/spin
JSON body: `{"family": "poultry"}`. The family is optional; leave it out for a random one. The sample comes from the validation window and includes each model's real lab result in `actual`.

Returns `200`:
```json
{
 "family": "poultry",
 "name": "Raw poultry",
 "sample_id": "103208553",
 "sample": {"sample_date": "2023-06-08", "product_category": "EXP_CH_MSK01", "establishment_id": "127044", "metadata": {"...": "..."}},
 "window": {"start": "2023-02-22", "end": "2024-10-11"},
 "results": [
  {"model": "salmonella", "pathogen": "Salmonella", "actual": "positive", "prediction": {"probability_positive": 0.761, "risk_band": "high", "...": "prediction object"}},
  {"model": "campylobacter", "pathogen": "Campylobacter", "actual": "positive", "prediction": {"probability_positive": 0.393, "risk_band": "high", "...": "prediction object"}}
 ]
}
```
- **`404`:** unknown family (`{"detail": "product family 'fish' is not available"}`).
- **`503`:** the family failed to load, or none loaded.

### 3.5 POST /models/predict
- **Body:** a Sample.
- **Query parameter `family`:** optional. Needed only when `product_category` is missing; otherwise the programme code picks the family.

Returns `200` in the same shape as 3.4, with `sample_id: null` and `actual: null`, because no lab result applies to an entered sample.

**Errors:**
- **`422`:** no programme and no `?family=` (`{"detail": "give the FSIS programme (product_category), or ?family=, so the right models run"}`), a programme no model knows, a programme that belongs to a different family, or unsupported metadata.
- **`404` / `503`:** as in 3.4.

---

## 4. Remaining limits

1. Upload findings persist, but an upload does not invent producer records, ingredient links or lab results. External lot codes must resolve to exactly one stored producer's batch; ambiguous matches require an organization choice.
2. One batch per shipment remains the MVP contract. Legacy shipment rows have no unit until a manifest is provided; new shipments require an explicit unit. Ingredient `quantity_used` retains its legacy unspecified unit and is not used for inventory arithmetic.
3. `/risk` retains the legacy flat 7 °C rule; uploads use per-product profiles. It is not used to rank shared ingredients.
4. The models predict FSIS sample positivity; they do not predict an uploaded batch's contamination probability. Predictions are not stored, and the chemical model has no endpoint.
5. Containment decisions are recorded, but the hold itself is simulated: no shipment status changes and nothing is sent to a site. Live replay is still pending. Trace selection is an investigation input, not laboratory confirmation.

## 5. Stored traceability API

| Method | Path | Input / output |
|---|---|---|
| GET / POST | `/api/organizations` | Create: `organization_id`, `name`, `type` (supplier/factory/warehouse/store). POST returns 201; duplicate ID 409. |
| POST | `/api/batches` | Existing fields plus optional `lot_code`. Requires an existing organization. Returns 201, includes `lot_code`. Duplicate `(organization_id, lot_code)` returns 409. |
| GET / POST | `/api/shipments` | Create: `shipment_id`, `shipment_code`, `batch_id`, `from_org_id`, `to_org_id`, positive finite `quantity`, `quantity_unit`, optional `status`, `departed_at`, `eta`. Status: pending/in_transit/delivered/held. Returns 201. List adds origin/destination names and units. |
| GET / POST | `/api/batch-relationships` | Create: `parent_batch_id`, `child_batch_id`, positive finite `quantity_used`. Returns 201, duplicate 409, self-link/cycle 400. Both batches must exist. |
| GET | `/api/trace/batches` | Batch catalog with lot code, producer name/type, product, status and production time. |
| GET | `/api/lots/resolve?lot_code=RM-402` | Optional `organization_id`. Returns a batch; unknown 404, ambiguous 409. No route-name inference. |
| GET | `/api/trace?batch_ids=910042&batch_ids=910091` | Investigate 1–20 selected batch IDs. See response below. Unknown batch 404; empty/oversize input 422. |
| GET | `/api/batches/{id}/trace` | Same rich response plus `batch_id`. Keeps legacy `upstream` and `downstream` arrays. |
| POST | `/api/records/import` | Multipart `file` (`.csv`, `.xlsx`, `.json`, up to 10 MB). Loads many records at once; see "Record import" below. Returns 200 with `rows`, `created` and `existing` counts per kind. Any bad row returns 400 naming the rows, and nothing is stored. |
| GET | `/api/organizations/{id}/lots` | Lots to investigate when the lead is a company: the lots it made, plus lots it received or sent on without making something from them (`relation`: `produced` / `handled`). Ingredients it used are left out, because tracing its products reaches them. Newest first; `limit` 1–200, default 20; `total` shows when the list was cut short. Unknown organization 404. |
| POST | `/api/decisions` | Body: `batch_ids` (1–20, the selection under investigation), `scope` (`targeted`/`extended`), `decision` (`approved`/`rejected`), `reason` (non-blank). Regulators only; the officer is the signed-in user, and a name sent by the client is ignored. The server recomputes the held lots and shipments from stored records; the client never sends them. Returns 201 with `decision_id`, `scope`, `decision`, `batch_ids`, `shipment_ids`, `officer`, `reason`, `decided_at`, `analysis_id`. Optional `analysis_id` links the decision to the upload that started it (stored in `decision_sources`); an unknown analysis returns 404. Unknown batch 404, invalid input 422. Append-only: nothing is updated or deleted. |
| POST | `/api/demo/seed` | No body required. Adds fixed synthetic rows idempotently, refusing conflicting reserved IDs with 409 and rolling back the whole seed. Returns `synthetic`, `selected_batch_ids`, `second_batch_id`, `shared_ingredient_id`, `message`. Never resets or deletes data. |

Trace response fields:

- `selected_batch_ids`: unique selected batches.
- `upstream`, `downstream`: batch IDs from directed ingredient links, excluding selected IDs.
- `related`: other products made from upstream lots, excluding the previous groups.
- `batches`: full catalog records for all included lots/products.
- `edges`: directed `[parent_batch_id, child_batch_id]` pairs.
- `shipments`: movements of included batches with origin/destination names, external codes, units, status and timestamps. These are not current-inventory totals.
- `organizations`: every organization that made or handled an included lot, suppliers first, then factories, warehouses and stores. Each has `organization_id`, `name`, `type`, `produced_batch_ids` and `holdings`, one per lot and unit: `received` (delivered to it), `incoming` (sent to it but not delivered), `sent` (in transit or delivered onward), `remaining` and `used_in` (products it made from that lot). `remaining` is `received − sent`: stock that may still be on site, was used in production or was sold. It is `null` where the lot was made, because production quantity is not stored; a negative value means the site sent on more than its recorded receipts. A `held` shipment counts as neither sent nor received.
- `source_ranking`: upstream lots ordered by count of selected descendants, then summed shortest-path distance, then ID. Each row includes `batch_id`, `matched_batch_ids`, `flagged_product_count`, `total_distance`. A count is not a probability or causal conclusion.
- `lab_results`: recorded laboratory evidence, independently of manual selection.
- `interpretation`: explicit scope of the investigation leads.
- `containment`: `recommended` scope, a `basis` sentence, a `note` that the action is simulated, and `options.targeted` / `options.extended`, each with `batch_ids` and `shipment_ids`. Targeted = the selection and products made from it; extended = every lot in the trace. Extended is recommended only when the top-ranked ingredient is shared by more than one selected product.
- `positive_elsewhere`: up to 10 positive lab results on batches outside this trace, newest first, each with its full `batch` record. These are the products the selection does not explain.
- `decisions`: recorded decisions for exactly this selection, newest first.

The synthetic seed uses 910xxx IDs. CW-42 (`910042`) and CS-91 (`910091`) share L-102 (`910102`). VW-17 is another product using L-102 at the second factory. RM-402 (`910402`, marinated chicken from Food Processing) is a separate ingredient of CW-42 and matches the bundled `supplier_shipments.csv`, including its SHIP-017 movement to Central Kitchen, QSR Group A. Both CW-42 and CS-91 have a `Salmonella (simulated)` positive. Selecting both finished products ranks L-102 first with `flagged_product_count: 2`. Re-running the seed renames rows still holding the first seed version's names (Poultry Supplier, FreshBite Factory KL, Chilled chicken); any other differing value is a 409 conflict.

### Record import

One row per record. The `record` column names the kind, which decides the other columns that are read. Headers are matched loosely, and row order does not matter. `frontend/public/trace_records_template.csv` is a working example.

| `record` | Columns |
|---|---|
| `organization` | `name`, `type` (supplier / factory / warehouse / store) |
| `lot` | `producer`, `lot_code`, `product`, `produced_at` |
| `ingredient` | `lot_code` (the product), `ingredient_lot_code`, `quantity`; optional `producer`, `ingredient_producer` |
| `shipment` | `shipment_code`, `lot_code`, `from`, `to`, `quantity`, `unit`, `status` (pending / in_transit / delivered / held); optional `producer`, `departed_at`, `eta` |

- **Matching:** organizations by name (ignoring case), lots by producer and lot code, shipments by sender and shipment code. A record that is already stored is counted under `existing` and left unchanged, so a file can be sent twice and two organizations can describe the same lot.
- **Producer columns:** may be left out when the lot code belongs to one producer only; otherwise the row is refused as ambiguous.
- **Dates:** ISO only (`2026-11-01` or `2026-11-01 06:00`). `01/11/2026` is refused rather than guessed as January or November.
- **Refused:** unknown organizations or lots, ingredient cycles, a second lot on one shipment code, non-positive quantities. One bad row rejects the whole file.
- **IDs:** assigned as the highest stored ID plus one. Two imports at the same moment can collide; the loser gets 409 and can be sent again.

New lab writes accept only `positive` or `negative`. Distribution upload grouping scopes routes and batch occurrences to their distributor/route, so identical route names do not merge independent suppliers.

## 6. Accounts and access

Every route except `GET /api/health` and `POST /api/auth/login` returns **401** without a session.

| Method | Path | What it does |
|---|---|---|
| POST | `/api/auth/login` | Body: `email`, `password`. Returns the user and sets the `tracefront_session` cookie (HttpOnly, SameSite=Lax, Secure, 12 hours). A wrong email, a wrong password and a locked account all return the same 401. Five failed attempts lock the account for 15 minutes. |
| POST | `/api/auth/logout` | Ends the session on the server and clears the cookie. |
| GET | `/api/auth/me` | The signed-in user: `user_id`, `email`, `name`, `role`, `organization_id`, `organization_name`. |

Browser clients must send requests with credentials, and their origin must be listed in `TRACEFRONT_CORS`.

**Tables:** `users` (email, name, scrypt password hash, role, organization, failed-attempt counter and lock time), `user_sessions` (SHA-256 of the cookie value, user, expiry; the cookie value itself is not stored) and `entries` (append-only: which user, acting for which organization, stored which record, and when). Accounts are created with `python -m app.auth add-user` on the server; there is no sign-up route. Sensor readings are not written to `entries`.

**Roles:**

- **`regulator`** (a Ministry of Health officer): reads and writes everything. Only a regulator can record containment decisions, create organizations one at a time, and load the demo scenario.
- **`company`**: acts for one organization and sees one step back and one step forward.

What a company user can see:

| Data | Rule |
|---|---|
| Lots | The lots its organization made, the lots in shipments it sent or received, and the ingredient lots of its own products. |
| Shipments | Those it sent or received. |
| Ingredient links | Those of its own products. What another company made from its lots is not shown. |
| Organizations | Itself, its trading partners and the makers of lots it can see. |
| Trace | Only lots it can see may be selected, and the result is cut to the rules above. |
| Lab results | Only on lots it made. `positive_elsewhere` and `decisions` are always empty. |
| Upload analyses | Those uploaded by its own organization. Uploads made before sign-in existed have no owner and are regulator-only. |

Anything outside these rules answers **404**, exactly like a record that does not exist.

What a company user can write:

| Record | Rule |
|---|---|
| Lot | For its own organization. Through a record import it may also declare another company's lot, but only with a shipment to or from itself, or as an ingredient of one of its own lots, in the same file. |
| Ingredient link | Only for a product its own organization made, from a lot it can see. |
| Shipment | Only one it sent or received, of a lot it can see. |
| Lab result | Only on a lot it made. |
| Sensor reading | Only on a shipment it sent or received. |
| Organization | Through a record import, to name a trading partner that is not stored yet. |

Import rows can refer only to lots the company can already see or that the same file declares, so a file cannot be used to find out which lots other companies hold. A refused write returns **403**, or **404** where saying more would reveal another company's record.
