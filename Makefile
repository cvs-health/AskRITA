# AskRITA Developer Makefile
# ---------------------------
# Utility commands for local development, testing, and CI validation.

.PHONY: help install dev-install lint format test security build ci clean

# Default target
help:
	@echo "AskRITA Developer Workflows:"
	@echo "  make install      - Install production and dev dependencies"
	@echo "  make dev-install  - Install all dependencies (including examples/pygraphviz)"
	@echo "  make lint         - Run all linters (check only)"
	@echo "  make format       - Fix formatting and import sorting"
	@echo "  make test         - Run full test suite with coverage"
	@echo "  make security     - Run security audits (bandit, pip-audit)"
	@echo "  make ci           - Run full CI suite (lint + security + test)"
	@echo "  make build        - Build sdist and wheel packages"
	@echo "  make clean        - Remove build and cache artifacts"

# ─────────────
# Installation
# ─────────────

install:
	poetry install --with test

dev-install:
	@echo "Note: Requires system headers (graphviz-dev) for pygraphviz."
	poetry install --with test,examples --extras exports

# ─────────────
# Quality gates
# ─────────────

lint:
	poetry run black --check askrita tests
	poetry run isort --check-only askrita tests
	poetry run flake8 askrita tests
	poetry run mypy askrita

format:
	poetry run isort .
	poetry run black .

test:
	poetry run pytest tests/ -v --cov=askrita --cov-report=term-missing --cov-fail-under=80

security:
	poetry run bandit -r askrita -ll -ii
	poetry run python -m pip install --upgrade pip
	poetry run pip-audit

# ─────────────
# Automation
# ─────────────

ci: lint security test
	@echo "CI suite passed successfully ✓"

build:
	poetry build

clean:
	rm -rf .pytest_cache .mypy_cache .coverage coverage.xml dist/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
