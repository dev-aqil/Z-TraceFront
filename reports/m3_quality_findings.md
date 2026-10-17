# M3 — Scientific review of the measured profiles

**NOT MODEL-READY.** Read alongside [the generated report](m3_eda_report.md), [full profiles](m3_eda_summary.json), and [visuals](m3_eda_visuals.html). This is interpretation of measured local artifacts, not a change to any source table or an approval of predictors/targets.

## USDA PDP: denominators, censoring and analytical outcomes

The 2,872,073 analytical records refer to 9,872 distinct sample IDs in the result table. All represented samples have multiple assays: 187–524 records per sample, with a median of 238. Thus assay-record frequencies cannot be interpreted as sample positivity rates, and random analytical-row splits would put the same sample into multiple partitions. No sample/result join or sample-level label was generated.

MEAN counts are ND 2,798,390; NP 55,193; O 18,458; R 32. Every ND/NP concentration is null and every O/R concentration is numeric in this captured release. The reviewed dictionary distinguishes well-recovered ND nondetects from marginal-performing NP nondetects. Neither becomes zero, an untested result, or an independently established safe-food outcome. All observed CONUNIT codes are `M`; the code is retained rather than guessed or converted.

There are 18,490 detected sample/analyte groups. **None contains both O and R, and none has multiple detected records in this release.** Re-extraction dependence is a future source-policy concern, not an observed duplicate group here. The broader assay panel still repeats each sample hundreds of times.

Observed nonempty annotations are Q 1,008; QV 18; V 376; X 78. The pinned reference workbook describes Q as below quantifiable level and QV/V/X as publisher presumptive-violation annotations. These are outcome-associated metadata. They are not approved predictors, and this audit neither verifies legal thresholds nor turns annotations into regulatory-exceedance labels.

Unknown sample location/origin attributes remain important: COUNTRY is null for 6,028 samples, GROWST for 8,926 and PACKST for 7,817. Missing COUNTRY includes documented domestic non-applicability as well as origin uncertainty; the profile preserves the origin/missing-reason cross-tabulation. SOURCE_ID has 7,314 non-null empty defaults, which must not be recoded as ordinary unknowns.

Dictionary evidence remains in the pinned annual archive recorded in `reports/m1_source_manifest.json`: `PDP DataDictionary 2024.pdf` and `PDP ReferenceTables 2024.xlsx`. Collection date is not result availability time.

## NOAA: incomplete coverage and quality information

The one captured station, MYM00048647, has represented records spanning 1949-04-01 through 2025-08-31. Coverage differs by element:

| Element | Represented calendar slots | Sentinel-missing slots | Entirely absent slots within element span | Quality-flagged numeric values |
| --- | ---: | ---: | ---: | ---: |
| PRCP | 22,552 | 5,320 | 5,360 | 0 |
| TAVG | 23,739 | 2,378 | 4,173 | 0 |
| TMAX | 16,532 | 5,760 | 11,380 | 0 |
| TMIN | 17,870 | 7,580 | 10,042 | 32 |

Each inclusive span contains 27,912 calendar days. Sentinel-missing counts are part of represented slots; absent slots are outside that denominator. Neither means zero rainfall or a temperature of zero. The audit does not fill either kind of gap.

All 32 quality-flagged numeric observations are TMIN: D 2 (failed duplicate check), K 24 (failed streak/frequent-value check), and O 6 (failed climatological outlier check). Flagged TMIN ranges from 12 to 23 °C. The publisher's QFLAG D is a failed quality check, not proof of duplicate table keys. Measurement flags also matter: PRCP has 1,381 D flags (four six-hour totals), while TAVG has 21,361 H flags (hourly-derived averages). These meanings come from the pinned GHCN README, whose path/hash and first-line definitions are in the profile JSON; consult continuation lines before applying any policy.

The largest reported-unflagged PRCP value is 400.1 mm on 1981-05-01 (raw integer 4001, raw monthly source row 839). It is an extreme value for review, **not** an automatic invalid reading. No arbitrary extreme-rainfall cutoff or new heat/rain feature was introduced. Blank QFLAG does not certify accuracy, and the source flag `S` and hourly-average semantics deserve review before future enrichment. No national representativeness or historical public-availability guarantee follows from this single station.

## openFDA: record/event dependence and retrospective fields

The 29,484 accepted recall records cover 7,906 distinct event IDs. Of those events, 2,780 contain multiple product records; the largest has 409. These repeated event IDs are legitimate record-grain structure. Recalling-firm strings are not validated supplier IDs.

**2,214 of 29,483 comparable records have a center-classification date after the report date.** This is evidence that report date cannot automatically serve as the availability time for the snapshot's classification field. No comparable accepted record has report date before initiation or termination before initiation. The malformed initiation token `02121207` remains an issue with a null normalized date, not a guessed correction.

In the 29,485-row raw snapshot, `more_code_info` is absent in 16,511 records, explicitly empty in 12,973, and populated in one. This explains the much larger cleaned null count than the M2 lexical-empty count. The denominators differ by the one quarantined record. All raw `openfda` objects are empty `{}`; this snapshot provides no populated openFDA identifier enrichment.

No tested-negative population or contaminated-versus-safe label exists here. Recall classification, status, reason, termination and later updates are retrospective leakage candidates. The registered snapshot still lacks its original download URL and retrieval clock; local registration and checksums do not repair historical field-version provenance.

## OpenDOSM: conflicts, zeros and a production-unit question

All three tables have no explicit null cells among accepted records. This says nothing about absent district/crop combinations. Legitimate zeros remain: 4,749 accepted district-area rows and 5,321 district-production rows have zero values. District coverage is 2017; state coverage is 2014–2024. These are annual reference years, not publication timestamps.

Area has 214 conflicting keys: Sarawak 126, Sabah 83, Selangor 3 and Johor 2. Production has 207: Sarawak 126, Sabah 79 and Johor 2. Of these, 113 area keys and 118 production keys contain zero and nonzero versions. The concentration in particular states merits publisher clarification; neither geographic risk nor the cause of the duplication can be inferred. The 117 additional identical duplicate rows in each district table are a separate issue. All conflicts remain quarantined, with raw values and source-row references.

**Production-unit interpretation requires confirmation for the state table, especially `crop_type=flower`.** Its largest value is `528096218.0` for Malaysia/2019/flower, accompanied by planted area `2702.3`. This is source row 28 in `crops_state.csv`. The preserved official catalog explicitly describes production as metric tonnes, so M2's unit label follows that metadata. However, the magnitude and category warrant confirmation of crop-specific units with the publisher before physical or cross-crop interpretation. No alternative unit (such as counts), conversion, clipping or correction has been assumed. The catalog alone does not settle this scientific concern.

Catalog evidence: [preserved crops_state catalog](../data/raw/opendosm/sha256/f5d90d4b1404fb01abbf3d4d775bc62e682d9e699df4e8120da09fab7a217d5c/crops_state.html), SHA-256 `f5d90d4b1404fb01abbf3d4d775bc62e682d9e699df4e8120da09fab7a217d5c`. The generated numeric summaries are descriptive distributions under the **publisher-declared** units, not confirmation that every crop shares physically comparable units. National/state totals overlap and were not summed.

## Implications for the next milestone

M3 auditing is complete for the eligible cohort; these findings remain open scientific/data questions. M4 may design source-specific contracts while marking uncertain units, entity meanings and field availability explicitly pending. Do not approve questionable production units, recall snapshot dates or assay outcomes as predictors merely because their datatypes parse.

Person B may inspect the reports and source tables descriptively. No dataset is a final training table, no universal contamination target exists, and no source-family joins or predictive features were created. FSIS remains **official source confirmed, raw file not yet acquired**; FDA inspections remain pending and neither was analyzed.
