from __future__ import annotations
from argparse import ArgumentParser, _SubParsersAction
from . import register
from ..config import load_config


def _run_show(args) -> int:
    # Prefer config computed by cli.py; fallback to fresh load if missing
    cfg = getattr(args, "_eidon_config", None)
    sources = getattr(args, "_eidon_sources", None)
    if cfg is None or sources is None:
        cfg, sources = load_config(getattr(args, "config", None))

    if getattr(args, "format", "text") == "json":
        import json
        payload = {
            "ok": True,
            "command": "config.show",
            "default_name": cfg.default_name,
            "log_level": cfg.log_level,  # will appear as null if None
        }
        if getattr(args, "with_sources", False):
            payload["sources"] = {
                "default_name": sources.get("default_name", "default"),
                "log_level": sources.get("log_level", "default"),
            }
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        return 0

    # Text mode (unchanged: keep compatibility with existing tests)
    if getattr(args, "with_sources", False):
        print(f"default_name: {cfg.default_name} (source={sources.get('default_name','default')})")
        print(f"log_level: {cfg.log_level or ''} (source={sources.get('log_level','default')})")
    else:
        print(f"default_name: {cfg.default_name}")
        print(f"log_level: {cfg.log_level or ''}")
    return 0


@register
def register_config(subparsers: _SubParsersAction) -> None:
    p: ArgumentParser = subparsers.add_parser(
        "config",
        help="Inspect and print effective configuration.",
        description="Show Eidon configuration derived from defaults, files, and environment.",
    )
    sp = p.add_subparsers(dest="config_cmd", metavar="<subcommand>")
    show = sp.add_parser("show", help="Show effective configuration.")
    show.add_argument("--with-sources", action="store_true", help="Include the source of each value.")
    show.add_argument("--format", choices=["text", "json"], default="text")  # <— add this
    show.set_defaults(func=_run_show)

