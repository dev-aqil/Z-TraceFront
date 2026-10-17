# Model card: imidacloprid detection model (USDA PDP 2024)

**Model version:** `chemical-imidacloprid-random_forest-20261017T133020Z` (random forest, Platt-calibrated)
**Trained:** 2026-10-17 from Person A's model-ready handoff `chemical_imidacloprid_detection_training_v1`. Provenance: `artifacts/registry_chemical_imidacloprid/<version>/metadata.json`.
**Status:** a retrospective association model for prioritising residue testing. It is a **CHEMICAL** model, completely separate from the pathogen models. Its probability is never combined with a Salmonella, Campylobacter or cold-chain score.

## What it predicts

- **Target:** `imidacloprid_detected`. For one USDA Pesticide Data Program (PDP) 2024 sample, does the original-extraction analysis detect imidacloprid (analyte 967, parent compound only)?
  - 1 = publisher MEAN `O` (detection)
  - 0 = MEAN `ND`, a validated well-recovered nondetect
  - excluded: `NP` (marginal-performing nondetect) and `R` (re-extraction)
- **A detection is not an exceedance.** The label says nothing about legal tolerances, and a detection does not mean unsafe food. A nondetect is relative to the assay: it does not mean zero residue, no pesticides, or safe food.
- **Scope: `RETROSPECTIVE_RELEASE_COHORT_ONLY`.** All 2024 labels were released together after the cohort. The model shows which 2024 samples resembled the ones where imidacloprid was found. It does **not** show that a model trained during 2024 would have worked in real time, and it makes no claim about other years, other countries (including Malaysia) or new farms.

**Output:** a probability, a risk band and SHAP contributions.
- `high`: score ≥ 0.024 (validation 80%-recall threshold)
- `medium`: from the validation 95%-recall net
- `low`: below that. Low does not mean no residue.

## Data

| | Rows | Detections | Prevalence | Collection dates |
|---|---|---|---|---|
| Train | 6,913 | 291 | 4.2% | 2024-01-02 → 2024-09-09 |
| Validation | 1,540 | 53 | 3.4% | 2024-09-10 → 2024-11-05 |
| Test | 1,418 | **46** | 3.2% | 2024-11-06 → 2024-12-23 |

- **Split:** Person A's audited temporal split on whole collection days. The training code re-applies it and checks that row and class counts match the audit exactly (`reports/m7_validation.json`, `split_audit`).
- **Gate:** the readiness file must say `model_ready: true` (a JSON boolean) and `leakage_audit_passed: true`. The SHA-256 of the dataset, feature manifest and leakage audit must match the pins. Undeclared columns are rejected, and the target contract must be `READY`. The contract was reviewed on 2026-10-17; see `reports/modeling_target_contracts.md`.
- **Line endings:** Windows checkouts used to convert line endings, which broke the pins. `.gitattributes` now keeps these files byte-exact.

## Features

There are 7 features, all from Person A's whitelist, all native sample descriptors fixed at collection:
- commodity
- commodity form (fresh/frozen/purée)
- origin (domestic/import/unknown)
- import-origin country (null for domestic or unknown, never imputed)
- label claim
- sample unit count (null is unknown, never zero)
- collection day-of-week

**Excluded before any training:** day-of-year and ISO week. The temporal split leaves no overlap: training covers day 2–253, validation 254–310 and test 311–358. Those features could only extrapolate into months the model never saw.

Every analytical-result field is forbidden: MEAN, CONCEN, LOD, ANNOTATE, QUANTITATE, CONFMETHOD, EXTRACT, DETERMIN, LAB and TESTCLASS. So are tolerances, recalls, history, and variety text.

## Procedure

- **Candidates:**
  - prior-rate dummy
  - **commodity-rate baseline:** each commodity's training detection rate, smoothed with 20 pseudo-samples
  - logistic regression, random forest, XGBoost, each in an sklearn `Pipeline`, with class reweighting and the same hyperparameters as the pathogen models
- **Selection:** best validation PR-AUC among the learned models. The tie rule (within 0.005, preferring XGBoost) did not apply: RF scored 0.148 against XGBoost's 0.139.
- **Calibration:** Platt on validation scores, applied because out-of-fold Brier fell from 0.149 to 0.032.
- **Threshold:** validation only, at ≥ 80% recall.
- **Pre-registered success criterion:** the learned model must beat the commodity-rate baseline on test, by a paired bootstrap (2,000 resamples) whose 95% interval excludes zero.

## Results

**Test period, 1,418 samples, 46 detections.** The 95% bootstrap intervals are wide because there are so few detections.

| Model | PR-AUC [95% CI] | ROC-AUC | Recall @10% budget | @20% | @30% |
|---|---|---|---|---|---|
| Dummy (prior rate) | 0.032 | 0.50 | 0.10 | 0.20 | 0.30 |
| **Commodity-rate baseline** | 0.104 [0.070, 0.147] | 0.83 | 0.36 | 0.57 | **0.93** |
| Logistic regression | 0.134 [0.088, 0.202] | 0.85 | 0.40 | 0.70 | 0.89 |
| XGBoost | 0.158 [0.099, 0.249] | 0.85 | 0.49 | 0.70 | 0.87 |
| **Random forest + Platt (registered)** | **0.161 [0.103, 0.249]** | **0.86** | **0.52** | **0.76** | 0.87 |

**Does the model add value beyond commodity?** These are paired bootstrap differences in PR-AUC, model minus commodity baseline:

| Split | Difference | 95% CI | Resamples where model is better |
|---|---|---|---|
| Test | **+0.057** | **[+0.023, +0.124]** | 100% |
| Validation | +0.047 | [−0.024, +0.127] | 92% |

What this means:
- **The criterion is met on test.** The interval excludes zero. On validation the gain points the same way but is not conclusive. With about 50 detections per split, the evidence is moderate, not strong.
- **Inspection budget:** testing the top-scored 10% of samples would have caught **52% of detections (5.2× random)**, against 36% for commodity alone. The model helps most for tight budgets. At a 30% budget the commodity baseline is as good or better (0.93 vs 0.87), because the few high-risk commodities fill that budget by themselves.
- **At the operating threshold:**
  - 44 of 46 detections caught (recall 0.96)
  - precision 6.3% against a 3.2% base rate
  - about half of all test samples flagged
  - The threshold is a policy choice. The budget view above is more useful for planning.
- **Calibration:** Brier 0.029 on test.

**Ablation (decided before training).** Restoring day-of-year and ISO week gives test PR-AUC 0.152 [0.095, 0.243], against 0.161 without them. Dropping them cost nothing.

**Explainability.** Global mean |SHAP| on test, in probability units, for the uncalibrated forest:

| Feature | Mean \|SHAP\| |
|---|---|
| commodity | 0.240 |
| sample unit count | 0.104 |
| import-origin country | 0.069 |
| label claim | 0.028 |
| commodity form | 0.023 |
| origin | 0.013 |
| day-of-week | 0.011 |

These describe which inputs move the score. They are associations within the 2024 cohort, **not causes**.
- Unit count probably reflects commodity-specific sampling protocols, not anything about the residue.
- Per-request SHAP on this forest takes about 30 ms per sample on x86.

## LinuxONE (IBM Z)

The model was retrained on the LinuxONE VM (s390x, big-endian) from commit `6513e9f`, with Person A's handoff files byte-exact. Evidence is in `reports/linuxone_evidence/chemical/`.
- The hash gate passed.
- 100 tests passed.
- Training took 18 s.
- The same random forest was selected, with identical test results (PR-AUC 0.161, ROC-AUC 0.859, recall@10% 0.517).

## Limitations

- **Few detections.** 46 test and 53 validation positives make every metric uncertain. Read the intervals, not the point estimates.
- **One year, one analyte.** No evidence about other years, metabolites or other pesticides.
- **The test period was looked at once.** This run is the evaluation, and nothing was tuned on test. Person A's split has no separate sealed period, so any further model change should be judged on validation, or on a new release (PDP 2025).
- **Commodity mix drives most of it.**
  - Several commodities never had a detection, and one (`FS`) appears only in validation and test.
  - Commodities differ in assay sensitivity, so part of what the model learns is the detectability of imidacloprid in each commodity, not exposure risk.
- **No farm, lot or supplier grouping.** Repeated upstream sources may sit on both sides of the split, so there is no new-farm or facility transfer claim.
- **Country null mixes** domestic non-applicability with unknown import origin.
