# M2 — Cleaning and standardization

**NOT MODEL-READY.** Eligible-cohort cleaning status: COMPLETE.

Source tables remain independent. No models, predictive features, cross-source joins, imputation or contamination/exceedance labels were created.

| Source / table | Raw input records | Clean records | Rejected | Duplicates |
| --- | ---: | ---: | ---: | ---: |
| noaa_ghcn_daily / daily_observations | 80,693 | 80,693 | 0 | 0 |
| opendosm_crops_district_area / crops_district_area | 10,555 | 10,010 | 545 | 331 |
| opendosm_crops_district_production / crops_district_production | 11,002 | 10,471 | 531 | 324 |
| opendosm_crops_state / crops_state | 1,584 | 1,584 | 0 | 0 |
| openfda_enforcement / recalls | 29,485 | 29,484 | 1 | 0 |
| usda_pdp / samples | 9,872 | 9,872 | 0 | 0 |
| usda_pdp / results | 2,872,073 | 2,872,073 | 0 | 0 |

## noaa_ghcn_daily

Output: `data/interim/m2_v1/noaa`. Role: AUXILIARY_FEATURE_SOURCE.

Known ambiguities:

- Missing source months are not expanded into a continuous historical calendar
- Quality-flagged values remain questionable; reporting date is not availability or an assumed UTC timestamp

NOAA monthly input accounting: `{"accepted_rows": 2651, "duplicate_rows": 0, "invalid_date_rows": 0, "malformed_rows": 0, "missing_critical_identifiers": 0, "raw_rows": 2651, "rejected_rows": 0}`.
Excluded noncalendar sentinel padding slots: 1488. Raw table count above refers to calendar-day slots, not original monthly lines.

### daily_observations

- Grain: Station x calendar date x element, including missing observations
- Missing critical identifiers: 0
- Malformed rows: 0
- Invalid numeric rows: 0
- Invalid date rows: 0
- Rejection reasons: `{}`
- Quality issue counts: `{"quality_flagged_observation_retained": 32}`
- Missingness before: `{"measurement_flag": 57951, "quality_flag": 80661, "source_flag": 21038}`
- Missingness after: `{"value": 21038}`

Transformations:

- Parse fixed-width monthly element rows into valid calendar day records
- Remove only nonexistent calendar-day sentinel padding; record counts separately
- Convert temperature tenths Celsius to Celsius and PRCP tenths mm to mm exactly
- Retain raw integer, measurement/quality/source flag characters including blanks/case
- Null -9999 values; retain quality-flagged numeric observations with explicit status
- Quarantine malformed/conflicting monthly records and physically invalid daily values

Preserved missingness semantics:

- -9999 means publisher missing, never zero rainfall/temperature
- Blank MFLAG means no measurement information applicable; blank QFLAG means no failed QA check
- Blank SFLAG means no source; all literal flag characters survive
- Quality-flagged numeric values remain visible and are not automatically fit for features
- Trace/estimated/presumed-zero distinctions remain encoded by original MFLAG; no imputation

## opendosm_crops_district_area

Output: `data/interim/m2_v1/opendosm_crops_district_area`. Role: EXTERNAL_CONTEXT_SOURCE.

Duplicate count definition: Extra natural-key occurrences, including conflicting versions; not the count of all quarantined rows.

Conflicting natural-key groups quarantined in full: 214.

Known ambiguities:

- Conflicting aggregate versions may reflect publisher duplication or undocumented strata; no winner/sum inferred
- State/national totals overlap; absent district/crop rows are not assumed zero

### crops_district_area

- Grain: Annual state x district x crop type x species
- Missing critical identifiers: 0
- Malformed rows: 0
- Invalid numeric rows: 0
- Invalid date rows: 0
- Rejection reasons: `{"conflicting_aggregate_key_all_versions_quarantined": 428, "exact_duplicate_aggregate": 117}`
- Quality issue counts: `{}`
- Missingness before: `{}`
- Missingness after: `{}`

Transformations:

- Trim categorical/name boundaries without fuzzy spelling or geography matching
- Validate annual YYYY-01-01 reference marker; emit reference_date/reference_year
- Parse finite nonnegative production/area; preserve null and zero distinction
- Remove exact repeated aggregate keys; quarantine all conflicting key versions

Preserved missingness semantics:

- Empty/whitespace means unknown/unprovided, never implicitly zero
- Absent district/crop rows are not synthesized
- Reference year/date is not an event timestamp or public-availability time
- National/state totals and separate district tables remain independent

## opendosm_crops_district_production

Output: `data/interim/m2_v1/opendosm_crops_district_production`. Role: EXTERNAL_CONTEXT_SOURCE.

Duplicate count definition: Extra natural-key occurrences, including conflicting versions; not the count of all quarantined rows.

Conflicting natural-key groups quarantined in full: 207.

Known ambiguities:

- Conflicting aggregate versions may reflect publisher duplication or undocumented strata; no winner/sum inferred
- State/national totals overlap; absent district/crop rows are not assumed zero

### crops_district_production

- Grain: Annual state x district x crop type x species
- Missing critical identifiers: 0
- Malformed rows: 0
- Invalid numeric rows: 0
- Invalid date rows: 0
- Rejection reasons: `{"conflicting_aggregate_key_all_versions_quarantined": 414, "exact_duplicate_aggregate": 117}`
- Quality issue counts: `{}`
- Missingness before: `{}`
- Missingness after: `{}`

Transformations:

- Trim categorical/name boundaries without fuzzy spelling or geography matching
- Validate annual YYYY-01-01 reference marker; emit reference_date/reference_year
- Parse finite nonnegative production/area; preserve null and zero distinction
- Remove exact repeated aggregate keys; quarantine all conflicting key versions

Preserved missingness semantics:

- Empty/whitespace means unknown/unprovided, never implicitly zero
- Absent district/crop rows are not synthesized
- Reference year/date is not an event timestamp or public-availability time
- National/state totals and separate district tables remain independent

## opendosm_crops_state

Output: `data/interim/m2_v1/opendosm_crops_state`. Role: EXTERNAL_CONTEXT_SOURCE.

Duplicate count definition: Extra natural-key occurrences, including conflicting versions; not the count of all quarantined rows.

Conflicting natural-key groups quarantined in full: 0.

Known ambiguities:

- Conflicting aggregate versions may reflect publisher duplication or undocumented strata; no winner/sum inferred
- State/national totals overlap; absent district/crop rows are not assumed zero

### crops_state

- Grain: Annual state/country x crop type
- Missing critical identifiers: 0
- Malformed rows: 0
- Invalid numeric rows: 0
- Invalid date rows: 0
- Rejection reasons: `{}`
- Quality issue counts: `{}`
- Missingness before: `{}`
- Missingness after: `{}`

Transformations:

- Trim categorical/name boundaries without fuzzy spelling or geography matching
- Validate annual YYYY-01-01 reference marker; emit reference_date/reference_year
- Parse finite nonnegative production/area; preserve null and zero distinction
- Remove exact repeated aggregate keys; quarantine all conflicting key versions

Preserved missingness semantics:

- Empty/whitespace means unknown/unprovided, never implicitly zero
- Absent district/crop rows are not synthesized
- Reference year/date is not an event timestamp or public-availability time
- National/state totals and separate district tables remain independent

## openfda_enforcement

Output: `data/interim/m2_v1/openfda`. Role: HISTORICAL_RISK_SOURCE.

Duplicate count definition: Extra occurrences of a recall number; exact repeats removed, all conflicting versions quarantined.

Known ambiguities:

- Initiation/event dates do not establish historical public availability of each field
- Retrospective status, classification and termination fields are not approved predictors

### recalls

- Grain: Product-specific food recall enforcement record; event_id can repeat
- Missing critical identifiers: 1
- Malformed rows: 0
- Invalid numeric rows: 0
- Invalid date rows: 1
- Rejection reasons: `{"missing_recall_number": 1}`
- Quality issue counts: `{"invalid_recall_initiation_date": 1}`
- Missingness before: `{"address_1": 2, "address_2": 8990, "code_info": 29, "initial_firm_notification": 3, "more_code_info": 12973, "product_quantity": 437, "recall_number": 1, "state": 237, "voluntary_mandated": 1}`
- Missingness after: `{"address_1": 2, "address_2": 8989, "center_classification_date": 1, "center_classification_date_raw": 1, "code_info": 29, "initial_firm_notification": 3, "more_code_info": 29483, "product_quantity": 437, "recall_initiation_date": 1, "state": 237, "termination_date": 1526, "termination_date_raw": 1526, "voluntary_mandated": 1}`

Transformations:

- Trim text boundaries; blank/null to explicit CSV null
- Parse strict YYYYMMDD to ISO dates in 1900..frozen retrieval-date window
- Invalid optional dates become null with original token and issue evidence
- Reject missing recall_number or missing/invalid report_date; quarantine conflicting recall numbers
- Remove exact repeated recall records, never deduplicate by event_id
- Normalize only documented classification/status casing; retain other categories

Preserved missingness semantics:

- Null is unknown/unprovided, not no recall or tested negative
- An empty openfda object is retained as {}, not made a missing scalar
- Free text such as N/A is not blindly converted to null
- Invalid optional dates are distinguishable from absent dates via raw tokens/issues

## usda_pdp

Output: `data/interim/m2_v1/usda_pdp`. Role: DIRECT_LABEL_SOURCE.

Duplicate count definition: Samples: extra PK occurrences; results: exact raw analytical-row repeats retained and linked.

Known ambiguities:

- Original and re-extraction rows are not automatically one independent sample/analyte observation
- VARIETY N/A/Na tokens can mean unknown or not applicable and are retained literally
- No effective-date regulatory tolerance/residue-definition comparison performed

### samples

- Grain: PDP 2024 sample identity record
- Missing critical identifiers: 0
- Malformed rows: 0
- Invalid numeric rows: 0
- Invalid date rows: 0
- Rejection reasons: `{}`
- Quality issue counts: `{}`
- Missingness before: `{"COUNTRY": 6028, "DISTST": 2661, "GROWST": 8926, "PACKST": 7817, "QUANTITY": 2046, "SOURCE_ID": 7314}`
- Missingness after: `{"country": 6028, "country_missing_reason": 3844, "distst": 2661, "growst": 8926, "packst": 7817, "quantity": 2046}`

Transformations:

- Trim surrounding whitespace; preserve opaque string IDs and codes
- Interpret YEAR=24 only within this explicitly reviewed 2024 release; validate calendar date
- Parse optional QUANTITY as nonnegative integer; no imputation
- Remove exact repeated sample PK rows; quarantine all conflicting PK versions

Preserved missingness semantics:

- Empty/whitespace becomes null, except documented SOURCE_ID blank default
- SOURCE_ID blank is the documented default, not unknown
- COUNTRY absent for domestic/unknown origin is retained null, not inferred
- VARIETY literal N/A/Na tokens are retained because free-text meaning is ambiguous

### results

- Grain: PDP analytical result; multiple analytes/extractions per sample
- Missing critical identifiers: 0
- Malformed rows: 0
- Invalid numeric rows: 0
- Invalid date rows: 0
- Rejection reasons: `{}`
- Quality issue counts: `{}`
- Missingness before: `{"ANNOTATE": 2870593, "CONCEN": 2853583, "CONFMETHOD": 2853583, "CONFMETHOD2": 2872073, "QUANTITATE": 2871781}`
- Missingness after: `{"concen": 2853583, "concen_missing_reason": 18490, "confmethod": 2853583, "confmethod2": 2872073, "duplicate_of_source_row": 2872073, "quantitate": 2871781}`

Transformations:

- Trim code boundaries; parse finite nonnegative decimals, retaining native CONUNIT
- Preserve MEAN ND/NP/O/R and ANNOTATE verbatim after boundary trimming
- Validate reference to accepted release-local sample IDs without joining tables
- Flag and retain exact analytical duplicates; sample/analyte is not assumed unique

Preserved missingness semantics:

- Blank CONCEN stays null; original token retained in concen_raw
- ND and NP censoring remain distinct; no zero imputation
- Blank ANNOTATE means no annotation, retained as non-null empty string
- Missing CONCEN/LOD in detection rows is flagged, not assigned an outcome
- Untested analytes remain absent; no synthetic negatives created

Preserved MEAN counts: `{"ND": 2798390, "NP": 55193, "O": 18458, "R": 32}`

## Output checksums

| Relative to output directory | Bytes | SHA-256 |
| --- | ---: | --- |
| `README.md` | 442 | `00c761f78d0f970104002fc5f43a1b63413f0a70bd98b2c4e51caa3548cb133d` |
| `noaa/daily_observations.csv` | 5,859,335 | `a0d6895bd265408f82c60831c9e0f69cfe85ab162e288d6c976085be620d9538` |
| `noaa/daily_observations.issues.jsonl` | 5,025 | `07dc617696a16ffe346e0306206106d3c6796cd0ae0d5d96493e1bb604276ad0` |
| `noaa/daily_observations.rejected.jsonl` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `noaa/daily_observations.schema.json` | 3,479 | `2eef99ce4be46139394f1f5e1be8ab501b5b66e068a3142149e749dd4d8f4128` |
| `noaa/monthly_records.rejected.jsonl` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `opendosm_crops_district_area/crops_district_area.csv` | 615,034 | `5efbe6359c11eccb80f0cbc29f82d4d367a497660be1c6854986662dcfec6ec7` |
| `opendosm_crops_district_area/crops_district_area.issues.jsonl` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `opendosm_crops_district_area/crops_district_area.rejected.jsonl` | 172,699 | `9b60b1cd4ea1d12eebd723595df0fe38caf333fa3dd3acd3ec5515e5225fca0e` |
| `opendosm_crops_district_area/crops_district_area.schema.json` | 2,743 | `02dacccf05aa94ef32a63a504ec7a931168e2d2c5973550ce7ecd8e5852afd43` |
| `opendosm_crops_district_production/crops_district_production.csv` | 646,744 | `d5ea31dc6d9badebc0efe8b2298b7e93a3a81dfdb7274e77f29a4a0b82da955e` |
| `opendosm_crops_district_production/crops_district_production.issues.jsonl` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `opendosm_crops_district_production/crops_district_production.rejected.jsonl` | 166,800 | `1e0b15657f62201f2c8a9e9ae81d4bdd4d67f18651a2d5e9d56867e7c96d948a` |
| `opendosm_crops_district_production/crops_district_production.schema.json` | 2,776 | `80fbc983a985148a6b82c564763615d475e6bc5ad235e67a31531ed06b869ee7` |
| `opendosm_crops_state/crops_state.csv` | 83,322 | `8f920022a90d7557c470c529816c500ba3be2cb1653e0f14d13f1cc60eea7b5a` |
| `opendosm_crops_state/crops_state.issues.jsonl` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `opendosm_crops_state/crops_state.rejected.jsonl` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `opendosm_crops_state/crops_state.schema.json` | 2,644 | `8fa9c2eb042b823d34ca77c65ed1399ed4171e2251e66c7901cdc56bca8c4753` |
| `openfda/recalls.csv` | 22,444,347 | `7b52562e147c8d6a3650d6200099cf9631acba1634f590c29252685f19b79d81` |
| `openfda/recalls.issues.jsonl` | 138 | `b561404e0e42889da2435c583f914b8cfc4f3b3a98ab14659ecd606edac2b1f4` |
| `openfda/recalls.rejected.jsonl` | 1,395 | `542c795a0eb419d1438d1b64d23b486dac248f4c8f5f6dd033c4887fbfa1de49` |
| `openfda/recalls.schema.json` | 4,947 | `58c11318be3d9b017ec9b0ebf0bc6d8102da1bc8c5a49456f8069eea6b10bbb0` |
| `usda_pdp/results.csv` | 217,770,561 | `42dddfe4df43cc63e8ed3295ed8a783aebb13b3a95dbc3ded3b58d9ccbc1b92e` |
| `usda_pdp/results.issues.jsonl` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `usda_pdp/results.rejected.jsonl` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `usda_pdp/results.schema.json` | 3,914 | `1931aefd789db2ef867933288496da36d7489a8591a37f8002f9a15954dae28a` |
| `usda_pdp/samples.csv` | 897,014 | `0d3d5bca6390f4cec5aed0fb35c953a10f996e56546ad2fe36dc1a6c138b979c` |
| `usda_pdp/samples.issues.jsonl` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `usda_pdp/samples.rejected.jsonl` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `usda_pdp/samples.schema.json` | 3,648 | `d376bda04bcea5dc4c6e9e2fdbc419d6c5e295d7172d151e42f7b2f6d6ca08f3` |

## Limits and handoff

- Before missingness counts lexical blank/null source fields; some blanks are documented defaults, not unknown
- After missingness counts explicit nulls among accepted rows only
- Rejection reason counts can overlap; row totals are unique records
- NOAA raw monthly rows expand to calendar-day element records; padding is accounted separately
- IDs and source-row references are lineage/grouping metadata, not approved predictors.
- Analytical CONCEN/MEAN/ANNOTATE, recall status/reason/termination, and quality metadata are not approved predictors or universal contamination labels.
- Literal free-text N/A/Na tokens are retained unless a field dictionary explicitly defines them; missing reasons can remain ambiguous.
- NOAA flagged values remain visible; M3 must inspect quality before later weather features. Daily reporting dates have unknown availability/timezone semantics.
- OpenDOSM reference_date/year is annual context, not publication time; national/state totals must not be blindly summed.
- Later EDA, canonical schema, features, enrichment and leakage audits are required before modeling.
- Python 3.11+ standard library only. sqlite3 provides temporary disk-backed exact-result duplicate detection; target Python must include SQLite support. No new PyPI/native package installed.
- Source manifest and cleaning-code hashes, output hashes and before/after raw integrity checks are in m2_cleaning_summary.json; reproducibility/test evidence is in m2_validation.json.
- Pending FSIS and FDA inspection source entries were not cleaned. Person B code, raw artifacts and frozen M1 reports/receipts remain unchanged.
