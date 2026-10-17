"""Download NASA COOLR point reports for pre-event dataset exploration."""

import json
import time
from collections import Counter
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
BASE = "https://gis.earthdata.nasa.gov/portal/rest/services/Landslides/COOLR_Reports_Points/FeatureServer/0/query"
SESSION = requests.Session()
SESSION.trust_env = False  # Avoid this workstation's inactive local proxy.


def get(params):
    for attempt in range(4):
        try:
            response = SESSION.get(BASE, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                raise RuntimeError(data["error"])
            return data
        except (requests.RequestException, ValueError) as exc:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


count = get({"f": "json", "where": "1=1", "returnCountOnly": "true"})["count"]
features = []
for offset in range(0, count, 1000):
    page = get(
        {
            "f": "geojson",
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "4326",
            "orderByFields": "objectid",
            "resultOffset": offset,
            "resultRecordCount": 1000,
        }
    )
    features.extend(page["features"])
    print(f"COOLR: {len(features)}/{count}", flush=True)

assert len(features) == count, (len(features), count)
assert len({f["properties"]["objectid"] for f in features}) == count
collection = {"type": "FeatureCollection", "features": features}
(RAW / "coolr_reports_global.geojson").write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")

countries = Counter(f["properties"].get("country_name") for f in features)
for country, slug in [("Malaysia", "malaysia"), ("United States", "united_states")]:
    subset = [f for f in features if f["properties"].get("country_name") == country]
    (RAW / f"coolr_reports_{slug}.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": subset}, ensure_ascii=False), encoding="utf-8"
    )

(RAW / "coolr_country_counts.json").write_text(
    json.dumps(dict(countries.most_common()), indent=2, ensure_ascii=False), encoding="utf-8"
)
print("Top countries:", countries.most_common(15))

malaysia = [f for f in features if f["properties"].get("country_name") == "Malaysia"]
cells = Counter()
for feature in malaysia:
    geometry = feature.get("geometry")
    if not geometry or geometry.get("type") != "Point":
        continue
    lon, lat = geometry["coordinates"]
    cells[(int(lon), int(lat))] += 1
print("Malaysia one-degree cells:", cells.most_common(15))
