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
