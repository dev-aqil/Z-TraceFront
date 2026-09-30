# Landslide data feasibility research

Checked primary-source pages and APIs on 30 September 2026. This is planning research, not a validated warning system or competition implementation.

## Main result

Public terrain, rainfall, land-cover, soil and road data cover Malaysia. Precise, comprehensive event labels and observed road-closure data are the main gaps. A regional decision-support prototype is feasible; reliable individual-slope prediction is not established by these datasets.

## Verified sources

- NASA COOLR: https://gpm.nasa.gov/applications/landslides/coolr
- Live reports layer: https://gis.earthdata.nasa.gov/portal/rest/services/Landslides/COOLR_Reports_Points/FeatureServer/0
- CHIRPS v3: https://www.chc.ucsb.edu/data/chirps3
- Public CHIRPS directory: https://data.chc.ucsb.edu/products/CHIRPS/v3.0/
- IMERG: https://gpm.nasa.gov/data/imerg
- Copernicus GLO-30/GLO-90: https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM
- OSM regional extracts: https://download.geofabrik.de/asia/malaysia-singapore-brunei.html
- ESA WorldCover: https://esa-worldcover.org/en/data-access
- SoilGrids: https://www.isric.org/explore/soilgrids
- Malaysian rainfall station portal: https://publicinfobanjir.water.gov.my/
- NASA LHASA code and documentation: https://github.com/nasa/LHASA

## Malaysian report-point query

Query filter: country_name = 'Malaysia'. Returned 236 records, no transfer-limit warning. This is one layer and filter, not a complete count across all COOLR inventories.

- Event dates: 22 March 2007 to 9 March 2022.
- Location labels: exact 21; 1km 61; 5km 66; 10km 31; 25km 35; 50km 15; unknown 6; 250km 1.
- Triggers: downpour 110; rain 59; continuous_rain 32; unknown 21; construction 5; other 3; tropical_cyclone 2; flooding 2; mining 1; monsoon 1.
- Regional counts: Sabah 47; Sarawak 35; Penang 34; Selangor 33; Kuala Lumpur 30; Pahang 23; others smaller.
- Export saved as malaysia-events.json. Contains source links and reported location-accuracy fields.

Reporting bias matters. An unreported event is not a verified non-event. Imprecise coordinates should not be treated as exact training points. Split validation by time and geography, not just random rows. Match predictor dates to event dates; current roads and later land-cover maps can introduce temporal mismatch.

## Source limitations

- IMERG provides half-hourly estimates, but Early Run has roughly four-hour latency. It is near-real-time observation, not a rainfall forecast. NASA directs users toward free Earthdata/PPS registration depending on access route. Bulk download was not tested.
- CHIRPS v3: 0.05 degree grid, roughly 5.5 km near Malaysia; historical record from 1981. Daily products are derived by partitioning pentad totals using ERA5 or IMERG, not independent daily gauge observations. Preliminary product availability is after the pentad. V2 production is scheduled to end after December 2026. Follow v3 citation/license guidance.
- Copernicus GLO-30: 30m global digital surface model, including vegetation/buildings; not bare-earth engineering survey data. Free license with attribution; official download route requires registration.
- WorldCover: 10m land cover for 2020/2021, CC-BY 4.0; too old for claims about recent land clearing without additional imagery.
- SoilGrids: 250m modelled soil properties, CC-BY 4.0. Not real-time soil moisture or engineering shear-strength measurements. Official page says REST API is paused; use documented alternative downloads.
- Geofabrik: current Malaysia/Singapore/Brunei OSM PBF available, approximately 239 MB displayed; ODbL attribution obligations. Road topology/completeness needs checking.
- Public InfoBanjir is accessible, but a supported bulk historical export/API and reuse terms were not verified. Do not depend on it for the MVP.

## Existing baseline and project direction

LHASA 2 already estimates daily landslide probability at approximately 1km and population/road exposure. It provides source code and hazard archives; repository says running inference is supported but retraining is not provided directly. Check its actual license and s390x dependencies before reuse. Installation examples use x86_64 and cannot be copied verbatim onto LinuxONE.

Proposed original contribution: network-level disruption and community access analysis under explicitly labelled road-failure scenarios, plus uncertainty caused by stale rainfall, coarse input grids, and imprecise reports. Exposure does not establish road closure, and remaining routes must not be labelled safe.

Suggested first region: screen Selangor/Pahang and Penang, then select using usable event labels and road topology. Start with a historical replay, rainfall + terrain + roads, baseline comparison, and LinuxONE inference/network analysis. Soil/land-cover inputs are optional. Seismic data are outside this rainfall-triggered scope.
