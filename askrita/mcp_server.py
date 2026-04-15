# Copyright 2026 CVS Health and/or one of its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This file uses the following unmodified third-party packages,
# each retaining its original copyright and license:
#   mcp (MIT)

"""Model Context Protocol (MCP) server for AskRITA framework.

Simple MCP wrapper that calls existing CLI commands.
"""

import argparse
import asyncio
import json
import logging
import subprocess
import sys
from typing import Any, Dict, Sequence

from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.types import TextContent, Tool

class SafeLogFormatter(logging.Formatter):
    """Formatter that sanitizes log messages to prevent log injection (CRLF)."""

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        return msg.replace("\n", "\\n").replace("\r", "\\r")


# Configure logging securely
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(SafeLogFormatter("%(levelname)s:%(name)s:%(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[_handler])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JSON response key constants (used 3+ times)
# ---------------------------------------------------------------------------
_KEY_SUCCESS = "success"
_KEY_COMMAND = "command"
_KEY_CONFIG_PATH = "config_path"
_KEY_QUESTION = "question"
_ARG_CONFIG = "--config"

# Global server instance
server = Server("askrita")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List all available AskRITA CLI tools."""
    return [
        Tool(
            name="askrita_query",
            description="Execute natural language SQL queries using askrita CLI",
            inputSchema={
                "type": "object",
                "properties": {
                    _KEY_QUESTION: {
                        "type": "string",
                        "description": "Natural language question to convert to SQL and execute",
                    },
                    _KEY_CONFIG_PATH: {
                        "type": "string",
                        "description": "Optional path to configuration file",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["json", "yaml", "text"],
                        "description": "Output format",
                    },
                },
                "required": [_KEY_QUESTION],
            },
        ),
        Tool(
            name="askrita_test",
            description="Test AskRITA configuration and connections",
            inputSchema={
                "type": "object",
                "properties": {
                    _KEY_CONFIG_PATH: {
                        "type": "string",
                        "description": "Optional path to configuration file",
                    }
                },
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: Dict[str, Any]
) -> Sequence[TextContent]:
    """Handle tool execution by calling CLI commands."""
    try:
        if name == "askrita_query":
            return await run_cli_query(arguments)
        elif name == "askrita_test":
            return await run_cli_test(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        error_message = f"Error executing {name}: {str(e)}"
        return [TextContent(type="text", text=error_message)]


async def run_cli_query(arguments: Dict[str, Any]) -> Sequence[TextContent]:
    """Run askrita query command via CLI."""
    question = arguments.get(_KEY_QUESTION)
    config_path = arguments.get(_KEY_CONFIG_PATH)
    format_type = arguments.get("format", "json")

    if not question:
        return [TextContent(type="text", text="Error: Question is required")]

    # Build CLI command
    cmd = [sys.executable, "-m", "askrita.cli", "query", question]

    if config_path:
        cmd.extend([_ARG_CONFIG, config_path])

    cmd.extend(["--format", format_type])

    try:
        # Run the CLI command
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300  # 5 minute timeout
        )

        if result.returncode == 0:
            # Successful execution
            response = {
                _KEY_SUCCESS: True,
                "output": result.stdout.strip(),
                _KEY_COMMAND: " ".join(cmd),
            }
        else:
            # Command failed
            response = {
                _KEY_SUCCESS: False,
                "error": result.stderr.strip() or result.stdout.strip(),
                _KEY_COMMAND: " ".join(cmd),
                "return_code": result.returncode,
            }

        return [TextContent(type="text", text=json.dumps(response, indent=2))]

    except subprocess.TimeoutExpired:
        error_response = {
            _KEY_SUCCESS: False,
            "error": "Command timed out after 5 minutes",
            _KEY_COMMAND: " ".join(cmd),
        }
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
    except Exception as e:
        error_response = {
            _KEY_SUCCESS: False,
            "error": f"Failed to execute command: {str(e)}",
            _KEY_COMMAND: " ".join(cmd),
        }
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]


async def run_cli_test(arguments: Dict[str, Any]) -> Sequence[TextContent]:
    """Run askrita test command via CLI."""
    config_path = arguments.get(_KEY_CONFIG_PATH)

    # Build CLI command
    cmd = [sys.executable, "-m", "askrita.cli", "test"]

    if config_path:
        cmd.extend([_ARG_CONFIG, config_path])

    try:
        # Run the CLI command
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60  # 1 minute timeout
        )

        if result.returncode == 0:
            response = {
                _KEY_SUCCESS: True,
                "output": result.stdout.strip(),
                _KEY_COMMAND: " ".join(cmd),
            }
        else:
            response = {
                _KEY_SUCCESS: False,
                "error": result.stderr.strip() or result.stdout.strip(),
                _KEY_COMMAND: " ".join(cmd),
                "return_code": result.returncode,
            }

        return [TextContent(type="text", text=json.dumps(response, indent=2))]

    except subprocess.TimeoutExpired:
        error_response = {
            _KEY_SUCCESS: False,
            "error": "Command timed out after 1 minute",
            _KEY_COMMAND: " ".join(cmd),
        }
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
    except Exception as e:
        error_response = {
            _KEY_SUCCESS: False,
            "error": f"Failed to execute command: {str(e)}",
            _KEY_COMMAND: " ".join(cmd),
        }
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]


async def main():
    """Main entry point for the MCP server."""
    # Argument parsing
    parser = argparse.ArgumentParser(description="AskRITA MCP Server")
    parser.add_argument(_ARG_CONFIG, help="Configuration file path")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    args = parser.parse_args()

    # Configure logging
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))

    logger.info("Starting AskRITA MCP Server...")

    # Store default config path if provided
    if args.config:
        logger.info(f"Using default config: {args.config}")

    # Run the server
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="askrita",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def serve():
    """Entry point for the askrita-mcp command."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("MCP Server stopped by user")
    except Exception as e:
        logger.error(f"MCP Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    serve()
