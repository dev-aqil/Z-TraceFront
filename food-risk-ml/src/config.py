import logging
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "config.toml"


def load_config(path: Path = DEFAULT_CONFIG, pathogen: str | None = None) -> dict[str, Any]:
    """Load the config and resolve one pathogen section into cfg["pathogen"] (display name),
    cfg["pathogen_key"] and cfg["paths"] (mapping, processed, reports, registry)."""
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    key = (pathogen or cfg["default_pathogen"]).lower()
    if key not in cfg["pathogens"]:
        raise KeyError(f"unknown pathogen {key!r}; configured: {sorted(cfg['pathogens'])}")
    section = cfg["pathogens"][key]
    cfg["pathogen"], cfg["pathogen_key"], cfg["product"] = section["name"], key, section.get("product")
    cfg["paths"] = {k: section[k] for k in ("mapping", "processed", "reports", "registry")}
    return cfg


def resolve(path: str | Path) -> Path:
    """Resolve a config path relative to the project root."""
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
