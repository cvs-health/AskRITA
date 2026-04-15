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

"""
Chain of Thoughts tracking system for LangQuery workflow steps.

This module provides a comprehensive system for tracking and recording the reasoning
process behind each step in the SQL query workflow, enabling transparent AI decision-making.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from .constants import DisplayLimits

# Import Pydantic models for type safety
try:
    from askrita.models import StepDetails

    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    StepDetails = None

logger = logging.getLogger(__name__)


@dataclass
class ChainOfThoughtsStep:
    """
    Represents a single step in the chain of thoughts reasoning process.

    Each step captures:
    - What was done
    - Why it was done
    - What was the input/output
    - How long it took
    - Any errors or decisions made
    """

    step_name: str
    step_type: str  # 'analysis', 'generation', 'validation', 'execution', 'formatting'
    status: str  # 'started', 'completed', 'failed', 'skipped'

    # Timing information
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None

    # Step reasoning and results
    reasoning: str = ""  # Why this step was needed and what approach was taken
    input_summary: str = ""  # Summary of key inputs to this step
    output_summary: str = ""  # Summary of what was produced

    # Detailed information - supports both Pydantic StepDetails and dict for backwards compatibility
    details: Union["StepDetails", Dict[str, Any]] = field(default_factory=dict)

    # Error handling
    error_message: Optional[str] = None
    retry_count: int = 0

    # Success metrics
    confidence_score: Optional[float] = None  # 0.0-1.0 confidence in result

    def complete(
        self,
        reasoning: str = "",
        output_summary: str = "",
        details: Union["StepDetails", Dict[str, Any]] = None,
        confidence_score: float = None,
        error_message: str = None,
    ):
        """Mark step as completed with results."""
        self.end_time = datetime.now(timezone.utc)
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000

        if error_message:
            self.status = "failed"
            self.error_message = error_message
        else:
            self.status = "completed"

        self.reasoning = reasoning
        self.output_summary = output_summary
        self.confidence_score = confidence_score

        # Handle details with type validation
        if details:
            self._assign_step_details(details)

    def _try_convert_dict_to_step_details(self, details: dict) -> None:
        """Convert a dict to StepDetails, falling back to raw dict on failure."""
        try:
            self.details = StepDetails(**details)
            logger.debug(f"Converted dict to StepDetails for step '{self.step_name}'")
        except Exception as e:
            logger.warning(f"Failed to validate details as StepDetails: {e}. Using raw dict.")
            if isinstance(self.details, dict):
                self.details.update(details)
            else:
                self.details = details

    def _assign_step_details(self, details) -> None:
        """Assign step details with type validation."""
        if PYDANTIC_AVAILABLE and StepDetails is not None:
            if isinstance(details, StepDetails):
                self.details = details
            elif isinstance(details, dict):
                self._try_convert_dict_to_step_details(details)
            else:
                self.details = details
        elif isinstance(self.details, dict) and isinstance(details, dict):
            self.details.update(details)
        else:
            self.details = details

    def to_dict(self) -> Dict[str, Any]:
        """Convert step to dictionary for serialization."""
        # Serialize details - handle both StepDetails and dict
        details_dict = self.details
        if (
            PYDANTIC_AVAILABLE
            and StepDetails is not None
            and isinstance(self.details, StepDetails)
        ):
            details_dict = self.details.model_dump()

        return {
            "step_name": self.step_name,
            "step_type": self.step_type,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "reasoning": self.reasoning,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "details": details_dict,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "confidence_score": self.confidence_score,
        }


class ChainOfThoughtsTracker:
    """
    Main tracker for chain of thoughts across the entire workflow.

    This class manages the step-by-step reasoning process and provides
    methods for starting, completing, and organizing steps.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.steps: List[ChainOfThoughtsStep] = []
        self.workflow_start_time = datetime.now(timezone.utc)
        self.workflow_end_time: Optional[datetime] = None
        self.current_step: Optional[ChainOfThoughtsStep] = None

        # Workflow-level metadata
        self.workflow_id = f"workflow_{int(time.time_ns() // 1000000)}"
        self.question: str = ""
        self.overall_success: bool = False
        self.final_answer: str = ""

        # Real-time listener support for streaming step updates
        self._step_listeners: List[Any] = []

        logger.debug(f"Chain of thoughts tracker initialized (enabled={enabled})")

    def start_step(
        self,
        step_name: str,
        step_type: str,
        reasoning: str = "",
        input_summary: str = "",
    ) -> Optional[ChainOfThoughtsStep]:
        """
        Start tracking a new workflow step.

        Args:
            step_name: Name of the workflow step (e.g., 'parse_question', 'generate_sql')
            step_type: Type of step ('analysis', 'generation', 'validation', etc.)
            reasoning: Initial reasoning for why this step is needed
            input_summary: Summary of inputs being processed

        Returns:
            ChainOfThoughtsStep: The created step object, or None if disabled
        """
        if not self.enabled:
            return None

        # Complete any previous step that wasn't explicitly completed
        if self.current_step and self.current_step.status == "started":
            logger.warning(
                f"Step '{self.current_step.step_name}' was not completed, auto-completing"
            )
            self.current_step.complete(
                error_message="Step was not explicitly completed"
            )

        step = ChainOfThoughtsStep(
            step_name=step_name,
            step_type=step_type,
            status="started",
            start_time=datetime.now(timezone.utc),
            reasoning=reasoning,
            input_summary=input_summary,
        )

        self.steps.append(step)
        self.current_step = step

        logger.debug(f"Started tracking step: {step_name} ({step_type})")
        return step

    def complete_current_step(
        self,
        reasoning: str = "",
        output_summary: str = "",
        details: Dict[str, Any] = None,
        confidence_score: float = None,
        error_message: str = None,
    ):
        """Complete the currently active step."""
        if not self.enabled or not self.current_step:
            return

        self.current_step.complete(
            reasoning=reasoning,
            output_summary=output_summary,
            details=details,
            confidence_score=confidence_score,
            error_message=error_message,
        )

        logger.debug(
            f"Completed step: {self.current_step.step_name} "
            f"(status={self.current_step.status}, duration={self.current_step.duration_ms:.1f}ms)"
        )

        # Notify listeners immediately for real-time streaming
        self._notify_step_listeners(self.current_step)

        self.current_step = None

    def add_step_detail(self, key: str, value: Any):
        """Add additional detail to the current step."""
        if not self.enabled or not self.current_step:
            return
        self.current_step.details[key] = value

    def skip_step(self, step_name: str, reason: str):
        """Record that a step was skipped."""
        if not self.enabled:
            return

        step = ChainOfThoughtsStep(
            step_name=step_name,
            step_type="skipped",
            status="skipped",
            start_time=datetime.now(timezone.utc),
            reasoning=f"Step skipped: {reason}",
        )
        step.end_time = step.start_time
        step.duration_ms = 0

        self.steps.append(step)
        logger.debug(f"Recorded skipped step: {step_name} - {reason}")

    def register_step_listener(self, listener: Any):
        """Register a listener to receive real-time step completion notifications.

        Args:
            listener: Callable that accepts a step dict with step data
        """
        if listener not in self._step_listeners:
            self._step_listeners.append(listener)
            logger.debug(f"Registered step listener: {listener}")

    def unregister_step_listener(self, listener: Any):
        """Unregister a previously registered step listener."""
        if listener in self._step_listeners:
            self._step_listeners.remove(listener)
            logger.debug(f"Unregistered step listener: {listener}")

    def _notify_step_listeners(self, step: ChainOfThoughtsStep):
        """Notify all registered listeners that a step has completed.

        This is called immediately when a step completes to enable real-time streaming.
        """
        if not self._step_listeners:
            return

        # Convert step to dict for serialization
        step_data = step.to_dict()

        # Notify all listeners
        for listener in tuple(
            self._step_listeners
        ):  # Use tuple to avoid modification during iteration
            try:
                listener(step_data)
            except Exception as e:
                logger.error(f"Error notifying step listener: {e}", exc_info=True)

    def finalize_workflow(
        self, success: bool, final_answer: str = "", _overall_reasoning: str = ""
    ):
        """Finalize the entire workflow tracking."""
        if not self.enabled:
            return

        self.workflow_end_time = datetime.now(timezone.utc)
        self.overall_success = success
        self.final_answer = final_answer

        # Complete any remaining step
        if self.current_step and self.current_step.status == "started":
            self.current_step.complete()

        total_duration = (
            self.workflow_end_time - self.workflow_start_time
        ).total_seconds() * 1000
        logger.info(
            f"Workflow finalized: success={success}, total_duration={total_duration:.1f}ms, steps={len(self.steps)}"
        )

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the chain of thoughts for the workflow."""
        if not self.enabled:
            return {"enabled": False}

        total_duration = 0
        if self.workflow_end_time:
            total_duration = (
                self.workflow_end_time - self.workflow_start_time
            ).total_seconds() * 1000

        step_summary = []
        for step in self.steps:
            # Serialize details - handle both StepDetails and dict
            details_dict = step.details
            if (
                PYDANTIC_AVAILABLE
                and StepDetails is not None
                and isinstance(step.details, StepDetails)
            ):
                details_dict = step.details.model_dump()

            step_summary.append(
                {
                    "name": step.step_name,
                    "type": step.step_type,
                    "status": step.status,
                    "duration_ms": step.duration_ms,
                    "reasoning": step.reasoning[: DisplayLimits.QUESTION_PREVIEW]
                    + (
                        "..."
                        if len(step.reasoning) > DisplayLimits.QUESTION_PREVIEW
                        else ""
                    ),
                    "confidence": step.confidence_score,
                    "details": details_dict,
                }
            )

        return {
            "enabled": True,
            "workflow_id": self.workflow_id,
            "total_steps": len(self.steps),
            "successful_steps": len([s for s in self.steps if s.status == "completed"]),
            "failed_steps": len([s for s in self.steps if s.status == "failed"]),
            "skipped_steps": len([s for s in self.steps if s.status == "skipped"]),
            "total_duration_ms": total_duration,
            "overall_success": self.overall_success,
            "steps": step_summary,
        }

    def get_detailed_chain(self) -> List[Dict[str, Any]]:
        """Get the complete detailed chain of thoughts."""
        if not self.enabled:
            return []

        return [step.to_dict() for step in self.steps]

    def get_step_by_name(self, step_name: str) -> Optional[ChainOfThoughtsStep]:
        """Get a specific step by name."""
        for step in self.steps:
            if step.step_name == step_name:
                return step
        return None


# Utility functions for step type classification
def get_step_type(step_name: str) -> str:
    """Classify workflow steps into logical types."""
    # Import here to avoid circular imports
    try:
        from .step_registry import get_step_type as registry_get_step_type

        return registry_get_step_type(step_name)
    except ImportError:
        # Fallback to hardcoded mapping if registry is not available
        step_types = {
            "parse_question": "analysis",
            "get_unique_nouns": "analysis",
            "generate_sql": "generation",
            "validate_and_fix_sql": "validation",
            "execute_sql": "execution",
            "format_results": "formatting",
            "choose_visualization": "analysis",
            "format_data_for_visualization": "formatting",
            "generate_followup_questions": "generation",
        }
        return step_types.get(step_name, "unknown")


def create_step_reasoning_templates() -> Dict[str, Dict[str, str]]:
    """Create templates for step reasoning descriptions."""
    # Import here to avoid circular imports
    try:
        from .step_registry import get_step_registry

        registry = get_step_registry()
        templates = {}
        for step_name, step_info in registry.get_all_steps().items():
            templates[step_name] = step_info.reasoning_template
        return templates
    except ImportError:
        # Fallback to hardcoded templates if registry is not available
        return {
            "parse_question": {
                "start": "Analyzing the natural language question to identify relevant database tables and columns",
                "success": "Successfully identified {table_count} relevant tables and extracted key information",
                "failure": "Failed to parse the question due to: {error}",
            },
            "get_unique_nouns": {
                "start": "Extracting unique values from relevant columns to improve query accuracy",
                "success": "Found {noun_count} unique values that will help generate precise SQL",
                "failure": "Could not extract unique nouns: {error}",
            },
            "generate_sql": {
                "start": "Generating SQL query based on question analysis and database schema",
                "success": "Generated SQL query with {complexity} complexity targeting {tables}",
                "failure": "SQL generation failed: {error}",
            },
            "validate_and_fix_sql": {
                "start": "Validating generated SQL for syntax, safety, and optimization opportunities",
                "success": "SQL validated successfully{fixes}",
                "failure": "SQL validation failed: {error}",
            },
            "execute_sql": {
                "start": "Executing validated SQL query against the database",
                "success": "Query executed successfully, returned {row_count} rows in {duration}ms",
                "failure": "Query execution failed: {error}",
            },
            "format_results": {
                "start": "Formatting query results into a comprehensive natural language response",
                "success": "Formatted results into {format_type} with {insight_count} key insights",
                "failure": "Result formatting failed: {error}",
            },
            "choose_visualization": {
                "start": "Analyzing data characteristics to recommend optimal visualization",
                "success": "Recommended {chart_type} visualization based on {criteria}",
                "failure": "Visualization selection failed: {error}",
            },
            "format_data_for_visualization": {
                "start": "Transforming query results into chart-ready data format",
                "success": "Formatted {data_points} data points for {chart_type} chart",
                "failure": "Data formatting for visualization failed: {error}",
            },
            "generate_followup_questions": {
                "start": "Generating strategic follow-up questions based on results and context",
                "success": "Generated {question_count} relevant follow-up questions",
                "failure": "Follow-up question generation failed: {error}",
            },
        }


# Memory context for managing chain of thoughts with user preferences
def save_chain_of_thoughts_preferences():
    """Save user preferences for chain of thoughts display."""
    return {
        "display_reasoning": True,
        "show_timing": True,
        "show_confidence": True,
        "collapse_successful_steps": False,
        "highlight_failed_steps": True,
        "show_step_details": False,  # Advanced mode
    }
