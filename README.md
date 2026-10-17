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

**Current milestone: M1 partial. FSIS: official source confirmed, raw file not yet acquired.** PDP 2024, the existing official-byte-verified openFDA snapshot, one NOAA Malaysian station history and three OpenDOSM crop tables are acquired. FDA inspection records remain pending after official export URLs returned 404; its API requires credentials. The [current inventory](reports/dataset_inventory.md), [machine-readable source manifest](reports/m1_source_manifest.json) and [expanded M1 report](reports/m1_public_ingestion_report.md) record actual counts, licenses, hashes and source-specific M2 eligibility. FSIS manual intake and [source-status evidence](reports/m1_fsis_source_status.json) remain unchanged. No cleaning, features, merges or training have occurred.

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

### Continue or reproduce public-source ingestion (M1)

Use the frozen receipt to verify local raw files or restore missing bytes. Restoration checks exact hashes and appends a receipt; a changed publisher file fails. Keep an offline copy of the raw store because publisher URLs can change or disappear. The full command details and pending-source routes are in the [expanded M1 report](reports/m1_public_ingestion_report.md).

```bash
PYTHONPATH=src python -m tracefront_data.public_sources verify --manifest data/manifests/20261017T060123145416Z-29c44de9.json
PYTHONPATH=src python -m tracefront_data.public_sources restore --manifest data/manifests/20261017T060123145416Z-29c44de9.json
PYTHONPATH=src python -m tracefront_data.public_sources inspect --manifest data/manifests/20261017T060123145416Z-29c44de9.json
```

With the frozen raw store present, `PYTHONPATH=src python -m tracefront_data.public_sources acquire` revalidates captured artifacts and retries pending public downloads, preserving original retrieval clocks. `--source usda_pdp` restricts acquisition to that source. Changing source/version requires deliberate config and dictionary review; the PDP schema is pinned to the reviewed archive hash.

M2 may subsequently handle only sources with all eligibility gates passed; FSIS and FDA inspection records remain excluded until acquired and reviewed. Then M3 analyzes distributions; M4 freezes verified mappings; M5 builds features; M6 enriches; M7 verifies leakage/quality; M8 produces separate Parquet training tables and a modeling handoff. Commands for M2–M8 do not exist yet.

No public dataset currently supplies a verified complete farm-to-retail batch trajectory. Keep unknowns explicit, avoid future/publication-time leakage, report sampling/domain limitations and avoid interpreting an uncalibrated score as the probability that a batch is safe or contaminated.
