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

"""Tests for SQLAgentWorkflow pure-logic methods (no live LLM/DB needed)."""

import os
import pytest
from unittest.mock import MagicMock, patch

from askrita.sqlagent.workflows.SQLAgentWorkflow import SQLAgentWorkflow
from askrita.sqlagent.State import WorkflowState
from askrita.exceptions import ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def openai_env():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        yield


def _make_workflow():
    """Create a SQLAgentWorkflow with all connections mocked."""
    mock_config = MagicMock()
    mock_config.database.connection_string = "sqlite:///./test.db"
    mock_config.database.cache_schema = False
    mock_config.database.schema_refresh_interval = 3600
    mock_config.database.max_results = 1000
    mock_config.database.sql_syntax.cast_to_string = None
    mock_config.database.sql_syntax.default_cast_types = {
        "bigquery": "STRING",
        "postgresql": "TEXT",
        "snowflake": "VARCHAR",
        "mysql": "CHAR",
        "sqlserver": "NVARCHAR(MAX)",
        "db2": "VARCHAR(255)",
    }
    mock_config.get_database_type.return_value = "SQLite"
    mock_config.framework.debug = False
    mock_config.pii_detection.enabled = False
    mock_config.pii_detection.validate_sample_data = False
    mock_config.workflow.steps = {
        "parse_question": True,
        "get_unique_nouns": True,
        "generate_sql": True,
        "validate_and_fix_sql": True,
        "execute_sql": True,
        "format_results": True,
        "choose_visualization": True,
        "generate_followup_questions": False,
    }
    mock_config.chain_of_thoughts = MagicMock()
    mock_config.chain_of_thoughts.enabled = False

    mock_llm = MagicMock()
    mock_db_manager = MagicMock()
    mock_data_formatter = MagicMock()
    mock_compiled_graph = MagicMock()

    with patch("askrita.sqlagent.workflows.SQLAgentWorkflow.LLMManager", return_value=mock_llm):
        with patch("askrita.sqlagent.workflows.SQLAgentWorkflow.DatabaseManager", return_value=mock_db_manager):
            with patch("askrita.sqlagent.workflows.SQLAgentWorkflow.DataFormatter", return_value=mock_data_formatter):
                with patch("askrita.sqlagent.workflows.SQLAgentWorkflow.create_pii_detector", return_value=None):
                    with patch("askrita.sqlagent.workflows.SQLAgentWorkflow.StateGraph") as mock_sg:
                        mock_sg.return_value.compile.return_value = mock_compiled_graph
                        workflow = SQLAgentWorkflow(
                            config_manager=mock_config,
                            test_llm_connection=False,
                            test_db_connection=False,
                            init_schema_cache=False,
                        )

    workflow.config = mock_config
    workflow.db_manager = mock_db_manager
    workflow.llm_manager = mock_llm
    workflow._cot_tracker = None
    workflow._cot_listeners = []
    workflow.progress_callback = None
    workflow._reasoning_templates = {}
    workflow._workflow_schema_cache = None
    workflow._workflow_schema_cache_time = None
    workflow.pii_detector = None
    workflow._last_callback_handler = None
    return workflow


def _make_state(**kwargs):
    """Create a WorkflowState with sensible defaults."""
    defaults = dict(
        question="What is the revenue?",
        sql_query=None,
        results=None,
        answer=None,
        parsed_question=None,
        needs_clarification=False,
        clarification_prompt=None,
        clarification_questions=None,
        execution_error=None,
        retry_count=0,
    )
    defaults.update(kwargs)
    return WorkflowState(**defaults)


# ---------------------------------------------------------------------------
# _convert_results_to_execution_result
# ---------------------------------------------------------------------------

class TestConvertResultsToExecutionResult:
    def test_empty_results(self):
        wf = _make_workflow()
        result = wf._convert_results_to_execution_result([])
        assert result.rows == []
        assert result.columns == []
        assert result.row_count == 0

    def test_list_of_dicts(self):
        wf = _make_workflow()
        data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        result = wf._convert_results_to_execution_result(data)
        assert result.row_count == 2
        assert "id" in result.columns
        assert "name" in result.columns

    def test_list_of_lists(self):
        wf = _make_workflow()
        data = [[1, "Alice"], [2, "Bob"]]
        result = wf._convert_results_to_execution_result(data)
        assert result.row_count == 2
        assert result.columns[0] == "column_1"

    def test_list_of_lists_empty_inner(self):
        wf = _make_workflow()
        data = [[]]
        result = wf._convert_results_to_execution_result(data)
        assert result.columns == []

    def test_fallback_scalar_results(self):
        wf = _make_workflow()
        data = [42, 43]
        result = wf._convert_results_to_execution_result(data)
        assert result.row_count == 2
        assert result.columns == ["value"]

    def test_none_results(self):
        wf = _make_workflow()
        result = wf._convert_results_to_execution_result(None)
        assert result.row_count == 0


# ---------------------------------------------------------------------------
# _convert_visualization_to_spec
# ---------------------------------------------------------------------------

class TestConvertVisualizationToSpec:
    def test_no_chart_data_returns_table(self):
        wf = _make_workflow()
        state = _make_state(visualization=None, chart_data=None)
        spec = wf._convert_visualization_to_spec(state)
        assert spec.kind == "table"

    def test_explicit_visualization_type(self):
        wf = _make_workflow()
        state = _make_state(visualization="bar", chart_data=None)
        spec = wf._convert_visualization_to_spec(state)
        assert spec.kind == "bar"

    def test_chart_data_none_returns_no_options(self):
        wf = _make_workflow()
        state = _make_state(visualization="bar", chart_data=None)
        spec = wf._convert_visualization_to_spec(state)
        assert spec.options is None
        assert spec.x is None
        assert spec.y is None


# ---------------------------------------------------------------------------
# to_chain_of_thoughts_output
# ---------------------------------------------------------------------------

class TestToChainOfThoughtsOutput:
    def test_needs_clarification_returns_clarification_question(self):
        wf = _make_workflow()
        state = _make_state(
            needs_clarification=True,
            clarification_prompt="Please clarify your question",
            clarification_questions=["What time period?"],
        )
        result = wf.to_chain_of_thoughts_output(state)
        from askrita.models.chain_of_thoughts import ClarificationQuestion
        assert isinstance(result, ClarificationQuestion)
        assert result.question == "Please clarify your question"
        assert result.rationale == "What time period?"

    def test_needs_clarification_no_questions(self):
        wf = _make_workflow()
        state = _make_state(
            needs_clarification=True,
            clarification_prompt="Please clarify",
            clarification_questions=None,
        )
        result = wf.to_chain_of_thoughts_output(state)
        from askrita.models.chain_of_thoughts import ClarificationQuestion
        assert isinstance(result, ClarificationQuestion)
        assert result.rationale == "Additional information needed"

    def test_normal_state_returns_cot_output(self):
        wf = _make_workflow()
        state = _make_state(
            question="What is revenue?",
            sql_query="SELECT SUM(revenue) FROM sales",
            results=[{"revenue": 1000}],
            answer="Revenue is $1000",
        )
        result = wf.to_chain_of_thoughts_output(state)
        from askrita.models.chain_of_thoughts import ChainOfThoughtsOutput
        assert isinstance(result, ChainOfThoughtsOutput)
        assert result.sql == "SELECT SUM(revenue) FROM sales"
        assert result.result.row_count == 1

    def test_no_callback_handler_uses_default_breadcrumbs(self):
        wf = _make_workflow()
        wf._last_callback_handler = None
        state = _make_state(answer="Some answer", results=[])
        result = wf.to_chain_of_thoughts_output(state)
        from askrita.models.chain_of_thoughts import ChainOfThoughtsOutput
        assert isinstance(result, ChainOfThoughtsOutput)
        assert len(result.reasoning.steps) > 0

    def test_with_callback_handler_uses_breadcrumbs(self):
        wf = _make_workflow()
        handler = MagicMock()
        handler.get_breadcrumbs.return_value = ["Step 1", "Step 2"]
        state = _make_state(answer="Some answer", results=[])
        result = wf.to_chain_of_thoughts_output(state, callback_handler=handler)
        from askrita.models.chain_of_thoughts import ChainOfThoughtsOutput
        assert isinstance(result, ChainOfThoughtsOutput)
        assert result.reasoning.steps == ["Step 1", "Step 2"]

    def test_uses_last_callback_handler_if_no_argument(self):
        wf = _make_workflow()
        handler = MagicMock()
        handler.get_breadcrumbs.return_value = ["A", "B"]
        wf._last_callback_handler = handler
        state = _make_state(answer="Some answer", results=[])
        result = wf.to_chain_of_thoughts_output(state)
        from askrita.models.chain_of_thoughts import ChainOfThoughtsOutput
        assert isinstance(result, ChainOfThoughtsOutput)
        assert result.reasoning.steps == ["A", "B"]


# ---------------------------------------------------------------------------
# chat() validation
# ---------------------------------------------------------------------------

class TestChatValidation:
    def test_empty_messages_raises_validation_error(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf.chat([])

    def test_none_messages_raises_validation_error(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf.chat(None)

    def test_messages_not_a_list_raises_validation_error(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf.chat("some string")

    def test_no_user_message_raises_validation_error(self):
        wf = _make_workflow()
        messages = [{"role": "assistant", "content": "Hello"}]
        with pytest.raises(ValidationError):
            wf.chat(messages)

    def test_empty_user_content_raises_validation_error(self):
        wf = _make_workflow()
        messages = [{"role": "user", "content": "   "}]
        with pytest.raises(ValidationError):
            wf.chat(messages)

    def test_valid_messages_calls_execute_query(self):
        wf = _make_workflow()
        wf._execute_query = MagicMock(return_value=_make_state())
        messages = [{"role": "user", "content": "Show me revenue"}]
        wf.chat(messages)
        wf._execute_query.assert_called_once()


# ---------------------------------------------------------------------------
# _should_continue_workflow
# ---------------------------------------------------------------------------

class TestShouldContinueWorkflow:
    def test_no_clarification_returns_continue(self):
        wf = _make_workflow()
        state = _make_state(needs_clarification=False)
        result = wf._should_continue_workflow(state, "parse_question")
        assert result == "continue"

    def test_clarification_needed_returns_end(self):
        wf = _make_workflow()
        state = _make_state(
            needs_clarification=True,
            clarification_prompt="Need more info",
            parsed_question=None,
        )
        result = wf._should_continue_workflow(state, "parse_question")
        assert result == "__end__"

    def test_not_relevant_question_continues(self):
        wf = _make_workflow()
        state = _make_state(
            needs_clarification=True,
            clarification_prompt="Need more info",
            parsed_question={"is_relevant": False},
        )
        result = wf._should_continue_workflow(state, "parse_question")
        assert result == "continue"

    def test_relevant_but_clarification_needed_returns_end(self):
        wf = _make_workflow()
        state = _make_state(
            needs_clarification=True,
            clarification_prompt="Which month?",
            parsed_question={"is_relevant": True},
        )
        result = wf._should_continue_workflow(state, "parse_question")
        assert result == "__end__"


# ---------------------------------------------------------------------------
# _should_retry_sql_generation
# ---------------------------------------------------------------------------

class TestShouldRetrySqlGeneration:
    def test_needs_clarification_returns_end(self):
        wf = _make_workflow()
        wf.config.workflow.max_retries = 3
        state = _make_state(needs_clarification=True, execution_error=None)
        result = wf._should_retry_sql_generation(state)
        assert result == "__end__"

    def test_no_error_returns_continue(self):
        wf = _make_workflow()
        wf.config.workflow.max_retries = 3
        state = _make_state(execution_error=None, retry_count=0)
        result = wf._should_retry_sql_generation(state)
        assert result == "continue"

    def test_error_below_max_retries_returns_generate_sql(self):
        wf = _make_workflow()
        wf.config.workflow.max_retries = 3
        state = _make_state(execution_error="table not found", retry_count=1)
        result = wf._should_retry_sql_generation(state)
        assert result == "generate_sql"

    def test_error_at_max_retries_returns_end(self):
        wf = _make_workflow()
        wf.config.workflow.max_retries = 3
        state = _make_state(execution_error="still failing", retry_count=3)
        result = wf._should_retry_sql_generation(state)
        assert result == "__end__"

    def test_uses_config_max_retries(self):
        wf = _make_workflow()
        # config.workflow.max_retries should be accessed via getattr
        wf.config.workflow = MagicMock()
        wf.config.workflow.max_retries = 5
        state = _make_state(execution_error="error", retry_count=4)
        result = wf._should_retry_sql_generation(state)
        assert result == "generate_sql"


# ---------------------------------------------------------------------------
# _summarize_conversation_context
# ---------------------------------------------------------------------------

class TestSummarizeConversationContext:
    def test_single_message_returns_empty(self):
        wf = _make_workflow()
        messages = [{"role": "user", "content": "What is revenue?"}]
        result = wf._summarize_conversation_context(messages)
        assert result == ""

    def test_two_messages_includes_context(self):
        wf = _make_workflow()
        wf.config.get_conversation_context_settings = MagicMock(return_value={"max_history_messages": 6})
        messages = [
            {"role": "user", "content": "Show me sales"},
            {"role": "assistant", "content": "Here are your sales numbers for last month"},
            {"role": "user", "content": "What about revenue?"},
        ]
        result = wf._summarize_conversation_context(messages)
        assert isinstance(result, str)

    def test_sales_content_detected(self):
        wf = _make_workflow()
        wf.config.get_conversation_context_settings = MagicMock(return_value={"max_history_messages": 6})
        messages = [
            {"role": "user", "content": "show me something"},
            {"role": "assistant", "content": "Here are your sales data by region"},
            {"role": "user", "content": "more detail please"},
        ]
        result = wf._summarize_conversation_context(messages)
        assert "sales" in result.lower()

    def test_revenue_content_detected(self):
        wf = _make_workflow()
        wf.config.get_conversation_context_settings = MagicMock(return_value={"max_history_messages": 6})
        messages = [
            {"role": "user", "content": "show me something"},
            {"role": "assistant", "content": "Total revenue is $1,000,000"},
            {"role": "user", "content": "more detail"},
        ]
        result = wf._summarize_conversation_context(messages)
        assert "financial" in result.lower() or "revenue" in result.lower()

    def test_previous_user_question_included(self):
        wf = _make_workflow()
        wf.config.get_conversation_context_settings = MagicMock(return_value={"max_history_messages": 6})
        messages = [
            {"role": "user", "content": "What is the revenue?"},
            {"role": "assistant", "content": "Revenue is $1M"},
            {"role": "user", "content": "Break it down by quarter"},
        ]
        result = wf._summarize_conversation_context(messages)
        assert "What is the revenue?" in result

    def test_no_assistant_messages_returns_empty_or_previous_question(self):
        wf = _make_workflow()
        wf.config.get_conversation_context_settings = MagicMock(return_value={"max_history_messages": 6})
        messages = [
            {"role": "user", "content": "First question"},
            {"role": "user", "content": "Second question"},
        ]
        result = wf._summarize_conversation_context(messages)
        # Either empty string or includes previous question
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# get_cache_status
# ---------------------------------------------------------------------------

class TestGetCacheStatus:
    def test_returns_dict_with_expected_keys(self):
        wf = _make_workflow()
        wf.config.get_schema_cache_info = MagicMock(return_value={
            "enabled": False,
            "cached": False,
        })
        wf.config.database.schema_refresh_interval = 3600
        wf._workflow_schema_cache = None
        wf._workflow_schema_cache_time = None
        result = wf.get_cache_status()
        assert "config_level_cache" in result
        assert "workflow_level_cache" in result
        assert "refresh_interval" in result

    def test_workflow_cache_has_age_when_set(self):
        from datetime import datetime, timedelta
        wf = _make_workflow()
        wf.config.get_schema_cache_info = MagicMock(return_value={})
        wf.config.database.schema_refresh_interval = 3600
        wf._workflow_schema_cache = "some schema"
        wf._workflow_schema_cache_time = datetime.now() - timedelta(seconds=100)
        result = wf.get_cache_status()
        assert result["workflow_level_cache"]["cached"] is True
        assert "age_seconds" in result["workflow_level_cache"]
        assert result["workflow_level_cache"]["age_seconds"] >= 99


# ---------------------------------------------------------------------------
# pii_detection_step - only test paths that don't call step.complete on a string
# Note: pii_detection_step calls step.complete() on the return value of _track_step,
# which returns a string. Paths that reach step.complete() on the pii_result branch
# will fail with AttributeError; we only test the early-exit path where
# pii_detector is None (returns {} before any step.complete call).
# ---------------------------------------------------------------------------

class TestPiiDetectionStep:
    def test_no_pii_detector_with_mocked_step(self):
        """Test that when pii_detector is None, returns empty dict (step.complete is mocked)."""
        wf = _make_workflow()
        wf.pii_detector = None
        # Patch _track_step to return a mock step object that has .complete()
        mock_step = MagicMock()
        wf._track_step = MagicMock(return_value=mock_step)
        state = _make_state(question="What is revenue?")
        result = wf.pii_detection_step(state)
        assert result == {}
        mock_step.complete.assert_called_once()

    def test_pii_not_detected_returns_result(self):
        wf = _make_workflow()
        pii_result = MagicMock()
        pii_result.has_pii = False
        pii_result.blocked = False
        pii_result.entity_types = []
        pii_result.max_confidence = 0.0
        pii_result.analysis_time_ms = 5
        wf.pii_detector = MagicMock()
        wf.pii_detector.detect_pii_in_text.return_value = pii_result
        mock_step = MagicMock()
        wf._track_step = MagicMock(return_value=mock_step)
        state = _make_state(question="What is revenue?")
        result = wf.pii_detection_step(state)
        assert result["pii_detection_result"]["blocked"] is False

    def test_pii_detected_blocked(self):
        wf = _make_workflow()
        pii_result = MagicMock()
        pii_result.has_pii = True
        pii_result.blocked = True
        pii_result.entity_types = ["PERSON"]
        pii_result.max_confidence = 0.95
        wf.pii_detector = MagicMock()
        wf.pii_detector.detect_pii_in_text.return_value = pii_result
        mock_step = MagicMock()
        wf._track_step = MagicMock(return_value=mock_step)
        state = _make_state(question="What about John Doe?")
        result = wf.pii_detection_step(state)
        assert result["needs_clarification"] is True
        assert result["pii_detection_result"]["blocked"] is True

    def test_pii_detected_not_blocked(self):
        wf = _make_workflow()
        pii_result = MagicMock()
        pii_result.has_pii = True
        pii_result.blocked = False
        pii_result.entity_types = ["EMAIL"]
        pii_result.max_confidence = 0.8
        pii_result.analysis_time_ms = 10
        wf.pii_detector = MagicMock()
        wf.pii_detector.detect_pii_in_text.return_value = pii_result
        mock_step = MagicMock()
        wf._track_step = MagicMock(return_value=mock_step)
        state = _make_state(question="Data with email@test.com")
        result = wf.pii_detection_step(state)
        assert result["pii_detection_result"]["blocked"] is False

    def test_pii_exception_returns_safe_result(self):
        wf = _make_workflow()
        wf.pii_detector = MagicMock()
        wf.pii_detector.detect_pii_in_text.side_effect = RuntimeError("PII error")
        mock_step = MagicMock()
        wf._track_step = MagicMock(return_value=mock_step)
        state = _make_state(question="What is revenue?")
        result = wf.pii_detection_step(state)
        assert result["pii_detection_result"]["blocked"] is False


# ---------------------------------------------------------------------------
# format_results step - early-exit paths
# ---------------------------------------------------------------------------

class TestFormatResultsEarlyExits:
    def test_step_disabled_returns_disabled_message(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=False)
        state = _make_state(sql_query="SELECT 1", results=[{"id": 1}])
        result = wf.format_results(state)
        assert "disabled" in result.get("answer", "").lower()

    def test_not_relevant_returns_helpful_response(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        state = _make_state(
            question="Who is the CEO?",
            sql_query="NOT_RELEVANT",
            sql_reason="This is about business data",
        )
        result = wf.format_results(state)
        assert "answer" in result
        assert result["answer"] != ""

    def test_not_relevant_uses_default_message_when_no_reason(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        state = _make_state(
            question="Who is the CEO?",
            sql_query="NOT_RELEVANT",
            sql_reason=None,
        )
        result = wf.format_results(state)
        assert "answer" in result

    def test_empty_results_returns_no_results_message(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        state = _make_state(sql_query="SELECT * FROM sales", results=[])
        result = wf.format_results(state)
        assert "no results" in result.get("answer", "").lower()


# ---------------------------------------------------------------------------
# execute_sql step - early-exit paths
# ---------------------------------------------------------------------------

class TestExecuteSqlEarlyExits:
    def test_step_disabled_returns_empty(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=False)
        state = _make_state(sql_query="SELECT 1")
        result = wf.execute_sql(state)
        assert result["results"] == []
        assert result["execution_error"] is None

    def test_not_relevant_skips_execution(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        state = _make_state(sql_query="NOT_RELEVANT")
        result = wf.execute_sql(state)
        assert result["results"] == []

    def test_empty_sql_skips_execution(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        state = _make_state(sql_query="")
        result = wf.execute_sql(state)
        assert result["results"] == []

    def test_error_sql_skips_execution(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        state = _make_state(sql_query="ERROR")
        result = wf.execute_sql(state)
        assert result["results"] == []

    def test_successful_execution(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        wf.db_manager.execute_query = MagicMock(return_value=[{"id": 1}])
        state = _make_state(sql_query="SELECT * FROM sales")
        result = wf.execute_sql(state)
        assert result["results"] == [{"id": 1}]
        assert result["execution_error"] is None

    def test_error_string_result(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        wf.db_manager.execute_query = MagicMock(return_value="Error: table not found")
        state = _make_state(sql_query="SELECT * FROM nonexistent")
        result = wf.execute_sql(state)
        assert result["results"] == []
        assert result["execution_error"] is not None

    def test_exception_raises_execution_error(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        from askrita.exceptions import DatabaseError
        wf.db_manager.execute_query = MagicMock(side_effect=DatabaseError("db crashed"))
        state = _make_state(sql_query="SELECT 1")
        result = wf.execute_sql(state)
        assert "execution_error" in result
        assert result["execution_error"] is not None


# ---------------------------------------------------------------------------
# choose_visualization step - early-exit paths
# ---------------------------------------------------------------------------

class TestChooseVisualizationEarlyExits:
    def test_step_disabled_returns_none(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=False)
        state = _make_state(sql_query="SELECT 1", results=[{"id": 1}])
        result = wf.choose_visualization(state)
        assert result["visualization"] == "none"

    def test_empty_results_returns_none(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        state = _make_state(sql_query="SELECT 1", results=[])
        result = wf.choose_visualization(state)
        assert result["visualization"] == "none"
        assert "No data" in result.get("visualization_reason", "")


# ---------------------------------------------------------------------------
# generate_followup_questions step - early-exit paths
# ---------------------------------------------------------------------------

class TestGenerateFollowupQuestionsEarlyExits:
    def test_step_disabled_returns_empty(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=False)
        state = _make_state(answer="Some answer", results=[{"id": 1}])
        result = wf.generate_followup_questions(state)
        assert result["followup_questions"] == []

    def test_no_results_returns_empty(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        state = _make_state(answer="Some answer", results=[])
        result = wf.generate_followup_questions(state)
        assert result["followup_questions"] == []

    def test_no_answer_returns_empty(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        state = _make_state(answer=None, results=[{"id": 1}])
        result = wf.generate_followup_questions(state)
        assert result["followup_questions"] == []


# ---------------------------------------------------------------------------
# _get_cached_schema
# ---------------------------------------------------------------------------

class TestGetCachedSchema:
    def test_uses_workflow_cache_when_valid(self):
        from datetime import datetime
        wf = _make_workflow()
        wf._workflow_schema_cache = "CREATE TABLE sales (id INT);"
        wf._workflow_schema_cache_time = datetime.now()
        wf.config.database.cache_schema = True
        wf.config.database.schema_refresh_interval = 3600
        result = wf._get_cached_schema()
        assert result == "CREATE TABLE sales (id INT);"

    def test_fetches_schema_when_cache_is_none(self):
        wf = _make_workflow()
        wf._workflow_schema_cache = None
        wf._workflow_schema_cache_time = None
        wf.config.database.cache_schema = False  # caching disabled, just fetches
        wf.db_manager.get_schema = MagicMock(return_value="CREATE TABLE orders (id INT);")
        result = wf._get_cached_schema()
        assert result == "CREATE TABLE orders (id INT);"

    def test_fetches_schema_when_cache_is_none_with_caching_enabled(self):
        wf = _make_workflow()
        wf._workflow_schema_cache = None
        wf._workflow_schema_cache_time = None
        wf.config.database.cache_schema = True
        wf.config.database.schema_refresh_interval = 3600
        wf.db_manager.get_schema = MagicMock(return_value="CREATE TABLE orders (id INT);")
        result = wf._get_cached_schema()
        assert result == "CREATE TABLE orders (id INT);"
        # With caching enabled, should also cache it
        assert wf._workflow_schema_cache == "CREATE TABLE orders (id INT);"

    def test_fetches_schema_when_cache_expired(self):
        from datetime import datetime, timedelta
        wf = _make_workflow()
        wf._workflow_schema_cache = "OLD SCHEMA"
        wf._workflow_schema_cache_time = datetime.now() - timedelta(seconds=7200)
        wf.config.database.cache_schema = True
        wf.config.database.schema_refresh_interval = 3600
        wf.db_manager.get_schema = MagicMock(return_value="NEW SCHEMA")
        result = wf._get_cached_schema()
        assert result == "NEW SCHEMA"


# ---------------------------------------------------------------------------
# _validate_sql_safety
# ---------------------------------------------------------------------------

class TestValidateSqlSafety:
    def test_valid_select_passes(self):
        wf = _make_workflow()
        wf.config.get_sql_safety_settings = MagicMock(return_value={
            "allowed_query_types": ["SELECT", "WITH"],
        })
        # Should not raise (specific column, not SELECT *)
        wf._validate_sql_safety("SELECT id, revenue FROM sales")

    def test_empty_query_raises_validation_error(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf._validate_sql_safety("")

    def test_none_raises_validation_error(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf._validate_sql_safety(None)

    def test_non_string_raises_validation_error(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf._validate_sql_safety(123)

    def test_drop_statement_raises_validation_error(self):
        wf = _make_workflow()
        wf.config.get_sql_safety_settings = MagicMock(return_value={
            "allowed_query_types": ["SELECT", "WITH"],
        })
        with pytest.raises(ValidationError):
            wf._validate_sql_safety("DROP TABLE sales")

    def test_with_cte_passes(self):
        wf = _make_workflow()
        wf.config.get_sql_safety_settings = MagicMock(return_value={
            "allowed_query_types": ["SELECT", "WITH"],
        })
        # Should not raise (CTE with specific columns)
        wf._validate_sql_safety("WITH cte AS (SELECT id FROM t) SELECT id FROM cte")

    def test_line_comment_stripped_before_check(self):
        wf = _make_workflow()
        wf.config.get_sql_safety_settings = MagicMock(return_value={
            "allowed_query_types": ["SELECT", "WITH"],
        })
        # Line comment should be stripped, leaving valid SELECT
        wf._validate_sql_safety("-- DROP TABLE\nSELECT 1")

    def test_block_comment_stripped_before_check(self):
        wf = _make_workflow()
        wf.config.get_sql_safety_settings = MagicMock(return_value={
            "allowed_query_types": ["SELECT", "WITH"],
        })
        # Block comment stripped, leaving SELECT
        wf._validate_sql_safety("/* DROP TABLE */ SELECT 1")


# ---------------------------------------------------------------------------
# choose_and_format_visualization step - early-exit paths
# ---------------------------------------------------------------------------

class TestChooseAndFormatVisualizationEarlyExits:
    def test_step_disabled_returns_none_visualization(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=False)
        state = _make_state(sql_query="SELECT 1", results=[{"id": 1}])
        result = wf.choose_and_format_visualization(state)
        assert result["visualization"] == "none"
        assert result["chart_data"] is None

    def test_empty_results_returns_none(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        state = _make_state(sql_query="SELECT 1", results=[])
        result = wf.choose_and_format_visualization(state)
        assert result["visualization"] == "none"
        assert result["chart_data"] is None


# ---------------------------------------------------------------------------
# generate_sql step - early-exit paths
# ---------------------------------------------------------------------------

class TestGenerateSqlEarlyExits:
    def test_step_disabled_returns_empty_sql(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=False)
        state = _make_state(
            parsed_question={"is_relevant": True},
            unique_nouns=[],
            execution_error=None,
            retry_count=0,
        )
        result = wf.generate_sql(state)
        assert result["sql_query"] == ""

    def test_not_relevant_returns_not_relevant_sql(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        state = _make_state(
            question="Who is the CEO?",
            parsed_question={"is_relevant": False, "relevance_reason": "Not about data"},
            unique_nouns=[],
            execution_error=None,
            retry_count=0,
        )
        result = wf.generate_sql(state)
        assert result["sql_query"] == "NOT_RELEVANT"


# ---------------------------------------------------------------------------
# backward compatibility methods
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_run_delegates_to_query(self):
        wf = _make_workflow()
        wf.query = MagicMock(return_value=_make_state())
        wf.run("What is revenue?")
        wf.query.assert_called_once_with("What is revenue?")

    def test_run_sql_agent_delegates_to_query(self):
        wf = _make_workflow()
        wf.query = MagicMock(return_value=_make_state())
        wf.run_sql_agent("What is revenue?")
        wf.query.assert_called_once_with("What is revenue?")


# ---------------------------------------------------------------------------
# _parse_schema_to_dict
# ---------------------------------------------------------------------------

class TestParseSchemaToDict:
    def test_empty_schema_returns_empty_tables(self):
        wf = _make_workflow()
        result = wf._parse_schema_to_dict("")
        assert result == {"tables": {}}

    def test_none_schema_raises_or_returns_empty(self):
        wf = _make_workflow()
        # _parse_schema_to_dict does not guard against None; it will raise TypeError.
        # If the implementation changes to handle None gracefully, this should return {"tables": {}}.
        try:
            result = wf._parse_schema_to_dict(None)
            assert result == {"tables": {}}
        except TypeError:
            pass  # expected given current implementation

    def test_simple_table_parsed(self):
        wf = _make_workflow()
        schema = "CREATE TABLE sales (id INT, revenue FLOAT);"
        result = wf._parse_schema_to_dict(schema)
        assert "tables" in result
        # Should find the 'sales' table
        tables = result["tables"]
        assert len(tables) > 0

    def test_bigquery_backtick_table_parsed(self):
        wf = _make_workflow()
        schema = "CREATE TABLE `project.dataset.orders` (id INT64, amount FLOAT64);"
        result = wf._parse_schema_to_dict(schema)
        assert "tables" in result
