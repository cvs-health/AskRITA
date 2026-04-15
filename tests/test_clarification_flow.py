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

"""
Tests for user clarification flow in workflow nodes.

This module tests the clarification system that prompts users for additional
information when the workflow cannot proceed reliably.
"""

import pytest
from unittest.mock import Mock, patch
from askrita.sqlagent.workflows.SQLAgentWorkflow import SQLAgentWorkflow, ParseQuestionResponse, TableInfo
from askrita.sqlagent.State import WorkflowState
from askrita.config_manager import ConfigManager
from askrita.models.chain_of_thoughts import ClarificationQuestion


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    config = Mock(spec=ConfigManager)
    config.chain_of_thoughts = Mock()
    config.chain_of_thoughts.enabled = True
    config.workflow = Mock()
    config.workflow.steps = {
        "parse_question": True,
        "get_unique_nouns": True,
        "generate_sql": True,
        "validate_and_fix_sql": True,
        "execute_sql": True,
        "format_results": True,
        "choose_visualization": True,
        "generate_followup_questions": True
    }
    config.llm = Mock()
    config.llm.model = "gpt-4"
    config.llm.provider = "openai"
    config.database = Mock()
    config.database.cache_schema = False
    config.is_step_enabled = Mock(return_value=True)
    config.get_parse_overrides = Mock(return_value=[])  # No parse overrides by default
    return config


@pytest.fixture
def workflow(mock_config):
    """Create a workflow instance for testing."""
    with patch('askrita.sqlagent.workflows.SQLAgentWorkflow.DatabaseManager'), \
         patch('askrita.sqlagent.workflows.SQLAgentWorkflow.LLMManager'), \
         patch('askrita.sqlagent.workflows.SQLAgentWorkflow.DataFormatter'):
        workflow = SQLAgentWorkflow(mock_config)
        workflow._compiled_graph = Mock()
        return workflow


class TestParseQuestionClarification:
    """Test clarification triggers in parse_question node."""

    def test_clarification_when_not_relevant(self, workflow):
        """Test that clarification is requested when question is not relevant."""
        # Use actual Pydantic model for LLM response
        mock_response = ParseQuestionResponse(
            is_relevant=False,
            relevant_tables=[]
        )

        workflow.llm_manager = Mock()
        workflow.llm_manager.invoke_with_structured_output = Mock(return_value=mock_response)
        workflow._get_cached_schema = Mock(return_value="CREATE TABLE test (id INT);")
        workflow._track_step = Mock(return_value=None)
        workflow._complete_step = Mock()

        state = WorkflowState(question="What is the weather today?")
        result = workflow.parse_question(state)

        # Verify clarification is requested
        assert result.get('needs_clarification') is True
        assert result.get('clarification_prompt') is not None
        assert 'relevant database tables' in result.get('clarification_prompt', '')
        assert isinstance(result.get('clarification_questions'), list)
        assert len(result.get('clarification_questions', [])) > 0

    def test_clarification_when_no_tables_found(self, workflow):
        """Test that clarification is requested when no tables are identified."""
        # Use actual Pydantic model with relevance but no tables
        mock_response = ParseQuestionResponse(
            is_relevant=True,
            relevant_tables=[]
        )

        workflow.llm_manager = Mock()
        workflow.llm_manager.invoke_with_structured_output = Mock(return_value=mock_response)
        workflow._get_cached_schema = Mock(return_value="CREATE TABLE test (id INT);")
        workflow._track_step = Mock(return_value=None)
        workflow._complete_step = Mock()

        state = WorkflowState(question="Show me the data")
        result = workflow.parse_question(state)

        # Verify clarification is requested
        assert result.get('needs_clarification') is True
        assert result.get('clarification_prompt') is not None
        assert 'specific tables' in result.get('clarification_prompt', '')
        assert isinstance(result.get('clarification_questions'), list)

    def test_no_clarification_when_successful(self, workflow):
        """Test that no clarification is requested when parsing succeeds."""
        # Use actual Pydantic model for successful parsing
        mock_table = TableInfo(
            table_name="customers",
            noun_columns=[],
            relevant_columns=[]
        )
        mock_response = ParseQuestionResponse(
            is_relevant=True,
            relevant_tables=[mock_table]
        )

        workflow.llm_manager = Mock()
        workflow.llm_manager.invoke_with_structured_output = Mock(return_value=mock_response)
        workflow._get_cached_schema = Mock(return_value="CREATE TABLE test (id INT);")
        workflow._track_step = Mock(return_value=None)
        workflow._complete_step = Mock()

        state = WorkflowState(question="Show me all customers")
        result = workflow.parse_question(state)

        # Verify no clarification is requested
        assert result.get('needs_clarification', False) is False


class TestGenerateSQLClarification:
    """Test clarification triggers in generate_sql node."""

    def test_clarification_after_multiple_retries(self, workflow):
        """Test that clarification is requested after multiple SQL generation failures."""
        workflow._track_step = Mock(return_value=None)
        workflow._complete_step = Mock()
        workflow.llm_manager = Mock()
        workflow.llm_manager.invoke_with_structured_output = Mock(side_effect=Exception("SQL generation failed"))
        workflow._get_cached_schema = Mock(return_value="CREATE TABLE test (id INT);")
        workflow._validate_sql_safety = Mock()

        state = WorkflowState(
            question="Show me data",
            parsed_question={"is_relevant": True, "relevant_tables": []},
            unique_nouns=[],
            retry_count=2  # Multiple retries
        )

        result = workflow.generate_sql(state)

        # Verify clarification is requested after retries
        assert result.get('needs_clarification') is True
        assert result.get('clarification_prompt') is not None
        assert 'trouble generating' in result.get('clarification_prompt', '')
        assert isinstance(result.get('clarification_questions'), list)

    def test_no_clarification_on_first_failure(self, workflow):
        """Test that clarification is NOT requested on first SQL generation failure."""
        workflow._track_step = Mock(return_value=None)
        workflow._complete_step = Mock()
        workflow.llm_manager = Mock()
        workflow.llm_manager.invoke_with_structured_output = Mock(side_effect=Exception("SQL generation failed"))
        workflow._get_cached_schema = Mock(return_value="CREATE TABLE test (id INT);")
        workflow._validate_sql_safety = Mock()

        state = WorkflowState(
            question="Show me data",
            parsed_question={"is_relevant": True, "relevant_tables": []},
            unique_nouns=[],
            retry_count=0  # First attempt
        )

        result = workflow.generate_sql(state)

        # Verify no clarification on first failure
        assert result.get('needs_clarification', False) is False


class TestExecuteSQLClarification:
    """Test clarification triggers in execute_sql node."""

    def test_clarification_on_column_not_found_error(self, workflow):
        """Test that clarification is requested when column doesn't exist."""
        workflow._track_step = Mock(return_value=None)
        workflow._complete_step = Mock()
        workflow.db_manager = Mock()
        workflow.db_manager.execute_query = Mock(side_effect=Exception("Column 'invalid_col' not found"))

        state = WorkflowState(
            question="Show me data",
            sql_query="SELECT invalid_col FROM test"
        )

        result = workflow.execute_sql(state)

        # Verify clarification is requested
        assert result.get('needs_clarification') is True
        assert result.get('clarification_prompt') is not None
        assert "columns or fields don't exist" in result.get('clarification_prompt', '')
        assert isinstance(result.get('clarification_questions'), list)

    def test_clarification_on_syntax_error(self, workflow):
        """Test that clarification is requested on SQL syntax error."""
        workflow._track_step = Mock(return_value=None)
        workflow._complete_step = Mock()
        workflow.db_manager = Mock()
        workflow.db_manager.execute_query = Mock(side_effect=Exception("Syntax error near 'FROM'"))

        state = WorkflowState(
            question="Show me data",
            sql_query="SELECT * FROM"
        )

        result = workflow.execute_sql(state)

        # Verify clarification is requested
        assert result.get('needs_clarification') is True
        assert result.get('clarification_prompt') is not None
        assert 'syntax error' in result.get('clarification_prompt', '')

    def test_clarification_on_permission_error(self, workflow):
        """Test that clarification is requested on permission/access error."""
        workflow._track_step = Mock(return_value=None)
        workflow._complete_step = Mock()
        workflow.db_manager = Mock()
        workflow.db_manager.execute_query = Mock(side_effect=Exception("Access denied to table"))

        state = WorkflowState(
            question="Show me data",
            sql_query="SELECT * FROM restricted_table"
        )

        result = workflow.execute_sql(state)

        # Verify clarification is requested
        assert result.get('needs_clarification') is True
        assert result.get('clarification_prompt') is not None
        assert 'permission' in result.get('clarification_prompt', '').lower()

    def test_no_clarification_on_other_errors(self, workflow):
        """Test that clarification is NOT requested for generic errors."""
        workflow._track_step = Mock(return_value=None)
        workflow._complete_step = Mock()
        workflow.db_manager = Mock()
        workflow.db_manager.execute_query = Mock(side_effect=Exception("Network timeout"))

        state = WorkflowState(
            question="Show me data",
            sql_query="SELECT * FROM test"
        )

        result = workflow.execute_sql(state)

        # Verify no clarification for generic errors
        assert result.get('needs_clarification', False) is False


class TestClarificationStateIntegration:
    """Test that clarification data properly flows through workflow state."""

    def test_state_fields_exist(self):
        """Test that WorkflowState has clarification fields."""
        state = WorkflowState(
            question="test",
            needs_clarification=True,
            clarification_prompt="Please clarify",
            clarification_questions=["Question 1", "Question 2"]
        )

        assert state.needs_clarification is True
        assert state.clarification_prompt == "Please clarify"
        assert len(state.clarification_questions) == 2

    def test_state_to_output_dict_includes_clarification(self):
        """Test that clarification fields are included in output dict."""
        state = WorkflowState(
            question="test",
            needs_clarification=True,
            clarification_prompt="Please clarify",
            clarification_questions=["Question 1"]
        )

        output = state.to_output_dict()

        assert 'needs_clarification' in output
        assert output['needs_clarification'] is True
        assert 'clarification_prompt' in output
        assert 'clarification_questions' in output
        assert len(output['clarification_questions']) == 1

    def test_clarification_converts_to_pydantic_model(self, workflow):
        """Test that clarification state converts to ClarificationQuestion Pydantic model."""
        state = WorkflowState(
            question="Show me data",
            needs_clarification=True,
            clarification_prompt="Could you specify which data you want to see?",
            clarification_questions=["Which columns?", "Which table?"]
        )

        # Use to_chain_of_thoughts_output to convert
        result = workflow.to_chain_of_thoughts_output(state)

        # Should return ClarificationQuestion model
        assert isinstance(result, ClarificationQuestion)
        assert result.question == "Could you specify which data you want to see?"
        assert len(result.rationale) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
