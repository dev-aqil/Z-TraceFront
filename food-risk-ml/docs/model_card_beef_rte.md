# Model cards: raw beef (Salmonella, STEC) and ready-to-eat (*Listeria monocytogenes*)

This document covers three separate models. They are trained on 2026-10-17 with the same pipeline and protocol as the poultry models (`docs/model_card.md`), on real FSIS data. Each has its own mapping, canonical table, registry and reports. **None is combined with any other score**: pathogen, chemical and cold-chain outputs stay separate.

| Model key | Version | Target | Source |
|---|---|---|---|
| `beef_salmonella` | `beef_salmonella-xgboost-20261017T141151Z` | `salmonella_sp_analysis` | FSIS Raw Beef Sampling FY2014–FY2026 |
| `beef_stec` | `beef_stec-xgboost-20261017T141331Z` | `stec_analysis` (all O-groups) | same files |
| `rte_listeria` | `rte_listeria-xgboost-20261017T141626Z` | `lm_listeria_analysis` (*L. monocytogenes*) | FSIS RTE Product Risk-based Lm Sampling FY2014–FY2026 |

## Shared facts

**Data.** 13 fiscal-year JSON files per product, downloaded 2026-10-17 from fsis.usda.gov. The embedded metadata has creation date October 09, 2026. All 26 zips match the SHA-256 recorded at download (`data/raw/fsis_raw_beef/`, `data/raw/fsis_rte/`). Only the primary table is used, one row per `form_id`.

**Labels.**
- `Positive` = 1 and `Negative` = 0.
- `Confirmed Negative of a Previous Presumptive` = 0: 29 STEC and 60 Lm rows. The data dictionary does not define this value; it is read literally as a screen that confirmation ruled out.
- `NULL` and lab-problem codes give no label.

**Features (pre-sampling only):**
- project code
- sample source
- establishment state
- RTE only: production alternative, the plant's declared Lm control
- collection month
- establishment history from **strictly earlier results of the same pathogen**, counted if `collection_date + 7 days < sample date` (an assumed lag, as for poultry)

Category spellings are merged (`ALT 3` and `Alt 3`, for example), and the same normalisation is applied to API requests.

**Excluded by design:**
- every other result for the same sample: the PCR stx/eae screens behind the STEC result, other Listeria species, MPN/plate counts, and the other pathogen
- `not_analyzed` and `*_canceled` fields
- establishment names and numbers

**Split.** The same fixed dates as every pathogen model: train up to 2023-02-21, validation 2023-02-22 → 2024-10-10, test 2024-10-11 → 2026-06-30.

**Selection.** Best validation PR-AUC, unless the validation data cannot tell two models apart: a paired bootstrap (1,000 resamples) 95% interval of the difference that includes 0. A tie goes to XGBoost, then logistic regression, then random forest, because XGBoost is fast and explains itself on IBM Z without the SHAP package.
- This rule replaced a fixed 0.005 tolerance on 2026-10-17, **after** seeing that STEC's forest led on validation. A fixed tolerance is meaningless when PR-AUCs are around 0.01.
- The rule is applied the same way to every model. For Campylobacter, beef Salmonella and poultry Salmonella it gives the same choice as before.

**Calibration and threshold.** Platt on validation, applied in all three because it cut out-of-fold Brier sharply. The threshold is chosen on validation at ≥ 80% recall.

## Results

### Rolling backtest (development data, four fiscal years FY2021–FY2024, XGBoost)

| Model | Base rate | PR-AUC mean (min fold) | ROC-AUC | Positives caught at a 10% / 20% / 30% testing budget |
|---|---|---|---|---|
| Beef Salmonella | 1.7% | 0.076 (0.068) | 0.77 | 41% / 59% / 71% |
| Beef STEC | 0.27% | 0.021 (0.007) | 0.73 | 34% / 57% / 65% |
| RTE Listeria | 0.6% | 0.044 (0.027) | 0.77 | 46% / 58% / 68% |

The dummy baseline catches 10% / 20% / 30% by definition. Per-fold results and bootstrap intervals are in `reports/<key>/backtest/`.

### Test period (Oct 2024 – Jun 2026), registered model with the validation threshold

| Model | Samples (positives) | PR-AUC | ROC-AUC | Recall | Share flagged `high` | Brier |
|---|---|---|---|---|---|---|
| Beef Salmonella | 33,803 (468) | 0.058 (4.2× base) | 0.72 | 0.67 | 36% | 0.013 |
| Beef STEC | 33,803 (115) | 0.018 (5.3× base) | 0.63 | 0.81 | 66% | 0.003 |
| RTE Listeria | 40,536 (273) | 0.032 (4.7× base) | 0.76 | 0.85 | 62% | 0.007 |

Test PR-AUC of the other candidates, reported only, never used to choose:

| Model | Logistic regression | Random forest | XGBoost (registered) | Dummy |
|---|---|---|---|---|
| Beef Salmonella | 0.055 | 0.050 | **0.058** | 0.014 |
| Beef STEC | 0.006 | 0.009 | **0.018** | 0.003 |
| RTE Listeria | 0.040 | **0.047** | 0.032 | 0.007 |

### Per-model notes

**Beef Salmonella.**
- Validation picked XGBoost. Logistic regression was statistically tied (difference +0.006, CI [−0.0002, +0.013]), and the forest was significantly worse.
- Test recall at the threshold fell to 0.67 against 0.80 on validation, so the test period drifted.
- Top drivers (mean |SHAP|, log-odds): establishment history 0.73, **collection month 0.58** (seasonality), state 0.35, project 0.33.

**Beef STEC.** This is the weakest model.
- With 0.3% positives, PR-AUC is low in absolute terms. Year-to-year it ranged 0.007–0.047 in the backtest, and test ROC-AUC is 0.63.
- **The tie was borderline.** On validation the forest led (0.022 vs 0.011), with paired difference CI [−0.001, +0.042] and the forest better in 95% of resamples. The backtest ranked XGBoost first (0.021 vs 0.012), and so did the test period (0.018 vs 0.009).
- Use it only to order which lots to test first. Top drivers: project code 0.92 (follow-up projects MT44/MT52/MT53 are triggered by earlier positives), state 0.89, sample source 0.61.

**RTE Listeria.**
- **On the test period XGBoost scored below the forest and logistic regression.** Validation could not separate the three, and the backtest had them level (0.044 / 0.042 / 0.046). Changing the model after seeing test results would invalidate the test, so XGBoost stays and this is reported instead.
- **Most of the ranking is between sample types.** On test:

| Test period | Samples | Positives | Base rate | PR-AUC | ROC-AUC | Recall at threshold | Flagged |
|---|---|---|---|---|---|---|---|
| RTE product | 23,681 | 78 | 0.33% | 0.028 (8.5×) | 0.68 | 0.79 | 60% |
| Food-contact surface | 13,450 | 68 | 0.51% | 0.011 (2.2×) | 0.59 | 0.63 | 58% |
| Non-food-contact surface | 3,373 | 127 | 3.8% | 0.049 (1.3×) | 0.57 | 1.00 | 99.6% |

  - Non-food-contact sponges (floors, drains) are positive about 11× as often as product, and almost all of them are flagged.
  - Within a sample type, discrimination is modest: usable for **product** ranking, weak for surfaces.
  - These figures were computed from the registered model on the test split. They are analysis only, and nothing was chosen from them.
- Top drivers: sample source 1.07, establishment history 0.53, state 0.52.

## LinuxONE (IBM Z)

All three models were retrained on the LinuxONE VM. Evidence is in `reports/linuxone_evidence/step4/`.
- **Tests:** 113 passed; the 2 SHAP-comparison tests are skipped because SHAP has no s390x package.
- **Explanations:** the API returns explanations on IBM Z through XGBoost's built-in TreeSHAP, at 90–140 ms median latency per request.
- **Results** match x86 for beef Salmonella (0.058) and RTE Listeria (0.032).
- **STEC is the exception.** On s390x the selection rule fell on the other side of its borderline tie and picked the forest, which cannot explain itself there. The x86 choice was therefore **pinned** (`train --model xgboost`) and retrained on IBM Z, giving test PR-AUC 0.011 against 0.018 on x86 (xgboost 2.0.3 vs 3.4.1; same ROC-AUC 0.63).

## Limitations (all three)

- **The test period has now been scored once.** Further changes must be judged on the backtest and validation. The final sealed scoring at the end of the project is the last use of this period.
- **Targeted sampling.** Follow-up and intensified projects are triggered by earlier positives, so the models partly learn FSIS targeting policy.
- **Method scope.** STEC "all O-groups" testing may differ by project and over the years. Nothing in the data shows an obvious step change, but this is not verified.
- **Assumed 7-day result lag** for history; stale history after 2026-06-30; small plants shrink toward the mean.
- **RTE Salmonella was not modelled:** 6 test positives cannot support any claim.
- **None of these is a safety verdict** or a lot-release decision. A low score does not mean safe.
