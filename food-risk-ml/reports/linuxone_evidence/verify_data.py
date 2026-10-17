import hashlib, json, pathlib
root = pathlib.Path("data/raw/fsis_raw_poultry")
prov = json.loads((root / "DOWNLOAD_PROVENANCE.json").read_text())
bad = 0
for name, meta in prov.items():
    if name.startswith("_"):
        continue
    digest = hashlib.sha256((root / "zips" / name).read_bytes()).hexdigest()
    ok = digest == meta["sha256"]
    bad += not ok
    print(("OK   " if ok else "FAIL ") + name + " " + digest)
print(f"{len([k for k in prov if not k.startswith('_')]) - bad} verified, {bad} mismatched")
raise SystemExit(bad)
