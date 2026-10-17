# Model-ready handoff contract (M8) — what Person B needs from Person A

Status date: 2026-10-17. **A request, not a demand to implement now.** Training starts only on a handoff that passes `python -m src.cli check-handoff <handoff.json>` (in `food-risk-ml/`).

## Deliverable per target

One **flat table** and one **manifest**, per target × analyte (e.g. `pathogen_positive` × Salmonella; `pesticide_detected` × one pesticide or a declared family).

- **Table:** UTF-8 CSV, header row. ISO-8601 dates and UTC timestamps. String IDs keep leading zeros. A single declared null token (default: empty cell). One row per observation at its prediction cutoff (Person A's `observations` grain), joined to its label.
- **Manifest** (`handoff.json`, standard-library JSON):

```json
{
  "handoff_version": "1",
  "model_ready": true,
  "target": "pathogen_positive",
  "analyte": "Salmonella",
  "target_column": "pathogen_positive",
  "label_columns": ["pathogen_positive"],
  "dataset_id": "fsis_raw_poultry",
  "dataset_version": "FY2014-FY2026@2026-10-09",
  "table": {"path": "pathogen_positive_salmonella.csv", "sha256": "<sha256 of the CSV>", "row_count": 325121,
            "null_token": ""},
  "prediction_time_column": "prediction_time",
  "id_columns": ["observation_id", "sample_id"],
  "group_columns": {"facility": "factory_id", "region": "state"},
  "features": [
    {"name": "sampling_program", "dtype": "categorical", "availability": "pre_prediction",
     "label_derived": false, "missing_meaning": "unknown", "source": "FSIS project_code"},
    {"name": "previous_test_count", "dtype": "numeric", "availability": "pre_prediction",
     "label_derived": true, "history_cutoff": "event_time < T and available_at < T",
     "missing_meaning": "no history", "source": "derived from FSIS history_events"}
  ],
  "is_synthetic": false,
  "provenance": {"source_manifests": ["data/manifests/<receipt>.json"], "code_commit": "<git sha>",
                 "cleaning_summary_sha256": "<…>"}
}
```

## Required items

| Item | Requirement |
|---|---|
| Target column | 0/1 or true/false for binary targets; numeric with a unit column for regression; declared class list for multiclass. Rows with untested/indeterminate status are excluded or left empty, **never negative**. |
| `label_columns` | Every label-like column present in the table (e.g. `label_status`, result codes). The gate forbids them as features. |
| Timestamps | `prediction_time` (the decision cutoff) is required. For label-derived history, `available_at` semantics are stated in `history_cutoff`. |
| Grouping IDs | Facility (`factory_id`), site, supplier, experiment, batch or shipment as the source supports. Used for grouped splits and overlap diagnostics, never as features. |
| Categorical columns | `dtype: "categorical"`, with values as published. Mappings (e.g. PDP VARIETY N/A) documented in `missing_meaning`. |
| Numeric columns | `dtype: "numeric"`, units in the name or the source note (`_c`, `_pct`, `_hours`, `_ppm`) |
| Missingness | Per feature `missing_meaning`: unknown / not applicable / not measured / no history. Blank ≠ zero. |
| Provenance | Source receipt paths, cleaning summary hash and code commit. The table SHA-256 is mandatory and checked. |
| Temporal cutoffs | Every feature `availability: "pre_prediction"`. Label-derived features need `history_cutoff`. |
| Synthetic | `is_synthetic: true` for any fabricated rows. Outputs are then flagged and never reported as results. |

## Requests where Person A's current design may not cover this

| # | Request | Why | Status |
|---|---|---|---|
| R1 | **Flat model view** per target, joining `observations` + `labels` | The multi-table store is right for lineage; the trainer needs one row per observation | Request |
| R2 | **FSIS intake** using Person B's downloaded files (hashes in `food-risk-ml/data/raw/fsis_raw_poultry/DOWNLOAD_PROVENANCE.json`) | Person A's M1 still lists FSIS as not acquired | Request |
| R3 | Raise or stream past the **128 MiB JSON cap** | FSIS FY2022 (149 MB) and FY2023 (143 MB) exceed it | Request |
| R4 | **FSIS result-availability**: record it as unknown, not as the collection date | FSIS publishes no result date; Person B applies a documented 7-day lag | Agreed approach; Person A to confirm |
| R5 | **PDP detection semantics**: document MEAN ND/NP/O/R and ANNOTATE, and the re-extraction/duplicate rule giving one determination per sample × pesticide | Unblocks `pesticide_detected` | Request |
| R6 | **PDP censoring policy** input: LOD per result retained as label evidence | Unblocks `residue_concentration` | Request |
| R7 | Tolerance table with effective dates and a residue-definition mapping | Unblocks `chemical_exceedance` | Request; may be out of scope |
| R8 | Leave establishment history to Person B (or deliver it only with `label_derived` + `history_cutoff`) | One implementation for training and serving | Request |
| R9 | Per-feature `availability` declaration | Gate-enforced | Request |
