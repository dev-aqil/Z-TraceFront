# USDA AMS official evidence — PDP Databases and Annual Summaries

- Retrieved by: Tracefront M5 continuation (fetch tool, read-only HTTPS GET; no login/paywall)
- Source URL: https://www.ams.usda.gov/datasets/pdp/pdpdata
- Fetched at (UTC): 2026-10-17T07:37:00+00:00
- Publisher: USDA Agricultural Marketing Service (AMS)
- Use: Establishes the official public-posting date of the complete 2024 PDP Database ZIP archive
  (the same archive pinned in configs/source_contracts.json as
  data/raw/usda_pdp/sha256/de916ba.../2024PDPDatabase.zip, containing both PDP24Samples.txt and
  PDP24Results.txt as ZIP members). No other document was found with an earlier public posting date
  for this archive.

## Verbatim fetched content (page body, nav/chrome trimmed)

# PDP Databases and Annual Summaries

Listed below are links to PDP Databases and published Annual Summary reports for calendar years 1992-2024. The PDP Data are compressed (zipped) into standard ZIP format files, which require a decompression utility.

The zipped files will extract to several ASCII, delimited data files containing PDP sampling and residue testing data along with file layouts and reference lists that can be used to interpret the standardized codes used in the PDP data. The data files can then be imported into the provided database structure.

## PDP Annual Summary Reports

- View the Annual Summary Report list

## Database Resources

- PDP Database Search
- PDP Search App User Guide (pdf)
- PDP Search App Data Dictionary (pdf)

## PDP Databases Available for Downloading

- Instructions for Using 1992-2024 Data ZIP files (pdf)
- 2024 Data ZIP File - 10.1MB - Posted on 12/23/2025
- 2023 Data ZIP File - 9.9MB - Posted on 11/04/2024
- 2022 Data ZIP File –  10.0MB - Posted on 1/30/2024
- 2021 Data ZIP File - 9.0MB - posted 12/21/2022
- 2020 Data ZIP File –  9.0MB - Posted on 1/18/2022
- 2019 Data ZIP File –  8.9MB - Revised on 9/15/2021
- 2018 Data ZIP File - 9.0MB - Posted on 12/10/2019
- 2017 Data ZIP File – 8.7MB - Posted on 12/17/2018
- 2016 Data ZIP File – 8.4MB - Posted on 2/08/2018
- 2015 Data ZIP File - 8.1MB - Revised on 8/23/2017
- 2014 Data ZIP File – 7.5MB - Posted on 1/11/2016

(remaining historical rows 1992-2013 omitted here; unrelated to the 2024 cohort pinned by this
project and not required to establish the 2024 posting date)

## Other Government Sources of Pesticide Information

- U.S. Environmental Protection Agency (EPA): Pesticides
- U.S. Food and Drug Administration (FDA) Pesticide Residue Monitoring Program
- USDA Food Safety and Inspection Service (FSIS) Residue Monitoring for meat, poultry, and egg products

## Key quoted line used as evidence

> 2024 Data ZIP File - 10.1MB - Posted on 12/23/2025

## Interpretation and limits of this evidence

1. This is a single, dated posting record for the entire 2024 ZIP archive. The archive bundles
   `PDP24Samples.txt` (sample-context fields) and `PDP24Results.txt` (analytical result fields,
   already excluded here as label evidence) together as ZIP members; AMS does not publish a
   separate, earlier posting date for either member individually.
2. This evidence therefore establishes only an upper bound: no field from either file is verifiably
   public before 2025-12-23. It does NOT establish that sample-context fields were available any
   earlier than analytical result fields, and it is not used to justify treating any
   `usda_pdp.results` field as a predictor.
3. No time-of-day is published, so the verified precision is DATE (calendar day), not a timestamp.
4. This is distinct from the press release / Annual Summary PDF publication (2026-01-06 and
   "December 2025" respectively), which describe the narrative summary report, not the raw ZIP
   database used by this pipeline. The raw-database posting date is the one used here because it is
   the artifact actually ingested (see configs/source_contracts.json archive hash).
