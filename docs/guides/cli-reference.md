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
# CLI Reference

Ask RITA provides a command-line interface for running queries, testing configurations, starting interactive sessions, and launching the MCP server.

## Table of Contents

- [Installation](#installation)
- [Commands Overview](#commands-overview)
- [Common Flags](#common-flags)
- [askrita query](#askrita-query)
- [askrita interactive](#askrita-interactive)
- [askrita test](#askrita-test)
- [askrita mcp](#askrita-mcp)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

## Installation

The `askrita` command is installed automatically with the package:

```bash
pip install askrita
```

Verify the installation:

```bash
askrita --help
```

## Commands Overview

| Command | Description |
|---|---|
| `askrita query` | Run a single natural-language query and print the result |
| `askrita interactive` | Start an interactive REPL session |
| `askrita test` | Test your configuration, database, and LLM connections |
| `askrita mcp` | Start the Model Context Protocol (MCP) server |

## Common Flags

These flags are available on all subcommands:

| Flag | Short | Description |
|---|---|---|
| `--config PATH` | `-c PATH` | Path to YAML configuration file |
| `--verbose` | `-v` | Enable debug logging (sets root logger to DEBUG) |

The config path is validated:

- Must end with `.yaml` or `.yml`
- Must not contain `..` (path traversal)
- File must exist

## askrita query

Run a single natural-language question against your database and print the result.

```
askrita query [OPTIONS] QUESTION
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `QUESTION` | Yes | The natural-language question (positional) |

### Options

| Flag | Default | Description |
|---|---|---|
| `--config PATH` | — | Path to YAML config file |
| `--format FORMAT` | From config | Output format: `json`, `yaml`, or `text` |
| `--verbose` | — | Enable debug logging |

### Output Formats

**json** (default) — Full `WorkflowState` as JSON:

```bash
askrita query -c config.yaml "How many orders last month?" --format json
```

**yaml** — Full `WorkflowState` as YAML:

```bash
askrita query -c config.yaml "How many orders last month?" --format yaml
```

**text** — Human-readable summary (answer, visualization, SQL, chart data):

```bash
askrita query -c config.yaml "How many orders last month?" --format text
```

### Behavior

1. Loads and validates the configuration
2. Tests database and LLM connections
3. Runs `SQLAgentWorkflow.query(question)`
4. Prints the result in the specified format

## askrita interactive

Start an interactive REPL session for running multiple queries.

```
askrita interactive [OPTIONS]
```

### Options

| Flag | Default | Description |
|---|---|---|
| `--config PATH` | — | Path to YAML config file |
| `--verbose` | — | Enable debug logging |

### Behavior

1. Loads and validates the configuration
2. Tests database and LLM connections
3. Enters a loop that prompts for questions via `input()`
4. Each question is run through `SQLAgentWorkflow.query()`
5. Results are printed as text (answer and visualization)

### Exit Commands

Type any of these to exit the session:

- `exit`
- `quit`
- `q`

### Example Session

```
$ askrita interactive -c config.yaml

AskRITA Interactive Mode
Type your questions (exit/quit/q to stop)
========================

Ask a question: How many customers do we have?

Answer: There are 1,247 customers in the database.

Ask a question: What is the average order value?

Answer: The average order value is $85.32.

Ask a question: quit
Goodbye!
```

Note: The interactive mode uses `query()` per question, not `chat()`. Each question is processed independently without conversation history. For multi-turn conversations with context, use the Python API with `workflow.chat(messages)`.

## askrita test

Test your configuration, database connection, and LLM connection.

```
askrita test [OPTIONS]
```

### Options

| Flag | Default | Description |
|---|---|---|
| `--config PATH` | — | Path to YAML config file |
| `--verbose` | — | Enable debug logging |

### Behavior

1. Loads and validates the configuration
2. Prints a summary of database, LLM, and workflow settings
3. Tests the database connection
4. Tests the LLM connection
5. Reports success or failure for each test

### Example Output

```
$ askrita test -c config.yaml

Configuration Summary:
  Database: postgresql://localhost:5432/mydb
  LLM Provider: openai
  LLM Model: gpt-4o

Testing database connection... ✓ Connected
Testing LLM connection... ✓ Connected

All tests passed!
```

## askrita mcp

Start the Model Context Protocol (MCP) server for integration with AI assistants like Claude Desktop.

```
askrita mcp [OPTIONS]
```

### Options

| Flag | Default | Description |
|---|---|---|
| `--config PATH` | — | Path to YAML config file |
| `--log-level LEVEL` | `INFO` | Log level for the MCP server |
| `--verbose` | — | Enable debug logging |

### Behavior

1. Loads the configuration
2. Starts the MCP server (communicates over stdio)
3. Exposes `askrita_query` and `askrita_test` as MCP tools

### Available MCP Tools

| Tool | Description |
|---|---|
| `askrita_query` | Run a natural-language query against the configured database |
| `askrita_test` | Test the configuration and connections |

### Integration

The MCP server is designed to be launched by AI assistants. See the [MCP Server Guide](mcp-server.md) and [Claude Desktop Setup](claude-desktop-setup.md) for configuration details.

## Examples

### Quick Query

```bash
askrita query -c config.yaml "What are the top 5 products by revenue?"
```

### Query with JSON Output

```bash
askrita query -c config.yaml --format json "Total sales by month" | jq '.answer'
```

### Verbose Debugging

```bash
askrita query -c config.yaml -v "Why are sales declining?"
```

### Test Before Running

```bash
# Verify everything is connected
askrita test -c config.yaml

# Then run your query
askrita query -c config.yaml "Show me the dashboard data"
```

### Multiple Configs

```bash
# Production database
askrita query -c configs/production.yaml "How many active users?"

# Staging database
askrita query -c configs/staging.yaml "How many active users?"
```

## Troubleshooting

### Command Not Found

**Symptom**: `askrita: command not found`

- Ensure the package is installed: `pip install askrita`
- If using a virtual environment, make sure it is activated
- Check that the virtual environment's bin directory is in your `PATH`

### Config Validation Errors

**Symptom**: `Error: Invalid configuration file path`

- The config path must end with `.yaml` or `.yml`
- The file must exist at the specified path
- Path traversal (`..`) is not allowed for security

### Connection Test Failures

**Symptom**: `askrita test` reports connection failures.

- **Database**: Check connection string, credentials, and network access
- **LLM**: Check API key environment variables and network/proxy settings
- Use `--verbose` to see detailed error messages

### Interactive Mode Hangs

**Symptom**: No prompt appears in interactive mode.

- The workflow tests DB and LLM connections at startup — this may take a few seconds
- Use `--verbose` to see what step is blocking
- Test connections first with `askrita test`

---

**See also:**

- [Configuration Guide](../configuration/overview.md) — Complete YAML configuration reference
- [MCP Server Guide](mcp-server.md) — Detailed MCP server setup
- [Claude Desktop Setup](claude-desktop-setup.md) — Using Ask RITA with Claude Desktop
