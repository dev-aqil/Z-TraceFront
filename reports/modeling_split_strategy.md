# Modeling split strategy — Person B

Status date: 2026-10-17. Owner: Person B. Design only: no final split has been executed on Person A data. The implementation is in `food-risk-ml/src/evaluation/splits.py`, and its tests in `food-risk-ml/tests/test_modeling_framework.py` use synthetic data only.

## Options compared

| Split | What it measures | Strengths | Risks | Default use |
|---|---|---|---|---|
| **Temporal** (whole time units per split, train < val < test) | Performance on future periods, as a deployed model would see them | Matches the intended use (predict upcoming samples); exposes drift | Same facility appears before and after: realistic, but it inflates results if IDs are features. Programmes that start or stop shift the base rate. | **Default** wherever reliable dates exist |
| Grouped by facility (establishment/plant) | Generalisation to unseen facilities | No facility on both sides | Ignores time, so future history can leak into training | Fallback when dates are unreliable; also a secondary "new facility" evaluation |
| Grouped by supplier | Generalisation to unseen suppliers | Same | Needs a verified supplier ID (none in current sources) | Not applicable yet |
| Grouped by experiment/batch | Generalisation to new experimental runs | Repeated readings of one run stay together | Small number of groups → high variance | Default for laboratory storage experiments |
| Geographical holdout | Transfer to unseen regions | Tests spatial transfer | Region confounded with programme and commodity; few regions → noisy | Secondary analysis only |
| Random (stratified) | Interpolation within the same population | Simple | Mixes the same facility, period and batch across train/test; overstates performance for forecasting | **Refused by code** unless `allow_random` is set for a documented cross-sectional experiment |

## Per target

| Target | Primary split | Secondary | Notes |
|---|---|---|---|
| `pathogen_positive` (FSIS) | Temporal on `prediction_time` (collection date), 70/15/15, whole days | Grouped by `factory_id` ("unseen plant"); per-programme breakdown | The runner reports the share of test rows from facilities unseen in training. History features use an online policy: test rows may use earlier test-period results, subject to the result lag. |
| `pesticide_detected` / `residue_concentration` (PDP 2024) | Temporal **within 2024** (by month) | Grouped by `site`; geographic by `state` | One year: seasonality and the commodity mix are confounded with time. Pool another year only as a separate, explicitly versioned dataset. |
| `chemical_exceedance` | — | — | No target until authoritative limits exist |
| `microbial_count`, `spoilage_class`, `storage_condition_class` | Grouped by `experiment_id` / batch | Temporal within run if timestamps allow | Repeated measurements of one batch must never span splits |
| `cold_chain_failure` | Temporal by shipment start, plus grouped by `shipment_id` | Grouped by route/carrier if available | Features must be prefix-only (readings before the cutoff) |

## Leakage risks and controls

| Risk | Control |
|---|---|
| Same supplier or facility in train and test | Temporal: accepted and reported (`test_rows_from_unseen_groups`). Grouped split: `assert_split_integrity(group_col=…)` raises on any overlap. |
| Same facility repeated across periods with ID as a feature | IDs are never features (gate rejects them); history is aggregated from earlier results instead |
| Future historical aggregates | History counts only events with `event_time < T` **and** `available_at < T`. The FSIS lag is an assumption (no result date published). |
| Post-event variables (recall status, termination, final-trip maxima) | Forbidden patterns per target in `targets.toml`; `availability` must be `pre_prediction` |
| Duplicate or re-extracted rows across splits | Whole time units per split; one determination per sample × analyte (Person A rule for PDP) |
| Preprocessing fit on all data | sklearn `Pipeline`: the encoder, imputer and scaler are fit on training rows only |
| Threshold or model chosen on test | Selection, calibration and thresholds use validation only; test is read once |
| Single-class split | Runner refuses splits with one class |
