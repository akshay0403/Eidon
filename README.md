# Eidon

Phase 1 scaffold with Python (uv), Makefile tasks, and CI.

## Quickstart

```bash
# From project root
uv run make setup
make run       # prints a hello line
make test      # 1 passing test
make lint      # Ruff lint
make typecheck # MyPy
uv pip install -e .
uv run eidon --help
