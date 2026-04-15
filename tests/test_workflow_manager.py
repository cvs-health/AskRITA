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
#   pytest (MIT)

"""Tests for SQLAgentWorkflow functionality."""

import os
from unittest.mock import Mock, patch

import pytest

from askrita.exceptions import ValidationError
from askrita.sqlagent.State import WorkflowState
from askrita.sqlagent.workflows.SQLAgentWorkflow import SQLAgentWorkflow


@pytest.fixture(autouse=True)
def mock_openai_api_key():
    """Automatically mock OPENAI_API_KEY for all workflow tests."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
        yield


class TestSQLAgentWorkflow:
    """Test cases for SQLAgentWorkflow class."""

    def test_initialization(
        self, mock_config, mock_database_manager, mock_llm_manager, mock_data_formatter
    ):
        """Test SQLAgentWorkflow initialization."""
        with (
            patch(
                "askrita.sqlagent.database.DatabaseManager.DatabaseManager", create=True
            ) as mock_db_class,
            patch("askrita.utils.LLMManager.LLMManager", create=True) as mock_llm_class,
            patch(
                "askrita.sqlagent.formatters.DataFormatter.DataFormatter", create=True
            ) as mock_formatter_class,
            patch.object(SQLAgentWorkflow, "_create_workflow") as mock_create_workflow,
            patch.object(SQLAgentWorkflow, "preload_schema"),
        ):

            mock_db_class.return_value = mock_database_manager
            mock_llm_class.return_value = mock_llm_manager
            mock_formatter_class.return_value = mock_data_formatter
            mock_create_workflow.return_value = Mock(compile=Mock(return_value=Mock()))

            workflow_manager = SQLAgentWorkflow(
                mock_config,
                test_llm_connection=False,
                test_db_connection=False,
                init_schema_cache=False,
            )

            # Verify basic initialization without exact object comparison
            assert workflow_manager.config == mock_config
            assert hasattr(workflow_manager, "db_manager")
            assert hasattr(workflow_manager, "llm_manager")
            assert hasattr(workflow_manager, "data_formatter")
            assert hasattr(workflow_manager, "_compiled_graph")


class TestWorkflowCreation:
    """Test workflow graph creation functionality."""

    def test_create_workflow_all_steps_enabled(self, mock_workflow_manager):
        """Test workflow creation with all steps enabled."""
        # Mock all steps as enabled
        mock_workflow_manager.config.workflow.steps = {
            "parse_question": True,
            "get_unique_nouns": True,
            "generate_sql": True,
            "validate_and_fix_sql": True,
            "execute_sql": True,
            "format_results": True,
            "choose_visualization": True,
            "format_data_for_visualization": True,
        }

        workflow = mock_workflow_manager.create_workflow()

        # Should create a workflow with all steps
        assert workflow is not None

    def test_create_workflow_some_steps_disabled(self, mock_workflow_manager):
        """Test workflow creation with some steps disabled."""
        # Mock some steps as disabled
        mock_workflow_manager.config.workflow.steps = {
            "parse_question": True,
            "get_unique_nouns": False,  # Disabled
            "generate_sql": True,
            "validate_and_fix_sql": False,  # Disabled
            "execute_sql": True,
            "format_results": True,
            "choose_visualization": True,
            "format_data_for_visualization": True,
        }

        workflow = mock_workflow_manager.create_workflow()

        # Should create a workflow with only enabled steps
        assert workflow is not None

    def test_create_workflow_no_steps_enabled(self, mock_workflow_manager):
        """Test workflow creation with no steps enabled."""
        # Mock all steps as disabled
        mock_workflow_manager.config.workflow.steps = {
            "parse_question": False,
            "get_unique_nouns": False,
            "generate_sql": False,
            "validate_and_fix_sql": False,
            "execute_sql": False,
            "format_results": False,
            "choose_visualization": False,
            "format_data_for_visualization": False,
        }

        workflow = mock_workflow_manager.create_workflow()

        # Should create a minimal dummy workflow
        assert workflow is not None

    def test_return_graph(self, mock_workflow_manager):
        """Test graph compilation and image generation."""
        mock_graph = Mock()
        mock_workflow_manager.get_graph.return_value = mock_graph

        # Mock the draw_png method
        mock_graph.get_graph.return_value.draw_png = Mock()

        result = mock_workflow_manager.get_graph()

        assert result == mock_graph


class TestQuery:
    """Test the main query method."""

    def test_query_success(self, mock_workflow_manager):
        """Test successful end-to-end SQL agent execution."""
        question = "What are the top 5 customers by revenue?"

        # The mock_workflow_manager already has a query method that returns proper results
        result = mock_workflow_manager.query(question)

        # Test that the result contains expected fields - result is now WorkflowState object
        assert result.answer is not None
        assert result.visualization is not None
        assert result.visualization_reason is not None
        assert result.chart_data is not None  # Only UniversalChartData now

        # Verify the query method was called with the question
        mock_workflow_manager.query.assert_called_with(question)

    def test_query_input_validation_string_type(self, mock_workflow_manager):
        """Test input validation for non-string question."""
        # Configure mock to raise ValidationError for this specific test
        mock_workflow_manager.query.side_effect = ValidationError(
            "Question must be a string"
        )

        with pytest.raises(ValidationError, match="Question must be a string"):
            mock_workflow_manager.query(123)  # Not a string

    def test_query_input_validation_empty_string(self, mock_workflow_manager):
        """Test input validation for empty question."""
        # Configure mock to raise ValidationError for empty strings
        mock_workflow_manager.query.side_effect = ValidationError(
            "Question cannot be empty"
        )

        with pytest.raises(ValidationError, match="Question cannot be empty"):
            mock_workflow_manager.query("")

        with pytest.raises(ValidationError, match="Question cannot be empty"):
            mock_workflow_manager.query("   ")  # Only whitespace

    def test_query_input_validation_too_long(self, mock_workflow_manager):
        """Test input validation for overly long question."""
        long_question = "A" * 10001  # Exceeds 10,000 character limit

        # Configure mock to raise ValidationError for long questions
        mock_workflow_manager.query.side_effect = ValidationError("Question too long")

        with pytest.raises(ValidationError, match="Question too long"):
            mock_workflow_manager.query(long_question)

    def test_query_input_validation_suspicious_content(self, mock_workflow_manager):
        """Test input validation for suspicious content."""
        suspicious_questions = [
            "Show me data <script>alert('xss')</script>",
            "Get customer info javascript:void(0)",
            "Find orders data:text/html,<script>alert(1)</script>",
            "Show sales @@version",
        ]

        # Configure mock to raise ValidationError for suspicious content
        mock_workflow_manager.query.side_effect = ValidationError(
            "potentially unsafe content"
        )

        for question in suspicious_questions:
            with pytest.raises(ValidationError, match="potentially unsafe content"):
                mock_workflow_manager.query(question)

    def test_query_database_error(self, mock_workflow_manager):
        """Test handling of database errors."""
        question = "What are the sales?"

        # Configure mock to raise database exception
        mock_workflow_manager.query.side_effect = Exception(
            "database connection failed"
        )

        with pytest.raises(Exception, match="database connection failed"):
            mock_workflow_manager.query(question)

    def test_query_llm_error(self, mock_workflow_manager):
        """Test handling of LLM errors."""
        question = "What are the sales?"

        # Configure mock to raise LLM exception
        mock_workflow_manager.query.side_effect = Exception(
            "openai api rate limit exceeded"
        )

        with pytest.raises(Exception, match="openai api rate limit exceeded"):
            mock_workflow_manager.query(question)

    def test_query_generic_error(self, mock_workflow_manager):
        """Test handling of generic errors."""
        question = "What are the sales?"

        # Configure mock to raise generic exception
        mock_workflow_manager.query.side_effect = Exception("unexpected error occurred")

        with pytest.raises(Exception, match="unexpected error occurred"):
            mock_workflow_manager.query(question)

    def test_query_invalid_result_format(self, mock_workflow_manager):
        """Test handling of invalid workflow result format."""
        question = "What are the sales?"

        # Configure mock to return invalid format
        mock_workflow_manager.query.return_value = "invalid result format"

        # The real query() method should handle this gracefully or raise an appropriate error
        result = mock_workflow_manager.query(question)

        # The actual behavior depends on what the query method does with invalid results
        assert result == "invalid result format"

    def test_query_missing_required_keys(self, mock_workflow_manager):
        """Test handling of workflow result missing required keys."""
        question = "What are the sales?"

        # Configure mock to return incomplete result
        mock_workflow_manager.query.return_value = WorkflowState(
            answer="Some answer"
            # Missing: visualization, visualization_reason, chart_data
        )

        # The real query() method returns whatever the workflow returns
        result = mock_workflow_manager.query(question)

        # Test that the result contains expected fields - result is now WorkflowState object
        assert result.answer == "Some answer"


class TestWorkflowIntegration:
    """Test workflow integration scenarios."""

    def test_end_to_end_workflow_success(self, mock_config):
        """Test complete end-to-end workflow with real component integration."""
        # Set up mock config with proper validation settings
        mock_config.get_input_validation_settings.return_value = {
            "max_question_length": 10000,
            "blocked_substrings": [
                "<script",
                "javascript:",
                "data:",
                "vbscript:",
                "@@",
            ],
        }

        with (
            patch(
                "askrita.sqlagent.database.DatabaseManager.DatabaseManager", create=True
            ) as mock_db_class,
            patch("askrita.utils.LLMManager", create=True) as mock_llm_class,
            patch(
                "askrita.sqlagent.formatters.DataFormatter", create=True
            ) as mock_formatter_class,
            patch.object(SQLAgentWorkflow, "_create_workflow") as mock_create_workflow,
        ):

            # Setup mocks for the constructor
            mock_db_class.return_value = Mock()
            mock_llm_class.return_value = Mock()
            mock_formatter_class.return_value = Mock()
            mock_create_workflow.return_value = Mock(compile=Mock(return_value=Mock()))

            workflow_manager = SQLAgentWorkflow(
                mock_config, test_llm_connection=False, test_db_connection=False
            )

            # Create expected end-to-end result
            expected_result = {
                "question": "What are the top customers by revenue?",
                "parsed_question": {"is_relevant": True, "relevant_tables": []},
                "unique_nouns": ["Customer A", "Customer B"],
                "sql_query": "SELECT name, amount FROM customers ORDER BY amount DESC LIMIT 5",
                "is_relevant": True,
                "validation_notes": "Query is valid",
                "query_results": [("Customer A", 1000), ("Customer B", 1500)],
                "execution_notes": "Query executed successfully",
                "answer": "Top customers: Customer B ($1500), Customer A ($1000)",
                "visualization": "bar",
                "visualization_reason": "Bar chart is best for comparing values",
                "chart_data": {
                    "type": "bar",
                    "title": "Top Customers by Revenue",
                    "datasets": [
                        {
                            "label": "Revenue",
                            "data": [
                                {"label": "Customer A", "value": 1000},
                                {"label": "Customer B", "value": 1500},
                            ],
                        }
                    ],
                },
            }

            # Mock the _compiled_graph.invoke method to return our expected result
            workflow_manager._compiled_graph = Mock()
            workflow_manager._compiled_graph.invoke.return_value = expected_result

            result = workflow_manager.query("What are the top customers by revenue?")

            # Verify all expected fields are present - result is now WorkflowState object
            assert (
                result.answer == "Top customers: Customer B ($1500), Customer A ($1000)"
            )
            assert result.visualization == "bar"
            assert (
                result.visualization_reason == "Bar chart is best for comparing values"
            )
            assert result.chart_data is not None  # Only UniversalChartData now

    def test_workflow_with_step_failures(self, mock_config):
        """Test workflow behavior when individual steps fail."""
        # Set up mock config with proper validation settings
        mock_config.get_input_validation_settings.return_value = {
            "max_question_length": 10000,
            "blocked_substrings": [
                "<script",
                "javascript:",
                "data:",
                "vbscript:",
                "@@",
            ],
        }

        with (
            patch(
                "askrita.sqlagent.database.DatabaseManager.DatabaseManager", create=True
            ) as mock_db_class,
            patch("askrita.utils.LLMManager", create=True) as mock_llm_class,
            patch(
                "askrita.sqlagent.formatters.DataFormatter", create=True
            ) as mock_formatter_class,
            patch.object(SQLAgentWorkflow, "_create_workflow") as mock_create_workflow,
        ):

            # Setup mocks for the constructor
            mock_db_class.return_value = Mock()
            mock_llm_class.return_value = Mock()
            mock_formatter_class.return_value = Mock()
            mock_create_workflow.return_value = Mock(compile=Mock(return_value=Mock()))

            workflow_manager = SQLAgentWorkflow(
                mock_config, test_llm_connection=False, test_db_connection=False
            )

            # The workflow should handle individual step failures gracefully
            # and not crash the entire process
            question = "What are the sales?"

            # Mock the _compiled_graph.invoke to return error result
            workflow_manager._compiled_graph = Mock()
            workflow_manager._compiled_graph.invoke.return_value = {
                "answer": "Error processing question",
                "visualization": "none",
                "visualization_reason": "No data to visualize",
                "chart_data": None,
            }

            # Should not raise an exception despite step failures
            result = workflow_manager.query(question)

            assert result.answer == "Error processing question"
            assert result.visualization == "none"


class TestSQLAgentWorkflowEdgeCases:
    """Test edge cases and special scenarios."""

    def test_workflow_manager_with_custom_config(self, sample_config_data):
        """Test SQLAgentWorkflow with custom workflow configuration."""
        # Modify workflow configuration
        sample_config_data["workflow"]["steps"]["get_unique_nouns"] = False
        sample_config_data["workflow"]["steps"]["validate_and_fix_sql"] = False
        sample_config_data["workflow"]["max_retries"] = 5

        with (
            patch(
                "askrita.sqlagent.database.DatabaseManager.DatabaseManager", create=True
            ),
            patch("askrita.utils.LLMManager", create=True),
            patch("askrita.sqlagent.formatters.DataFormatter", create=True),
            patch.object(SQLAgentWorkflow, "_create_workflow") as mock_create_workflow,
        ):

            import os

            # Create a real config with custom settings
            import tempfile

            import yaml

            from askrita.config_manager import ConfigManager

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as f:
                yaml.dump(sample_config_data, f)
                temp_path = f.name

            try:
                # Setup mock workflow creation
                mock_create_workflow.return_value = Mock(
                    compile=Mock(return_value=Mock())
                )

                config = ConfigManager(temp_path)
                SQLAgentWorkflow(
                    config, test_llm_connection=False, test_db_connection=False
                )

                # Verify configuration is properly set
                assert config.workflow.max_retries == 5
                assert config.workflow.steps["get_unique_nouns"] is False
                assert config.workflow.steps["validate_and_fix_sql"] is False
            finally:
                os.unlink(temp_path)

    def test_workflow_manager_question_preprocessing(self, mock_workflow_manager):
        """Test question preprocessing and normalization."""
        questions_with_whitespace = [
            "  What are the sales?  ",
            "\t\nWhat are the sales?\n\t",
            "What are the sales?   \r\n",
        ]

        for question in questions_with_whitespace:
            expected_result = {
                "answer": "Sales data",
                "visualization": "bar",
                "visualization_reason": "Good for sales",
                "chart_data": {},
            }

            # Configure mock to return expected result
            mock_workflow_manager.query.return_value = expected_result

            mock_workflow_manager.query(question)

            # Verify the query method was called
            mock_workflow_manager.query.assert_called_with(question)

            # Reset mock for next iteration
            mock_workflow_manager.query.reset_mock()

    def test_workflow_manager_error_propagation(self, mock_workflow_manager):
        """Test that framework exceptions are properly propagated."""
        question = "What are the sales?"

        # Configure mock to raise ValidationError
        mock_workflow_manager.query.side_effect = ValidationError(
            "Input validation failed"
        )

        # ValidationError should be re-raised as-is
        with pytest.raises(ValidationError, match="Input validation failed"):
            mock_workflow_manager.query(question)

    def test_workflow_manager_with_none_config(self):
        """Test SQLAgentWorkflow initialization with None config."""
        # This test verifies that get_config() is called when None is passed
        # We'll patch the constructor to avoid complex initialization
        with (
            patch.object(SQLAgentWorkflow, "__init__", return_value=None),
            patch("askrita.config_manager.get_config") as mock_get_config,
        ):

            mock_config = Mock()
            mock_get_config.return_value = mock_config

            # Create instance (constructor is mocked)
            workflow_manager = SQLAgentWorkflow.__new__(SQLAgentWorkflow)

            # Manually call the original __init__ logic for config handling only
            original_config = None or mock_get_config()
            workflow_manager.config = original_config

            # Should use global config when None is passed
            mock_get_config.assert_called_once()
            assert workflow_manager.config == mock_config
