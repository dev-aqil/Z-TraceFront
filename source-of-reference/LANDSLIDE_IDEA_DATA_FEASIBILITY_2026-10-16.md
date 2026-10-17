# Landslide idea: data and ML feasibility check

Checked 16 October 2026. This records a candidate for team reconsideration, not a change to the voted project. The teammate's earlier description was a landslide simulator that finds high-risk places and shows how surrounding areas could be affected. The more specific current proposal adds rainfall, terrain/land type, historical events, a risk map, and exposure assessment.

## Data that appears available

| Role | Candidate public source | What it can support | Limitation |
| --- | --- | --- | --- |
| Historical landslide reports | [NASA COOLR](https://gis.earthdata.nasa.gov/portal/rest/services/Landslides/COOLR_Reports_Points/FeatureServer/layers) | Positive event locations, approximate dates, triggers, and sometimes impact fields | Incomplete and media/citizen-report biased; an unreported location is not a verified non-event. Locations and dates have varying accuracy. |
| Rainfall history | [CHIRPS Daily](https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHG_CHIRPS_DAILY) | Antecedent and event-window rainfall features | Roughly 5.6 km pixels: insufficient to claim a particular cliff face is safe or unsafe. Verify usable date coverage when extracting. |
| Terrain | [NASA SRTM 30 m elevation](https://developers.google.com/earth-engine/datasets/catalog/USGS_SRTMGL1_003) | Elevation, approximate slope, aspect, terrain position | Resolution and age limit site-specific engineering claims. |
| Land cover | [ESA WorldCover 10 m 2021](https://developers.google.com/earth-engine/datasets/catalog/ESA_WorldCover_v200) | Broad built-up, vegetation, cropland, and bare-ground context | Land cover is not a soil or geological stability measurement; 2021 cover can be stale for earlier events. |
| Existing benchmark | [NASA LHASA](https://gis.earthdata.nasa.gov/portal/rest/services/Landslides/LHASA_Exposure/MapServer) | Demonstrates that rainfall plus susceptibility ML is a real operational research direction | It is an existing solution to compare against, not evidence that our model is accurate or original. |

## Defensible MVP hypothesis

Choose one region and one target: **relative rainfall-triggered landslide susceptibility by grid cell and day**. Join historical event points to prior rainfall and static terrain/cover features. Define candidate non-event samples carefully and acknowledge they are unverified. Use a simple baseline and a small tabular model first, with spatial and time holdouts. Evaluate recall, precision, calibration, and false alerts against held-out historical reports. A random row split would leak nearby locations and repeated storms. PyTorch is optional; it should only replace the baseline if it improves a measured result. LinuxONE should run the actual inference and return map-cell scores and explanations through an API.

Show a map of **relative risk / research prototype outputs**, not a certified probability that a specific cliff will collapse. Overlay roads or buildings for an exposure estimate, clearly separate from the hazard model. A physically realistic runout path, casualty estimate, or precise cliff-level prediction requires local geotechnical and high-resolution data that these sources do not provide.

Synthetic data can fill presentation gaps, test API flows, and simulate an incident. It cannot repair missing real labels or validate predictive accuracy. Synthetic non-events or damage outcomes must never be presented as observed ground truth.

## Decision gate before asking the team to switch

1. Pick a region with enough dated, sufficiently located historical events. Count them and inspect source quality.
2. Confirm rainfall, terrain, and cover can be joined at a common spatial and temporal scale without future-data leakage.
3. Build a small baseline and holdout evaluation during the permitted event period. Compare it with a PyTorch model only if time and data warrant it.
4. Confirm that a useful inference path fits the team's LinuxONE VM and that the demo can show a map plus a clearly labelled exposure overlay.
5. If these checks fail, keep the food-recall concept or narrow the landslide idea to a non-predictive map. Do not choose based only on the availability of many input rasters.
