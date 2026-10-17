"""Package application code/config only. Model registries, data and secrets stay on LinuxONE."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def allowed(name):
    p = Path(name)
    return (p.parts[:2] in (("backend", "app"), ("food-risk-ml", "src")) and p.suffix == ".py"
            or p.parts[:2] == ("food-risk-ml", "configs") and p.suffix == ".toml"
            or p.parent.as_posix() == "backend" and p.suffix in (".py", ".ps1", ".sh", ".txt")
            or name == "food-risk-ml/pyproject.toml") and "__pycache__" not in p.parts


def package(output, working_tree=False):
    args = ["git", "-C", str(ROOT), "ls-files", "-z", "--cached"]
    if working_tree:
        args += ["--others", "--exclude-standard"]
    names = sorted(set(subprocess.check_output(args).decode().strip("\0").split("\0")))
    if not working_tree:
        names = subprocess.check_output(["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", "HEAD"]).decode().splitlines()
    revision = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"]).decode().strip()
    hashes = {}
    with tarfile.open(output, "w:gz") as archive:
        def add(name, raw):
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(raw))
        for name in names:
            if not allowed(name):
                continue
            path = ROOT / name
            if working_tree:
                if not path.is_file():
                    continue
                if not path.resolve().is_relative_to(ROOT.resolve()):
                    raise RuntimeError(f"refusing external source link: {name}")
                raw = path.read_bytes()
            else:
                raw = subprocess.check_output(["git", "-C", str(ROOT), "show", f"HEAD:{name}"])
            if name.endswith(".sh"):
                raw = raw.replace(b"\r\n", b"\n")
            add(name, raw)
            hashes[name] = hashlib.sha256(raw).hexdigest()
        add("release-manifest.json", json.dumps({"revision": revision, "working_tree": working_tree,
                                               "sha256": hashes}, indent=2).encode())
    print(f"packaged {len(hashes)} source/config files from {'working tree' if working_tree else revision}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--working-tree", action="store_true")
    args = parser.parse_args()
    package(args.output, args.working_tree)
