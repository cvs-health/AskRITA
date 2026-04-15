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

"""Tests for NoSQLAgentWorkflow pure-logic methods (no live LLM/DB needed)."""

import os
from unittest.mock import MagicMock, patch

import pytest

from askrita.exceptions import ValidationError
from askrita.sqlagent.State import WorkflowState
from askrita.sqlagent.workflows.NoSQLAgentWorkflow import NoSQLAgentWorkflow

_REVENUE_QUESTION = "What is the revenue?"
_SAMPLE_QUERY = (
    "db.orders.aggregate([{$group: {_id: null, total: {$sum: '$revenue'}}}])"
)


@pytest.fixture(autouse=True)
def openai_env():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        yield


def _make_workflow():
    """Create a NoSQLAgentWorkflow with all connections mocked."""
    mock_config = MagicMock()
    mock_config.database.connection_string = "mongodb://localhost:27017/testdb"
    mock_config.database.cache_schema = False
    mock_config.database.schema_refresh_interval = 3600
    mock_config.database.max_results = 1000
    mock_config.get_database_type.return_value = "MongoDB"
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
        "choose_and_format_visualization": True,
        "generate_followup_questions": False,
    }
    mock_config.chain_of_thoughts = MagicMock()
    mock_config.chain_of_thoughts.enabled = False

    mock_llm = MagicMock()
    mock_db_manager = MagicMock()
    mock_data_formatter = MagicMock()
    mock_compiled_graph = MagicMock()

    with patch(
        "askrita.sqlagent.workflows.NoSQLAgentWorkflow.LLMManager",
        return_value=mock_llm,
    ):
        with patch(
            "askrita.sqlagent.workflows.NoSQLAgentWorkflow.NoSQLDatabaseManager",
            return_value=mock_db_manager,
        ):
            with patch(
                "askrita.sqlagent.workflows.NoSQLAgentWorkflow.DataFormatter",
                return_value=mock_data_formatter,
            ):
                with patch(
                    "askrita.sqlagent.workflows.NoSQLAgentWorkflow.create_pii_detector",
                    return_value=None,
                ):
                    with patch(
                        "askrita.sqlagent.workflows.NoSQLAgentWorkflow.StateGraph"
                    ) as mock_sg:
                        mock_sg.return_value.compile.return_value = mock_compiled_graph
                        workflow = NoSQLAgentWorkflow(
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
    defaults = dict(
        question=_REVENUE_QUESTION,
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
# query() validation
# ---------------------------------------------------------------------------


class TestQueryValidation:
    def test_empty_question_raises_validation_error(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf.query("")

    def test_whitespace_only_raises_validation_error(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf.query("   ")

    def test_non_string_raises_validation_error(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf.query(123)

    def test_valid_question_calls_execute_query(self):
        wf = _make_workflow()
        wf._execute_query = MagicMock(return_value=_make_state())
        wf.query(_REVENUE_QUESTION)
        wf._execute_query.assert_called_once_with(_REVENUE_QUESTION)


# ---------------------------------------------------------------------------
# chat() validation
# ---------------------------------------------------------------------------


class TestChatValidation:
    def test_empty_messages_raises(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf.chat([])

    def test_none_messages_raises(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf.chat(None)

    def test_non_list_raises(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf.chat("just a string")

    def test_no_user_message_raises(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf.chat([{"role": "assistant", "content": "Hello"}])

    def test_empty_user_content_raises(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf.chat([{"role": "user", "content": "   "}])

    def test_valid_messages_calls_execute_query(self):
        wf = _make_workflow()
        wf._execute_query = MagicMock(return_value=_make_state())
        wf.chat([{"role": "user", "content": "Show me revenue"}])
        wf._execute_query.assert_called_once()


# ---------------------------------------------------------------------------
# _validate_query_safety
# ---------------------------------------------------------------------------


class TestValidateQuerySafety:
    def test_valid_aggregate_passes(self):
        wf = _make_workflow()
        wf._validate_query_safety(_SAMPLE_QUERY)

    def test_empty_string_raises(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf._validate_query_safety("")

    def test_none_raises(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf._validate_query_safety(None)

    def test_non_string_raises(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf._validate_query_safety(42)

    def test_out_stage_raises(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf._validate_query_safety("db.orders.aggregate([{$out: 'output'}])")

    def test_merge_stage_raises(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf._validate_query_safety(
                "db.orders.aggregate([{$merge: {into: 'target'}}])"
            )

    def test_delete_one_raises(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf._validate_query_safety("db.orders.deleteOne({_id: 1})")

    def test_delete_many_raises(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf._validate_query_safety("db.orders.deleteMany({})")

    def test_insert_one_raises(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf._validate_query_safety("db.orders.insertOne({name: 'test'})")

    def test_update_one_raises(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf._validate_query_safety("db.orders.updateOne({}, {$set: {x: 1}})")

    def test_drop_raises(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf._validate_query_safety("db.orders.drop()")

    def test_too_long_query_raises(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf._validate_query_safety("SELECT " + "x" * 50001)

    def test_case_insensitive_forbidden_check(self):
        wf = _make_workflow()
        with pytest.raises(ValidationError):
            wf._validate_query_safety("db.orders.DeleteOne({_id: 1})")


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
        state = _make_state(needs_clarification=True, parsed_question=None)
        result = wf._should_continue_workflow(state, "parse_question")
        assert result == "__end__"

    def test_not_relevant_continues(self):
        wf = _make_workflow()
        state = _make_state(
            needs_clarification=True,
            parsed_question={"is_relevant": False},
        )
        result = wf._should_continue_workflow(state, "parse_question")
        assert result == "continue"

    def test_relevant_but_clarification_returns_end(self):
        wf = _make_workflow()
        state = _make_state(
            needs_clarification=True,
            parsed_question={"is_relevant": True},
        )
        result = wf._should_continue_workflow(state, "parse_question")
        assert result == "__end__"


# ---------------------------------------------------------------------------
# _should_retry_query_generation
# ---------------------------------------------------------------------------


class TestShouldRetryQueryGeneration:
    def test_needs_clarification_returns_end(self):
        wf = _make_workflow()
        wf.config.workflow.max_retries = 3
        state = _make_state(needs_clarification=True, execution_error=None)
        assert wf._should_retry_query_generation(state) == "__end__"

    def test_no_error_returns_continue(self):
        wf = _make_workflow()
        wf.config.workflow.max_retries = 3
        state = _make_state(execution_error=None, retry_count=0)
        assert wf._should_retry_query_generation(state) == "continue"

    def test_error_below_max_returns_generate_sql(self):
        wf = _make_workflow()
        wf.config.workflow.max_retries = 3
        state = _make_state(execution_error="query failed", retry_count=1)
        assert wf._should_retry_query_generation(state) == "generate_sql"

    def test_error_at_max_returns_end(self):
        wf = _make_workflow()
        wf.config.workflow.max_retries = 3
        state = _make_state(execution_error="still failing", retry_count=3)
        assert wf._should_retry_query_generation(state) == "__end__"


# ---------------------------------------------------------------------------
# _get_cached_schema
# ---------------------------------------------------------------------------


class TestGetCachedSchema:
    def test_returns_cached_when_fresh(self):
        from datetime import datetime

        wf = _make_workflow()
        wf._workflow_schema_cache = "db.orders schema"
        wf._workflow_schema_cache_time = datetime.now()
        wf.config.database.cache_schema = True
        wf.config.database.schema_refresh_interval = 3600
        result = wf._get_cached_schema()
        assert result == "db.orders schema"

    def test_fetches_when_cache_none(self):
        wf = _make_workflow()
        wf._workflow_schema_cache = None
        wf._workflow_schema_cache_time = None
        wf.config.database.cache_schema = False
        wf.db_manager.get_schema = MagicMock(return_value="fresh schema")
        result = wf._get_cached_schema()
        assert result == "fresh schema"

    def test_caches_when_enabled(self):
        wf = _make_workflow()
        wf._workflow_schema_cache = None
        wf._workflow_schema_cache_time = None
        wf.config.database.cache_schema = True
        wf.config.database.schema_refresh_interval = 3600
        wf.db_manager.get_schema = MagicMock(return_value="new schema")
        wf._get_cached_schema()
        assert wf._workflow_schema_cache == "new schema"

    def test_refetches_on_expired_cache(self):
        from datetime import datetime, timedelta

        wf = _make_workflow()
        wf._workflow_schema_cache = "old schema"
        wf._workflow_schema_cache_time = datetime.now() - timedelta(seconds=7200)
        wf.config.database.cache_schema = True
        wf.config.database.schema_refresh_interval = 3600
        wf.db_manager.get_schema = MagicMock(return_value="new schema")
        result = wf._get_cached_schema()
        assert result == "new schema"


# ---------------------------------------------------------------------------
# clear_schema_cache
# ---------------------------------------------------------------------------


class TestClearSchemaCache:
    def test_clears_when_set(self):
        wf = _make_workflow()
        from datetime import datetime

        wf._workflow_schema_cache = "some schema"
        wf._workflow_schema_cache_time = datetime.now()
        wf.clear_schema_cache()
        assert wf._workflow_schema_cache is None
        assert wf._workflow_schema_cache_time is None

    def test_no_op_when_already_none(self):
        wf = _make_workflow()
        wf._workflow_schema_cache = None
        wf.clear_schema_cache()  # Should not raise


# ---------------------------------------------------------------------------
# CoT listener management
# ---------------------------------------------------------------------------


class TestCotListeners:
    def test_register_listener(self):
        wf = _make_workflow()
        listener = MagicMock()
        wf.register_cot_listener(listener)
        assert listener in wf._cot_listeners

    def test_register_duplicate_not_added(self):
        wf = _make_workflow()
        listener = MagicMock()
        wf.register_cot_listener(listener)
        wf.register_cot_listener(listener)
        assert wf._cot_listeners.count(listener) == 1

    def test_unregister_listener(self):
        wf = _make_workflow()
        listener = MagicMock()
        wf.register_cot_listener(listener)
        wf.unregister_cot_listener(listener)
        assert listener not in wf._cot_listeners

    def test_unregister_nonexistent_no_crash(self):
        wf = _make_workflow()
        wf.unregister_cot_listener(MagicMock())

    def test_clear_listeners(self):
        wf = _make_workflow()
        wf.register_cot_listener(MagicMock())
        wf.register_cot_listener(MagicMock())
        wf.clear_cot_listeners()
        assert wf._cot_listeners == []


# ---------------------------------------------------------------------------
# execute_query step - early exits
# ---------------------------------------------------------------------------


class TestExecuteQueryStep:
    def test_step_disabled_returns_empty(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=False)
        state = _make_state(sql_query=_SAMPLE_QUERY)
        result = wf.execute_query(state)
        assert result["results"] == []
        assert result["execution_error"] is None

    def test_not_relevant_returns_empty(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        state = _make_state(sql_query="NOT_RELEVANT")
        result = wf.execute_query(state)
        assert result["results"] == []

    def test_empty_query_returns_empty(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        state = _make_state(sql_query="")
        result = wf.execute_query(state)
        assert result["results"] == []

    def test_successful_execution(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        wf.db_manager.execute_query = MagicMock(return_value=[{"revenue": 1000}])
        state = _make_state(sql_query=_SAMPLE_QUERY)
        result = wf.execute_query(state)
        assert result["results"] == [{"revenue": 1000}]
        assert result["execution_error"] is None

    def test_exception_captured_in_error(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        wf.db_manager.execute_query = MagicMock(
            side_effect=RuntimeError("connection lost")
        )
        state = _make_state(sql_query=_SAMPLE_QUERY)
        result = wf.execute_query(state)
        assert result["results"] == []
        assert result["execution_error"] is not None


# ---------------------------------------------------------------------------
# format_results step - early exits
# ---------------------------------------------------------------------------


class TestFormatResultsStep:
    def test_step_disabled_returns_disabled_message(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=False)
        state = _make_state(sql_query=_SAMPLE_QUERY, results=[{"id": 1}])
        result = wf.format_results(state)
        assert "disabled" in result.get("answer", "").lower()

    def test_not_relevant_returns_sql_reason(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        state = _make_state(
            sql_query="NOT_RELEVANT",
            sql_reason="This is a people question, not data",
        )
        result = wf.format_results(state)
        assert result["answer"] == "This is a people question, not data"

    def test_not_relevant_default_reason(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        state = _make_state(sql_query="NOT_RELEVANT", sql_reason=None)
        result = wf.format_results(state)
        assert result["answer"] != ""

    def test_empty_results_returns_no_results(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        state = _make_state(sql_query=_SAMPLE_QUERY, results=[])
        result = wf.format_results(state)
        assert "no results" in result.get("answer", "").lower()

    def test_exception_returns_error_message(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        wf.llm_manager.invoke_with_structured_output = MagicMock(
            side_effect=RuntimeError("LLM crashed")
        )
        state = _make_state(
            sql_query=_SAMPLE_QUERY,
            results=[{"revenue": 1000}],
        )
        result = wf.format_results(state)
        assert "error" in result.get("answer", "").lower()


# ---------------------------------------------------------------------------
# choose_and_format_visualization step - early exits
# ---------------------------------------------------------------------------


class TestChooseAndFormatVisualizationStep:
    def test_step_disabled_returns_none(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=False)
        state = _make_state(sql_query=_SAMPLE_QUERY, results=[{"id": 1}])
        result = wf.choose_and_format_visualization(state)
        assert result["visualization"] == "none"
        assert result["chart_data"] is None

    def test_empty_results_returns_none(self):
        wf = _make_workflow()
        wf.config.is_step_enabled = MagicMock(return_value=True)
        state = _make_state(sql_query=_SAMPLE_QUERY, results=[])
        result = wf.choose_and_format_visualization(state)
        assert result["visualization"] == "none"


# ---------------------------------------------------------------------------
# generate_followup_questions step - early exits
# ---------------------------------------------------------------------------


class TestGenerateFollowupQuestionsStep:
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
# _track_step and _complete_step
# ---------------------------------------------------------------------------


class TestTrackAndCompleteStep:
    def test_track_step_returns_step_name(self):
        wf = _make_workflow()
        result = wf._track_step("parse_question")
        assert result == "parse_question"

    def test_track_step_with_progress_callback(self):
        wf = _make_workflow()
        events = []
        wf.progress_callback = events.append
        wf._track_step("parse_question")
        assert len(events) == 1

    def test_complete_step_with_progress_callback(self):
        wf = _make_workflow()
        events = []
        wf.progress_callback = events.append
        wf._complete_step("parse_question")
        assert len(events) == 1
        from askrita.sqlagent.progress_tracker import ProgressStatus

        assert events[0].status == ProgressStatus.COMPLETED

    def test_complete_step_with_error(self):
        wf = _make_workflow()
        events = []
        wf.progress_callback = events.append
        wf._complete_step("parse_question", error="something failed")
        from askrita.sqlagent.progress_tracker import ProgressStatus

        assert events[0].status == ProgressStatus.FAILED

    def test_track_step_with_tracker(self):
        wf = _make_workflow()
        tracker = MagicMock()
        tracker.enabled = True
        wf._cot_tracker = tracker
        wf._track_step("generate_sql", details={"question": "What is revenue?"})
        tracker.start_step.assert_called_once()

    def test_complete_step_with_tracker(self):
        wf = _make_workflow()
        tracker = MagicMock()
        tracker.enabled = True
        tracker.steps = []
        wf._cot_tracker = tracker
        wf._complete_step("parse_question")
        tracker.complete_current_step.assert_called_once()


# ---------------------------------------------------------------------------
# _summarize_conversation_context
# ---------------------------------------------------------------------------


class TestSummarizeConversationContext:
    def test_single_message_returns_empty(self):
        wf = _make_workflow()
        messages = [{"role": "user", "content": _REVENUE_QUESTION}]
        result = wf._summarize_conversation_context(messages)
        assert result == ""

    def test_multi_message_returns_context(self):
        wf = _make_workflow()
        wf.config.get_conversation_context_settings = MagicMock(
            return_value={"max_history_messages": 6}
        )
        messages = [
            {"role": "user", "content": "Show me sales"},
            {"role": "assistant", "content": "Here are the sales numbers"},
            {"role": "user", "content": _REVENUE_QUESTION},
        ]
        result = wf._summarize_conversation_context(messages)
        assert isinstance(result, str)

    def test_sales_keyword_detected(self):
        wf = _make_workflow()
        wf.config.get_conversation_context_settings = MagicMock(
            return_value={"max_history_messages": 6}
        )
        messages = [
            {"role": "user", "content": "show me something"},
            {"role": "assistant", "content": "Your sales by region are..."},
            {"role": "user", "content": "more detail"},
        ]
        result = wf._summarize_conversation_context(messages)
        assert "sales" in result.lower()


# ---------------------------------------------------------------------------
# get_graph
# ---------------------------------------------------------------------------


class TestGetGraph:
    def test_get_graph_returns_compiled(self):
        wf = _make_workflow()
        result = wf.get_graph()
        assert result is wf._compiled_graph
