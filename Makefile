# Use uv to manage Python, and uvx to run CLI tools without pinning them as deps.
UV := uv
PY := $(UV) run python

.PHONY: setup run test lint typecheck format clean

setup:
	uv sync
	uv pip install -e .

run:
	$(PY) -m eidon

lint:
	uvx ruff check .

typecheck:
	uvx mypy src

format:
	uvx ruff format .

clean:
	rm -rf .venv .pytest_cache __pycache__ dist build htmlcov .coverage

NAME ?= World

hello:
	uv run eidon hello --name $(NAME)

config-show:
	uv run eidon config show --with-sources

test:
	uv run python -m unittest discover -s tests -p "test_*.py" -v

test-q:
	uv run python -m unittest discover -s tests -p "test_*.py" -q

log-demo-info:
	uv run eidon --log-level INFO hello --name Akshay

log-demo-debug:
	uv run eidon --log-level DEBUG hello --name Akshay

config-show:
	uv run eidon config show --with-sources

# (Optional) small help target to list common commands
help:
	@echo "make test       - run unit tests (verbose)"
	@echo "make test-q     - run unit tests (quiet)"
	@echo "make hello NAME=Akshay - run hello demo"
	@echo "make log-demo-info / log-demo-debug - logging demos"
	@echo "make config-show - print effective config"

