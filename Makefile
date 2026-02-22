.PHONY: test lint typecheck check build up down bootstrap clean

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check src/

typecheck:
	uv run mypy src/

check: lint typecheck test

build:
	docker compose build

up:
	docker compose up api streamlit -d

down:
	docker compose down

bootstrap:
	docker compose --profile pipeline up pipeline

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null; true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null; true
