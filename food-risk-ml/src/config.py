import logging
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "config.toml"


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    with open(path, "rb") as f:
        return tomllib.load(f)


def resolve(path: str | Path) -> Path:
    """Resolve a config path relative to the project root."""
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
