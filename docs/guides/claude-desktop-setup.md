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
# Claude Desktop MCP Setup for Ask RITA

This guide shows how to add Ask RITA as an MCP server to Claude Desktop.

## Quick Setup

Add this to your Claude Desktop MCP configuration:

```json
{
  "mcpServers": {
    "askrita": {
      "command": "askrita",
      "args": [
        "mcp",
        "--config",
        "/path/to/your/askrita-config.yaml"
      ]
    }
  }
}
```

## Complete Example

1. **Create your config file** at `/path/to/askrita-config.yaml`:
```yaml
llm:
  provider: "openai"
  model: "gpt-4o"
  # API key is read from OPENAI_API_KEY environment variable
  # Set it with: export OPENAI_API_KEY="your-api-key-here"

database:
  type: "bigquery"
  connection_string: "bigquery://your-project/your-dataset"
```

2. **Add to Claude Desktop config**:
```json
{
  "mcpServers": {
    "askrita": {
      "command": "askrita", 
      "args": [
        "mcp",
        "--config",
        "/Users/yourname/askrita-config.yaml"
      ]
    }
  }
}
```

3. **Restart Claude Desktop**

## Available Tools

Once configured, Claude can use these tools:

- **askrita_query**: Ask natural language questions about your database
- **askrita_test**: Test your Ask RITA configuration

## Example Usage in Claude

After setup, you can ask Claude:

> "Use the askrita_query tool to find the top 10 customers by revenue"

Claude will call:
```json
{
  "tool": "askrita_query",
  "arguments": {
    "question": "What are the top 10 customers by revenue?",
    "format": "json"
  }
}
```

## Troubleshooting

If the MCP server doesn't start:

1. **Check the command path**:
   ```bash
   # Test if askrita command is available
   askrita --help
   
   # Test MCP subcommand
   askrita mcp --help
   ```

2. **Test the config**:
   ```bash
   askrita test --config /path/to/your/config.yaml
   ```

3. **Check Claude Desktop logs** for MCP connection errors

## Configuration File Location

On macOS, Claude Desktop's config is usually at:
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

That's it! Simple as adding a JSON config entry.