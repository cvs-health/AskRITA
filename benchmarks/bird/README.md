# BIRD Benchmark Evaluation for askRITA

Evaluate askRITA's text-to-SQL capabilities against the [BIRD benchmark](https://bird-bench.github.io/) — the industry-standard benchmark for large-scale database grounded text-to-SQL evaluation.

## What is BIRD?

BIRD (**BI**g Bench for La**R**ge-scale **D**atabase Grounded Text-to-SQL) is a cross-domain benchmark with:
- **12,751+** question-SQL pairs across **95** databases and **37** professional domains
- Real-world "dirty" data values requiring reasoning
- External knowledge evidence for domain-specific questions
- Difficulty levels: Simple (30%), Moderate (50%), Challenging (20%)

This module uses **BIRD Mini-Dev** (500 instances, 11 SQLite databases) — the recommended development evaluation set.

## Quick Start

### 1. Install Dependencies

```bash
pip install datasets func-timeout
```

### 2. Download BIRD Databases

The SQLite databases must be downloaded separately (not included in HuggingFace):

```bash
# Download from Google Drive:
# https://drive.google.com/file/d/13VLWIwpw5E3d5DUkMvzw7hvHE67a4XkG/view

# Extract to the data directory:
unzip minidev.zip -d ./benchmarks/bird/data/
# Ensure dev_databases/ folder is at: ./benchmarks/bird/data/dev_databases/
```

### 3. Run the Benchmark

```bash
# Full benchmark (500 questions) with GPT-4o
python -m benchmarks.bird.run_benchmark --provider openai --model gpt-4o

# Quick test on one database (~30 questions)
python -m benchmarks.bird.run_benchmark --provider openai --model gpt-4o --db-filter financial

# Cost-controlled test (10 questions)
python -m benchmarks.bird.run_benchmark --provider openai --model gpt-4o --limit 10

# Stratified sample: N questions spread proportionally across all 11 databases (default N=100).
# Produces benchmark_results.xlsx with a "Baseline vs askRITA" sheet (published Mini-Dev SQLite EX vs this run).
python -m benchmarks.bird.run_benchmark --provider openai --model gpt-4o --stratified
python -m benchmarks.bird.run_benchmark --provider openai --model gpt-4o --stratified --stratified-size 100 --stratified-seed 42

# Without oracle knowledge (harder, matches "without evidence" leaderboard)
python -m benchmarks.bird.run_benchmark --provider openai --model gpt-4o --no-evidence
```

### 4. View Results

Results are saved to `./benchmarks/bird/output/<model>_<timestamp>/`:

```
output/
└── gpt-4o_20260323_143000/
    ├── predictions.json          # BIRD-format (submittable to leaderboard)
    ├── detailed_results.json     # Per-question details with latency
    ├── evaluation_report.json    # EX and Soft F1 scores
    ├── run_summary.json          # Complete run metadata
    └── configs/                  # Generated askRITA configs per database
```

## Usage Examples

### Azure OpenAI

```bash
python -m benchmarks.bird.run_benchmark \
  --provider azure_openai \
  --model gpt-4o \
  --api-base https://your-endpoint.openai.azure.com/ \
  --deployment-name gpt-4o \
  --api-version 2024-08-01-preview
```

### Evaluate Existing Predictions

```bash
# Re-evaluate a previous run's predictions
python -m benchmarks.bird.run_benchmark \
  --evaluate-only \
  --predictions ./benchmarks/bird/output/gpt-4o_20260323/predictions.json
```

### Resume Interrupted Run

```bash
# Resumes from the last checkpoint
python -m benchmarks.bird.run_benchmark \
  --provider openai --model gpt-4o --resume
```

### Programmatic Usage

```python
from benchmarks.bird import BIRDDatasetManager, BIRDBenchmarkRunner, BIRDEvaluator

# Setup
dataset = BIRDDatasetManager(data_dir="./benchmarks/bird/data")
dataset.setup()

# Run
runner = BIRDBenchmarkRunner(
    dataset_manager=dataset,
    llm_provider="openai",
    llm_model="gpt-4o",
    include_evidence=True,
)
questions = dataset.load_questions(limit=10)
results = runner.run(questions=questions)

# Evaluate
evaluator = BIRDEvaluator(db_root_path=dataset.db_dir, num_workers=4)
report = evaluator.evaluate_from_results(results)
report.print_report()
```

## Evaluation Metrics

### EX (Execution Accuracy) — Primary Metric

The standard BIRD metric. A prediction scores 1 if executing the predicted SQL returns the **same result set** as the gold SQL (order-independent).

### Soft F1 Score

A more lenient metric that gives partial credit. Compares result sets row-by-row with cell-level matching, tolerating column reordering.

### Difficulty Breakdown

Results are broken down by BIRD's difficulty levels:
- **Simple** (30%): Single-table queries, basic aggregations
- **Moderate** (50%): Multi-table joins, subqueries, GROUP BY
- **Challenging** (20%): Complex reasoning, nested queries, external knowledge

## How It Works

```
┌─────────────────────────────────────────────────┐
│              BIRD Mini-Dev Dataset               │
│  500 questions × 11 SQLite databases             │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│           BIRDBenchmarkRunner                    │
│                                                  │
│  For each question:                              │
│  1. Create askRITA config for the target DB      │
│  2. Build prompt (question + optional evidence)  │
│  3. Run SQLAgentWorkflow.query()                 │
│  4. Extract generated SQL from WorkflowState     │
│  5. Save in BIRD prediction format               │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│              BIRDEvaluator                       │
│                                                  │
│  For each prediction:                            │
│  1. Execute predicted SQL against SQLite DB      │
│  2. Execute gold SQL against same DB             │
│  3. Compare result sets (EX, Soft F1)            │
│  4. Aggregate by difficulty level                │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│              EvaluationReport                    │
│                                                  │
│  EX:      simple=X%  moderate=Y%  challenging=Z% │
│  Soft F1: simple=X%  moderate=Y%  challenging=Z% │
│  Total EX: XX.XX%                                │
└─────────────────────────────────────────────────┘
```

## BIRD Leaderboard Context

For reference, here are some notable scores on the BIRD benchmark (with oracle knowledge):

| System | Dev EX (%) | Test EX (%) |
|--------|-----------|------------|
| Human Performance | 92.96 | — |
| AskData + GPT-4o (AT&T) | 77.64 | 81.95 |
| CHASE-SQL + Gemini (Google) | 74.90 | 76.02 |
| Claude Opus 4.6 (baseline) | 68.77 | 70.15 |
| GPT-4 (baseline) | 46.35 | 54.89 |
| ChatGPT (baseline) | 37.22 | 39.30 |

Source: [BIRD Leaderboard](https://bird-bench.github.io/) (March 2026)

## File Structure

```
benchmarks/bird/
├── __init__.py          # Package exports
├── setup_data.py        # Dataset download and management
├── runner.py            # Benchmark runner (askRITA integration)
├── evaluate.py          # BIRD-compatible evaluation metrics
├── run_benchmark.py     # CLI entry point
├── README.md            # This file
├── data/                # Downloaded dataset (gitignored)
│   ├── mini_dev_sqlite.json
│   ├── mini_dev_sqlite_gold.sql
│   ├── mini_dev_sqlite.jsonl
│   └── dev_databases/
│       ├── financial/
│       ├── formula_1/
│       └── ...
└── output/              # Benchmark results (gitignored)
    └── <model>_<timestamp>/
```

## Submitting to the BIRD Leaderboard

The `predictions.json` file produced by this benchmark is in BIRD's official format. To submit:

1. Run the full benchmark (all 500 Mini-Dev questions)
2. Locate `predictions.json` in the output directory
3. Follow submission instructions at [bird-bench.github.io](https://bird-bench.github.io/)
4. Email `bird.bench23@gmail.com` with your predictions for test set evaluation

## Citation

If you use this benchmark evaluation, please cite the BIRD benchmark:

```bibtex
@article{li2024can,
  title={Can llm already serve as a database interface? a big bench for large-scale database grounded text-to-sqls},
  author={Li, Jinyang and Hui, Binyuan and Qu, Ge and Yang, Jiaxi and Li, Binhua and Li, Bowen and Wang, Bailin and Qin, Bowen and Geng, Ruiying and Huo, Nan and others},
  journal={Advances in Neural Information Processing Systems},
  volume={36},
  year={2024}
}
```
