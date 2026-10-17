"""Check both services and run each model family once, without changing the application database."""

import argparse
import json
import math
from urllib.request import Request, urlopen


def request(url, body=None):
    req = Request(url, data=json.dumps(body).encode() if body is not None else None,
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=60) as response:
        return json.load(response)


def check(api, ml):
    health = request(api + "/api/health")
    if health.get("status") != "ok" or health.get("analysis_storage") != "database":
        raise RuntimeError("backend is not serving the durable-analysis release")
    if request(ml + "/health").get("status") != "ok":
        raise RuntimeError("ML service has no default model")
    catalog = request(ml + "/models")
    if catalog["unavailable"]:
        raise RuntimeError(f"unavailable model families: {catalog['unavailable']}")
    expected = {"poultry": 2, "beef": 2, "rte": 1}
    if {f["key"] for f in catalog["families"]} != set(expected):
        raise RuntimeError("model family catalog is incomplete")
    for family, count in expected.items():
        run = request(ml + "/models/spin", {"family": family})
        if len(run["results"]) != count:
            raise RuntimeError(f"{family}: incomplete prediction")
        for result in run["results"]:
            prediction = result["prediction"]
            p = prediction["probability_positive"]
            if not math.isfinite(p) or not 0 <= p <= 1 or not prediction["explanation"]:
                raise RuntimeError(f"{result['model']}: invalid prediction or missing explanation")
            print(f"ready: {result['model']} / {prediction['model_version']}")
    print("ready: durable backend, all five pathogen models and explanations")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--ml", default="http://127.0.0.1:8100")
    args = parser.parse_args()
    check(args.api.rstrip("/"), args.ml.rstrip("/"))
