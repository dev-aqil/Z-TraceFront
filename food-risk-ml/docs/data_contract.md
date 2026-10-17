# Data contract: Person A → Person B

This document defines the **canonical internal table** that Person B's Salmonella model consumes. The names here are internal. **They are not the official FSIS field names.** The mapping from real FSIS columns is set in `configs/source_mapping.toml`, and only after someone has inspected the downloaded files and the official FSIS metadata. At the time of writing that has not happened, because the FSIS site was unreachable from the build machine. See the README.

Validate any delivered file with:

```
python -m src.cli validate data/processed/canonical.csv
```

## 1. Scope: three separate problem types

The project has three ML problem types. Each one has its own training table, label, model, registry entry and API output. **They are never merged into one table, and their outputs are never combined into one numerical probability.**

| Problem | Source(s) | Label | Status |
|---|---|---|---|
| **Biological contamination** (this contract) | USDA FSIS Laboratory Sampling Data, raw poultry | `salmonella_positive` | MVP; implemented, training blocked on data |
| Chemical residue | USDA Pesticide Data Program | `pesticide_exceedance` | future, separate model |
| Cold-chain / spoilage | milk tank, paneer, beef, fruit storage datasets | `microbial_count` / `spoilage_class` | future, separate model (§8) |

The other microbiological datasets (milk, paneer, beef) measure different organisms, products and conditions, and none of them are FSIS samples. They must not be row-joined to FSIS samples.

## 2. Canonical columns (biological model, one row per laboratory sample)

| Column | Type | Required | Definition | Missing / invalid |
|---|---|---|---|---|
| `sample_id` | string | yes | Unique identifier of one laboratory sample, from the source. If the source has none, `prepare` derives a hash of the full source row; this weakens duplicate detection, so the substitution is logged. | Not allowed. Must be unique. |
| `sample_date` | date `YYYY-MM-DD` | yes | **Collection** date of the sample. Never the result, report or publication date. Timezone-naive. | Empty = unknown. Unknown dates are excluded from the chronological split. If more than 5% of labelled rows lack a date, the documented fallback split is used (§6). Future dates are invalid. |
| `establishment_id` | string | no | Identifier of the establishment (plant) where the sample was taken, exactly as in the source. | Empty = unknown. Establishment history features are then zero/prior for that row. |
| `product_category` | string | yes | Product/sampling category known before testing (e.g. the FSIS project or product class, once verified). | `__unknown__`. Never empty. |
| `meta_cat_<name>` | string | no | Extra **pre-sampling** categorical metadata (§4). | `__unknown__` |
| `meta_num_<name>` | number | no | Extra **pre-sampling** numeric metadata (§4). | Empty (median-imputed, with a missing indicator). |
| `salmonella_positive` | 0/1 | yes (column) | `1`: the laboratory result for **this sample** reports Salmonella detected. `0`: the sample was tested and Salmonella was not detected. | Empty = not tested, not analysed, inconclusive, or a code not yet interpreted. Such rows are **excluded** from training and evaluation. Labels are never imputed. |

Any other column is rejected by validation.

### Label semantics

- The target is whether **a laboratory sample tested positive**. It is not whether a batch, lot or retail product is safe or unsafe.
- The positive and negative source codes must be copied from the official FSIS metadata into `labels.positive_values` and `labels.negative_values`. Any value in neither list becomes a missing label and is counted in the logs. Nothing is guessed.

### Identifiers and duplicates

- Exact duplicate rows are collapsed to one.
- If several rows share a `sample_id` but differ, all of them are dropped and logged, because there is no basis to choose one.
- Person A's canonical deliveries must already be unique on `sample_id`. Validation rejects duplicates.

## 3. Forbidden as features (leakage)

These must never appear as `meta_*` features, whatever they are called. `src/features/leakage.py` also rejects names containing denylist terms:

- Any laboratory result for the **same sample**: Salmonella, and also **Campylobacter, Listeria and STEC/E. coli** (FSIS tests one sample for several pathogens), serotype/serovar, PFGE/WGS, isolate IDs, AMR/resistance, MPN/CFU counts.
- Anything recorded after collection: result or report dates, outcome, finding, status, follow-up actions.
- Recall, enforcement or regulatory actions linked to the sample or to its outcome.
- Any column derived from `salmonella_positive`.

## 4. Optional pre-sampling metadata

Declare an extra column in `[features.extra]` of `source_mapping.toml` as `"categorical"` or `"numeric"`, or deliver it with a `meta_cat_` / `meta_num_` prefix, **only if its value is known at the time of collection**.

Caveat: sampling-program or project codes can encode *targeted* sampling, for example intensified sampling after earlier failures. Such codes are legitimate inputs only if the trigger predates the sample. They also make the model partly reflect FSIS targeting policy as well as plant performance. Document this in the model card if you use one.

## 5. Historical risk features

Person B computes establishment history from labels inside the pipeline (`src/features/build.py`):

- `est_prior_samples`, `est_prior_positives`, `est_prior_rate_smoothed`, `est_days_since_prior`
- A labelled sample collected on date *d* counts toward a sample on date *t* only if `d + label_lag_days < t`. The lag defaults to 7 days, an **assumption** about reporting turnaround that must be confirmed. Same-day and later samples never count, and neither does the sample itself.
- The rate is shrunk toward the training-period positive rate using 20 pseudo-samples.
- Tests check this by brute force (`tests/test_leakage.py`).

For the biological model, Person A should therefore **not** deliver precomputed `factory_previous_positive_rate` / `previous_positive_tests` columns. Their time windows cannot be verified here, and the denylist rejects them.

**Cross-source historical features** (FDA inspection classification, openFDA recalls, EU RASFF) are **not used** in the MVP:

- FSIS establishments are USDA-inspected meat and poultry plants. FDA inspections and openFDA recalls cover FDA-regulated facilities and products, so the populations largely do not overlap.
- No verified key links those records to FSIS establishment identifiers. Joining on firm name, state, food type or date would pretend that unrelated records describe the same entity.
- They can be added only with a documented, verified entity-resolution key and strictly-prior time windows (`*_previous_365d` counted as of `sample_date - 1 day`). Even then they must arrive as `meta_num_*` columns and pass review.

NOAA weather (`rainfall_7d` and so on) may be added later as `meta_num_*`, but only when a sample's location is known at the right granularity, and only from days before collection.

## 6. Splitting rules (for reference)

- Default: chronological by `sample_date`, 70/15/15. Whole days go to a single split.
- Fallback, when more than 5% of labelled rows lack a date: seeded grouped split by `establishment_id`, so no establishment appears in two splits. History features are disabled in this mode. Results are marked as not measuring performance on future periods.
- Every split must contain both classes, or training stops.

## 7. Crosswalk to Person A's project-wide feature groups

`load_canonical` accepts these Person A names and renames them:

| Person A name | Canonical name | Note |
|---|---|---|
| `sample_time` | `sample_date` | Date part of the collection time |
| `factory_id` | `establishment_id` | FSIS establishment |
| `food_category` | `product_category` | |
| `pathogen_positive` + `pathogen` | `salmonella_positive` | Accepted only together with a `pathogen` column. Only rows where `pathogen == "Salmonella"` are kept. Other pathogens are separate targets. |

The other Person A groups (Storage, Transportation, Processing, Environment, batch/shipment/retailer IDs) do not exist at FSIS sample level. They belong to the extension schema below.

## 8. Extension schema: batch-level cold chain (future, separate model)

This is a **separate table and a separate model** for cold-chain/spoilage risk. It is keyed by batch, not by FSIS sample, and it is never joined to FSIS rows.

| Column | Type | Definition |
|---|---|---|
| `batch_id` | string | Unique physical batch/lot |
| `supplier_id`, `farm_id`, `factory_id`, `shipment_id`, `retailer_id` | string | Entities that handled **this** batch, from the batch's own records |
| `food_type`, `commodity`, `processing_type` | string | |
| `country`, `state`, `district`, `latitude`, `longitude` | string/number | |
| `harvest_time`, `processing_time`, `shipment_start`, `shipment_end`, `retail_arrival` | ISO-8601 datetime | Event times for this batch |
| `observation_time` | ISO-8601 datetime | The time the prediction is made. All features must be computable from data before it. |
| `storage_avg_temp_c`, `storage_max_temp_c`, `storage_min_temp_c`, `storage_duration_hr`, `storage_humidity_pct` | number | Aggregated over readings before `observation_time` |
| `transport_avg_temp_c`, `transport_max_temp_c`, `transport_duration_hr`, `number_of_stops` | number | Same |
| `temperature_excursion_count`, `total_minutes_above_threshold`, `maximum_temperature_deviation`, `longest_temperature_excursion`, `temperature_std`, `temperature_range` | number | Derived from sensor readings before `observation_time`; the threshold is stated per product |
| `farm_to_factory_hours`, `processing_to_shipping_hours`, `shipping_duration_hours`, `total_supply_chain_duration_hours` | number | |
| Label: `microbial_count` (CFU/g or CFU/ml, with unit column) or `spoilage_class` | number / string | Measured at a stated time **after** `observation_time` |

Rules:

- The source datasets (milk tank, paneer, beef, fruit) are separate experiments with different units, organisms and labels.
- They may share a model only after units and labels are harmonised and documented. Otherwise each gets its own model.
- The fruit storage label is a storage-condition class, not a pathogen or microbial label, and must be named that way.
- `cold_chain_failure_flag` must be defined by a rule fixed in advance, never derived from the outcome label.

## 9. Delivery

- UTF-8 CSV with a header, at `data/processed/canonical.csv` or a path passed with `--canonical`.
- Dates in ISO-8601 format. Empty cell means missing.
- Include a `canonical.provenance.json` next to the file listing the source files and their SHA-256 hashes. `prepare` writes this automatically.
