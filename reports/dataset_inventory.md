# Dataset inventory — current M1 acquisition, 2026-10-17

**M1 PARTIAL.** This section supersedes acquisition statuses and priorities in the historical M0 inventory below. M2 has not begun. Six source entries across four source families are eligible for later **source-specific cleaning**, not for modeling, pooling or enrichment joins. FSIS and FDA inspection records remain pending. Experimental cold-chain sources and RASFF were not acquired.

[Machine-readable source manifest](m1_source_manifest.json) contains all receipts, schemas, raw result-code counts, licenses, gates and dictionary evidence. [Immutable acquisition receipt](../data/manifests/20261017T060123145416Z-29c44de9.json) preserves the run config/code hashes and original clocks. The inspection report records its own current code hashes. Sizes/counts below are measured from bytes; unknown counts are not zero. Hashes are locally computed SHA-256 pins, not publisher signatures.

| Source | Acquisition | Measured records / grain | ML role | Domain | M2 eligible |
| --- | --- | --- | --- | --- | --- |
| USDA PDP 2024 | acquired | 9,872 sample records; 2,872,073 analytical results | `DIRECT_LABEL_SOURCE` | `CHEMICAL` | Yes, source-specific |
| openFDA Food Enforcement | acquired | 29,485 raw records | `HISTORICAL_RISK_SOURCE` | `CONTEXT_ONLY` | Yes, source-specific |
| FDA inspection classifications | pending | Unknown; no data artifact acquired | `HISTORICAL_RISK_SOURCE` | `CONTEXT_ONLY` | No |
| NOAA GHCN-Daily Malaysian station pilot | acquired | 2,651 raw records | `AUXILIARY_FEATURE_SOURCE` | `CONTEXT_ONLY` | Yes, source-specific |
| OpenDOSM state crops | acquired | 1,584 raw records | `EXTERNAL_CONTEXT_SOURCE` | `CONTEXT_ONLY` | Yes, source-specific |
| OpenDOSM district crop production | acquired | 11,002 raw records | `EXTERNAL_CONTEXT_SOURCE` | `CONTEXT_ONLY` | Yes, source-specific |
| OpenDOSM district crop planted area | acquired | 10,555 raw records | `EXTERNAL_CONTEXT_SOURCE` | `CONTEXT_ONLY` | Yes, source-specific |
| USDA FSIS raw poultry | pending | Unknown; no data artifact acquired | `DIRECT_LABEL_SOURCE` | `BIOLOGICAL` | No |

## USDA PDP 2024

- Official publisher: USDA Agricultural Marketing Service.
- Canonical source: [https://www.ams.usda.gov/datasets/pdp/pdpdata](https://www.ams.usda.gov/datasets/pdp/pdpdata).
- Acquisition: **acquired**. Scope: One complete annual release; no pooling with other years.
- License: US public domain under USDA Digital Rights and Copyright policy, except marked third-party material; attribution requested.
- Release/version: 2024 annual database; publisher posted 2025-12-23; embedded dictionary dated 2025-08-08.
- Measured count: 9,872 sample records; 2,872,073 analytical results.
- Row granularity: Sample identity record and separate analytical result record; multiple results per SAMPLE_PK; not yet joined.
- Time coverage: 2024 (raw YEAR/MONTH/DAY distributions recorded; no date normalization).
- Geography: US sampling STATE; ORIGIN/COUNTRY and GROWST/PACKST/DISTST codes; not coordinates.
- Available identifiers: SAMPLE_PK (release-local), SITE (collection site, not farm/facility), LAB, COMMOD, PESTCODE.
- Available timestamps: YEAR, MONTH, DAY.
- Useful fields / schema: Samples: SAMPLE_PK, STATE, YEAR, MONTH, DAY, SITE, COMMOD, SOURCE_ID, VARIETY, ORIGIN, COUNTRY, DISTTYPE, COMMTYPE, CLAIM, QUANTITY, GROWST, PACKST, DISTST; results: SAMPLE_PK, COMMOD, COMMTYPE, LAB, PESTCODE, TESTCLASS, CONCEN, LOD, CONUNIT, CONFMETHOD, CONFMETHOD2, ANNOTATE, QUANTITATE, MEAN, EXTRACT, DETERMIN.
- Possible target: Raw concentration / documented detection finding; regulatory exceedance remains conditional.
- Intended role/domain: `DIRECT_LABEL_SOURCE` / `CHEMICAL`.
- M2 eligible: **Yes**. Gates: license_known=true; provenance_confirmed=true; raw_data_present_and_hash_pinned=true; row_granularity_understood=true; schema_issues_documented=true; schema_review_passed=true.
- License basis: [USDA Digital Rights and Copyright policy](https://www.usda.gov/policies-and-links), reviewed in the browser on 2026-10-17. Automated HTML capture returned 403. The review/basis is pinned in config and receipt; no 2024-specific CC0 statement was obtained and another year's catalog license was not substituted. Retain policy exceptions/USDA attribution.
- Matching dictionary/code tables are embedded in the ZIP and have member SHA-256/CRC evidence in the manifest. Source text is headerless; publisher instructions offer a text import route without Microsoft Access. No sample/results join was executed.
- Observed MEAN codes: ND=2,798,390; NP=55,193; O=18,458; R=32. Observed ANNOTATE: blank=2,870,593; Q=1,008; QV=18; V=376; X=78. These are analytical-result counts, not unsafe sample counts. All result CONUNIT values are M (ppm).
- SAMPLE_PK is unique in all 9,872 samples; every result SAMPLE_PK exists in that table. The result table is one-to-many; sample/analyte uniqueness has not been assumed. This is referential inspection, not data merging.
- Major limitations:
  - Detection is not regulatory exceedance; applicable tolerance, units, residue definition and effective date require review
  - Search-export dictionary may differ from annual archive; embedded release documentation takes precedence
  - Untested analytes are not negatives; nondetects are censored
  - No 2024-specific CC0 declaration located; reuse basis is USDA general public-domain policy with stated exceptions, not the CC0 catalog entry for another year
  - Headerless file order from matching embedded annual dictionary; basename case differs in dictionary
  - SAMPLE_PK only unique within annual release; results are one-to-many and sample/analyte uniqueness unproven
  - Blank concentration denotes nondetect in annual text; ND and NP have distinct analytical quality meanings
  - Tolerance workbook exists but has special strings/notes and requires effective-date/residue-definition review
  - No safe/unsafe or chemical_exceedance label created; untested analytes absent

| Filename / local immutable path | Role | Bytes | SHA-256 | Actual retrieval time (UTC) |
| --- | --- | ---: | --- | --- |
| [2024PDPDatabase.zip](../data/raw/usda_pdp/sha256/de916ba119f8d6dd5a4d5596c69b00c476fceeb31a96b1389dd005031c9c4d79/2024PDPDatabase.zip)<br>`data/raw/usda_pdp/sha256/de916ba119f8d6dd5a4d5596c69b00c476fceeb31a96b1389dd005031c9c4d79/2024PDPDatabase.zip` | data | 10,600,875 | `de916ba119f8d6dd5a4d5596c69b00c476fceeb31a96b1389dd005031c9c4d79` | 2026-10-17T05:55:45.335571+00:00 |
| [pdpdata.html](../data/raw/usda_pdp/sha256/2ed2e7b9eb9111d0bd5ca722cf28a3101e49bc5c7d9615f33025e5509bcbf338/pdpdata.html)<br>`data/raw/usda_pdp/sha256/2ed2e7b9eb9111d0bd5ca722cf28a3101e49bc5c7d9615f33025e5509bcbf338/pdpdata.html` | documentation | 49,219 | `2ed2e7b9eb9111d0bd5ca722cf28a3101e49bc5c7d9615f33025e5509bcbf338` | 2026-10-17T05:55:44.364242+00:00 |
| [PDPDatabaseInstructions.pdf](../data/raw/usda_pdp/sha256/e1e1bbe759d73074a9915373097b5433f05aeb4c8ef7d70c5a904949ae4bb1fe/PDPDatabaseInstructions.pdf)<br>`data/raw/usda_pdp/sha256/e1e1bbe759d73074a9915373097b5433f05aeb4c8ef7d70c5a904949ae4bb1fe/PDPDatabaseInstructions.pdf` | documentation | 80,736 | `e1e1bbe759d73074a9915373097b5433f05aeb4c8ef7d70c5a904949ae4bb1fe` | 2026-10-17T05:55:44.645478+00:00 |
| [PDPSearchAppDataDictionary.pdf](../data/raw/usda_pdp/sha256/da5a0b019cafd956b707aef30059d1e089fa9893e721c78967fd3c3942e176e1/PDPSearchAppDataDictionary.pdf)<br>`data/raw/usda_pdp/sha256/da5a0b019cafd956b707aef30059d1e089fa9893e721c78967fd3c3942e176e1/PDPSearchAppDataDictionary.pdf` | documentation | 250,124 | `da5a0b019cafd956b707aef30059d1e089fa9893e721c78967fd3c3942e176e1` | 2026-10-17T05:55:43.768886+00:00 |

## openFDA Food Enforcement

- Official publisher: US FDA openFDA.
- Canonical source: [https://open.fda.gov/apis/food/enforcement/download/](https://open.fda.gov/apis/food/enforcement/download/).
- Acquisition: **acquired**. Scope: Existing official-byte-verified full food enforcement snapshot; original acquisition unknown.
- License: CC0-1.0 generally, subject to stated exceptions and service terms.
- Release/version: embedded last_updated=2026-10-14.
- Measured count: 29,485 raw records.
- Row granularity: product-specific recall enforcement record; multiple products can share event_id.
- Time coverage: report_date 2012-06-20..2026-10-07.
- Geography: Recalling-firm country/state/city/postal address plus textual distribution.
- Available identifiers: recall_number (one missing), event_id, recalling_firm (name, no verified facility ID).
- Available timestamps: report_date, recall_initiation_date, center_classification_date, termination_date.
- Useful fields / schema: address_1, address_2, center_classification_date, city, classification, code_info, country, distribution_pattern, event_id, initial_firm_notification, more_code_info, openfda, postal_code, product_description, product_quantity, product_type, reason_for_recall, recall_initiation_date, recall_number, recalling_firm, report_date, state, status, termination_date, voluntary_mandated.
- Possible target: None: context/history only, not safe-versus-contaminated truth.
- Intended role/domain: `HISTORICAL_RISK_SOURCE` / `CONTEXT_ONLY`.
- M2 eligible: **Yes**. Gates: license_known=true; provenance_confirmed=true; raw_data_present_and_hash_pinned=true; row_granularity_understood=true; schema_issues_documented=true; schema_review_passed=true.
- Existing `data/external/openfda/` paths are retained. Official ZIP comparison and extracted-member equality were revalidated; old local retrieval time stays unknown. The official comparison ZIP has its actual earlier M1 retrieval time in the receipt.
- 29,485 product-recall records, 25 columns, 7,907 event IDs; one missing recall_number and a raw initiation-date year 0212 remain unchanged. No negative denominator or direct contamination labels.
- Major limitations:
  - No tested-negative denominator or direct contamination labels
  - Firm location is not food origin; no verified facility crosswalk
  - Current recall status/termination and retrospective corrections can reveal future information
  - Original local retrieval time remains unknown
  - One missing recall_number; initiation-date year 0212 is retained unchanged

| Filename / local immutable path | Role | Bytes | SHA-256 | Actual retrieval time (UTC) |
| --- | --- | ---: | --- | --- |
| [food-enforcement-0001-of-0001.json](../data/external/openfda/sha256/02f3e7959cc732d8f1983f2b87edbbecc6d2f4959eaef50a597f640fbc513e2d/food-enforcement-0001-of-0001.json)<br>`data/external/openfda/sha256/02f3e7959cc732d8f1983f2b87edbbecc6d2f4959eaef50a597f640fbc513e2d/food-enforcement-0001-of-0001.json` | context_data | 39,906,111 | `02f3e7959cc732d8f1983f2b87edbbecc6d2f4959eaef50a597f640fbc513e2d` | Unknown original retrieval; import recorded separately |
| [food-enforcement-0001-of-0001.json.zip](../data/external/openfda/sha256/7f8e2b5bd6e05e0cbf15e43860c74538ad09e1f8b07928e9c92de3ead3dac9c6/food-enforcement-0001-of-0001.json.zip)<br>`data/external/openfda/sha256/7f8e2b5bd6e05e0cbf15e43860c74538ad09e1f8b07928e9c92de3ead3dac9c6/food-enforcement-0001-of-0001.json.zip` | original_local_archive | 5,858,570 | `7f8e2b5bd6e05e0cbf15e43860c74538ad09e1f8b07928e9c92de3ead3dac9c6` | Unknown original retrieval; import recorded separately |
| [download_index.json](../data/external/openfda/sha256/e9c8536852ecd25fdc15b79a5f7c41cb3803f31dbc7c52b86a6feddc3ac220a1/download_index.json)<br>`data/external/openfda/sha256/e9c8536852ecd25fdc15b79a5f7c41cb3803f31dbc7c52b86a6feddc3ac220a1/download_index.json` | official_download_metadata | 593,799 | `e9c8536852ecd25fdc15b79a5f7c41cb3803f31dbc7c52b86a6feddc3ac220a1` | 2026-10-17T05:40:03.609682+00:00 |
| [license.html](../data/external/openfda/sha256/7fda0041a24f8d7139a1781d4462ae39643a2ee6f3b0f079946c989a8e1982d2/license.html)<br>`data/external/openfda/sha256/7fda0041a24f8d7139a1781d4462ae39643a2ee6f3b0f079946c989a8e1982d2/license.html` | license_evidence | 123,019 | `7fda0041a24f8d7139a1781d4462ae39643a2ee6f3b0f079946c989a8e1982d2` | 2026-10-17T05:40:05.044709+00:00 |
| [foodenforcement_reference.pdf](../data/external/openfda/sha256/9c92fc04f447e70936c8646d9ac0f7a50af2118f01fd3b26d039e19860418baa/foodenforcement_reference.pdf)<br>`data/external/openfda/sha256/9c92fc04f447e70936c8646d9ac0f7a50af2118f01fd3b26d039e19860418baa/foodenforcement_reference.pdf` | official_field_dictionary | 55,827 | `9c92fc04f447e70936c8646d9ac0f7a50af2118f01fd3b26d039e19860418baa` | 2026-10-17T05:40:05.830130+00:00 |
| [food-enforcement-0001-of-0001.json.zip](../data/external/openfda/sha256/7f8e2b5bd6e05e0cbf15e43860c74538ad09e1f8b07928e9c92de3ead3dac9c6/food-enforcement-0001-of-0001.json.zip)<br>`data/external/openfda/sha256/7f8e2b5bd6e05e0cbf15e43860c74538ad09e1f8b07928e9c92de3ead3dac9c6/food-enforcement-0001-of-0001.json.zip` | official_archive_comparison | 5,858,570 | `7f8e2b5bd6e05e0cbf15e43860c74538ad09e1f8b07928e9c92de3ead3dac9c6` | 2026-10-17T05:40:08.830596+00:00 |

## FDA inspection classifications

- Official publisher: US FDA Office of Inspections and Investigations.
- Canonical source: [https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/inspection-classification-database](https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/inspection-classification-database).
- Acquisition: **pending**. Scope: Full public inspection classification XLSX; API alternative requires credentials.
- License: US public domain unless otherwise noted, under FDA website reuse policy; credit appreciated.
- Release/version: Sample release unknown; catalog dates are not sample-release dates.
- Measured count: Unknown; no data artifact acquired.
- Row granularity: Pending actual official raw file; documentation alone does not establish observed granularity.
- Time coverage: Unknown for raw records; no data file.
- Geography: Not observed in actual rows; pending data file.
- Available identifiers: Pending actual file.
- Available timestamps: Pending actual file.
- Useful fields / schema: Pending actual file; no field list inferred from catalog.
- Possible target: None: context/history only, not safe-versus-contaminated truth.
- Intended role/domain: `HISTORICAL_RISK_SOURCE` / `CONTEXT_ONLY`.
- M2 eligible: **No**. Gates: license_known=true; provenance_confirmed=true; raw_data_present_and_hash_pinned=false; row_granularity_understood=false; schema_issues_documented=false; schema_review_passed=false.
- Public dashboard documents classifications per project area within inspections. No actual inspection export was acquired, so row counts, observed schema, dates and identifier values are unknown.
- The dashboard's absolute `https://datadashboard.fda.gov/InspectionsDataset.xlsx` link and the tested dashboard-relative `/oii/cd/InspectionsDataset.xlsx` candidate both returned 404. The [official API documentation](https://datadashboard.fda.gov/oii/api/index.htm) requires Authorization-User and Authorization-Key via OII Unified Logon; no credentials or account creation used.
- Authenticated alternative: POST JSON with required `columns`, `filters`, `sort`, `sortorder`; optional rows<=5000, 1-based start and returntotalcount. Freeze request filters/order and every response page/total count after credentials become available. Inspect food project areas and actual response keys before a parser or M2 claim.
- Only official documentation and FDA public-domain reuse policy are captured here. No fabricated data filename or successful download is claimed; attempted export filenames are recorded as failed requests.
- Major limitations:
  - Official POST API requires Authorization-User and Authorization-Key from OII Unified Logon
  - NAI/VAI/OAI are compliance classifications, not measured contamination
  - FEI is not an FSIS establishment ID; classifications are project-area specific
  - No raw records acquired: dashboard absolute export link and dashboard-relative candidate returned 404; documented API needs credentials. Source field definitions do not establish actual export schema.

| Filename / local immutable path | Role | Bytes | SHA-256 | Actual retrieval time (UTC) |
| --- | --- | ---: | --- | --- |
| [inspection-classification-database.html](../data/raw/fda_inspections/sha256/7113e6b41a7ba98f99e93c2f4e073550636a653992ab555d1763b0127873a3f6/inspection-classification-database.html)<br>`data/raw/fda_inspections/sha256/7113e6b41a7ba98f99e93c2f4e073550636a653992ab555d1763b0127873a3f6/inspection-classification-database.html` | documentation | 42,257 | `7113e6b41a7ba98f99e93c2f4e073550636a653992ab555d1763b0127873a3f6` | 2026-10-17T05:55:45.750521+00:00 |
| [inspections.htm](../data/raw/fda_inspections/sha256/b47ab3cb75d1e4d97ef5b26081de461e873e4c323bef698f9c7ff02fa715c73d/inspections.htm)<br>`data/raw/fda_inspections/sha256/b47ab3cb75d1e4d97ef5b26081de461e873e4c323bef698f9c7ff02fa715c73d/inspections.htm` | documentation | 27,649 | `b47ab3cb75d1e4d97ef5b26081de461e873e4c323bef698f9c7ff02fa715c73d` | 2026-10-17T05:55:46.921522+00:00 |
| [api-index.htm](../data/raw/fda_inspections/sha256/91b62cbff3b236e5a2253030fb2d9ea5957d4ba99ffafe190a1f423f8e58a97d/api-index.htm)<br>`data/raw/fda_inspections/sha256/91b62cbff3b236e5a2253030fb2d9ea5957d4ba99ffafe190a1f423f8e58a97d/api-index.htm` | documentation | 58,406 | `91b62cbff3b236e5a2253030fb2d9ea5957d4ba99ffafe190a1f423f8e58a97d` | 2026-10-17T05:55:47.159603+00:00 |
| [website-policies.html](../data/raw/fda_inspections/sha256/63fe227e41e9843bd7855c25c9a7a26a50f0d5a51a7da23aab868d75361b605d/website-policies.html)<br>`data/raw/fda_inspections/sha256/63fe227e41e9843bd7855c25c9a7a26a50f0d5a51a7da23aab868d75361b605d/website-policies.html` | license_evidence | 45,587 | `63fe227e41e9843bd7855c25c9a7a26a50f0d5a51a7da23aab868d75361b605d` | 2026-10-17T05:57:23.596251+00:00 |

**No data artifact is present for this source.** The above are catalog/documentation artifacts only; their presence cannot pass the raw-data gate.

## NOAA GHCN-Daily Malaysian station pilot

- Official publisher: NOAA National Centers for Environmental Information.
- Canonical source: [https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc:C00861](https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc:C00861).
- Acquisition: **acquired**. Scope: Full available history for MYM00048647, verified in station inventory: Sultan Abdul Aziz Shah Intl, 3.131N 101.549E; bounded Malaysian ingestion pilot, not national weather coverage.
- License: US public domain under NCEI copyright policy, with exceptions and dataset use/citation constraints.
- Release/version: GHCN-Daily Version 3; rolling reconstruction; exact status file captured.
- Measured count: 2,651 raw records.
- Row granularity: station x year x month x weather element, with 31 day value/measurement/quality/source slots.
- Time coverage: ['1949-04', '2025-08'].
- Geography: Single Malaysian airport station; current official station line retained below.
- Available identifiers: MYM00048647.
- Available timestamps: YEAR, MONTH, day slot 1..31.
- Useful fields / schema: ID, YEAR, MONTH, ELEMENT, VALUE1..31, MFLAG1..31, QFLAG1..31, SFLAG1..31.
- Possible target: None: context/history only, not safe-versus-contaminated truth.
- Intended role/domain: `AUXILIARY_FEATURE_SOURCE` / `CONTEXT_ONLY`.
- M2 eligible: **Yes**. Gates: license_known=true; provenance_confirmed=true; raw_data_present_and_hash_pinned=true; row_granularity_understood=true; schema_issues_documented=true; schema_review_passed=true.
- Selected station was verified in the acquired official station inventory: MYM00048647, Sultan Abdul Aziz Shah Intl, 3.131°N 101.549°E, elevation 27.4 m. Selection establishes a reproducible Malaysian pilot, not national coverage or a farm/sample crosswalk.
- Element/month rows: PRCP=741, TAVG=780, TMAX=543, TMIN=587. Measured 59,655 populated day slots and 22,526 -9999 slots including calendar padding. These are not independent batches or uniformly complete station-days.
- Global status: 3.35-upd-2026101517, last full reprocessing 3.35-por-2026100923. Station history ends August 2025; global version and station file were separate HTTPS captures, not a transactional snapshot.
- NCEI [copyright policy](https://data.ngdc.noaa.gov/ngdcinfo/privacy.html) and dataset-specific citation/use constraints are captured; no blanket claim that all third-party NOAA inputs carry CC0.
- Major limitations:
  - Station metadata is current, not an historical location crosswalk
  - Station observations do not measure batch exposure or contamination
  - Quality flags, missing sentinels, reporting lags and retrospective revisions must be retained
  - A current archive is not a historical availability-time snapshot
  - The acquired station file ends 2025-08 although the global version status is 2026-10; global version is not station coverage or proof of a transactional snapshot
  - 31-day slots include invalid calendar days as -9999 padding; not all slots are observations
  - TMIN/TMAX/TAVG are tenths Celsius and PRCP tenths mm in raw .dly; other elements have distinct units
  - Nonblank quality flags need exclusion/review in M2; blanks do not prove perfect measurements
  - One station is not national coverage, a farm location, or an FSIS weather join
  - Station-month counts differ by element; earliest/latest month is not continuous daily completeness
  - Downloaded global station inventory contains UTF-8 station names; .dly weather values are ASCII

| Filename / local immutable path | Role | Bytes | SHA-256 | Actual retrieval time (UTC) |
| --- | --- | ---: | --- | --- |
| [ghcnd-stations.txt](../data/raw/noaa/sha256/428eabc955883187935bce283766d5646e3ed7484b92eb0803874c0e8dd9b342/ghcnd-stations.txt)<br>`data/raw/noaa/sha256/428eabc955883187935bce283766d5646e3ed7484b92eb0803874c0e8dd9b342/ghcnd-stations.txt` | station_metadata | 11,441,354 | `428eabc955883187935bce283766d5646e3ed7484b92eb0803874c0e8dd9b342` | 2026-10-17T05:55:51.729577+00:00 |
| [readme.txt](../data/raw/noaa/sha256/0e4e6f0e6947cf1add884c328a01760f31c56ef5fb86b85ed57dd5dc4c4aeaa6/readme.txt)<br>`data/raw/noaa/sha256/0e4e6f0e6947cf1add884c328a01760f31c56ef5fb86b85ed57dd5dc4c4aeaa6/readme.txt` | documentation | 29,587 | `0e4e6f0e6947cf1add884c328a01760f31c56ef5fb86b85ed57dd5dc4c4aeaa6` | 2026-10-17T05:55:48.222051+00:00 |
| [ghcnd-version.txt](../data/raw/noaa/sha256/af43ea47247547b0905b10a88cf70d7d99a04120dd29cd0e8f4487457a608cef/ghcnd-version.txt)<br>`data/raw/noaa/sha256/af43ea47247547b0905b10a88cf70d7d99a04120dd29cd0e8f4487457a608cef/ghcnd-version.txt` | release_metadata | 270 | `af43ea47247547b0905b10a88cf70d7d99a04120dd29cd0e8f4487457a608cef` | 2026-10-17T05:55:47.997985+00:00 |
| [C00861.html](../data/raw/noaa/sha256/48c36b6d4d9ebe2ad523cb20c634372c25a14c89fc1608743d6038638c61d5a0/C00861.html)<br>`data/raw/noaa/sha256/48c36b6d4d9ebe2ad523cb20c634372c25a14c89fc1608743d6038638c61d5a0/C00861.html` | documentation | 53,716 | `48c36b6d4d9ebe2ad523cb20c634372c25a14c89fc1608743d6038638c61d5a0` | 2026-10-17T05:55:48.719235+00:00 |
| [privacy.html](../data/raw/noaa/sha256/472f577c9f53d5f54782f71a9e6a110b694b9e8b4fd33fcb26a4bc4e6417e999/privacy.html)<br>`data/raw/noaa/sha256/472f577c9f53d5f54782f71a9e6a110b694b9e8b4fd33fcb26a4bc4e6417e999/privacy.html` | license_evidence | 19,821 | `472f577c9f53d5f54782f71a9e6a110b694b9e8b4fd33fcb26a4bc4e6417e999` | 2026-10-17T05:55:49.230594+00:00 |
| [MYM00048647.dly](../data/raw/noaa/sha256/66f1bdd365da92a90f5fe4f74347f9988c09bc09eeadeff8090f031f8f75ee24/MYM00048647.dly)<br>`data/raw/noaa/sha256/66f1bdd365da92a90f5fe4f74347f9988c09bc09eeadeff8090f031f8f75ee24/MYM00048647.dly` | data | 715,770 | `66f1bdd365da92a90f5fe4f74347f9988c09bc09eeadeff8090f031f8f75ee24` | 2026-10-17T05:56:38.000203+00:00 |

## OpenDOSM state crops

- Official publisher: Department of Statistics Malaysia; Department of Agriculture; Ministry of Agriculture and Food Security.
- Canonical source: [https://open.dosm.gov.my/data-catalogue/crops_state](https://open.dosm.gov.my/data-catalogue/crops_state).
- Acquisition: **acquired**. Scope: Full publisher CSV; annual aggregate table retained separately.
- License: CC-BY-4.0.
- Release/version: Rolling publisher CSV; version pinned by content hash.
- Measured count: 1,584 raw records.
- Row granularity: year x state/country x crop type.
- Time coverage: ['2014-01-01', '2024-01-01'].
- Geography: Malaysia; state/district names and national aggregates where present.
- Available identifiers: state, crop_type.
- Available timestamps: date (annual reference year, not publication instant).
- Useful fields / schema: state, date, crop_type, planted_area, production.
- Possible target: None: context/history only, not safe-versus-contaminated truth.
- Intended role/domain: `EXTERNAL_CONTEXT_SOURCE` / `CONTEXT_ONLY`.
- M2 eligible: **Yes**. Gates: license_known=true; provenance_confirmed=true; raw_data_present_and_hash_pinned=true; row_granularity_understood=true; schema_issues_documented=true; schema_review_passed=true.
- License CC BY 4.0 is explicitly declared on the captured source catalog; attribute DOSM/DOA/MAFS and retain the canonical link. Production is metric tonnes; planted area is hectares. Reference dates are annual and must not stand in for publication dates.
- Major limitations:
  - Annual reference date 01-01 is not publication/availability date
  - State/country totals and district/crop breakdowns can overlap; do not sum or join without grain review
  - Agricultural production/area does not label food safety; no justified link to US FSIS samples
  - Reporting lag, absent zero-activity districts, rounding and district definitions require review

| Filename / local immutable path | Role | Bytes | SHA-256 | Actual retrieval time (UTC) |
| --- | --- | ---: | --- | --- |
| [crops_state.csv](../data/raw/opendosm/sha256/b977d8ff61c536909f8131374de484bd1d0cb2d37935c875018b1b89577a849b/crops_state.csv)<br>`data/raw/opendosm/sha256/b977d8ff61c536909f8131374de484bd1d0cb2d37935c875018b1b89577a849b/crops_state.csv` | data | 68,546 | `b977d8ff61c536909f8131374de484bd1d0cb2d37935c875018b1b89577a849b` | 2026-10-17T05:55:52.137738+00:00 |
| [crops_state.html](../data/raw/opendosm/sha256/f5d90d4b1404fb01abbf3d4d775bc62e682d9e699df4e8120da09fab7a217d5c/crops_state.html)<br>`data/raw/opendosm/sha256/f5d90d4b1404fb01abbf3d4d775bc62e682d9e699df4e8120da09fab7a217d5c/crops_state.html` | license_and_dictionary_evidence | 106,748 | `f5d90d4b1404fb01abbf3d4d775bc62e682d9e699df4e8120da09fab7a217d5c` | 2026-10-17T05:55:52.313171+00:00 |

## OpenDOSM district crop production

- Official publisher: Department of Statistics Malaysia; Department of Agriculture; Ministry of Agriculture and Food Security.
- Canonical source: [https://open.dosm.gov.my/data-catalogue/crops_district_production](https://open.dosm.gov.my/data-catalogue/crops_district_production).
- Acquisition: **acquired**. Scope: Full publisher CSV; annual aggregate table retained separately.
- License: CC-BY-4.0.
- Release/version: Rolling publisher CSV; version pinned by content hash.
- Measured count: 11,002 raw records.
- Row granularity: year x state x district x crop type x species.
- Time coverage: ['2017-01-01', '2017-01-01'].
- Geography: Malaysia; state/district names and national aggregates where present.
- Available identifiers: state, district, crop_type, crop_species.
- Available timestamps: date (annual reference year, not publication instant).
- Useful fields / schema: date, state, district, crop_type, crop_species, production.
- Possible target: None: context/history only, not safe-versus-contaminated truth.
- Intended role/domain: `EXTERNAL_CONTEXT_SOURCE` / `CONTEXT_ONLY`.
- M2 eligible: **Yes**. Gates: license_known=true; provenance_confirmed=true; raw_data_present_and_hash_pinned=true; row_granularity_understood=true; schema_issues_documented=true; schema_review_passed=true.
- License CC BY 4.0 is explicitly declared on the captured source catalog; attribute DOSM/DOA/MAFS and retain the canonical link. Production is metric tonnes; planted area is hectares. Reference dates are annual and must not stand in for publication dates.
- Major limitations:
  - Annual reference date 01-01 is not publication/availability date
  - State/country totals and district/crop breakdowns can overlap; do not sum or join without grain review
  - Agricultural production/area does not label food safety; no justified link to US FSIS samples
  - Reporting lag, absent zero-activity districts, rounding and district definitions require review

| Filename / local immutable path | Role | Bytes | SHA-256 | Actual retrieval time (UTC) |
| --- | --- | ---: | --- | --- |
| [crops_district_production.csv](../data/raw/opendosm/sha256/d3bdf3a710f4635214f3191deb6970849e9f8b623bae43b3de823bfe802449cd/crops_district_production.csv)<br>`data/raw/opendosm/sha256/d3bdf3a710f4635214f3191deb6970849e9f8b623bae43b3de823bfe802449cd/crops_district_production.csv` | data | 567,921 | `d3bdf3a710f4635214f3191deb6970849e9f8b623bae43b3de823bfe802449cd` | 2026-10-17T05:55:52.598252+00:00 |
| [crops_district_production.html](../data/raw/opendosm/sha256/90f565daeeec929a06eb4e178441d0675fdd0fbebbda944b52b658764f297fee/crops_district_production.html)<br>`data/raw/opendosm/sha256/90f565daeeec929a06eb4e178441d0675fdd0fbebbda944b52b658764f297fee/crops_district_production.html` | license_and_dictionary_evidence | 115,273 | `90f565daeeec929a06eb4e178441d0675fdd0fbebbda944b52b658764f297fee` | 2026-10-17T05:55:52.732970+00:00 |

## OpenDOSM district crop planted area

- Official publisher: Department of Statistics Malaysia; Department of Agriculture; Ministry of Agriculture and Food Security.
- Canonical source: [https://open.dosm.gov.my/data-catalogue/crops_district_area](https://open.dosm.gov.my/data-catalogue/crops_district_area).
- Acquisition: **acquired**. Scope: Full publisher CSV; annual aggregate table retained separately.
- License: CC-BY-4.0.
- Release/version: Rolling publisher CSV; version pinned by content hash.
- Measured count: 10,555 raw records.
- Row granularity: year x state x district x crop type x species.
- Time coverage: ['2017-01-01', '2017-01-01'].
- Geography: Malaysia; state/district names and national aggregates where present.
- Available identifiers: state, district, crop_type, crop_species.
- Available timestamps: date (annual reference year, not publication instant).
- Useful fields / schema: date, state, district, crop_type, crop_species, planted_area.
- Possible target: None: context/history only, not safe-versus-contaminated truth.
- Intended role/domain: `EXTERNAL_CONTEXT_SOURCE` / `CONTEXT_ONLY`.
- M2 eligible: **Yes**. Gates: license_known=true; provenance_confirmed=true; raw_data_present_and_hash_pinned=true; row_granularity_understood=true; schema_issues_documented=true; schema_review_passed=true.
- License CC BY 4.0 is explicitly declared on the captured source catalog; attribute DOSM/DOA/MAFS and retain the canonical link. Production is metric tonnes; planted area is hectares. Reference dates are annual and must not stand in for publication dates.
- Major limitations:
  - Annual reference date 01-01 is not publication/availability date
  - State/country totals and district/crop breakdowns can overlap; do not sum or join without grain review
  - Agricultural production/area does not label food safety; no justified link to US FSIS samples
  - Reporting lag, absent zero-activity districts, rounding and district definitions require review

| Filename / local immutable path | Role | Bytes | SHA-256 | Actual retrieval time (UTC) |
| --- | --- | ---: | --- | --- |
| [crops_district_area.csv](../data/raw/opendosm/sha256/10e71cb5da3471b92ecf20d7ac0d74c3be3e403b226086307fefa808b4b7e672/crops_district_area.csv)<br>`data/raw/opendosm/sha256/10e71cb5da3471b92ecf20d7ac0d74c3be3e403b226086307fefa808b4b7e672/crops_district_area.csv` | data | 542,038 | `10e71cb5da3471b92ecf20d7ac0d74c3be3e403b226086307fefa808b4b7e672` | 2026-10-17T05:55:52.943510+00:00 |
| [crops_district_area.html](../data/raw/opendosm/sha256/2b93292c7c60d6712557c4976087f0f4b84ede81adc45dd06fb32ccab36b9ecf/crops_district_area.html)<br>`data/raw/opendosm/sha256/2b93292c7c60d6712557c4976087f0f4b84ede81adc45dd06fb32ccab36b9ecf/crops_district_area.html` | license_and_dictionary_evidence | 115,303 | `2b93292c7c60d6712557c4976087f0f4b84ede81adc45dd06fb32ccab36b9ecf` | 2026-10-17T05:55:53.003432+00:00 |

## USDA FSIS raw poultry

- Official publisher: USDA FSIS.
- Canonical source: [https://catalog.data.gov/dataset/fsis-laboratory-sampling-data-raw-poultry-sampling](https://catalog.data.gov/dataset/fsis-laboratory-sampling-data-raw-poultry-sampling).
- Acquisition: **official source confirmed, raw file not yet acquired**. Scope: No sample acquisition attempted; manual intake unchanged.
- License: CC0-1.0 (catalog declaration).
- Release/version: Sample release unknown; catalog dates are not sample-release dates.
- Measured count: Unknown; no data artifact acquired.
- Row granularity: Pending actual official raw file; documentation alone does not establish observed granularity.
- Time coverage: Unknown for raw records; no data file.
- Geography: Not observed in actual rows; pending data file.
- Available identifiers: Pending actual file.
- Available timestamps: Pending actual file.
- Useful fields / schema: Pending actual file; no field list inferred from catalog.
- Possible target: None for contextual sources; FSIS raw outcome vocabulary remains pending.
- Intended role/domain: `DIRECT_LABEL_SOURCE` / `BIOLOGICAL`.
- M2 eligible: **No**. Gates: license_known=true; provenance_confirmed=true; raw_data_present_and_hash_pinned=false; row_granularity_understood=false; schema_issues_documented=false; schema_review_passed=false.
- Raw sample keys, actual filename, assay codes, dictionary, counts and selected chicken-parts/Salmonella cohort remain pending. Existing catalog metadata is source evidence only. No new FSIS acquisition attempted.
- Manual intake remains `data/raw/fsis/incoming/<publisher-original-filename>.json` or `.csv`; matching actual documentation under `incoming/docs/`. These are documented conventions, not existing official file names. See [manual intake](../data/raw/fsis/README.md).
- Major limitations:
  - Raw sample file and matching dictionary pending; no schema or counts known

| Filename / local immutable path | Role | Bytes | SHA-256 | Actual retrieval time (UTC) |
| --- | --- | ---: | --- | --- |
| [catalog.html](../data/raw/fsis/sha256/ce9ab489a207ae0faa1aaaf80a6a31318c4f118d81af4a2c8839f2223c4a4ce3/catalog.html)<br>`data/raw/fsis/sha256/ce9ab489a207ae0faa1aaaf80a6a31318c4f118d81af4a2c8839f2223c4a4ce3/catalog.html` | authoritative_catalog_and_license_evidence | 123,843 | `ce9ab489a207ae0faa1aaaf80a6a31318c4f118d81af4a2c8839f2223c4a4ce3` | 2026-10-17T05:39:59.722602+00:00 |
| [catalog_metadata.json](../data/raw/fsis/sha256/e8f3d9d7641f8109eab5405de93e833f573ed349e13266f1b03e71058338c3a0/catalog_metadata.json)<br>`data/raw/fsis/sha256/e8f3d9d7641f8109eab5405de93e833f573ed349e13266f1b03e71058338c3a0/catalog_metadata.json` | authoritative_catalog_metadata | 1,581 | `e8f3d9d7641f8109eab5405de93e833f573ed349e13266f1b03e71058338c3a0` | 2026-10-17T05:40:00.232526+00:00 |

**No data artifact is present for this source.** The above are catalog/documentation artifacts only; their presence cannot pass the raw-data gate.

---

## Historical M0 inventory (pre-acquisition evidence only)

The following audit is retained for provenance; its old priorities, acquisition/license unknowns and evidence labels are superseded by the M1 section above.

# Dataset inventory — M0, 2026-10-17

Evidence states: **LOCAL** = measured from repository bytes; **PUBLISHER** = primary-source metadata reviewed, files not downloaded; **UNVERIFIED** = unknown until file/dictionary inspection. Counts marked unknown are not zero. No external source was ingested in M0. Licenses must accompany the exact acquired release; public accessibility alone is not a license.

## M1 amendment — 2026-10-17

Current FSIS state: **official source confirmed, raw file not yet acquired**. The [source-status record](m1_fsis_source_status.json) confirms that the saved authoritative catalog contains no sample field descriptions/schema. FSIS data dictionary, actual filename, raw sample keys and assay-code counts are pending. The documented manual intake pattern is `data/raw/fsis/incoming/<publisher-original-filename>.json` or `.csv`, with applicable separate official documents under `incoming/docs/`; these paths describe conventions and do not assert any local sample file exists.

The entries below preserve the M0 audit. M1 has now captured the authoritative [Data.gov FSIS catalog](https://catalog.data.gov/dataset/fsis-laboratory-sampling-data-raw-poultry-sampling) and raw metadata: identifier `usda-fsis-105`, CC0 declaration, and official FSIS resource URL. This resolves the catalog-level FSIS license uncertainty; actual sample rows, current dictionary and release schema remain uninspected because automated FSIS resource access returns HTTP 403 in this session. This does not imply the dataset is unavailable. Official manual JSON/CSV intake is implemented.

The existing openFDA archive matches a newly downloaded official archive by SHA-256, and its extracted JSON matches the registered local JSON. Official download metadata reports export 2026-10-14 and 29,485 records. The official field dictionary and license page are captured as raw evidence. Original local acquisition time remains unknown. No FSIS/openFDA merge or label generation has occurred. Full evidence and commands: [M1 report](m1_ingestion_report.md).

## Summary and priority

| Dataset | Evidence | Hazard domain | Intended role | Acquisition priority |
| --- | --- | --- | --- | --- |
| USDA FSIS laboratory sampling | PUBLISHER | Biological | Candidate supervised training/temporal validation; previous-test histories | 1: one raw-poultry/pathogen/program cohort |
| openFDA food enforcement | LOCAL + PUBLISHER | Mixed incident context | Historical recall context and source audit; not lab labels | 1: register existing snapshot separately |
| Bulk milk tank performance | PUBLISHER | Microbial quality/spoilage | Candidate within-farm quality experiment, subject to actual lab files | 2: feasibility inspection |
| Paneer storage | PUBLISHER | Microbial quality/spoilage | Candidate controlled-storage experiment | 2: feasibility inspection |
| Beef electronic nose/freshness | PUBLISHER | Spoilage/quality | Separate sensor benchmark; independent-run limitations | 2: alternative pilot |
| USDA PDP | PUBLISHER | Chemical | Separate sample×analyte experiment; explicit exceedance definition | 3 |
| FDA inspections | PUBLISHER | Facility compliance context | Historical enrichment if facility crosswalk and availability exist | Conditional |
| EU RASFF | PUBLISHER | Biological/chemical/other notification context | Country/commodity/hazard incident history | Conditional |
| NOAA GHCN-Daily | PUBLISHER | Environment context | Geotemporal enrichment when actual source location is known | Conditional |
| OpenDOSM crop production | PUBLISHER | Agricultural context | Malaysia district/crop context only | Low; no US-FSIS linkage |
| Fruit cold storage | PUBLISHER | Environmental condition proxy | Separate condition-classification benchmark only | Low; not contamination validation |

## 1. USDA FSIS Laboratory Sampling Data

- Source: [FSIS laboratory sampling](https://www.fsis.usda.gov/science-data/data-sets-visualizations/laboratory-sampling-data); [raw-poultry schema changes](https://www.fsis.usda.gov/news-events/news-press-releases/constituent-update-august-18-2023).
- License: exact release/policy evidence UNVERIFIED; record before redistribution.
- Rows / columns / size / exact time range: UNVERIFIED; program-specific releases, not one universal table.
- Row granularity: sample-level program records with organism-specific results; confirm whether an export is wide or sample×assay. Geography: US FSIS-regulated establishments; exact origin/location fields UNVERIFIED.
- Labels: candidate Salmonella, Campylobacter, Listeria and STEC results depending on program. Explicit negatives, untested outcomes and method changes must be inspected.
- Useful variables: establishment, sample/program, product and organism results as documented per release. Missing or unverified: farm, shipment, full cold-chain sensors, batch identifiers and result-publication time.
- Limitations: program selection and assay changes; not population prevalence, causal source attribution or complete farm-to-retail coverage. Official page stresses reading release metadata before analysis. Direct page requests sometimes returned 403 in M0; search-indexed official metadata was available, download access remains untested.
- Domain / use: biological; conditional training, source-specific validation and prior-test history. Never pool organisms/programs without a target-specific rationale.

## 2. USDA Pesticide Data Program (PDP)

- Source: [annual databases and documentation](https://www.ams.usda.gov/datasets/pdp/pdpdata); [database search and code tables](https://apps.ams.usda.gov/pdp/).
- License: exact release reuse terms UNVERIFIED.
- Rows / columns: UNVERIFIED, several linked files per year. Size: publisher lists 2024 ZIP as 10.1 MB; not locally measured. Time: listed annual releases 1992–2024; choose a frozen year subset.
- Entity/grain: sampled commodity plus multiple analyte results and reference tables. Geography: US monitoring with origin codes; farm coordinates not established.
- Labels: residue concentrations, detection qualifiers and detection limits; `chemical_exceedance` requires a valid applicable tolerance, not merely detection.
- Useful: commodity/analyte/origin codes, concentration, LOD and code lookups subject to dictionary verification. Missing: linked transportation history, farm practices, universal safety label.
- Limitations: left-censoring, changing assay panels, residue definitions and tolerance versions. Do not treat an analyte not tested as a nondetection, or nondetection as exact zero concentration.
- Domain/use: chemical; independent training/validation task after defining limits and units. Regulatory limit retrieval and interpretation are deferred to M1/M4, not asserted here.

## 3. Dataset on Bulk Milk Tank Performance

- Source/version: [Mendeley V2, DOI 10.17632/2sw758pw38.2](https://data.mendeley.com/datasets/2sw758pw38/2), published 2024-10-17.
- License: publisher states CC BY 4.0; retain authors/version attribution.
- Rows / columns / size: UNVERIFIED per file. Publisher reports collection 2024-08-03 to 2024-10-15 at a farm in Talavera de la Reina, Spain.
- Granularity: tank sensor readings, daily meteorological observations and separate milk-quality samples according to description; exact file inventory and linking keys UNVERIFIED.
- Labels: description mentions bacteriology CFU/ml, SCC and milk quality; **presence of usable lab files is not verified**. Sensor folders visible in search metadata do not prove all described lab/weather files exist.
- Useful: temperature, agitation, weather and milk assays if present. Missing: multiple independent farms, shipment/retail lineage, tank refill/cleaning-cycle mapping and assay-availability timestamps unless files establish otherwise.
- Limitations: strong time dependence and possible single-farm/cycle confounding; cannot label every sensor reading from one sparse lab result. CFU quality is not a specific-pathogen positive label.
- Domain/use: microbial quality/spoilage; conditional source-specific experiment/validation. Reject supervised use if lab endpoints or cycle linkage are absent.

## 4. Paneer Storage Dataset

- Source/version: [Storage study data, V2, DOI 10.17632/rd9dmr54xx.2](https://data.mendeley.com/datasets/rd9dmr54xx/2), published 2026-02-17.
- License: CC BY 4.0 per publisher.
- Rows / columns / actual timestamps: UNVERIFIED. Publisher file listings: `20241118 DataLog.csv` (67.1 KB) and `20241230 Testing Data.xlsx` (28.8 KB), not locally measured. Description reports a thirteen-day device study; filenames do not establish paired sampling dates.
- Grain: high-frequency environmental log plus microbiological/physical observations at storage sampling times. Exact treatment/run/replicate/specimen identities require inspection.
- Geography: Indian contributor institutions; actual experimental coordinates UNVERIFIED.
- Labels/useful variables: microbiological and sensory measurements, pH, moisture; temperature/RH log; verify assay units and biological replication.
- Missing: supply-chain/facility identifiers, independent production runs, direct pathogen labels unless documented.
- Limitations: small controlled experiment; published storage conditions are not universal safe limits. No cross-file join until experimental correspondence is demonstrated.
- Domain/use: separate spoilage/quality training feasibility and within-experiment validation; not whole-chain contamination calibration.

## 5. Beef Quality / Freshness Dataset

- Candidate source: [electronic nose beef dataset V1, DOI 10.17632/mwmhh766fc.1](https://data.mendeley.com/datasets/mwmhh766fc/1); [V1/V2 comparison](https://data.mendeley.com/datasets/compare/mwmhh766fc?new=2&old=1). V2 exists; select and pin an inspected version in M1.
- License: CC BY 4.0 per V1 publisher metadata.
- Rows/columns: publisher V1 reports 4,553 observations and lists 15 fields; not locally verified. Size: UNVERIFIED. Time: elapsed minutes, about 75 hours; calendar period/location UNVERIFIED.
- Grain: sequential e-nose measurements of a beef specimen/experiment, not thousands of independent batches.
- Labels: TVC and excellent/good/acceptable/spoiled class. Useful: ten gas sensors, temperature, humidity, elapsed time.
- Missing: verified independent runs, farm/factory/shipment IDs, exact TVC transformation/units and class construction.
- Limitations: autocorrelation, run memorization, sensor drift; class may be derived from TVC. Exclude TVC from inputs when predicting that derived class. Random row splits are misleading.
- Domain/use: separate spoilage/quality benchmark; independent-run generalization remains unverified.

## 6. Fruit Cold-Storage Dataset

- Source/version: [Mendeley V1, DOI 10.17632/czz68d9fwj.1](https://data.mendeley.com/datasets/czz68d9fwj/1), published 2025-09-29.
- License: publisher states CC BY 4.0.
- Publisher-reported rows / columns / size: 10,996 / 6 / 376 KB CSV; not locally verified. Observation dates and exact collection geography UNVERIFIED; project context is Uganda.
- Grain: fruit-type/environment-condition record; timestamps, storage-run and specimen keys are not among the six listed columns.
- Target: `Class` Good/Bad describes optimal/suboptimal storage conditions, **not a laboratory-confirmed spoilage or pathogen outcome**.
- Useful original columns: `Fruit`, `Temp` (°C), `Humid` (%RH), `Light` (lux), `CO2` (ppm), `Class`.
- Missing: CFU/TVC, assays, exposure duration, batch/run identity, temporal order and complete label derivation.
- Limitations: a model may reproduce a labeling rule rather than biological risk. Cannot construct temporal features or splits from absent timestamps.
- Domain/use: cold-storage condition proxy benchmark only; do not use as contamination training or validation. No direct joining to FSIS by fruit/product label.

## 7. FDA Inspection Classification Data

- Source: [FDA inspection classification database](https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/inspection-classification-database).
- License / rows / columns / size / exact export range: UNVERIFIED for an acquired dashboard export.
- Grain: inspection/project-area final classification, not necessarily one row per physical inspection or food sample. Geography: FDA-inspected facilities; export scope needs verification.
- Labels: NAI, VAI, OAI are compliance classifications, not contamination-test labels.
- Useful: stable facility identifier if present, inspection dates, project area and classification. Missing: FSIS facility crosswalk, specimen outcomes, cold-chain sensors and exact classification-publication history.
- Limitations: official page says coverage is incomplete and some postings wait for enforcement decisions. A classification may become known well after inspection close. OAI cannot simply be recoded as contaminated; VAI should not silently be counted as a failed laboratory test.
- Domain/use: historical compliance enrichment only, once entity and availability mapping is defensible. Unique inspection counting must avoid project-area duplicates.

## 8. openFDA Food Recall Enforcement Data

- Source: [official bulk-download documentation](https://open.fda.gov/apis/food/enforcement/download/); [FDA enforcement definitions](https://www.fda.gov/safety/enforcement-reports/enforcement-report-information-and-definitions).
- License: [openFDA licensing](https://open.fda.gov/license/) states generally public domain/CC0 unless excepted, subject to service terms. Snapshot embeds this license URL; original download URL/time and authenticity are not verified.
- LOCAL: `tmp/food-enforcement-0001-of-0001.json`, **29,485 rows; 25 top-level fields; 39,906,111 bytes (38.06 MiB)**. Matching ZIP 5,858,570 bytes (5.59 MiB). Row count matches embedded metadata. SHA-256 and field-level measurements: [audit JSON](openfda_snapshot_audit.json).
- Grain: product-recall enforcement record, grouped into **7,907 event IDs**; not a batch/sample cohort. `recall_number`: 29,484 distinct populated values, one missing.
- Time: `report_date` 2012-06-20–2026-10-07; embedded `last_updated` 2026-10-14. One initiation date parses to year 0212; do not silently repair it. Initiation, reporting, classification and termination dates have different meanings.
- Geography: 32 firm-country strings; 29,039 records list United States. Firm location/distribution text is not farm origin or a verified destination list.
- Labels: recall classification/status/reason exist; no tested-negative samples or laboratory contamination labels. Useful context: recalling firm, product description, reason, event ID, report date and location strings. No validated farm/supplier IDs, sensors, manufacturing dates, complete assay denominator or FEI crosswalk. All 29,485 nested `openfda` objects are empty.
- Limitations: selected enforcement events, outcome narratives and changing statuses; repeat products within one event; imperfect source dates; snapshot revisions prevent naïve historical reconstruction.
- Domain/use: mixed-hazard historical context, incident research and risk-history calculation after entity/time validation. Not standalone contamination training or independent safety validation. Class I/II/III counts are enforcement severity, not pathogen class balance.

## 9. EU RASFF

- Source: [official RASFF Window public-portal/API guide](https://webgate.ec.europa.eu/imsoc-guide/rasff-window-help/en/public-portal/homepage.html).
- License / exact downloaded rows / columns / size: UNVERIFIED; consult the specific open-data API terms/export in M1/M6.
- Time: current public guide describes notifications from 2020 onward; older coverage must not be assumed. Geography: European notification system with product-origin information, not a random worldwide food survey.
- Grain: notification/hazard/product/country relationships and possible follow-ups; inspect export cardinality.
- Targets: reported hazards/alerts, not a representative positive/negative sample label.
- Useful: commodity, origin, hazard, notification date and notification identifier where exported. Missing: non-notified denominator, local batch links, comprehensive lab outcomes and publication/revision history.
- Limitations: surveillance intensity, selection and multiple notification updates. Country×commodity counts are contextual incident frequency, not contamination prevalence.
- Domain/use: mixed-hazard historical/contextual enrichment only with origin mapping, harmonized categories and availability cutoffs. Never merge individual incidents into unrelated samples.

## 10. NOAA Historical Weather

- Source: [NCEI service API documentation](https://www.ncei.noaa.gov/support/access-data-service-api-user-documentation); [GHCN-Daily format/units/quality flags](https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme.txt).
- License: retain NOAA data-use/citation policy for the selected product; release terms not captured in M0. Rows/columns/size/time range: UNVERIFIED until station/date subset chosen.
- Grain: station×day×element (or wide station-day API output). Geography: station network coverage varies; exact farm proximity and Malaysian station completeness unverified.
- Labels: none for food contamination. Useful: precipitation, temperatures, station coordinates and quality flags; API and raw units differ and must be recorded.
- Missing: food entities, cold-chain measurements, guaranteed same-day availability and uniform station coverage.
- Limitations: daily aggregates are incomplete until day close; observation intervals/timezones, missing flags, station selection and historical revisions matter. Ambient temperature is not measured product temperature.
- Domain/use: environmental enrichment only when genuine observation location/date is known. Use prior completed, available days; report window coverage instead of treating missing rain as zero.

## 11. Malaysia OpenDOSM Agricultural Data

- Specific source: [crop production by district](https://open.dosm.gov.my/data-catalogue/crops_district_production), with official CSV/Parquet links.
- License: CC BY 4.0 per catalogue.
- Publisher states >10,000 rows; exact rows/size unverified. Six documented columns: `date`, `state`, `district`, `crop_type`, `crop_species`, `production`. Reference coverage shown as data through 2017; earliest year unverified. Catalogue last update shown as 2023-12-31.
- Grain: annual region×crop type/species production; aggregate-region rows need filtering before district joins. Geography: Malaysia; coverage depends on agricultural activity.
- Labels: no contamination outcome. Useful: production (metric tonnes), district, state and crop context. Missing: food samples, farm IDs, assays, daily conditions and supply-chain linkage.
- Limitations: annual dates use January 1 as a reference-year marker, not publication time. Crop output is not biological risk; ecological and publication-lag errors would invalidate naïve joins.
- Domain/use: optional Malaysian regional context for appropriately located crop observations, not sample-level training labels and not enrichment for US establishments.

## M0 unresolved acquisition gates

Exact artifact URLs, terms and dictionaries for FSIS/FDA/RASFF/NOAA; file contents for all ten nonlocal sources; negative-label and assay vocabularies; milk lab-file availability; paneer run linkage; beef TVC units and independent runs; fruit label derivation; actual source release times; s390x dependency installation. These unknowns do not block completion of the M0 inventory; they block unsupported downstream use.
