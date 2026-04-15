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
# Usage Examples and API Reference

Complete code examples for every Ask RITA workflow, plus the full API reference.

## SQL Agent Workflow

```python
from askrita import SQLAgentWorkflow, ConfigManager

# Load configuration (LLM + database + prompts required)
config = ConfigManager("my-config.yaml")
workflow = SQLAgentWorkflow(config)

# Query your database in natural language
result = workflow.query("What are the top 10 customers by revenue?")

# Access results
print(f"Answer: {result.answer}")
print(f"Suggested Chart: {result.visualization}")
if result.chart_data:
    print(f"Universal Chart Data: {result.chart_data}")
```

## NoSQL Agent Workflow

```python
from askrita import NoSQLAgentWorkflow, ConfigManager

# Load MongoDB configuration
config = ConfigManager("example-configs/query-mongodb.yaml")
workflow = NoSQLAgentWorkflow(config)

# Query MongoDB in natural language
result = workflow.query("What are the top 5 products by total sales?")

# Access results (same structure as SQL workflow)
print(f"Answer: {result.answer}")
print(f"Query: {result.sql_query}")           # Contains db.collection.aggregate([...])
print(f"Visualization: {result.visualization}")
if result.chart_data:
    print(f"Chart Data: {result.chart_data}")

# Conversational queries work too
messages = [
    {"role": "user", "content": "How many orders per month in 2025?"}
]
result = workflow.chat(messages)
print(result.answer)
```

> See [NoSQL Workflow Guide](guides/nosql-workflow.md) for complete API reference, configuration, and troubleshooting.

## Conversational SQL Queries

```python
from askrita import SQLAgentWorkflow, ConfigManager

config = ConfigManager("my-config.yaml")
workflow = SQLAgentWorkflow(config)

# Start a conversation with OpenAI-style messages
messages = [
    {"role": "user", "content": "What are the top 5 products by sales?"}
]

result = workflow.chat(messages)
print(f"Answer: {result.answer}")

# Follow up with context-aware questions
messages.extend([
    {"role": "assistant", "content": result.answer},
    {"role": "user", "content": "Show me the monthly trends for these products"}
])

result = workflow.chat(messages)
print(f"Follow-up Answer: {result.answer}")
```

## Data Classification Workflow

```python
from askrita import DataClassificationWorkflow, ConfigManager

# Load classification config
config = ConfigManager("example-configs/data-classification-openai.yaml")
workflow = DataClassificationWorkflow(config)

# Classify single text
result = workflow.classify_text("Customer service was terrible!")
print(f"Category: {result['issue_category']}")

# Or process entire Excel/CSV files
workflow.run_workflow()
```

## Export to PPTX, PDF, and Excel

```python
from askrita import SQLAgentWorkflow, ConfigManager, ExportSettings

config = ConfigManager("my-config.yaml")
workflow = SQLAgentWorkflow(config)

# Get query results
result = workflow.query("Show me sales by region with NPS scores")

# Customize export branding (optional)
export_settings = ExportSettings(
    brand_primary_color=(25, 118, 210),
    brand_secondary_color=(66, 66, 66),
    company_name="My Company"
)

# Export to PowerPoint
pptx_bytes = workflow.export_to_pptx(result, export_settings)
with open("report.pptx", "wb") as f:
    f.write(pptx_bytes)

# Export to PDF
pdf_bytes = workflow.export_to_pdf(result, export_settings)
with open("report.pdf", "wb") as f:
    f.write(pdf_bytes)

# Export to Excel (with native multi-axis charts!)
excel_bytes = workflow.export_to_excel(result, export_settings)
with open("report.xlsx", "wb") as f:
    f.write(excel_bytes)
```

**Export Features:**
- Native Multi-Axis Charts — Excel exports include native dual-axis charts (bar + line combinations)
- Customizable Branding — Configure company name and brand colors
- Complete Data — Includes answer, SQL query, data table, chart, and follow-up questions
- Bytes Output — Returns bytes for maximum flexibility (save to file, cloud storage, or API response)
- Optional Dependencies — Install with `pip install askrita[exports]` for full export support

**Installation for Exports:**
```bash
# Install with export dependencies
pip install askrita[exports]

# Or install manually
pip install python-pptx reportlab matplotlib xlsxwriter
```

## Command Line Interface

```bash
# Set environment variables first (for OpenAI)
export OPENAI_API_KEY="your-api-key-here"

# Test your configuration
askrita test --config my-config.yaml

# Interactive session  
askrita interactive --config my-config.yaml

# Direct query
askrita query "Top 10 customers" --config my-config.yaml
```

Configuration file and appropriate environment variables are always required.

---

## API Reference

### Core Classes

```python
from askrita import SQLAgentWorkflow, NoSQLAgentWorkflow, DataClassificationWorkflow, ConfigManager
import os

# Set environment variables first (if using OpenAI)
os.environ["OPENAI_API_KEY"] = "your-api-key-here"

# Always required: config file with LLM, database, prompts  
config = ConfigManager("my-config.yaml")

# SQL workflow (PostgreSQL, MySQL, BigQuery, Snowflake, etc.)
sql_workflow = SQLAgentWorkflow(config)

# NoSQL workflow (MongoDB)
nosql_config = ConfigManager("mongodb-config.yaml")
nosql_workflow = NoSQLAgentWorkflow(nosql_config)

# Data classification workflow
data_workflow = DataClassificationWorkflow(config)

# Or use convenience factory functions
from askrita import create_sql_agent, create_nosql_agent
sql_workflow = create_sql_agent("my-config.yaml")
nosql_workflow = create_nosql_agent("mongodb-config.yaml")
```

### Main Methods

| Method | Description | Input | Output |
|--------|-------------|-------|---------|
| `workflow.query(question)` | SQL or NoSQL workflow | Natural language string | `WorkflowState` (Pydantic model) |
| `workflow.chat(messages)` | SQL or NoSQL workflow (conversational) | OpenAI-style messages list | `WorkflowState` (Pydantic model) |
| `workflow.classify_text(text)` | Classification workflow | Text string | `dict` |
| `workflow.save_workflow_diagram(path)` | Generate diagram | File path | Saves PNG/DOT file |

### Result Format

```python
# query() and chat() return a WorkflowState Pydantic model
result = workflow.query("Your question")

result.question              # Original question
result.sql_query             # Generated SQL
result.sql_reason            # Explanation of SQL approach
result.results               # Raw data (list)
result.answer                # Human-readable answer
result.visualization         # Chart type recommendation
result.visualization_reason  # Explanation of chart choice
result.chart_data            # UniversalChartData Pydantic model

# Convert to dict when needed (e.g., for JSON APIs)
result_dict = result.model_dump()
```
