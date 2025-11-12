from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import tomllib

ENV_PREFIX = "EIDON_"

DEFAULTS: Dict[str, str] = {
    "default_name": "World",
    "log_level": "WARNING",  # keep CLI quiet by default
}

@dataclass(frozen=True)
class Config:
    values: Dict[str, str]
    sources: Dict[str, str]  # e.g., "env:EIDON_LOG_LEVEL" or "project:/path/eidon.toml"

def _read_toml(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        data = tomllib.load(f)

    section = data.get("eidon", data) if isinstance(data, dict) else {}
    out: Dict[str, str] = {}
    if isinstance(section, dict):
        if isinstance(section.get("default_name"), str):
            out["default_name"] = section["default_name"]
        if isinstance(section.get("log_level"), str):
            out["log_level"] = section["log_level"]
    return out

def _user_config_path() -> Path:
    return Path.home() / ".config" / "eidon" / "config.toml"

def _project_config_path(cwd: Path | None = None) -> Path:
    base = cwd or Path.cwd()
    return base / "eidon.toml"

def _load_env() -> Tuple[Dict[str, str], Dict[str, str]]:
    vals: Dict[str, str] = {}
    srcs: Dict[str, str] = {}
    mapping = {
        "default_name": f"{ENV_PREFIX}DEFAULT_NAME",
        "log_level": f"{ENV_PREFIX}LOG_LEVEL",
    }
    for key, env_key in mapping.items():
        val = os.environ.get(env_key)
        if val:
            vals[key] = val
            srcs[key] = f"env:{env_key}"
    return vals, srcs

def load_config(config_path: str | None = None) -> Config:
    values: Dict[str, str] = dict(DEFAULTS)
    sources: Dict[str, str] = {k: "default" for k in DEFAULTS.keys()}

    # User config
    user_path = _user_config_path()
    user_vals = _read_toml(user_path)
    for k, v in user_vals.items():
        values[k] = v
        sources[k] = f"user:{user_path}"

    # Project config
    project_path = _project_config_path()
    if config_path:
        project_path = Path(config_path)
    proj_vals = _read_toml(project_path)
    for k, v in proj_vals.items():
        values[k] = v
        sources[k] = f"project:{project_path}"

    # Env overrides
    env_vals, env_srcs = _load_env()
    for k, v in env_vals.items():
        values[k] = v
        sources[k] = env_srcs[k]

    return Config(values=values, sources=sources)
