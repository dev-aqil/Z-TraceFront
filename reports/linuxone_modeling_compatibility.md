# LinuxONE (s390x) modeling dependency compatibility — Person B

Status date: 2026-10-17. Owner: Person B. Complements Person A's [linuxone_portability.md](linuxone_portability.md), which covers the standard-library data pipeline. **No s390x execution has been performed.** Classifications rest on the evidence below, not on a target run.

## Evidence gathered

1. **PyPI wheel listing** (pypi.org JSON API, latest release, queried 2026-10-17). Counts files whose name contains `s390x`.
2. **Debian package archive** (`qa.debian.org/madison`, arch `s390x`, or `all` for pure-Python packages). Debian builds and normally runs upstream tests on every architecture, so a published s390x binary means it built (and usually tested) there. The target distribution (RHEL/SLES/Ubuntu/Debian) is **not yet confirmed**.
3. **Local version-compatibility run** (x86_64, Python 3.13). The full `food-risk-ml` suite (84 tests) passed both with the latest versions and with versions matching Debian 13 "trixie" (numpy 2.2.4, pandas 2.2.3, scipy 1.15.3, matplotlib 3.10.1, joblib 1.4.2, xgboost 3.0.0, fastapi 0.115.11, pydantic 2.10.6). The one exception is scikit-learn: 1.5.2 was used because trixie's 1.4.2 has no Python 3.13 wheel. The suite also passed with `shap` and `xgboost` **uninstalled**. This verifies API compatibility of those versions, not the s390x architecture.

| Package | PyPI s390x wheels (latest) | Debian s390x package | Classification | Notes |
|---|---|---|---|---|
| Python | n/a | python3 (trixie: 3.13) | **SUPPORTED** | Use the distro Python; record version and ABI |
| NumPy | 0 (2.5.4) | 2.2.4 trixie, 2.4.6 sid | **LIKELY_SUPPORTED** via distro; pip = REQUIRES_BUILD | Source build needs a compiler plus BLAS/LAPACK |
| pandas | 0 (3.0.6) | 2.2.3 trixie (`python3-pandas-lib`) | **LIKELY_SUPPORTED** via distro | Code verified on 2.2.3 |
| Polars | 0 (Rust build) | none | **AVOID** | Not needed |
| SciPy | 0 (1.18.1) | 1.15.3 trixie | **LIKELY_SUPPORTED** via distro | pip build needs Fortran + BLAS |
| scikit-learn | 0 (1.9.1) | **1.4.2 trixie**, 1.9.0 forky/sid | **LIKELY_SUPPORTED**, with a version gap | `food-risk-ml` requires ≥ 1.5 (verified on 1.5.2). On trixie, use Debian testing's 1.9.0, build 1.5+, or verify on 1.4.2 first. |
| joblib | pure Python | 1.4.2 trixie | **SUPPORTED** | Pickles are **not** portable across library versions (see below) |
| XGBoost | 0 (3.4.1); `xgboost-cpu` also 0 | 3.0.0 trixie, 3.3.0 sid | **REQUIRES_BUILD** via pip / LIKELY_SUPPORTED via distro | `pip install xgboost` 3.x declares `nvidia-nccl-cu13` on all Linux, which has no s390x build. Use the distro package or a source build. It is optional in `food-risk-ml` (`[boost]` extra). |
| LightGBM | 0 (4.7.0) | none | **AVOID** | CMake/C++ build, no distro package; not offered |
| SHAP | 0 (0.54.1) | none | **REQUIRES_BUILD** | sdist with a C extension; pure-Python dependencies (0.54 no longer needs numba). Optional (`[explain]` extra). Fallbacks: permutation importance, coefficients, XGBoost `pred_contribs`. |
| matplotlib | 0 (3.11.2; pillow 0) | 3.10.1 trixie | **LIKELY_SUPPORTED** via distro | kiwisolver and contourpy publish s390x wheels; matplotlib and pillow do not |
| FastAPI / Starlette | pure Python | 0.115.11 trixie | **SUPPORTED** | — |
| pydantic-core | **8 s390x wheels** | pydantic 2.10.6 trixie | **SUPPORTED** | — |
| uvicorn | pure Python | — | **SUPPORTED** (plain) | The `[standard]` extras (uvloop, httptools) are native and unverified; `food-risk-ml` now depends on plain `uvicorn` |
| PyArrow / Parquet | 0 (26.0.0) | none in trixie | **AVOID** for now | Matches Person A: CSV + JSON schema interchange |

## s390x-specific risks

| Risk | Mitigation |
|---|---|
| **Big-endian byte order** | Don't move binary model files from x86 to s390x. Retrain on the target. Record `sys.byteorder` in run metadata (done). For XGBoost use `save_model("*.json")` (text). Person A's CSV/JSON interchange is endian-neutral. |
| **Pickles tied to library versions** | Verified locally: loading the registered FSIS model (scikit-learn 1.9.1) under 1.5.2 emits `InconsistentVersionWarning`, and fails outright without xgboost. **Retrain on LinuxONE with the target's pinned versions.** The API now starts in `no_model` state and reports the load error on `/health` instead of crashing. |
| Missing optional packages | XGBoost and SHAP are optional extras; every model sequence and the API work without them (tested) |
| Thread oversubscription | Set `OMP_NUM_THREADS` and `n_jobs` explicitly on shared LinuxONE LPARs |

## Recommended environment

1. Prefer the **distribution's Python packages** (Debian/Ubuntu `python3-numpy`, `python3-pandas`, `python3-sklearn`, `python3-scipy`, `python3-matplotlib`, `python3-joblib`, optional `python3-xgboost`). Create the venv with `--system-site-packages` and pip-install only the pure-Python pieces (`fastapi`, `uvicorn`, `httpx`, `pytest`).
2. If the distro's scikit-learn is older than 1.5, either use a newer distro channel or run the test suite on that version before relaxing the floor.
3. Build SHAP from source only if SHAP output is required; otherwise use the portable explainers.
4. Conda channels for s390x: **UNKNOWN**, not verified here.

## Verification commands for the first LinuxONE session

```bash
uname -m && python3 -c "import sys,platform;print(platform.python_version(), sys.byteorder)"
python3 -c "import numpy,pandas,sklearn,scipy,joblib,matplotlib;print(numpy.__version__,pandas.__version__,sklearn.__version__,scipy.__version__)"
python3 -c "import xgboost;print(xgboost.__version__)" || echo "xgboost absent (optional)"
python3 -c "import shap;print(shap.__version__)" || echo "shap absent (optional)"
cd food-risk-ml && PYTHONPATH=. python3 -m pytest -q        # 84 tests, synthetic data only
```

Record the outputs in this report, then change classifications to SUPPORTED only where the run passes.
