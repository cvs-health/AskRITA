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
# BIRD Benchmark Evaluation

Ask RITA includes two built-in evaluation suites based on the [BIRD benchmark](https://bird-bench.github.io/) — the industry-standard benchmark for large-scale database grounded text-to-SQL evaluation.

| Benchmark | Module | Questions | Focus |
|---|---|---|---|
| **BIRD Mini-Dev** | `benchmarks.bird` | 500 | Single-turn text-to-SQL accuracy |
| **BIRD Mini-Interact** | `benchmarks.bird_interact` | 300 | Multi-turn conversational SQL with clarification |

## Table of Contents

- [BIRD Mini-Dev](#bird-mini-dev)
    - [What is BIRD?](#what-is-bird)
    - [Setup](#setup)
    - [Running the Benchmark](#running-the-benchmark)
    - [CLI Reference](#cli-reference)
    - [Results and Metrics](#results-and-metrics)
- [BIRD Mini-Interact](#bird-mini-interact)
    - [What is BIRD-Interact?](#what-is-bird-interact)
    - [Interact Setup](#interact-setup)
    - [Running the Interact Benchmark](#running-the-interact-benchmark)
    - [Interact CLI Reference](#interact-cli-reference)
    - [User Simulator](#user-simulator)
    - [Interact Results and Metrics](#interact-results-and-metrics)
- [Automated Multi-Model Benchmarking](#automated-multi-model-benchmarking)

---

## BIRD Mini-Dev

### What is BIRD?

BIRD (**BI**g Bench for La**R**ge-scale **D**atabase Grounded Text-to-SQL) is a cross-domain benchmark with:

- **12,751+** question-SQL pairs across **95** databases and **37** professional domains
- Real-world "dirty" data values requiring reasoning
- External knowledge evidence for domain-specific questions
- Difficulty levels: Simple (30%), Moderate (50%), Challenging (20%)

This module uses **BIRD Mini-Dev** (500 instances, 11 SQLite databases) — the recommended development evaluation set.

### Setup

#### 1. Install Dependencies

```bash
poetry install --with dev
```

#### 2. Download BIRD Databases

The SQLite databases must be downloaded separately (they are too large to be included in the repository or HuggingFace):

1. Download the `minidev.zip` file from the [BIRD Google Drive](https://drive.google.com/file/d/13VLWIwpw5E3d5DUkMvzw7hvHE67a4XkG/view).
2. Extract the contents into the `benchmarks/bird/data/` directory.
3. Ensure the `dev_databases/` folder is located at: `benchmarks/bird/data/dev_databases/`

```bash
unzip minidev.zip -d ./benchmarks/bird/data/
```

### Running the Benchmark

The benchmark runner supports multiple LLM providers (OpenAI, Vertex AI, Azure OpenAI, Bedrock) and automatically manages the Ask RITA configuration, prompt generation, SQL execution, and metric calculation.

#### Basic Usage

Run the full benchmark (500 questions) with GPT-4o:

```bash
poetry run python -m benchmarks.bird.run_benchmark --provider openai --model gpt-4o
```

#### Quick Tests and Cost Control

Run a quick test on a single database (~30 questions):

```bash
poetry run python -m benchmarks.bird.run_benchmark --provider openai --model gpt-4o --db-filter financial
```

Limit the total number of questions processed:

```bash
poetry run python -m benchmarks.bird.run_benchmark --provider openai --model gpt-4o --limit 10
```

Run a stratified sample (proportionally across all 11 databases):

```bash
poetry run python -m benchmarks.bird.run_benchmark --provider openai --model gpt-4o --stratified --stratified-size 100
```

Omit external knowledge/evidence from prompts:

```bash
poetry run python -m benchmarks.bird.run_benchmark --provider openai --model gpt-4o --no-evidence
```

#### Resuming a Failed Run

If a run is interrupted, resume from the checkpoint:

```bash
poetry run python -m benchmarks.bird.run_benchmark --provider openai --model gpt-4o --resume
```

This loads `predictions_checkpoint.json` from the latest matching output directory and skips already-completed questions.

#### Evaluate-Only Mode

Re-evaluate existing predictions without re-running SQL generation:

```bash
poetry run python -m benchmarks.bird.run_benchmark \
  --evaluate-only \
  --predictions ./benchmarks/bird/output/gpt-4o_20250101_120000/predictions.json
```

#### Provider-Specific Configurations

**Vertex AI (Gemini):**

```bash
poetry run python -m benchmarks.bird.run_benchmark \
  --provider vertex_ai \
  --model gemini-2.5-pro \
  --project-id your-gcp-project-id \
  --credentials-path /path/to/service-account.json
```

Use gcloud CLI authentication instead of a service account:

```bash
poetry run python -m benchmarks.bird.run_benchmark \
  --provider vertex_ai \
  --model gemini-2.5-pro \
  --project-id your-gcp-project-id \
  --gcloud-cli-auth \
  --location us-central1
```

**Azure OpenAI:**

```bash
poetry run python -m benchmarks.bird.run_benchmark \
  --provider azure_openai \
  --model gpt-4o \
  --api-base https://your-endpoint.openai.azure.com/ \
  --deployment-name gpt-4o \
  --api-version 2024-08-01-preview
```

**Corporate Proxies (Zscaler):**

```bash
poetry run python -m benchmarks.bird.run_benchmark \
  --provider openai \
  --model gpt-4o \
  --ca-bundle credentials/zscaler-ca-bundle.pem
```

### CLI Reference

| Flag | Default | Description |
|---|---|---|
| `--provider` | `openai` | LLM provider: `openai`, `azure_openai`, `vertex_ai`, `bedrock` |
| `--model` | `gpt-4o` | Model name |
| `--api-key` | From env | API key (overrides environment variable) |
| `--api-base` | — | OpenAI base URL or Azure endpoint |
| `--api-version` | — | Azure API version |
| `--deployment-name` | — | Azure deployment name |
| `--project-id` | — | GCP project ID (Vertex AI) |
| `--credentials-path` | — | Service account JSON path (Vertex AI) |
| `--location` | `us-central1` | GCP region (Vertex AI) |
| `--gcloud-cli-auth` | `false` | Use gcloud CLI auth (Vertex AI) |
| `--ca-bundle` | — | CA bundle PEM path for corporate proxies |
| `--limit` | — | Max questions to process |
| `--db-filter` | — | Only process questions for one database |
| `--stratified` | `false` | Use stratified sampling across databases |
| `--stratified-size` | `100` | Number of questions in stratified sample |
| `--stratified-seed` | `42` | Random seed for stratified sampling |
| `--no-evidence` | `false` | Omit external knowledge from prompts |
| `--max-retries` | `2` | SQL generation retries per question |
| `--timeout` | `120` | Per-question timeout (seconds) |
| `--resume` | `false` | Resume from checkpoint in latest matching output dir |
| `--evaluate-only` | `false` | Skip generation; evaluate existing predictions |
| `--predictions` | — | Path to predictions JSON (for `--evaluate-only`) |
| `--eval-timeout` | `30` | SQL execution timeout during evaluation (seconds) |
| `--eval-workers` | `4` | Parallel evaluation workers |
| `--data-dir` | `./benchmarks/bird/data` | BIRD data directory |
| `--output-dir` | `./benchmarks/bird/output` | Output parent directory |
| `--local-data` | `false` | Skip HuggingFace download; use local data only |
| `-v` / `--verbose` | `false` | Debug logging |

### Results and Metrics

Results are saved to `./benchmarks/bird/output/<model>_<timestamp>/`:

- `predictions.json`: Generated SQL in BIRD's official format (submittable to the leaderboard)
- `detailed_results.json`: Per-question details including latency, generated SQL, and errors
- `evaluation_report.json`: Final EX and Soft F1 scores
- `benchmark_results.xlsx`: Spreadsheet comparing baseline scores vs Ask RITA

#### Evaluation Metrics

1. **EX (Execution Accuracy) — Primary Metric:** A prediction scores 1 if executing the predicted SQL returns the *exact same result set* as the gold SQL (order-independent).
2. **Soft F1 Score:** A more lenient metric that gives partial credit by comparing result sets row-by-row with cell-level matching, tolerating column reordering.

---

## BIRD Mini-Interact

### What is BIRD-Interact?

BIRD Mini-Interact is a **conversational** text-to-SQL benchmark. Instead of single-turn question-SQL pairs, each task starts with an **ambiguous query** that requires clarification. The system must:

1. Identify the ambiguity in the user's question
2. Ask clarifying questions
3. Receive responses from a **user simulator** (LLM-powered)
4. Generate the correct SQL after sufficient clarification

The benchmark evaluates both the system's ability to ask good clarifying questions and to produce correct SQL from multi-turn conversations.

- **300 tasks** across SQLite databases
- **Multiple ambiguity types** per task (user ambiguity + knowledge ambiguity)
- **User simulator** powered by an LLM (default: GPT-4o) that provides natural responses based on ground-truth SQL

### Interact Setup

#### 1. Install Dependencies

```bash
poetry install --with dev
```

#### 2. Data Download

The dataset is cloned automatically from HuggingFace on first run:

```
https://huggingface.co/datasets/birdsql/mini-interact
```

This requires `git` and `git-lfs` to be installed. The data is placed in `benchmarks/bird_interact/data/mini-interact/`.

#### 3. Ground Truth (Optional)

The official ground truth SQL is not publicly available. To obtain it:

1. Email `bird.bench25@gmail.com` with subject `[mini-interact GT&Test Cases]`
2. Once received, merge it into the tasks file:

```bash
poetry run python -m benchmarks.bird_interact \
  --provider openai --model gpt-4o \
  --gt-path /path/to/ground_truth.jsonl
```

Without ground truth, the benchmark runs generation but skips evaluation.

### Running the Interact Benchmark

#### Basic Usage

```bash
poetry run python -m benchmarks.bird_interact --provider openai --model gpt-4o
```

#### With a Different User Simulator Model

The system LLM and user simulator LLM can be different models:

```bash
poetry run python -m benchmarks.bird_interact \
  --provider openai --model gpt-4o \
  --user-sim-model gpt-4o-mini
```

#### Quick Test

```bash
poetry run python -m benchmarks.bird_interact \
  --provider openai --model gpt-4o \
  --limit 10 --db-filter financial
```

#### Resuming

```bash
poetry run python -m benchmarks.bird_interact \
  --provider openai --model gpt-4o --resume
```

#### Evaluate-Only

Re-evaluate existing results:

```bash
poetry run python -m benchmarks.bird_interact \
  --evaluate-only \
  --results ./benchmarks/bird_interact/output/gpt-4o_interact_20250101/detailed_results.jsonl
```

### Interact CLI Reference

| Flag | Default | Description |
|---|---|---|
| `--provider` | `openai` | LLM provider for the Ask RITA system |
| `--model` | `gpt-4o` | System model name |
| `--user-sim-model` | `gpt-4o` | Model for the user simulator |
| `--api-key` | From env | API key override |
| `--api-base` | — | OpenAI base URL or Azure endpoint |
| `--api-version` | — | Azure API version |
| `--deployment-name` | — | Azure deployment name |
| `--ca-bundle` | — | CA bundle PEM path |
| `--limit` | — | Max tasks to process |
| `--db-filter` | — | Only tasks for one database |
| `--patience` | `3` | Extra turns beyond task ambiguity count |
| `--max-retries` | `2` | SQL generation retries |
| `--timeout` | `300` | Per-task timeout (seconds) |
| `--resume` | `false` | Resume from checkpoint |
| `--evaluate-only` | `false` | Evaluate existing results only |
| `--results` | — | JSONL path (for `--evaluate-only`) |
| `--gt-path` | — | Ground truth JSONL to merge into tasks |
| `--eval-timeout` | `30` | SQL execution timeout during evaluation |
| `--data-dir` | `./benchmarks/bird_interact/data` | Data directory |
| `--output-dir` | `./benchmarks/bird_interact/output` | Output parent directory |
| `-v` / `--verbose` | `false` | Debug logging |

### User Simulator

The user simulator is an LLM-based agent that plays the role of the user in the conversation. It:

1. **Encodes** the system's clarifying question — classifies each question as addressing a `labeled` ambiguity, an `unlabeled` ambiguity, or as `unanswerable`
2. **Decodes** a natural-language response — uses the ground-truth SQL segments, schema, and ambiguity definitions to generate a helpful but natural user reply

The simulator uses the OpenAI client directly (not through Ask RITA) and can be configured with `--user-sim-model` and `--ca-bundle`.

When no ground-truth SQL is available for a task, the simulator returns a generic "use your best judgment" response.

### Interact Results and Metrics

Results are saved to `./benchmarks/bird_interact/output/<model>_interact_<timestamp>/`:

- `predictions.json`: Generated SQL for each task
- `detailed_results.jsonl`: Per-task details including conversation history
- `evaluation_report.json`: Reward scores and pass rates
- `run_summary.json`: Run configuration and timing
- `benchmark_results.xlsx`: Spreadsheet with Summary, Per-Task Results, and Conversations sheets

#### Evaluation Metrics

1. **Reward Score (Primary):** `1.0` if all test cases pass (or execution accuracy matches gold SQL); `0.0` otherwise.
2. **Test Pass Rate:** Percentage of test cases passed per task (when test cases are available).
3. **Per-Database Reward:** Average reward broken down by database.

Test cases can include:

- **Result match**: Execute a test SQL and compare result sets with the prediction
- **Value check**: Verify that expected values appear in the prediction's result set

---

## Automated Multi-Model Benchmarking

The `run_all_benchmarks.sh` script in the `benchmarks/bird/` directory automates the process of running the BIRD Mini-Dev benchmark across all supported models (GPT-5.4, GPT-5.4 Mini, GPT-5.4 Nano, Gemini 2.5 Pro, Gemini 2.5 Flash, Gemini 2.5 Flash-Lite) and updates the results chart in `README.md`.

```bash
cd benchmarks/bird
./run_all_benchmarks.sh
```

*(Note: Running the full suite across 6 models takes approximately 15-18 hours. Ensure you are on a network that does not block the respective LLM APIs.)*

---

**See also:**

- [Configuration Guide](../configuration/overview.md) — Complete YAML configuration reference
- [Supported Platforms](../supported-platforms.md) — LLM provider setup
- [Conversational SQL](../guides/conversational-sql.md) — Multi-turn chat mode in Ask RITA
