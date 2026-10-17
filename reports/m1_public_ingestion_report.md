# M1 — Expanded official-source ingestion

**Milestone status: PARTIAL.** Four source families are acquired and six source entries pass the M2 intake gates. FSIS and FDA inspection records remain pending independently. No M2 cleaning, units/timestamp normalization, labels, feature engineering, enrichment joins or model training were performed.

## Evidence and reproducibility

Frozen receipt: [data/manifests/20261017T060123145416Z-29c44de9.json](../data/manifests/20261017T060123145416Z-29c44de9.json); created 2026-10-17T06:01:23.145495+00:00. [Source manifest](m1_source_manifest.json) records all raw artifacts, prior original retrieval/import clocks, actual source URLs/HTTP headers, observed fields/grain/codes and M2 gates. [Inventory](dataset_inventory.md) provides the readable detail. Config and pipeline code hashes are frozen in the receipt; current inspection code hashes are separately pinned in the derived report. License review notes and per-release dictionary mapping are part of the config snapshot.

28 captured artifact records pass size/SHA-256 verification; the openFDA local ZIP and official comparison ZIP intentionally reference the same immutable bytes. Distinguish record count from unique files. Raw files are read-only and content-addressed; these are tamper-detectable filesystem conventions, not storage-level WORM guarantees. All seven PDP ZIP members were streamed for SHA-256 and CRC validation. No publisher-issued cryptographic signature/checksum was obtained.

Exact publishers' data basenames are preserved. Catalog pages/API indexes without a useful source basename have explicit local evidence labels such as `pdpdata.html` or `C00861.html`; this does not rename a published data file. Original JSON/CSV/ZIP/.dly/PDF/XLSX/MDB bytes remain unchanged. No Access/Excel application is needed. New raw source directories are Git-ignored; backup them with receipts because upstream content may be removed or revised. Hash-pinned restoration detects drift; it cannot guarantee old publisher bytes remain hosted.

## Sources attempted

| Source | State | Reason / next gate |
| --- | --- | --- |
| USDA PDP 2024 | acquired | 2024 ZIP + annual dictionary/reference members acquired; policy browser-reviewed; raw policy HTML blocked. Sample/result counts and keys inspected. |
| openFDA Food Enforcement | acquired | Existing full snapshot matches official ZIP; JSON member equals local bytes. Retained as historical context. |
| FDA inspection classifications | pending | Documentation/license acquired. Absolute and dashboard-relative XLSX URLs returned 404; official API requires credentials. |
| NOAA GHCN-Daily Malaysian station pilot | acquired | Verified one Malaysian station and captured its entire available .dly file plus stations/readme/version/policy/catalog. |
| OpenDOSM state crops | acquired | Full official CSV + license/dictionary catalog acquired, 2014–2024. |
| OpenDOSM district crop production | acquired | Full official CSV + license/dictionary catalog acquired, 2017 only. |
| OpenDOSM district crop planted area | acquired | Full official CSV + license/dictionary catalog acquired, 2017 only. |
| USDA FSIS raw poultry | pending | official source confirmed, raw file not yet acquired. Manual/direct intake unchanged; catalog only. |

## Primary raw artifact summary

| Source / filename | Bytes | Locally computed SHA-256 | Measured record counts |
| --- | ---: | --- | --- |
| USDA PDP 2024 / `2024PDPDatabase.zip` | 10,600,875 | `de916ba119f8d6dd5a4d5596c69b00c476fceeb31a96b1389dd005031c9c4d79` | 9,872 sample records; 2,872,073 analytical results |
| openFDA Food Enforcement / `food-enforcement-0001-of-0001.json` | 39,906,111 | `02f3e7959cc732d8f1983f2b87edbbecc6d2f4959eaef50a597f640fbc513e2d` | 29,485 raw records |
| openFDA Food Enforcement / `food-enforcement-0001-of-0001.json.zip` | 5,858,570 | `7f8e2b5bd6e05e0cbf15e43860c74538ad09e1f8b07928e9c92de3ead3dac9c6` | 29,485 raw records |
| NOAA GHCN-Daily Malaysian station pilot / `MYM00048647.dly` | 715,770 | `66f1bdd365da92a90f5fe4f74347f9988c09bc09eeadeff8090f031f8f75ee24` | 2,651 raw records |
| OpenDOSM state crops / `crops_state.csv` | 68,546 | `b977d8ff61c536909f8131374de484bd1d0cb2d37935c875018b1b89577a849b` | 1,584 raw records |
| OpenDOSM district crop production / `crops_district_production.csv` | 567,921 | `d3bdf3a710f4635214f3191deb6970849e9f8b623bae43b3de823bfe802449cd` | 11,002 raw records |
| OpenDOSM district crop planted area / `crops_district_area.csv` | 542,038 | `10e71cb5da3471b92ecf20d7ac0d74c3be3e403b226086307fefa808b4b7e672` | 10,555 raw records |

Full local paths, all supporting metadata/dictionary/license artifacts and actual retrieval times appear in the inventory and source manifest. PDP embedded member sizes/hashes are in `inspection.members`; original ZIP alone is sufficient to restore those exact member bytes without normalization.

## Scientific and data findings

- PDP has 9,872 unique sample PKs and 2,872,073 analytical rows, with no orphan sample references or malformed field widths observed. Rows are sample identity and analytical results, not complete supply-chain batches. MEAN ND=2,798,390; NP=55,193; O=18,458; R=32. Their meaning comes from the embedded 2024 reference tables; NP must not be silently treated as the same analytical-quality category as ND. Unmeasured analytes are not nondetects.
- Concentration is blank for nondetect in the annual text; the search-app dictionary describes a different export representation. Preserve release-local IDs/leading zeros, blanks/spaces, raw units and methods. The reference workbook has a Tolerance sheet, but numeric and special-code tolerance values, action levels, residue definitions and effective dates need separate review. ANNOTATE X=78 is a presumptive exceedance annotation count, not 78 definitively unsafe batches. Concentration, MEAN and result annotations are outcomes and cannot be same-observation predictors.
- openFDA is product-recall enforcement history with repeated event IDs and no tested-negative denominator. Firm names/addresses are not farm coordinates or verified facility keys. A current export has retrospective status/termination updates; event dates do not establish the public availability of each field. Known missing-ID and year-0212 anomalies remain unchanged.
- NOAA rows are station/month/element with 31 day slots, missing sentinels, units and flags. The chosen station spans 1949-04 through 2025-08 with uneven coverage by element. Airport weather is not measured food exposure, and no station-to-farm mapping or weather join exists. Current archive revisions do not recreate what was available at a past prediction cutoff.
- OpenDOSM state data is 2014–2024; district data is only 2017. Area/production tables have different row counts and must remain separate. Annual reference dates are not publication dates; national/state totals, administrative changes, rounding and missing zero-activity districts need future checks. Malaysia crop aggregates cannot simply enrich US food samples by crop names.
- Inspection classifications are project-area-specific agency compliance decisions, not laboratory outcomes. FEI and FSIS establishment IDs are different namespaces; no crosswalk was assumed. FSIS fields/codes/counts remain unknown. No cold-chain experimental datasets or unofficial mirrors were ingested.

## License and provenance findings

- PDP: [USDA reuse policy](https://www.usda.gov/policies-and-links) was reviewed on 2026-10-17 and its public-domain basis/exceptions and requested attribution recorded. Automated raw HTML capture returned 403; a page snapshot remains a provenance-documentation gap. No release-specific 2024 CC0 claim is made. No protected-data notice was identified in the reviewed release dictionaries/instructions; retain exceptions and USDA attribution.
- openFDA: [official license](https://open.fda.gov/license/) captured; public-domain/CC0 basis with stated exceptions and service terms retained. Original local acquisition is unknown; official byte equality and actual comparison-download time are documented independently.
- FDA inspections: [FDA reuse policy](https://www.fda.gov/about-fda/about-website/website-policies) captured. Public-domain unless otherwise noted, credit appreciated; record acquisition remains pending, so source is not M2-eligible.
- NOAA: [NCEI copyright policy](https://data.ngdc.noaa.gov/ngdcinfo/privacy.html) captured, with public-domain US scope/explicit exceptions and dataset-specific citation/use constraints; do not assume blanket CC0 for all contributed NOAA products.
- OpenDOSM: CC BY 4.0 declared in each captured official catalog; attribute DOSM, DOA and MAFS with source URL. CSV coverage is measured rather than inferred from a chart preview.

## Commands

Run from the repository root with Python 3.11+. No third-party runtime dependency:

```bash
PYTHONPATH=src python -m tracefront_data.public_sources verify --manifest data/manifests/20261017T060123145416Z-29c44de9.json
PYTHONPATH=src python -m tracefront_data.public_sources restore --manifest data/manifests/20261017T060123145416Z-29c44de9.json
PYTHONPATH=src python -m tracefront_data.public_sources inspect --manifest data/manifests/20261017T060123145416Z-29c44de9.json
PYTHONPATH=src python -m tracefront_data.public_sources acquire
PYTHONPATH=src .venv/bin/python -m pytest -q
```

`verify` and `inspect` are offline. `restore` only downloads/imports missing captured artifacts with exact expected hashes; prior timestamps/receipts remain unchanged. A local no-op restore was exercised. Existing replay tests cover missing-file restoration with mocked HTTPS; live re-download of every frozen new artifact was not repeated. `acquire` expects the frozen store or prior restoration, revalidates reused artifacts, retries failed requests, writes a new immutable receipt and never overwrites a previous one. `--source SOURCE_ID` narrows acquisition. Corrupt preserved bytes fail rather than being replaced. The config pins reviewed PDP schema to its ZIP; a new release requires new dictionary review.

FDA pending route: use the public dashboard's official entire-dataset export when repaired, or authenticated documented POST API. API requests require `columns`, `filters`, `sort`, `sortorder`; use `rows<=5000`, 1-based `start`, and totalrecordcount. Request/response pages must be frozen consistently and inspected for food project areas, field names and repeated inspection/project-area rows. No credentials were requested or stored by this implementation; an authenticated paging client remains future M1 work. FSIS uses the existing [manual/direct intake](../data/raw/fsis/README.md), with no invented filenames.

## LinuxONE and validation

Runtime: standard Python 3.11+ only; no dependency/lock changes and no new compilation requirement. Stdlib CSV/ZIP/XML handles the PDP references. Poppler `pdftotext` was a local one-time documentation aid, not a runtime/test dependency; optional s390x package installation must use the target distribution. No s390x execution was performed. See [portability notes](linuxone_portability.md).

41 tests passed with pytest on Python 3.11.17 and unittest on Python 3.14.7. Tests cover immutable capture/checksums, corrupt/truncated inputs, path guards, source failure isolation, code and orphan-key inspection, ND blank preservation, dictionary hash drift, station UTF-8 names, weather sentinel/flag handling, all M2 gates, source replay, and existing FSIS/openFDA behavior. The new source receipt passes 28 captured-artifact integrity checks. M1 inspection measured full raw table counts and widths and PDP referential integrity; no rows were removed or values rewritten. `verify` and no-op `restore` succeeded locally. Git whitespace validation and current code/config fingerprint checks are recorded separately in the validation report.

## Remaining M1 issues and next milestone

FSIS official samples and matching dictionary remain unacquired. FDA inspection raw export/API access remains unresolved. USDA policy raw HTML snapshot is blocked even though the authoritative policy text was reviewed and recorded; a 2024-specific CC0 declaration was not obtained. Vendor cryptographic signatures/checksums were not obtained. Maintain an offline raw backup. Historical field-availability times, facility crosswalks, temporal joins, regulatory-label definitions and full source-specific quality handling remain later scientific/data gates. No training table is ready.

Eligible acquired sources may proceed to M2 after an explicit next prompt, with contextual sources kept separate and unsupported labels excluded. FSIS/FDA pending status must not force fabricated raw data or hold up source-specific cleaning of acquired sources.

Copy-ready next prompt:

> Begin M2 only for sources marked m2_eligible=true in reports/m1_source_manifest.json. Read the M1 inventory/report and verify the frozen receipt first. Implement deterministic source-specific cleaning with raw-byte preservation, rejection/missingness reports and tests. Keep PDP sample/results and tolerance interpretation under their documented grains; preserve censoring/quality distinctions and do not create a regulatory exceedance label yet. Keep openFDA, NOAA and OpenDOSM separate as history/context. Keep FSIS and FDA inspection records pending. Do not merge sources, engineer predictive features or train models.
