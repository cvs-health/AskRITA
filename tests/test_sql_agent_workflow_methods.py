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

"""Tests for SQLAgentWorkflow helper methods (no live LLM/DB needed)."""

import os
from unittest.mock import MagicMock, patch

import pytest

from askrita.sqlagent.workflows.SQLAgentWorkflow import SQLAgentWorkflow

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

    with patch(
        "askrita.sqlagent.workflows.SQLAgentWorkflow.LLMManager", return_value=mock_llm
    ):
        with patch(
            "askrita.sqlagent.workflows.SQLAgentWorkflow.DatabaseManager",
            return_value=mock_db_manager,
        ):
            with patch(
                "askrita.sqlagent.workflows.SQLAgentWorkflow.DataFormatter",
                return_value=mock_data_formatter,
            ):
                with patch(
                    "askrita.sqlagent.workflows.SQLAgentWorkflow.create_pii_detector",
                    return_value=None,
                ):
                    with patch(
                        "askrita.sqlagent.workflows.SQLAgentWorkflow.StateGraph"
                    ) as mock_sg:
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
    return workflow


# ---------------------------------------------------------------------------
# _get_database_type
# ---------------------------------------------------------------------------


class TestGetDatabaseType:
    def test_bigquery(self):
        wf = _make_workflow()
        wf.config.database.connection_string = "bigquery://project/dataset"
        result = wf._get_database_type()
        assert result == "bigquery"

    def test_snowflake(self):
        wf = _make_workflow()
        wf.config.database.connection_string = "snowflake://account/db"
        result = wf._get_database_type()
        assert result == "snowflake"

    def test_postgresql(self):
        wf = _make_workflow()
        wf.config.database.connection_string = "postgresql://user:pass@host/db"
        result = wf._get_database_type()
        assert result == "postgresql"

    def test_postgres(self):
        wf = _make_workflow()
        wf.config.database.connection_string = "postgres://user:pass@host/db"
        result = wf._get_database_type()
        assert result == "postgresql"

    def test_mysql(self):
        wf = _make_workflow()
        wf.config.database.connection_string = "mysql://user:pass@host/db"
        result = wf._get_database_type()
        assert result == "mysql"

    def test_mssql(self):
        wf = _make_workflow()
        wf.config.database.connection_string = "mssql://server/db"
        result = wf._get_database_type()
        assert result == "sqlserver"

    def test_sqlserver(self):
        wf = _make_workflow()
        wf.config.database.connection_string = "sqlserver://server/db"
        result = wf._get_database_type()
        assert result == "sqlserver"

    def test_db2(self):
        wf = _make_workflow()
        wf.config.database.connection_string = "db2://host/db"
        result = wf._get_database_type()
        assert result == "db2"

    def test_ibm_db_sa(self):
        wf = _make_workflow()
        wf.config.database.connection_string = "ibm_db_sa://user:pass@host/db"
        result = wf._get_database_type()
        assert result == "db2"

    def test_unknown(self):
        wf = _make_workflow()
        wf.config.database.connection_string = "sqlite:///./test.db"
        result = wf._get_database_type()
        assert result == "unknown"

    def test_non_string_returns_unknown(self):
        wf = _make_workflow()
        wf.config.database.connection_string = MagicMock()
        result = wf._get_database_type()
        assert result == "unknown"


# ---------------------------------------------------------------------------
# _get_cast_to_string_syntax
# ---------------------------------------------------------------------------


class TestGetCastToStringSyntax:
    def test_explicit_config_cast_type(self):
        wf = _make_workflow()
        wf.config.database.sql_syntax.cast_to_string = "NVARCHAR(MAX)"
        result = wf._get_cast_to_string_syntax("my_col")
        assert result == "CAST(my_col AS NVARCHAR(MAX))"

    def test_default_bigquery_cast(self):
        wf = _make_workflow()
        wf.config.database.sql_syntax.cast_to_string = None
        wf._db_type = "bigquery"
        result = wf._get_cast_to_string_syntax("my_col")
        assert result == "CAST(my_col AS STRING)"

    def test_default_postgresql_cast(self):
        wf = _make_workflow()
        wf.config.database.sql_syntax.cast_to_string = None
        wf._db_type = "postgresql"
        result = wf._get_cast_to_string_syntax("my_col")
        assert result == "CAST(my_col AS TEXT)"

    def test_fallback_varchar_for_unknown_db(self):
        wf = _make_workflow()
        wf.config.database.sql_syntax.cast_to_string = None
        wf._db_type = "unknown_db_type"
        result = wf._get_cast_to_string_syntax("my_col")
        assert result == "CAST(my_col AS VARCHAR)"


# ---------------------------------------------------------------------------
# _track_step and _complete_step
# ---------------------------------------------------------------------------


class TestTrackStep:
    def test_track_step_no_tracker_no_crash(self):
        wf = _make_workflow()
        wf._cot_tracker = None
        wf._reasoning_templates = {}
        result = wf._track_step("parse_question")
        assert result == "parse_question"

    def test_track_step_with_tracker(self):
        wf = _make_workflow()
        tracker = MagicMock()
        tracker.enabled = True
        wf._cot_tracker = tracker
        wf._reasoning_templates = {}
        wf._track_step("generate_sql", details={"question": "What is the revenue?"})
        tracker.start_step.assert_called_once()

    def test_track_step_with_step_inputs(self):
        wf = _make_workflow()
        tracker = MagicMock()
        tracker.enabled = True
        wf._cot_tracker = tracker
        wf._reasoning_templates = {}
        wf._track_step("execute_sql", details={"step_inputs": {"sql": "SELECT 1"}})
        tracker.start_step.assert_called_once()

    def test_track_step_with_progress_callback(self):
        wf = _make_workflow()
        events = []
        wf.progress_callback = events.append
        wf._cot_tracker = None
        wf._reasoning_templates = {}
        wf._track_step("parse_question")
        assert len(events) == 1

    def test_track_step_progress_callback_error_ignored(self):
        wf = _make_workflow()

        def bad_cb(data):
            raise RuntimeError("callback error")

        wf.progress_callback = bad_cb
        wf._cot_tracker = None
        wf._reasoning_templates = {}
        wf._track_step("parse_question")  # Should not raise

    def test_track_step_tracker_error_ignored(self):
        wf = _make_workflow()
        tracker = MagicMock()
        tracker.enabled = True
        tracker.start_step.side_effect = RuntimeError("tracker error")
        wf._cot_tracker = tracker
        wf._reasoning_templates = {}
        wf._track_step("parse_question")  # Should not raise


class TestCompleteStep:
    def test_complete_step_no_tracker_no_crash(self):
        wf = _make_workflow()
        wf._cot_tracker = None
        wf._reasoning_templates = {}
        wf._complete_step("parse_question")  # Should not raise

    def test_complete_step_with_error(self):
        wf = _make_workflow()
        tracker = MagicMock()
        tracker.enabled = True
        tracker.steps = []
        wf._cot_tracker = tracker
        wf._reasoning_templates = {}
        wf._complete_step("parse_question", error="failed")
        tracker.complete_current_step.assert_called_once()
        call_kwargs = tracker.complete_current_step.call_args[1]
        assert call_kwargs["confidence_score"] == 0.0
        assert call_kwargs["error_message"] == "failed"

    def test_complete_step_success(self):
        wf = _make_workflow()
        tracker = MagicMock()
        tracker.enabled = True
        tracker.steps = []
        wf._cot_tracker = tracker
        wf._reasoning_templates = {}
        wf._complete_step("parse_question", details={"answer": "result"})
        call_kwargs = tracker.complete_current_step.call_args[1]
        assert call_kwargs["confidence_score"] == 0.9

    def test_complete_step_with_output_in_details(self):
        wf = _make_workflow()
        tracker = MagicMock()
        tracker.enabled = True
        tracker.steps = []
        wf._cot_tracker = tracker
        wf._reasoning_templates = {}
        wf._complete_step("parse_question", details={"output": "some output"})
        call_kwargs = tracker.complete_current_step.call_args[1]
        assert "some output" in call_kwargs["output_summary"]

    def test_complete_step_with_answer_preview(self):
        wf = _make_workflow()
        tracker = MagicMock()
        tracker.enabled = True
        tracker.steps = []
        wf._cot_tracker = tracker
        wf._reasoning_templates = {}
        wf._complete_step("format_results", details={"answer_preview": "Preview text"})
        call_kwargs = tracker.complete_current_step.call_args[1]
        assert "Preview text" in call_kwargs["output_summary"]

    def test_complete_step_with_progress_callback(self):
        wf = _make_workflow()
        events = []
        wf.progress_callback = events.append
        wf._cot_tracker = None
        wf._reasoning_templates = {}
        wf._complete_step("parse_question")
        assert len(events) == 1
        from askrita.sqlagent.progress_tracker import ProgressStatus

        assert events[0].status == ProgressStatus.COMPLETED

    def test_complete_step_error_progress_callback(self):
        wf = _make_workflow()
        events = []
        wf.progress_callback = events.append
        wf._cot_tracker = None
        wf._reasoning_templates = {}
        wf._complete_step("parse_question", error="something failed")
        from askrita.sqlagent.progress_tracker import ProgressStatus

        assert events[0].status == ProgressStatus.FAILED


# ---------------------------------------------------------------------------
# _notify_cot_listeners
# ---------------------------------------------------------------------------


class TestNotifyCotListeners:
    def test_no_listeners_no_crash(self):
        wf = _make_workflow()
        wf._cot_listeners = []
        wf._notify_cot_listeners({"event_type": "test"})

    def test_listeners_called(self):
        wf = _make_workflow()
        events = []
        wf._cot_listeners = [events.append]
        wf._notify_cot_listeners({"event_type": "step_done"})
        assert len(events) == 1
        assert events[0]["event_type"] == "step_done"

    def test_listener_error_doesnt_stop_others(self):
        wf = _make_workflow()
        good_events = []

        def bad_listener(e):
            raise RuntimeError("bad")

        wf._cot_listeners = [bad_listener, good_events.append]
        wf._notify_cot_listeners({"event_type": "test"})
        assert len(good_events) == 1


# ---------------------------------------------------------------------------
# register/unregister/clear CoT listeners
# ---------------------------------------------------------------------------


class TestCotListenerManagement:
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
# _finalize_cot
# ---------------------------------------------------------------------------


class TestFinalizeCot:
    def test_no_tracker_returns_none(self):
        wf = _make_workflow()
        wf._cot_tracker = None
        result = wf._finalize_cot(True, "final answer")
        assert result is None

    def test_disabled_tracker_returns_none(self):
        wf = _make_workflow()
        tracker = MagicMock()
        tracker.enabled = False
        wf._cot_tracker = tracker
        result = wf._finalize_cot(True, "final answer")
        assert result is None

    def test_enabled_tracker_finalizes(self):
        wf = _make_workflow()
        tracker = MagicMock()
        tracker.enabled = True
        tracker.get_summary.return_value = {"steps": []}
        tracker.get_detailed_chain.return_value = []
        tracker.workflow_id = "wf-123"
        wf._cot_tracker = tracker
        wf._cot_listeners = []
        result = wf._finalize_cot(True, "answer")
        tracker.finalize_workflow.assert_called_once_with(
            success=True, final_answer="answer"
        )
        assert result is not None
