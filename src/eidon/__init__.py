from __future__ import annotations

# Resolve package version from installed metadata when available.
# Falls back to a dev/local version when running from source.
try:
    from importlib.metadata import version  # Py>=3.8
    __version__ = version("eidon")
except Exception:
    __version__ = "0.0.0+local"
