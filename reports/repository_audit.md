# M0 — Repository and dataset audit

Audit date: 2026-10-17. Status: M0 COMPLETE; ingestion, cleaning, features, enrichment and modeling are not implemented. This report describes the current `predictive-ml` checkout, not historical files mentioned in Git history.

## 1. Current repository status

- The repository is an existing Tracefront application, not an empty ML project.
- Pre-existing user work: modified `.gitignore` adding `tmp/`; staged addition of `tmp/food-enforcement-0001-of-0001.json` (39,906,111 bytes). The ignored ZIP is also present (5,858,570 bytes). M0 does not stage, move, rewrite, unstage or delete either file. M0 preserves the `tmp/` rule and appends Python tooling ignore patterns.
- Seven tracked Python 3.13 bytecode files exist under `backend/app/__pycache__/`. They are historical build artifacts, not proof of the current Python version. Cleanup is deferred.
- `INDEX.md` references `source-of-reference/`, `alt-landslide-idea/`, `adam-food-recall-data/`, `research/` and `planning/`; none exists in this working tree. Those references cannot establish local data provenance.
- No applicable `AGENTS.md` was found in this repository or its ancestor directories.

## 2. Existing architecture and tooling

| Area | Observed state |
| --- | --- |
| Python | Default `python` / `python3`: 3.14.7. Alternative `python3.11`: 3.11.17. No project Python pin or declared version existed. |
| Package management | `uv` 0.12.21, pip and pip3 available. Backend uses pinned `requirements.txt`; no Python lockfile. Frontend uses npm scripts; no npm lockfile. No Poetry/PDM config. |
| Backend | FastAPI, SQLAlchemy, PostgreSQL driver, Pydantic, dotenv, NetworkX. `backend/app/main.py` creates tables on import; do not import it just to audit data. |
| Backend dependencies | fastapi 0.115.0; uvicorn 0.30.6; sqlalchemy 2.0.35; psycopg2-binary 2.9.9; pydantic 2.9.2; python-dotenv 1.0.1; networkx 3.3. Backend dependencies were not installed in the audited default environment. |
| Backend data model | Organization, Batch, BatchRelationship, Shipment, SensorReading, LabResult. No local database export or DB contents inspected. No external DB connection attempted. |
| Existing risk logic | `backend/app/risk.py`: transparent rule score, universal 7°C threshold, excursion reading counts. It has no prediction cutoff or availability-time filtering. It is not an ML contamination probability or a valid reusable feature pipeline. Leave behavior unchanged in M0. |
| Tests | `backend/app/test_risk.py`: two fake-session checks for the existing rule score. No prior data tests or CI configuration. |
| Frontend | Next.js 14.2.15, React 18.3.1, Tailwind 3.4.13, TypeScript 5.6.3, Cytoscape dependencies; batch list and API health. |
| Other source/docs | `index.html` static event page; README application setup; INDEX historical workspace index; project summary including proposed hybrid AI revision. All source files were read before editing. |
| Existing data | One openFDA-style JSON snapshot and its matching ZIP, both under `tmp/`. No FSIS/PDP/sensor datasets, notebooks, Parquet tables, download scripts, feature scripts or source manifests found. |
| ML environment | NumPy 2.5.3 and Pydantic 2.13.5 installed globally; pandas, PyArrow and pytest absent. Global packages are not a reproducible environment. |

## 3. Architecture established by M0

Retain `backend/` and `frontend/`. Place offline data logic in the uniquely named `src/tracefront_data/` package, with root `pyproject.toml`. This avoids a generic `src`/`data` import namespace and keeps database startup out of audits.

```text
configs/canonical_schema.json       proposed contract, not a source mapping
data/{raw,external,interim,processed}/
notebooks/README.md                 exploration policy; notebooks deferred
src/tracefront_data/audit.py        offline source audit only
tests/test_audit.py                 audit integrity tests
reports/                           measured audit + source research + design
backend/ and frontend/             existing application, unchanged
```

Select **uv + pyproject.toml** for local dependency resolution, keeping standard venv/pip compatibility on LinuxONE. M0's audit needs only Python's standard library (Python >=3.11); it was exercised on 3.11 and 3.14. No dependencies were installed. The optional pytest dependency is declared for future use; unittest also runs the current tests. M1 should resolve a data dependency set and commit a lockfile. Pin the deployment Python only after verifying the teammate/LinuxONE interpreter; 3.12 is a candidate, not a tested deployment claim. Avoid changing the backend environment as part of this data task. Final training/pipeline target is **s390x**, not the local x86_64 machine; native NumPy/pandas/PyArrow support must be verified as described in [portability](linuxone_portability.md).

## 4. Missing infrastructure

Versioned download manifests and licensing evidence; locked data dependencies; source-specific parsers; explicit timezone/availability contracts; schema adapters; entity crosswalks; configurable food-specific threshold policies; quality/quarantine tables; feature builders; leakage tests; experiment-specific Parquet outputs; data version/split manifests; EDA; final modeling handoff. All are future milestones. Current application lab timestamps are timezone-naive and lack result-availability time; do not reuse them as historical training truth without extension.

## 5. Dataset strategy

Prioritize an FSIS **single commodity × single pathogen × sampling program** pilot with tested positive and negative results, subject to inspecting its actual dictionary. Ingest the existing recall snapshot as a separate contextual table. Next inspect one spoilage dataset with real laboratory endpoints (milk/paneer/beef) and auditable experimental units. Keep PDP as a separate chemical experiment. Fruit condition labels are a proxy task, not contamination labels. NOAA, FDA inspections, RASFF and OpenDOSM are optional enrichment subject to keys, spatial relevance and time availability. See [inventory](dataset_inventory.md) and [join strategy](dataset_strategy.md).

## 6. Proposed canonical schema

The [draft contract](../configs/canonical_schema.json) separates observation snapshots, timestamped sensor events, delayed labels and historical events. The [dictionary](data_dictionary.md) defines proposed roles, units and availability. Sparse historical sources retain native granularity; missing batch/farm identifiers remain null, never invented. A schema is a design, not evidence that all features exist.

## 7. Major risks

No local supervised cohort; recalls lack negative denominators; selective surveillance; test-result and publication-delay leakage; unverified establishment-to-FEI/company matching; repeated trajectories masquerading as independent samples; chemical detection confused with exceedance; generic temperature limits; region/domain shift; unsupported universal contamination labels. See [leakage audit](data_leakage_audit.md).

## 8. Exact M0 implementation plan and acceptance

1. Read tracked source/configuration/docs and enumerate ignored local data, Python tools and user changes. **Done.**
2. Inspect local JSON structure, full row count, field union, missingness, identifiers, date plausibility, categories, hashes and ZIP equivalence without altering source. **Done.**
3. Locate primary publishers for all eleven candidates; record source/license evidence, row units, labels, limitations, unknowns and intended role. Do not download new datasets in M0. **Done; file-level verification deferred explicitly.**
4. Establish an offline package and data lifecycle directories; leave application behavior and user changes intact. **Done.**
5. Write a provisional canonical contract, data dictionary, join matrix, assumptions, preliminary leakage audit and quality report. **Done.**
6. Add and exercise a deterministic audit CLI and focused tests; regenerate the local snapshot report; inspect counts and verify source hashes/Git state. **See validation record in the quality report.**
7. Stop at M0. No ML training, new ingestion, cleaning, final EDA, feature computation, APIs or deployment. Recommend M1 with explicit source gates. **M0 stop condition.**

## 9. Project assumptions and deferred decisions

- Person A owns data and Person B modeling/evaluation. Target granularity and prediction cutoff must be agreed before a training table, not guessed from a dashboard demo.
- Biological pilot default: predict a selected assay's positive result using information known at sample collection; label becomes known later. This is a sampled-population task, not universal batch safety or causal source identification.
- No universal `contamination_label`. No negative label inferred from absence of recall. No synthetic safety labels mixed with real evaluation.
- Source timestamps keep their original precision and timezone metadata. Date-only data must not be assigned fabricated intraday order. Unknown public availability is a feature eligibility issue, not permission to assume immediate availability.
- There is no verified international facility crosswalk, source shipment linkage, food threshold registry or applicable chemical-limit mapping yet. They remain gates, not missing values to manufacture.
- Repository-wide bytecode/Git cleanup and stale historical INDEX links are recorded but outside M0 edits. The previously staged raw JSON will remain staged despite `tmp/` being ignored.

## 10. Subsequent milestone boundaries

| Milestone | Concrete output and gate |
| --- | --- |
| M1 | Immutable downloads/imports + hashes, license/dictionary snapshots, source manifests and locked data environment. FSIS negatives/keys and result vocabulary must be inspected. |
| M2 | Source-specific clean tables, unit/time normalization, rejection ledger and before/after quality counts. |
| M3 | Real EDA for label counts, effective independent sample sizes, missingness, category counts and anomalies. |
| M4 | Freeze supported schema subset with verified original-column mappings and prediction-time roles. |
| M5 | Tested product-specific temperature, time and history features with event/availability cutoffs. |
| M6 | Only approved, coverage-audited, cardinality-safe historical/weather/context joins. |
| M7 | Automated leakage, availability, uniqueness, quality and split-boundary gates. |
| M8 | Separate validated training tables, frozen feature/label lists, split manifests and `modeling_handoff.md` with actual balance/missingness. |
