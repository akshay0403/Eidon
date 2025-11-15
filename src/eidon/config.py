from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, Optional, Any
import os

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


@dataclass
class Config:
    default_name: str = "World"
    log_level: Optional[str] = None  # e.g., "INFO", "DEBUG"


def _read_toml(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def _find_name_recursive(mapping: Dict[str, Any]) -> Optional[str]:
    """
    Recursively search for a string value under keys 'default_name' or 'name'
    anywhere in the mapping (top-level or nested tables).
    """
    # direct keys first
    for key in ("default_name", "name"):
        val = mapping.get(key)
        if isinstance(val, str):
            return val
    # then nested tables
    for v in mapping.values():
        if isinstance(v, dict):
            found = _find_name_recursive(v)
            if isinstance(found, str):
                return found
    return None


def _apply_from_mapping(cfg: Config, sources: Dict[str, str], mapping: Dict[str, Any], label: str) -> None:
    nm = _find_name_recursive(mapping)
    if isinstance(nm, str):
        cfg.default_name = nm
        sources["default_name"] = label

    # logging.level either top-level "log_level" or table [logging].level (string)
    if isinstance(mapping.get("log_level"), str):
        cfg.log_level = mapping["log_level"].upper()
        sources["log_level"] = label

    logging_tbl = mapping.get("logging")
    if isinstance(logging_tbl, dict):
        level = logging_tbl.get("level")
        if isinstance(level, str):
            cfg.log_level = level.upper()
            sources["log_level"] = label


def _user_config_path() -> Path:
    xdg = os.getenv("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "eidon" / "config.toml"
    return Path.home() / ".config" / "eidon" / "config.toml"


def _project_config_path() -> Path:
    return Path.cwd() / "eidon.toml"


def load_config(override_path: Optional[str] = None) -> Tuple[Config, Dict[str, str]]:
    """
    Precedence:
    defaults < user < project < override file < env
    (CLI flags are handled in cli.py and beat all of these.)
    """
    cfg = Config()
    sources: Dict[str, str] = {"default_name": "default", "log_level": "default"}

    # user
    u = _user_config_path()
    if u.exists():
        try:
            _apply_from_mapping(cfg, sources, _read_toml(u), "user")
        except Exception:
            pass

    # project
    p = _project_config_path()
    if p.exists():
        try:
            _apply_from_mapping(cfg, sources, _read_toml(p), "project")
        except Exception:
            pass

    # explicit override file
    if override_path:
        op = Path(override_path)
        if op.exists():
            try:
                _apply_from_mapping(cfg, sources, _read_toml(op), f"override:{op}")
            except Exception:
                pass

    # env (highest among config sources)
    if "EIDON_DEFAULT_NAME" in os.environ:
        cfg.default_name = os.environ["EIDON_DEFAULT_NAME"]
        sources["default_name"] = "env:EIDON_DEFAULT_NAME"

    if "EIDON_LOG_LEVEL" in os.environ:
        cfg.log_level = os.environ["EIDON_LOG_LEVEL"].upper()
        sources["log_level"] = "env:EIDON_LOG_LEVEL"

    return cfg, sources
