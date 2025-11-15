from __future__ import annotations
import logging
import os
from argparse import ArgumentParser, _SubParsersAction
from ..errors import EidonError
from . import register

logger = logging.getLogger("eidon.hello")


def _effective_name(args) -> str:
    # Precedence: CLI --name > ENV > config > default "World"
    if getattr(args, "name", None):
        return args.name
    env_name = os.getenv("EIDON_DEFAULT_NAME")
    if env_name:
        return env_name
    cfg = getattr(args, "_eidon_config", None)
    if cfg and getattr(cfg, "default_name", None):
        return cfg.default_name
    return "World"


def _run(args) -> int:
    if os.getenv("EIDON_TEST_RAISE") == "EidonError":
        raise EidonError("boom", code=7)

    logger.debug("Preparing greeting")  # DEBUG for tests
    name = _effective_name(args)
    greeting = f"Hello, {name}!"

    if getattr(args, "format", "text") == "json":
        import json
        payload = {
            "ok": True,
            "command": "hello",
            "name": name,
            "greeting": greeting,
        }
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    else:
        print(greeting)

    logger.info("Greeting sent")        # INFO for tests
    return 0

@register
def register_hello(subparsers: _SubParsersAction) -> None:
    parser: ArgumentParser = subparsers.add_parser(
        "hello",
        help="Print a friendly greeting.",
        description="Say hello to someone.",
    )
    parser.add_argument("--name", default=None, help="Name to greet.")
    parser.add_argument("--format", choices=["text", "json"], default="text")  # <— add this
    parser.set_defaults(func=_run)
