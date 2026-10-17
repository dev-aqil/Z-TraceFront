# Preliminary data-leakage audit — M0

Status: source/design review only. No training table exists and no automated temporal-feature tests exist yet. The M0 integrity tests do not prove M5/M6 features are leakage-free. This is a prevention contract to implement and test in M5–M7.

## Classification

| Feature/evidence family | Classification | Decision |
| --- | --- | --- |
| Source hashes/versions, specimen/run/lot IDs, synthetic flag | SAFE metadata | Retain for lineage/grouping; exclude IDs/versions from default model predictors. |
| Product identity, origin, farm/process attributes | QUESTIONABLE | Require verified measurement before cutoff and original source mapping. Outcome narrative must not generate predictor values. |
| Sensor readings recorded and available by T | SAFE conditionally | Reject future/delayed readings; retain device QA flags; use a validated source-specific sensor window. |
| Final-trip maximum temperature, actual final duration/arrival | LEAKAGE for a mid-trip decision | Use prefix-only features or predict after trip completion under a separate task definition. ETA is a known forecast, not actual arrival. |
| Laboratory result, test positivity, organism subtype/serotype obtained after test | LABEL / LEAKAGE as input | Keep in target/evidence table. Assay selection and sample commodity may be known; result-derived organism details are not predictors. |
| Current `recall_status`, investigation result, enforcement outcome, later closure | LEAKAGE | Do not use for the focal observation. Historical features require a genuinely available historical version. |
| Recall reason text/confirmation narrative | LEAKAGE as same-incident input | Can contain the answer. Historical reviewed hazard categories only after publication and entity/time validation. |
| Recall classification | QUESTIONABLE history; LEAKAGE as focal predictor | Severity classification is neither a test result nor an early-incident feature. |
| FDA NAI/VAI/OAI result | QUESTIONABLE history; LEAKAGE if not yet published | Public availability may lag inspection end. No current classification backfill into earlier observations. |
| Previous positive counts/rates and recall counts | SAFE only after strict event+availability filtering | Need real entity links and comparable tested denominators; exclude focal specimens. Otherwise QUESTIONABLE. |
| Weather daily summaries on prediction day | LEAKAGE when day/measurement interval is incomplete | Use completed, published intervals; retrospective archives may include unavailable revisions. |
| OpenDOSM annual production | QUESTIONABLE | Reference year is not release date. Use a prior available release, only for relevant Malaysian crop observations. |
| PDP concentration/LOD/qualifier and applicable limit | LABEL evidence | Needed to define chemical target. Same-sample concentration cannot also predict its own exceedance. |
| TVC when predicting a class derived from TVC | LEAKAGE | Train count regression from eligible sensors, or predict class without count. Document any independently measured pre-cutoff quality predictor separately. |
| Fruit Good/Bad; threshold-derived cold_chain_failure | LABEL proxy | Keep separate from biological labels. Using all variables that mechanically define the class tests rule reproduction, not contamination prediction. |
| Missingness flags | QUESTIONABLE | Can encode testing initiated after suspicion; derive from prediction-time data, not final dataset completeness. |

## Required temporal invariants

For historical events use both `event_time < T` and `available_at < T`. A sample collected yesterday with a result tomorrow is not a known historical negative/positive today. Do not fill unknown availability with collection time. Keep `source_retrieved_at` separate: today's downloaded snapshot is not proof of what was available years ago.

Current openFDA rows contain updated status and termination fields. `report_date` can indicate a reporting day but does not establish when every current field value became known. Earliest-publication snapshots or immutable historical event fields are needed; otherwise label the enrichment retrospective/uncertain and exclude it from strict deployment claims.

For contemporaneous sensors the operational contract may allow equality (`observed_at <= T`, `available_at <= T`). Unknown-time daily records use conservative boundaries; do not invent order within a day. Features need traceable max-input-event-time and max-input-availability-time evidence in M5/M7.

## Tests required before release of features

1. Future-event insertion leaves earlier feature values unchanged.
2. Old collection with future result availability is excluded from earlier history.
3. Events at exactly T are excluded from strict history; same-day date-only events cannot precede an unknown intraday cutoff.
4. Focal sample/duplicate assay is excluded; recall products sharing an event are counted according to the documented event unit.
5. Feature builders cannot read label columns or post-event status through a broad input-column selection.
6. Different entities/programs/analytes do not contaminate one another's history; zero prior tests yields a null rate and count zero.
7. Joins preserve observation IDs/counts, reject ambiguous crosswalks and validate match/coverage rates.
8. Adding future sensor values or final-trip facts cannot change a mid-trip snapshot.
9. Train-fitted preprocessing sees training rows only; shared specimens/lots/experiments and overlapping windows cannot straddle incompatible evaluation partitions.
10. Labels not available at the training cutoff cannot enter historical model fitting. Test-history updates follow a declared online or frozen policy.

These are acceptance tests for later milestones, **not tests already implemented in M0**. Current predictor allowlist remains empty.
