from __future__ import annotations

import argparse
import logging
from typing import List, Optional

from .config import load_config, Config

_LOG = logging.getLogger("eidon")

_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "NOTSET": logging.NOTSET,
}

def _setup_logging(level_str: str | None) -> None:
    level = _LEVELS.get((level_str or "WARNING").upper(), logging.WARNING)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        force=True,  # <-- reconfigure handlers each call (needed for tests)
    )
    _LOG.debug("Logging initialized at %s", logging.getLevelName(level))

def cmd_hello(args: argparse.Namespace, cfg: Config) -> int:
    name = args.name if args.name is not None else cfg.values.get("default_name", "World")
    _LOG.debug("Preparing greeting for %s", name)
    print(f"Hello, {name}!")
    _LOG.info("Greeting sent")
    return 0

def cmd_config_show(args: argparse.Namespace, cfg: Config) -> int:
    print("Effective config:")
    for k, v in cfg.values.items():
        print(f"  {k}: {v}")
    if args.with_sources:
        print("\nSources:")
        for k, src in cfg.sources.items():
            print(f"  {k}: {src}")
    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eidon",
        description="Eidon command-line interface."
    )
    parser.add_argument(
        "-c", "--config",
        help="Path to a TOML config file (overrides default search)."
    )
    parser.add_argument(
        "--log-level",
        choices=list(_LEVELS.keys()),
        help="Set log verbosity (overrides config/env).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    hello = subparsers.add_parser("hello", help="Print a friendly greeting.")
    hello.add_argument(
        "-n", "--name",
        default=None,
        help="Name to greet (default comes from config)."
    )
    hello.set_defaults(func="hello")

    cfg = subparsers.add_parser("config", help="Inspect and manage configuration.")
    cfg_sub = cfg.add_subparsers(dest="config_cmd", required=True)

    cfg_show = cfg_sub.add_parser("show", help="Show effective configuration.")
    cfg_show.add_argument("--with-sources", action="store_true", help="Also show where each value came from.")
    cfg_show.set_defaults(func="config_show")

    return parser

def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    cfg = load_config(args.config)

    # Decide final log level by precedence: CLI > env > config > default
    level_str = args.log_level or cfg.values.get("log_level", "WARNING")
    _setup_logging(level_str)

    if getattr(args, "func", None) == "hello":
        return int(cmd_hello(args, cfg) or 0)
    if getattr(args, "func", None) == "config_show":
        return int(cmd_config_show(args, cfg) or 0)

    parser.print_help()
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
