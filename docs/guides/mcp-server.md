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
# Ask RITA MCP (Model Context Protocol) Server Guide

This guide explains how to use Ask RITA as a simple MCP server that wraps existing CLI commands for AI assistants and other MCP clients.

## Overview

The Ask RITA MCP server is a **lightweight wrapper** around the existing CLI commands. It provides these tools:

1. **askrita_query** - Execute natural language SQL queries (calls `askrita query`)
2. **askrita_test** - Test configuration and connections (calls `askrita test`)

**Key Benefits:**
- ✅ **Simple**: Just wraps existing CLI commands  
- ✅ **Reliable**: Uses proven CLI functionality
- ✅ **Lightweight**: No business logic duplication
- ✅ **Easy to maintain**: Changes to CLI automatically benefit MCP

## Installation

### 1. Install MCP Dependencies

```bash
# Install AskRITA with MCP support
pip install "mcp>=1.0.0"

# Or install in development mode
pip install -e .
```

### 2. Verify Installation

```bash
# Check that MCP server command is available
askrita mcp --help
```

## Configuration

Create a configuration file for your MCP server. See `example-configs/mcp-server-config.yaml` for a complete example.

### Basic Configuration

```yaml
# Minimal MCP server configuration
llm:
  provider: "openai"
  # API key is read from OPENAI_API_KEY environment variable
  # Set it with: export OPENAI_API_KEY="your-api-key-here"
  model: "gpt-4o"

database:
  type: "bigquery"  # or postgresql, mysql, sqlite
  connection_string: "bigquery://project/dataset"

framework:
  name: "askrita"
  version: "0.1.4"
  
logging:
  level: "INFO"
```

## Starting the MCP Server

### Method 1: Through Main CLI

```bash
# Start MCP server
askrita mcp --config config.yaml

# With verbose logging  
askrita mcp --config config.yaml --verbose
```

### Method 2: Programmatic

```python
from askrita.mcp_server import serve
import asyncio

# Run MCP server programmatically
asyncio.run(serve())
```

## Available MCP Tools

### 1. askrita_query

Execute natural language SQL queries by calling `askrita query` CLI command.

**Input Schema:**
```json
{
  "question": "What are the top 10 products by sales?",
  "config_path": "/path/to/config.yaml",  // optional
  "format": "json"  // optional: json, yaml, text
}
```

**Example Response:**
```json
{
  "success": true,
  "output": "{\n  \"answer\": \"The top 10 products are...\",\n  \"sql_query\": \"SELECT...\"\n}",
  "command": "python -m askrita.cli query 'What are the top 10 products?' --format json"
}
```

### 2. askrita_test

Test configuration and connections by calling `askrita test` CLI command.

**Input Schema:**
```json
{
  "config_path": "/path/to/config.yaml"  // optional
}
```

**Example Response:**
```json
{
  "success": true,
  "output": "✅ Database connection successful\n✅ LLM connection successful\n🎯 Configuration test completed!",
  "command": "python -m askrita.cli test --config config.yaml"
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Configuration file not found: config.yaml",
  "command": "python -m askrita.cli test --config config.yaml",
  "return_code": 1
}
```

## Using with AI Assistants

### Claude Desktop

Add to your Claude Desktop MCP configuration:

```json
{
  "mcpServers": {
    "askrita": {
      "command": "askrita",
      "args": ["mcp", "--config", "/path/to/mcp-server-config.yaml"]
    }
  }
}
```

### Other MCP Clients

The Ask RITA MCP server follows the standard MCP protocol and should work with any MCP-compatible client.

## Security Considerations

1. **API Keys**: Store sensitive credentials in environment variables or secure config files
2. **Database Access**: Use read-only database accounts (see [Configuration Reference](../configuration/security.md#2-read-only-database-accounts-recommended))
3. **Query Safety**: Ask RITA applies static query analysis to block write operations; configure via `workflow.sql_safety`
4. **Query Limits**: Configure appropriate limits in business rules

## Troubleshooting

### Common Issues

1. **MCP Dependencies Missing**
   ```bash
   pip install "mcp>=1.0.0"
   ```

2. **Configuration Errors**
   ```bash
   askrita test --config your-config.yaml
   ```

3. **Database Connection Issues**
   - Verify connection string format
   - Check database credentials and permissions
   - Test with simple SQL query

4. **LLM Connection Issues**
   - Verify API keys are set correctly
   - Check network connectivity
   - Verify LLM provider configuration

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
askrita mcp --config config.yaml --log-level DEBUG
```

## Examples

### SQL Query via MCP

```python
# Example of calling askrita_query tool via MCP client
tool_result = mcp_client.call_tool(
    "askrita_query",
    {
        "question": "How many customers do we have by region?",
        "config_path": "config.yaml",
        "format": "json"
    }
)
```

### Configuration Testing via MCP

```python
# Example of calling askrita_test tool via MCP client
tool_result = mcp_client.call_tool(
    "askrita_test", 
    {
        "config_path": "config.yaml"
    }
)
```

## Integration Examples

### Workflow Automation

Use Ask RITA MCP tools in automated workflows to:

- Generate SQL reports on demand
- Validate database configurations
- Monitor database schemas and connections
- Automate natural language queries

### AI Assistant Integration

Integrate with AI assistants to provide:

- Natural language database querying
- SQL query generation and execution  
- Database connectivity testing
- Configuration validation

## Advanced Configuration

### Multiple Database Support

```yaml
database:
  type: "postgresql"
  connection_string: "postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}/db"
  
# Additional configurations for different environments
# can be specified and selected via config_path parameter
```

### Business Rules Configuration

```yaml
business_rules:
  max_results: 1000
  query_timeout: 30
  enable_caching: true
  allowed_operations: ["SELECT", "SHOW", "DESCRIBE"]
```

### LLM Provider Options

```yaml
llm:
  provider: "azure"  # or openai, vertex, bedrock
  model: "gpt-4o"
  temperature: 0.1
  max_tokens: 4000
  api_version: "2025-04-01-preview"  # for Azure
```

This MCP integration makes Ask RITA's SQL querying capabilities available to any MCP-compatible AI assistant or automation system, providing powerful natural language database access through a standardized protocol.