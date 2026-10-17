# Persistence, deployment and traceability validation

Verified 18 October 2026 against the working-tree release based on `827b44f032857653ac1b5255e899a7d480c92b67`. No commit or push was created. The deployed `~/tracefront/release-manifest.json` records SHA-256 values of the shipped source/config bytes.

## Local checks

- TypeScript check passed for the trace screen and API client.
- Production frontend build passed with the new `/trace` route.
- Seven backend analysis/risk checks passed, including a regression proving identical route names do not connect independent distributors.
- Four HTTP/database integration checks passed: cross-factory trace and ranking; rollback of a seed conflicting with existing records; upload survival across an actual API-process restart; write validation, scoped lot-code ambiguity and ingredient-cycle rejection.
- Ten model-family API tests passed, including the legacy Salmonella label-column regression and rejection of that column for a different pathogen.
- The release package was checked for both services' source/config, absence of secrets/model registries/source datasets/bytecode, and LF-only shell scripts.

## LinuxONE deployment

- Both backend and ML services run under systemd on loopback ports 8000 and 8100.
- Existing Python dependencies were reused. No package installation or model retraining was performed.
- Missing canonical poultry sample tables were restored only from server archives matching each trained model's recorded SHA-256. Existing model registries and database credentials were preserved.
- Backend checks and the four isolated integration checks passed on s390x during deployment.
- Preflight passed for all five models, with valid probabilities and nonempty explanations:
  - `salmonella-xgboost-20261017T103204Z`
  - `campylobacter-xgboost-20261017T131153Z`
  - `beef_salmonella-xgboost-20261017T142904Z`
  - `beef_stec-xgboost-20261017T143643Z`
  - `rte_listeria-xgboost-20261017T143149Z`
- The same preflight passed through the local 18000/18100 SSH tunnel used by the frontend.

## Actual PostgreSQL and restart checks

- Confirmed the deployed database dialect is PostgreSQL.
- An intentionally invalid organization reference was rejected with PostgreSQL SQLSTATE `23503`; the transaction was rolled back.
- The synthetic seed loaded successfully, and a trace of CW-42 plus CS-91 ranked L-102 first with two matching selected products.
- The trace included related products and Store JB-01 at the second factory's distribution branch. Synthetic provenance was present for every seeded batch.
- Uploaded one synthetic verification file, retrieved its findings and distribution, restarted `tracefront-backend`, and retrieved identical findings, distribution and lot trace afterwards. Verification upload: `analysis-1dc3522d274f`.
- Confirmed the frontend origin `http://localhost:3000` receives the expected CORS allowance.

## Browser checks

The `/trace` page was exercised against LinuxONE through the tunnel. Loading the scenario selected CW-42; adding CS-91 changed the first ingredient's count to **2 / 2 products**. The view listed both factories, warehouses, stores, shipment units/statuses and the separately recorded simulated lab result. Investigation selections are encoded in the URL for refresh/share.

The original browser upload walkthrough also completed against LinuxONE: the bundled example produced three findings, then the distribution page showed three marked shipments and linked into lot investigation. Browser verification upload: `analysis-109f98c2f80d`. Synthetic lot matches are labelled explicitly; the example upload does not establish the seeded ingredient links.

## Scope still pending

Containment recommendation/approval logging and live replay were not implemented. Trace selection does not create a lab result or execute a hold/recall. Model results remain sample-scoped. Shipment movement quantities are not current inventory or estimates of prevented illness.
