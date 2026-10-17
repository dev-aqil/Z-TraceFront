"""Command line entry point:  python -m src.cli <command> --help"""

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path

from src.config import DEFAULT_CONFIG, load_config, resolve, setup_logging

log = logging.getLogger("food_risk")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="food-risk", description=__doc__)
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--pathogen", help="pathogen section of the config, e.g. salmonella or campylobacter")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inspect", help="profile raw FSIS file(s) to fill configs/source_mapping.toml")
    p.add_argument("raw", type=Path, nargs="+")
    p = sub.add_parser("prepare", help="raw FSIS file(s) with identical columns + mapping -> validated canonical CSV")
    p.add_argument("raw", type=Path, nargs="+")
    p = sub.add_parser("validate", help="validate a canonical CSV (e.g. delivered by Person A)")
    p.add_argument("canonical", type=Path)
    p = sub.add_parser("eda", help="exploratory analysis of the canonical CSV")
    p.add_argument("--canonical", type=Path)
    p = sub.add_parser("train", help="train/evaluate baselines and register the selected model")
    p.add_argument("--canonical", type=Path)
    p = sub.add_parser("predict", help="score a JSON request file (object or list) with a registered model")
    p.add_argument("request", type=Path)
    p.add_argument("--model-dir", type=Path)
    p = sub.add_parser("backtest", help="rolling yearly backtest on development data (sealed test untouched)")
    p.add_argument("--canonical", type=Path)
    p.add_argument("--label", default="baseline")
    p.add_argument("--models", help="comma-separated subset, e.g. logistic_regression,xgboost")
    p = sub.add_parser("check-handoff", help="validate a Person A model-ready handoff manifest (no training)")
    p.add_argument("manifest", type=Path)
    p = sub.add_parser("experiment", help="baseline experiment on a validated Person A handoff")
    p.add_argument("manifest", type=Path)
    p.add_argument("--out", type=Path, default=Path("artifacts/experiments"))
    p.add_argument("--no-xgboost", action="store_true")
    p = sub.add_parser("train-chemical", help="train/register a chemical model from a Person A readiness bundle")
    p.add_argument("--key", default="imidacloprid", help="[chemical.<key>] section of the config")
    p.add_argument("--readiness", type=Path, help="override the configured readiness.json")
    args = ap.parse_args(argv)

    setup_logging()
    cfg = load_config(args.config, args.pathogen)
    paths = cfg["paths"]
    canonical = getattr(args, "canonical", None) or resolve(paths["processed"])

    # Imports are local so `inspect` works before the heavier ML stack is needed.
    from src.data.contract import TARGET, SchemaError
    from src.data.loader import MappingIncompleteError, load_canonical, load_fsis
    from src.models.contracts import ContractError, NotModelReadyError

    try:
        if args.cmd == "inspect":
            from src.data.inspect import inspect_file
            for raw in args.raw:
                rep = inspect_file(raw, resolve(paths["reports"]))
                print(f"{raw}: {rep['n_rows']} rows, {rep['n_columns']} columns "
                      f"-> reports/schema_inspection_{raw.stem}.md")
        elif args.cmd == "prepare":
            df = load_fsis(args.raw, resolve(paths["mapping"]))
            out = resolve(paths["processed"])
            out.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(out, index=False, date_format="%Y-%m-%d")
            (out.with_suffix(".provenance.json")).write_text(json.dumps(
                {"raw_files": {str(p): _sha256(p) for p in args.raw}, "mapping": str(paths["mapping"]),
                 "mapping_sha256": _sha256(resolve(paths["mapping"]))}, indent=2))
            print(f"wrote {len(df)} canonical rows -> {out}")
        elif args.cmd == "validate":
            df = load_canonical(args.canonical, cfg["pathogen"])
            print(f"OK: {len(df)} rows, {int(df[TARGET].notna().sum())} labelled")
        elif args.cmd == "eda":
            from src.data.eda import run_eda
            print(json.dumps(run_eda(load_canonical(canonical, cfg["pathogen"]),
                                     resolve(paths["reports"]) / "eda"), indent=2))
        elif args.cmd == "train":
            if not Path(canonical).exists():
                print(f"BLOCKED: {canonical} not found. Obtain the FSIS data (README 'Getting the data'), "
                      "fill configs/source_mapping.toml, then run `prepare`.", file=sys.stderr)
                return 2
            from src.models.train import run_training
            prov_file = Path(canonical).with_suffix(".provenance.json")
            provenance = {"canonical_file": str(canonical), "canonical_sha256": _sha256(Path(canonical)),
                          "upstream": json.loads(prov_file.read_text()) if prov_file.exists() else None}
            rep = run_training(load_canonical(canonical, cfg["pathogen"]), cfg, resolve(paths["reports"]),
                               resolve(paths["registry"]), provenance)
            print(json.dumps({k: rep[k] for k in ("model_version", "selected_model", "threshold", "test")}, indent=2))
        elif args.cmd == "predict":
            from src.models.predict import Predictor
            from src.models.registry import latest_model_dir
            req = json.loads(args.request.read_text())
            predictor = Predictor(args.model_dir or latest_model_dir(resolve(paths["registry"])))
            print(json.dumps(predictor.predict(req if isinstance(req, list) else [req]), indent=2))
        elif args.cmd == "backtest":
            from src.evaluation.backtest import run_backtest
            rep = run_backtest(load_canonical(canonical, cfg["pathogen"]), cfg, resolve(paths["reports"]) / "backtest",
                               args.label, args.models.split(",") if args.models else None)
            print(json.dumps(rep["summary"], indent=2))
        elif args.cmd == "check-handoff":
            from src.models.chemical import load_pdp_readiness
            from src.models.contracts import load_handoff
            is_readiness = args.manifest.exists() and "dataset_path" in json.loads(args.manifest.read_text())
            h = load_pdp_readiness(args.manifest)[0] if is_readiness else load_handoff(args.manifest)
            print(f"OK: {h.manifest['target']} handoff, {len(h.table)} labelled rows, {len(h.features())} features")
        elif args.cmd == "experiment":
            from src.models.experiment import run_experiment
            rep = run_experiment(args.manifest, resolve(args.out), cfg["seed"], use_xgboost=not args.no_xgboost)
            print(json.dumps({r["model_type"]: r["metrics"]["test"] for r in rep["runs"]}, indent=2, default=str))
        elif args.cmd == "train-chemical":
            from src.models.chemical import run_chemical
            rep = run_chemical(cfg, args.key, args.readiness)
            print(json.dumps({k: rep[k] for k in ("model_version", "selected_model", "tied_models", "test",
                                                   "test_pr_auc_ci", "vs_commodity_rate_pr_auc",
                                                   "ablation_with_calendar_position")}, indent=2, default=str))
    except (MappingIncompleteError, SchemaError, FileNotFoundError, NotModelReadyError, ContractError) as e:
        print(f"BLOCKED: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
