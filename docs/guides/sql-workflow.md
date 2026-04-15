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
# SQL Workflow Guide

Complete guide for using Ask RITA's `SQLAgentWorkflow` to query SQL databases with natural language. This is the core workflow that powers text-to-SQL across PostgreSQL, MySQL, BigQuery, Snowflake, SQLite, and Db2.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [API Reference](#api-reference)
- [How It Works](#how-it-works)
- [Workflow Steps](#workflow-steps)
- [Initialization Options](#initialization-options)
- [Troubleshooting](#troubleshooting)

## Overview

`SQLAgentWorkflow` converts natural language questions into SQL, executes them against your database, and returns formatted answers with visualization recommendations. It uses a LangGraph state machine that orchestrates up to 10 configurable steps.

| Component | Role |
|---|---|
| `SQLAgentWorkflow` | Orchestrates the full question-to-answer pipeline |
| `DatabaseManager` | Manages database connections, schema introspection, and query execution |
| `LLMManager` | Handles LLM interactions across providers (OpenAI, Azure, Vertex AI, Bedrock) |
| `ConfigManager` | Loads and validates YAML configuration |
| `WorkflowState` | Carries data through every step of the pipeline |

Key capabilities:

- **Natural language to SQL** — Ask questions in plain English; get SQL, results, and answers
- **Multi-turn conversations** — Use `chat()` for follow-up questions with context
- **Visualization** — Automatic chart type selection and `UniversalChartData` for any charting library
- **Exports** — Generate PPTX, PDF, and Excel reports from query results
- **Observability** — Chain of Thoughts tracing and progress callbacks
- **Security** — SQL safety validation, prompt injection detection, PII/PHI scanning

## Quick Start

### 1. Install

```bash
pip install askrita
```

### 2. Set Environment Variables

```bash
# For OpenAI
export OPENAI_API_KEY="your-api-key"

# For Azure OpenAI
export AZURE_OPENAI_API_KEY="your-key"

# For Vertex AI — use service account or gcloud CLI auth
# For Bedrock — use AWS credentials
```

### 3. Create Configuration

Create a `config.yaml` with three required sections — `database`, `llm`, and `prompts`:

```yaml
database:
  connection_string: "postgresql://${DB_USER}:${DB_PASSWORD}@localhost:5432/mydb"
  query_timeout: 30
  max_results: 1000
  cache_schema: true
  schema_refresh_interval: 3600

llm:
  provider: "openai"
  model: "gpt-4o"
  temperature: 0.1
  max_tokens: 4000

workflow:
  max_retries: 3
  steps:
    parse_question: true
    get_unique_nouns: true
    generate_sql: true
    validate_and_fix_sql: true
    execute_sql: true
    format_results: true
    choose_and_format_visualization: true

prompts:
  parse_question:
    system: "You are a database expert."
    human: |
      Given the following database schema:
      {schema}
      Determine if this question is relevant: {question}

  generate_sql:
    system: "You are a SQL expert."
    human: |
      Schema: {schema}
      Unique values: {unique_nouns}
      Parsed question: {parsed_question}
      Generate SQL for: {question}

  validate_sql:
    system: "You are a SQL validator."
    human: |
      Schema: {schema}
      Validate and fix this SQL: {sql_query}

  format_results:
    system: "You are a data analyst."
    human: |
      Question: {question}
      SQL: {sql_query}
      Results: {query_results}
      Provide a clear answer.

  choose_and_format_visualization:
    system: "You are a data visualization expert."
    human: |
      Question: {question}
      SQL: {sql_query}
      Results: {query_results}
      Choose a chart type and format the data.
```

### 4. Query Your Database

```python
from askrita import SQLAgentWorkflow, ConfigManager

config = ConfigManager("config.yaml")
workflow = SQLAgentWorkflow(config)

result = workflow.query("What are the top 10 customers by revenue?")

print(f"Answer: {result.answer}")
print(f"SQL: {result.sql_query}")
print(f"Chart: {result.visualization}")
```

### 5. Factory Shortcut

```python
from askrita import create_sql_agent

workflow = create_sql_agent("config.yaml")
result = workflow.query("How many orders last month?")
```

## Configuration

### Database (`database`)

```yaml
database:
  connection_string: "postgresql://${DB_USER}:${DB_PASSWORD}@host:5432/db"
  query_timeout: 30              # Query timeout in seconds
  max_results: 1000              # Maximum rows returned
  cache_schema: true             # Cache schema in memory
  schema_refresh_interval: 3600  # Cache TTL in seconds
```

Supported connection strings:

| Database | Connection String |
|---|---|
| PostgreSQL | `postgresql://${DB_USER}:${DB_PASSWORD}@host:5432/db` |
| MySQL | `mysql+pymysql://${DB_USER}:${DB_PASSWORD}@host:3306/db` |
| SQLite | `sqlite:///path/to/database.db` |
| BigQuery | `bigquery://project-id/dataset` |
| Snowflake | `snowflake://${DB_USER}:${DB_PASSWORD}@account/db/schema` |
| Db2 | `db2+ibm_db://${DB_USER}:${DB_PASSWORD}@host:50000/db` |

See [Supported Platforms](../supported-platforms.md) for detailed connection string examples and authentication options.

### LLM Provider (`llm`)

```yaml
llm:
  provider: "openai"       # openai, azure_openai, vertex_ai, bedrock
  model: "gpt-4o"
  temperature: 0.1
  max_tokens: 4000
  timeout: 120
```

### Workflow Steps (`workflow`)

```yaml
workflow:
  max_retries: 3              # SQL generation retry attempts
  timeout_per_step: 120       # Per-step timeout in seconds
  steps:
    pii_detection: false                    # PII/PHI scanning (disabled by default)
    parse_question: true                    # Determine question relevance
    get_unique_nouns: true                  # Extract distinct values from DB
    generate_sql: true                      # LLM generates SQL
    validate_and_fix_sql: true              # LLM validates and fixes SQL
    execute_sql: true                       # Execute SQL against database
    format_results: true                    # Format results into an answer
    choose_and_format_visualization: true   # Combined visualization (recommended)
    generate_followup_questions: false      # Suggest follow-up questions
```

#### Visualization Modes

Choose **one** approach:

| Mode | Steps | LLM Calls | Recommended |
|---|---|---|---|
| **Combined** (default) | `choose_and_format_visualization: true` | 1 | Yes |
| **Separate** (legacy) | `choose_visualization: true` + `format_data_for_visualization: true` | 2 | No |

### Prompts (`prompts`)

Each enabled step that uses the LLM requires a corresponding prompt with `system` and `human` keys. Available template variables vary by step:

| Prompt | Required Variables |
|---|---|
| `parse_question` | `{schema}`, `{question}` |
| `generate_sql` | `{schema}`, `{unique_nouns}`, `{parsed_question}`, `{question}` |
| `validate_sql` | `{schema}`, `{sql_query}` |
| `format_results` | `{question}`, `{sql_query}`, `{query_results}` |
| `choose_and_format_visualization` | `{question}`, `{sql_query}`, `{query_results}` |
| `generate_followup_questions` | `{question}`, `{answer}`, `{sql_query}`, `{results_summary}`, `{schema_context}` |

### Optional Sections

```yaml
# Chain of Thoughts observability
chain_of_thoughts:
  enabled: true

# Framework settings
framework:
  results_limit_for_llm: 50     # Max rows sent to LLM for formatting
  debug: false

# PII/PHI detection
pii_detection:
  enabled: true
  block_on_detection: true

# SQL safety overrides (add under the workflow: key above)
#  sql_safety:
#    allow_select_star: false
#  input_validation:
#    max_question_length: 10000
#  conversation_context:
#    max_history_messages: 6
```

## Usage Examples

### Single Query

```python
from askrita import SQLAgentWorkflow, ConfigManager

config = ConfigManager("config.yaml")
workflow = SQLAgentWorkflow(config)

result = workflow.query("What are total sales by region this quarter?")

print(f"Answer: {result.answer}")
print(f"SQL: {result.sql_query}")
print(f"Why this SQL: {result.sql_reason}")
print(f"Chart type: {result.visualization}")
print(f"Why this chart: {result.visualization_reason}")

if result.chart_data:
    print(f"Chart data: {result.chart_data}")

if result.followup_questions:
    for q in result.followup_questions:
        print(f"  Follow-up: {q}")
```

### Multi-Turn Conversation

```python
messages = []

# Turn 1
messages.append({"role": "user", "content": "Show me the top 10 customers by revenue"})
result = workflow.chat(messages)
print(result.answer)

# Turn 2 — references previous context
messages.append({"role": "assistant", "content": result.answer})
messages.append({"role": "user", "content": "What products do they buy most?"})
result = workflow.chat(messages)
print(result.answer)
```

See [Conversational SQL](conversational-sql.md) for details on context handling, follow-ups, and clarification.

### With Progress Tracking

```python
from askrita.sqlagent.progress_tracker import create_simple_progress_callback

workflow = SQLAgentWorkflow(
    config,
    progress_callback=create_simple_progress_callback()
)

result = workflow.query("Average order value by month")
# Prints step-by-step progress to console
```

### With Chain of Thoughts

```python
def on_cot_event(event):
    if event["event_type"] == "cot_step_completed":
        step = event["cot_step"]
        print(f"  {step['step_name']}: {step['status']} ({step.get('duration_ms', 0):.0f}ms)")

workflow.register_cot_listener(on_cot_event)
result = workflow.query("How many active users this month?")
```

See [Chain of Thoughts](chain-of-thoughts.md) for the full observability API.

### Export Results

```python
result = workflow.query("Revenue by product category")

# PowerPoint
pptx_bytes = workflow.export_to_pptx(result, title="Revenue Report")
with open("report.pptx", "wb") as f:
    f.write(pptx_bytes)

# PDF
pdf_bytes = workflow.export_to_pdf(result, title="Revenue Report")
with open("report.pdf", "wb") as f:
    f.write(pdf_bytes)

# Excel
excel_bytes = workflow.export_to_excel(result, title="Revenue Report")
with open("report.xlsx", "wb") as f:
    f.write(excel_bytes)
```

See [Exports](exports.md) for full details on export settings and brand customization.

### Schema Inspection

```python
# Raw schema (DDL string)
print(workflow.schema)

# Structured schema (parsed dict)
for table_name, info in workflow.structured_schema["tables"].items():
    print(f"\n{table_name}:")
    for col in info["columns"]:
        print(f"  {col['name']}: {col['type']}")

# Schema cache control
status = workflow.get_cache_status()
print(f"Cache valid: {status['valid']}, age: {status.get('age_seconds', 0):.0f}s")

workflow.clear_schema_cache()    # Force refresh on next query
workflow.preload_schema()        # Preload into cache now
```

### Save Workflow Diagram

```python
workflow.save_workflow_diagram("workflow.png")
```

Generates a PNG of the LangGraph state machine showing all enabled steps and their connections.

## API Reference

### SQLAgentWorkflow

```python
class SQLAgentWorkflow:
    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        test_llm_connection: bool = True,
        test_db_connection: bool = True,
        init_schema_cache: bool = True,
        progress_callback: Optional[Callable] = None,
    ): ...

    # Query methods
    def query(self, question: str) -> WorkflowState: ...
    def chat(self, messages: list) -> WorkflowState: ...
    def query_with_cot(self, question: str) -> ChainOfThoughtsOutput: ...

    # Export methods
    def export_to_pptx(self, output_state, title=..., ...) -> bytes: ...
    def export_to_pdf(self, output_state, title=..., ...) -> bytes: ...
    def export_to_excel(self, output_state, title=..., ...) -> bytes: ...

    # Schema
    @property
    def schema(self) -> str: ...
    @property
    def structured_schema(self) -> dict: ...
    def preload_schema(self) -> None: ...
    def clear_schema_cache(self) -> None: ...
    def get_cache_status(self) -> dict: ...

    # CoT listeners
    def register_cot_listener(self, listener: Callable) -> None: ...
    def unregister_cot_listener(self, listener: Callable) -> None: ...
    def clear_cot_listeners(self) -> None: ...

    # Graph
    def get_graph(self): ...
    def save_workflow_diagram(self, output_path: str) -> None: ...

    # Attributes
    db_manager: DatabaseManager
    llm_manager: LLMManager
```

### WorkflowState (Result Object)

The result returned by `query()` and `chat()`:

| Field | Type | Description |
|---|---|---|
| `question` | `str` | Original question |
| `messages` | `list` | Chat history (from `chat()`) |
| `parsed_question` | `dict` | Parsed question analysis |
| `unique_nouns` | `list` | Distinct values found in DB |
| `sql_query` | `str` | Generated SQL |
| `sql_reason` | `str` | Explanation of SQL approach |
| `sql_valid` | `bool` | Whether SQL passed validation |
| `sql_issues` | `str` | Validation issues found |
| `results` | `list` | Raw query results |
| `answer` | `str` | Human-readable answer |
| `analysis` | `str` | Detailed analysis |
| `visualization` | `str` | Recommended chart type |
| `visualization_reason` | `str` | Why this chart was chosen |
| `chart_data` | `UniversalChartData` | Pydantic model for chart rendering |
| `followup_questions` | `list` | Suggested follow-up questions |
| `needs_clarification` | `bool` | Whether the question needs clarification |
| `clarification_prompt` | `str` | Clarification prompt for the user |
| `clarification_questions` | `list` | Specific clarification questions |
| `execution_error` | `str` | Error message if execution failed |
| `retry_count` | `int` | Number of SQL retry attempts |
| `is_relevant` | `bool` | Whether question is relevant to the DB |
| `chain_of_thoughts` | `dict` | CoT trace (when enabled) |
| `error` | `str` | General error message |

### DatabaseManager

```python
class DatabaseManager:
    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        test_llm_connection: bool = True,
        test_db_connection: bool = True,
    ): ...

    def get_schema(self) -> str: ...
    def execute_query(self, query: str) -> List[Dict[str, Any]]: ...
    def get_sample_data(self, limit: int = 100) -> Dict[str, List[Dict]]: ...
    def test_connection(self) -> bool: ...
    def get_table_names(self) -> List[str]: ...
    def get_connection_info(self) -> dict: ...
```

### LLMManager

```python
class LLMManager:
    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        test_connection: bool = True,
    ): ...

    def test_connection(self) -> bool: ...
    def get_model_info(self) -> Dict[str, Any]: ...
    def invoke(self, prompt: ChatPromptTemplate, **kwargs) -> str: ...
    def invoke_with_structured_output(self, prompt_name, response_model, ...) -> BaseModel: ...
    def cleanup(self) -> None: ...
```

### create_sql_agent

```python
def create_sql_agent(config_path: str = None) -> SQLAgentWorkflow:
    """
    Factory function for quick setup.
    Loads config, validates it, and returns a ready-to-use workflow.
    """
```

## How It Works

### Workflow Pipeline

```mermaid
flowchart TD
    A[User Question] --> B["PII Detection (optional)"]
    B -->|"Scan question for personal data"| C[Parse Question]
    C -->|"LLM checks relevance to DB schema; may trigger clarification"| D[Get Unique Nouns]
    D -->|"Query DB for distinct values matching key terms"| E[Generate SQL]
    E -->|"LLM generates SQL using schema, unique nouns, context"| F[Validate & Fix SQL]
    F -->|"LLM reviews SQL for correctness"| G[Execute SQL]
    G -->|"Run SQL; retry on failure up to max_retries"| H{Parallel}
    H --> I[Format Results]
    H --> J[Visualization + Chart Data]
    I --> K["Follow-up Questions (optional)"]
    K --> L[Final Result]
    style A fill:#2F5496,color:#fff
    style B fill:#4CAF50,color:#fff
    style C fill:#0288D1,color:#fff
    style D fill:#4CAF50,color:#fff
    style E fill:#0288D1,color:#fff
    style F fill:#0288D1,color:#fff
    style G fill:#4CAF50,color:#fff
    style H fill:#00897B,color:#fff
    style I fill:#0288D1,color:#fff
    style J fill:#0288D1,color:#fff
    style K fill:#0288D1,color:#fff
    style L fill:#7B1FA2,color:#fff
```

### Conditional Routing

Several steps include conditional edges:

- **Parse Question** — If the question is not relevant to the database or needs clarification, the workflow exits early
- **Execute SQL** — On failure, routes back to **Generate SQL** for retry (up to `max_retries`)
- **Post-execution** — Format Results and Visualization run in parallel via a dispatcher node

### SQL Retry Loop

When SQL execution fails:

1. The error is captured in `execution_error`
2. `retry_count` is incremented
3. If `retry_count < max_retries`, the workflow routes back to `generate_sql` with the error context
4. The LLM uses the error message to generate corrected SQL
5. If retries are exhausted, the workflow proceeds with the error

## Workflow Steps

### Step Details

| Step | Config Key | Default | LLM Call | Description |
|---|---|---|---|---|
| PII Detection | `pii_detection` | `false` | No | Scans question for PII/PHI using Presidio |
| Parse Question | `parse_question` | `true` | Yes | Determines relevance, extracts key entities |
| Get Unique Nouns | `get_unique_nouns` | `true` | No | Queries DB for distinct values to ground the SQL |
| Generate SQL | `generate_sql` | `true` | Yes | Generates SQL from natural language |
| Validate & Fix | `validate_and_fix_sql` | `true` | Yes | Reviews and corrects SQL errors |
| Execute SQL | `execute_sql` | `true` | No | Executes SQL against the database |
| Format Results | `format_results` | `true` | Yes | Creates human-readable answer from results |
| Visualization | `choose_and_format_visualization` | `true` | Yes | Selects chart type and formats chart data |
| Follow-up Qs | `generate_followup_questions` | `false` | Yes | Suggests follow-up questions |

### Disabling Steps

Disable steps for faster execution or specialized use cases:

```yaml
workflow:
  steps:
    get_unique_nouns: false         # Skip if DB is too large for noun extraction
    format_results: false           # Skip if you only need raw SQL + results
    choose_and_format_visualization: false  # Skip if no charting needed
```

## Initialization Options

Control startup behavior for different deployment scenarios:

```python
# Full initialization (default) — tests everything at startup
workflow = SQLAgentWorkflow(config)

# Fast startup — skip connection tests
workflow = SQLAgentWorkflow(
    config,
    test_llm_connection=False,
    test_db_connection=False,
    init_schema_cache=False,
)

# With progress tracking
from askrita.sqlagent.progress_tracker import create_simple_progress_callback

workflow = SQLAgentWorkflow(
    config,
    progress_callback=create_simple_progress_callback(),
)
```

| Parameter | Default | Description |
|---|---|---|
| `config_manager` | `None` | `ConfigManager` instance (uses global config if `None`) |
| `test_llm_connection` | `True` | Test LLM API connectivity at startup |
| `test_db_connection` | `True` | Test database connectivity at startup |
| `init_schema_cache` | `True` | Preload schema into cache at startup |
| `progress_callback` | `None` | Callback for step-by-step progress notifications |

## Troubleshooting

### Connection Errors at Startup

**Symptom**: `DatabaseError` or `LLMError` during initialization.

- Check your connection string and credentials
- Verify network access to the database and LLM API
- For corporate proxies, set `ca_bundle_path` in the `llm` config
- Use `test_llm_connection=False` / `test_db_connection=False` to skip tests and debug separately

### SQL Generation Failures

**Symptom**: Empty or incorrect SQL, `execution_error` in result.

- Check that your prompts include all required template variables
- Increase `max_retries` for complex queries
- Enable `validate_and_fix_sql` to catch and fix common errors
- Use `--verbose` in CLI or set `framework.debug: true` for detailed logs

### Query Returns No Results

**Symptom**: `results` is empty but no error.

- Check that the SQL is correct: `print(result.sql_query)`
- Verify the data exists in the database
- Check `max_results` — your query may return more rows than the limit

### Clarification Instead of Answer

**Symptom**: `result.needs_clarification` is `True`.

The LLM determined the question is ambiguous. Check `result.clarification_questions` for what information is needed, then ask a more specific question.

### Schema Too Large

**Symptom**: Token limit errors or slow responses.

- Use `framework.results_limit_for_llm` to limit rows sent to the LLM
- Use [Schema Enrichment](schema-enrichment.md) to focus on relevant tables
- Enable schema caching to avoid repeated introspection

### Workflow Diagram Not Rendering

**Symptom**: `save_workflow_diagram()` fails.

- Install graphviz: `pip install graphviz` and ensure the `dot` command is on your PATH
- On macOS: `brew install graphviz`
- On Ubuntu: `apt-get install graphviz`

---

**See also:**

- [Configuration Guide](../configuration/overview.md) — Complete YAML configuration reference
- [Conversational SQL](conversational-sql.md) — Multi-turn chat mode
- [Security](security.md) — SQL safety, prompt injection, PII detection
- [Schema Enrichment](schema-enrichment.md) — Schema descriptions, caching, cross-project access
- [Exports](exports.md) — PPTX, PDF, Excel export
- [Chain of Thoughts](chain-of-thoughts.md) — Observability and progress tracking
- [CLI Reference](cli-reference.md) — Command-line interface
- [Supported Platforms](../supported-platforms.md) — Database and LLM provider details
