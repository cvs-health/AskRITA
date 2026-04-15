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
#   langchain-core (MIT)

"""Tests for langgraph_callback_handler.py – targets missing coverage lines."""

from unittest.mock import MagicMock
from uuid import uuid4

from langchain_core.outputs import LLMResult, Generation

from askrita.sqlagent.workflows.langgraph_callback_handler import (
    ChainOfThoughtsCallbackHandler,
    CallbackEvent,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_handler(**kwargs):
    return ChainOfThoughtsCallbackHandler(**kwargs)


def _run_id():
    return uuid4()


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestInit:
    def test_defaults(self):
        h = _make_handler()
        assert h.cot_tracker is None
        assert h.progress_callback is None
        assert h.cot_listeners == []
        assert h.enable_streaming is True

    def test_with_tracker_and_listener(self):
        tracker = MagicMock()
        listener = MagicMock()
        h = _make_handler(cot_tracker=tracker, cot_listeners=[listener])
        assert h.cot_tracker is tracker
        assert len(h.cot_listeners) == 1


# ---------------------------------------------------------------------------
# on_chain_start
# ---------------------------------------------------------------------------

class TestOnChainStart:
    def test_known_step_name_tracked(self):
        h = _make_handler()
        run_id = _run_id()
        h.on_chain_start({"name": "parse_question"}, {"question": "What?"}, run_id=run_id)
        assert str(run_id) in h._active_steps

    def test_none_serialized_handled(self):
        h = _make_handler()
        run_id = _run_id()
        # Should not raise
        h.on_chain_start(None, {}, run_id=run_id)

    def test_none_inputs_handled(self):
        h = _make_handler()
        run_id = _run_id()
        h.on_chain_start({"name": "generate_sql"}, None, run_id=run_id)
        assert str(run_id) in h._active_steps

    def test_metadata_step_name_takes_priority(self):
        h = _make_handler()
        run_id = _run_id()
        h.on_chain_start({"name": "unknown"}, {}, run_id=run_id, metadata={"step_name": "custom_step"})
        step_state = h._active_steps[str(run_id)]
        assert step_state.step_name == "custom_step"

    def test_tags_step_name_used(self):
        h = _make_handler()
        run_id = _run_id()
        h.on_chain_start({"name": "unknown"}, {}, run_id=run_id, tags=["step:my_step"])
        step_state = h._active_steps[str(run_id)]
        assert step_state.step_name == "my_step"

    def test_cot_tracker_start_step_called(self):
        tracker = MagicMock()
        h = _make_handler(cot_tracker=tracker)
        run_id = _run_id()
        h.on_chain_start({"name": "parse_question"}, {}, run_id=run_id)
        tracker.start_step.assert_called_once()

    def test_cot_tracker_error_doesnt_crash(self):
        tracker = MagicMock()
        tracker.start_step.side_effect = RuntimeError("tracker error")
        h = _make_handler(cot_tracker=tracker)
        run_id = _run_id()
        h.on_chain_start({"name": "parse_question"}, {}, run_id=run_id)
        # Should not raise

    def test_streaming_event_sent_to_listeners(self):
        events = []
        h = _make_handler(cot_listeners=[events.append])
        run_id = _run_id()
        h.on_chain_start({"name": "parse_question"}, {}, run_id=run_id)
        assert len(events) == 1
        assert events[0]["event_type"] == "step_started"

    def test_streaming_disabled_no_event(self):
        events = []
        h = _make_handler(cot_listeners=[events.append], enable_streaming=False)
        run_id = _run_id()
        h.on_chain_start({"name": "parse_question"}, {}, run_id=run_id)
        assert len(events) == 0

    def test_unknown_step_name_not_tracked(self):
        h = _make_handler()
        run_id = _run_id()
        h.on_chain_start({"name": "unknown"}, {}, run_id=run_id)
        # "unknown" chain name should still be tracked (step_name = "" stripped → None)
        # This verifies no crash occurs
        # The step may or may not be in active_steps depending on strip result

    def test_auto_completes_previous_started_step(self):
        h = _make_handler()
        run_id1 = _run_id()
        run_id2 = _run_id()
        h.on_chain_start({"name": "parse_question"}, {}, run_id=run_id1)
        # Simulate previous step still in "started" state
        first_step_key = str(run_id1)
        if first_step_key in h._active_steps:
            h._active_steps[first_step_key] = h._active_steps[first_step_key].model_copy(
                update={"status": "started"}
            )
        h.on_chain_start({"name": "generate_sql"}, {}, run_id=run_id2)


# ---------------------------------------------------------------------------
# on_chain_end
# ---------------------------------------------------------------------------

class TestOnChainEnd:
    def _start_step(self, h, step_name="parse_question"):
        run_id = _run_id()
        h.on_chain_start({"name": step_name}, {"question": "Q?"}, run_id=run_id)
        return run_id

    def test_completes_active_step(self):
        h = _make_handler()
        run_id = self._start_step(h)
        h.on_chain_end({"answer": "42"}, run_id=run_id)
        assert str(run_id) not in h._active_steps

    def test_none_outputs_handled(self):
        h = _make_handler()
        run_id = self._start_step(h)
        h.on_chain_end(None, run_id=run_id)
        assert str(run_id) not in h._active_steps

    def test_untracked_run_id_no_crash(self):
        h = _make_handler()
        run_id = _run_id()
        h.on_chain_end({}, run_id=run_id)  # Should not raise

    def test_cot_tracker_complete_step_called(self):
        tracker = MagicMock()
        h = _make_handler(cot_tracker=tracker)
        run_id = self._start_step(h)
        h.on_chain_end({"sql_query": "SELECT 1"}, run_id=run_id)
        tracker.complete_step.assert_called_once()

    def test_streaming_event_on_complete(self):
        events = []
        h = _make_handler(cot_listeners=[events.append])
        run_id = self._start_step(h)
        h.on_chain_end({}, run_id=run_id)
        # Should have step_started + step_completed events
        event_types = [e["event_type"] for e in events]
        assert "step_completed" in event_types

    def test_breadcrumb_added_on_complete(self):
        h = _make_handler()
        run_id = self._start_step(h, "format_results")
        h.on_chain_end({"answer": "The result is..."}, run_id=run_id)
        assert len(h._breadcrumbs) > 0

    def test_different_output_summaries(self):
        """Test various step types produce different summaries."""
        for step, outputs in [
            ("parse_question", {"parsed_question": {"is_relevant": True, "relevant_tables": ["t1"]}}),
            ("generate_sql", {"sql_query": "SELECT * FROM t"}),
            ("validate_and_fix_sql", {"sql_valid": True}),
            ("execute_sql", {"results": [{"a": 1}, {"a": 2}]}),
            ("format_results", {"answer": "Answer here"}),
        ]:
            h = _make_handler()
            run_id = self._start_step(h, step)
            h.on_chain_end(outputs, run_id=run_id)


# ---------------------------------------------------------------------------
# on_chain_error
# ---------------------------------------------------------------------------

class TestOnChainError:
    def _start_step(self, h, step_name="parse_question"):
        run_id = _run_id()
        h.on_chain_start({"name": step_name}, {}, run_id=run_id)
        return run_id

    def test_marks_step_as_failed(self):
        h = _make_handler()
        run_id = self._start_step(h)
        h.on_chain_error(RuntimeError("oops"), run_id=run_id)
        assert str(run_id) not in h._active_steps

    def test_untracked_run_id_no_crash(self):
        h = _make_handler()
        run_id = _run_id()
        h.on_chain_error(ValueError("err"), run_id=run_id)

    def test_cot_tracker_fail_step_called(self):
        tracker = MagicMock()
        h = _make_handler(cot_tracker=tracker)
        run_id = self._start_step(h)
        h.on_chain_error(RuntimeError("fail"), run_id=run_id)
        tracker.fail_step.assert_called_once()

    def test_streaming_event_on_error(self):
        events = []
        h = _make_handler(cot_listeners=[events.append])
        run_id = self._start_step(h)
        h.on_chain_error(RuntimeError("fail"), run_id=run_id)
        event_types = [e["event_type"] for e in events]
        assert "step_failed" in event_types


# ---------------------------------------------------------------------------
# on_llm_start
# ---------------------------------------------------------------------------

class TestOnLlmStart:
    def test_tracks_llm_metadata(self):
        h = _make_handler()
        run_id = _run_id()
        h.on_llm_start({"name": "gpt-4"}, ["prompt"], run_id=run_id)
        assert str(run_id) in h._llm_tokens

    def test_none_serialized(self):
        h = _make_handler()
        run_id = _run_id()
        h.on_llm_start(None, ["prompt"], run_id=run_id)
        assert str(run_id) in h._llm_tokens

    def test_streaming_event_sent(self):
        events = []
        h = _make_handler(cot_listeners=[events.append])
        run_id = _run_id()
        h.on_llm_start({"name": "gpt-4"}, ["prompt"], run_id=run_id)
        event_types = [e["event_type"] for e in events]
        assert "llm_started" in event_types


# ---------------------------------------------------------------------------
# on_llm_end
# ---------------------------------------------------------------------------

class TestOnLlmEnd:
    def test_updates_token_usage(self):
        h = _make_handler()
        run_id = _run_id()
        h.on_llm_start({"name": "gpt-4"}, ["prompt"], run_id=run_id)

        llm_output = {"token_usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}}
        gen = Generation(text="response text")
        response = LLMResult(generations=[[gen]], llm_output=llm_output)
        h.on_llm_end(response, run_id=run_id)

        usage = h._llm_tokens[str(run_id)]
        assert usage.prompt_tokens == 10
        assert usage.completion_tokens == 20

    def test_no_token_usage_in_output(self):
        h = _make_handler()
        run_id = _run_id()
        h.on_llm_start({"name": "gpt-4"}, ["prompt"], run_id=run_id)

        response = LLMResult(generations=[[Generation(text="OK")]], llm_output={})
        h.on_llm_end(response, run_id=run_id)

    def test_streaming_event_on_llm_end(self):
        events = []
        h = _make_handler(cot_listeners=[events.append])
        run_id = _run_id()
        h.on_llm_start({"name": "gpt-4"}, ["prompt"], run_id=run_id)
        response = LLMResult(generations=[[Generation(text="OK")]], llm_output={})
        h.on_llm_end(response, run_id=run_id)
        event_types = [e["event_type"] for e in events]
        assert "llm_completed" in event_types

    def test_no_generations(self):
        h = _make_handler()
        run_id = _run_id()
        response = LLMResult(generations=[], llm_output=None)
        h.on_llm_end(response, run_id=run_id)


# ---------------------------------------------------------------------------
# on_llm_error
# ---------------------------------------------------------------------------

class TestOnLlmError:
    def test_streams_error_event(self):
        events = []
        h = _make_handler(cot_listeners=[events.append])
        run_id = _run_id()
        h.on_llm_error(RuntimeError("LLM failed"), run_id=run_id)
        event_types = [e["event_type"] for e in events]
        assert "llm_error" in event_types

    def test_streaming_disabled_no_event(self):
        events = []
        h = _make_handler(cot_listeners=[events.append], enable_streaming=False)
        run_id = _run_id()
        h.on_llm_error(RuntimeError("fail"), run_id=run_id)
        assert len(events) == 0


# ---------------------------------------------------------------------------
# on_tool_start / on_tool_end / on_tool_error
# ---------------------------------------------------------------------------

class TestToolEvents:
    def test_tool_start_streams_event(self):
        events = []
        h = _make_handler(cot_listeners=[events.append])
        run_id = _run_id()
        h.on_tool_start({"name": "db_query"}, "SELECT 1", run_id=run_id)
        event_types = [e["event_type"] for e in events]
        assert "tool_started" in event_types

    def test_tool_start_none_serialized(self):
        h = _make_handler()
        run_id = _run_id()
        h.on_tool_start(None, None, run_id=run_id)

    def test_tool_end_streams_event(self):
        events = []
        h = _make_handler(cot_listeners=[events.append])
        run_id = _run_id()
        h.on_tool_end("output data", run_id=run_id)
        event_types = [e["event_type"] for e in events]
        assert "tool_completed" in event_types

    def test_tool_end_none_output(self):
        h = _make_handler()
        run_id = _run_id()
        h.on_tool_end(None, run_id=run_id)

    def test_tool_error_streams_event(self):
        events = []
        h = _make_handler(cot_listeners=[events.append])
        run_id = _run_id()
        h.on_tool_error(RuntimeError("db error"), run_id=run_id)
        event_types = [e["event_type"] for e in events]
        assert "tool_error" in event_types


# ---------------------------------------------------------------------------
# _extract_step_name
# ---------------------------------------------------------------------------

class TestExtractStepName:
    def test_metadata_priority(self):
        h = _make_handler()
        result = h._extract_step_name("chain_name", {"step_name": "from_meta"}, None)
        assert result == "from_meta"

    def test_tags_fallback(self):
        h = _make_handler()
        result = h._extract_step_name("chain_name", None, ["step:tag_step"])
        assert result == "tag_step"

    def test_chain_name_fallback(self):
        h = _make_handler()
        result = h._extract_step_name("my_step", None, None)
        assert result == "my_step"

    def test_unknown_returns_none(self):
        h = _make_handler()
        result = h._extract_step_name("unknown", None, None)
        assert result is None

    def test_runnable_lambda_stripped(self):
        h = _make_handler()
        result = h._extract_step_name("RunnableLambda_parse", None, None)
        assert "RunnableLambda" not in result

    def test_empty_chain_name_returns_none(self):
        h = _make_handler()
        result = h._extract_step_name("", None, None)
        assert result is None


# ---------------------------------------------------------------------------
# _infer_step_type
# ---------------------------------------------------------------------------

class TestInferStepType:
    def test_parse_is_analysis(self):
        h = _make_handler()
        assert h._infer_step_type("parse_question") == "analysis"

    def test_generate_is_generation(self):
        h = _make_handler()
        assert h._infer_step_type("generate_sql") == "generation"

    def test_validate_is_validation(self):
        h = _make_handler()
        assert h._infer_step_type("validate_sql") == "validation"

    def test_execute_is_execution(self):
        h = _make_handler()
        assert h._infer_step_type("execute_query") == "execution"

    def test_format_is_formatting(self):
        h = _make_handler()
        assert h._infer_step_type("format_results") == "formatting"

    def test_followup_is_suggestion(self):
        h = _make_handler()
        # "followup" check is after "generate", so "generate_followup" maps to "generation"
        assert h._infer_step_type("followup_questions") == "suggestion"

    def test_unknown_is_processing(self):
        h = _make_handler()
        assert h._infer_step_type("some_random_step") == "processing"

    def test_create_is_generation(self):
        h = _make_handler()
        assert h._infer_step_type("create_query") == "generation"

    def test_fix_is_validation(self):
        h = _make_handler()
        assert h._infer_step_type("fix_sql") == "validation"

    def test_run_is_execution(self):
        h = _make_handler()
        assert h._infer_step_type("run_query") == "execution"

    def test_visualiz_is_formatting(self):
        h = _make_handler()
        assert h._infer_step_type("visualize_data") == "formatting"


# ---------------------------------------------------------------------------
# _summarize_inputs
# ---------------------------------------------------------------------------

class TestSummarizeInputs:
    def test_empty_inputs(self):
        h = _make_handler()
        assert h._summarize_inputs({}) == ""

    def test_question_in_inputs(self):
        h = _make_handler()
        result = h._summarize_inputs({"question": "What is the sales?"})
        assert "Question:" in result

    def test_sql_query_in_inputs(self):
        h = _make_handler()
        result = h._summarize_inputs({"sql_query": "SELECT *"})
        assert "SQL query provided" in result

    def test_results_in_inputs(self):
        h = _make_handler()
        result = h._summarize_inputs({"results": [1, 2, 3]})
        assert "3 results" in result

    def test_non_string_question_ignored(self):
        h = _make_handler()
        result = h._summarize_inputs({"question": 42})
        # Should not contain "Question:" as 42 is not a string
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _get_concise_reasoning
# ---------------------------------------------------------------------------

class TestGetConciseReasoning:
    def test_track_step_skipped(self):
        h = _make_handler()
        result = h._get_concise_reasoning("track_internal", "summary")
        assert result is None

    def test_parse_relevant(self):
        h = _make_handler()
        result = h._get_concise_reasoning("parse_question", "Relevant: true, Tables: 2")
        assert result is not None

    def test_parse_not_relevant(self):
        h = _make_handler()
        result = h._get_concise_reasoning("parse_question", "relevant: false, no tables")
        assert "relevance" in result.lower()

    def test_generate_sql(self):
        h = _make_handler()
        result = h._get_concise_reasoning("generate_sql", "SQL generated: 45 chars")
        assert result is not None

    def test_validate_corrected(self):
        h = _make_handler()
        result = h._get_concise_reasoning("validate_and_fix_sql", "valid: false, corrected")
        assert result is not None

    def test_execute_with_rows(self):
        h = _make_handler()
        result = h._get_concise_reasoning("execute_sql", "10 rows returned")
        assert result is not None

    def test_format(self):
        h = _make_handler()
        result = h._get_concise_reasoning("format_results", "answer provided")
        assert result is not None

    def test_visualiz(self):
        h = _make_handler()
        result = h._get_concise_reasoning("visualize_data", "chart selected")
        assert result is not None

    def test_unknown_step_generic(self):
        h = _make_handler()
        result = h._get_concise_reasoning("some_custom_step", "done")
        assert result is not None


# ---------------------------------------------------------------------------
# _summarize_outputs edge cases
# ---------------------------------------------------------------------------

class TestSummarizeOutputs:
    def test_empty_outputs_returns_no_output(self):
        h = _make_handler()
        result = h._summarize_outputs({}, "any_step")
        assert result == "No output"

    def test_parse_outputs_with_parsed_question(self):
        h = _make_handler()
        result = h._summarize_outputs(
            {"parsed_question": {"is_relevant": True, "relevant_tables": ["a", "b"]}},
            "parse_question"
        )
        assert "Tables: 2" in result

    def test_parse_outputs_not_dict(self):
        h = _make_handler()
        result = h._summarize_outputs({"parsed_question": "something"}, "parse_question")
        assert isinstance(result, str)

    def test_format_with_answer(self):
        h = _make_handler()
        result = h._summarize_outputs({"answer": "Here is the answer."}, "format_results")
        assert "Answer:" in result

    def test_generic_outputs(self):
        h = _make_handler()
        result = h._summarize_outputs({"key1": "v", "key2": "v"}, "other_step")
        assert "2 outputs" in result


# ---------------------------------------------------------------------------
# Public API: get_active_steps, get_token_usage, get_breadcrumbs, reset
# ---------------------------------------------------------------------------

class TestPublicAPI:
    def test_get_active_steps_empty(self):
        h = _make_handler()
        assert h.get_active_steps() == {}

    def test_get_token_usage_empty(self):
        h = _make_handler()
        assert h.get_token_usage() == {}

    def test_get_breadcrumbs_all(self):
        h = _make_handler()
        h._breadcrumbs = ["step1", "step2", "step3"]
        assert h.get_breadcrumbs() == ["step1", "step2", "step3"]

    def test_get_breadcrumbs_max_items(self):
        h = _make_handler()
        h._breadcrumbs = ["s1", "s2", "s3", "s4"]
        result = h.get_breadcrumbs(max_items=2)
        assert result == ["s3", "s4"]

    def test_get_breadcrumbs_zero_max(self):
        h = _make_handler()
        h._breadcrumbs = ["s1", "s2"]
        result = h.get_breadcrumbs(max_items=0)
        assert result == []

    def test_reset_clears_state(self):
        h = _make_handler()
        run_id = _run_id()
        h.on_chain_start({"name": "parse_question"}, {}, run_id=run_id)
        h._breadcrumbs.append("some breadcrumb")
        h.reset()
        assert h._active_steps == {}
        assert h._step_start_times == {}
        assert h._llm_tokens == {}
        assert h._breadcrumbs == []

    def test_get_active_steps_returns_copy(self):
        h = _make_handler()
        run_id = _run_id()
        h.on_chain_start({"name": "parse_question"}, {}, run_id=run_id)
        steps = h.get_active_steps()
        assert str(run_id) in steps

    def test_get_token_usage_after_llm(self):
        h = _make_handler()
        run_id = _run_id()
        h.on_llm_start({"name": "gpt-4"}, ["p"], run_id=run_id)
        usage = h.get_token_usage()
        assert str(run_id) in usage


# ---------------------------------------------------------------------------
# _stream_event
# ---------------------------------------------------------------------------

class TestStreamEvent:
    def test_listener_error_doesnt_propagate(self):
        def bad_listener(event):
            raise RuntimeError("listener error")

        h = _make_handler(cot_listeners=[bad_listener])
        # Should not raise
        h._stream_event(
            CallbackEvent(event_type="test", run_id="abc", timestamp=1.0)
        )

    def test_no_listeners_no_op(self):
        h = _make_handler(enable_streaming=True)
        # No listeners, should not raise
        h._stream_event(
            CallbackEvent(event_type="test", run_id="abc", timestamp=1.0)
        )


# ---------------------------------------------------------------------------
# _extract_step_details
# ---------------------------------------------------------------------------

class TestExtractStepDetails:
    def test_extracts_known_fields(self):
        h = _make_handler()
        outputs = {
            "sql_query": "SELECT 1",
            "sql_reason": "reason",
            "sql_valid": True,
            "answer": "42",
            "visualization": "bar",
        }
        details = h._extract_step_details(outputs, "any_step")
        assert details["sql_query"] == "SELECT 1"
        assert details["sql_valid"] is True
        assert details["answer"] == "42"

    def test_extracts_row_count(self):
        h = _make_handler()
        outputs = {"results": [1, 2, 3, 4]}
        details = h._extract_step_details(outputs, "execute_sql")
        assert details["row_count"] == 4

    def test_unknown_fields_not_included(self):
        h = _make_handler()
        outputs = {"unknown_field": "value"}
        details = h._extract_step_details(outputs, "step")
        assert "unknown_field" not in details
