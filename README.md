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

Dashboard at http://localhost:3000. The supplier-report list is sample UI data and the file control only selects a local file. Report storage and analysis endpoints are not connected yet.

Design workspace at http://localhost:3000/design. It maps the two HTML mockups into three planned Next.js screens and keeps the original mockups under `frontend/design/reference/`. The full screens have not been converted yet.

The network animation preview is at http://localhost:3000/ml-process. Connections draw over three seconds, then new links appear while older ones retract and signal dots move rapidly across active links. The dots thin out over three seconds, leaving the lines to retract into their endpoint dashes. The dash circle closes into the first dash, then the camera slowly zooms toward it. This is an illustrative sequence, not a trained model visualization. It includes pause and replay controls and a static view for reduced-motion settings.

## Not built yet

Decision engine, ML risk model training, Cytoscape graph visualization (dependency is in `package.json`, no component yet), human-approval flow. Per the project summary, don't build these until the batch → trace → risk → dashboard flow above works end to end.
