# Landslide feasibility research

Planning research collected on 30 September 2026; no competition application code is included.

- [Findings](findings.md): primary sources, access constraints, data limitations, existing LHASA baseline, and proposed project scope.
- [Malaysian event export](malaysia-events.json): original JSON response from NASA COOLR's report-point API, including response field definitions and 236 records.
- [Session transcript](../../planning/session-transcript-2026-09-30.md): user prompts and assistant responses from the initial greeting through the request to commit this material.

## Export provenance

Source: NASA Goddard Space Flight Center, Cooperative Open Online Landslide Repository (COOLR).

Endpoint: https://gis.earthdata.nasa.gov/portal/rest/services/Landslides/COOLR_Reports_Points/FeatureServer/0/query

Query parameters:

```json
{
  "f": "json",
  "where": "country_name = 'Malaysia'",
  "outFields": "event_id,event_date,event_title,latitude,longitude,location_accuracy,landslide_trigger,admin_division_name,source_link",
  "returnGeometry": "false",
  "resultRecordCount": 2000
}
```

Retrieved 30 September 2026. Dates are Unix epoch milliseconds as supplied by the API. No transfer-limit warning was returned. This export covers one layer and filter, not every Malaysian landslide or every COOLR inventory. Preserve source attribution and consult the source terms before downstream redistribution. No separate export-specific license was verified.

## Interpretation

Reports have uneven geographical coverage, uncertain locations, and reporting bias. Missing reports are not verified non-events. Exposure does not establish a road closure; scenario routes are not certified safe. Current road maps and 2020/2021 land-cover maps may mismatch historical event dates.

This research does not demonstrate a validated warning system. The transcript preserves earlier assessments and subsequent corrections; use findings.md for the consolidated research position. Transcript links under /workspace refer to the original session filesystem and are retained verbatim.
