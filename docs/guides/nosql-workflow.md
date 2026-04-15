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
# NoSQL (MongoDB) Workflow Guide

Complete guide for using Ask RITA's `NoSQLAgentWorkflow` to query MongoDB databases with natural language.

> **New in v0.12.0** — The NoSQL workflow mirrors the SQL workflow architecture, reusing LLMManager, DataFormatter, LangGraph orchestration, Chain-of-Thoughts, PII detection, and visualization.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [API Reference](#api-reference)
- [How It Works](#how-it-works)
- [Safety & Security](#safety-security)
- [Troubleshooting](#troubleshooting)

## Overview

`NoSQLAgentWorkflow` converts natural language questions into MongoDB aggregation pipelines. It uses the same workflow steps as `SQLAgentWorkflow` but adapted for MongoDB:

| SQL Workflow | NoSQL Workflow | Description |
|---|---|---|
| `DatabaseManager` | `NoSQLDatabaseManager` | Database connection and query execution |
| `SQLDatabase` (langchain) | `MongoDBDatabase` (langchain-mongodb) | Schema inference and query runner |
| SQL queries | `db.collection.aggregate([...])` | Generated query format |
| `DatabaseConnectionStrategy` | `NoSQLConnectionStrategy` | Authentication and connection testing |

**Shared components** (identical in both workflows):
- `WorkflowState` — state model
- `LLMManager` — LLM interactions
- `DataFormatter` — visualization formatting
- LangGraph `StateGraph` — workflow orchestration
- PII detection, Chain-of-Thoughts, progress callbacks

## Quick Start

### 1. Install Dependencies

```bash
pip install askrita
# langchain-mongodb is included automatically
```

### 2. Set Environment Variables

```bash
# LLM provider (example: OpenAI)
export OPENAI_API_KEY="your-api-key-here"
```

### 3. Create Configuration

Create a `mongodb-config.yaml`:

```yaml
database:
  connection_string: "mongodb://${MONGO_USER}:${MONGO_PASSWORD}@localhost:27017/mydb"
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
    generate_sql: true           # Maps to MongoDB query generation
    validate_and_fix_sql: true   # Maps to MongoDB query validation
    execute_sql: true            # Maps to MongoDB query execution
    format_results: true
    choose_and_format_visualization: true
    generate_followup_questions: true

prompts:
  parse_question:
    system: "You are a MongoDB database expert."
    human: |
      Given the following MongoDB database schema:
      {schema}

      Determine if this question is relevant to the database:
      {question}

  generate_sql:
    system: "You are a MongoDB aggregation pipeline expert."
    human: |
      Given the following MongoDB database schema:
      {schema}

      Unique values found in the database:
      {unique_nouns}

      The user's question has been parsed as:
      {parsed_question}

      Generate a MongoDB aggregation pipeline to answer this question:
      {question}

  validate_sql:
    system: "You are a MongoDB query validator."
    human: |
      Given the following MongoDB database schema:
      {schema}

      Validate and fix this MongoDB query if needed:
      {sql_query}

  format_results:
    system: "You are a data analyst."
    human: |
      Question: {question}
      MongoDB Query: {sql_query}
      Results: {query_results}

      Provide a clear, concise answer.

  generate_followup_questions:
    system: "You are a helpful data analyst."
    human: |
      Based on the question: {question}
      Answer: {answer}
      Query: {sql_query}
      Results summary: {results_summary}
      Schema: {schema_context}

      Generate 3 relevant follow-up questions.
```

### 4. Query Your Database

```python
from askrita import NoSQLAgentWorkflow, ConfigManager

config = ConfigManager("mongodb-config.yaml")
workflow = NoSQLAgentWorkflow(config)

result = workflow.query("How many orders were placed last month?")
print(result.answer)
```

## Configuration

### Connection Strings

```yaml
# Local MongoDB
database:
  connection_string: "mongodb://localhost:27017/mydb"

# MongoDB with authentication
database:
  connection_string: "mongodb://${MONGO_USER}:${MONGO_PASSWORD}@host:27017/mydb?authSource=admin"

# MongoDB Atlas (cloud)
database:
  connection_string: "mongodb+srv://${MONGO_USER}:${MONGO_PASSWORD}@cluster.mongodb.net/mydb"

# With environment variables (recommended)
database:
  connection_string: "mongodb://${MONGO_USER}:${MONGO_PASSWORD}@${MONGO_HOST}:27017/${MONGO_DB}"
```

### Environment Variables

```bash
# MongoDB credentials
export MONGO_USER="your-username"
export MONGO_PASSWORD="your-password"
export MONGO_HOST="your-host"
export MONGO_DB="your-database"

# LLM provider
export OPENAI_API_KEY="your-api-key"
```

### Database Settings

```yaml
database:
  connection_string: "mongodb://..."

  # Performance settings
  query_timeout: 30              # Query timeout in seconds
  max_results: 1000              # Maximum documents returned
  cache_schema: true             # Cache collection schema
  schema_refresh_interval: 3600  # Schema cache TTL in seconds
```

### Workflow Step Names

The NoSQL workflow reuses the same step names as the SQL workflow for configuration compatibility. The mapping is:

| Config Step Name | NoSQL Method | What It Does |
|---|---|---|
| `parse_question` | `parse_question()` | Identify relevant collections and fields |
| `get_unique_nouns` | `get_unique_nouns()` | Extract distinct values from collections |
| `generate_sql` | `generate_query()` | Generate MongoDB aggregation pipeline |
| `validate_and_fix_sql` | `validate_and_fix_query()` | Validate and fix the MongoDB query |
| `execute_sql` | `execute_query()` | Execute the MongoDB command |
| `format_results` | `format_results()` | Format results into human-readable answer |
| `choose_and_format_visualization` | `choose_and_format_visualization()` | Choose chart type and format data |
| `generate_followup_questions` | `generate_followup_questions()` | Generate follow-up questions |
| `pii_detection` | `pii_detection_step()` | Scan for PII/PHI (optional) |

## Usage Examples

### Single Query

```python
from askrita import NoSQLAgentWorkflow, ConfigManager

config = ConfigManager("mongodb-config.yaml")
workflow = NoSQLAgentWorkflow(config)

result = workflow.query("What are the top 5 products by total sales?")

print(f"Answer: {result.answer}")
print(f"Query: {result.sql_query}")          # Contains the MongoDB command
print(f"Results: {result.results}")
print(f"Visualization: {result.visualization}")
print(f"Follow-ups: {result.followup_questions}")
```

### Conversational Queries

```python
from askrita import NoSQLAgentWorkflow, ConfigManager

config = ConfigManager("mongodb-config.yaml")
workflow = NoSQLAgentWorkflow(config)

# First question
messages = [
    {"role": "user", "content": "How many orders per month in 2025?"}
]
result = workflow.chat(messages)
print(result.answer)

# Follow-up with context
messages.extend([
    {"role": "assistant", "content": result.answer},
    {"role": "user", "content": "Which month had the highest revenue?"}
])
result = workflow.chat(messages)
print(result.answer)
```

### Convenience Factory Function

```python
from askrita import create_nosql_agent

# One-liner setup
workflow = create_nosql_agent("mongodb-config.yaml")
result = workflow.query("Show me customer distribution by city")
print(result.answer)
```

### With Progress Callbacks

```python
from askrita import NoSQLAgentWorkflow, ConfigManager

def on_progress(progress_data):
    print(f"Step: {progress_data.step_name} — {progress_data.status}")

config = ConfigManager("mongodb-config.yaml")
workflow = NoSQLAgentWorkflow(config, progress_callback=on_progress)

result = workflow.query("Average order value by category")
```

### With Chain-of-Thoughts Tracking

```python
from askrita import NoSQLAgentWorkflow, ConfigManager

config = ConfigManager("mongodb-config.yaml")
workflow = NoSQLAgentWorkflow(config)

# Register a listener for real-time reasoning updates
def cot_listener(event):
    print(f"[CoT] {event['event_type']}: {event.get('step_name', '')}")

workflow.register_cot_listener(cot_listener)

result = workflow.query("What is the average delivery time by region?")
```

### Initialization Options

```python
from askrita import NoSQLAgentWorkflow, ConfigManager

config = ConfigManager("mongodb-config.yaml")

# Full initialization (default)
workflow = NoSQLAgentWorkflow(config)

# Skip connection tests (faster startup, useful for testing)
workflow = NoSQLAgentWorkflow(
    config,
    test_llm_connection=False,
    test_db_connection=False,
    init_schema_cache=False,
)

# With progress tracking
workflow = NoSQLAgentWorkflow(
    config,
    progress_callback=my_callback_function,
)
```

## API Reference

### NoSQLAgentWorkflow

```python
class NoSQLAgentWorkflow:
    def __init__(
        self,
        config_manager=None,           # ConfigManager instance
        test_llm_connection=True,       # Test LLM on init
        test_db_connection=True,        # Test MongoDB on init
        init_schema_cache=True,         # Preload schema
        progress_callback=None,         # Progress callback
    ): ...

    def query(self, question: str) -> WorkflowState: ...
    def chat(self, messages: list) -> WorkflowState: ...
    def preload_schema(self) -> None: ...
    def clear_schema_cache(self) -> None: ...
    def get_graph(self): ...  # Get compiled LangGraph

    # Chain-of-Thoughts listeners
    def register_cot_listener(self, listener): ...
    def unregister_cot_listener(self, listener): ...
    def clear_cot_listeners(self): ...

    @property
    def schema(self) -> str: ...  # Current database schema
```

### WorkflowState (Result Object)

The result returned by `query()` and `chat()` is a `WorkflowState` with these fields:

| Field | Type | Description |
|---|---|---|
| `question` | `str` | Original question |
| `answer` | `str` | Human-readable answer |
| `analysis` | `str` | Detailed analysis |
| `sql_query` | `str` | MongoDB command (e.g. `db.orders.aggregate([...])`) |
| `sql_reason` | `str` | Explanation of query approach |
| `sql_valid` | `bool` | Whether query passed validation |
| `sql_issues` | `str` | Validation issues found |
| `results` | `list` | Raw query results as `List[Dict]` |
| `visualization` | `str` | Recommended chart type |
| `visualization_reason` | `str` | Why this chart was chosen |
| `chart_data` | `dict` | Universal chart data for rendering |
| `followup_questions` | `list` | Suggested follow-up questions |
| `retry_count` | `int` | Number of retry attempts |
| `execution_error` | `str` | Error message if execution failed |

### NoSQLDatabaseManager

```python
class NoSQLDatabaseManager:
    def __init__(self, config_manager=None, test_db_connection=True): ...
    def test_connection(self) -> bool: ...
    def get_schema(self) -> str: ...
    def execute_query(self, command: str) -> List[Dict[str, Any]]: ...
    def get_collection_names(self) -> List[str]: ...
    def get_sample_data(self, limit=100) -> Dict[str, List[Dict]]: ...
    def get_connection_info(self) -> dict: ...
```

### create_nosql_agent

```python
def create_nosql_agent(config_path=None) -> NoSQLAgentWorkflow:
    """
    Factory function for quick setup.

    Args:
        config_path: Path to YAML config file

    Returns:
        Ready-to-use NoSQLAgentWorkflow
    """
```

## How It Works

### Workflow Pipeline

```mermaid
flowchart TD
    A[User Question] --> B["PII Detection (optional)"]
    B -->|"Scan for personal data"| C[Parse Question]
    C -->|"Identify relevant collections & fields"| D[Get Unique Nouns]
    D -->|"Extract distinct values from collections"| E[Generate Query]
    E -->|"LLM creates db.collection.aggregate"| F[Validate Query]
    F -->|"LLM checks and fixes the query"| G[Execute Query]
    G -->|"Run against MongoDB via langchain-mongodb"| H{Parallel}
    H --> I[Format Results]
    H --> J[Visualization + Chart Data]
    I --> K[Follow-up Questions]
    K --> L[Final Result]
    style A fill:#2F5496,color:#fff
    style B fill:#4CAF50,color:#fff
    style C fill:#4CAF50,color:#fff
    style D fill:#4CAF50,color:#fff
    style E fill:#0288D1,color:#fff
    style F fill:#0288D1,color:#fff
    style G fill:#4CAF50,color:#fff
    style H fill:#00897B,color:#fff
    style I fill:#4CAF50,color:#fff
    style J fill:#4CAF50,color:#fff
    style K fill:#0288D1,color:#fff
    style L fill:#7B1FA2,color:#fff
```

### Schema Inference

The `NoSQLDatabaseManager` uses `langchain-mongodb`'s `MongoDBDatabase.get_collection_info()` to infer schema from your MongoDB collections. This includes:

- Collection names
- Field names and types (inferred from document sampling)
- Sample documents
- Index information

The `MongoDBStrategy.enhance_schema()` then prepends database type context and project context to help the LLM understand it's working with MongoDB.

### Query Generation

The LLM generates MongoDB aggregation pipeline commands in the format:

```
db.collectionName.aggregate([
  { $match: { status: "active" } },
  { $group: { _id: "$category", total: { $sum: "$amount" } } },
  { $sort: { total: -1 } },
  { $limit: 10 }
])
```

These commands are executed via `MongoDBDatabase.run()`.

### Result Normalization

MongoDB documents are automatically serialized for JSON compatibility:

| MongoDB Type | Serialized As |
|---|---|
| `ObjectId` | `str` |
| `Decimal128` | `float` |
| `datetime` | ISO 8601 string |
| `Binary` | `"<binary data>"` |
| Nested documents | Recursively serialized |

## Safety & Security

### Blocked Operations

The workflow blocks all destructive MongoDB operations. Only read operations are allowed:

**Allowed**: `aggregate`, `find`, `count`, `distinct`

**Blocked**:
- Write stages: `$out`, `$merge`
- Delete: `deleteOne`, `deleteMany`
- Insert: `insertOne`, `insertMany`
- Update: `updateOne`, `updateMany`, `replaceOne`
- Admin: `drop`, `rename`, `createIndex`, `dropIndex`, `bulkWrite`

### Credential Safety

Connection strings with credentials are masked in logs:

```
# What you configure (credentials via env vars):
mongodb://${MONGO_USER}:${MONGO_PASSWORD}@cluster.mongodb.net/mydb

# What appears in logs:
MongoDB: cluster.mongodb.net/mydb
```

### PII Detection

Enable PII/PHI detection to scan user questions before processing:

```yaml
pii_detection:
  enabled: true
  block_on_detection: true
  confidence_threshold: 0.7

workflow:
  steps:
    pii_detection: true  # Must be enabled in workflow steps too
```

## Troubleshooting

### Connection Issues

**Error**: `MongoDB connection test failed`
- Verify the connection string is correct
- Check that the MongoDB server is running and accessible
- Ensure credentials are valid
- For Atlas: check IP whitelist settings

**Error**: `Could not extract database name from MongoDB connection string`
- Ensure your connection string includes a database name: `mongodb://host:27017/your_database`

### Query Issues

**Error**: `Query contains forbidden operation`
- The generated query contains a write operation. The LLM sometimes generates `$out` or `$merge` stages. The safety validator blocks these automatically. Retry the question with more specific wording.

**Error**: `Error executing MongoDB command`
- Check the MongoDB server logs for details
- Ensure the database user has read permissions on the target collections
- Verify collection names match what's in the database

### Schema Issues

**Empty schema / no collections found**
- Verify the database name in the connection string is correct
- Ensure the database contains collections with documents
- Check that the user has `listCollections` and `find` permissions

### Performance Tips

- **Enable schema caching**: Set `cache_schema: true` and `schema_refresh_interval: 3600`
- **Limit results**: Set `max_results` to a reasonable number (e.g., 1000)
- **Use Atlas indexes**: Ensure your collections have appropriate indexes for common query patterns
- **Preload schema**: The workflow preloads schema by default during initialization

---

**See also:**
- [Configuration Guide](../configuration/overview.md) — Complete YAML configuration reference
- [Home](../index.md) — Project overview and quick start
- [Chart Documentation](../charts/README.md) — Visualization implementation
