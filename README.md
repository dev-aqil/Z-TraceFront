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

API docs at http://localhost:8000/docs; [docs/schema-and-api.md](docs/schema-and-api.md) describes every table and every backend and ML-service route with real example responses. Tables are created automatically on startup from `app/models.py` (matches the ERD in section 14 of the project summary).

Endpoints:
- `GET /api/health`
- `GET /api/batches`, `POST /api/batches`
- `GET/POST /api/organizations`, `/api/shipments`, `/api/batch-relationships`
- `GET /api/trace?batch_ids=<id>&batch_ids=<id>` — ingredients, related products, shipment locations and shared-ingredient ranking
- `POST /api/demo/seed` — idempotent synthetic trace scenario; preserves existing records
- `POST /api/decisions` — record an officer's approve/reject on the trace's containment recommendation (simulated hold)
- `POST /api/analyses`, `GET /api/analyses/{id}/findings`, `GET /api/analyses/{id}/distribution` — database-backed upload results
- `POST /api/sensor-readings`, `POST /api/lab-results`
- `GET /api/batches/{id}/trace` — upstream/downstream via `app/graph.py` (NetworkX)
- `GET /api/shipments/{id}/risk` — rule-based priority score (`app/risk.py`); swap for a trained XGBoost/GBM model later

### Shared backend on LinuxONE

The team API and its PostgreSQL database run on the LinuxONE server and listen only on the server itself. Reach both through an SSH tunnel; your public key must be in the server's `~/.ssh/authorized_keys`:

```
ssh -L 8000:127.0.0.1:8000 -L 5432:127.0.0.1:5432 linux1@148.100.77.171
```

While it is open, the API is at http://localhost:8000 and the database at `localhost:5432` (user and database `tracefront`, password in `~/tracefront/backend/.env` on the server).

Run `.\backend\deploy.ps1` to ship committed backend **and ML** code/config, or add `-WorkingTree` to ship the current source without committing. Server-native model registries, data, database contents and credentials are preserved. Missing model sample tables are restored only when an archived copy matches the model's recorded SHA-256. The script backs up application code, verifies release bytes, runs backend checks, restarts both services and verifies all five pathogen models with explanations. It uses existing dependencies; package installs require the explicit `-InstallDependencies` switch. See [the demo runbook](docs/demo-runbook.md).

For presentation, run `.\backend\demo-tunnel.ps1` and keep it open: this forwards both 8000 and 8100. Run `.\backend\.venv\Scripts\python backend/preflight.py` from the repository root to verify both tunneled services. Additive tables are created at startup; existing tables are not dropped or altered.

## Frontend (Next.js + Tailwind)

```
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Upload page at http://localhost:3000. CSV/XLSX/JSON uploads are analyzed by the backend, and findings/distribution results survive backend restart. The upload dialogue includes a bundled example and a real device-file picker. The earlier supplier-report dashboard at `/reports` still uses sample UI data.

Lot investigation is at http://localhost:3000/trace, linked from the start and distribution screens. From an upload, **Trace related lots** opens RM-402 with the finding that led there. Loading the labelled synthetic scenario links it to CW-42 and flags a second positive, CS-91, that the chicken cannot explain; investigating both positives together ranks the lettuce lot L-102 first because both products used it. The view includes other connected products and shipment destinations across both factories. Unmapped uploaded lot codes are reported explicitly; ingredient relationships are never inferred from a route label. Lot codes are unique per producer, while existing integer batch IDs remain unchanged.

For the final presentation, stop the development server, run `npm run build`, then `npm start` from `frontend/`. Do not build while `next dev` is running. `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_ML_URL` are embedded at build time and default to the two localhost tunnel ports.

Design workspace at http://localhost:3000/design. It maps the two HTML mockups into six separate Next.js screens and keeps the original mockups under `frontend/design/reference/`. Page one and the step-two overlay demo are implemented; the later screens are design drafts.

The network animation preview is at http://localhost:3000/ml-process. The selected demo file's "Start analysis" button fades the upload screen out, then this page fades in with the circle fully visible on a desktop viewport. Connections draw over three seconds, then new links appear while older ones retract and signal dots move rapidly across active links. The dots thin out over three seconds, leaving the lines to retract into their endpoint dashes. The dash circle closes into the first dash, then the camera slowly zooms toward it. This is an illustrative sequence, not a trained model visualization. It includes pause and replay controls and a static view for reduced-motion settings.

## Not built yet

Live event replay remains pending. Containment decisions are recorded with officer, reason and time, but the hold itself is simulated. Five pathogen models and the SVG distribution/lot visualizations are implemented. Model predictions concern FSIS laboratory samples; cold-chain upload findings use transparent rules, not a trained contamination detector.

## Offline data pipeline — Person A

The data work prepares reproducible source-specific observations for Person B's modeling: ingestion → cleaning → features → validation → training-table handoff. Biological contamination, chemical exceedance and spoilage/quality remain separate prediction tasks. Recalls and inspection classes are contextual signals, not laboratory labels. Raw inputs stay immutable; operational demos and synthetic data do not establish predictive accuracy.

**Current milestone: M8 COMPLETE for Person A. CHEMICAL MODEL_READY for a narrowly defined retrospective imidacloprid-detection task; BIOLOGICAL and COLD_CHAIN remain BLOCKED.** The [modeling handoff](reports/modeling_handoff.md), [machine-readable readiness](reports/modeling_handoff.json) and [final leakage audit](reports/data_leakage_audit.md) define the exact target, feature whitelist, split and interpretation limits. No model was trained. FSIS official raw pathogen samples, FDA inspections and legitimate cold-chain sensor/microbial datasets remain pending. M2–M5 records below describe their historical milestone scope; their interim outputs remain NOT MODEL-READY. Only versioned M8 artifacts with `model_ready=true` may be used for training.

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

M2 handles only the eligible acquired cohort; FSIS and FDA inspection records remain excluded until acquired and reviewed. M3 audits distributions; M4 declares reviewed source mappings and explicit holds; M5 assesses and builds only supported features; M6 enriches; M7 verifies leakage/quality; M8 produces task-specific portable CSV/JSON training artifacts and a modeling handoff. M6–M8 are now complete for the named chemical task; other domains remain blocked.

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

The assessor writes reports only. The separate materialization command re-checks the assessment, re-verifies the pinned M2 `usda_pdp.samples` bytes against `reports/m2_cleaning_summary.json`, then writes one un-joined, unlabeled, source-specific feature table (10 features plus lineage columns) under [data/interim/m5_v1/](data/interim/m5_v1/) with what was written described in [its own report](reports/m5_pdp_sample_context_features_report.md). Native codes pass through verbatim, nulls remain null (no imputation), the three calendar features are deterministic derivations of `pdp_collection_date` only, and no cross-source join, label, missingness indicator or model output is produced. The [validation record](reports/m5_validation.json) documents tests and upstream preservation. Further M5 families require real cutoff/availability and source-policy evidence; all M5 interim outputs remain **NOT MODEL-READY**. The M6–M8 section below defines the separate final ready artifact.

No public dataset currently supplies a verified complete farm-to-retail batch trajectory. Keep unknowns explicit, avoid future/publication-time leakage, report sampling/domain limitations and avoid interpreting an uncalibrated score as the probability that a batch is safe or contaminated.

### M6–M8 — Audited chemical detection handoff

The final dataset is `data/processed/chemical_imidacloprid_detection_training_v1.csv`: 9,871 rows, 18 columns, one unambiguous original imidacloprid result per PDP 2024 sample. Target `imidacloprid_detected` means publisher original detection (`O=1`) versus validated well-recovered nondetect (`ND=0`). Re-extractions and marginal-performing nondetects are excluded. Detection does not mean regulatory exceedance, unsafe food or biological contamination.

M6 records 14 formal join proposals: one approved same-release exact `SAMPLE_PK` linkage, five rejected relationships, eight pending proposals. No cross-source context or history is attached. [Join audit](reports/m6_join_audit.md) and [M6 summary](reports/m6_enrichment_summary.json) preserve all decisions. [M7 validation](reports/m7_validation_report.md) audits every candidate column, sample grouping, both clocks, schema and target separation. Nine explicitly allowed sample-context/calendar features form the default matrix; variety text and all analytical evidence are excluded.

The experiment is **retrospective released-cohort association only**. All public context/outcomes were available by the archive posting day 2025-12-23; observation_time is conservatively 2025-12-24. The whole-day collection-date holdout measures later-2024 cohort drift, not a model trainable prospectively during 2024. Facility/lot independence and future-year generalization remain unproved.

With frozen raw files and M1–M5 metadata present:

```bash
PYTHONPATH=src python -m tracefront_data.clean
PYTHONPATH=src python -m tracefront_data.pdp_sample_context_features
PYTHONPATH=src python -m tracefront_data.modeling_handoff --rebuild-check
PYTHONPATH=src python -m tracefront_data.modeling_handoff --verify-only
PYTHONPATH=src python -m unittest discover -s tests -q
```

The handoff command executes M6 → M7 → M8, refuses changed versioned data, and never downloads substitutes or trains models. `--rebuild-check` independently cleans every eligible source from frozen raw twice, reconstructs M5/M6 and the final dataset, and compares all output bytes. It writes [rebuild evidence](reports/m8_rebuild_validation.json). Missing raw artifacts stop processing; use the recorded M1 restoration receipts and maintain an offline raw backup.

Person B should start with the `.readiness.json` and `.features.json` adjacent to the final CSV. The standard-library reader verifies readiness, hashes, provenance, schema, whitelist and target separation:

```python
from pathlib import Path
from tracefront_data.modeling_handoff import load_model_ready
X_records, y_values, identifiers = load_model_ready(Path.cwd())
```

The existing `food-risk-ml` contract is for FSIS/Salmonella and does not accept this chemical task. Person B must use a separate chemical adapter; never rename this target to Salmonella or pesticide exceedance. Only fit preprocessing on training rows. Biological and cold-chain training remain blocked.

Generation/reading requires Python 3.11+ standard library (SQLite for upstream cleaning), UTF-8 CSV/JSON and no native data wheels. Local Python 3.11.17 and 3.14.7 are supported. Actual IBM Z LinuxONE/s390x execution is **not tested**. See [final validation](reports/m8_validation.json) for measured tests and portability limits.
