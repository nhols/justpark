UV_CACHE_DIR ?= /tmp/justpark-uv-cache
export UV_CACHE_DIR

.PHONY: web fetch-data prepare-demo test help

web:
	npm --prefix web run dev

fetch-data:
	uv run scripts/fetch_jp_data.py

prepare-demo:
	uv run python -m tests.sample_data | PYTHONPATH=. uv run scripts/prepare_dashboard.py - web/public/dashboard.json

test:
	uv run python -m unittest
	npm --prefix web run build

help:
	@echo "Available commands:"
	@echo "  web          - Run the frontend"
	@echo "  fetch-data   - Fetch JustPark data"
	@echo "  prepare-demo - Generate local sample dashboard data"
	@echo "  test         - Run Python tests and build the frontend"
