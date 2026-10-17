"""Save publicly exposed JMG lithology polygons for Peninsular Malaysia states."""

import json
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "raw" / "lithology"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "https://mygems.jmg.gov.my/server/rest/services/Demarcation/Litology_by_Negeri/FeatureServer"
LAYERS = {2: "kedah", 4: "pulau_pinang", 6: "perak", 8: "kelantan", 10: "terengganu", 12: "pahang", 14: "selangor", 18: "kuala_lumpur", 20: "negeri_sembilan"}
session = requests.Session()
session.trust_env = False


def query(layer, params):
    response = session.get(f"{BASE}/{layer}/query", params=params, timeout=90)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    return data


for layer, name in LAYERS.items():
    count = query(layer, {"f": "json", "where": "1=1", "returnCountOnly": "true"})["count"]
    features = []
    for offset in range(0, count, 1000):
        page = query(
            layer,
            {
                "f": "geojson",
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": "4326",
                "resultOffset": offset,
                "resultRecordCount": 1000,
            },
        )
        features.extend(page["features"])
    if len(features) != count:
        raise RuntimeError(f"{name}: {len(features)} of {count} records")
    path = OUT / f"jmg_lithology_{name}.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False), encoding="utf-8")
    print(name, count, path.stat().st_size, flush=True)
