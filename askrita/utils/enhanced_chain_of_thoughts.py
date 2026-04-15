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
Enhanced Chain of Thoughts tracking system for LangQuery workflow steps.

This module provides an improved system for tracking and recording the reasoning
process behind each step in the SQL query workflow, with better maintainability,
performance, and extensibility.

Key improvements:
- Decorator pattern for automatic step tracking
- Step registry system for better organization
- Context manager for safer step tracking
- Configuration validation
- Performance monitoring
"""

import functools
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from .constants import DisplayLimits

logger = logging.getLogger(__name__)

# Type variables for generic support
T = TypeVar("T")
F = TypeVar("F", bound=Callable)


class StepStatus(Enum):
    """Enumeration for step status values."""

    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepType(Enum):
    """Enumeration for step types."""

    ANALYSIS = "analysis"
    GENERATION = "generation"
    VALIDATION = "validation"
    EXECUTION = "execution"
    FORMATTING = "formatting"
    UNKNOWN = "unknown"


@dataclass
class StepInfo:
    """Information about a registered step."""

    name: str
    step_type: StepType
    reasoning_template: Dict[str, str] = field(default_factory=dict)
    description: str = ""
    enabled: bool = True


class StepRegistry:
    """Registry for managing workflow steps and their configurations."""

    def __init__(self):
        self._steps: Dict[str, StepInfo] = {}
        self._default_type = StepType.UNKNOWN
        self._lock = threading.Lock()

    def register_step(
        self,
        name: str,
        step_type: Union[str, StepType],
        reasoning_template: Dict[str, str] = None,
        description: str = "",
        enabled: bool = True,
    ) -> None:
        """
        Register a step with its type and reasoning template.

        Args:
            name: Step name (e.g., 'parse_question', 'generate_sql')
            step_type: Type of step ('analysis', 'generation', etc.)
            reasoning_template: Template for reasoning messages
            description: Human-readable description of the step
            enabled: Whether this step is enabled by default
        """
        with self._lock:
            if isinstance(step_type, str):
                try:
                    step_type = StepType(step_type)
                except ValueError:
                    logger.warning(f"Unknown step type '{step_type}', using UNKNOWN")
                    step_type = StepType.UNKNOWN

            self._steps[name] = StepInfo(
                name=name,
                step_type=step_type,
                reasoning_template=reasoning_template or {},
                description=description,
                enabled=enabled,
            )

            logger.debug(f"Registered step: {name} ({step_type.value})")

    def get_step_info(self, name: str) -> StepInfo:
        """Get step information including type and template."""
        with self._lock:
            return self._steps.get(
                name,
                StepInfo(
                    name=name,
                    step_type=self._default_type,
                    reasoning_template={},
                    description=f"Unregistered step: {name}",
                    enabled=True,
                ),
            )

    def is_step_enabled(self, name: str) -> bool:
        """Check if a step is enabled."""
        return self.get_step_info(name).enabled

    def get_all_steps(self) -> Dict[str, StepInfo]:
        """Get all registered steps."""
        with self._lock:
            return self._steps.copy()

    def unregister_step(self, name: str) -> bool:
        """Unregister a step. Returns True if step was found and removed."""
        with self._lock:
            if name in self._steps:
                del self._steps[name]
                logger.debug(f"Unregistered step: {name}")
                return True
            return False


# Global step registry instance
_step_registry = StepRegistry()


def get_step_registry() -> StepRegistry:
    """Get the global step registry instance."""
    return _step_registry


@dataclass
class ChainOfThoughtsStep:
    """
    Enhanced step representation with better type safety and validation.

    Each step captures:
    - What was done
    - Why it was done
    - What was the input/output
    - How long it took
    - Any errors or decisions made
    """

    step_name: str
    step_type: StepType
    status: StepStatus

    # Timing information
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None

    # Step reasoning and results
    reasoning: str = ""
    input_summary: str = ""
    output_summary: str = ""

    # Detailed information
    details: Dict[str, Any] = field(default_factory=dict)

    # Error handling
    error_message: Optional[str] = None
    retry_count: int = 0

    # Success metrics
    confidence_score: Optional[float] = None

    def complete(
        self,
        reasoning: str = "",
        output_summary: str = "",
        details: Dict[str, Any] = None,
        confidence_score: float = None,
        error_message: str = None,
    ) -> None:
        """Mark step as completed with results."""
        self.end_time = datetime.now(timezone.utc)
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000

        if error_message:
            self.status = StepStatus.FAILED
            self.error_message = error_message
        else:
            self.status = StepStatus.COMPLETED

        self.reasoning = reasoning
        self.output_summary = output_summary
        self.confidence_score = confidence_score

        if details:
            self.details.update(details)

    def to_dict(self) -> Dict[str, Any]:
        """Convert step to dictionary for serialization."""
        return {
            "step_name": self.step_name,
            "step_type": self.step_type.value,
            "status": self.status.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "reasoning": self.reasoning,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "details": self.details,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "confidence_score": self.confidence_score,
        }


@dataclass
class CoTPerformanceMetrics:
    """Performance metrics for chain of thoughts tracking."""

    total_tracking_time_ms: float = 0.0
    step_count: int = 0
    average_step_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    enabled_steps: int = 0
    disabled_steps: int = 0

    def calculate_average_step_time(self) -> None:
        """Calculate average step time."""
        if self.step_count > 0:
            self.average_step_time_ms = self.total_tracking_time_ms / self.step_count


class EnhancedChainOfThoughtsTracker:
    """
    Enhanced tracker for chain of thoughts with better performance and features.

    This class manages the step-by-step reasoning process and provides
    methods for starting, completing, and organizing steps with improved
    error handling and performance monitoring.
    """

    def __init__(self, enabled: bool = True, config: Optional[Any] = None):
        self.enabled = enabled
        self.config = config
        self.workflow_id = str(uuid.uuid4())  # Unique ID for this workflow execution
        self.steps: List[ChainOfThoughtsStep] = []
        self.workflow_start_time = datetime.now(timezone.utc)
        self.workflow_end_time: Optional[datetime] = None
        self.overall_success: bool = False
        self.final_answer: str = ""

        # Step tracking state - support concurrent steps
        self._active_steps: Dict[str, ChainOfThoughtsStep] = {}  # Active steps by name

        # Performance monitoring
        self.performance_metrics = CoTPerformanceMetrics()
        self._lock = threading.Lock()

        # Step registry
        self.step_registry = get_step_registry()

        # Real-time listener support for streaming step updates
        self._step_listeners: List[Any] = []

        logger.debug(
            f"Enhanced chain of thoughts tracker initialized (enabled={enabled}, workflow_id={self.workflow_id})"
        )

    def start_step(
        self,
        step_name: str,
        step_type: Union[str, StepType] = None,
        reasoning: str = "",
        input_summary: str = "",
    ) -> Optional[ChainOfThoughtsStep]:
        """
        Start tracking a new workflow step.

        Args:
            step_name: Name of the workflow step
            step_type: Type of step (auto-detected if None)
            reasoning: Initial reasoning for why this step is needed
            input_summary: Summary of inputs being processed

        Returns:
            ChainOfThoughtsStep: The created step object, or None if disabled
        """
        if not self.enabled:
            return None

        with self._lock:
            # Get step info from registry
            step_info = self.step_registry.get_step_info(step_name)

            # Use provided step_type or get from registry
            if step_type is None:
                step_type = step_info.step_type
            elif isinstance(step_type, str):
                try:
                    step_type = StepType(step_type)
                except ValueError:
                    logger.warning(
                        f"Unknown step type '{step_type}', using registry default"
                    )
                    step_type = step_info.step_type

            # Use template reasoning if available and no custom reasoning provided
            if not reasoning and step_info.reasoning_template:
                reasoning = step_info.reasoning_template.get("start", "")

            step = ChainOfThoughtsStep(
                step_name=step_name,
                step_type=step_type,
                status=StepStatus.STARTED,
                start_time=datetime.now(timezone.utc),
                reasoning=reasoning
                or step_info.reasoning_template
                or f"Executing {step_name}",
                input_summary=(
                    input_summary[: self.config.max_reasoning_length]
                    if input_summary
                    else ""
                ),
            )

            # Add to active steps dictionary (supports concurrent execution)
            self._active_steps[step_name] = step
            self.steps.append(step)
            self.performance_metrics.step_count += 1

            logger.debug(f"Started tracking step: {step_name} ({step_type.value})")
            return step

    def _resolve_step_to_complete(self, step_name: str):
        """Return (step, resolved_name) for the step to complete, or (None, None) on failure."""
        if step_name:
            step = self._active_steps.get(step_name)
            if not step:
                logger.warning(
                    f"Attempted to complete step '{step_name}' but it is not active"
                )
                return None, None
            return step, step_name

        if not self._active_steps:
            logger.warning(
                "Attempted to complete step but no steps are currently active"
            )
            return None, None

        step = list(self._active_steps.values())[-1]
        return step, step.step_name

    def complete_current_step(
        self,
        step_name: str = None,
        reasoning: str = "",
        output_summary: str = "",
        details: Dict[str, Any] = None,
        confidence_score: float = None,
        error_message: str = None,
    ) -> None:
        """Complete an active step by name (supports concurrent steps).

        Args:
            step_name: Name of the step to complete. If None, completes the most recently started step.
            reasoning: Completion reasoning
            output_summary: Summary of outputs
            details: Additional details
            confidence_score: Confidence score for this step
            error_message: Error message if step failed
        """
        if not self.enabled:
            return

        with self._lock:
            step, step_name = self._resolve_step_to_complete(step_name)
            if step is None:
                return

            # Get step info for template reasoning
            step_info = self.step_registry.get_step_info(step_name)

            # Use template reasoning if available and no custom reasoning provided
            if not reasoning and step_info.reasoning_template:
                if error_message:
                    reasoning = step_info.reasoning_template.get("failure", "").format(
                        error=error_message
                    )
                else:
                    reasoning = step_info.reasoning_template.get("success", "")

            # Update step with completion details
            step.complete(
                reasoning=(
                    reasoning[: self.config.max_reasoning_length]
                    if reasoning
                    else step.reasoning
                ),
                output_summary=(
                    output_summary[: self.config.max_reasoning_length]
                    if output_summary
                    else ""
                ),
                details=details,
                confidence_score=(
                    confidence_score if confidence_score is not None else 0.9
                ),
                error_message=error_message,
            )

            # Notify listeners immediately for real-time streaming
            self._notify_step_listeners(step)

            # Remove from active steps
            self._active_steps.pop(step_name, None)

            # Update performance metrics
            step_duration = step.duration_ms or 0
            self.performance_metrics.total_tracking_time_ms += step_duration
            self.performance_metrics.calculate_average_step_time()

            logger.debug(
                f"Completed step: {step.step_name} ({step.status.value}) in {step_duration:.1f}ms"
            )

    def add_step_detail(self, step_name: str, key: str, value: Any) -> None:
        """Add a detail to an active step.

        Args:
            step_name: Name of the step to add detail to
            key: Detail key
            value: Detail value
        """
        if not self.enabled:
            return

        step = self._active_steps.get(step_name)
        if not step:
            logger.warning(f"Cannot add detail: step '{step_name}' is not active")
            return

        step.details[key] = value

    def skip_step(self, step_name: str, reason: str) -> None:
        """Record that a step was skipped."""
        if not self.enabled:
            return

        with self._lock:
            step_info = self.step_registry.get_step_info(step_name)

            step = ChainOfThoughtsStep(
                step_name=step_name,
                step_type=step_info.step_type,
                status=StepStatus.SKIPPED,
                start_time=datetime.now(timezone.utc),
                reasoning=f"Step skipped: {reason}",
            )
            step.end_time = step.start_time
            step.duration_ms = 0

            self.steps.append(step)
            self.performance_metrics.step_count += 1
            logger.debug(f"Recorded skipped step: {step_name} - {reason}")

    def register_step_listener(self, listener: Any):
        """Register a listener to receive real-time step completion notifications.

        Args:
            listener: Callable that accepts a step dict with step data
        """
        with self._lock:
            if listener not in self._step_listeners:
                self._step_listeners.append(listener)
                logger.debug(f"Registered step listener: {listener}")

    def unregister_step_listener(self, listener: Any):
        """Unregister a previously registered step listener."""
        with self._lock:
            if listener in self._step_listeners:
                self._step_listeners.remove(listener)
                logger.debug(f"Unregistered step listener: {listener}")

    def _notify_step_listeners(self, step: ChainOfThoughtsStep):
        """Notify all registered listeners that a step has completed.

        This is called immediately when a step completes to enable real-time streaming.
        Thread-safe notification from within locked section.
        """
        if not self._step_listeners:
            return

        # Convert step to dict for serialization (inside lock is fine, it's just dict conversion)
        step_data = step.to_dict()

        # Notify all listeners - make a copy to avoid modification during iteration
        for listener in tuple(self._step_listeners):
            try:
                listener(step_data)
            except Exception as e:
                logger.error(f"Error notifying step listener: {e}", exc_info=True)

    def finalize_workflow(self, success: bool, final_answer: str = "") -> None:
        """Finalize the entire workflow tracking."""
        if not self.enabled:
            return

        with self._lock:
            self.workflow_end_time = datetime.now(timezone.utc)
            self.overall_success = success
            self.final_answer = final_answer

            # Complete any remaining active steps
            for step_name, step in self._active_steps.copy().items():
                if step.status == StepStatus.STARTED:
                    logger.warning(
                        f"Finalizing workflow with active step '{step_name}' - auto-completing"
                    )
                    step.complete(
                        error_message="Workflow completed before step finished"
                    )
            self._active_steps.clear()

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

        with self._lock:
            total_duration = 0
            if self.workflow_end_time:
                total_duration = (
                    self.workflow_end_time - self.workflow_start_time
                ).total_seconds() * 1000

            step_summary = []
            for step in self.steps:
                step_summary.append(
                    {
                        "name": step.step_name,
                        "type": step.step_type.value,
                        "status": step.status.value,
                        "duration_ms": step.duration_ms,
                        "reasoning": step.reasoning[: DisplayLimits.QUESTION_PREVIEW]
                        + (
                            "..."
                            if len(step.reasoning) > DisplayLimits.QUESTION_PREVIEW
                            else ""
                        ),
                        "confidence": step.confidence_score,
                    }
                )

            return {
                "enabled": True,
                "workflow_id": self.workflow_id,
                "total_steps": len(self.steps),
                "successful_steps": len(
                    [s for s in self.steps if s.status == StepStatus.COMPLETED]
                ),
                "failed_steps": len(
                    [s for s in self.steps if s.status == StepStatus.FAILED]
                ),
                "skipped_steps": len(
                    [s for s in self.steps if s.status == StepStatus.SKIPPED]
                ),
                "total_duration_ms": total_duration,
                "overall_success": self.overall_success,
                "performance_metrics": {
                    "total_tracking_time_ms": self.performance_metrics.total_tracking_time_ms,
                    "average_step_time_ms": self.performance_metrics.average_step_time_ms,
                    "step_count": self.performance_metrics.step_count,
                },
                "steps": step_summary,
            }

    def get_detailed_chain(self) -> List[Dict[str, Any]]:
        """Get the complete detailed chain of thoughts."""
        if not self.enabled:
            return []

        with self._lock:
            return [step.to_dict() for step in self.steps]

    def get_step_by_name(self, step_name: str) -> Optional[ChainOfThoughtsStep]:
        """Get a specific step by name."""
        with self._lock:
            for step in self.steps:
                if step.step_name == step_name:
                    return step
            return None


class StepTracker:
    """Context manager for safer step tracking."""

    def __init__(
        self,
        cot_tracker: Optional[EnhancedChainOfThoughtsTracker],
        step_name: str,
        step_type: Union[str, StepType] = None,
        reasoning: str = "",
        input_summary: str = "",
    ):
        self.cot_tracker = cot_tracker
        self.step_name = step_name
        self.step_type = step_type
        self.reasoning = reasoning
        self.input_summary = input_summary
        self.step = None

    def __enter__(self):
        if self.cot_tracker:
            self.step = self.cot_tracker.start_step(
                self.step_name, self.step_type, self.reasoning, self.input_summary
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cot_tracker and self.step:
            if exc_type:
                self.cot_tracker.complete_current_step(error_message=str(exc_val))
            else:
                self.cot_tracker.complete_current_step()

    def add_detail(self, key: str, value: Any) -> None:
        """Add detail to the current step."""
        if self.cot_tracker:
            self.cot_tracker.add_step_detail(key, value)


def _resolve_cot_tracker(args, kwargs):
    """Find a CoT tracker from method args or a 'state' keyword argument."""
    if args and hasattr(args[0], "_cot_tracker"):
        return args[0]._cot_tracker
    state = kwargs.get("state")
    if state is not None:
        if isinstance(state, dict) and "_cot_tracker" in state:
            return state["_cot_tracker"]
        if hasattr(state, "_cot_tracker"):
            return state._cot_tracker
    return None


def track_step(
    step_name: str,
    step_type: Union[str, StepType] = None,
    reasoning: str = "",
    input_summary: str = "",
):
    """
    Decorator for automatic step tracking.

    Args:
        step_name: Name of the step being tracked
        step_type: Type of step (auto-detected if None)
        reasoning: Initial reasoning for the step
        input_summary: Summary of inputs

    Usage:
        @track_step("generate_sql", "generation")
        def generate_sql(self, state):
            # Step logic here
            pass
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cot_tracker = _resolve_cot_tracker(args, kwargs)
            with StepTracker(
                cot_tracker, step_name, step_type, reasoning, input_summary
            ):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def _validate_max_reasoning_length(config: Any, errors: List[str]) -> None:
    """Append errors for max_reasoning_length field if present and invalid."""
    if not hasattr(config, "max_reasoning_length"):
        return
    if not isinstance(config.max_reasoning_length, int):
        errors.append("'max_reasoning_length' must be an integer")
    elif config.max_reasoning_length < 50:
        errors.append("'max_reasoning_length' must be at least 50")
    elif config.max_reasoning_length > 5000:
        errors.append("'max_reasoning_length' should not exceed 5000")


def _validate_display_preferences(config: Any, errors: List[str]) -> None:
    """Append errors for display_preferences field if present and invalid."""
    if not hasattr(config, "display_preferences"):
        return
    if not isinstance(config.display_preferences, dict):
        errors.append("'display_preferences' must be a dictionary")
        return
    for key, value in config.display_preferences.items():
        if not isinstance(value, bool):
            errors.append(f"display_preferences.{key} must be boolean")


def validate_cot_config(config: Any) -> List[str]:
    """
    Validate chain of thoughts configuration.

    Args:
        config: ChainOfThoughtsConfig instance

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    if not hasattr(config, "enabled"):
        errors.append("Missing 'enabled' field in chain_of_thoughts config")
        return errors

    if not isinstance(config.enabled, bool):
        errors.append("'enabled' field must be boolean")

    _validate_max_reasoning_length(config, errors)
    _validate_display_preferences(config, errors)

    return errors


def initialize_default_steps() -> None:
    """Initialize the step registry with default workflow steps."""
    registry = get_step_registry()

    # Define default steps with their types and reasoning templates
    default_steps = {
        "parse_question": {
            "type": StepType.ANALYSIS,
            "template": {
                "start": "Analyzing the natural language question to identify relevant database tables and columns",
                "success": "Successfully identified {table_count} relevant tables and extracted key information",
                "failure": "Failed to parse the question due to: {error}",
            },
            "description": "Parse and analyze user question to identify relevant database elements",
        },
        "get_unique_nouns": {
            "type": StepType.ANALYSIS,
            "template": {
                "start": "Extracting unique values from relevant columns to improve query accuracy",
                "success": "Found {noun_count} unique values that will help generate precise SQL",
                "failure": "Could not extract unique nouns: {error}",
            },
            "description": "Extract unique values from database columns for better query generation",
        },
        "generate_sql": {
            "type": StepType.GENERATION,
            "template": {
                "start": "Generating SQL query based on question analysis and database schema",
                "success": "Generated SQL query with {complexity} complexity targeting {tables}",
                "failure": "SQL generation failed: {error}",
            },
            "description": "Generate SQL query from natural language question",
        },
        "validate_and_fix_sql": {
            "type": StepType.VALIDATION,
            "template": {
                "start": "Validating generated SQL for syntax, safety, and optimization opportunities",
                "success": "SQL validated successfully{fixes}",
                "failure": "SQL validation failed: {error}",
            },
            "description": "Validate and fix SQL query for correctness and safety",
        },
        "execute_sql": {
            "type": StepType.EXECUTION,
            "template": {
                "start": "Executing validated SQL query against the database",
                "success": "Query executed successfully, returned {row_count} rows in {duration}ms",
                "failure": "Query execution failed: {error}",
            },
            "description": "Execute SQL query against the database",
        },
        "format_results": {
            "type": StepType.FORMATTING,
            "template": {
                "start": "Formatting query results into a comprehensive natural language response",
                "success": "Formatted results into {format_type} with {insight_count} key insights",
                "failure": "Result formatting failed: {error}",
            },
            "description": "Format query results into natural language response",
        },
        "choose_visualization": {
            "type": StepType.ANALYSIS,
            "template": {
                "start": "Analyzing data characteristics to recommend optimal visualization",
                "success": "Recommended {chart_type} visualization based on {criteria}",
                "failure": "Visualization selection failed: {error}",
            },
            "description": "Analyze data and recommend appropriate visualization type",
        },
        "format_data_for_visualization": {
            "type": StepType.FORMATTING,
            "template": {
                "start": "Transforming query results into chart-ready data format",
                "success": "Formatted {data_points} data points for {chart_type} chart",
                "failure": "Data formatting for visualization failed: {error}",
            },
            "description": "Transform query results into visualization-ready format",
        },
        "generate_followup_questions": {
            "type": StepType.GENERATION,
            "template": {
                "start": "Generating strategic follow-up questions based on results and context",
                "success": "Generated {question_count} relevant follow-up questions",
                "failure": "Follow-up question generation failed: {error}",
            },
            "description": "Generate strategic follow-up questions for deeper analysis",
        },
    }

    # Register all default steps
    for step_name, step_config in default_steps.items():
        registry.register_step(
            name=step_name,
            step_type=step_config["type"],
            reasoning_template=step_config["template"],
            description=step_config["description"],
        )

    logger.info(f"Initialized {len(default_steps)} default workflow steps")


# Initialize default steps when module is imported
initialize_default_steps()
