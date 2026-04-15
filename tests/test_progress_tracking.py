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
Comprehensive tests for progress tracking functionality.

Tests cover:
1. ProgressData and ProgressStatus classes
2. Progress callback integration in SQLAgentWorkflow
3. Step tracking and completion callbacks
4. Error handling in callbacks
5. Backward compatibility (no callback provided)
"""

import os
import time
from unittest.mock import Mock, patch

import pytest

from askrita.config_manager import ConfigManager
from askrita.sqlagent.progress_tracker import (
    PROGRESS_MESSAGES,
    ProgressData,
    ProgressStatus,
)
from askrita.sqlagent.workflows.SQLAgentWorkflow import SQLAgentWorkflow


@pytest.fixture(autouse=True)
def mock_openai_api_key():
    """Automatically mock OPENAI_API_KEY for all progress tracking tests."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
        yield


class TestProgressDataClass:
    """Test the ProgressData class and its methods."""

    def test_progress_data_initialization_minimal(self):
        """Test ProgressData initialization with minimal parameters."""
        progress = ProgressData(step_name="test_step", status=ProgressStatus.STARTED)

        assert progress.step_name == "test_step"
        assert progress.status == ProgressStatus.STARTED
        assert progress.message is not None  # Should use default message
        assert progress.error is None
        assert progress.step_index is None
        assert progress.total_steps is None
        assert progress.step_data == {}
        assert progress.timestamp is not None
        assert isinstance(progress.timestamp, float)

    def test_progress_data_initialization_full(self):
        """Test ProgressData initialization with all parameters."""
        test_data = {"sql": "SELECT * FROM users", "count": 42}
        progress = ProgressData(
            step_name="generate_sql",
            status=ProgressStatus.COMPLETED,
            message="Custom message",
            error=None,
            step_index=3,
            total_steps=8,
            step_data=test_data,
        )

        assert progress.step_name == "generate_sql"
        assert progress.status == ProgressStatus.COMPLETED
        assert progress.message == "Custom message"
        assert progress.error is None
        assert progress.step_index == 3
        assert progress.total_steps == 8
        assert progress.step_data == test_data

    def test_progress_data_with_error(self):
        """Test ProgressData with error information."""
        progress = ProgressData(
            step_name="execute_sql",
            status=ProgressStatus.FAILED,
            error="Connection timeout",
        )

        assert progress.status == ProgressStatus.FAILED
        assert progress.error == "Connection timeout"

    def test_progress_data_to_dict(self):
        """Test ProgressData serialization to dictionary."""
        test_data = {"results": 100}
        progress = ProgressData(
            step_name="test_step",
            status=ProgressStatus.COMPLETED,
            message="Test message",
            error=None,
            step_index=1,
            total_steps=5,
            step_data=test_data,
        )

        result = progress.to_dict()

        assert isinstance(result, dict)
        assert result["step_name"] == "test_step"
        assert result["status"] == "completed"
        assert result["message"] == "Test message"
        assert result["error"] is None
        assert result["step_index"] == 1
        assert result["total_steps"] == 5
        assert result["step_data"] == test_data
        assert "timestamp" in result
        assert isinstance(result["timestamp"], float)

    def test_progress_data_default_message(self):
        """Test that default messages are used when none provided."""
        progress = ProgressData(
            step_name="parse_question", status=ProgressStatus.STARTED
        )

        # Should use message from PROGRESS_MESSAGES
        assert progress.message == PROGRESS_MESSAGES.get(
            "parse_question", "parse_question started"
        )


class TestProgressStatus:
    """Test the ProgressStatus enum."""

    def test_progress_status_values(self):
        """Test that all expected status values exist."""
        assert ProgressStatus.STARTED.value == "started"
        assert ProgressStatus.COMPLETED.value == "completed"
        assert ProgressStatus.FAILED.value == "failed"
        assert ProgressStatus.SKIPPED.value == "skipped"

    def test_progress_status_comparison(self):
        """Test ProgressStatus enum comparison."""
        assert ProgressStatus.STARTED.value == "started"
        assert ProgressStatus.STARTED != ProgressStatus.COMPLETED


class TestProgressMessages:
    """Test the default progress messages."""

    def test_progress_messages_exist(self):
        """Test that default messages are defined for workflow steps."""
        expected_steps = [
            "parse_question",
            "get_unique_nouns",
            "generate_sql",
            "validate_and_fix_sql",
            "execute_sql",
            "format_results",
            "generate_followup_questions",
            "choose_visualization",
            "choose_and_format_visualization",
        ]

        for step in expected_steps:
            assert step in PROGRESS_MESSAGES
            assert isinstance(PROGRESS_MESSAGES[step], str)
            assert len(PROGRESS_MESSAGES[step]) > 0


class TestWorkflowProgressTracking:
    """Test progress tracking integration in SQLAgentWorkflow."""

    def test_workflow_without_progress_callback(self):
        """Test that workflow works normally without progress callback."""
        # This is the backward compatibility test
        config = ConfigManager()
        workflow = SQLAgentWorkflow(
            config,
            test_llm_connection=False,
            test_db_connection=False,
            init_schema_cache=False,
        )

        # Should initialize successfully without callback
        assert workflow.progress_callback is None

    def test_workflow_with_progress_callback(self):
        """Test that workflow accepts and stores progress callback."""
        config = ConfigManager()
        callback = Mock()

        workflow = SQLAgentWorkflow(
            config,
            test_llm_connection=False,
            test_db_connection=False,
            init_schema_cache=False,
            progress_callback=callback,
        )

        assert workflow.progress_callback is callback

    def test_track_step_without_callback(self):
        """Test _track_step when no callback is provided."""
        config = ConfigManager()
        workflow = SQLAgentWorkflow(
            config,
            test_llm_connection=False,
            test_db_connection=False,
            init_schema_cache=False,
        )

        # Should not raise error
        result = workflow._track_step("test_step")
        assert result == "test_step"

    def test_track_step_with_callback(self):
        """Test _track_step calls callback with correct data."""
        config = ConfigManager()
        callback = Mock()

        workflow = SQLAgentWorkflow(
            config,
            test_llm_connection=False,
            test_db_connection=False,
            init_schema_cache=False,
            progress_callback=callback,
        )

        workflow._track_step("test_step")

        # Verify callback was called
        callback.assert_called_once()

        # Verify ProgressData structure
        call_args = callback.call_args[0][0]
        assert isinstance(call_args, ProgressData)
        assert call_args.step_name == "test_step"
        assert call_args.status == ProgressStatus.STARTED

    def test_track_step_with_step_data(self):
        """Test _track_step includes step_data in callback."""
        config = ConfigManager()
        callback = Mock()

        workflow = SQLAgentWorkflow(
            config,
            test_llm_connection=False,
            test_db_connection=False,
            init_schema_cache=False,
            progress_callback=callback,
        )

        test_data = {"key": "value", "count": 42}
        workflow._track_step("test_step", step_data=test_data)

        call_args = callback.call_args[0][0]
        assert call_args.step_data == test_data

    def test_complete_step_without_callback(self):
        """Test _complete_step when no callback is provided."""
        config = ConfigManager()
        workflow = SQLAgentWorkflow(
            config,
            test_llm_connection=False,
            test_db_connection=False,
            init_schema_cache=False,
        )

        # Should not raise error
        workflow._complete_step("test_step")

    def test_complete_step_success_with_callback(self):
        """Test _complete_step calls callback with COMPLETED status."""
        config = ConfigManager()
        callback = Mock()

        workflow = SQLAgentWorkflow(
            config,
            test_llm_connection=False,
            test_db_connection=False,
            init_schema_cache=False,
            progress_callback=callback,
        )

        workflow._complete_step("test_step")

        callback.assert_called_once()
        call_args = callback.call_args[0][0]
        assert isinstance(call_args, ProgressData)
        assert call_args.step_name == "test_step"
        assert call_args.status == ProgressStatus.COMPLETED
        assert call_args.error is None

    def test_complete_step_failure_with_callback(self):
        """Test _complete_step calls callback with FAILED status on error."""
        config = ConfigManager()
        callback = Mock()

        workflow = SQLAgentWorkflow(
            config,
            test_llm_connection=False,
            test_db_connection=False,
            init_schema_cache=False,
            progress_callback=callback,
        )

        workflow._complete_step("test_step", error="Test error message")

        callback.assert_called_once()
        call_args = callback.call_args[0][0]
        assert call_args.step_name == "test_step"
        assert call_args.status == ProgressStatus.FAILED
        assert call_args.error == "Test error message"

    def test_complete_step_with_step_data(self):
        """Test _complete_step includes step_data in callback."""
        config = ConfigManager()
        callback = Mock()

        workflow = SQLAgentWorkflow(
            config,
            test_llm_connection=False,
            test_db_connection=False,
            init_schema_cache=False,
            progress_callback=callback,
        )

        test_data = {"sql": "SELECT 1", "rows": 100}
        workflow._complete_step("test_step", step_data=test_data)

        call_args = callback.call_args[0][0]
        assert call_args.step_data == test_data


class TestProgressCallbackErrorHandling:
    """Test error handling in progress callbacks."""

    def test_callback_exception_is_caught(self):
        """Test that exceptions in callback don't break workflow."""
        config = ConfigManager()

        # Create callback that raises exception
        def failing_callback(progress):
            raise RuntimeError("Callback error")

        workflow = SQLAgentWorkflow(
            config,
            test_llm_connection=False,
            test_db_connection=False,
            init_schema_cache=False,
            progress_callback=failing_callback,
        )

        # Should not raise exception
        workflow._track_step("test_step")
        workflow._complete_step("test_step")

    def test_callback_with_none_raises_no_error(self):
        """Test that None callback is handled gracefully."""
        config = ConfigManager()
        workflow = SQLAgentWorkflow(
            config,
            test_llm_connection=False,
            test_db_connection=False,
            init_schema_cache=False,
            progress_callback=None,
        )

        # Should not raise
        workflow._track_step("test_step")
        workflow._complete_step("test_step")


class TestProgressTrackingTimestamps:
    """Test timestamp functionality in progress tracking."""

    def test_timestamp_is_current_time(self):
        """Test that timestamp reflects current time."""
        before = time.time()
        progress = ProgressData(step_name="test", status=ProgressStatus.STARTED)
        after = time.time()

        assert before <= progress.timestamp <= after

    def test_timestamps_are_sequential(self):
        """Test that sequential progress events have increasing timestamps."""
        progress1 = ProgressData("step1", ProgressStatus.STARTED)
        time.sleep(0.01)  # Small delay
        progress2 = ProgressData("step2", ProgressStatus.STARTED)

        assert progress2.timestamp > progress1.timestamp


class TestProgressTrackingIntegration:
    """Integration tests for complete progress tracking flow."""

    def test_full_workflow_progress_sequence(self):
        """Test that a workflow emits expected progress events."""
        config = ConfigManager()

        # Track all progress events
        progress_events = []

        def tracking_callback(progress: ProgressData):
            progress_events.append(
                {
                    "step": progress.step_name,
                    "status": progress.status,
                    "error": progress.error,
                }
            )

        workflow = SQLAgentWorkflow(
            config,
            test_llm_connection=False,
            test_db_connection=False,
            init_schema_cache=False,
            progress_callback=tracking_callback,
        )

        # Simulate step tracking
        workflow._track_step("parse_question")
        workflow._complete_step("parse_question")

        # Verify events
        assert len(progress_events) == 2
        assert progress_events[0]["step"] == "parse_question"
        assert progress_events[0]["status"] == ProgressStatus.STARTED
        assert progress_events[1]["step"] == "parse_question"
        assert progress_events[1]["status"] == ProgressStatus.COMPLETED

    def test_progress_data_serialization_for_json(self):
        """Test that progress data can be serialized to JSON."""
        import json

        progress = ProgressData(
            step_name="test",
            status=ProgressStatus.COMPLETED,
            step_data={"count": 42, "sql": "SELECT 1"},
        )

        # Should be JSON serializable
        json_str = json.dumps(progress.to_dict())
        assert json_str is not None

        # Should be deserializable
        data = json.loads(json_str)
        assert data["step_name"] == "test"
        assert data["status"] == "completed"
        assert data["step_data"]["count"] == 42


class TestProgressTrackingBackwardCompatibility:
    """Test backward compatibility - existing code should work unchanged."""

    def test_existing_workflow_initialization_unchanged(self):
        """Test that existing workflow initialization still works."""
        config = ConfigManager()

        # Old way - should still work
        workflow = SQLAgentWorkflow(
            config, test_llm_connection=False, test_db_connection=False
        )
        assert workflow is not None
        assert workflow.progress_callback is None

    def test_no_performance_impact_without_callback(self):
        """Test that there's no performance impact when callback is not used."""
        config = ConfigManager()

        workflow_without = SQLAgentWorkflow(
            config,
            test_llm_connection=False,
            test_db_connection=False,
            init_schema_cache=False,
        )

        # Measure time without callback
        start = time.time()
        for _ in range(100):
            workflow_without._track_step("test")
            workflow_without._complete_step("test")
        time_without = time.time() - start

        # Should be very fast (< 0.1 seconds for 100 iterations)
        assert time_without < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
