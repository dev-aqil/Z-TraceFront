# M3 — Source-specific EDA and data-quality audit

**COMPLETE for the validated M2 cohort. NOT MODEL-READY.**

Full streaming census of seven source tables. No source joins, predictive features, new labels, imputation or training.

Reproduce: `PYTHONPATH=src python -m tracefront_data.eda`.

The JSON contains per-column null/empty/token counts, categorical cardinality, date coverage, unit-specific numeric distributions, assay/flag diagnostics and rejected-record evidence. The HTML contains focused count visuals and expandable diagnostics.

## Methods and interpretation

- Nulls follow the M2 typed schema. Empty strings, blank flags, empty JSON objects, legitimate zero and literal N/A are counted separately.
- Categorical counts are exact up to 10,000 distinct values per field. Above that, report a lower bound and withhold rankings. Free text is not treated as a useful category distribution.
- Numeric quantiles use exact nearest rank; histogram bins are left-closed/right-open except the final inclusive bin. Numeric summaries separate units and NOAA element/status. Reference years and lineage integers are excluded from numeric distributions.
- All percentages are descriptive frequencies of captured records. They do not establish population risks or contamination prevalence.
- Every M1 raw artifact and M2 output was verified before profiling; their bytes were checked again after profiling.

## noaa_ghcn_daily

Role: AUXILIARY_FEATURE_SOURCE

### daily_observations

Rows: 80,693. Grain: Station x calendar date x element, including missing observations.

| Field with nulls | Count | % of clean rows |
| --- | ---: | ---: |
| value | 21,038 | 26.07% |

Date coverage: `{"observation_date": {"max": "2025-08-31", "min": "1949-04-01"}}`.

| Numeric field / unit partition | Nonnull | Zero | Min | Median | p95 | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| value [PRCP/mm/reported_unflagged] | 17,232 | 7,777 | 0 | 0.5 | 39.1 | 400.1 |
| value [TAVG/degC/reported_unflagged] | 21,361 | 0 | 22.6 | 27.2 | 29.6 | 32 |
| value [TMAX/degC/reported_unflagged] | 10,772 | 0 | 24.6 | 33 | 35 | 39 |
| value [TMIN/degC/quality_flagged] | 32 | 0 | 12 | 23 | 23 | 23 |
| value [TMIN/degC/reported_unflagged] | 10,258 | 0 | 18 | 23.9 | 25.7 | 27.5 |

- MYM00048647 / PRCP (mm): 1949-04-01 to 2025-08-31; 22,552 represented slots; 5,360 absent calendar slots within that span.
- Status counts: `{"publisher_missing": 5320, "reported_unflagged": 17232}`; quality flags: `{"<BLANK>": 22552}`.

- MYM00048647 / TAVG (degC): 1949-04-01 to 2025-08-31; 23,739 represented slots; 4,173 absent calendar slots within that span.
- Status counts: `{"publisher_missing": 2378, "reported_unflagged": 21361}`; quality flags: `{"<BLANK>": 23739}`.

- MYM00048647 / TMAX (degC): 1949-04-01 to 2025-08-31; 16,532 represented slots; 11,380 absent calendar slots within that span.
- Status counts: `{"publisher_missing": 5760, "reported_unflagged": 10772}`; quality flags: `{"<BLANK>": 16532}`.

- MYM00048647 / TMIN (degC): 1949-04-01 to 2025-08-31; 17,870 represented slots; 10,042 absent calendar slots within that span.
- Status counts: `{"publisher_missing": 7580, "quality_flagged": 32, "reported_unflagged": 10258}`; quality flags: `{"<BLANK>": 17838, "D": 2, "K": 24, "O": 6}`.

Retained issue counts: `{"quality_flagged_observation_retained": 32}`.

Interpretation and leakage candidates:

- One Malaysian station is not national spatial coverage.
- Absent calendar slots and -9999 missing values have different denominators.
- Blank quality flag means no failed check recorded, not guaranteed validity.
- Yearly counts audit coverage only; no rolling weather features are computed.
- Daily reference dates do not establish historical public availability.

Pinned NOAA flag definitions are included in the JSON, with the complete README path/checksum. Observed QFLAG D = failed duplicate check; K = failed streak/frequent-value check; O = failed climatological outlier check.

## opendosm_crops_district_area

Role: EXTERNAL_CONTEXT_SOURCE

### crops_district_area

Rows: 10,010. Grain: Annual state x district x crop type x species.

| Field with nulls | Count | % of clean rows |
| --- | ---: | ---: |
| None | 0 | 0.00% |

Date coverage: `{"reference_date": {"max": "2017-01-01", "min": "2017-01-01"}}`.

| Numeric field / unit partition | Nonnull | Zero | Min | Median | p95 | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| planted_area [hectares] | 10,010 | 4,749 | 0.0 | 0.2 | 133.1 | 24628.0 |

Rejections: 545; reasons: `{"conflicting_aggregate_key_all_versions_quarantined": 428, "exact_duplicate_aggregate": 117}`.

Annual reference coverage: 2017-01-01 to 2017-01-01; not publication dates.
Conflicting key groups: 214; groups containing both zero and nonzero values: 113.

Example conflicting keys (all versions remain quarantined):

- `2017-01-01|Johor|Tangkak|industrial_crops|coconut`: 2551.2, 0.0
- `2017-01-01|Johor|Tangkak|industrial_crops|mushroom`: 62.6, 0.0
- `2017-01-01|Sabah|Keningau|cash_crops|cassava`: 0.0, 10.0
- `2017-01-01|Sabah|Keningau|cash_crops|sweet_corn`: 34.0, 0.0
- `2017-01-01|Sabah|Keningau|cash_crops|yam`: 0.0, 18.0

Interpretation and leakage candidates:

- Annual reference markers are not publication timestamps; district coverage is 2017 only.
- Missing district/crop combinations are not measured zeros.
- National/state totals overlap; neither are blindly summed here.
- Conflicting key versions remain quarantined; undocumented strata or publisher duplication remain unresolved.
- Production/area context is not food contamination ground truth.

## opendosm_crops_district_production

Role: EXTERNAL_CONTEXT_SOURCE

### crops_district_production

Rows: 10,471. Grain: Annual state x district x crop type x species.

| Field with nulls | Count | % of clean rows |
| --- | ---: | ---: |
| None | 0 | 0.00% |

Date coverage: `{"reference_date": {"max": "2017-01-01", "min": "2017-01-01"}}`.

| Numeric field / unit partition | Nonnull | Zero | Min | Median | p95 | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| production [metric tonnes] | 10,471 | 5,321 | 0.0 | 0.0 | 848.7 | 175141.75 |

Rejections: 531; reasons: `{"conflicting_aggregate_key_all_versions_quarantined": 414, "exact_duplicate_aggregate": 117}`.

Annual reference coverage: 2017-01-01 to 2017-01-01; not publication dates.
Conflicting key groups: 207; groups containing both zero and nonzero values: 118.

Example conflicting keys (all versions remain quarantined):

- `2017-01-01|Johor|Tangkak|industrial_crops|coconut`: 12384.5, 0.0
- `2017-01-01|Johor|Tangkak|industrial_crops|mushroom`: 2135.8, 0.0
- `2017-01-01|Sabah|Keningau|cash_crops|cassava`: 0.0, 98.7
- `2017-01-01|Sabah|Keningau|cash_crops|sweet_corn`: 8.2, 0.0
- `2017-01-01|Sabah|Keningau|cash_crops|yam`: 0.0, 30.0

Interpretation and leakage candidates:

- Annual reference markers are not publication timestamps; district coverage is 2017 only.
- Missing district/crop combinations are not measured zeros.
- National/state totals overlap; neither are blindly summed here.
- Conflicting key versions remain quarantined; undocumented strata or publisher duplication remain unresolved.
- Production/area context is not food contamination ground truth.

## opendosm_crops_state

Role: EXTERNAL_CONTEXT_SOURCE

### crops_state

Rows: 1,584. Grain: Annual state/country x crop type.

| Field with nulls | Count | % of clean rows |
| --- | ---: | ---: |
| None | 0 | 0.00% |

Date coverage: `{"reference_date": {"max": "2024-01-01", "min": "2014-01-01"}}`.

| Numeric field / unit partition | Nonnull | Zero | Min | Median | p95 | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| planted_area [hectares] | 1,584 | 128 | 0.0 | 1319.0 | 74594.0 | 699980.0 |
| production [metric tonnes] | 1,584 | 130 | 0.0 | 19406.0 | 3480604.0 | 528096218.0 |

Annual reference coverage: 2014-01-01 to 2024-01-01; not publication dates.
Conflicting key groups: 0; groups containing both zero and nonzero values: 0.

Interpretation and leakage candidates:

- Annual reference markers are not publication timestamps; district coverage is 2017 only.
- Missing district/crop combinations are not measured zeros.
- National/state totals overlap; neither are blindly summed here.
- Conflicting key versions remain quarantined; undocumented strata or publisher duplication remain unresolved.
- Production/area context is not food contamination ground truth.

## openfda_enforcement

Role: HISTORICAL_RISK_SOURCE

### recalls

Rows: 29,484. Grain: Product-specific food recall enforcement record; event_id can repeat.

| Field with nulls | Count | % of clean rows |
| --- | ---: | ---: |
| more_code_info | 29,483 | 100.00% |
| address_2 | 8,989 | 30.49% |
| termination_date | 1,526 | 5.18% |
| termination_date_raw | 1,526 | 5.18% |
| product_quantity | 437 | 1.48% |
| state | 237 | 0.80% |
| code_info | 29 | 0.10% |
| initial_firm_notification | 3 | 0.01% |
| address_1 | 2 | 0.01% |
| center_classification_date | 1 | 0.00% |
| center_classification_date_raw | 1 | 0.00% |
| recall_initiation_date | 1 | 0.00% |
| voluntary_mandated | 1 | 0.00% |

Date coverage: `{"center_classification_date": {"max": "2026-10-01", "min": "2012-06-08"}, "recall_initiation_date": {"max": "2026-09-24", "min": "2008-02-22"}, "report_date": {"max": "2026-10-07", "min": "2012-06-20"}, "termination_date": {"max": "2026-10-01", "min": "2012-06-08"}}`.

| Numeric field / unit partition | Nonnull | Zero | Min | Median | p95 | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |

Date-order audit (comparable-pair denominators included): `{"empty_openfda_object": 29484, "report_date_before_center_classification_date": 2214, "report_date_before_center_classification_date__comparable": 29483, "report_date_before_recall_initiation_date__comparable": 29483, "termination_date_before_recall_initiation_date__comparable": 27957}`.

Repeated event identifiers: `{"distinct_keys": 7906, "keys_with_multiple_records": 2780, "records_beyond_first_per_key": 21578, "records_per_key": {"count": 7906, "distribution_status": "exact", "histogram": [{"count": 7816, "lower": "1.0", "upper": "41.8", "upper_inclusive": false}, {"count": 56, "lower": "41.8", "upper": "82.6", "upper_inclusive": false}, {"count": 18, "lower": "82.6", "upper": "123.4", "upper_inclusive": false}, {"count": 4, "lower": "123.4", "upper": "164.2", "upper_inclusive": false}, {"count": 5, "lower": "164.2", "upper": "205.0", "upper_inclusive": false}, {"count": 2, "lower": "205.0", "upper": "245.8", "upper_inclusive": false}, {"count": 2, "lower": "245.8", "upper": "286.6", "upper_inclusive": false}, {"count": 0, "lower": "286.6", "upper": "327.4", "upper_inclusive": false}, {"count": 1, "lower": "327.4", "upper": "368.2", "upper_inclusive": false}, {"count": 2, "lower": "368.2", "upper": "409.0", "upper_inclusive": true}], "max": "409", "mean": "3.729319504174045029091828991", "min": "1", "negative_count": 0, "quantile_method": "Exact nearest-rank, among nonnull values; no interpolation", "quantiles": {"p25": "1", "p50": "1", "p75": "2", "p95": "12", "p99": "47"}, "zero_count": 0}, "rows": 29484}`.

Rejections: 1; reasons: `{"missing_recall_number": 1}`.

Retained issue counts: `{"invalid_recall_initiation_date": 1}`.

Interpretation and leakage candidates:

- All records describe recalls; there is no tested-negative comparison population.
- Classification/status frequencies are contextual, not contamination class balance.
- event_id may repeat across product-specific recalls; firm strings are not verified entity IDs.
- Status, reason, classification and termination can reveal retrospective outcomes.
- Snapshot registration does not recover its original download URL/time or historical field versions.

Raw-source field presence (includes the rejected record; absent fields explain null counts not shown in M2 lexical-blank counts):

```json
{
  "fields": {
    "address_1": {
      "empty_string": 2,
      "provided": 29483
    },
    "address_2": {
      "empty_string": 8990,
      "provided": 20495
    },
    "center_classification_date": {
      "absent": 2,
      "provided": 29483
    },
    "city": {
      "provided": 29485
    },
    "classification": {
      "provided": 29485
    },
    "code_info": {
      "empty_string": 29,
      "provided": 29456
    },
    "country": {
      "provided": 29485
    },
    "distribution_pattern": {
      "provided": 29485
    },
    "event_id": {
      "provided": 29485
    },
    "initial_firm_notification": {
      "empty_string": 3,
      "provided": 29482
    },
    "more_code_info": {
      "absent": 16511,
      "empty_string": 12973,
      "provided": 1
    },
    "openfda": {
      "empty_object": 29485
    },
    "postal_code": {
      "provided": 29485
    },
    "product_description": {
      "provided": 29485
    },
    "product_quantity": {
      "empty_string": 437,
      "provided": 29048
    },
    "product_type": {
      "provided": 29485
    },
    "reason_for_recall": {
      "provided": 29485
    },
    "recall_initiation_date": {
      "provided": 29485
    },
    "recall_number": {
      "empty_string": 1,
      "provided": 29484
    },
    "recalling_firm": {
      "provided": 29485
    },
    "report_date": {
      "provided": 29485
    },
    "state": {
      "empty_string": 237,
      "provided": 29248
    },
    "status": {
      "provided": 29485
    },
    "termination_date": {
      "absent": 1527,
      "provided": 27958
    },
    "voluntary_mandated": {
      "empty_string": 1,
      "provided": 29484
    }
  },
  "raw_rows": 29485,
  "warning": "Raw-source counts include the quarantined record; M2 accepted-row null counts use a different denominator."
}
```

## usda_pdp

Role: DIRECT_LABEL_SOURCE

### results

Rows: 2,872,073. Grain: PDP analytical result; multiple analytes/extractions per sample.

| Field with nulls | Count | % of clean rows |
| --- | ---: | ---: |
| confmethod2 | 2,872,073 | 100.00% |
| duplicate_of_source_row | 2,872,073 | 100.00% |
| quantitate | 2,871,781 | 99.99% |
| concen | 2,853,583 | 99.36% |
| confmethod | 2,853,583 | 99.36% |
| concen_missing_reason | 18,490 | 0.64% |

Date coverage: `{}`.

| Numeric field / unit partition | Nonnull | Zero | Min | Median | p95 | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| concen [M] | 18,490 | 0 | 0.001 | 0.0202 | 0.8535 | 41.5806 |
| lod [M] | 2,872,073 | 0 | 0.0006 | 0.005 | 0.030 | 0.50 |

MEAN result codes: `{"ND": 2798390, "NP": 55193, "O": 18458, "R": 32}`.

Detected sample/analyte groups with both O and R: 0. These are repeated analytical evidence, not independent samples.

### Analytical-record codes by commodity

| Commodity code | ND | NP | O | R | Analytical rows |
| --- | ---: | ---: | ---: | ---: | ---: |
| AL | 100,752 | 1,290 | 601 | 5 | 102,648 |
| AP | 164,870 | 0 | 2,742 | 2 | 167,614 |
| AV | 258,213 | 7,763 | 98 | 0 | 266,074 |
| BK | 134,726 | 1,493 | 2,465 | 18 | 138,702 |
| CB | 149,002 | 6,155 | 78 | 0 | 155,235 |
| CS | 24,805 | 1,041 | 3 | 0 | 25,849 |
| CT | 168,987 | 7,890 | 1,724 | 0 | 178,601 |
| CU | 195,571 | 3,827 | 2,577 | 0 | 201,975 |
| FS | 34,964 | 176 | 3 | 0 | 35,143 |
| KZ | 4,671 | 62 | 130 | 0 | 4,863 |
| LH | 162,223 | 2,832 | 703 | 1 | 165,759 |
| LL | 157,854 | 4,235 | 3,144 | 0 | 165,233 |
| NZ | 26,557 | 579 | 4 | 0 | 27,140 |
| OG | 167,267 | 0 | 1,648 | 2 | 168,917 |
| ON | 156,279 | 1,337 | 257 | 0 | 157,873 |
| PK | 161,996 | 0 | 344 | 0 | 162,340 |
| PN | 335,266 | 7,325 | 82 | 0 | 342,673 |
| PO | 52,457 | 5,822 | 308 | 0 | 58,587 |
| TT | 341,930 | 3,366 | 1,547 | 4 | 346,847 |

Denominator: analytical records within each commodity code, not food-batch contamination frequency. Codes retain official source spelling; no product matching or source join.
### samples

Rows: 9,872. Grain: PDP 2024 sample identity record.

| Field with nulls | Count | % of clean rows |
| --- | ---: | ---: |
| growst | 8,926 | 90.42% |
| packst | 7,817 | 79.18% |
| country | 6,028 | 61.06% |
| country_missing_reason | 3,844 | 38.94% |
| distst | 2,661 | 26.96% |
| quantity | 2,046 | 20.73% |

Date coverage: `{"collection_date": {"max": "2024-12-23", "min": "2024-01-02"}}`.

| Numeric field / unit partition | Nonnull | Zero | Min | Median | p95 | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| quantity [unspecified] | 7,826 | 0 | 1 | 7 | 27 | 2124 |

Interpretation and leakage candidates:

- Assay counts are not independent sample counts or population contamination rates.
- ND and NP are distinct nondetect codes, not zeros. LOD varies by assay.
- O/R and publisher annotations are analytical outcomes, not approved predictors.
- Publisher presumptive-violation annotation codes do not establish an independently validated exceedance label.
- Collection date does not prove result/publication availability; sample IDs and lab codes require leakage review.

## Decisions and remaining issues

- M3 eligible-source profiling is complete. No sample-level contamination prevalence or regulatory exceedance target was created.
- PDP target definition must address censoring, assay panels, repeated extractions and effective regulatory thresholds separately. Result codes, concentration and annotations require outcome/predictor separation in later milestones.
- NOAA coverage is station/element-specific; missing spans, QA flags and source changes require an explicit future policy before enrichment.
- OpenDOSM conflicts require publisher clarification. Keep rejected versions; never select zero/nonzero or add them together by assumption.
- openFDA snapshot provenance and historical field-availability gaps remain; recall frequencies cannot estimate incidence.
- FSIS remains **official source confirmed, raw file not yet acquired**. FDA inspections remain pending. Neither was profiled.
- Person B may inspect these descriptive reports. Source tables remain NOT MODEL-READY; canonical contracts, feature engineering, enrichment and formal leakage validation remain future work.
- Python 3.11+ standard library only; no native dependency added. LinuxONE/s390x execution remains untested.
