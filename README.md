# Tracefront

Real-time AI decision support for food safety incidents. See [tracefront_project_summary.md](tracefront_project_summary.md) for the full spec.

## Backend (FastAPI + PostgreSQL)

```
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # point DATABASE_URL at your Postgres instance
uvicorn app.main:app --reload
```

API docs at http://localhost:8000/docs. Tables are created automatically on startup from `app/models.py` (matches the ERD in section 14 of the project summary).

Endpoints:
- `GET /api/health`
- `GET /api/batches`, `POST /api/batches`
- `POST /api/sensor-readings`, `POST /api/lab-results`
- `GET /api/batches/{id}/trace` — upstream/downstream via `app/graph.py` (NetworkX)
- `GET /api/shipments/{id}/risk` — rule-based priority score (`app/risk.py`); swap for a trained XGBoost/GBM model later

## Frontend (Next.js + Tailwind)

```
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Dashboard at http://localhost:3000, lists batches from the API and shows API health.

## Not built yet

Decision engine, ML risk model training, Cytoscape graph visualization (dependency is in `package.json`, no component yet), human-approval flow. Per the project summary, don't build these until the batch → trace → risk → dashboard flow above works end to end.

## Offline data pipeline — Person A

The data work prepares reproducible source-specific observations for Person B's modeling: ingestion → cleaning → features → validation → training-table handoff. Biological contamination, chemical exceedance and spoilage/quality remain separate prediction tasks. Recalls and inspection classes are contextual signals, not laboratory labels. Raw inputs stay immutable; operational demos and synthetic data do not establish predictive accuracy.

**Current milestone: M5 PARTIAL — readiness assessment complete; feature implementation remains blocked. Data remains NOT MODEL-READY.** M1 remains partial: FSIS is **official source confirmed, raw file not yet acquired**, and FDA inspection records remain pending. PDP 2024, openFDA, one NOAA station history and three OpenDOSM crop tables have independently cleaned interim tables and rejection/quality evidence. The [M2 report](reports/m2_cleaning_report.md), [summary](reports/m2_cleaning_summary.json) and [validation](reports/m2_validation.json) record cleaning results. The [M3 report](reports/m3_eda_report.md), [profiles](reports/m3_eda_summary.json) and [visuals](reports/m3_eda_visuals.html) audit observed distributions and unresolved quality issues. The [M4 source mappings](configs/source_contracts.json) and [dictionary](reports/m4_data_dictionary.md) document proposed names and semantics without rewriting tables. The [M1 inventory](reports/dataset_inventory.md) and [source manifest](reports/m1_source_manifest.json) remain frozen acquisition evidence. No predictive features, enrichment joins, invented contamination labels or model training were performed.

| Path | Purpose |
| --- | --- |
| `src/tracefront_data/` | Reusable audit, immutable artifact capture, FSIS inspection and source-ingestion commands |
| `configs/canonical_schema.json` | Draft observation/sensor/label/history/feature contract; source mappings pending |
| `data/raw/`, `data/external/` | Immutable source and contextual artifact bytes; FSIS manual intake under `data/raw/fsis/` |
| `data/manifests/` | Immutable source receipts containing hashes, timestamps, source evidence and explicit acquisition gaps |
| `data/interim/`, `data/processed/` | Future source-specific standardized tables and validated experiment-specific outputs |
| `notebooks/` | Exploration policy; actual notebooks follow ingestion |
| `tests/` | Focused offline data audit tests; no application/database dependency |
| `reports/` | Repository audit, inventory, dictionary, source strategy, quality and leakage findings |

### Run the M0 audit

Use Python 3.11+ from the repository root. No additional packages or database are required. Tested locally on Python 3.11.17 and 3.14.7; final target is LinuxONE/s390x, which has not yet been tested. Shell examples below use Linux bash.

```bash
PYTHONPATH=src python -m tracefront_data.audit \
  --input tmp/food-enforcement-0001-of-0001.json \
  --archive tmp/food-enforcement-0001-of-0001.json.zip \
  --output reports/openfda_snapshot_audit.json
PYTHONPATH=src python -m unittest discover -s tests -v
```

The JSON/ZIP are existing local files, not downloaded by this command. Their SHA-256 values and known provenance gaps are recorded in the report. If absent in a fresh clone, do not fabricate replacement data; M1 will add a reproducible acquisition/import mechanism. The user's previously staged JSON remains staged despite the `tmp/` ignore rule.

The M1 runtime still has no third-party dependencies. `uv.lock` freezes optional pytest tooling; `requirements-dev.lock` provides hashes for pip users on LinuxONE. All locked development wheels are architecture-independent; actual s390x execution remains untested. pandas/NumPy/Parquet libraries are deferred until a later milestone requires them and target support is verified. [Native compilation and portable-format considerations](reports/linuxone_portability.md) cover those gates.

### Run M1 ingestion

```bash
PYTHONPATH=src python -m tracefront_data.ingest run
```

Each run preserves/copies source bytes and appends a new receipt under `data/manifests/`. Exit code **2** means acquisition/review is partial; **1** means a fatal command error; **0** means the ingestion acceptance gates passed. A partial run still contains useful verified artifacts and explicit failures. Network access is required for official metadata/downloads; `--offline` performs supplied local imports and records skipped requests.

For future official FSIS files, the exact intake convention is `data/raw/fsis/incoming/<publisher-original-filename>.json` or `.csv`, with actual separately downloaded documentation under `incoming/docs/`. These are patterns, not existing files or guessed official basenames. The directories may remain empty. Read the [manual intake instructions](data/raw/fsis/README.md) for provenance, checksum, metadata and schema review gates. `--fsis-data-url` accepts a verified direct official URL and uses the same inspector. The default cohort contract stays unreviewed until actual source fields and applicable official documentation are inspected. Unofficial mirrors are not substituted.

Use a recorded receipt path for offline integrity checks or exact-byte restoration:

```bash
PYTHONPATH=src python -m tracefront_data.ingest verify data/manifests/20261017T053958804059Z-a2601437.json
PYTHONPATH=src python -m tracefront_data.ingest restore data/manifests/20261017T053958804059Z-a2601437.json
```

Restoration never replaces existing corrupted bytes or silently accepts a newer upstream version. It appends a restoration receipt when downloads/imports are attempted. Download timestamps are acquisition evidence, not historical label availability.

Optional locked test environment (M1 itself runs without it):

```bash
uv sync --locked --extra dev --no-install-project
PYTHONPATH=src .venv/bin/python -m pytest -q
```

Without uv, use `python -m venv .venv` and `.venv/bin/python -m pip install --require-hashes --only-binary=:all: -r requirements-dev.lock`, then run the same pytest command. The direct `PYTHONPATH` workflow does not need a package build or native compilation. LinuxONE needs Python 3.11+; record its actual interpreter/distro before later native-library resolution.

### Audit and design documents

- [Repository state, assumptions, architecture and exact milestone plan](reports/repository_audit.md)
- [All eleven dataset candidates, evidence and limitations](reports/dataset_inventory.md)
- [Experiment separation, valid/blocked joins and evaluation split guidance](reports/dataset_strategy.md)
- [Draft data dictionary](reports/data_dictionary.md)
- [Measured data quality](reports/data_quality_report.md) and [full local audit JSON](reports/openfda_snapshot_audit.json)
- [Preliminary leakage audit and future acceptance tests](reports/data_leakage_audit.md)
- [LinuxONE/s390x portability](reports/linuxone_portability.md)

### M2 — Source-specific cleaning

The M2 cleaner processes only entries explicitly marked `m2_eligible=true` in the frozen [M1 source manifest](reports/m1_source_manifest.json). It verifies every M1 captured artifact before and after the run. It does not change raw bytes, pending FSIS/FDA inspection inputs, Person B's component or the final canonical schema.

```bash
PYTHONPATH=src python -m tracefront_data.clean
PYTHONPATH=src .venv/bin/python -m pytest -q tests
```

Outputs go under `data/interim/m2_v1/`, independently for PDP samples/results, openFDA recalls, NOAA daily element observations and each OpenDOSM table. The [cleaning report](reports/m2_cleaning_report.md), [machine-readable summary](reports/m2_cleaning_summary.json) and [validation evidence](reports/m2_validation.json) record measured acceptance/rejection counts, missingness, code/raw fingerprints and output hashes.

**NOT MODEL-READY.** CSV files have datatype/unit schemas (`*.schema.json`) and explicit null encoding: `\N` means null, an empty cell is a non-null empty string, and a literal leading backslash is escaped by an extra backslash. Disable dataframe default NA/type guessing when reading these files, or use `tracefront_data.cleaning.common.read_table`, which returns declared Python types without extra dependencies. IDs stay strings. `*.rejected.jsonl` preserves rejected source rows/reasons; `*.issues.jsonl` preserves warnings. `source_row_number` and duplicate references are lineage, not approved predictors.

PDP preserves ND/NP censoring, original concentration tokens, units and result annotations without declaring regulatory exceedance. NOAA preserves missing sentinels and all flags alongside scaled measurements. openFDA remains historical context. OpenDOSM annual reference markers are not publication dates; conflicting aggregate-key versions are quarantined together, without choosing or summing values.

Cleaning is deterministic and uses Python's standard library, including temporary SQLite storage for bounded-memory analytical duplicate checks. A repeat run reuses byte-identical generated outputs and refuses to overwrite changed ones. To compare a separate reproduction, use a new directory below `data/interim/` via `--output-dir`; no output directory under `data/raw/` is permitted. Raw-store backups remain necessary.

`PYTHONPATH=src python -m tracefront_data.clean --verify-only` checks all output hashes and streams the seven typed tables to validate counts, nulls, source-specific keys, PDP references/censoring and NOAA scaling/flags without cleaning again. Full raw-to-output rebuilding on Python 3.11 matched all 30 output files from Python 3.14. The 56 portable tests pass on both versions. Training-dependent tests were excluded as instructed; separate ML/backend suites could not collect without their existing application dependencies (first missing modules: matplotlib and SQLAlchemy). No ML/native dependency was added to the data environment to run those unrelated suites.

### Continue or reproduce public-source ingestion (M1)

Use the frozen receipt to verify local raw files or restore missing bytes. Restoration checks exact hashes and appends a receipt; a changed publisher file fails. Keep an offline copy of the raw store because publisher URLs can change or disappear. The full command details and pending-source routes are in the [expanded M1 report](reports/m1_public_ingestion_report.md).

```bash
PYTHONPATH=src python -m tracefront_data.public_sources verify --manifest data/manifests/20261017T060123145416Z-29c44de9.json
PYTHONPATH=src python -m tracefront_data.public_sources restore --manifest data/manifests/20261017T060123145416Z-29c44de9.json
PYTHONPATH=src python -m tracefront_data.public_sources inspect --manifest data/manifests/20261017T060123145416Z-29c44de9.json
```

With the frozen raw store present, `PYTHONPATH=src python -m tracefront_data.public_sources acquire` revalidates captured artifacts and retries pending public downloads, preserving original retrieval clocks. `--source usda_pdp` restricts acquisition to that source. Changing source/version requires deliberate config and dictionary review; the PDP schema is pinned to the reviewed archive hash.

M2 handles only the eligible acquired cohort; FSIS and FDA inspection records remain excluded until acquired and reviewed. M3 audits distributions; M4 declares reviewed source mappings and explicit holds; M5 assesses and builds only supported features; M6 enriches; M7 verifies leakage/quality; M8 produces separate Parquet training tables and a modeling handoff. M5 has completed its readiness assessment; M6–M8 have not begun.

### M3 — Source-specific EDA and quality audit

```bash
PYTHONPATH=src python -m tracefront_data.eda
PYTHONPATH=src .venv/bin/python -m pytest -q tests
```

The command verifies frozen M1 artifacts, M2 producer fingerprints, all M2 output checksums and full typed readback before profiling all seven tables. It checks the raw/output bytes again after the audit. It writes only `reports/m3_eda_report.md`, `reports/m3_eda_summary.json` and the standalone `reports/m3_eda_visuals.html`; the HTML opens locally without a server or external assets. No source tables are rewritten. Identical code and verified inputs produce identical reports.

Profiles preserve explicit null/empty/blank-code distinctions and include categorical cardinality, unit-specific numeric distributions, temporal coverage, PDP MEAN/annotation/extraction diagnostics, NOAA flag/gap audits, recall record/event counts and rejected OpenDOSM conflicts. Categories above 10,000 distinct values report a lower bound without biased prefix rankings; numeric distribution caps are explicit. Free-text values are not ranked as categories. These are descriptive record counts, not contamination prevalence or model features. The standard-library runtime adds no native dependency and retains LinuxONE portability; actual s390x execution is still pending.

Read the [M3 scientific quality review](reports/m3_quality_findings.md) alongside the generated profiles. It explains the observed assay/event dependence, historical classification-date concern, NOAA coverage/flags, district conflicts and the unresolved production-unit interpretation for OpenDOSM flowers. Publisher-declared units in the profiles do not establish scientific comparability across crops.

### M4 — Source-specific canonical contracts and dictionaries

```bash
PYTHONPATH=src python -m tracefront_data.contracts
PYTHONPATH=src python -m tracefront_data.contracts --check-only
```

The [source registry](configs/source_contracts.json) covers all 106 columns across seven M2 tables and remains separate from the [future batch design](configs/canonical_schema.json). The command validates upstream fingerprints and actual M2 sidecars, then renders the [dictionary](reports/m4_data_dictionary.md), [CSV](reports/m4_data_dictionary.csv) and [schema summary](reports/m4_schema_summary.json). Read the [M4 decisions and remaining holds](reports/m4_schema_report.md) before using proposed names. It performs no data renames, source joins, feature generation or label materialization.

Exact decimals, date precision, native code vocabularies, scoped identifiers and missingness semantics remain explicit. Historical availability stays pending for every source; both OpenDOSM production fields have pending physical units. Predictor allowlists are empty. Source mappings do not establish verified supplier/farm/factory relationships. Python 3.11+ standard library only; no new native dependency. Outputs remain **NOT MODEL-READY**.

### M5 — Feature readiness assessment and cleared source-specific features

```bash
PYTHONPATH=src python -m tracefront_data.feature_readiness
PYTHONPATH=src python -m tracefront_data.pdp_sample_context_features
PYTHONPATH=src python -m tracefront_data.pdp_sample_context_features --verify-only
```

The [M5 report](reports/m5_feature_report.md) and [machine-readable assessment](reports/m5_feature_readiness.json) assess 11 feature families against the pinned M4 contract. The [scope file](configs/m5_feature_scope.json) records the one documented experiment (`pdp_2024_sample_context_retrospective`), its prediction cutoff (2025-12-23, DATE precision) and the official availability evidence (USDA AMS posting record for the pinned 2024 PDP Database ZIP; reproduced in [reports/m5_evidence/](reports/m5_evidence/)). Exactly two families — `pdp_product_context` and `pdp_collection_calendar` — clear all prerequisites; the other nine stay blocked, with `pdp_input_missingness` still pending its missingness-semantics policy and `growst`/`packst` availability evidence, and the `usda_pdp.results` analytical fields excluded outright as label evidence.

The assessor writes reports only. The separate materialization command re-checks the assessment, re-verifies the pinned M2 `usda_pdp.samples` bytes against `reports/m2_cleaning_summary.json`, then writes one un-joined, unlabeled, source-specific feature table (10 features plus lineage columns) under [data/interim/m5_v1/](data/interim/m5_v1/) with what was written described in [its own report](reports/m5_pdp_sample_context_features_report.md). Native codes pass through verbatim, nulls remain null (no imputation), the three calendar features are deterministic derivations of `pdp_collection_date` only, and no cross-source join, label, missingness indicator or model output is produced. The [validation record](reports/m5_validation.json) documents tests and upstream preservation. Continue M5 only after further real cutoff/availability and source-policy evidence; all outputs remain **NOT MODEL-READY**.

No public dataset currently supplies a verified complete farm-to-retail batch trajectory. Keep unknowns explicit, avoid future/publication-time leakage, report sampling/domain limitations and avoid interpreting an uncalibrated score as the probability that a batch is safe or contaminated.
