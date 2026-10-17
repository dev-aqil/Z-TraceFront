# Tracefront handoff: current state and remaining work

## Latest implementation update — 18 October 2026

The persistence/deployment and traceability priorities below are now implemented and deployed to LinuxONE. The older snapshot is retained below as history; use [demo-runbook.md](demo-runbook.md), [schema-and-api.md](schema-and-api.md), and [demo-validation.md](demo-validation.md) for the current state.

- Analyses are stored in PostgreSQL as findings/distribution JSON and survive a real service restart.
- Both `tracefront-backend` and `tracefront-ml` are active on LinuxONE. All five models respond with explanations. Missing poultry sample tables were restored from checksum-matching server archives; the legacy Salmonella label header is supported without rewriting the table.
- `/trace` shows stored upstream ingredients, related products at other factories, shipment destinations and shared-ingredient ranking. The synthetic scenario is idempotent and labels remain visible after refresh.
- Organizations, shipments and ingredient links can be created through the API. Lot codes are unique per producer; cycles and invalid references are rejected.
- Deployment now packages both services' code/config; `-WorkingTree` ships uncommitted source explicitly, without creating a commit. Package installation is opt-in. Server data, native models and credentials are preserved, with application-code backups.
- For this session, the production frontend on port 3000 uses the LinuxONE tunnel on local ports 18000/18100. Existing local APIs on 8000/8100 were left running. The helper supports those alternate ports. Stop `npm start` before switching back to `npm run dev`; stop the development server before rebuilding.
- Still pending: containment recommendations/approval log, live event replay and integration of model sampling priority with the incident workflow. One batch per shipment remains the MVP limit.

State as of 2026-10-18. Branch `ml-b` at `827b44f`; `main` was fast-forwarded to `ml-b` up to `38f13eb`. Read this first, then [schema-and-api.md](schema-and-api.md) (every table and route, with real responses) and [../tracefront_project_summary.md](../tracefront_project_summary.md) (the product pitch and its demo script, section 17).

## What Tracefront is

Tracefront is a food-safety decision-support demo for the **IBM Z Datathon, Real-Time AI track**. It flags risky shipments and batches, shows where food went, and supports a human containment decision. It must not claim to detect contamination: scores are prioritisation signals, and the UI says so.

## Repository layout

| Path | What it is |
|---|---|
| `backend/` | FastAPI + SQLAlchemy 2.0.35. `app/main.py` holds the CRUD and trace routes; `app/analysis.py` handles shipment-file upload and cold-chain findings; `app/graph.py` is the NetworkX trace; `app/models.py` holds 6 tables. Tests are `app/test_*.py`. |
| `food-risk-ml/` | ML service (FastAPI, port 8100). There are five pathogen models trained on real FSIS lab samples: poultry Salmonella and Campylobacter, beef Salmonella and STEC, RTE Listeria. `src/api/spin.py` serves `/models`, `/models/spin` and `/models/predict`; `src/coldchain/rules.py` and `configs/cold_chain_rules.toml` are the cold-chain rules the backend imports. An imidacloprid chemical model exists but has no endpoint. Model cards are in `docs/`. |
| `frontend/` | Next.js 14 + Tailwind. The flow runs `/` (upload or spin) → `/ml-process` (animation) → `/analysis-results` (findings or model cards) → `/distribution` (tree + Notify). `lib/api.ts` is the only API client. `/reports` and `/design` are unlinked leftovers. |
| `src/tracefront_data/`, `tests/`, `reports/`, `data/` | Person A's offline data pipeline and audits. Don't modify it unless asked. |
| `contracts/ml-findings.schema.json` | The findings response contract the frontend consumes. |

## Running locally (Windows, PowerShell)

```
cd backend;      .venv\Scripts\python -m uvicorn app.main:app --port 8000          # set DATABASE_URL (e.g. sqlite:///./dev.db) first
cd food-risk-ml; .venv\Scripts\python -m uvicorn src.api.app:app --port 8100       # model artifacts are local, gitignored
cd frontend;     npm run dev                                                        # http://localhost:3000
```

The frontend defaults to `localhost:8000` and `localhost:8100` (`NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_ML_URL`). Both services' CORS settings allow only `http://localhost:3000`.

**Checks:**
- **Frontend:** `cd frontend; npx tsc --noEmit`.
- **Backend:** the backend venv has no pytest. Import `app.test_analysis` and `app.test_risk` and call each `test_*` function.
- **ML:** `cd food-risk-ml; .venv\Scripts\python -m pytest -q -p no:cacheprovider`.

## LinuxONE server (shared)

- **Login:** `ssh -i $env:USERPROFILE\.ssh\linuxone-teammate linux1@148.100.77.171` from **PowerShell**; Git Bash's ssh is rejected with the same key. Ubuntu 24.04, s390x, passwordless sudo.
- **Backend:** systemd service `tracefront-backend` on `127.0.0.1:8000`, in `~/tracefront/backend`.
- **Database:** PostgreSQL 16 on `127.0.0.1:5432`, database and role `tracefront`. The password lives only in `~/tracefront/backend/.env`; never print it. All tables are currently empty.
- **Deploy:** `.\backend\deploy.ps1` ships the **last commit's** `backend/` and runs `backend/setup_linuxone.sh`, which is idempotent: it keeps the data, runs the tests and restarts the service.
- **Python environment:** the venv is `~/.venvs/foodrisk`, which sees the apt numpy and pandas. `psycopg2` comes from apt (`python3-psycopg2`): `psycopg2-binary` has no s390x wheel. SQLAlchemy is pinned to 2.0.35, because 2.1 switches `postgresql://` to the psycopg 3 driver.
- **ML on the server:** `~/tracefront/food-risk-ml` is an **old copy**, unpacked from a tarball. It has no `spin.py` and is missing `data/processed/canonical.csv` and `canonical_campylobacter.csv`; older copies sit in the sibling `food-risk-ml-*` dirs. The ML service is **not** running on the server.
- **Access for teammates:** `ssh -L 8000:127.0.0.1:8000 -L 5432:127.0.0.1:5432 linux1@148.100.77.171`.

## Rules for working in this repo

- **Don't commit, push, rebase or amend.** Leave changes in the working tree and give the user a `git commit -m "..." -m "..."` command, with no AI co-author line.
- **The user runs package installs** (pip and npm). Give the commands instead of running them.
- **Never run `npm run build` while `next dev` is running.** Both write to `frontend/.next`, and the dev server breaks with 500s. Use `npx tsc --noEmit`.
- **Shell scripts must stay LF.** `.gitattributes` has `*.sh text eol=lf`; this machine's `core.autocrlf=true` would otherwise put CRLF into `git archive` output.
- **Tables are never altered on startup.** `Base.metadata.create_all` only creates missing tables. A column change in `models.py` needs the table dropped on the server or a migration.
- **Postgres enforces all 8 foreign keys** (SQLite doesn't by default), so test write paths against Postgres semantics.
- **Match the code style:** short docstrings and comments, no unrequested abstractions, and `ponytail:` comments mark known shortcuts with their ceiling.
- **The root `tests/` suite fails on Windows** for environmental reasons: CRLF breaks hash pins, raw data is gitignored, and Windows locks files. That's expected; don't "fix" it.

## Known limitations (true today)

1. **Uploaded analyses live in memory** (the `ANALYSES` dict in `analysis.py`). Any restart loses them, including an `--reload` restart mid-demo. This was seen during testing.
2. **The API can't fill the database:**
   - there are no create endpoints for `organizations`, `shipments` or `batch_relationships`;
   - with foreign keys enforced, `POST /api/batches`, `/api/sensor-readings` and `/api/lab-results` return 500 until those rows exist;
   - `batch_id` is an integer in the database but a string (`RM-402`) in uploads.
3. **Trace is shallow.** `GET /api/batches/{id}/trace` returns IDs only, follows ingredient → product links only, and isn't used by the UI.
4. **Separate models.** The ML models score FSIS lab samples, not this app's batches or shipments. Spin-a-sample is a separate demo path.
5. **Notify is preview-only** (labelled "Demo mode"). There's no approval or decision log.
6. **There's no real-time stream.** The demo is a one-off file upload, even though `ColdChainMonitor` already processes readings one at a time.
7. **There are two temperature rules.** `/api/shipments/{id}/risk` uses a flat 7 °C; uploads use the per-product profiles.

## Remaining work, in priority order

Each item has a "done when" criterion. Keep diffs small and update `docs/schema-and-api.md` when an API changes.

1. **Persist analyses** (`backend/app/analysis.py`, `models.py`).
   - Store each analysis's findings and distribution documents, as JSON in a new table keyed by `analysis_id`, in place of the in-memory dict.
   - **Done when:** an upload's findings are still served after the backend restarts, and the backend tests pass.
2. **Serve the ML models from LinuxONE.**
   - Ship the current `food-risk-ml` code to `~/tracefront/food-risk-ml` without deleting its `artifacts/` or `data/`, and restore the two missing canonical CSVs from the sibling dirs.
   - Run `uvicorn src.api.app:app --port 8100` as a systemd service, mirroring `setup_linuxone.sh`, ideally as a second script plus a deploy step.
   - **Done when:** `/models` and `/models/spin` answer on the server, and the frontend works through the tunnel with `-L 8100:127.0.0.1:8100`.
3. **Demo-day setup.**
   - Add one script or command that opens the tunnel for both ports.
   - Document running the frontend as a production build (`npm run build && npm start`, with the dev server stopped).
   - Fix stale README lines: "Server upload is not connected yet", and "Not built yet: … Cytoscape …".
4. **Small UI polish.**
   - A red "High" severity tag on high findings in `analysis-results/page.tsx`; today severity only shows in the counter.
   - Spread the finding icons evenly around the "N anomalies found" number; today they fill fixed slots, and with 3 they all sit on the left.
   - Shorten the danger-zone sentence in the temperature summary.
5. **Traceability** (the pitch's core; see the project summary, sections 6–7 and 17).
   - **Seed data:** a synthetic seed script where Lettuce L-102 goes into Chicken Wrap CW-42 and Caesar Salad CS-91, shipped by two trucks to two factories and on to stores.
   - **Endpoints:** create and list organizations, shipments, shipment items (several batches per truck) and batch relationships.
   - **Trace output:** tiers, with locations taken from the shipments:
     - T0, the flagged batch;
     - T1, downstream products and every place they were shipped;
     - T2, "siblings": other products made from the same ingredient lots;
     - T3, upstream suppliers.
   - **Ranking:** shared ingredients rank by how many flagged products use them.
   - **UI:** a graph page; `cytoscape` and `cytoscape-dagre` are already in `package.json`, unused.
   - **Done when:** flagging CW-42, then CS-91, ranks L-102 first and lists the other factory's products and stores.
   - **Design questions still open with the user:** what triggers a trace (model flag, lab positive, cold-chain finding, manual), whether factories record exact lot links, and lot-code uniqueness (use `UNIQUE(org_id, lot_code)`).
6. **Containment decision and human approval.**
   - Hold, stop-truck and recall recommendations on a finding or trace, with Approve and Reject buttons.
   - A decision log table with timestamps (summary steps 7–8).
7. **Real-time replay.** Stream an uploaded file's readings in time order through `ColdChainMonitor`, and show risk and alerts appearing live.

## Known-good demo path (to keep working)

1. On `/`, choose Browse files → Browse files → Open (the example file) → Preview analysis.
2. Watch the animation (about 9 s).
3. The results show "3 anomalies found" (1 high SHIP-017, 1 medium SHIP-039, 1 low SHIP-042).
4. Click Next to reach the distribution tree, with 3 amber paths and Notify.
5. Separately, use Spin real sample → Run analysis to reach the pathogen cards, each showing "N× this model's high-risk line".
