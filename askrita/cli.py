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
#   PyYAML (MIT)

"""Command-line interface for AskRITA framework."""

import argparse
import json
import logging
import sys

import yaml

from .config_manager import ConfigManager
from .sqlagent.database.DatabaseManager import DatabaseManager
from .sqlagent.workflows.SQLAgentWorkflow import SQLAgentWorkflow
from .utils.LLMManager import LLMManager

class SafeLogFormatter(logging.Formatter):
    """Formatter that sanitizes log messages to prevent log injection (CRLF)."""

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        # Replace newlines and carriage returns to prevent log injection
        return msg.replace("\n", "\\n").replace("\r", "\\r")


# Configure logging securely
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(
    SafeLogFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)
logging.basicConfig(level=logging.INFO, handlers=[_handler])  # NOSONAR
logger = logging.getLogger(__name__)


def _sanitize_config_path(config_path: str) -> str:
    """Validate and sanitize a user-supplied config file path.

    Resolves the path and rejects path-traversal sequences, non-YAML
    extensions, and paths that do not point to an existing file.

    Args:
        config_path: Raw path string from CLI argument

    Returns:
        Resolved absolute path string

    Raises:
        SystemExit: If the path fails validation
    """
    from pathlib import Path

    if ".." in Path(config_path).parts:
        logger.error(
            f"Path traversal ('..') is not allowed in config path: {config_path}"
        )
        sys.exit(1)

    resolved = Path(config_path).resolve()

    if not resolved.is_file():
        logger.error(f"Config file does not exist: {resolved}")
        sys.exit(1)

    if resolved.suffix not in (".yaml", ".yml"):
        logger.error(f"Config file must be a YAML file (.yaml or .yml): {resolved}")
        sys.exit(1)

    return str(resolved)


def setup_config(config_path: str = None) -> ConfigManager:
    """Set up configuration from file and environment."""
    try:
        if config_path:
            config_path = _sanitize_config_path(config_path)

        config = ConfigManager(config_path)

        # Validate configuration
        if not config.validate_config():
            logger.error("Configuration validation failed")
            sys.exit(1)

        # Setup logging from config
        log_config = config._config_data.get("logging", {})
        log_level = getattr(logging, log_config.get("level", "INFO").upper())

        # Reconfigure logging with config settings
        logging.basicConfig(  # NOSONAR
            level=log_level,
            format=log_config.get(
                "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            ),
            force=True,
        )

        config_source = config.config_path or "built-in defaults"
        logger.info(f"Configuration loaded from: {config_source}")
        logger.info(f"Environment: {config.environment}")

        # Only log database info if connection string exists
        if config.database.connection_string:
            db_host = (
                config.database.connection_string.split("@")[1]
                if "@" in config.database.connection_string
                else "configured host"
            )
            logger.info(f"Database: {config.get_database_type()} at {db_host}")
        else:
            logger.warning("No database connection configured")

        logger.info(f"LLM: {config.llm.provider} {config.llm.model}")

        return config

    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        logger.error("Please provide a valid configuration file path using --config")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to setup configuration: {e}")
        sys.exit(1)


def run_interactive(args):
    """Start an interactive AskRITA session."""
    config = setup_config(args.config)

    logger.info("Starting AskRITA interactive session")
    print("🔍 AskRITA Interactive SQL Agent")
    print("Type your questions in natural language. Type 'exit' to quit.\n")

    # Initialize workflow with configuration
    workflow_manager = SQLAgentWorkflow(config)

    # Test connections
    if not workflow_manager.db_manager.test_connection():
        print("❌ Database connection failed. Please check your configuration.")
        sys.exit(1)

    if not workflow_manager.llm_manager.test_connection():
        print("❌ LLM connection failed. Please check your API key and configuration.")
        sys.exit(1)

    print("✅ All connections successful. Ready for questions!\n")

    while True:
        try:
            question = input("💬 Ask a question: ").strip()

            if question.lower() in ["exit", "quit", "q"]:
                print("👋 Goodbye!")
                break

            if not question:
                continue

            print("🤔 Processing your question...")

            # Run the query
            result = workflow_manager.query(question)

            # Display results
            print(f"\n📝 Answer: {getattr(result, 'answer', 'No answer generated')}")

            if result.visualization and result.visualization != "none":
                print(f"📊 Recommended Visualization: {result.visualization}")
                print(
                    f"   Reason: {getattr(result, 'visualization_reason', 'No reason provided')}"
                )

            print("-" * 60 + "\n")

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            print("Please try again or type 'exit' to quit.\n")


def run_query(args):
    """Run a direct query using configuration."""
    config = setup_config(args.config)

    try:
        logger.info(f"Processing query: {args.question}")

        # Initialize workflow with configuration
        workflow_manager = SQLAgentWorkflow(config)

        # Test database connection
        if not workflow_manager.db_manager.test_connection():
            logger.error("Database connection test failed")
            sys.exit(1)

        # Test LLM connection
        if not workflow_manager.llm_manager.test_connection():
            logger.error("LLM connection test failed")
            sys.exit(1)

        # Run the query
        result = workflow_manager.query(args.question)

        # Format output based on configuration or argument
        output_format = getattr(args, "format", None) or config.workflow.output_format

        if output_format == "json":
            # Convert WorkflowState to dict for JSON serialization
            result_dict = (
                result.model_dump(exclude_none=True)
                if hasattr(result, "model_dump")
                else result
            )
            print(json.dumps(result_dict, indent=2))
        elif output_format == "yaml":
            # Convert WorkflowState to dict for YAML serialization
            result_dict = (
                result.model_dump(exclude_none=True)
                if hasattr(result, "model_dump")
                else result
            )
            print(yaml.dump(result_dict, default_flow_style=False))
        else:
            # Text format
            print(f"Question: {args.question}")
            print(f"Answer: {getattr(result, 'answer', 'No answer generated')}")
            if result.visualization:
                print(f"Recommended Visualization: {result.visualization}")
                print(
                    f"Reason: {getattr(result, 'visualization_reason', 'No reason provided')}"
                )

    except KeyboardInterrupt:
        logger.info("Query interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Query failed: {e}")
        sys.exit(1)


def run_config_test(args):
    """Test the configuration and connections."""
    config = setup_config(args.config)

    print("=== AskRITA Configuration Test ===\n")

    # Test configuration loading
    print("✓ Configuration loaded successfully")
    print(f"  Config file: {config.config_path}")
    print(f"  Environment: {config.environment}")

    # Test database configuration
    print("\n📊 Database Configuration:")
    db_info = config.database
    print(f"  Type: {config.get_database_type()}")
    print(
        f"  Connection: {db_info.connection_string.split('@')[1] if '@' in db_info.connection_string else 'configured'}"
    )
    print(f"  Cache enabled: {db_info.cache_schema}")
    print(f"  Query timeout: {db_info.query_timeout}s")
    print(f"  Max results: {db_info.max_results}")

    # Test LLM configuration
    print("\n🤖 LLM Configuration:")
    llm_info = config.llm
    print(f"  Provider: {llm_info.provider}")
    print(f"  Model: {llm_info.model}")
    print(f"  Temperature: {llm_info.temperature}")
    print(f"  Max tokens: {llm_info.max_tokens}")
    import os

    if os.getenv("OPENAI_API_KEY"):
        api_key_status = "Yes"
    elif llm_info.provider == "openai":
        api_key_status = "No"
    else:
        api_key_status = "N/A"
    print(f"  API key configured: {api_key_status}")

    # Test workflow configuration
    print("\n⚙️  Workflow Configuration:")
    workflow_info = config.workflow
    enabled_steps = [step for step, enabled in workflow_info.steps.items() if enabled]
    print(f"  Enabled steps: {', '.join(enabled_steps)}")
    print(f"  Output format: {workflow_info.output_format}")
    print(f"  Max retries: {workflow_info.max_retries}")

    # Test actual connections
    print("\n🔌 Connection Tests:")

    try:
        db_manager = DatabaseManager(config)

        if db_manager.test_connection():
            print("  ✓ Database connection successful")

            # Get table count
            tables = db_manager.get_table_names()
            print(f"  ✓ Found {len(tables)} tables in database")
        else:
            print("  ✗ Database connection failed")

    except Exception as e:
        print(f"  ✗ Database connection error: {e}")

    try:
        llm_manager = LLMManager(config)

        if llm_manager.test_connection():
            print("  ✓ LLM connection successful")
        else:
            print("  ✗ LLM connection failed")

    except Exception as e:
        print(f"  ✗ LLM connection error: {e}")

    print("\n🎯 Configuration test completed!")


def run_mcp_server(args):
    """Run the Model Context Protocol server."""
    try:
        import sys

        from .mcp_server import serve

        # Set up arguments for MCP server
        mcp_args = []
        if args.config:
            mcp_args.extend(["--config", args.config])
        if hasattr(args, "log_level"):
            mcp_args.extend(["--log-level", args.log_level])

        # Replace sys.argv for the MCP server
        original_argv = sys.argv.copy()
        sys.argv = ["askrita-mcp"] + mcp_args

        try:
            logger.info("Starting AskRITA MCP Server...")
            serve()
        finally:
            # Restore original argv
            sys.argv = original_argv

    except ImportError as e:
        logger.error(f"MCP dependencies not available: {e}")
        logger.error("Install MCP support with: pip install mcp>=1.0.0")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to start MCP server: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="AskRITA - Natural Language SQL Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start interactive session with default config
  askrita interactive

  # Start interactive session with custom config
  askrita interactive --config myconfig.yaml

  # Run a direct query
  askrita query "What are the top 10 customers by revenue?"

  # Test configuration
  askrita test --config myconfig.yaml
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Add global arguments to each subcommand
    def add_common_args(parser):
        parser.add_argument("--config", "-c", help="Path to YAML configuration file")
        parser.add_argument(
            "--verbose", "-v", action="store_true", help="Enable verbose logging"
        )

    # Interactive command
    interactive_parser = subparsers.add_parser(
        "interactive", help="Start interactive AskRITA session"
    )
    add_common_args(interactive_parser)

    # Query command for direct CLI usage
    query_parser = subparsers.add_parser("query", help="Run a query directly")
    query_parser.add_argument("question", help="The question to ask")
    query_parser.add_argument(
        "--format",
        choices=["json", "yaml", "text"],
        help="Output format (overrides config)",
    )
    add_common_args(query_parser)

    # Configuration test command
    test_parser = subparsers.add_parser(
        "test", help="Test configuration and connections"
    )
    add_common_args(test_parser)

    # MCP serve command
    mcp_parser = subparsers.add_parser(
        "mcp", help="Start Model Context Protocol (MCP) server"
    )
    mcp_parser.add_argument(
        "--log-level", default="INFO", help="Logging level for MCP server"
    )
    add_common_args(mcp_parser)

    args = parser.parse_args()

    # Set verbose logging if requested
    if hasattr(args, "verbose") and args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.command == "interactive":
        run_interactive(args)
    elif args.command == "query":
        run_query(args)
    elif args.command == "test":
        run_config_test(args)
    elif args.command == "mcp":
        run_mcp_server(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
