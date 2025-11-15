from __future__ import annotations
from typing import Callable, List
import importlib
import pkgutil

# Registry stores callables that will attach themselves to argparse subparsers.
# Each "registrar" is a function with signature: registrar(subparsers) -> None
_REGISTRY: List[Callable] = []

def register(registrar: Callable) -> Callable:
    """Decorator to add a subcommand registrar to the global registry."""
    _REGISTRY.append(registrar)
    return registrar

def autodiscover() -> None:
    """
    Import all submodules under eidon.commands so their @register decorators run.
    Safe to call multiple times (subsequent imports are no-ops).
    """
    package_name = __name__  # "eidon.commands"
    for module_info in pkgutil.iter_modules(__path__):  # type: ignore[name-defined]
        importlib.import_module(f"{package_name}.{module_info.name}")

def get_registry() -> List[Callable]:
    return list(_REGISTRY)
