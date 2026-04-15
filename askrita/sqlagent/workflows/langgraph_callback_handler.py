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
#   pydantic (MIT)

"""
LangGraph Callback Handler for Chain-of-Thoughts Integration

This module provides a callback handler that bridges LangGraph's native event system
with AskRITA's Chain-of-Thoughts tracking, enabling real-time progress updates and
detailed step-by-step execution visibility.
"""

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Union
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from pydantic import BaseModel, Field

from ...utils.constants import DisplayLimits

logger = logging.getLogger(__name__)


class StepTrackingState(BaseModel):
    """Runtime metadata tracked for each workflow step."""

    step_name: str
    start_time: float
    status: str
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Optional[Dict[str, Any]] = None
    duration_ms: Optional[int] = None
    output_summary: Optional[str] = None
    error_message: Optional[str] = None


class LLMTokenUsage(BaseModel):
    """Token accounting for a single LLM invocation."""

    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class CallbackEvent(BaseModel):
    """Base event structure dispatched to Chain-of-Thought listeners."""

    event_type: str
    run_id: str
    timestamp: Optional[float] = None


class StepEvent(CallbackEvent):
    """Event associated with a named workflow step."""

    step_name: str


class StepStartedEvent(StepEvent):
    """Emitted when a workflow step begins execution."""

    pass


class StepCompletedEvent(StepEvent):
    """Emitted when a workflow step finishes successfully."""

    status: str
    duration_ms: int
    output_summary: Optional[str] = None


class StepFailedEvent(StepEvent):
    """Emitted when a workflow step fails with an error."""

    status: str
    duration_ms: int
    error_message: str


class LLMEvent(CallbackEvent):
    """Captures token usage and output from a single LLM invocation."""

    model: Optional[str] = None
    tokens: Optional[LLMTokenUsage] = None
    output_preview: Optional[str] = None
    error_message: Optional[str] = None


class ToolEvent(CallbackEvent):
    """Captures input/output from a tool call (e.g., database query)."""

    tool_name: Optional[str] = None
    input_preview: Optional[str] = None
    output_preview: Optional[str] = None
    error_message: Optional[str] = None


class ChainOfThoughtsCallbackHandler(BaseCallbackHandler):
    """
    LangGraph callback handler that captures workflow events and transforms them
    into Chain-of-Thoughts data for the Emma UI.

    This handler captures:
    - Node execution (workflow steps)
    - LLM calls (reasoning generation)
    - Tool calls (database queries, validation)
    - Errors and retries
    - Timing and performance metrics

    Usage:
        handler = ChainOfThoughtsCallbackHandler(
            cot_tracker=workflow._cot_tracker,
            progress_callback=workflow.progress_callback
        )
        result = compiled_graph.invoke(state, config={"callbacks": [handler]})
    """

    def __init__(
        self,
        cot_tracker=None,
        progress_callback=None,
        cot_listeners: Optional[List[Callable[[Dict[str, Any]], None]]] = None,
        enable_streaming: bool = True,
    ):
        """
        Initialize the callback handler.

        Args:
            cot_tracker: EnhancedChainOfThoughtsTracker instance for step tracking
            progress_callback: Optional callback function for progress updates
            cot_listeners: Optional list of listener functions for real-time events
            enable_streaming: Whether to enable real-time event streaming (default: True)
        """
        super().__init__()
        self.cot_tracker = cot_tracker
        self.progress_callback = progress_callback
        self.cot_listeners = cot_listeners or []
        self.enable_streaming = enable_streaming

        # Track active steps and their metadata
        self._active_steps: Dict[str, StepTrackingState] = {}
        self._step_start_times: Dict[str, float] = {}
        self._llm_tokens: Dict[str, LLMTokenUsage] = {}
        # Track concise reasoning breadcrumbs for ReasoningSummary
        self._breadcrumbs: List[str] = []

        logger.info(
            "ChainOfThoughtsCallbackHandler initialized with streaming=%s",
            enable_streaming,
        )

    # =========================================================================
    # CHAIN/WORKFLOW EVENTS
    # =========================================================================

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Called when a chain (workflow node) starts execution.

        This maps to workflow steps like parse_question, generate_sql, etc.
        """
        try:
            # Handle case where serialized might be None
            if serialized is None:
                serialized = {}

            # Handle case where inputs might be None
            if inputs is None:
                inputs = {}

            chain_name = (
                serialized.get("name", "unknown")
                if isinstance(serialized, dict)
                else "unknown"
            )

            # Extract step name from chain name or metadata
            step_name = self._extract_step_name(chain_name, metadata, tags)

            if step_name:
                run_id_key = str(run_id)
                start_time = time.time()
                self._step_start_times[run_id_key] = start_time

                logger.debug(f"Chain started: {step_name} (run_id={run_id})")

                # Initialize active step tracking
                self._active_steps[run_id_key] = StepTrackingState(
                    step_name=step_name,
                    start_time=start_time,
                    status="running",
                    inputs=inputs or {},
                )

                # Notify CoT tracker if enabled
                if self.cot_tracker and hasattr(self.cot_tracker, "start_step"):
                    try:
                        self.cot_tracker.start_step(
                            step_name=step_name,
                            step_type=self._infer_step_type(step_name),
                            reasoning=f"Starting {step_name}...",
                            input_summary=self._summarize_inputs(inputs),
                        )
                    except Exception as e:
                        logger.warning(f"Failed to notify CoT tracker: {e}")

                # Stream event to listeners
                if self.enable_streaming:
                    self._stream_event(
                        StepStartedEvent(
                            event_type="step_started",
                            step_name=step_name,
                            run_id=run_id_key,
                            timestamp=time.time(),
                        )
                    )
        except Exception as e:
            # Log the error but don't break the workflow
            logger.error(
                f"Error in ChainOfThoughtsCallbackHandler.on_chain_start callback: {e}",
                exc_info=True,
            )

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """
        Called when a chain (workflow node) completes successfully.
        """
        try:
            # Handle case where outputs might be None
            if outputs is None:
                outputs = {}

            run_id_str = str(run_id)

            if run_id_str in self._active_steps:
                step_state = self._active_steps[run_id_str]
                step_name = step_state.step_name
                start_time = step_state.start_time
                duration_ms = int((time.time() - start_time) * 1000)

                logger.debug(f"Chain completed: {step_name} in {duration_ms}ms")

                # Extract key outputs for summary
                output_summary = self._summarize_outputs(outputs, step_name)

                # Update active step
                self._active_steps[run_id_str] = step_state.model_copy(
                    update={
                        "status": "completed",
                        "duration_ms": duration_ms,
                        "outputs": outputs,
                        "output_summary": output_summary,
                    }
                )

                # Add concise breadcrumb for ReasoningSummary (user-safe, high-level)
                concise_reasoning = self._get_concise_reasoning(
                    step_name, output_summary
                )
                if concise_reasoning:
                    self._breadcrumbs.append(concise_reasoning)

                # Notify CoT tracker if enabled
                if self.cot_tracker and hasattr(self.cot_tracker, "complete_step"):
                    try:
                        self.cot_tracker.complete_step(
                            reasoning=f"Completed {step_name}",
                            output_summary=output_summary,
                            details=self._extract_step_details(outputs, step_name),
                        )
                    except Exception as e:
                        logger.warning(f"Failed to complete CoT step: {e}")

                # Stream event to listeners
                if self.enable_streaming:
                    self._stream_event(
                        StepCompletedEvent(
                            event_type="step_completed",
                            step_name=step_name,
                            status="completed",
                            duration_ms=duration_ms,
                            output_summary=output_summary,
                            run_id=run_id_str,
                            timestamp=time.time(),
                        )
                    )

                # Clean up
                del self._active_steps[run_id_str]
                if run_id_str in self._step_start_times:
                    del self._step_start_times[run_id_str]
        except Exception as e:
            # Log the error but don't break the workflow
            logger.error(
                f"Error in ChainOfThoughtsCallbackHandler.on_chain_end callback: {e}",
                exc_info=True,
            )

    def on_chain_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """
        Called when a chain (workflow node) encounters an error.
        """
        run_id_str = str(run_id)

        if run_id_str in self._active_steps:
            step_state = self._active_steps[run_id_str]
            step_name = step_state.step_name
            start_time = step_state.start_time
            duration_ms = int((time.time() - start_time) * 1000)

            error_message = str(error)
            logger.error(f"Chain error in {step_name}: {error_message}")

            # Update active step
            self._active_steps[run_id_str] = step_state.model_copy(
                update={
                    "status": "failed",
                    "duration_ms": duration_ms,
                    "error_message": error_message,
                }
            )

            # Notify CoT tracker if enabled
            if self.cot_tracker and hasattr(self.cot_tracker, "fail_step"):
                try:
                    self.cot_tracker.fail_step(
                        error_message=error_message,
                        details={"exception_type": type(error).__name__},
                    )
                except Exception as e:
                    logger.warning(f"Failed to mark CoT step as failed: {e}")

            # Stream event to listeners
            if self.enable_streaming:
                self._stream_event(
                    StepFailedEvent(
                        event_type="step_failed",
                        step_name=step_name,
                        status="failed",
                        duration_ms=duration_ms,
                        error_message=error_message,
                        run_id=run_id_str,
                        timestamp=time.time(),
                    )
                )

            # Clean up
            del self._active_steps[run_id_str]

    # =========================================================================
    # LLM EVENTS (Reasoning Generation)
    # =========================================================================

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Called when an LLM call starts.

        Useful for tracking reasoning generation and capturing prompts.
        """
        try:
            # Handle case where serialized might be None
            if serialized is None:
                serialized = {}

            llm_name = (
                serialized.get("name", "unknown_llm")
                if isinstance(serialized, dict)
                else "unknown_llm"
            )

            logger.debug(f"LLM call started: {llm_name} (run_id={run_id})")

            # Track LLM metadata
            self._llm_tokens[str(run_id)] = LLMTokenUsage(model=llm_name)

            # Optionally stream LLM start event
            if self.enable_streaming:
                self._stream_event(
                    LLMEvent(
                        event_type="llm_started",
                        model=llm_name,
                        run_id=str(run_id),
                        timestamp=time.time(),
                    )
                )
        except Exception as e:
            # Log the error but don't break the workflow
            logger.error(
                f"Error in ChainOfThoughtsCallbackHandler.on_llm_start callback: {e}",
                exc_info=True,
            )

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """
        Called when an LLM call completes.

        Captures token usage and reasoning output.
        """
        run_id_str = str(run_id)

        # Extract token usage if available
        if response.llm_output and "token_usage" in response.llm_output:
            token_usage = response.llm_output["token_usage"]
            if run_id_str in self._llm_tokens:
                usage_model = self._llm_tokens[run_id_str]
                self._llm_tokens[run_id_str] = usage_model.model_copy(
                    update={
                        "prompt_tokens": token_usage.get(
                            "prompt_tokens", usage_model.prompt_tokens
                        ),
                        "completion_tokens": token_usage.get(
                            "completion_tokens", usage_model.completion_tokens
                        ),
                        "total_tokens": token_usage.get(
                            "total_tokens", usage_model.total_tokens
                        ),
                    }
                )

        # Extract generated text
        generated_text = ""
        if response.generations and len(response.generations) > 0:
            if len(response.generations[0]) > 0:
                generated_text = response.generations[0][0].text

        token_state = self._llm_tokens.get(run_id_str)
        logger.debug(
            "LLM call completed (run_id=%s, tokens=%s)",
            run_id,
            token_state.model_dump() if token_state else {},
        )

        # Stream LLM completion event
        if self.enable_streaming:
            self._stream_event(
                LLMEvent(
                    event_type="llm_completed",
                    run_id=run_id_str,
                    tokens=token_state,
                    output_preview=(
                        generated_text[: DisplayLimits.INPUT_SUMMARY]
                        if generated_text
                        else None
                    ),
                    timestamp=time.time(),
                )
            )

    def on_llm_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """
        Called when an LLM call fails.
        """
        logger.error(f"LLM error (run_id={run_id}): {error}")

        if self.enable_streaming:
            self._stream_event(
                LLMEvent(
                    event_type="llm_error",
                    run_id=str(run_id),
                    error_message=str(error),
                    timestamp=time.time(),
                )
            )

    # =========================================================================
    # TOOL EVENTS (Database Queries, Validation, etc.)
    # =========================================================================

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Called when a tool (like database query) starts.
        """
        try:
            # Handle case where serialized might be None
            if serialized is None:
                serialized = {}

            # Handle case where input_str might be None
            if input_str is None:
                input_str = ""

            tool_name = (
                serialized.get("name", "unknown_tool")
                if isinstance(serialized, dict)
                else "unknown_tool"
            )
            logger.debug(f"Tool started: {tool_name} (run_id={run_id})")

            if self.enable_streaming:
                self._stream_event(
                    ToolEvent(
                        event_type="tool_started",
                        tool_name=tool_name,
                        input_preview=(
                            input_str[: DisplayLimits.INPUT_SUMMARY]
                            if input_str
                            else ""
                        ),
                        run_id=str(run_id),
                        timestamp=time.time(),
                    )
                )
        except Exception as e:
            # Log the error but don't break the workflow
            logger.error(
                f"Error in ChainOfThoughtsCallbackHandler.on_tool_start callback: {e}",
                exc_info=True,
            )

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """
        Called when a tool completes.
        """
        logger.debug(f"Tool completed (run_id={run_id})")

        if self.enable_streaming:
            self._stream_event(
                ToolEvent(
                    event_type="tool_completed",
                    run_id=str(run_id),
                    output_preview=(
                        output[: DisplayLimits.INPUT_SUMMARY] if output else None
                    ),
                    timestamp=time.time(),
                )
            )

    def on_tool_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """
        Called when a tool fails.
        """
        logger.error(f"Tool error (run_id={run_id}): {error}")

        if self.enable_streaming:
            self._stream_event(
                ToolEvent(
                    event_type="tool_error",
                    run_id=str(run_id),
                    error_message=str(error),
                    timestamp=time.time(),
                )
            )

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _extract_step_name(
        self,
        chain_name: str,
        metadata: Optional[Dict[str, Any]],
        tags: Optional[List[str]],
    ) -> Optional[str]:
        """
        Extract workflow step name from chain name, metadata, or tags.
        """
        # Try metadata first
        if metadata and "step_name" in metadata:
            return metadata["step_name"]

        # Try tags
        if tags:
            for tag in tags:
                if tag.startswith("step:"):
                    return tag.replace("step:", "")

        # Use chain name as fallback (clean up if needed)
        if chain_name and chain_name != "unknown":
            # Remove common prefixes/suffixes
            step_name = chain_name.replace("RunnableLambda", "").replace("Runnable", "")
            step_name = step_name.strip("_")
            return step_name if step_name else None

        return None

    def _infer_step_type(self, step_name: str) -> str:
        """
        Infer step type from step name for categorization.
        """
        step_name_lower = step_name.lower()

        if "parse" in step_name_lower:
            return "analysis"
        elif "generate" in step_name_lower or "create" in step_name_lower:
            return "generation"
        elif "validate" in step_name_lower or "fix" in step_name_lower:
            return "validation"
        elif "execute" in step_name_lower or "run" in step_name_lower:
            return "execution"
        elif "format" in step_name_lower or "visualiz" in step_name_lower:
            return "formatting"
        elif "followup" in step_name_lower:
            return "suggestion"
        else:
            return "processing"

    def _summarize_inputs(self, inputs: Dict[str, Any]) -> str:
        """
        Create a concise summary of step inputs.
        """
        if not inputs:
            return ""

        # Extract key information
        parts = []

        if "question" in inputs:
            question = inputs["question"]
            if isinstance(question, str):
                parts.append(f"Question: {question[:DisplayLimits.QUESTION_PREVIEW]}")

        if "sql_query" in inputs:
            parts.append("SQL query provided")

        if "results" in inputs:
            results = inputs["results"]
            if isinstance(results, list):
                parts.append(f"{len(results)} results")

        return (
            " | ".join(parts) if parts else str(inputs)[: DisplayLimits.INPUT_SUMMARY]
        )

    def _summarize_outputs(self, outputs: Dict[str, Any], step_name: str) -> str:
        """
        Create a concise summary of step outputs based on step type.
        """
        if not outputs:
            return "No output"

        step_name_lower = step_name.lower()

        # Dispatch to specific summarizer based on step type
        if "parse" in step_name_lower:
            return self._summarize_parse_outputs(outputs)
        elif "generate" in step_name_lower and "sql" in step_name_lower:
            return self._summarize_sql_generation_outputs(outputs)
        elif "validate" in step_name_lower:
            return self._summarize_validation_outputs(outputs)
        elif "execute" in step_name_lower:
            return self._summarize_execution_outputs(outputs)
        elif "format" in step_name_lower:
            return self._summarize_format_outputs(outputs)

        # Generic fallback
        return f"Completed with {len(outputs)} outputs"

    def _summarize_parse_outputs(self, outputs: Dict[str, Any]) -> str:
        """Summarize parse question outputs."""
        parsed = outputs.get("parsed_question")
        if isinstance(parsed, dict):
            relevant = parsed.get("is_relevant", False)
            tables = parsed.get("relevant_tables", [])
            return f"Relevant: {relevant}, Tables: {len(tables)}"
        return f"Completed with {len(outputs)} outputs"

    def _summarize_sql_generation_outputs(self, outputs: Dict[str, Any]) -> str:
        """Summarize SQL generation outputs."""
        if "sql_query" in outputs:
            return f"SQL generated: {len(outputs['sql_query'])} chars"
        return f"Completed with {len(outputs)} outputs"

    def _summarize_validation_outputs(self, outputs: Dict[str, Any]) -> str:
        """Summarize SQL validation outputs."""
        if "sql_valid" in outputs:
            return f"Valid: {outputs['sql_valid']}"
        return f"Completed with {len(outputs)} outputs"

    def _summarize_execution_outputs(self, outputs: Dict[str, Any]) -> str:
        """Summarize SQL execution outputs."""
        results = outputs.get("results")
        if isinstance(results, list):
            return f"{len(results)} rows returned"
        return f"Completed with {len(outputs)} outputs"

    def _summarize_format_outputs(self, outputs: Dict[str, Any]) -> str:
        """Summarize formatting outputs."""
        if "answer" in outputs:
            return f"Answer: {outputs['answer'][:DisplayLimits.QUESTION_PREVIEW]}"
        return f"Completed with {len(outputs)} outputs"

    @staticmethod
    def _reasoning_for_parse(output_summary: str) -> str:
        """Return reasoning text for a parse step."""
        summary_lower = output_summary.lower()
        if "not relevant" in summary_lower or "relevant: false" in summary_lower:
            return "Analyzed question relevance to database schema"
        return "Identified relevant database tables and columns"

    @staticmethod
    def _reasoning_for_validate(output_summary: str) -> str:
        """Return reasoning text for a validate step."""
        summary_lower = output_summary.lower()
        if "valid: false" in summary_lower or "corrected" in summary_lower:
            return "Validated and corrected SQL query"
        return "Validated SQL query syntax"

    @staticmethod
    def _reasoning_for_execute(output_summary: str) -> str:
        """Return reasoning text for an execute step."""
        if "rows" in output_summary.lower():
            return f"Executed query and retrieved {output_summary}"
        return "Executed SQL query against database"

    def _get_concise_reasoning(
        self, step_name: str, output_summary: str
    ) -> Optional[str]:
        """
        Generate concise, user-safe reasoning breadcrumb for a completed step.

        Args:
            step_name: Name of the completed step
            output_summary: Summary of step outputs

        Returns:
            Concise reasoning string or None if step should be skipped
        """
        step_name_lower = step_name.lower()

        if any(skip in step_name_lower for skip in ["track", "callback", "internal"]):
            return None

        if "parse" in step_name_lower:
            return self._reasoning_for_parse(output_summary)
        if "generate" in step_name_lower and "sql" in step_name_lower:
            return "Generated SQL query based on question and schema"
        if "validate" in step_name_lower:
            return self._reasoning_for_validate(output_summary)
        if "execute" in step_name_lower:
            return self._reasoning_for_execute(output_summary)
        if "format" in step_name_lower:
            return "Formatted results into natural language response"
        if "visualiz" in step_name_lower:
            return "Selected appropriate visualization type"

        return f"Completed {step_name.replace('_', ' ')}"

    def _extract_step_details(
        self, outputs: Dict[str, Any], step_name: str
    ) -> Dict[str, Any]:
        """
        Extract detailed metadata for Chain-of-Thoughts tracking.
        """
        details = {}

        # Common fields
        for key in ["sql_query", "sql_reason", "sql_valid", "answer", "visualization"]:
            if key in outputs:
                details[key] = outputs[key]

        # Add step-specific details
        results = outputs.get("results")
        if isinstance(results, list):
            details["row_count"] = len(results)

        return details

    def _stream_event(self, event: CallbackEvent) -> None:
        """
        Stream event to registered listeners for real-time updates.
        """
        if not self.enable_streaming or not self.cot_listeners:
            return

        for listener in self.cot_listeners:
            try:
                listener(event.model_dump(exclude_none=True))
            except Exception as e:
                logger.warning(f"Listener error: {e}")

    # =========================================================================
    # PUBLIC METHODS
    # =========================================================================

    def get_active_steps(self) -> Dict[str, StepTrackingState]:
        """
        Get currently active workflow steps.

        Returns:
            Dictionary mapping run_id to step metadata models
        """
        return {
            run_id: state.model_copy(deep=True)
            for run_id, state in self._active_steps.items()
        }

    def get_token_usage(self) -> Dict[str, LLMTokenUsage]:
        """
        Get LLM token usage for all calls.

        Returns:
            Dictionary mapping run_id to token usage models
        """
        return {
            run_id: usage.model_copy(deep=True)
            for run_id, usage in self._llm_tokens.items()
        }

    def get_breadcrumbs(self, max_items: Optional[int] = None) -> List[str]:
        """
        Get concise reasoning breadcrumbs for ReasoningSummary.

        Args:
            max_items: Maximum number of breadcrumbs to return (default: all)

        Returns:
            List of concise, user-safe reasoning steps
        """
        if max_items is None:
            return list(self._breadcrumbs)
        return self._breadcrumbs[-max_items:] if max_items > 0 else []

    def reset(self) -> None:
        """
        Reset handler state (useful between queries).
        """
        self._active_steps.clear()
        self._step_start_times.clear()
        self._llm_tokens.clear()
        self._breadcrumbs.clear()
        logger.debug("Callback handler state reset")
