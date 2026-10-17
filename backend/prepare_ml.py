"""Verify server-native models and restore missing sample tables only from matching archived bytes."""

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tomllib


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare(root):
    config = tomllib.loads((root / "configs/config.toml").read_text())
    for key, spec in config["pathogens"].items():
        registry = root / spec["registry"]
        version = (registry / "LATEST").read_text().strip()
        model_dir = registry / version
        if model_dir.resolve().parent != registry.resolve():
            raise RuntimeError(f"invalid registry pointer for {key}")
        meta = json.loads((model_dir / "metadata.json").read_text())
        expected = meta["provenance"]["canonical_sha256"]
        destination = root / spec["processed"]
        if destination.exists():
            if sha(destination) != expected:
                raise RuntimeError(f"{key}: current sample table does not match the served model; refusing to overwrite")
        else:
            candidates = sorted(root.parent.glob(f"food-risk-ml-*/data/processed/{destination.name}"))
            source = next((p for p in candidates if sha(p) == expected), None)
            if source is None:
                raise RuntimeError(f"{key}: no archived sample table matches {expected}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            print(f"restored {key} samples from {source.parent.parent.parent.name}; sha256={expected}")
        for name in ("model.joblib", "background.csv"):
            if not (model_dir / name).is_file():
                raise RuntimeError(f"{key}: missing {name}")
        print(f"verified {key}: {version}; sha256={expected}")


if __name__ == "__main__":
    prepare(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "food-risk-ml")
