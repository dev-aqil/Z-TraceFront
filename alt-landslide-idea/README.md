# Alternative landslide idea: source data workspace

Created 17 October 2026 as a separate data workspace. This folder contains source downloads and download scripts, not a trained or validated landslide model. Large raw files are excluded from Git by the repository `.gitignore`.

## What is here

| Data | Location under `data/raw/` | Scope | Source |
| --- | --- | --- | --- |
| Reported landslides | `coolr_reports_global.geojson`, `coolr_reports_malaysia.geojson`, `coolr_reports_united_states.geojson`, `coolr_country_counts.json` | All 14,750 NASA COOLR point reports returned on 17 October; 236 tagged Malaysia and 3,979 tagged United States | [NASA COOLR FeatureServer](https://gis.earthdata.nasa.gov/portal/rest/services/Landslides/COOLR_Reports_Points/FeatureServer/0) |
| Elevation | `dem/*.tif` | Copernicus GLO-30 Public, 100-103 E by 2-6 N, 12 one-degree tiles | [Copernicus DEM on AWS](https://registry.opendata.aws/copernicus-dem/) |
| Land cover | `landcover/*.tif` | ESA WorldCover 2021, four 3-degree tiles around Peninsular Malaysia | [ESA WorldCover data access](https://esa-worldcover.org/en/data-access) |
| Bedrock lithology | `lithology/*.geojson` | 5,442 polygons across nine Peninsular Malaysia state/federal-territory layers | [JMG MyGEMS geology service](https://mygems.jmg.gov.my/server/rest/services/Demarcation/Litology_by_Negeri/FeatureServer) |
| Historical rainfall | `rainfall/YYYY/*.tif.gz` | CHIRPS v2 global daily grids for each Malaysian report dated 2013-2018 and seven preceding days; 773 unique dates, including some in late 2012 | [CHIRPS v2 archive](https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_daily/tifs/p05/) |
| Roads and buildings | `exposure/*.osm.pbf` | Current Malaysia, Singapore, and Brunei extract | [Geofabrik Asia downloads](https://download.geofabrik.de/asia.html) |

The `data/download-manifest.jsonl` file records the source URL and size for each environmental download, plus SHA-256 for files downloaded in this run. Use `download_catalog.py` and `download_environment.py` to reproduce or resume the downloads. Raw CHIRPS files are global because the source publishes full-day rasters; the intended model area is only 100-103 E and 2-6 N.

That model area contains 143 of the Malaysian COOLR points, including 97 with dates in 2013-2018 before any location-quality filtering. The rainfall-date set was generated from all Malaysian reports in those years, so some downloaded dates belong to events outside this model area. Day alignment still needs checking against Malaysia local time and the CHIRPS daily definition.

## Data quality and valid claims

- COOLR is a catalog of *reported* events, largely from media and citizen sources. Missing events are not verified negatives. Location uncertainty matters: among the 236 Malaysian reports, only 21 are labelled exact, 61 within 1 km, 66 within 5 km, and the rest coarser or unknown.
- CHIRPS rainfall is a roughly 5 km grid. It cannot support a prediction for an individual cliff face. Eight-day windows cover event and antecedent rainfall for the chosen reports, not a continuous six-year rainfall archive or a control sample.
- Copernicus GLO-30 is a **digital surface model** that includes vegetation and buildings, not a surveyed bare-earth geotechnical model. Check each tile's coverage and nodata before use.
- ESA WorldCover 2021 and current OpenStreetMap exposure features are newer than most COOLR events (mostly 2007-2018). Do not use them as if they were historical land cover, roads, or buildings in a backtest. They can support a *present-day illustrative exposure overlay*.
- JMG lithology is useful bedrock context, not a direct measurement of soil strength or slope stability. The public service describes the geology data as open, but its item metadata does not state a reuse licence; check terms before redistribution or including raw polygons in a public submission.
- “Landslide susceptibility” or relative area risk is defensible for an exploratory prototype after spatial/temporal validation. “This specific cliff will collapse” and casualties or physical runout are not supported by these sources.
- A soil property map is still missing. Land cover and lithology are not soil type. The documented [SoilGrids WCS](https://docs.isric.org/globaldata/soilgrids/wcs.html) timed out from this machine during the initial download attempt, so no soil layer is claimed here.

## Next data checks

1. Confirm all manifest entries are downloaded and open a sample file from each source.
2. Clip rainfall and raster tiles to a consistent Malaysian area; convert reported events to grid-cell/day labels with location-accuracy filtering.
3. Compare a rainfall/slope baseline with an ML model under time and spatial holdouts. Construct comparison locations carefully; absence from COOLR is not a true negative.
