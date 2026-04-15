---
template: home.html
title: Ask RITA
hide:
  - navigation
  - toc
---
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

## Four Powerful Workflows

<div class="grid cards" markdown>

-   :material-database-search:{ .lg .middle } **SQL Agent**

    ---

    Natural language to SQL across 7+ database engines with conversational follow-ups, error recovery, and smart visualization.

    [:octicons-arrow-right-24: SQL Workflow Guide](guides/sql-workflow.md)

-   :material-leaf:{ .lg .middle } **NoSQL Agent**

    ---

    Natural language to MongoDB aggregation pipelines with full feature parity — PII detection, charts, and Chain-of-Thoughts.

    [:octicons-arrow-right-24: MongoDB Guide](guides/nosql-workflow.md)

-   :material-flask:{ .lg .middle } **Research Agent**

    ---

    CRISP-DM data science workflows with scipy-powered hypothesis testing, effect sizes, and actionable insights.

    [:octicons-arrow-right-24: Research Guide](guides/research-workflow.md)

-   :material-tag-text:{ .lg .middle } **Data Classification**

    ---

    LLM-powered processing of Excel, CSV, and images with runtime configuration, multi-tenant support, and batch processing.

    [:octicons-arrow-right-24: Classification Guide](guides/data-classification.md)

</div>

## Key Features

<div class="grid cards" markdown>

-   :material-shield-check:{ .lg .middle } **Security & PII Detection**

    ---

    SQL safety validation, prompt injection detection, and Microsoft Presidio-powered PII/PHI scanning for HIPAA and GDPR compliance.

    [:octicons-arrow-right-24: Security Guide](guides/security.md)

-   :material-table-cog:{ .lg .middle } **Schema Enrichment**

    ---

    Automatic schema caching, hybrid descriptions, business glossary terms, and cross-project access for BigQuery.

    [:octicons-arrow-right-24: Schema Enrichment](guides/schema-enrichment.md)

-   :material-file-export:{ .lg .middle } **Export to PPTX, PDF, Excel**

    ---

    One-call export of query results into branded PowerPoint decks, PDF reports, and Excel spreadsheets.

    [:octicons-arrow-right-24: Export Guide](guides/exports.md)

-   :material-chart-bar:{ .lg .middle } **13 Chart Types**

    ---

    Automatic visualization recommendations with Google Charts integration. Bar, line, pie, scatter, treemap, Sankey, and more.

    [:octicons-arrow-right-24: Charts Overview](charts/README.md)

-   :material-thought-bubble:{ .lg .middle } **Chain of Thoughts**

    ---

    Step-by-step reasoning traces, progress callbacks, and full observability into every stage of the analytics pipeline.

    [:octicons-arrow-right-24: CoT Guide](guides/chain-of-thoughts.md)

-   :material-console:{ .lg .middle } **CLI & MCP Server**

    ---

    `askrita` CLI for interactive queries, batch testing, and an MCP server for integration with Claude Desktop and other AI tools.

    [:octicons-arrow-right-24: CLI Reference](guides/cli-reference.md)

</div>

## Supported Platforms

<div class="grid cards" markdown>

-   :material-cloud:{ .lg .middle } **LLM Providers**

    ---

    OpenAI · Azure OpenAI · Google Vertex AI · AWS Bedrock

    [:octicons-arrow-right-24: Provider Details](supported-platforms.md#multi-cloud-llm-support)

-   :material-database:{ .lg .middle } **Databases**

    ---

    PostgreSQL · MySQL · SQLite · SQL Server · BigQuery · Snowflake · IBM DB2 · MongoDB

    [:octicons-arrow-right-24: Connection Strings](supported-platforms.md#connection-string-examples)

</div>

## Quick Start

<!-- termynal -->

```
$ pip install askrita
---> 100%
Successfully installed askrita-0.13.9
$ export OPENAI_API_KEY="your-key"
$ askrita query "What are the top 10 customers by revenue?" --config my-config.yaml
Question: What are the top 10 customers by revenue?
Answer: The top 10 customers by revenue are: 1. Acme Corp ($42.3M),
2. Globex Inc ($38.7M), 3. Initech ($35.1M), 4. Umbrella Co ($31.9M),
5. Wonka Industries ($28.4M), 6. Stark Enterprises ($25.6M),
7. Wayne Corp ($22.8M), 8. Pied Piper ($19.3M), 9. Hooli ($16.7M),
10. Dunder Mifflin ($14.2M).
Recommended Visualization: bar_chart
Reason: Bar chart is ideal for comparing revenue across customers
```

Or use the Python API directly:

```python
from askrita import SQLAgentWorkflow, ConfigManager

config = ConfigManager("my-config.yaml")
workflow = SQLAgentWorkflow(config)
result = workflow.query("What are the top 10 customers by revenue?")
print(result["answer"])
```

## Explore the Docs

<div class="grid cards" markdown>

-   :material-download:{ .lg .middle } **Getting Started**

    ---

    Installation, configuration, usage examples, and supported platforms.

    [:octicons-arrow-right-24: Installation](installation.md)

-   :material-cog:{ .lg .middle } **Configuration**

    ---

    YAML config for LLM providers, databases, workflows, PII detection, and security.

    [:octicons-arrow-right-24: Configuration](configuration/overview.md)

-   :material-book-open-variant:{ .lg .middle } **Guides**

    ---

    In-depth walkthroughs for every workflow, feature, and integration.

    [:octicons-arrow-right-24: SQL Workflow](guides/sql-workflow.md)

-   :material-speedometer:{ .lg .middle } **Benchmarks**

    ---

    BIRD Mini-Dev accuracy results across 6 models — Gemini, GPT-5.4, and more.

    [:octicons-arrow-right-24: Results Overview](benchmarks/results.md)

-   :material-chart-areaspline:{ .lg .middle } **Charts**

    ---

    13 chart types with React and Angular integration guides and sample previews.

    [:octicons-arrow-right-24: Chart Overview](charts/README.md)

-   :material-code-braces:{ .lg .middle } **Developer**

    ---

    Contributing guide, branching workflow, and Docker-based compatibility testing.

    [:octicons-arrow-right-24: Contributing](developer/contributing.md)

</div>
