# LinuxONE/s390x data-pipeline portability — M0

Target: IBM Z LinuxONE, Linux **s390x**, for eventual training and pipeline execution. Person A scope remains data ingestion → cleaning → features → validation → handoff. No training performance optimization or deployment infrastructure belongs in this milestone.

## M1 update — implemented scope

The expanded acquisition also uses `zipfile`, `csv`, fixed-width text, `hashlib` and `xml.etree.ElementTree` from the standard library. PDP's bundled Microsoft Access `.MDB` is preserved as publisher bytes but is not opened or required: the annual text files and embedded PDF/XLSX reference tables provide the documented portable route. No Access, ODBC, pandas, NumPy, PyArrow, Excel application or architecture-specific wheel is required. The small PDP reference XLSX is inspected as ZIP/XML only; this is not a general spreadsheet/date/formula importer.

The already installed `pdftotext` executable (Poppler) was used once as a local documentation-review aid. It is a native external utility, not an ingestion runtime or test dependency. On s390x use a distribution-supported Poppler package if desired, or read the preserved PDFs manually; compilation/installation is unnecessary for reproduction of this pipeline. Python itself needs ordinary SSL/zlib support supplied by the target OS. No LinuxONE/s390x execution has been performed.

M1 ingestion, hashing, HTTP capture, CSV/JSON inspection and manifest verification remain standard-library-only. There are **zero third-party runtime packages and no new native-compilation requirement**. Immutable publication uses POSIX same-filesystem hard links under each artifact directory; the intended LinuxONE filesystem must support ordinary hard links. Cross-host/source files are copied into a temporary file in the destination directory first, so imports do not require a hard link across filesystems.

`uv.lock` now pins optional development tooling, with `requirements-dev.lock` exported for hash-checked pip installation without uv. The resolved test dependencies are pytest 9.1.1, iniconfig 2.3.1, packaging 26.3, pluggy 1.7.0 and Pygments 2.21.0; Colorama 0.4.6 is Windows-only. Their recorded wheels use `none-any` tags. These are test tools, not data/model libraries. The environment was installed locally with Python 3.11, with no package build and no native dependency. This does not substitute for an actual s390x execution check.

Run-time CLI needs only Python 3.11+ and normal HTTPS certificate support. No Parquet engine is installed or exercised in M1; raw JSON/CSV is retained and CSV inspection streams rows. JSON inspection has a documented 128 MiB limit; artifacts can be captured up to 256 MiB without loading them all into memory. A larger release needs a single-FY export or a bounded parser rather than assuming unlimited RAM. NumPy, pandas, PyArrow and their source-build decisions below remain future gates, with no model-training optimization performed.

## Current evidence

M0 code uses Python standard-library modules only and has no native extension, GPU library, architecture check, x86 instruction dependency or downloaded executable. It runs directly with `PYTHONPATH=src` on the local **x86_64** machine. Tests were run with Python 3.11.17 and 3.14.7. **No s390x execution or target dependency installation has been performed.** Source portability is not a claim of tested target compatibility.

Local `uv` is a convenience for future dependency resolution, not a target runtime requirement. Use standard `python -m venv` / `python -m pip` on LinuxONE if a vetted uv distribution is unavailable. Do not install an x86_64 uv executable on s390x. Record the target distro, Python ABI, libc, architecture and package provenance before resolving native packages in M1.

## Planned dependency decisions

These are candidates, not installed or version-locked dependencies. Confirm a supported build for the actual target interpreter/distro before adopting them. A package supporting Linux in general does not guarantee a wheel for s390x.

| Package | Proposed purpose | Native compilation / target gate |
| --- | --- | --- |
| Python standard library | HTTP/download streaming, CSV/JSON parsing, hashing, timestamps, manifests | M0 runtime only; no added compiled package. TLS, timezone database and OS Python availability still depend on target installation. |
| NumPy | Numerical operations in M2+ | Native compiled components; source builds need documented compilers/build dependencies and may use a system BLAS. Do not reuse x86-built wheels or machine-specific BLAS artifacts. Check native s390x package/wheel or supported distribution channel. |
| pandas | Source-specific tabular cleaning/features | Compiled extensions; may need a source build and NumPy/build-tool dependencies. Prefer a target-supported version over blindly reproducing the local global environment. |
| PyArrow | Parquet read/write | Native Arrow C++ libraries plus Python bindings; source builds can require CMake, C++ toolchain, Cython and chosen compression libraries. Verify supported architecture, byte-order behavior and an actual Parquet round trip on s390x. Do not assume pip wheels exist or attempt a large compile during M0. |
| openpyxl | Read paneer XLSX if selected | Mostly pure Python; inspect resolved dependencies. Treat cached/formula cells and units explicitly; this does not replace CSV/Parquet intermediate outputs. |
| pytest (optional dev) | Later data/feature validation runner | Core Python tool; resolve its dependencies for target Python. M0 tests also run with stdlib unittest, so no install is needed now. |
| setuptools (build only) | Build/install the offline Python package | Pure Python packaging tooling; not needed for direct `PYTHONPATH` audit execution. Freeze build tooling with the M1 environment. |

Primary references: [NumPy source-build guide](https://numpy.org/doc/stable/building/index.html), [pandas installation guide](https://pandas.pydata.org/docs/getting_started/install.html), [PyArrow installation](https://arrow.apache.org/docs/python/install.html) and [PyArrow source-build guide](https://arrow.apache.org/docs/developers/python/building.html). These explain native build paths; they do not establish that this project's eventual locked set has been tested on LinuxONE.

Do not default to architecture-limited accelerators or extra compiled frameworks. Polars/Numba and alternative Parquet engines are not added speculatively. Existing application dependencies (e.g. psycopg2 and Pydantic's native core) have their own portability requirements and are deliberately not inherited by the offline data package.

## Portable data contract

- Raw bytes remain unchanged, including source ZIP/XLSX formats. Use UTF-8 CSV/JSON plus explicit schema manifests as the baseline exchange format. Use Parquet for processed tables once a target-supported engine is proven.
- CSV exports require a documented null representation distinct from empty/unknown category text, ISO dates/UTC timestamps, explicit dtypes, units and category mappings. Preserve string IDs/leading zeros; do not trust read-time type guessing.
- Parquet schema must preserve nullable integer/boolean/string columns and agreed timestamp precision. Test a local-written file on LinuxONE and a LinuxONE-written file locally. Check row counts, nulls, category values, timestamps and numeric tolerances. Logical file portability does not imply every implementation supports every architecture.
- Do not use pickle/joblib/native NumPy buffers as the shared training-table contract. Avoid host-native endian assumptions in any future binary sensor adapter; parse declared byte order explicitly.
- Use configurable paths and small/bounded imports. The existing local audit loads a 40 MB JSON file into memory; it is not a streaming solution for arbitrary source volumes. M1 should measure input size and choose chunked/streamed ingestion where necessary.

## M1 target acceptance gate

Record actual s390x runtime and dependency sources; resolve a minimal lock/constraints set; verify imports; run the audit tests and a tiny CSV/Parquet round trip on target when access is available. If Parquet native support is not available, use the documented CSV+schema interchange temporarily and record Parquet as unresolved rather than claiming it works. Keep training optimization outside this gate. No target access or source-build approval is needed to finish M0's design audit.
