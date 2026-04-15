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
#   pydantic (MIT)
#   pytest (MIT)

"""
Test suite for Pydantic models integration in AskRITA.

Tests that StepDetails and RecommendedAction models work correctly
with the chain of thoughts system.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from askrita.models import RecommendedAction, StepDetails
from askrita.utils.chain_of_thoughts import ChainOfThoughtsStep, ChainOfThoughtsTracker


class TestStepDetails:
    """Test StepDetails Pydantic model."""

    def test_stepdetails_valid_data(self):
        """Test StepDetails with valid data."""
        details = StepDetails(
            llm_calls=2,
            tokens_used=1250,
            llm_latency_ms=850.5,
            database_calls=1,
            rows_processed=150,
            cache_hit=True,
            retries=0,
        )

        assert details.llm_calls == 2
        assert details.tokens_used == 1250
        assert details.llm_latency_ms == 850.5
        assert details.cache_hit is True
        assert details.retries == 0

    def test_stepdetails_negative_values_rejected(self):
        """Test that StepDetails rejects negative values."""
        with pytest.raises(ValidationError) as exc_info:
            StepDetails(llm_calls=-1, tokens_used=100)  # Invalid

        assert "llm_calls" in str(exc_info.value)

    def test_stepdetails_with_extra_data(self):
        """Test StepDetails extra field for custom data."""
        details = StepDetails(
            llm_calls=1,
            extra={
                "custom_metric": "value",
                "data_points": 42,
                "has_formatted_data": True,
            },
        )

        assert details.llm_calls == 1
        assert details.extra["custom_metric"] == "value"
        assert details.extra["data_points"] == 42

    def test_stepdetails_serialization(self):
        """Test StepDetails can be serialized to dict."""
        details = StepDetails(llm_calls=2, tokens_used=500, cache_hit=True)

        data_dict = details.model_dump()

        assert isinstance(data_dict, dict)
        assert data_dict["llm_calls"] == 2
        assert data_dict["tokens_used"] == 500
        assert data_dict["cache_hit"] is True


class TestRecommendedAction:
    """Test RecommendedAction Pydantic model."""

    def test_recommended_action_valid(self):
        """Test RecommendedAction with valid data."""
        action = RecommendedAction(
            id="add_timeframe",
            title="Add a time period",
            guidance="Specify when: 'in October 2023', 'last quarter'",
            priority=1,
            action_type="clarify",
        )

        assert action.id == "add_timeframe"
        assert action.title == "Add a time period"
        assert action.priority == 1
        assert action.action_type == "clarify"

    def test_recommended_action_empty_title_rejected(self):
        """Test that empty title is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RecommendedAction(id="test", title="", guidance="Some guidance")  # Invalid

        assert "title" in str(exc_info.value).lower()

    def test_recommended_action_invalid_priority(self):
        """Test that priority outside 1-5 range is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RecommendedAction(
                id="test",
                title="Test",
                guidance="Test guidance",
                priority=10,  # Invalid - must be 1-5
            )

        assert "priority" in str(exc_info.value).lower()

    def test_recommended_action_strips_whitespace(self):
        """Test that title and guidance are stripped."""
        action = RecommendedAction(
            id="test", title="  Test Title  ", guidance="  Test Guidance  "
        )

        assert action.title == "Test Title"
        assert action.guidance == "Test Guidance"


class TestChainOfThoughtsStepIntegration:
    """Test ChainOfThoughtsStep integration with Pydantic models."""

    def test_cot_step_with_stepdetails(self):
        """Test ChainOfThoughtsStep accepts StepDetails."""
        step = ChainOfThoughtsStep(
            step_name="test_step",
            step_type="analysis",
            status="started",
            start_time=datetime.now(timezone.utc),
        )

        # Complete with StepDetails
        details = StepDetails(llm_calls=1, tokens_used=500, cache_hit=False)

        step.complete(
            reasoning="Test reasoning",
            output_summary="Test output",
            details=details,
            confidence_score=0.9,
        )

        assert step.status == "completed"
        assert isinstance(step.details, StepDetails)
        assert step.details.llm_calls == 1
        assert step.details.tokens_used == 500

    def test_cot_step_with_dict_converts_to_stepdetails(self):
        """Test ChainOfThoughtsStep converts dict to StepDetails."""
        step = ChainOfThoughtsStep(
            step_name="test_step",
            step_type="generation",
            status="started",
            start_time=datetime.now(timezone.utc),
        )

        # Complete with dict - should be converted to StepDetails
        step.complete(
            reasoning="Test",
            details={"llm_calls": 2, "tokens_used": 1000, "cache_hit": True},
        )

        # Should be converted to StepDetails
        assert isinstance(step.details, StepDetails)
        assert step.details.llm_calls == 2
        assert step.details.tokens_used == 1000
        assert step.details.cache_hit is True

    def test_cot_step_to_dict_serializes_stepdetails(self):
        """Test to_dict properly serializes StepDetails."""
        step = ChainOfThoughtsStep(
            step_name="test_step",
            step_type="execution",
            status="started",
            start_time=datetime.now(timezone.utc),
        )

        step.complete(
            details=StepDetails(llm_calls=1, database_calls=1, rows_processed=100)
        )

        step_dict = step.to_dict()

        assert isinstance(step_dict, dict)
        assert isinstance(step_dict["details"], dict)
        assert step_dict["details"]["llm_calls"] == 1
        assert step_dict["details"]["database_calls"] == 1
        assert step_dict["details"]["rows_processed"] == 100

    def test_cot_step_backwards_compatible_with_dict(self):
        """Test ChainOfThoughtsStep still works with plain dicts when Pydantic not available."""
        step = ChainOfThoughtsStep(
            step_name="test_step",
            step_type="formatting",
            status="started",
            start_time=datetime.now(timezone.utc),
        )

        # Use plain dict (backwards compatible)
        step.complete(details={"custom_field": "value", "another_field": 123})

        # Should work with dict (either as StepDetails or dict)
        assert step.details is not None
        step_dict = step.to_dict()
        assert "details" in step_dict


class TestChainOfThoughtsTrackerIntegration:
    """Test full chain of thoughts workflow with Pydantic models."""

    def test_tracker_with_typed_details(self):
        """Test ChainOfThoughtsTracker with typed StepDetails."""
        tracker = ChainOfThoughtsTracker(enabled=True)

        # Start a step
        tracker.start_step(
            step_name="parse_question",
            step_type="analysis",
            reasoning="Analyzing user question",
            input_summary="User question: What is NPS?",
        )

        # Complete with typed details
        tracker.complete_current_step(
            output_summary="Question parsed successfully",
            details=StepDetails(
                llm_calls=1,
                tokens_used=750,
                llm_latency_ms=420.5,
                extra={"tables_identified": 2},
            ),
            confidence_score=0.95,
        )

        # Verify
        assert len(tracker.steps) == 1
        step = tracker.steps[0]
        assert step.status == "completed"
        assert isinstance(step.details, StepDetails)
        assert step.details.llm_calls == 1
        assert step.details.extra["tables_identified"] == 2

    def test_tracker_summary_with_typed_details(self):
        """Test tracker summary includes typed details."""
        tracker = ChainOfThoughtsTracker(enabled=True)

        # Add multiple steps with typed details
        for i in range(3):
            tracker.start_step(
                step_name=f"step_{i}", step_type="analysis", reasoning=f"Step {i}"
            )
            tracker.complete_current_step(
                details=StepDetails(llm_calls=1, tokens_used=i * 100)
            )

        summary = tracker.get_summary()

        assert summary["enabled"] is True
        assert len(summary["steps"]) == 3

        # Verify details in summary
        for step_summary in summary["steps"]:
            assert "details" in step_summary
            assert isinstance(step_summary["details"], dict)


class TestBackwardsCompatibility:
    """Test that changes maintain backwards compatibility."""

    def test_dict_details_still_work(self):
        """Test that plain dict details still work without Pydantic."""
        step = ChainOfThoughtsStep(
            step_name="legacy_step",
            step_type="execution",
            status="started",
            start_time=datetime.now(timezone.utc),
            details={"legacy_field": "value"},
        )

        step.complete(details={"another_field": 123})

        # Should work
        step_dict = step.to_dict()
        assert "details" in step_dict

    def test_none_details_handled_gracefully(self):
        """Test that None details are handled gracefully."""
        step = ChainOfThoughtsStep(
            step_name="test",
            step_type="analysis",
            status="started",
            start_time=datetime.now(timezone.utc),
        )

        # Complete without details
        step.complete(reasoning="No details provided")

        # Should work
        step_dict = step.to_dict()
        assert "details" in step_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
