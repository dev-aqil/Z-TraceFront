# Tracefront demo runbook

## Deploy the prepared source

From the repository root in PowerShell:

```powershell
.\backend\deploy.ps1 -WorkingTree
```

This deploys current backend/ML source and configuration without creating a commit. Omit `-WorkingTree` to package HEAD. The package contains no `.env`, model registry, source datasets, virtual environment or Python bytecode. Shell scripts are packaged with LF line endings. A checksum manifest records every shipped source file and whether the package contains working-tree changes.

Deployment preserves PostgreSQL contents and server-native models. It saves the previous application code under `~/tracefront-backups/<UTC timestamp>/code.tgz`. Restoring that archive and restarting the two services rolls application code back; it does not revert database contents. Additive tables remain harmless to the previous release. Existing process-local analyses from the old release cannot be recovered after that old process stops; all analyses uploaded to this release are durable.

No packages are installed by default. The existing LinuxONE virtual environment is checked and reused. If a dependency is actually missing, the operator can review and run `-InstallDependencies` for the backend dependencies; ML dependencies/native models must already be provisioned. ML setup checks and restores missing canonical tables from archived server copies only when their bytes match the served model's recorded checksum. It never retrains or replaces models.

The backend and ML services bind to `127.0.0.1` on LinuxONE as `tracefront-backend` and `tracefront-ml`. Backend health checks the database; preflight also verifies the full model catalog and runs each family, requiring valid probabilities and explanations.

## Start the presentation

1. Open a terminal at the repository root and run `.\backend\demo-tunnel.ps1`. Keep it open. A port conflict fails immediately instead of silently forwarding only one service.
2. In a second terminal, run `.\backend\.venv\Scripts\python -B backend/preflight.py`. All five models must report ready.
3. In `frontend/`, run `npm run dev` while rehearsing (it reloads on every change). For the final presentation you may instead stop it and run `npm run build`, then `npm start`; that serves a frozen build that does not pick up later edits. Never build while `next dev` is running, and run only one of them, or Next.js moves to port 3001.
4. Open `http://localhost:3000`. Upload the example. Expect 54 rows, eight shipments, seven batches, and three findings.
5. Open Distribution, then **Trace related lots**. The trace page shows the upload finding that opened it (SHIP-017, RM-402, peak 12.1 °C). If the scenario is not loaded yet, click **Load synthetic scenario**: it adds reserved demo rows idempotently, keeps RM-402 selected, never deletes a record, and refuses conflicting IDs. Rows from the first version of the seed are renamed in place to match the example file.
6. RM-402 (marinated chicken) went into CW-42 (chicken wrap), which shipped to Warehouse KL and two stores. CW-42 has a simulated Salmonella positive, so the chicken excursion looks like the explanation. Only one hold option is shown, because with no upstream lot an extended hold would cover the same stock.
7. The amber panel shows a second positive the selection does not explain: CS-91, a Caesar salad with no chicken in it. Click **Investigate all 2 positive products together**.
8. With CW-42 and CS-91 selected, L-102 (lettuce) ranks first, shared by 2 of 2 products; RM-402 drops to 1 of 2. The recommendation changes to an extended hold covering VW-17 too, which has not tested positive. The count is evidence of a shared lot, not a probability or proof of contamination.
9. In **Containment decision**, enter an officer name and reason, then approve. The decision appears in the history with a link back to the upload, and the held shipments are marked "Hold approved · simulated". Decisions are append-only, so a previous rehearsal's decision stays in the history.
10. Refresh the trace URL to verify the selection is restored. For uploaded results, restart the backend and reopen the same `?analysis=...` URL to verify persistence.

The seed includes ingredient movements in kg and finished-product shipments in units. Shipment rows are movement records, not current warehouse stock; do not sum repeated movements into inventory or prevented-exposure claims. One batch per shipment remains the MVP limit.

If local APIs already occupy 8000/8100, leave them running and use `.\backend\demo-tunnel.ps1 -BackendPort 18000 -MlPort 18100`. Set `NEXT_PUBLIC_API_URL=http://localhost:18000` and `NEXT_PUBLIC_ML_URL=http://localhost:18100` in the frontend terminal before starting development or building production. Preflight accepts `--api http://localhost:18000 --ml http://localhost:18100`. The default URLs still target 8000/8100; do not mistake a local service for the tunneled deployment.

## Local checks

No package installation is needed in the existing backend virtual environment:

```powershell
cd backend
.\.venv\Scripts\python -B -m unittest app.test_system -v
.\.venv\Scripts\python -B -m app.test_analysis
.\.venv\Scripts\python -B -m app.test_risk
```

The HTTP integration suite starts its own isolated API/database, enforces foreign keys, checks invalid references and graph cycles, verifies scoped lot codes, loads the scenario twice, traces across factories, and restarts the API to verify upload persistence. It does not use or reset the real database.

Frontend: `frontend/node_modules/.bin/tsc --noEmit --incremental false` and a production build while no development server is running. A restricted Windows sandbox can prevent Next.js from detecting TypeScript through `realpath`; use a normal terminal if that environment-specific error appears.

Hold execution is simulated: approving records the decision but changes no shipment status. Live sensor replay remains pending.
