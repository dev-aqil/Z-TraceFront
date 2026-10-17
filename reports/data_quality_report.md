# Data quality report — M0 local snapshot

Scope: read-only full-file audit of the existing openFDA-style snapshot, not cleaning or a validated training table. The origin URL, download time and authoritative completeness remain unverified. Values below are measured locally; [machine-readable audit](openfda_snapshot_audit.json) is the detailed evidence.

M1 update: the same unchanged local archive now has a verified byte match to an official openFDA download; source metadata/dictionary/license are captured. Original acquisition time remains unknown, and there is still no contamination training cohort. See [M1 evidence and validation](m1_ingestion_report.md). The M0 measurements and validation record below remain historical.

## Measurements

| Check | Result |
| --- | --- |
| Input JSON | `tmp/food-enforcement-0001-of-0001.json` |
| Rows / union of top-level fields | 29,485 / 25 |
| JSON bytes / SHA-256 | 39,906,111 / `02f3e7959cc732d8f1983f2b87edbbecc6d2f4959eaef50a597f640fbc513e2d` |
| ZIP bytes / SHA-256 | 5,858,570 / `7f8e2b5bd6e05e0cbf15e43860c74538ad09e1f8b07928e9c92de3ead3dac9c6` |
| ZIP validation | CRC check passed; sole member matches the JSON bytes by SHA-256 |
| Embedded total / limit | 29,485 / 29,485; agrees with local rows, not proof of current upstream completeness |
| Exact duplicate objects | 0 |
| Recall identifiers | 29,484 unique populated `recall_number`; 1 missing; 0 duplicate populated recall numbers |
| Event identifiers | 7,907 unique `event_id`; 0 missing. Repeated event IDs are expected multi-product grouping, not duplicate samples |
| Report dates | 2012-06-20 to 2026-10-07; source metadata claims updated 2026-10-14 |
| Invalid date syntax/calendar values | 0 among four audited source date fields |
| Implausible date | One `recall_initiation_date=02121207`, row index 10149, recall `F-0880-2013`; valid calendar year 0212, scientifically suspect |
| Classes / statuses | Class I 12,976; II 14,745; III 1,762; Not Yet Classified 2. Terminated 27,958; Ongoing 1,079; Completed 448 |
| Geographic strings | 32 firm-country values; US 29,039. Not verified farm origin or consumer-exposure locations |
| Label availability | No laboratory sample labels/negative cohort. Enforcement-class counts are not contamination class balance |

## Missingness and row accounting

Missing = absent key, null, empty/whitespace string, empty list or empty object. Zero and false are not missing. No rows have been removed or changed. Before/after missingness is identical because **no cleaning occurred**. Do not infer missingness semantics from these counts alone.

| Field | Missing before | Missing after M0 | Interpretation / next action |
| --- | ---: | ---: | --- |
| address_1 | 2 | 2 | Unknown firm address; no inferred geography |
| address_2 | 8,990 | 8,990 | May be inapplicable supplementary address |
| center_classification_date | 2 | 2 | Could be pending/unknown; preserve source |
| city | 0 | 0 | Populated does not mean geocoded/valid |
| classification | 0 | 0 | Enforcement severity, not lab truth |
| code_info | 29 | 29 | Missing lot narrative; no invented batch ID |
| country | 0 | 0 | Firm-country strings, not origin |
| distribution_pattern | 0 | 0 | Text not verified store network |
| event_id | 0 | 0 | Shared event-level grouping |
| initial_firm_notification | 3 | 3 | Outcome-era communication metadata |
| more_code_info | 29,484 | 29,484 | Essentially absent; exclude until justified |
| openfda | 29,485 | 29,485 | All empty objects; no available nested identity crosswalk |
| postal_code | 0 | 0 | String, leading zeros matter |
| product_description | 0 | 0 | Free text; taxonomy not validated |
| product_quantity | 437 | 437 | Mixed units/text; not numeric batch size |
| product_type | 0 | 0 | Food only; constant here |
| reason_for_recall | 0 | 0 | Post-event narrative; leakage candidate |
| recall_initiation_date | 0 | 0 | One implausible year despite full population |
| recall_number | 1 | 1 | Missing natural key; quarantine/alternate provenance key in M2 |
| recalling_firm | 0 | 0 | Names are not verified supplier IDs |
| report_date | 0 | 0 | Date-only reporting, not full field-version availability |
| state | 237 | 237 | May be unknown or not applicable to country; no blanket filling |
| status | 0 | 0 | Mutable final/current state; historical leakage risk |
| termination_date | 1,527 | 1,527 | Often unclosed/unknown, not arbitrary random missingness |
| voluntary_mandated | 1 | 1 | Source unknown; keep nullable |

Rows before = 29,485; rows removed = 0; rows modified = 0; rows after = 29,485. Removal reasons: none (audit only). Flag reasons: missing recall identity and implausible initiation date. The date was **not** silently repaired to 2012. A cleaned-source quarantine policy belongs in M2.

## Reproduction and validation

From the repository root:

```bash
PYTHONPATH=src python -m tracefront_data.audit \
  --input tmp/food-enforcement-0001-of-0001.json \
  --archive tmp/food-enforcement-0001-of-0001.json.zip \
  --output reports/openfda_snapshot_audit.json
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python3.11 -m unittest discover -s tests -v
git diff --check
```

The six audit tests cover absent versus zero values, duplicate/partial identities, invalid and suspicious dates, empty/malformed result collections, ZIP/JSON matching and mismatch, deterministic reports, source preservation and CLI source-overwrite rejection. They pass on local Python 3.11.17 and 3.14.7. Full-file audit output was inspected, reproduced and checked against the original source hashes. Contract/documentation consistency and local links were checked separately with standard-library validation. See [portability limits](linuxone_portability.md): local x86_64 execution is not s390x proof.

Existing backend tests were not run: application dependencies/database were not installed or started, and no backend behavior changed. No pytest run is claimed (runner absent). No temporal-feature, cleaning, model, external-download or target-platform validations have occurred; those implementations do not exist yet.

## Remaining quality work

Original acquisition provenance; fresh authoritative download comparison; date/event ordering and revision semantics; text/category normalization; mixed-unit quantities; source-specific missingness reasons; geographic validation; negative-test cohort; entity matching; time-aware source versioning. No meaningful temperature-versus-microbe, geographic risk or contamination-frequency charts can be produced from this snapshot alone. Save those questions for actual compatible data in M3.
