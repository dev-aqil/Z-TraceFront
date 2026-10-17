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

Upload page at http://localhost:3000. It matches the approved page-one mockup and uses the TraceFront logo. Its single upload button opens a simulated file-selection walkthrough; drag-and-drop checks a local file extension. Server upload is not connected yet. The earlier supplier-report dashboard is at http://localhost:3000/reports and still uses sample UI data.

Design workspace at http://localhost:3000/design. It maps the two HTML mockups into six separate Next.js screens and keeps the original mockups under `frontend/design/reference/`. Page one and the step-two overlay demo are implemented; the later screens are design drafts.

The network animation preview is at http://localhost:3000/ml-process. The selected demo file's "Start analysis" button fades the upload screen out, then this page fades in with the circle fully visible on a desktop viewport. Connections draw over three seconds, then new links appear while older ones retract and signal dots move rapidly across active links. The dots thin out over three seconds, leaving the lines to retract into their endpoint dashes. The dash circle closes into the first dash, then the camera slowly zooms toward it. This is an illustrative sequence, not a trained model visualization. It includes pause and replay controls and a static view for reduced-motion settings.

## Not built yet

Decision engine, ML risk model training, Cytoscape graph visualization (dependency is in `package.json`, no component yet), human-approval flow. Per the project summary, don't build these until the batch → trace → risk → dashboard flow above works end to end.
