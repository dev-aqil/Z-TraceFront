# Modeling target contracts — Person B

Status date: 2026-10-17. Owner: Person B. Machine-readable version used by code: [food-risk-ml/configs/modeling/targets.toml](../food-risk-ml/configs/modeling/targets.toml). The experiment runner refuses any target whose status is not `READY`. **Every target is currently blocked.**

Each problem type below is separate. Outputs from different targets are never combined into one probability, and rows from different targets are never concatenated into one training table.

## Summary

| Target | Domain | Type | Status | Unblocked by |
|---|---|---|---|---|
| `pathogen_positive` | Biological | binary | `BLOCKED_PENDING_PERSON_A_FSIS_HANDOFF` | Person A FSIS intake + model-ready handoff |
| `pesticide_detected` | Chemical | binary | `BLOCKED_PENDING_PDP_CODE_SEMANTICS` | Person A documents the MEAN/ANNOTATE/re-extraction rules that define detection |
| `residue_concentration` | Chemical | regression (censored) | `BLOCKED_PENDING_CENSORING_POLICY` | Agreed handling of nondetects below LOD |
| `chemical_exceedance` | Chemical | binary | `BLOCKED_NO_AUTHORITATIVE_LIMITS` | Tolerance table with effective dates, residue definitions, commodity mapping |
| `microbial_count` | Cold chain | regression | `BLOCKED_PENDING_SOURCE` | Milk/paneer/beef source acquired and cleaned |
| `spoilage_class` | Cold chain | multiclass | `BLOCKED_PENDING_SOURCE` | Same |
| `cold_chain_failure` | Cold chain | binary | `BLOCKED_PENDING_SOURCE_AND_RULE` | Sensor source + failure rule fixed before looking at outcomes |
| `storage_condition_class` | Cold chain (proxy) | binary | `BLOCKED_PENDING_SOURCE` | Fruit storage source acquired |

**Not targets, ever:** openFDA recall/enforcement (a regulatory action with no tested-negative denominator), FDA NAI/VAI/OAI inspection classification (a compliance classification), NOAA weather, and OpenDOSM agricultural statistics. The handoff gate rejects any target name without a contract.

### Note on FSIS

Person A's inventory still lists FSIS as pending. Person B has separately downloaded the official FY2014–FY2026 files and trained an **exploratory** model from Person B's own mapping. That model is documented in [food-risk-ml/docs/model_card.md](../food-risk-ml/docs/model_card.md); it reached a test PR-AUC of 0.30 against a 0.098 base rate. It did **not** go through a Person A model-ready handoff, so it is not this plan's production evaluation. Person A can reuse the files and their hashes (`food-risk-ml/data/raw/fsis_raw_poultry/DOWNLOAD_PROVENANCE.json`).

---

## A. Biological

### `pathogen_positive`

| Field | Contract |
|---|---|
| Scientific meaning | An official laboratory result for **one named analyte** (e.g. Salmonella) on **one sample** reports it detected |
| Unit / grain | 0/1 per sample × analyte. One model per analyte. |
| Type | Binary classification |
| Positive class | Official lab-positive result for that analyte (FSIS `salmonella_sp_analysis = "Positive"`) |
| Negative class | Official lab-negative result for that analyte on a tested sample |
| Missing | Untested, cancelled, not analysed, indeterminate → **no label**, row excluded. Absence of a result is never a negative. |
| Acceptable sources | FSIS laboratory sampling, primary test table only. Later: other official microbiological testing programmes, as separate cohorts. |
| Forbidden labels / proxies | Recall, enforcement action, investigation outcome, outbreak association, inspection classification, any other analyte's result |
| Prediction time | Sample collection (date boundary) |
| Expected inputs | Sampling programme, product type, establishment state, collection month, establishment history computed only from results available before the prediction time |
| Major leakage risks | Same-sample results for other pathogens. Secondary tests (serotype, allele, PFGE/WGS, AMR) exist only because the result was positive. `not_analyzed`/cancellation fields. History counted without a result-availability lag. Follow-up sampling programmes (`F_*`) encode earlier failures. These are legitimate inputs, but they must be documented. |
| Readiness | `BLOCKED_PENDING_PERSON_A_FSIS_HANDOFF` |

## B. Chemical

The PDP 2024 tables are cleaned (M2) but not model-ready. **A PDP detection is not a regulatory exceedance.**

### `pesticide_detected`

| Field | Contract |
|---|---|
| Scientific meaning | For one sample and one pesticide (PESTCODE), the analytical result is a detection |
| Unit / grain | 0/1 per sample × pesticide. Re-extraction and duplicate analytical rows must be resolved to one determination per sample × pesticide by a rule Person A documents. |
| Type | Binary classification; one model per pesticide or pesticide family, decided per experiment |
| Positive class | Detection **as defined by Person A's documented semantics** of MEAN (ND/NP/O/R), CONCEN, LOD and ANNOTATE. Person B does not define these codes. |
| Negative class | Tested and not detected (ND), per the same documentation |
| Missing | Untested pesticides for a sample are absent, not negative. Codes with unclear meaning give no label. |
| Acceptable sources | USDA PDP (2024 now; other years only as separate, explicitly pooled releases) |
| Forbidden labels / proxies | Recalls, tolerances, any concentration-derived field of the same sample |
| Prediction time | Sample collection date |
| Expected inputs | Commodity, commodity type, claim, origin/country, sampling state, distribution type, month |
| Major leakage risks | CONCEN/LOD/MEAN/ANNOTATE/QUANTITATE/CONFMETHOD of the same sample × pesticide. Other pesticides' results on the same sample (multi-residue co-occurrence) are same-sample lab results, so they are excluded by default. Lab and test-class fields affect detection limits (see the feature requirements). |
| Readiness | `BLOCKED_PENDING_PDP_CODE_SEMANTICS` |

### `residue_concentration`

| Field | Contract |
|---|---|
| Scientific meaning | Measured residue concentration of one pesticide in one sample |
| Unit | ppm (PDP CONUNIT = M), **left-censored**: nondetects are below an LOD, not zero |
| Type | Regression, censored. Candidate approaches: a detection model (above) plus a conditional model of log concentration among detections, or a censored-regression model. Choosing one is the blocking decision. |
| Forbidden proxies / leakage | Same as `pesticide_detected`. Imputing nondetects as 0 or LOD/2 without a documented policy is forbidden. |
| Readiness | `BLOCKED_PENDING_CENSORING_POLICY` |

### `chemical_exceedance`

| Field | Contract |
|---|---|
| Scientific meaning | A residue exceeds the **applicable legal limit** for that commodity, residue definition and date |
| Positive class | **Undefined.** It needs an authoritative tolerance with an effective date, a residue definition and a commodity mapping. Detection is never substituted for it. |
| Readiness | `BLOCKED_NO_AUTHORITATIVE_LIMITS` |

## C. Cold chain and spoilage

No source has been acquired. These are separate experiments with different organisms, units and labels. They may share a model only after units and labels are harmonised and documented.

| Target | Meaning | Type / unit | Forbidden proxies | Prediction time | Readiness |
|---|---|---|---|---|---|
| `microbial_count` | Measured microbial load (e.g. TVC) | regression, log10 CFU/g or /ml, with a declared unit column | Spoilage/freshness class derived from the same count; the count itself | A declared storage time before the measurement | `BLOCKED_PENDING_SOURCE` |
| `spoilage_class` | Publisher's spoilage or freshness class | multiclass (ordered where documented) | TVC or other measurements that **define** the class | Same | `BLOCKED_PENDING_SOURCE` |
| `cold_chain_failure` | A pre-registered failure rule (e.g. > X °C for ≥ Y min) is met **after** the prediction cutoff | binary | Any reading after the cutoff; final-trip totals. Computing the rule from the same readings used as features is rule reproduction, not prediction. | A cutoff part-way through the batch/shipment | `BLOCKED_PENDING_SOURCE_AND_RULE` |
| `storage_condition_class` | Fruit dataset Good/Bad storage condition | binary | The variables that mechanically define the class | Same | `BLOCKED_PENDING_SOURCE`. A **proxy**: never renamed to a microbial or pathogen label. |

## Changing a status

A status becomes `READY` only by editing `targets.toml` **and** recording the reason here (date, evidence, reviewer). Code defaults never change it.
