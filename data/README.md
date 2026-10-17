# Data lifecycle

M1 captures immutable source bytes and receipts. No cleaned tables or training tables exist yet.

| Directory | Contract |
| --- | --- |
| `raw/` | Immutable, versioned source bytes and download manifests; never edit in place. |
| `external/` | Immutable supporting weather, inspections, recalls and lookup snapshots with provenance. |
| `interim/` | Source-specific parsed/standardized tables, exclusions and quality reports. |
| `processed/` | Validated, versioned, experiment-specific Parquet tables and split manifests. |

The existing `tmp/food-enforcement-0001-of-0001.json` and ZIP remain in place. M1 copies them unchanged into `external/openfda/sha256/` and compares the ZIP with a newly retrieved official archive. The successful official byte match is recorded; original local acquisition time remains unknown.

FSIS status: **official source confirmed, raw file not yet acquired**. Manual intake is ready at `raw/fsis/incoming/<publisher-original-filename>.json` or `.csv`; actual separate documentation belongs in `raw/fsis/incoming/docs/`. These are conventions, not existing sample filenames. The sample dictionary is pending because preserved official catalog metadata does not supply field descriptions or a sample schema. Read [manual intake instructions](raw/fsis/README.md). Direct download and manual intake share the same inspector, with checksum, provenance, official metadata, actual schema and dictionary review gates before a selected cohort is claimed. Unofficial mirrors are not used as a fallback.

New raw artifact bytes under `raw/fsis/` and `external/openfda/` are ignored by Git. Versioned JSON receipts under `manifests/` are retained for provenance and replay. Historical failed attempts remain as evidence; later successful receipts do not rewrite them. The user's `tmp/` ignore rule and previously staged raw JSON are preserved. Future generated interim/processed table exclusions will be added when those outputs exist.

Each manifest records original/canonical source references, source/config versions, hashes, sizes, available HTTP metadata, actual download/import timestamps, failed attempts and source inspections. `retrieved_at=null` means original acquisition is unknown; `imported_at` records local capture. Neither catalog modification nor source `last_updated` is a result-availability timestamp.

`python -m tracefront_data.ingest verify MANIFEST` checks captured artifact bytes offline. `restore MANIFEST` restores missing bytes with expected hashes pinned and writes a separate restoration receipt; upstream drift fails. Do not edit files under `sha256/` or existing manifests. A successful integrity check does not imply that pending source acquisition or cohort review is complete.

Planned processed paths: `biological/<version>/observations.parquet`, `chemical/<version>/observations.parquet`, and `spoilage/<dataset>/<version>/observations.parquet`. A universal `training_dataset.parquet` would conceal incompatible targets and row units. Features, labels, metadata and split manifests should be distinguishable at handoff.
