# BIRD Mini-Interact Benchmark for askRITA

Multi-turn interactive text-to-SQL evaluation using the [BIRD-Interact](https://bird-interact.github.io/) benchmark (Mini-Interact subset, 300 tasks, SQLite).

## Overview

Unlike the single-turn [BIRD Mini-Dev](../bird/) benchmark, Mini-Interact tasks start with an **ambiguous** user query. The system (askRITA) must converse with a **user simulator** (LLM-based) to clarify ambiguities before generating SQL. The SQL is then evaluated against executable **test cases**.

Key features:
- **Multi-turn conversation**: askRITA asks clarifying questions, user simulator responds
- **User simulator**: 2-step LLM process (encoder + decoder) following the official BIRD protocol
- **Test-case evaluation**: Reward scoring (1.0 first try, 0.5 after debug, 0 fail)
- **Graceful GT handling**: Works without ground-truth; instructions provided for obtaining GT

## Quick Start

### 1. Install Dependencies

```bash
pip install sqlglot openai openpyxl
```

### 2. Run Benchmark

```bash
# Full benchmark (300 tasks)
python -m benchmarks.bird_interact --provider openai --model gpt-4o

# Quick test (5 tasks)
python -m benchmarks.bird_interact --provider openai --model gpt-4o --limit 5

# Filter by database
python -m benchmarks.bird_interact --provider openai --model gpt-4o --db-filter financial
```

### 3. With Ground-Truth Evaluation

Ground-truth data (test cases, solution SQL) must be requested separately:

1. Email `bird.bench25@gmail.com` with subject: `[mini-interact GT&Test Cases]`
2. Save the received JSONL file
3. Run with `--gt-path`:

```bash
python -m benchmarks.bird_interact --provider openai --model gpt-4o --gt-path ./gt.jsonl
```

## CLI Arguments

| Argument | Default | Description |
|---|---|---|
| `--provider` | `openai` | LLM provider (`openai`, `azure_openai`, `vertex_ai`, `bedrock`) |
| `--model` | `gpt-4o` | System model for askRITA |
| `--user-sim-model` | `gpt-4o` | Model for user simulator |
| `--patience` | `3` | Extra turns beyond ambiguity count |
| `--limit` | all | Max tasks to process |
| `--db-filter` | all | Filter to specific database |
| `--gt-path` | none | Path to GT JSONL file |
| `--evaluate-only` | - | Evaluate existing results only |
| `--results` | - | Path to results JSONL (with `--evaluate-only`) |
| `--resume` | - | Resume from checkpoint |
| `--ca-bundle` | - | CA bundle for SSL/proxy |
| `--timeout` | `300` | Per-task timeout (seconds) |
| `-v` | - | Verbose logging |

## Architecture

```
benchmarks/bird_interact/
  __init__.py              # Package exports
  __main__.py              # python -m entry point
  setup_data.py            # Dataset download + MiniInteractTask dataclass
  user_simulator.py        # 2-step LLM user simulator (BIRD protocol)
  runner.py                # Multi-turn conversation loop
  evaluate.py              # Test-case evaluation + reward scoring
  run_benchmark.py         # CLI entry point
  README.md                # This file
```

### Conversation Flow

```
┌─────────────┐     ambiguous query + schema     ┌──────────────┐
│             │ ──────────────────────────────>   │              │
│   Runner    │     clarification question        │   askRITA    │
│             │ <──────────────────────────────   │  (Workflow)  │
│             │                                   │              │
│             │     user response                 └──────────────┘
│             │ ──── (from simulator) ─────>
│             │
│             │     ... loop until SQL or max_turn ...
│             │
│             │     ```sqlite SELECT ... ```
│             │ <──────────────────────────────
└─────────────┘

      │  predicted SQL
      ▼
┌─────────────┐
│  Evaluator  │ ── run test cases ── reward score
└─────────────┘
```

## Output Files

| File | Description |
|---|---|
| `benchmark_results.xlsx` | Spreadsheet with Summary, Per-Task, Conversations |
| `predictions.json` | Predicted SQL per task |
| `detailed_results.jsonl` | Full results with conversation history |
| `evaluation_report.json` | Reward scores and test-case results |
| `run_summary.json` | Complete run metadata |

## Dataset

The Mini-Interact dataset is automatically downloaded from HuggingFace:
- Repository: [birdsql/mini-interact](https://huggingface.co/datasets/birdsql/mini-interact)
- 300 tasks across multiple SQLite databases
- Each task includes: ambiguous query, ambiguity labels, schema, knowledge base
- Ground-truth (solution SQL, test cases) available via email request
