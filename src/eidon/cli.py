from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Optional

from . import __version__
from .commands import get_registry, autodiscover
from .errors import EidonError, EXIT_USAGE, EXIT_RUNTIME
from .config import load_config  # NEW
from .commands import get_registry, autodiscover
from .demo_launch import run_demo_web  # new small launcher module we created

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eidon",
        description="Eidon command-line interface.",  # match tests
    )

    # Global/root flags
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Override log level (default from env/config).",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to a TOML config file to use (highest precedence).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"eidon {__version__}",
        help="Show version and exit.",
    )
    parser.add_argument(
        "--format",
        default="text",
        choices=["text", "json"],
        help="Output format for command results.",
    )

    subparsers = parser.add_subparsers(
        title="subcommands",
        dest="subcommand",
        metavar="<command>",
        required=False,
    )
    # Import all subcommand modules so they @register
    autodiscover()

    # Wire everything in the registry
    for registrar in get_registry():
        registrar(subparsers)

    demo_parser = subparsers.add_parser("demo-web", help="Launch the Eidon web demo UI.")
    demo_parser.set_defaults(func=run_demo_web)


    return parser


def _configure_logging(cli_level_name: Optional[str], cfg_level_name: Optional[str]) -> None:
    # Precedence: CLI > ENV > CONFIG > default(WARNING)
    level_name = (
        (cli_level_name or "").strip()
        or (os.getenv("EIDON_LOG_LEVEL") or "").strip()
        or (cfg_level_name or "").strip()
        or "WARNING"
    )
    level = getattr(logging, level_name.upper(), logging.WARNING)

    # IMPORTANT: force=True so repeated test runs reconfigure handlers
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )


def run_cli(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Load effective config once, attach to args so subcommands can use it
    cfg, sources = load_config(args.config)
    setattr(args, "_eidon_config", cfg)
    setattr(args, "_eidon_sources", sources)

    _configure_logging(getattr(args, "log_level", None), cfg.log_level)

    


    if not hasattr(args, "func"):
        parser.print_help(sys.stderr)
        return EXIT_USAGE

    try:
        return int(args.func(args))
    except EidonError as e:
        logging.getLogger("eidon").error(str(e))
        return getattr(e, "code", EXIT_RUNTIME)
    except KeyboardInterrupt:
        logging.getLogger("eidon").error("Interrupted.")
        return 130
    except Exception as e:
        logging.getLogger("eidon").exception("Unexpected error: %s", e)
        return EXIT_RUNTIME


