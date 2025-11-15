from __future__ import annotations
import sys
from .cli import run_cli

def main(argv: list[str] | None = None) -> int:
    return run_cli(argv)

if __name__ == "__main__":
    sys.exit(main())
