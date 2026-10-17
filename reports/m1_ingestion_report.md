# M1 — Source ingestion and registration

Date: 2026-10-17. **Milestone status: PARTIAL.** The ingestion/manual-intake implementation is tested and openFDA registration is verified. The official FSIS sample file and matching release dictionary have not been acquired, so actual sample-key/result-code inspection and selection of a biological cohort remain pending. Do not begin M2 biological cleaning by assuming a schema or inventing labels.

**Current FSIS state: official source confirmed, raw file not yet acquired.** [Current source-status evidence](m1_fsis_source_status.json) checks the preserved catalog against the configured dataset ID, license and official resource link. It confirms that no sample-field descriptions or sample-schema references are exposed by that saved metadata. The sample dictionary, exact official filename, keys, assay codes and cohort counts remain pending. No nonexistent local file or dictionary path is assumed, and no unofficial mirror is used.

The exact future intake convention is `data/raw/fsis/incoming/<publisher-original-filename>.json` or `.csv`; separate documentation goes under `incoming/docs/` with its actual publisher basename. These are patterns, not actual files. The local directories are created empty. The [intake instructions](../data/raw/fsis/README.md) document guarded commands, optional known origin/retrieval information and review gates. Known fields/schema in future official metadata are retained as evidence for review; catalog resource records are explicitly rejected as sample rows.

Earlier [intake-check evidence](m1_fsis_intake_check.json) records the previous metadata-only workspace scan. Its statement that no implementation changes occurred applies to that earlier check. This update adds source-state reporting, catalog/resource validation, rejection of catalog JSON as samples, and preservation of publisher filenames containing spaces. Earlier immutable capture receipts remain unchanged; their historical code/config fingerprints are retained. The current source-status report records the updated code/config hashes.

## Implemented

- `src/tracefront_data/provenance.py`: bounded HTTPS/local import, actual retrieval/import clocks, response URL/headers, SHA-256 and byte counts, atomic immutable publication, append-only manifests and offline integrity verification.
- `src/tracefront_data/ingest.py`: source-specific orchestration, official catalog checks, separate openFDA contextual registration, manual/direct FSIS intake, exact-hash restoration and restoration receipts.
- `src/tracefront_data/fsis.py`: JSON/CSV structure inspection, explicit record pointers, reviewed exact-value cohort filters, sample-key uniqueness/missingness and raw assay-code accounting. No labels/features are generated.
- `configs/ingestion_sources.json`: authoritative sources, artifact roles, local snapshot hash expectations, license references and provenance rules.
- `configs/fsis_pilot.json`: intended single-program raw chicken-parts/Salmonella pilot; **unreviewed and inactive** until actual release inspection. No guessed current FSIS field names or codes.
- `uv.lock` and `requirements-dev.lock`: pinned optional pure-Python testing tools. Runtime dependencies remain empty.

New source bytes are stored under `data/raw/fsis/sha256/` and `data/external/openfda/sha256/`, ignored by Git. Metadata receipts are retained in `data/manifests/`. The source filename and exact original bytes survive capture. Existing content is hash-checked before reuse, never overwritten; temporary files do not become complete artifacts until validated. Read-only permissions discourage edits, while manifests detect later tampering; this is application-level immutability, not a claim of WORM storage.

The existing `tmp/` JSON/ZIP and the user's staged JSON remain unchanged. No frontend/backend code was edited.

## FSIS authoritative findings

The [Data.gov entry](https://catalog.data.gov/dataset/fsis-laboratory-sampling-data-raw-poultry-sampling) and its [raw harvest record](https://catalog.data.gov/harvest_record/8bd3606e-32f0-415c-ab74-38527ec5f9aa/raw) were downloaded successfully, preserving their bytes, URLs, retrieval instants and hashes.

| Metadata item | Observed value |
| --- | --- |
| Dataset identifier | `usda-fsis-105` |
| Publisher | Food Safety and Inspection Service |
| Declared license | CC0, `https://creativecommons.org/publicdomain/zero/1.0/` |
| Official resource | `https://www.fsis.usda.gov/news-events/publications/raw-poultry-sampling` |
| Catalog issued / modified | 2023-10-13 / 2025-01-22 |
| Distribution metadata | Resource-page access URL; no direct JSON/CSV download URL in this record |
| Documented organization | Fiscal-year files; current/archived releases have different update schedules |

The catalog modification date is **not** an acquired sample release version, collection-date range or result-publication date. Both the FSIS resource page and historical Regulations.gov dictionary reference returned HTTP 403 in live acquisition. This documents automated access restrictions from this session, **not dataset unavailability**. No unofficial Kaggle/GitHub mirror was substituted.

| Required actual-release inspection | Current evidence |
| --- | --- |
| Current sample/assay row unit and sample key | Unknown; actual source file pending |
| Establishment identifier and exact project/commodity fields | Unknown for acquired release; do not activate legacy guesses |
| Positive/negative/untested/indeterminate codes and counts | Unknown; no real assay rows have been inspected |
| Matching current dictionary | Pending; historical reference must not automatically be treated as current |
| Single commodity × pathogen × sampling-program cohort | Intended pilot specified, selection not yet activated |
| Result-availability timestamps | Unverified; do not equate collection or download time with availability |

## Manual intake and cohort review

The user's approved fallback is implemented under [data/raw/fsis/](../data/raw/fsis/README.md). Place the officially downloaded fiscal-year JSON/CSV and its matching dictionary there, retain their original names, and run `ingest run` with `--fsis-file`, `--fsis-source-version` and, when separate, `--fsis-dictionary`. If known, supply the actual direct official URL through `--fsis-origin-url` and the actual original download instant through `--fsis-retrieved-at`. Unknown original retrieval remains null; import time is recorded separately. Manual origin/version is an operator assertion unless independently verified against official bytes.

Direct retrieval instead uses `--fsis-data-url` on an official FSIS host. Both paths preserve content and call the identical inspector. No downstream file-format adapter depends on whether acquisition was manual or automated.

First inspect candidate JSON record pointers and actual columns; ambiguous data/dictionary arrays require an explicit RFC 6901 pointer. Then review the exact dictionary and fill the contract's real identity/date/result columns and exact cohort filter values. For an initial raw-code inventory, a result field may be specified while `mapping_reviewed=false`; no selected cohort is then claimed. Activate only after review, pinning `reviewed_source_sha256` and confirming `dictionary_release_match_verified`. Embedded JSON documentation may be referenced with `dictionary_pointer`.

Result vocabularies are exact and source-specific. Unknown codes are reported; missing/blank values cannot be configured as positive or negative. Untested and indeterminate remain separate, and no absence of a result is converted to a negative. Duplicate/absent keys are counted without deduplicating/removing source rows. CSV input retains string IDs and leading zeros. M1 date ranges, when reported, are raw lexical ranges only; timestamp normalization is M2 work.

## openFDA registration and source verification

The local archive matches a newly retrieved archive from the [official download endpoint](https://download.open.fda.gov/food/enforcement/food-enforcement-0001-of-0001.json.zip) by SHA-256. Its ZIP member matches the registered local JSON. The [official download index](https://api.fda.gov/download.json) records export 2026-10-14 and 29,485 records. The [license page](https://open.fda.gov/license/) and [official field dictionary PDF](https://open.fda.gov/fields/foodenforcement_reference.pdf) are also captured.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Local JSON, copied unchanged | 39,906,111 | `02f3e7959cc732d8f1983f2b87edbbecc6d2f4959eaef50a597f640fbc513e2d` |
| Local ZIP and official ZIP | 5,858,570 each | `7f8e2b5bd6e05e0cbf15e43860c74538ad09e1f8b07928e9c92de3ead3dac9c6` |

Rows remain 29,485 with 25 top-level fields, at product-recall enforcement granularity. This is **context only**, not a biological/chemical/spoilage training cohort. There is no tested-negative denominator. Nothing is joined to FSIS. The successful current official byte match resolves source-copy verification; it does **not** recover the initial local acquisition time or make every current status field historically available.

## Receipts, replay and validation

Each run writes a new immutable JSON receipt containing source/config snapshots and hashes, code fingerprints, runtime architecture/Python, license evidence, acquisition status, failed HTTP attempts, sizes, SHA-256 values and inspection results. Old failed attempts remain intact. Repeated bytes share the same content-addressed file; retrieval events remain distinct records. Eight captured artifact records in a successful network run include the two identical local/official archive references, so record count is not a count of distinct physical files.

```bash
PYTHONPATH=src python -m tracefront_data.ingest run
PYTHONPATH=src python -m tracefront_data.ingest verify data/manifests/20261017T053958804059Z-a2601437.json
PYTHONPATH=src python -m tracefront_data.ingest restore data/manifests/20261017T053958804059Z-a2601437.json
```

`run` exits 2 for partial acquisition/review, 1 for fatal command errors, and 0 when acceptance gates pass. `verify` exits 0 for successful captured-byte integrity **even if acquisition remains partial**, explicitly reporting both states. `restore` restores missing files with expected hashes pinned and writes a separate timestamped receipt when it attempts acquisition. Existing corruption is rejected. A verified openFDA archive can reproduce the exact original JSON even without the original `tmp/` copy. Unknown original manual FSIS sources need their supplied file or recorded direct official URL; there is no invented fallback.

Mutable upstream content or dynamically rendered HTML may no longer match a frozen receipt. Restoration then reports hash drift rather than replacing the frozen snapshot. Share preserved raw artifacts alongside receipts when a source cannot reproduce an older byte version; no external storage/deployment service is introduced here.

Tests cover local/HTTPS intake, original-byte preservation, repeated capture, corrupt existing artifacts, path traversal, hash mismatch, truncated/oversized responses, explicit HTTP 403, timestamp provenance, immutable manifests, exact-hash replay, archive-member replay without original local files, JSON record ambiguity, CSV width/ID handling, conflicting/unknown/blank result codes, cohort filtering and source-hash/dictionary gates. All FSIS test observations are synthetic temporary fixtures, never written to research data directories or represented as official samples.

Validation performed:

- Current update: **31 tests passed** with locked pytest on Python 3.11 and stdlib unittest on Python 3.14. New coverage checks metadata-only source confirmation without sample claims, preservation of official field-description evidence when present, rejection of mismatched resource links and catalog-as-sample intake, and preservation of filenames containing spaces. All eight preserved artifact references still verify. There are no files in the manual intake directories and no sample counts have been invented.
- **27 tests passed** with the locked pytest 9.1.1 environment on Python 3.11.17; the same 27 passed with stdlib unittest on Python 3.14.7.
- The [final live receipt](../data/manifests/20261017T053958804059Z-a2601437.json) records eight captured artifact references, two explicit HTTP 403 acquisition gaps, and successful verification of all eight captured hashes/sizes. Source/config/code fingerprints and runtime are preserved in that receipt.
- CLI `verify` passed; CLI `restore` of already-present valid artifacts was a no-op with no manifest rewrite.
- An additional [real-data replay validation](m1_replay_validation.json) used the preserved official ZIP in a temporary target with no original `tmp/` files. It restored the full 39,906,111-byte JSON to the expected SHA-256, verified three raw-artifact references, made zero network calls and left the source manifest unchanged. This exercised real archived bytes, not only a synthetic fixture.
- The initial sandbox-DNS failures and subsequent successful network captures are retained as separate immutable receipts; no failed history was overwritten. The previously staged original JSON remains unchanged.

## LinuxONE/s390x and remaining scope

No new native packages are needed for M1. Optional test wheels are architecture-independent, with a hash-locked pip route for targets without uv. Local checks use Python 3.11 and 3.14 on x86_64. Actual s390x execution, target OS/Python details and future pandas/NumPy/Parquet native support remain unverified. See [portability notes](linuxone_portability.md).

No cleaning, feature engineering, merges, Parquet training table, model training or training optimization was performed. Finish M1 with the official FSIS source/dictionary and actual sample/code inspection before advancing to M2 biological processing.
