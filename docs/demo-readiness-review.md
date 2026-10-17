# Tracefront demo readiness review

Reviewed 18 October 2026. The user reports submission is tomorrow. This is a source review and local verification, not certification of the current remote deployment.

**Implementation update:** priorities 1–3 in the table below (durable analyses, LinuxONE release, and stored traceability) have since been implemented and verified on LinuxONE. This document preserves the original assessment. See [demo-validation.md](demo-validation.md) for current verification and [demo-runbook.md](demo-runbook.md) to present the result. Containment approval and live replay remain pending.

## Assessment

Tracefront has useful working components, but the advertised incident-to-decision flow is incomplete. The highest-value work is connecting event ingestion, evidence, traceability, a containment recommendation and a recorded human decision in one reproducible scenario.

The [organizer's track description](https://www.starhacks.org/ibm-z-datathon-2026) calls for streaming data, risk identification and decisions as events unfold. The priorities below are an assessment against that description; numerical judging weights and the exact submission requirements were not available in the retrieved official pages. Check the team's submission portal for the deadline, time zone, required video duration, repository access and deliverables.

## Verified foundation

- The frontend TypeScript check passed (`tsc --noEmit --incremental false`).
- The frontend production build passed with normal filesystem access and generated all nine static pages. The first restricted run failed because sandbox `realpath` permissions prevented Next.js from detecting TypeScript; that was an environment failure, not an established alias/configuration defect.
- All six existing backend analysis/risk test functions passed.
- The full `food-risk-ml` test suite passed with normal runtime permissions and an explicit writable temporary directory. It emitted one Starlette/httpx deprecation warning.
- The real bundled `frontend/public/supplier_shipments.csv` produced 54 rows, eight shipments, seven batches and exactly three findings: high temperature excursion for SHIP-017, medium sensor gap for SHIP-039, and low destination mismatch for SHIP-042.
- Upload analysis is implemented. The early README statement that upload is unconnected is stale.
- The distribution visualization is implemented as a custom SVG tree. Installing or switching to Cytoscape is not necessary merely to claim a visualization exists.
- Five pathogen model routes exist across three product families. Their model cards document real FSIS training data, time splits, calibration, metrics, explanations and limitations.
- Checked-in LinuxONE logs record previous training and inference on s390x, including median API request latency of roughly 90–134 ms over 20 calls for the recorded step-four runs. This is historical evidence for those runs, not a measurement of the current complete application.

## Required work, in recommended order

| Order | Deliverable | Current gap | Acceptance criterion |
|---|---|---|---|
| 1 | Durable analysis and incident state | `backend/app/analysis.py` stores uploads in the process-local `ANALYSES` dictionary. Restarting or switching workers loses access. | Upload, restart the API, reopen the same URL, and retrieve the same findings and network. Decisions and event progress also survive. |
| 2 | One reproducible LinuxONE release | `backend/deploy.ps1` ships only `backend/`; analysis imports sibling ML code and rules. The handoff reports stale remote ML code, missing processed files and no running ML service. Remote state was not independently checked in this review. | Both API services start from the documented release with the correct rule/config/model/data files. Health and model catalog checks pass; an actual prediction with explanation and a real upload work from the frontend. Record the served model versions. |
| 3 | A database-backed trace for one incident | The UI renders an upload grouping, while `backend/app/graph.py` follows only ingredient-product relationships and returns IDs. There are no create routes for organizations, shipments or batch relationships. Uploaded lot IDs are strings; database batch IDs are integers. | A seed/reset command creates one consistent incident. Selecting a batch shows its ingredients, related finished products and affected shipments/sites, using real stored relationships. A second simulated lab positive highlights their shared ingredient as an investigation lead. |
| 4 | Containment recommendation and officer decision | Notify produces a draft only; there is no stored recommendation, approval, rejection or action state. | Show a bounded recommendation with the affected lot/shipment IDs and evidence. Approve or reject it with an officer identity, timestamp and reason. The stored action state and decision history update and survive refresh/restart. Clearly label simulated execution. |
| 5 | Live event replay | Upload analysis processes the complete file once. The animation is illustrative and does not demonstrate a streaming decision system. `ColdChainMonitor.update` already accepts successive readings. | A controllable replay emits time-ordered readings to the backend. The UI updates evidence, alert and recommendation as events arrive. Pause/reset work, duplicate events do not double-count, and a late lab confirmation changes the proposed action. Label the source as a simulated stream. |
| 6 | A coherent use of ML | FSIS sample predictions and cold-chain upload findings are separate paths. FSIS sample positivity is not a batch-contamination probability or a temperature-based predictor. | The incident view shows each output's source and scope. Any historical sample attached to the synthetic scenario is explicitly identified. Use the sample model for inspection/testing priority, cold-chain rules for excursion evidence, and deterministic trace/decision logic for containment. Lab confirmation remains a distinct event. |
| 7 | Evidence of value and a submission package | There is no verified integrated before/after result in the reviewed demo. README and handoff differ. | Show scenario-derived affected sites, stock quantities with units, time to alert and time to decision. Compare no intervention, targeted holds and a broad hold under stated assumptions. Include architecture, model evaluation, limitations, setup, artifact versions, submission links and a backup recording. |

Build orders 3–6 around the same small seed dataset. Avoid implementing a general enterprise platform before this one path works.

## Concrete correctness fixes

1. **Insufficient evidence must be visible.** An input containing only `shipment_id,batch_id` is accepted and returns zero findings; the results page says no anomalies were found. Report which checks ran, which were unavailable and what evidence is missing. Zero findings must not read like a safety clearance. The legacy risk function also reports LOW if readings exist but all their temperatures are null.
2. **Scope graph identities correctly.** `distribution()` keys route nodes by route text alone. A local two-distributor case with the same `Cold` route produced one shared route node, making both distributors appear connected to both sets of downstream batches. Scope route IDs to distributor identity, preserve each batch's actual parentage, and derive Notify's supplier from the selected shipment path. `distribution/page.tsx` currently takes the first root as the supplier.
3. **Use one temperature policy.** The legacy shipment-risk endpoint uses a flat 7 °C threshold and scores reading counts; uploads use product profiles and elapsed-time rules. Apply the same profile and duration policy, or remove the legacy result from the demonstrated flow.
4. **Seed and validate database writes.** Missing organizations/shipments cause foreign-key failures in PostgreSQL. Add the minimal seed/import path and clear validation errors for nonexistent references and duplicate IDs. Test with foreign keys enforced.
5. **Make example mode explicit.** Results/distribution URLs without an analysis ID show fixtures, and the pending analysis is a module-level promise. Refreshing `/ml-process` loses that promise. Restore the current job by ID, or show a clear recovery screen; identify sample pages as examples.
6. **Bound network waits and show service status.** The shared frontend request helper has no request timeout. Make a disconnected service recoverable during the pitch. Include a preflight that checks both services and all required model families, rather than treating a single health response as full readiness.

## Suggested three-minute demonstration

This sequence describes work to implement and rehearse; it is not all available today.

1. **0:00–0:20 — The operational decision.** Introduce one food-safety officer and a chilled poultry lot whose truck is approaching its next delivery. Show quantities and destinations from the seed scenario.
2. **0:20–0:50 — Detect.** Start a clearly labelled simulated sensor stream. Show a temperature excursion and the evidence/time that causes an alert. Present model-based sampling priority separately, with the FSIS sample and model version identified.
3. **0:50–1:30 — Trace.** Inject simulated laboratory confirmation. Trace the lot into two finished products and their receiving sites. Highlight a shared ingredient as an investigation lead, without asserting causation.
4. **1:30–2:15 — Decide and respond.** Compare a targeted hold with a broader hold. Approve one recommendation; show the persisted decision and the simulated shipment/inventory state change.
5. **2:15–3:00 — Prove it.** Show the scenario-derived distribution avoided and inventory left unaffected, plus measured system latency, relevant model evaluation and LinuxONE execution evidence. Close on the officer's decision and its practical consequence.

Keep a deterministic scenario for the main presentation. The existing random sample spin is useful for questions after the core demonstration.

## How to present the existing science

- Lead with one model whose documented evaluation is understandable, such as poultry Campylobacter. Its card reports test PR-AUC 0.434, prevalence 0.198 and ROC-AUC 0.752 on x86. The registered threshold flags about 49% of samples and catches about 77% of positives. Present the workload tradeoff as well as the discrimination metric.
- Use the metrics for the actual served LinuxONE model in the final presentation; the evidence records small platform/version differences and a larger STEC PR-AUC difference.
- Identify random spins as validation-window samples, not an untouched final evaluation. Session tallies do not replace the formal evaluation.
- Preserve the documented restrictions: US FSIS sample scope, targeted sampling, assumed seven-day label lag, stale establishment history and limits to transfer across products or countries.
- Do not claim saved lives, prevented illness or deployed economic savings from synthetic scenario counts. Quantities held or distribution avoided are simulated operational outcomes under explicit assumptions.

## Defer until the core flow works

- New LLM/RAG pipelines, additional models and new datasets.
- More animation work or changing graph libraries.
- Production integrations for calls, email or regulatory recall execution. Simulated actions are sufficient if the approval and state changes are real and clearly labelled.
- Extensive CRUD, multi-tenant architecture and unrelated dashboards.

## Release acceptance checklist

- [x] Frontend production build succeeds; no development server was running during that build.
- [x] Existing backend checks and ML suite pass locally with normal runtime permissions.
- [ ] Seed/reset is repeatable and does not require manual database editing.
- [ ] Both LinuxONE services and the frontend can be started using the runbook.
- [ ] Upload → findings → trace → recommendation → decision works on one scenario.
- [ ] Restart/refresh retains the same incident and decision.
- [ ] Missing data and disconnected services show useful status rather than a successful-looking result.
- [ ] The live replay changes an alert/recommendation as new evidence arrives.
- [ ] Measured latency is separated from animation time and measured on the presented deployment.
- [ ] Three consecutive rehearsals complete without manual repair.
- [ ] Backup video, setup instructions and required submission materials are ready.

## Verification notes

The initial ML-suite attempt hit sandbox temporary-folder creation errors. A second attempt using a writable temporary directory stalled and was stopped; the complete rerun with normal runtime permissions passed. The frontend production build also passed outside the sandbox after a restricted filesystem failure. The offline Person A data pipeline was not rerun or modified. No browser walkthrough or current remote-deployment verification was performed. No remote deployment, production database or application source code was changed; this report is the only new review artifact.
