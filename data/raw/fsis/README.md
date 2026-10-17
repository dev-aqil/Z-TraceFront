# Official FSIS manual intake

Authoritative dataset: [Data.gov raw poultry catalog](https://catalog.data.gov/dataset/fsis-laboratory-sampling-data-raw-poultry-sampling), identifier `usda-fsis-105`.

Official resource: [FSIS raw poultry sampling](https://www.fsis.usda.gov/news-events/publications/raw-poultry-sampling).

**Current source status: official source confirmed, raw file not yet acquired.** No sample filename, sample schema, assay-code mapping or separate local dictionary is known yet. The saved catalog establishes the dataset reference; its `distribution` array describes download resources, not food samples.

## Exact location and filename convention

| Purpose | Convention |
| --- | --- |
| Manual JSON intake | `data/raw/fsis/incoming/<publisher-original-filename>.json` |
| Manual CSV intake | `data/raw/fsis/incoming/<publisher-original-filename>.csv` |
| Separate official documentation, only if downloaded | `data/raw/fsis/incoming/docs/<publisher-original-documentation-filename>` |
| Captured immutable copy | `data/raw/fsis/sha256/<computed-sha256>/<publisher-original-filename>` |

Angle-bracket names are **patterns, not actual files or known official filenames**. The publisher's actual basename determines the filename; do not rename a download to a guessed `FSIS_FY...` name. Preserve spaces and original extension case; quote paths when invoking commands. One fiscal-year release is the intended pilot input, but no FY/version is assumed before acquisition. Intake directories may remain empty. Do not create sample files, a dictionary or a provenance sidecar just to satisfy the convention.

On a fresh checkout, create the empty intake directories with:

```bash
mkdir -p data/raw/fsis/incoming/docs
```

Acquire files from the official FSIS resource linked by Data.gov. Record the actual direct URL, official release/FY/version and original download instant if known. Unknown original retrieval stays null; the pipeline records actual import time separately. Catalog modification time is not a sample release date or result-availability timestamp. Supply `--fsis-origin-url` only for a known actual direct official URL and `--fsis-retrieved-at` only for a known timezone-aware original retrieval instant.

## Intake after a real file exists

Set `FSIS_FILE` to the real downloaded path following the convention and `FSIS_RELEASE` to the observed official release identifier. This command deliberately fails before invocation if either variable is unset; it does not assume a local sample file:

```bash
PYTHONPATH=src python -m tracefront_data.ingest run \
  --fsis-file "${FSIS_FILE:?Set the actual officially downloaded file path}" \
  --fsis-source-version "${FSIS_RELEASE:?Set the actual official release identifier}"
```

Add `--fsis-dictionary` only when a separate matching official document actually exists. An embedded dictionary can instead be referenced by `dictionary_pointer`. Original bytes are copied unchanged; SHA-256 demonstrates preservation, not publisher authenticity. Manual origin/version remains an operator assertion unless independently verified against official bytes.

## Validation gates before downstream processing

1. Verify the saved catalog's dataset ID, declared license and official resource link against configured authority. Check source provenance, actual release/version and byte/hash receipts. Unknown origin or timestamps remain explicitly unknown.
2. Inspect actual JSON/CSV structure. Reject a catalog document supplied as samples; resolve ambiguous JSON arrays explicitly. Inspect columns, sample/assay row unit, identifiers, missingness, raw result codes and exact commodity/program filter values without cleaning or generating labels.
3. Use field descriptions/schema supplied by official metadata if present. The current saved metadata supplies none, so the sample dictionary is **pending**. Neither the draft canonical schema nor a legacy dictionary may stand in for an uninspected current release.
4. Compare the actual release with matching official documentation; populate the cohort contract only after review. Pin `reviewed_source_sha256`, and set `mapping_reviewed` / `dictionary_release_match_verified` true only when justified. Retain unknown, untested and indeterminate outcomes separately; blanks are not negative tests.
5. Require the catalog, schema, provenance and hash gates before declaring cohort inspection complete. Until then `training_eligible=false`; no downstream cleaning, feature generation, joins or training is authorized by intake success alone.

For a verified direct official URL, replace `--fsis-file` with `--fsis-data-url`; both paths use the same inspector. The documented directory is the convention for new manual intake; an existing real file elsewhere under the project can still be explicitly imported without renaming it. Raw files here are ignored by Git; receipts live in `data/manifests/`. **Do not substitute an unofficial mirror to unblock this source.**
