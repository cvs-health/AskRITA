<!--
  © 2026 CVS Health and/or one of its affiliates. All rights reserved.

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.
-->
# Unit Test Coverage Report

**Generated:** 2026-03-26 | **Python:** 3.13 | **Tool:** pytest-cov

## Summary

| Metric | Value |
|--------|------:|
| **Total statements** | 8,638 |
| **Statements covered** | 7,354 |
| **Statements missed** | 1,284 |
| **Overall coverage** | **85.1%** |
| **Tests passing** | 1,524 |
| **Tests skipped** | 10 |

## Coverage by Module

| Module | Files | Stmts | Miss | Coverage |
|--------|------:|------:|-----:|---------:|
| `askrita/exceptions.py` | 1 | 18 | 0 | 100.0% |
| `askrita/config_manager.py` | 1 | 631 | 7 | 98.9% |
| `askrita/models/` | 4 | 76 | 2 | 97.4% |
| `askrita/utils/` | 10 | 1,413 | 128 | 90.9% |
| `askrita/cli.py` | 1 | 223 | 33 | 85.2% |
| `askrita/sqlagent/` | 23 | 4,994 | 826 | 83.5% |
| `askrita/__init__.py` | 1 | 47 | 8 | 83.0% |
| `askrita/research/` | 4 | 1,236 | 280 | 77.3% |

## Coverage by File (below 90%)

Files at or above 90% are omitted for brevity. 15 files have 100% coverage.

| File | Stmts | Miss | Coverage |
|------|------:|-----:|---------:|
| `askrita/utils/llm_models.py` | 10 | 5 | 50.0% |
| `askrita/research/ResearchAgent.py` | 408 | 149 | 63.5% |
| `askrita/sqlagent/database/DatabaseManager.py` | 390 | 140 | 64.1% |
| `askrita/sqlagent/database/database_factory.py` | 35 | 9 | 74.3% |
| `askrita/research/SchemaAnalyzer.py` | 344 | 84 | 75.6% |
| `askrita/sqlagent/progress_tracker.py` | 30 | 7 | 76.7% |
| `askrita/sqlagent/workflows/NoSQLAgentWorkflow.py` | 654 | 148 | 77.4% |
| `askrita/sqlagent/database/NoSQLDatabaseManager.py` | 241 | 49 | 79.7% |
| `askrita/sqlagent/database/schema_decorators.py` | 383 | 77 | 79.9% |
| `askrita/utils/pii_detector.py` | 155 | 31 | 80.0% |
| `askrita/sqlagent/exporters/excel_exporter.py` | 286 | 52 | 81.8% |
| `askrita/utils/LLMManager.py` | 317 | 56 | 82.3% |
| `askrita/sqlagent/database/validation_chain.py` | 150 | 25 | 83.3% |
| `askrita/sqlagent/workflows/SQLAgentWorkflow.py` | 1,150 | 180 | 84.3% |
| `askrita/cli.py` | 223 | 33 | 85.2% |
| `askrita/sqlagent/exporters/core.py` | 453 | 57 | 87.4% |
| `askrita/sqlagent/exporters/chart_generator.py` | 455 | 48 | 89.5% |
| `askrita/sqlagent/formatters/DataFormatter.py` | 138 | 14 | 89.9% |

## Files with 100% Coverage (15)

`exceptions.py`, `models/__init__.py`, `models/chain_of_thoughts.py`, `models/step_details.py`, `research/__init__.py`, `sqlagent/State.py`, `sqlagent/__init__.py`, `sqlagent/database/__init__.py`, `sqlagent/database/database_strategies.py`, `sqlagent/exporters/__init__.py`, `sqlagent/exporters/models.py`, `sqlagent/formatters/__init__.py`, `sqlagent/graph_instructions.py`, `sqlagent/workflows/__init__.py`, `utils/__init__.py`, `utils/cot_config_validator.py`, `utils/step_registry.py`

## How to Regenerate

```bash
source .venv/bin/activate

# Terminal report with missing lines
python -m pytest tests/ --cov=askrita --cov-report=term-missing

# HTML report (opens in browser)
python -m pytest tests/ --cov=askrita --cov-report=html:htmlcov
open htmlcov/index.html

# Fail if coverage drops below threshold
python -m pytest tests/ --cov=askrita --cov-fail-under=80
```

## Coverage Thresholds

| Tier | Target | Applies to |
|------|-------:|------------|
| New code | 80% | Any newly added module |
| Core modules | 70% | `config_manager`, `LLMManager`, formatters |
| Overall project | 80% | Gated via `--cov-fail-under` |
