"""Fetch source rasters/vectors, scoped to Malaysian landslide history and exposure."""

import datetime as dt
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
LOG = ROOT / "data" / "download-manifest.jsonl"
RAW.mkdir(parents=True, exist_ok=True)
CATALOG = RAW / "coolr_reports_malaysia.geojson"
if not CATALOG.exists():
    raise SystemExit("Run download_catalog.py first")


def targets():
    # 100-103 E, 2-6 N covers the major Peninsular Malaysia report clusters.
    for lat in range(2, 6):
        for lon in range(100, 103):
            tile = f"N{lat:02d}_00_E{lon:03d}_00"
            stem = f"Copernicus_DSM_COG_10_{tile}_DEM"
            url = f"https://copernicus-dem-30m.s3.amazonaws.com/{stem}/{stem}.tif"
            yield (f"dem/{stem}.tif", url, "Copernicus GLO-30 Public")
    for lat in (0, 3):
        for lon in (99, 102):
            tile = f"N{lat:02d}E{lon:03d}"
            name = f"ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
            url = f"https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/{name}"
            yield (f"landcover/{name}", url, "ESA WorldCover 2021")
    events = json.loads(CATALOG.read_text(encoding="utf-8"))["features"]
    days = set()
    for feature in events:
        props = feature["properties"]
        date_ms = props.get("event_date")
        if not date_ms:
            continue
        date = dt.datetime.fromtimestamp(date_ms / 1000, dt.timezone.utc).date()
        if 2013 <= date.year <= 2018:
            for lag in range(8):
                days.add(date - dt.timedelta(days=lag))
    for date in sorted(days):
        name = f"chirps-v2.0.{date:%Y.%m.%d}.tif.gz"
        url = f"https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_daily/tifs/p05/{date.year}/{name}"
        yield (f"rainfall/{date.year}/{name}", url, "CHIRPS v2 daily")
    yield (
        "exposure/malaysia-singapore-brunei-latest.osm.pbf",
        "https://download.geofabrik.de/asia/malaysia-singapore-brunei-latest.osm.pbf",
        "Geofabrik OpenStreetMap extract",
    )


def download(item):
    relative, url, source = item
    path = RAW / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return {"path": relative, "source": source, "url": url, "bytes": path.stat().st_size, "status": "existing"}
    part = path.with_suffix(path.suffix + ".part")
    session = requests.Session()
    session.trust_env = False
    for attempt in range(4):
        try:
            with session.get(url, stream=True, timeout=(20, 90)) as response:
                response.raise_for_status()
                expected = int(response.headers.get("Content-Length", 0))
                digest = hashlib.sha256()
                total = 0
                with part.open("wb") as handle:
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk:
                            handle.write(chunk)
                            digest.update(chunk)
                            total += len(chunk)
                if expected and total != expected:
                    raise IOError(f"incomplete download: {total}/{expected}")
                part.replace(path)
                return {"path": relative, "source": source, "url": url, "bytes": total, "sha256": digest.hexdigest(), "status": "downloaded"}
        except (requests.RequestException, IOError) as exc:
            part.unlink(missing_ok=True)
            if attempt == 3:
                return {"path": relative, "source": source, "url": url, "status": "failed", "error": str(exc)}
            time.sleep(2 ** attempt)


items = list(targets())
print(f"Downloading {len(items)} source files", flush=True)
results = []
with ThreadPoolExecutor(max_workers=8) as pool:
    futures = {pool.submit(download, item): item for item in items}
    for future in as_completed(futures):
        result = future.result()
        results.append(result)
        if len(results) % 50 == 0 or result["status"] == "failed":
            print(f"{len(results)}/{len(items)} {result['status']} {result['path']}", flush=True)

with LOG.open("w", encoding="utf-8") as handle:
    for result in sorted(results, key=lambda r: r["path"]):
        handle.write(json.dumps(result, ensure_ascii=False) + "\n")
print("Finished:", {status: sum(r["status"] == status for r in results) for status in {r["status"] for r in results}})
