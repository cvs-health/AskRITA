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
Tests for Chain-of-Thoughts Pydantic models and query_with_cot method.

This module tests the new Pydantic model-based API that returns
ChainOfThoughtsOutput and ClarificationQuestion models.
"""

from unittest.mock import Mock, patch

import pytest

from askrita.config_manager import ConfigManager
from askrita.models.chain_of_thoughts import (
    ChainOfThoughtsOutput,
    ClarificationQuestion,
    ExecutionResult,
    ReasoningSummary,
    SqlCorrection,
    VisualizationSpec,
)
from askrita.sqlagent.State import WorkflowState
from askrita.sqlagent.workflows.SQLAgentWorkflow import SQLAgentWorkflow


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
        "generate_followup_questions": True,
    }
    config.llm = Mock()
    config.llm.model = "gpt-4"
    config.llm.provider = "openai"
    config.database = Mock()
    config.database.cache_schema = False
    config.is_step_enabled = Mock(return_value=True)
    config.get_parse_overrides = Mock(return_value=[])
    config.get_input_validation_settings = Mock(return_value={})
    config.get_database_type = Mock(return_value="bigquery")
    return config


@pytest.fixture
def workflow(mock_config):
    """Create a workflow instance for testing."""
    with (
        patch("askrita.sqlagent.workflows.SQLAgentWorkflow.DatabaseManager"),
        patch("askrita.sqlagent.workflows.SQLAgentWorkflow.LLMManager"),
        patch("askrita.sqlagent.workflows.SQLAgentWorkflow.DataFormatter"),
    ):
        workflow = SQLAgentWorkflow(
            mock_config, test_llm_connection=False, test_db_connection=False
        )
        workflow._compiled_graph = Mock()
        return workflow


class TestChainOfThoughtsOutput:
    """Test ChainOfThoughtsOutput model and query_with_cot method."""

    def test_query_with_cot_returns_chain_of_thoughts_output(self, workflow):
        """Test that query_with_cot returns ChainOfThoughtsOutput on success."""
        # Mock successful workflow execution
        mock_state = WorkflowState(
            question="Show me sales by region",
            sql_query="SELECT region, SUM(sales) FROM sales_table GROUP BY region",
            sql_valid=True,
            results=[
                {"region": "North", "sales": 1000},
                {"region": "South", "sales": 2000},
            ],
            visualization="bar",
            answer="Sales by region: North $1000, South $2000",
            needs_clarification=False,
        )

        workflow.query = Mock(return_value=mock_state)
        workflow._last_callback_handler = Mock()
        workflow._last_callback_handler.get_breadcrumbs = Mock(
            return_value=[
                "Analyzed your question",
                "Generated SQL query",
                "Executed query against database",
            ]
        )

        result = workflow.query_with_cot("Show me sales by region")

        # Assert result is ChainOfThoughtsOutput
        assert isinstance(result, ChainOfThoughtsOutput)
        assert isinstance(result.reasoning, ReasoningSummary)
        assert len(result.reasoning.steps) > 0
        assert (
            result.sql == "SELECT region, SUM(sales) FROM sales_table GROUP BY region"
        )
        assert isinstance(result.result, ExecutionResult)
        assert result.result.row_count == 2
        assert len(result.result.columns) > 0
        assert isinstance(result.viz, VisualizationSpec)
        assert result.viz.kind == "bar"

    def test_query_with_cot_returns_clarification_question(self, workflow):
        """Test that query_with_cot returns ClarificationQuestion when clarification needed."""
        # Mock workflow state requiring clarification
        mock_state = WorkflowState(
            question="Show me data",
            needs_clarification=True,
            clarification_prompt="Could you specify which data you want to see?",
            clarification_questions=["Which columns?", "Which table?"],
        )

        workflow.query = Mock(return_value=mock_state)

        result = workflow.query_with_cot("Show me data")

        # Assert result is ClarificationQuestion
        assert isinstance(result, ClarificationQuestion)
        assert "specify which data" in result.question.lower()
        assert len(result.rationale) > 0

    def test_execution_result_conversion(self, workflow):
        """Test conversion of database results to ExecutionResult."""
        # Test with dict results (most common)
        dict_results = [
            {"region": "North", "sales": 1000},
            {"region": "South", "sales": 2000},
        ]

        exec_result = workflow._convert_results_to_execution_result(dict_results)

        assert isinstance(exec_result, ExecutionResult)
        assert exec_result.row_count == 2
        assert exec_result.columns == ["region", "sales"]
        assert len(exec_result.rows) == 2
        assert exec_result.rows[0] == ["North", 1000]
        assert exec_result.rows[1] == ["South", 2000]

    def test_execution_result_empty(self, workflow):
        """Test ExecutionResult with empty results."""
        exec_result = workflow._convert_results_to_execution_result([])

        assert isinstance(exec_result, ExecutionResult)
        assert exec_result.row_count == 0
        assert exec_result.columns == []
        assert exec_result.rows == []

    def test_visualization_spec_conversion(self, workflow):
        """Test conversion of visualization to VisualizationSpec."""
        from askrita.sqlagent.formatters.DataFormatter import (
            ChartDataset,
            DataPoint,
            UniversalChartData,
        )

        # Create mock chart data with proper DataPoint objects
        chart_data = UniversalChartData(
            type="bar",
            labels=["North", "South"],
            datasets=[
                ChartDataset(label="Sales", data=[DataPoint(y=1000), DataPoint(y=2000)])
            ],
            title="Sales by Region",
        )

        mock_state = WorkflowState(visualization="bar", chart_data=chart_data)

        viz_spec = workflow._convert_visualization_to_spec(mock_state)

        assert isinstance(viz_spec, VisualizationSpec)
        assert viz_spec.kind == "bar"
        assert viz_spec.options is not None


class TestSqlCorrection:
    """Test SqlCorrection model tracking."""

    def test_sql_correction_tracked_in_state(self, workflow):
        """Test that SqlCorrection is tracked when SQL is corrected."""
        # Mock validate_and_fix_sql to return correction
        workflow.llm_manager = Mock()
        workflow.llm_manager.invoke_with_structured_output = Mock(
            return_value=Mock(
                valid=False,
                corrected_query="SELECT region, SUM(sales) FROM sales_table GROUP BY region",
                issues="Fixed syntax error",
            )
        )
        workflow._get_cached_schema = Mock(return_value="CREATE TABLE sales_table...")
        workflow._track_step = Mock(return_value=None)
        workflow._complete_step = Mock()
        workflow.config.is_step_enabled = Mock(return_value=True)

        state = WorkflowState(
            sql_query="SELECT region SUM(sales) FROM sales_table"  # Missing comma
        )

        result = workflow.validate_and_fix_sql(state)

        # Check if sql_correction is in the result
        assert "sql_correction" in result or hasattr(result, "sql_correction")
        if "sql_correction" in result:
            correction = result["sql_correction"]
            assert isinstance(correction, SqlCorrection)
            assert (
                correction.original_sql == "SELECT region SUM(sales) FROM sales_table"
            )
            assert "SUM(sales)" in correction.corrected_sql
            assert len(correction.reason) > 0


class TestClarificationQuestion:
    """Test ClarificationQuestion model in query_with_cot."""

    def test_query_with_cot_returns_clarification_for_ambiguous_question(
        self, workflow
    ):
        """Test that ambiguous questions return ClarificationQuestion."""
        # Mock state requiring clarification
        mock_state = WorkflowState(
            question="Show me the data",
            needs_clarification=True,
            clarification_prompt="Could you specify which data you want to see?",
            clarification_questions=[
                "Which columns or fields do you want to retrieve?",
                "What conditions or filters should be applied?",
            ],
        )

        workflow.query = Mock(return_value=mock_state)

        result = workflow.query_with_cot("Show me the data")

        # Assert Pydantic model type
        assert isinstance(result, ClarificationQuestion)
        assert "specify which data" in result.question.lower()
        assert len(result.rationale) > 0
        # Verify it's not ChainOfThoughtsOutput
        assert not isinstance(result, ChainOfThoughtsOutput)

    def test_clarification_question_model(self):
        """Test ClarificationQuestion Pydantic model directly."""
        clarification = ClarificationQuestion(
            question="Which columns do you want to see?",
            rationale="Question is ambiguous about which data to retrieve",
        )

        assert isinstance(clarification, ClarificationQuestion)
        assert clarification.question == "Which columns do you want to see?"
        assert "ambiguous" in clarification.rationale.lower()


class TestReasoningSummary:
    """Test ReasoningSummary from callback breadcrumbs."""

    def test_reasoning_summary_from_breadcrumbs(self):
        """Test that ReasoningSummary is created from breadcrumbs."""
        breadcrumbs = [
            "Analyzed your question",
            "Generated SQL query",
            "Executed query against database",
            "Formatted results",
        ]

        reasoning = ReasoningSummary(steps=breadcrumbs)

        assert isinstance(reasoning, ReasoningSummary)
        assert len(reasoning.steps) == 4
        assert reasoning.steps[0] == "Analyzed your question"

    def test_reasoning_summary_max_items(self, workflow):
        """Test that breadcrumbs are limited to max_items."""
        from askrita.sqlagent.workflows.langgraph_callback_handler import (
            ChainOfThoughtsCallbackHandler,
        )

        handler = ChainOfThoughtsCallbackHandler()
        handler._breadcrumbs = [
            "Step 1",
            "Step 2",
            "Step 3",
            "Step 4",
            "Step 5",
            "Step 6",
        ]

        # Get last 5 items
        breadcrumbs = handler.get_breadcrumbs(max_items=5)

        assert len(breadcrumbs) == 5
        assert breadcrumbs[0] == "Step 2"  # Last 5 items


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
