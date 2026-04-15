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
#   pytest (MIT)

"""Tests for CLI functionality."""

import pytest
import json
from unittest.mock import Mock, patch
from argparse import Namespace

from askrita.cli import (
    setup_config, run_interactive, run_query, run_config_test, main
)
from askrita.sqlagent.State import WorkflowState


class TestSetupConfig:
    """Test configuration setup functionality."""

    def test_setup_config_success(self, temp_config_file):
        """Test successful configuration setup."""
        from pathlib import Path
        resolved_path = str(Path(temp_config_file).resolve())

        with patch('askrita.cli.ConfigManager') as mock_config_class:
            mock_config = Mock()
            mock_config.validate_config.return_value = True
            mock_config.config_path = resolved_path
            mock_config.environment = "development"
            mock_config.database.connection_string = "sqlite:///test.db"
            mock_config.get_database_type.return_value = "SQLite"
            mock_config.llm.provider = "openai"
            mock_config.llm.model = "gpt-4o"
            mock_config._config_data = {
                "logging": {
                    "level": "INFO",
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                }
            }
            mock_config_class.return_value = mock_config

            result = setup_config(temp_config_file)

            assert result == mock_config
            mock_config_class.assert_called_once_with(resolved_path)
            mock_config.validate_config.assert_called_once()

    def test_setup_config_validation_failure(self, temp_config_file):
        """Test configuration setup with validation failure."""
        with patch('askrita.cli.ConfigManager') as mock_config_class:
            mock_config = Mock()
            mock_config.validate_config.return_value = False
            mock_config_class.return_value = mock_config

            with pytest.raises(SystemExit) as exc_info:
                setup_config(temp_config_file)

            assert exc_info.value.code == 1

    def test_setup_config_file_not_found(self):
        """Test configuration setup with missing file."""
        with pytest.raises(SystemExit) as exc_info:
            setup_config("/nonexistent/config.yaml")

        assert exc_info.value.code == 1

    def test_setup_config_generic_error(self, temp_config_file):
        """Test configuration setup with generic error."""
        with patch('askrita.cli.ConfigManager') as mock_config_class, \
             patch('sys.exit') as mock_exit:

            mock_config_class.side_effect = Exception("Generic error")

            setup_config(temp_config_file)

            mock_exit.assert_called_once_with(1)


class TestRunInteractive:
    """Test interactive mode functionality."""

    def test_run_interactive_success(self, temp_config_file):
        """Test successful interactive session."""
        args = Namespace(config=temp_config_file)

        with patch('askrita.cli.setup_config') as mock_setup_config, \
             patch('askrita.cli.SQLAgentWorkflow') as mock_workflow_class, \
             patch('builtins.input') as mock_input, \
             patch('builtins.print') as mock_print, \
             patch('sys.exit'):

            # Setup mocks
            mock_config = Mock()
            mock_setup_config.return_value = mock_config

            mock_workflow = Mock()
            mock_workflow.db_manager.test_connection.return_value = True
            mock_workflow.llm_manager.test_connection.return_value = True
            mock_workflow.query.return_value = WorkflowState(answer="Top customers: Customer A, Customer B", visualization="bar", visualization_reason="Bar chart is good for comparisons")
            mock_workflow_class.return_value = mock_workflow

            # Simulate user input sequence: question -> exit
            mock_input.side_effect = ["What are the top customers?", "exit"]

            run_interactive(args)

            # Verify workflow was called
            mock_workflow.query.assert_called_once_with("What are the top customers?")

            # Verify appropriate messages were printed
            mock_print.assert_any_call("✅ All connections successful. Ready for questions!\n")
            mock_print.assert_any_call("👋 Goodbye!")

    def test_run_interactive_database_connection_failure(self, temp_config_file):
        """Test interactive mode with database connection failure."""
        args = Namespace(config=temp_config_file)

        with patch('askrita.cli.setup_config') as mock_setup_config, \
             patch('askrita.cli.SQLAgentWorkflow') as mock_workflow_class, \
             patch('builtins.print'):

            mock_config = Mock()
            mock_setup_config.return_value = mock_config

            mock_workflow = Mock()
            mock_workflow.db_manager.test_connection.return_value = False
            mock_workflow_class.return_value = mock_workflow

            with pytest.raises(SystemExit) as exc_info:
                run_interactive(args)

            assert exc_info.value.code == 1

    def test_run_interactive_llm_connection_failure(self, temp_config_file):
        """Test interactive mode with LLM connection failure."""
        args = Namespace(config=temp_config_file)

        with patch('askrita.cli.setup_config') as mock_setup_config, \
             patch('askrita.cli.SQLAgentWorkflow') as mock_workflow_class, \
             patch('builtins.print'):

            mock_config = Mock()
            mock_setup_config.return_value = mock_config

            mock_workflow = Mock()
            mock_workflow.db_manager.test_connection.return_value = True
            mock_workflow.llm_manager.test_connection.return_value = False
            mock_workflow_class.return_value = mock_workflow

            with pytest.raises(SystemExit) as exc_info:
                run_interactive(args)

            assert exc_info.value.code == 1

    def test_run_interactive_empty_input(self, temp_config_file):
        """Test interactive mode with empty input."""
        args = Namespace(config=temp_config_file)

        with patch('askrita.cli.setup_config') as mock_setup_config, \
             patch('askrita.cli.SQLAgentWorkflow') as mock_workflow_class, \
             patch('builtins.input') as mock_input, \
             patch('builtins.print'):

            mock_config = Mock()
            mock_setup_config.return_value = mock_config

            mock_workflow = Mock()
            mock_workflow.db_manager.test_connection.return_value = True
            mock_workflow.llm_manager.test_connection.return_value = True
            mock_workflow_class.return_value = mock_workflow

            # Simulate empty input followed by exit
            mock_input.side_effect = ["", "   ", "exit"]

            run_interactive(args)

            # Should not call run_sql_agent for empty inputs
            mock_workflow.query.assert_not_called()

    def test_run_interactive_keyboard_interrupt(self, temp_config_file):
        """Test interactive mode with keyboard interrupt."""
        args = Namespace(config=temp_config_file)

        with patch('askrita.cli.setup_config') as mock_setup_config, \
             patch('askrita.cli.SQLAgentWorkflow') as mock_workflow_class, \
             patch('builtins.input') as mock_input, \
             patch('builtins.print') as mock_print:

            mock_config = Mock()
            mock_setup_config.return_value = mock_config

            mock_workflow = Mock()
            mock_workflow.db_manager.test_connection.return_value = True
            mock_workflow.llm_manager.test_connection.return_value = True
            mock_workflow_class.return_value = mock_workflow

            # Simulate keyboard interrupt
            mock_input.side_effect = KeyboardInterrupt()

            run_interactive(args)

            mock_print.assert_any_call("\n👋 Goodbye!")

    def test_run_interactive_query_error(self, temp_config_file):
        """Test interactive mode with query processing error."""
        args = Namespace(config=temp_config_file)

        with patch('askrita.cli.setup_config') as mock_setup_config, \
             patch('askrita.cli.SQLAgentWorkflow') as mock_workflow_class, \
             patch('builtins.input') as mock_input, \
             patch('builtins.print') as mock_print:

            mock_config = Mock()
            mock_setup_config.return_value = mock_config

            mock_workflow = Mock()
            mock_workflow.db_manager.test_connection.return_value = True
            mock_workflow.llm_manager.test_connection.return_value = True
            mock_workflow.query.side_effect = Exception("Query failed")
            mock_workflow_class.return_value = mock_workflow

            # Simulate question that causes error, then exit
            mock_input.side_effect = ["What are the sales?", "exit"]

            run_interactive(args)

            # Should print error message
            mock_print.assert_any_call("❌ Error: Query failed")


class TestRunQuery:
    """Test direct query functionality."""

    def test_run_query_success_text_format(self, temp_config_file):
        """Test successful direct query with text format."""
        args = Namespace(
            config=temp_config_file,
            question="What are the top customers?",
            format=None
        )

        with patch('askrita.cli.setup_config') as mock_setup_config, \
             patch('askrita.cli.SQLAgentWorkflow') as mock_workflow_class, \
             patch('builtins.print') as mock_print:

            mock_config = Mock()
            mock_config.workflow.output_format = "text"
            mock_setup_config.return_value = mock_config

            mock_workflow = Mock()
            mock_workflow.db_manager.test_connection.return_value = True
            mock_workflow.llm_manager.test_connection.return_value = True
            mock_workflow.query.return_value = WorkflowState(answer="Top customers: Customer A, Customer B", visualization="bar", visualization_reason="Bar chart is good for comparisons")
            mock_workflow_class.return_value = mock_workflow

            run_query(args)

            # Verify text output
            mock_print.assert_any_call("Question: What are the top customers?")
            mock_print.assert_any_call("Answer: Top customers: Customer A, Customer B")
            mock_print.assert_any_call("Recommended Visualization: bar")

    def test_run_query_success_json_format(self, temp_config_file):
        """Test successful direct query with JSON format."""
        args = Namespace(
            config=temp_config_file,
            question="What are the top customers?",
            format="json"
        )

        with patch('askrita.cli.setup_config') as mock_setup_config, \
             patch('askrita.cli.SQLAgentWorkflow') as mock_workflow_class, \
             patch('builtins.print') as mock_print:

            mock_config = Mock()
            mock_setup_config.return_value = mock_config

            mock_workflow = Mock()
            mock_workflow.db_manager.test_connection.return_value = True
            mock_workflow.llm_manager.test_connection.return_value = True
            mock_workflow.query.return_value = WorkflowState(answer="Top customers: Customer A, Customer B", visualization="bar", visualization_reason="Bar chart is good for comparisons")
            mock_workflow_class.return_value = mock_workflow

            run_query(args)

            # Verify JSON output was printed - check that it contains expected fields
            # (model_dump outputs all non-None fields, so we can't check exact match)
            assert mock_print.called
            json_output = mock_print.call_args[0][0]
            parsed_output = json.loads(json_output)

            # Verify expected fields are present
            assert parsed_output["answer"] == "Top customers: Customer A, Customer B"
            assert parsed_output["visualization"] == "bar"
            assert parsed_output["visualization_reason"] == "Bar chart is good for comparisons"
            assert parsed_output["retry_count"] == 0

    def test_run_query_success_yaml_format(self, temp_config_file):
        """Test successful direct query with YAML format."""
        args = Namespace(
            config=temp_config_file,
            question="What are the top customers?",
            format="yaml"
        )

        with patch('askrita.cli.setup_config') as mock_setup_config, \
             patch('askrita.cli.SQLAgentWorkflow') as mock_workflow_class, \
             patch('builtins.print') as mock_print:

            mock_config = Mock()
            mock_setup_config.return_value = mock_config

            mock_workflow = Mock()
            mock_workflow.db_manager.test_connection.return_value = True
            mock_workflow.llm_manager.test_connection.return_value = True
            mock_workflow.query.return_value = WorkflowState(answer="Top customers: Customer A, Customer B", visualization="bar")
            mock_workflow_class.return_value = mock_workflow

            run_query(args)

            # Should print YAML format
            mock_print.assert_called()

    def test_run_query_database_connection_failure(self, temp_config_file):
        """Test direct query with database connection failure."""
        args = Namespace(
            config=temp_config_file,
            question="What are the sales?",
            format=None
        )

        with patch('askrita.cli.setup_config') as mock_setup_config, \
             patch('askrita.cli.SQLAgentWorkflow') as mock_workflow_class:

            mock_config = Mock()
            mock_setup_config.return_value = mock_config

            mock_workflow = Mock()
            mock_workflow.db_manager.test_connection.return_value = False
            mock_workflow_class.return_value = mock_workflow

            with pytest.raises(SystemExit) as exc_info:
                run_query(args)

            assert exc_info.value.code == 1

    def test_run_query_llm_connection_failure(self, temp_config_file):
        """Test direct query with LLM connection failure."""
        args = Namespace(
            config=temp_config_file,
            question="What are the sales?",
            format=None
        )

        with patch('askrita.cli.setup_config') as mock_setup_config, \
             patch('askrita.cli.SQLAgentWorkflow') as mock_workflow_class:

            mock_config = Mock()
            mock_setup_config.return_value = mock_config

            mock_workflow = Mock()
            mock_workflow.db_manager.test_connection.return_value = True
            mock_workflow.llm_manager.test_connection.return_value = False
            mock_workflow_class.return_value = mock_workflow

            with pytest.raises(SystemExit) as exc_info:
                run_query(args)

            assert exc_info.value.code == 1

    def test_run_query_keyboard_interrupt(self, temp_config_file):
        """Test direct query with keyboard interrupt."""
        args = Namespace(
            config=temp_config_file,
            question="What are the sales?",
            format=None
        )

        with patch('askrita.cli.setup_config') as mock_setup_config, \
             patch('askrita.cli.SQLAgentWorkflow') as mock_workflow_class, \
             patch('sys.exit') as mock_exit:

            mock_config = Mock()
            mock_setup_config.return_value = mock_config

            mock_workflow = Mock()
            mock_workflow.db_manager.test_connection.return_value = True
            mock_workflow.llm_manager.test_connection.return_value = True
            mock_workflow.query.side_effect = KeyboardInterrupt()
            mock_workflow_class.return_value = mock_workflow

            run_query(args)

            mock_exit.assert_called_once_with(0)

    def test_run_query_exception(self, temp_config_file):
        """Test direct query with exception."""
        args = Namespace(
            config=temp_config_file,
            question="What are the sales?",
            format=None
        )

        with patch('askrita.cli.setup_config') as mock_setup_config, \
             patch('askrita.cli.SQLAgentWorkflow') as mock_workflow_class, \
             patch('sys.exit') as mock_exit:

            mock_config = Mock()
            mock_setup_config.return_value = mock_config

            mock_workflow = Mock()
            mock_workflow.db_manager.test_connection.return_value = True
            mock_workflow.llm_manager.test_connection.return_value = True
            mock_workflow.query.side_effect = Exception("Query failed")
            mock_workflow_class.return_value = mock_workflow

            run_query(args)

            mock_exit.assert_called_once_with(1)


class TestRunConfigTest:
    """Test configuration testing functionality."""

    def test_run_config_test_success(self, temp_config_file):
        """Test successful configuration test."""
        args = Namespace(config=temp_config_file)

        with patch('askrita.cli.setup_config') as mock_setup_config, \
             patch('askrita.cli.DatabaseManager') as mock_db_class, \
             patch('askrita.cli.LLMManager') as mock_llm_class, \
             patch('builtins.print') as mock_print:

            mock_config = Mock()
            mock_config.config_path = temp_config_file
            mock_config.environment = "development"
            mock_config.database.connection_string = "sqlite:///test.db"
            mock_config.database.cache_schema = True
            mock_config.database.query_timeout = 30
            mock_config.database.max_results = 1000
            mock_config.llm.provider = "openai"
            mock_config.llm.model = "gpt-4o"
            mock_config.llm.temperature = 0.1
            mock_config.llm.max_tokens = 4000

            mock_config.workflow.steps = {"parse_question": True, "generate_sql": True}
            mock_config.workflow.output_format = "json"
            mock_config.workflow.max_retries = 3
            mock_config.get_database_type.return_value = "SQLite"
            mock_setup_config.return_value = mock_config

            # Setup database manager mock
            mock_db_manager = Mock()
            mock_db_manager.test_connection.return_value = True
            mock_db_manager.get_table_names.return_value = ["customers", "orders", "products"]
            mock_db_class.return_value = mock_db_manager

            # Setup LLM manager mock
            mock_llm_manager = Mock()
            mock_llm_manager.test_connection.return_value = True
            mock_llm_class.return_value = mock_llm_manager

            run_config_test(args)

            # Verify configuration sections were printed
            mock_print.assert_any_call("✓ Configuration loaded successfully")
            mock_print.assert_any_call("  ✓ Database connection successful")
            mock_print.assert_any_call("  ✓ LLM connection successful")
            mock_print.assert_any_call("\n🎯 Configuration test completed!")

    def test_run_config_test_database_failure(self, temp_config_file):
        """Test configuration test with database failure."""
        args = Namespace(config=temp_config_file)

        with patch('askrita.cli.setup_config') as mock_setup_config, \
             patch('askrita.cli.DatabaseManager') as mock_db_class, \
             patch('builtins.print') as mock_print:

            mock_config = Mock()
            mock_config.config_path = temp_config_file
            mock_config.environment = "development"
            mock_config.database.connection_string = "sqlite:///test.db"
            mock_config.database.cache_schema = True
            mock_config.database.query_timeout = 30
            mock_config.database.max_results = 1000
            mock_config.llm.provider = "openai"
            mock_config.llm.model = "gpt-4o"
            mock_config.llm.temperature = 0.1
            mock_config.llm.max_tokens = 4000

            mock_config.workflow.steps = {"parse_question": True}
            mock_config.workflow.output_format = "json"
            mock_config.workflow.max_retries = 3
            mock_config.get_database_type.return_value = "SQLite"
            mock_setup_config.return_value = mock_config

            mock_db_manager = Mock()
            mock_db_manager.test_connection.return_value = False
            mock_db_class.return_value = mock_db_manager

            run_config_test(args)

            mock_print.assert_any_call("  ✗ Database connection failed")

    def test_run_config_test_llm_failure(self, temp_config_file):
        """Test configuration test with LLM failure."""
        args = Namespace(config=temp_config_file)

        with patch('askrita.cli.setup_config') as mock_setup_config, \
             patch('askrita.cli.DatabaseManager') as mock_db_class, \
             patch('askrita.cli.LLMManager') as mock_llm_class, \
             patch('builtins.print') as mock_print:

            mock_config = Mock()
            mock_config.config_path = temp_config_file
            mock_config.environment = "development"
            mock_config.database.connection_string = "sqlite:///test.db"
            mock_config.database.cache_schema = True
            mock_config.database.query_timeout = 30
            mock_config.database.max_results = 1000
            mock_config.llm.provider = "openai"
            mock_config.llm.model = "gpt-4o"
            mock_config.llm.temperature = 0.1
            mock_config.llm.max_tokens = 4000

            mock_config.workflow.steps = {"parse_question": True}
            mock_config.workflow.output_format = "json"
            mock_config.workflow.max_retries = 3
            mock_config.get_database_type.return_value = "SQLite"
            mock_setup_config.return_value = mock_config

            mock_db_manager = Mock()
            mock_db_manager.test_connection.return_value = True
            mock_db_manager.get_table_names.return_value = ["customers"]
            mock_db_class.return_value = mock_db_manager

            mock_llm_manager = Mock()
            mock_llm_manager.test_connection.return_value = False
            mock_llm_class.return_value = mock_llm_manager

            run_config_test(args)

            mock_print.assert_any_call("  ✗ LLM connection failed")


class TestMainFunction:
    """Test main CLI entry point."""

    def test_main_interactive_command(self):
        """Test main function with interactive command."""
        test_args = ['askrita', 'interactive', '--config', 'test.yaml']

        with patch('sys.argv', test_args), \
             patch('askrita.cli.run_interactive') as mock_run_interactive:

            main()

            mock_run_interactive.assert_called_once()

    def test_main_query_command(self):
        """Test main function with query command."""
        test_args = ['askrita', 'query', 'What are the sales?', '--format', 'json']

        with patch('sys.argv', test_args), \
             patch('askrita.cli.run_query') as mock_run_query:

            main()

            mock_run_query.assert_called_once()

    def test_main_test_command(self):
        """Test main function with test command."""
        test_args = ['askrita', 'test', '--config', 'test.yaml']

        with patch('sys.argv', test_args), \
             patch('askrita.cli.run_config_test') as mock_run_config_test:

            main()

            mock_run_config_test.assert_called_once()

    def test_main_no_command(self):
        """Test main function with no command."""
        test_args = ['askrita']

        with patch('sys.argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1

    def test_main_verbose_logging(self):
        """Test main function with verbose logging enabled."""
        test_args = ['askrita', 'test', '--verbose']

        with patch('sys.argv', test_args), \
             patch('askrita.cli.run_config_test'), \
             patch('logging.getLogger') as mock_get_logger:

            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            main()

            mock_logger.setLevel.assert_called_once()


class TestCLIEdgeCases:
    """Test CLI edge cases and error scenarios."""

    def test_setup_config_logging_configuration(self, temp_config_file):
        """Test that logging is properly configured from config."""
        with patch('askrita.cli.ConfigManager') as mock_config_class, \
             patch('logging.basicConfig') as mock_logging_config:

            mock_config = Mock()
            mock_config.validate_config.return_value = True
            mock_config.config_path = temp_config_file
            mock_config.environment = "production"
            mock_config._config_data = {
                "logging": {
                    "level": "DEBUG",
                    "format": "%(levelname)s - %(message)s"
                }
            }
            mock_config.database.connection_string = "postgresql://user:pass@host/db"
            mock_config.get_database_type.return_value = "PostgreSQL"
            mock_config.llm.provider = "azure_openai"
            mock_config.llm.model = "gpt-4"

            mock_config_class.return_value = mock_config

            setup_config(temp_config_file)

            # Should reconfigure logging with config settings
            mock_logging_config.assert_called()

    def test_run_interactive_with_visualization_output(self, temp_config_file):
        """Test interactive mode displaying visualization recommendations."""
        args = Namespace(config=temp_config_file)

        with patch('askrita.cli.setup_config') as mock_setup_config, \
             patch('askrita.cli.SQLAgentWorkflow') as mock_workflow_class, \
             patch('builtins.input') as mock_input, \
             patch('builtins.print') as mock_print:

            mock_config = Mock()
            mock_setup_config.return_value = mock_config

            mock_workflow = Mock()
            mock_workflow.db_manager.test_connection.return_value = True
            mock_workflow.llm_manager.test_connection.return_value = True
            mock_workflow.query.return_value = WorkflowState(answer="Sales data", visualization="line", visualization_reason="Line chart shows trends over time")
            mock_workflow_class.return_value = mock_workflow

            mock_input.side_effect = ["Show sales trends", "exit"]

            run_interactive(args)

            # Should display visualization recommendation
            mock_print.assert_any_call("📊 Recommended Visualization: line")
            mock_print.assert_any_call("   Reason: Line chart shows trends over time")

    def test_config_test_with_missing_api_key(self, temp_config_file):
        """Test configuration test when API key is missing."""
        args = Namespace(config=temp_config_file)

        with patch('askrita.cli.setup_config') as mock_setup_config, \
             patch('builtins.print') as mock_print, \
             patch('os.getenv') as mock_getenv:

            mock_config = Mock()
            mock_config.config_path = temp_config_file
            mock_config.environment = "development"
            mock_config.database.connection_string = "sqlite:///test.db"
            mock_config.database.cache_schema = True
            mock_config.database.query_timeout = 30
            mock_config.database.max_results = 1000
            mock_config.llm.provider = "openai"
            mock_config.llm.model = "gpt-4o"
            mock_config.llm.temperature = 0.1
            mock_config.llm.max_tokens = 4000

            mock_config.workflow.steps = {"parse_question": True}
            mock_config.workflow.output_format = "json"
            mock_config.workflow.max_retries = 3
            mock_config.get_database_type.return_value = "SQLite"
            mock_setup_config.return_value = mock_config

            # Mock missing API key
            mock_getenv.return_value = None

            run_config_test(args)

            # Check that configuration test was run (should print something about configuration)
            mock_print.assert_called()  # Just verify that print was called
            print_calls = [str(call) for call in mock_print.call_args_list]
            # Should have some configuration-related output
            assert any("Configuration" in call or "config" in call.lower() for call in print_calls)

    def test_run_query_with_no_visualization(self, temp_config_file):
        """Test direct query when no visualization is recommended."""
        args = Namespace(
            config=temp_config_file,
            question="What is the count?",
            format=None
        )

        with patch('askrita.cli.setup_config') as mock_setup_config, \
             patch('askrita.cli.SQLAgentWorkflow') as mock_workflow_class, \
             patch('builtins.print') as mock_print:

            mock_config = Mock()
            mock_config.workflow.output_format = "text"
            mock_setup_config.return_value = mock_config

            mock_workflow = Mock()
            mock_workflow.db_manager.test_connection.return_value = True
            mock_workflow.llm_manager.test_connection.return_value = True
            mock_workflow.query.return_value = WorkflowState(answer="Count is 42")
            mock_workflow_class.return_value = mock_workflow

            run_query(args)

            # Should not print visualization info when None
            mock_print.assert_any_call("Answer: Count is 42")
            # Should not print visualization lines
            calls = [call.args for call in mock_print.call_args_list]
            viz_calls = [call for call in calls if any("Recommended Visualization" in str(arg) for arg in call)]
            assert len(viz_calls) == 0
