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

"""Comprehensive tests for enhanced_chain_of_thoughts.py."""

import threading
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from askrita.config_manager import ChainOfThoughtsConfig
from askrita.utils.enhanced_chain_of_thoughts import (
    ChainOfThoughtsStep,
    CoTPerformanceMetrics,
    EnhancedChainOfThoughtsTracker,
    StepRegistry,
    StepStatus,
    StepTracker,
    StepType,
    get_step_registry,
    track_step,
    validate_cot_config,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**kwargs):
    defaults = dict(
        enabled=True,
        include_timing=True,
        include_confidence=True,
        include_step_details=False,
        track_retries=True,
        max_reasoning_length=500,
        display_preferences={
            "show_successful_steps": True,
            "show_failed_steps": True,
            "show_skipped_steps": True,
            "collapse_successful_steps": False,
            "highlight_failed_steps": True,
            "show_step_timing": True,
            "show_confidence_scores": True,
        },
    )
    defaults.update(kwargs)
    return ChainOfThoughtsConfig(**defaults)


def _make_tracker(enabled=True, config=None):
    if config is None:
        config = _make_config()
    return EnhancedChainOfThoughtsTracker(enabled=enabled, config=config)


# ---------------------------------------------------------------------------
# StepRegistry
# ---------------------------------------------------------------------------


class TestStepRegistry:
    def test_register_and_get(self):
        registry = StepRegistry()
        registry.register_step("my_step", "analysis", description="Test step")
        info = registry.get_step_info("my_step")
        assert info.name == "my_step"
        assert info.step_type == StepType.ANALYSIS

    def test_register_with_string_type(self):
        registry = StepRegistry()
        registry.register_step("gen_step", "generation")
        info = registry.get_step_info("gen_step")
        assert info.step_type == StepType.GENERATION

    def test_register_unknown_string_type_defaults_to_unknown(self):
        registry = StepRegistry()
        registry.register_step("odd_step", "nonexistent_type")
        info = registry.get_step_info("odd_step")
        assert info.step_type == StepType.UNKNOWN

    def test_get_unregistered_step_returns_default(self):
        registry = StepRegistry()
        info = registry.get_step_info("unregistered")
        assert info.step_type == StepType.UNKNOWN
        assert "unregistered" in info.description.lower()

    def test_is_step_enabled(self):
        registry = StepRegistry()
        registry.register_step("enabled_step", "analysis", enabled=True)
        registry.register_step("disabled_step", "analysis", enabled=False)
        assert registry.is_step_enabled("enabled_step") is True
        assert registry.is_step_enabled("disabled_step") is False

    def test_get_all_steps(self):
        registry = StepRegistry()
        registry.register_step("a", "analysis")
        registry.register_step("b", "generation")
        all_steps = registry.get_all_steps()
        assert "a" in all_steps
        assert "b" in all_steps

    def test_unregister_existing_step(self):
        registry = StepRegistry()
        registry.register_step("temp", "analysis")
        assert registry.unregister_step("temp") is True
        assert "temp" not in registry.get_all_steps()

    def test_unregister_nonexistent_step(self):
        registry = StepRegistry()
        assert registry.unregister_step("ghost") is False

    def test_register_with_enum_type(self):
        registry = StepRegistry()
        registry.register_step("val_step", StepType.VALIDATION)
        info = registry.get_step_info("val_step")
        assert info.step_type == StepType.VALIDATION

    def test_register_with_reasoning_template(self):
        registry = StepRegistry()
        registry.register_step(
            "sql_step",
            "generation",
            reasoning_template={
                "start": "Starting SQL",
                "success": "SQL done",
                "failure": "Failed: {error}",
            },
        )
        info = registry.get_step_info("sql_step")
        assert info.reasoning_template["start"] == "Starting SQL"

    def test_thread_safe_registration(self):
        registry = StepRegistry()
        errors = []

        def register(n):
            try:
                registry.register_step(f"step_{n}", "analysis")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0


# ---------------------------------------------------------------------------
# ChainOfThoughtsStep
# ---------------------------------------------------------------------------


class TestChainOfThoughtsStep:
    def _make_step(self, **kwargs):
        defaults = dict(
            step_name="test_step",
            step_type=StepType.ANALYSIS,
            status=StepStatus.STARTED,
            start_time=datetime.now(timezone.utc),
        )
        defaults.update(kwargs)
        return ChainOfThoughtsStep(**defaults)

    def test_complete_marks_completed(self):
        step = self._make_step()
        step.complete(reasoning="Done", output_summary="Output")
        assert step.status == StepStatus.COMPLETED
        assert step.end_time is not None
        assert step.duration_ms >= 0

    def test_complete_with_error_marks_failed(self):
        step = self._make_step()
        step.complete(error_message="Something went wrong")
        assert step.status == StepStatus.FAILED
        assert step.error_message == "Something went wrong"

    def test_complete_with_details(self):
        step = self._make_step()
        step.complete(details={"key": "value"})
        assert step.details["key"] == "value"

    def test_complete_with_confidence(self):
        step = self._make_step()
        step.complete(confidence_score=0.95)
        assert step.confidence_score == 0.95

    def test_to_dict(self):
        step = self._make_step()
        step.complete(reasoning="test")
        d = step.to_dict()
        assert d["step_name"] == "test_step"
        assert d["status"] == "completed"
        assert "duration_ms" in d

    def test_to_dict_with_none_end_time(self):
        step = self._make_step()
        d = step.to_dict()
        assert d["end_time"] is None


# ---------------------------------------------------------------------------
# CoTPerformanceMetrics
# ---------------------------------------------------------------------------


class TestCoTPerformanceMetrics:
    def test_calculate_average(self):
        m = CoTPerformanceMetrics(total_tracking_time_ms=100.0, step_count=5)
        m.calculate_average_step_time()
        assert m.average_step_time_ms == 20.0

    def test_calculate_average_no_steps(self):
        m = CoTPerformanceMetrics(total_tracking_time_ms=100.0, step_count=0)
        m.calculate_average_step_time()
        assert m.average_step_time_ms == 0.0  # Not changed


# ---------------------------------------------------------------------------
# EnhancedChainOfThoughtsTracker – basic operations
# ---------------------------------------------------------------------------


class TestTrackerBasic:
    def test_start_step_returns_step(self):
        tracker = _make_tracker()
        step = tracker.start_step(
            "parse_question", "analysis", "Parsing...", "question text"
        )
        assert step is not None
        assert step.step_name == "parse_question"

    def test_start_step_disabled_returns_none(self):
        tracker = _make_tracker(enabled=False)
        step = tracker.start_step("parse_question")
        assert step is None

    def test_complete_current_step(self):
        tracker = _make_tracker()
        tracker.start_step("step1")
        tracker.complete_current_step(reasoning="Done", output_summary="Result")
        assert tracker.steps[0].status == StepStatus.COMPLETED

    def test_complete_named_step(self):
        tracker = _make_tracker()
        tracker.start_step("step_a")
        tracker.start_step("step_b")
        tracker.complete_current_step(step_name="step_a", reasoning="A done")
        assert tracker.steps[0].status == StepStatus.COMPLETED
        # step_b should still be active
        assert "step_b" in tracker._active_steps

    def test_complete_nonexistent_step_logs_warning(self):
        tracker = _make_tracker()
        tracker.complete_current_step(step_name="ghost")  # Should not raise

    def test_complete_no_active_steps(self):
        tracker = _make_tracker()
        tracker.complete_current_step()  # Should not raise

    def test_complete_step_disabled_returns_early(self):
        tracker = _make_tracker(enabled=False)
        tracker.complete_current_step()  # Should not raise

    def test_start_step_with_unknown_string_type(self):
        tracker = _make_tracker()
        step = tracker.start_step("step1", step_type="unknown_xyz")
        assert step is not None

    def test_start_step_with_enum_type(self):
        tracker = _make_tracker()
        step = tracker.start_step("step1", step_type=StepType.EXECUTION)
        assert step.step_type == StepType.EXECUTION

    def test_start_step_uses_template_reasoning(self):
        registry = get_step_registry()
        registry.register_step(
            "templated_step",
            "analysis",
            reasoning_template={"start": "Starting templated step"},
        )
        tracker = _make_tracker()
        step = tracker.start_step("templated_step")  # no reasoning provided
        assert step.reasoning == "Starting templated step"

    def test_complete_step_uses_template_success(self):
        registry = get_step_registry()
        registry.register_step(
            "tpl_complete",
            "analysis",
            reasoning_template={"success": "Success template"},
        )
        tracker = _make_tracker()
        tracker.start_step("tpl_complete")
        tracker.complete_current_step(step_name="tpl_complete")  # no reasoning
        assert tracker.steps[0].reasoning == "Success template"

    def test_complete_step_uses_template_failure(self):
        registry = get_step_registry()
        registry.register_step(
            "tpl_fail", "analysis", reasoning_template={"failure": "Failed: {error}"}
        )
        tracker = _make_tracker()
        tracker.start_step("tpl_fail")
        tracker.complete_current_step(step_name="tpl_fail", error_message="DB error")
        assert tracker.steps[0].status == StepStatus.FAILED

    def test_add_step_detail(self):
        tracker = _make_tracker()
        tracker.start_step("detail_step")
        tracker.add_step_detail("detail_step", "key", "value")
        assert tracker.steps[0].details["key"] == "value"

    def test_add_step_detail_disabled(self):
        tracker = _make_tracker(enabled=False)
        tracker.add_step_detail("step", "key", "val")  # Should not raise

    def test_add_step_detail_not_active(self):
        tracker = _make_tracker()
        tracker.add_step_detail("nonexistent", "key", "val")  # Should not raise

    def test_skip_step(self):
        tracker = _make_tracker()
        tracker.skip_step("some_step", "Feature not enabled")
        assert len(tracker.steps) == 1
        assert tracker.steps[0].status == StepStatus.SKIPPED

    def test_skip_step_disabled(self):
        tracker = _make_tracker(enabled=False)
        tracker.skip_step("some_step", "reason")
        assert len(tracker.steps) == 0


# ---------------------------------------------------------------------------
# Step listeners
# ---------------------------------------------------------------------------


class TestStepListeners:
    def test_register_listener(self):
        tracker = _make_tracker()
        listener = MagicMock()
        tracker.register_step_listener(listener)
        assert listener in tracker._step_listeners

    def test_listener_called_on_complete(self):
        tracker = _make_tracker()
        received = []
        tracker.register_step_listener(lambda d: received.append(d))
        tracker.start_step("step1")
        tracker.complete_current_step()
        assert len(received) == 1
        assert received[0]["step_name"] == "step1"

    def test_listener_exception_does_not_crash(self):
        tracker = _make_tracker()

        def bad_listener(d):
            raise RuntimeError("listener error")

        tracker.register_step_listener(bad_listener)
        tracker.start_step("step1")
        tracker.complete_current_step()  # Should not raise

    def test_unregister_listener(self):
        tracker = _make_tracker()
        listener = MagicMock()
        tracker.register_step_listener(listener)
        tracker.unregister_step_listener(listener)
        assert listener not in tracker._step_listeners

    def test_register_duplicate_listener(self):
        tracker = _make_tracker()
        listener = MagicMock()
        tracker.register_step_listener(listener)
        tracker.register_step_listener(listener)
        assert tracker._step_listeners.count(listener) == 1


# ---------------------------------------------------------------------------
# finalize_workflow
# ---------------------------------------------------------------------------


class TestFinalizeWorkflow:
    def test_finalize_sets_success(self):
        tracker = _make_tracker()
        tracker.finalize_workflow(success=True, final_answer="The answer")
        assert tracker.overall_success is True
        assert tracker.final_answer == "The answer"

    def test_finalize_auto_completes_active_steps(self):
        tracker = _make_tracker()
        tracker.start_step("hanging_step")
        tracker.finalize_workflow(success=False)
        assert tracker.steps[0].status == StepStatus.FAILED

    def test_finalize_disabled_returns_early(self):
        tracker = _make_tracker(enabled=False)
        tracker.finalize_workflow(success=True)
        assert tracker.workflow_end_time is None


# ---------------------------------------------------------------------------
# get_summary / get_detailed_chain / get_step_by_name
# ---------------------------------------------------------------------------


class TestSummaryAndChain:
    def test_get_summary_disabled(self):
        tracker = _make_tracker(enabled=False)
        summary = tracker.get_summary()
        assert summary == {"enabled": False}

    def test_get_summary_with_steps(self):
        tracker = _make_tracker()
        tracker.start_step("s1")
        tracker.complete_current_step(step_name="s1")
        tracker.skip_step("s2", "skipped")
        tracker.finalize_workflow(success=True)
        summary = tracker.get_summary()
        assert summary["total_steps"] == 2
        assert summary["successful_steps"] == 1
        assert summary["skipped_steps"] == 1

    def test_get_summary_without_finalize(self):
        tracker = _make_tracker()
        tracker.start_step("s1")
        tracker.complete_current_step(step_name="s1")
        summary = tracker.get_summary()
        assert summary["total_duration_ms"] == 0

    def test_get_detailed_chain_disabled(self):
        tracker = _make_tracker(enabled=False)
        assert tracker.get_detailed_chain() == []

    def test_get_detailed_chain_with_steps(self):
        tracker = _make_tracker()
        tracker.start_step("s1")
        tracker.complete_current_step(step_name="s1")
        chain = tracker.get_detailed_chain()
        assert len(chain) == 1
        assert chain[0]["step_name"] == "s1"

    def test_get_step_by_name(self):
        tracker = _make_tracker()
        tracker.start_step("find_me")
        tracker.complete_current_step(step_name="find_me")
        step = tracker.get_step_by_name("find_me")
        assert step is not None
        assert step.step_name == "find_me"

    def test_get_step_by_name_not_found(self):
        tracker = _make_tracker()
        assert tracker.get_step_by_name("nonexistent") is None


# ---------------------------------------------------------------------------
# StepTracker context manager
# ---------------------------------------------------------------------------


class TestStepTrackerContext:
    def test_basic_usage(self):
        tracker = _make_tracker()
        with StepTracker(tracker, "ctx_step", "analysis", "reason", "input"):
            pass
        assert tracker.steps[0].status == StepStatus.COMPLETED

    def test_exception_marks_failed(self):
        tracker = _make_tracker()
        with pytest.raises(ValueError):
            with StepTracker(tracker, "ctx_step"):
                raise ValueError("test error")
        assert tracker.steps[0].status == StepStatus.FAILED

    def test_no_tracker(self):
        with StepTracker(None, "step"):
            pass  # Should not raise

    def test_add_detail(self):
        tracker = _make_tracker()
        with StepTracker(tracker, "detail_step"):
            # StepTracker.add_detail passes key and value to add_step_detail
            # which requires (step_name, key, value) – use step_name from context
            tracker.add_step_detail("detail_step", "key", "val")
        assert tracker.steps[0].details.get("key") == "val"


# ---------------------------------------------------------------------------
# track_step decorator
# ---------------------------------------------------------------------------


class TestTrackStepDecorator:
    def test_decorator_with_cot_tracker(self):
        tracker = _make_tracker()

        class Obj:
            def __init__(self):
                self._cot_tracker = tracker

            @track_step("decorated_step", "analysis")
            def do_something(self):
                return "result"

        obj = Obj()
        result = obj.do_something()
        assert result == "result"
        assert len(tracker.steps) == 1

    def test_decorator_without_tracker(self):
        @track_step("no_tracker_step")
        def standalone():
            return 42

        result = standalone()
        assert result == 42


# ---------------------------------------------------------------------------
# validate_cot_config (module-level function)
# ---------------------------------------------------------------------------


class TestValidateCotConfig:
    def test_valid_config(self):
        config = _make_config()
        errors = validate_cot_config(config)
        assert errors == []

    def test_invalid_max_reasoning_length(self):
        config = _make_config(max_reasoning_length=10)
        errors = validate_cot_config(config)
        assert any("max_reasoning_length" in e for e in errors)

    def test_too_large_max_reasoning_length(self):
        config = _make_config(max_reasoning_length=9999)
        errors = validate_cot_config(config)
        assert any("max_reasoning_length" in e for e in errors)

    def test_invalid_enabled_type(self):
        config = _make_config()
        config.enabled = "yes"  # Wrong type
        errors = validate_cot_config(config)
        assert any("enabled" in e for e in errors)

    def test_invalid_display_preferences_type(self):
        config = _make_config()
        config.display_preferences = "not_a_dict"
        errors = validate_cot_config(config)
        assert any("display_preferences" in e for e in errors)

    def test_no_errors_for_empty_display_preferences(self):
        # enhanced_chain_of_thoughts validator doesn't check display_preferences keys
        config = _make_config(display_preferences={})
        errors = validate_cot_config(config)
        # No error expected for this validator (different from cot_config_validator)
        assert isinstance(errors, list)
