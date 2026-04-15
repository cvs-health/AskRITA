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
#   langgraph (MIT)
#   pydantic (MIT)

"""
NoSQL Agent Workflow for AskRITA.

Provides a natural-language-to-MongoDB-query workflow that reuses the same
architecture, state model, LLM manager, data formatter, progress tracking,
chain-of-thoughts, PII detection, and visualization pipeline as SQLAgentWorkflow.

The key differences from SQLAgentWorkflow:
  - Uses NoSQLDatabaseManager instead of DatabaseManager
  - Schema is inferred from document sampling instead of SQL DDL
  - LLM generates MongoDB aggregation pipelines instead of SQL queries
  - Query safety validation checks for MongoDB-specific dangerous operations
  - Unique nouns extraction uses MongoDB distinct() instead of SELECT DISTINCT
"""

import logging
import re
from typing import Any, Callable, Dict, List, Optional

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from ...config_manager import ChainOfThoughtsConfig, get_config
from ...exceptions import DatabaseError, LLMError, QueryError, ValidationError
from ...utils.chain_of_thoughts import (
    create_step_reasoning_templates,
    get_step_type,
)
from ...utils.constants import DetailKeys, DisplayLimits, WorkflowSteps
from ...utils.enhanced_chain_of_thoughts import EnhancedChainOfThoughtsTracker
from ...utils.LLMManager import LLMManager
from ...utils.pii_detector import create_pii_detector
from ...utils.token_utils import optimize_context_for_model
from ..database.NoSQLDatabaseManager import NoSQLDatabaseManager
from ..formatters.DataFormatter import DataFormatter, UniversalChartData
from ..progress_tracker import ProgressData, ProgressStatus
from ..State import WorkflowState
from .langgraph_callback_handler import ChainOfThoughtsCallbackHandler

logger = logging.getLogger(__name__)


# =============================================================================
# RESPONSE MODELS (NoSQL-adapted versions)
# =============================================================================


class MongoQueryGenerationResponse(BaseModel):
    """Structured response model for MongoDB query generation.

    The query_command must use the db.collectionName.aggregate([...]) syntax
    that langchain-mongodb's MongoDBDatabase.run() expects.
    """

    query_command: str = Field(
        description=(
            "A MongoDB aggregation command string in the form: "
            "db.collectionName.aggregate([{$match: ...}, {$group: ...}, ...]). "
            "Must use valid MongoDB aggregation pipeline syntax."
        )
    )
    query_reason: str = Field(
        description="Explanation of why this query approach was chosen"
    )


class MongoQueryValidationResponse(BaseModel):
    """Structured response model for MongoDB query validation."""

    valid: bool = Field(description="Whether the MongoDB query is valid")
    corrected_query: str = Field(
        description="The corrected query command if fixes were needed"
    )
    issues: str = Field(description="Description of any issues found", default="")


class TableInfo(BaseModel):
    """Collection/table information structure (reused from SQL workflow)."""

    table_name: str = Field(description="Name of the collection")
    noun_columns: List[str] = Field(
        description="List of fields containing noun values", default_factory=list
    )
    relevance_score: float = Field(
        description="Relevance score from 0.0 to 1.0", default=0.0
    )


class ParseQuestionResponse(BaseModel):
    """Structured response model for question parsing."""

    is_relevant: bool = Field(
        description="Whether the question is relevant to the database"
    )
    relevant_tables: List[TableInfo] = Field(
        description="List of relevant collection information", default_factory=list
    )
    relevance_reason: Optional[str] = Field(
        default=None, description="Brief explanation of relevance"
    )


class FollowupQuestionsResponse(BaseModel):
    """Structured response model for followup questions generation."""

    followup_questions: List[str] = Field(
        description="List of relevant follow-up questions", default_factory=list
    )


class VisualizationResponse(BaseModel):
    """Structured response model for visualization choice."""

    visualization: str = Field(description="Recommended visualization type")
    visualization_reason: str = Field(description="Reason for the visualization choice")


class CombinedVisualizationResponse(BaseModel):
    """Combined response for visualization choice AND data formatting."""

    model_config = {"extra": "forbid"}

    visualization: str = Field(description="Recommended visualization type")
    visualization_reason: str = Field(description="Reason for the visualization choice")
    universal_format: UniversalChartData = Field(
        description="Universal chart data structure"
    )


class ResultsFormattingResponse(BaseModel):
    """Structured response model for results formatting."""

    answer: Optional[str] = Field(
        default=None, description="Short paragraph summarizing results"
    )
    analysis: Optional[str] = Field(default=None, description="Detailed analysis")


# =============================================================================
# NOSQL AGENT WORKFLOW
# =============================================================================


class NoSQLAgentWorkflow:
    """
    NoSQL Agent Workflow for natural-language-to-MongoDB queries.

    Reuses the same architecture as SQLAgentWorkflow:
      - LLMManager for all LLM interactions
      - DataFormatter for visualization data formatting
      - WorkflowState as the shared state model
      - LangGraph StateGraph for workflow orchestration
      - Chain-of-Thoughts tracking
      - PII detection
      - Progress callbacks

    The only differences are:
      - NoSQLDatabaseManager replaces DatabaseManager
      - Query generation produces MongoDB aggregation pipelines instead of SQL
      - Safety validation checks MongoDB-specific operations
    """

    def __init__(
        self,
        config_manager: Any = None,
        test_llm_connection: bool = True,
        test_db_connection: bool = True,
        init_schema_cache: bool = True,
        progress_callback: Optional[Callable] = None,
    ):
        """
        Initialize NoSQLAgentWorkflow.

        Args:
            config_manager: Optional ConfigManager instance.
            test_llm_connection: Whether to test LLM connection during init.
            test_db_connection: Whether to test database connection during init.
            init_schema_cache: Whether to preload schema cache during init.
            progress_callback: Optional callback for progress tracking.
        """
        self.config = config_manager or get_config()

        # Store progress callback
        self.progress_callback = progress_callback
        self._chain_of_thoughts_config = getattr(
            self.config, "chain_of_thoughts", ChainOfThoughtsConfig()
        )
        self._cot_tracker: Optional[EnhancedChainOfThoughtsTracker] = None
        self._cot_listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._reasoning_templates = create_step_reasoning_templates()
        self._last_callback_handler: Optional[ChainOfThoughtsCallbackHandler] = None

        logger.info("🚀 Initializing NoSQL Agent Workflow components...")
        self.db_manager = NoSQLDatabaseManager(
            self.config, test_db_connection=test_db_connection
        )
        self.llm_manager = LLMManager(self.config, test_connection=test_llm_connection)
        self.data_formatter = DataFormatter(
            self.config, test_llm_connection=test_llm_connection
        )

        # Initialize PII detector if enabled
        self.pii_detector = create_pii_detector(self.config.pii_detection)
        if self.pii_detector:
            logger.info(
                "🔒 PII detection enabled - queries will be scanned for PHI/PII"
            )

        logger.info("✅ All NoSQL Agent Workflow components initialized successfully")

        # Cache schema at workflow level
        self._workflow_schema_cache: Optional[str] = None
        self._workflow_schema_cache_time = None

        # Create and compile the workflow
        logger.info("Creating and compiling NoSQL agent workflow during initialization")
        self._compiled_graph = self._create_workflow().compile()
        logger.info("NoSQL agent workflow compiled and ready for use")

        # Preload schema cache
        if init_schema_cache:
            self.preload_schema()

    # =========================================================================
    # PUBLIC API (mirrors SQLAgentWorkflow)
    # =========================================================================

    def query(self, question: str) -> WorkflowState:
        """
        Query the database using natural language.

        Args:
            question: Natural language question

        Returns:
            WorkflowState with answer, results, visualization, etc.
        """
        if not isinstance(question, str):
            raise ValidationError("Question must be a string")
        if not question.strip():
            raise ValidationError("Question cannot be empty")

        return self._execute_query(question)

    def chat(self, messages: list) -> WorkflowState:
        """
        Chat interface for conversational queries.

        Args:
            messages: List of conversation messages

        Returns:
            WorkflowState with answer, results, visualization, etc.
        """
        if not messages or not isinstance(messages, list):
            raise ValidationError("Messages must be a non-empty list")

        current_question = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                current_question = msg.get("content", "")
                break

        if not current_question or not current_question.strip():
            raise ValidationError("No user question found in messages")

        return self._execute_query(current_question, messages=messages)

    def preload_schema(self) -> None:
        """Preload schema cache during initialization."""
        logger.info("Preloading NoSQL schema cache...")
        try:
            schema = self._get_cached_schema()
            logger.info(
                f"✅ Schema cache preloaded successfully ({len(schema)} characters)"
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to preload schema cache: {e}")

    @property
    def schema(self) -> str:
        """Get the cached database schema."""
        return self._get_cached_schema()

    def clear_schema_cache(self) -> None:
        """Manually clear the workflow schema cache."""
        if self._workflow_schema_cache is not None:
            logger.info("Manually clearing workflow schema cache")
            self._workflow_schema_cache = None
            self._workflow_schema_cache_time = None

    def get_graph(self):
        """Get the compiled workflow graph."""
        return self._compiled_graph

    def register_cot_listener(self, listener: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback that receives Chain of Thoughts updates."""
        if listener not in self._cot_listeners:
            self._cot_listeners.append(listener)

    def unregister_cot_listener(
        self, listener: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Unregister a previously registered Chain of Thoughts listener."""
        if listener in self._cot_listeners:
            self._cot_listeners.remove(listener)

    def clear_cot_listeners(self) -> None:
        """Clear all registered Chain of Thoughts listeners."""
        self._cot_listeners.clear()

    # =========================================================================
    # INTERNAL: Schema caching (same pattern as SQLAgentWorkflow)
    # =========================================================================

    def _get_cached_schema(self) -> str:
        """Get database schema with time-based caching."""
        from datetime import datetime

        if (
            self._workflow_schema_cache is not None
            and self._workflow_schema_cache_time is not None
            and self.config.database.cache_schema
        ):
            elapsed = (
                datetime.now() - self._workflow_schema_cache_time
            ).total_seconds()
            if elapsed < self.config.database.schema_refresh_interval:
                logger.debug(
                    f"Using workflow-level cached schema (age: {elapsed:.1f}s)"
                )
                return self._workflow_schema_cache
            else:
                logger.info(f"Workflow schema cache expired after {elapsed:.1f}s")
                self._workflow_schema_cache = None
                self._workflow_schema_cache_time = None

        logger.debug("Fetching fresh schema from NoSQLDatabaseManager")
        schema = self.db_manager.get_schema()

        if self.config.database.cache_schema:
            self._workflow_schema_cache = schema
            self._workflow_schema_cache_time = datetime.now()

        return schema

    # =========================================================================
    # INTERNAL: Progress & Chain-of-Thoughts tracking (reused from SQL workflow)
    # =========================================================================

    def _track_step(self, step_name: str, details: dict = None, step_data: dict = None):
        """Track step execution with optional progress callback."""
        cot_enabled = self._cot_tracker is not None and getattr(
            self._cot_tracker, "enabled", False
        )
        if cot_enabled:
            reasoning_template = self._reasoning_templates.get(step_name, {})
            input_summary = ""
            if details:
                question_preview = details.get("question")
                if isinstance(question_preview, str):
                    input_summary = (
                        f"Question: {question_preview[:DisplayLimits.QUESTION_PREVIEW]}"
                    )
                elif details.get("step_inputs") is not None:
                    input_summary = str(details["step_inputs"])[
                        : DisplayLimits.INPUT_SUMMARY
                    ]
            try:
                self._cot_tracker.start_step(
                    step_name=step_name,
                    step_type=get_step_type(step_name),
                    reasoning=reasoning_template.get("start", f"Executing {step_name}"),
                    input_summary=input_summary,
                )
            except Exception:
                logger.exception(
                    "Failed to start chain-of-thought step '%s'", step_name
                )

        if self.progress_callback:
            progress_data = ProgressData(
                step_name=step_name,
                status=ProgressStatus.STARTED,
                step_data=step_data or {},
            )
            try:
                self.progress_callback(progress_data)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

        return step_name

    @staticmethod
    def _build_combined_details(details: dict, step_data: dict) -> Dict[str, Any]:
        """Merge step details and step_data into a single dict."""
        combined: Dict[str, Any] = {}
        if details:
            combined.update(details)
        if step_data:
            combined.setdefault("progress_data", step_data)
        return combined

    @staticmethod
    def _extract_output_summary(combined_details: Dict[str, Any]) -> str:
        """Return a truncated output summary from combined step details."""
        if "output" in combined_details:
            return str(combined_details["output"])[:DisplayLimits.INPUT_SUMMARY]
        if "answer" in combined_details:
            return str(combined_details["answer"])[:DisplayLimits.INPUT_SUMMARY]
        return ""

    def _complete_cot_step(
        self,
        step_name: str,
        error: Optional[str],
        combined_details: Dict[str, Any],
        output_summary: str,
    ) -> None:
        """Call complete_current_step on the CoT tracker for success or failure."""
        reasoning_template = self._reasoning_templates.get(step_name, {})
        try:
            if error:
                self._cot_tracker.complete_current_step(
                    step_name=step_name,
                    reasoning=reasoning_template.get("failure", f"{step_name} failed: {error}"),
                    output_summary=output_summary,
                    details=combined_details,
                    confidence_score=0.0,
                    error_message=error,
                )
            else:
                self._cot_tracker.complete_current_step(
                    step_name=step_name,
                    reasoning=reasoning_template.get("success", f"Completed {step_name}"),
                    output_summary=output_summary,
                    details=combined_details,
                    confidence_score=0.9,
                )
        except Exception:
            logger.exception(
                "Failed to complete chain-of-thought step '%s'", step_name
            )

    def _complete_step(
        self,
        step_name: str,
        details: dict = None,
        error: str = None,
        step_data: dict = None,
    ):
        """Complete step tracking."""
        if self.progress_callback:
            status = ProgressStatus.FAILED if error else ProgressStatus.COMPLETED
            progress_data = ProgressData(
                step_name=step_name,
                status=status,
                error=error,
                step_data=step_data or {},
            )
            try:
                self.progress_callback(progress_data)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

        cot_enabled = self._cot_tracker is not None and getattr(
            self._cot_tracker, "enabled", False
        )
        if cot_enabled:
            combined_details = self._build_combined_details(details, step_data)
            output_summary = self._extract_output_summary(combined_details)
            self._complete_cot_step(step_name, error, combined_details, output_summary)
            self._notify_cot_listeners(
                {
                    "event_type": "cot_step_completed",
                    "step_name": step_name,
                    "error": error,
                    "details": combined_details,
                    "progress_data": step_data or {},
                }
            )

    def _notify_cot_listeners(self, event: Dict[str, Any]) -> None:
        """Send Chain of Thoughts events to registered listeners."""
        for listener in tuple(self._cot_listeners):
            try:
                listener(event)
            except Exception:
                logger.exception("Chain of Thoughts listener raised an exception")

    def _finalize_cot(
        self, success: bool, final_answer: str, error: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Finalize Chain of Thoughts tracker."""
        tracker = self._cot_tracker
        if not tracker or not getattr(tracker, "enabled", False):
            return None
        try:
            tracker.finalize_workflow(success=success, final_answer=final_answer)
            cot_payload = {
                "summary": tracker.get_summary(),
                "detailed_steps": tracker.get_detailed_chain(),
                "workflow_id": tracker.workflow_id,
            }
            self._notify_cot_listeners(
                {
                    "event_type": "cot_workflow_completed",
                    "success": success,
                    "error": error,
                    "final_answer": final_answer,
                    "cot": cot_payload,
                }
            )
            return cot_payload
        finally:
            self._cot_tracker = None

    # =========================================================================
    # INTERNAL: Query execution (mirrors SQLAgentWorkflow._execute_query)
    # =========================================================================

    def _validate_question_input(self, question: str) -> None:
        """Validate question length and content against configured rules."""
        validation_settings = (
            getattr(self.config, "get_input_validation_settings", lambda: {})() or {}
        )
        max_q_len = int(validation_settings.get("max_question_length", 10000))
        if len(question) > max_q_len:
            raise ValidationError(f"Question too long (max {max_q_len} characters)")

        suspicious_patterns = validation_settings.get(
            "blocked_substrings", ["<script", "javascript:", "data:", "vbscript:", "@@"]
        )
        question_lower = question.lower()
        for pattern in suspicious_patterns:
            if pattern in question_lower:
                raise ValidationError(
                    f"Question contains potentially unsafe content: {pattern}"
                )

    def _init_cot_tracker(self, question: str) -> None:
        """Initialise (or clear) the Chain of Thoughts tracker for a new query."""
        if self._chain_of_thoughts_config.enabled:
            self._cot_tracker = EnhancedChainOfThoughtsTracker(
                enabled=True, config=self._chain_of_thoughts_config
            )
            self._cot_tracker.question = question.strip()
        else:
            self._cot_tracker = None

    def _create_callback_handler(self) -> Optional[Any]:
        """Create a ChainOfThoughtsCallbackHandler, returning None on failure."""
        try:
            return ChainOfThoughtsCallbackHandler(
                cot_tracker=self._cot_tracker,
                progress_callback=self.progress_callback,
                cot_listeners=self._cot_listeners,
                enable_streaming=True,
            )
        except Exception as e:
            logger.warning(f"Failed to create callback handler: {e}")
            return None

    def _invoke_graph(self, initial_state: WorkflowState, callback_handler) -> dict:
        """Invoke the compiled workflow graph, with or without a callback handler."""
        if callback_handler:
            result = self._compiled_graph.invoke(
                initial_state, config={"callbacks": [callback_handler]}
            )
        else:
            result = self._compiled_graph.invoke(initial_state)
        if not isinstance(result, dict):
            raise QueryError("Workflow returned invalid result format")
        return result

    def _build_workflow_state(self, result: dict, initial_state: WorkflowState) -> WorkflowState:
        """Construct a WorkflowState from the raw graph result dict."""
        return WorkflowState(
            question=result.get("question", initial_state.question),
            answer=result.get("answer", "Unable to generate answer"),
            analysis=result.get("analysis", ""),
            visualization=result.get("visualization", "none"),
            visualization_reason=result.get("visualization_reason", ""),
            sql_query=result.get("sql_query", ""),
            sql_reason=result.get("sql_reason", ""),
            sql_valid=result.get("sql_valid", False),
            sql_issues=result.get("sql_issues", ""),
            results=result.get("results", []),
            followup_questions=result.get("followup_questions", []),
            chart_data=result.get("chart_data", None),
            retry_count=result.get("retry_count", 0),
            execution_error=result.get("execution_error", None),
            messages=result.get("messages", initial_state.messages or []),
        )

    def _attach_cot_to_state(self, workflow_state: WorkflowState) -> WorkflowState:
        """Finalise CoT tracker and attach the payload to the workflow state if present."""
        if not self._cot_tracker:
            return workflow_state
        cot_payload = self._finalize_cot(
            success=workflow_state.execution_error is None,
            final_answer=workflow_state.answer or "",
        )
        if cot_payload is not None:
            state_dict = workflow_state.model_dump()
            state_dict["chain_of_thoughts"] = cot_payload
            return WorkflowState(**state_dict)
        return workflow_state

    @staticmethod
    def _classify_query_error(e: Exception) -> Exception:
        """Map a generic exception to a typed DatabaseError, LLMError, or QueryError."""
        error_msg = str(e).lower()
        if "database" in error_msg or "connection" in error_msg:
            return DatabaseError(f"Database error: {e}")
        if "llm" in error_msg or "api" in error_msg or "openai" in error_msg:
            return LLMError(f"LLM provider error: {e}")
        return QueryError(f"Query processing error: {e}")

    def _execute_query(self, question: str, messages: list = None) -> dict:
        """Common query execution logic for both query() and chat()."""
        self._validate_question_input(question)

        try:
            initial_state = WorkflowState(
                question=question.strip(),
                retry_count=0,
                execution_error=None,
                messages=messages or [],
            )

            self._init_cot_tracker(question)
            callback_handler = self._create_callback_handler()
            result = self._invoke_graph(initial_state, callback_handler)

            workflow_state = self._build_workflow_state(result, initial_state)
            workflow_state = self._attach_cot_to_state(workflow_state)

            self._last_callback_handler = callback_handler
            return workflow_state

        except ValidationError:
            raise
        except Exception as e:
            if self._cot_tracker:
                self._finalize_cot(success=False, final_answer="", error=str(e))
            raise self._classify_query_error(e)
        finally:
            if self._cot_tracker:
                if getattr(self._cot_tracker, "enabled", False):
                    self._finalize_cot(
                        success=False, final_answer="", error="Workflow aborted"
                    )
                self._cot_tracker = None

    # =========================================================================
    # WORKFLOW STEP METHODS
    # =========================================================================

    def pii_detection_step(self, state: WorkflowState) -> dict:
        """PII/PHI detection step - scans user question for personally identifiable information."""
        self._track_step(
            "pii_detection",
            {"question_length": len(state.question) if state.question else 0},
        )

        try:
            if not self.pii_detector:
                logger.debug("PII detection disabled, skipping step")
                return {}

            logger.info("🔍 Scanning user question for PII/PHI content")
            pii_result = self.pii_detector.detect_pii_in_text(
                state.question, context="user_query"
            )

            if pii_result.has_pii:
                entity_summary = ", ".join(pii_result.entity_types)
                logger.warning(f"⚠️  PII detected: {entity_summary}")

                if pii_result.blocked:
                    logger.error("🚫 Query blocked due to PII detection")
                    return {
                        "needs_clarification": True,
                        "clarification_reason": (
                            f"Your question contains personally identifiable information ({entity_summary}) "
                            "and cannot be processed for privacy protection."
                        ),
                    }
            else:
                logger.info("✅ No PII detected in user question")

            return {}

        except Exception as e:
            logger.error(f"PII detection failed: {e}")
            logger.warning("Continuing workflow despite PII detection error")
            return {}

    def parse_question(self, state: WorkflowState) -> dict:
        """Parse the user's question to identify relevant collections and fields."""
        self._track_step(
            WorkflowSteps.PARSE_QUESTION,
            {
                "question": (
                    state.question[: DisplayLimits.INPUT_SUMMARY]
                    if state.question
                    else ""
                )
            },
        )

        if not self.config.is_step_enabled(WorkflowSteps.PARSE_QUESTION):
            logger.info("parse_question step is disabled, skipping")
            return {"parsed_question": {"is_relevant": True, "relevant_tables": []}}

        question = state.question
        schema = self._get_cached_schema()

        try:
            logger.info(
                "Parsing user question to identify relevant collections and fields"
            )

            model_name = self.config.llm.model
            optimized_context = optimize_context_for_model(
                schema=schema,
                unique_nouns=[],
                question=question,
                parsed_question={},
                model_name=model_name,
            )

            parsed_response = self.llm_manager.invoke_with_structured_output(
                "parse_question",
                ParseQuestionResponse,
                schema=optimized_context["schema"],
                question=optimized_context["question"],
            )

            logger.info(f"Parsing result: relevant={parsed_response.is_relevant}")

            needs_clarification = False
            clarification_prompt = None
            clarification_questions = None

            if not parsed_response.is_relevant:
                needs_clarification = True
                clarification_prompt = (
                    "I couldn't identify any relevant collections for your question. "
                    "Could you provide more details?"
                )
                clarification_questions = [
                    "Which specific data or metrics are you interested in?",
                    "Are there particular collections you'd like to query?",
                ]
            elif not parsed_response.relevant_tables:
                needs_clarification = True
                clarification_prompt = (
                    "I understood your question but couldn't identify specific collections. "
                    "Could you clarify which data sources you want to analyze?"
                )
                clarification_questions = [
                    "Which collection contains the data you need?",
                    "What specific entities are you asking about?",
                ]

            self._complete_step(
                WorkflowSteps.PARSE_QUESTION,
                step_data={
                    "question_length": len(question),
                    DetailKeys.IS_RELEVANT: parsed_response.is_relevant,
                    "tables_identified": len(parsed_response.relevant_tables),
                    "needs_clarification": needs_clarification,
                },
            )

            response: Dict[str, Any] = {"parsed_question": parsed_response.model_dump()}

            if (
                hasattr(parsed_response, "relevance_reason")
                and parsed_response.relevance_reason
            ):
                response["parsed_question"][
                    "relevance_reason"
                ] = parsed_response.relevance_reason

            if needs_clarification:
                response.update(
                    {
                        "needs_clarification": needs_clarification,
                        "clarification_prompt": clarification_prompt,
                        "clarification_questions": clarification_questions,
                    }
                )

            return response

        except Exception as e:
            logger.error(f"Error parsing question: {e}")
            self._complete_step(WorkflowSteps.PARSE_QUESTION, error=str(e))
            return {
                "parsed_question": {
                    "is_relevant": False,
                    "relevant_tables": [],
                    "relevance_reason": "Error analyzing your question. Please try rephrasing.",
                }
            }

    def _collect_field_nouns(self, collection_name: str, field_name: str) -> set:
        """Return distinct non-null values for one field in one collection."""
        command = (
            f"db.{collection_name}.aggregate(["
            f'{{"$group": {{"_id": "${field_name}"}}}},'
            f'{{"$limit": 200}}'
            f"])"
        )
        result = self.db_manager.db.run_no_throw(command)
        if not result or (isinstance(result, str) and result.startswith("Error")):
            return set()
        normalized = self.db_manager._normalize_result(result)
        nouns = set()
        for doc in normalized:
            val = doc.get("_id")
            if val is not None and str(val).strip() and str(val) != "N/A":
                nouns.add(str(val))
        return nouns

    def _collect_collection_nouns(self, table_info: dict) -> set:
        """Return all unique noun values from a single collection's noun columns."""
        collection_name = table_info.get("table_name")
        noun_columns = table_info.get("noun_columns", [])
        if not noun_columns or not collection_name:
            return set()
        nouns: set = set()
        for field_name in noun_columns:
            try:
                nouns |= self._collect_field_nouns(collection_name, field_name)
            except Exception as e:
                logger.warning(
                    f"Error getting distinct values for {collection_name}.{field_name}: {e}"
                )
        return nouns

    def get_unique_nouns(self, state: WorkflowState) -> dict:
        """Extract unique values from relevant collections using MongoDB distinct()."""
        self._track_step(WorkflowSteps.GET_UNIQUE_NOUNS)

        if not self.config.is_step_enabled(WorkflowSteps.GET_UNIQUE_NOUNS):
            return {"unique_nouns": []}

        parsed_question = state.parsed_question
        if not parsed_question or not parsed_question.get("is_relevant"):
            return {"unique_nouns": []}

        try:
            logger.info("Extracting unique values from relevant collections")
            unique_nouns: set = set()
            for table_info in parsed_question.get("relevant_tables", []):
                unique_nouns |= self._collect_collection_nouns(table_info)

            logger.info(f"Extracted {len(unique_nouns)} unique nouns from collections")
            self._complete_step(
                WorkflowSteps.GET_UNIQUE_NOUNS,
                step_data={DetailKeys.NOUNS_COUNT: len(unique_nouns)},
            )
            return {"unique_nouns": list(unique_nouns)}

        except Exception as e:
            logger.error(f"Error extracting unique nouns: {e}")
            self._complete_step(WorkflowSteps.GET_UNIQUE_NOUNS, error=str(e))
            return {"unique_nouns": []}

    def generate_query(self, state: WorkflowState) -> dict:
        """Generate a MongoDB query based on parsed question and unique nouns."""
        step = self._track_step(
            WorkflowSteps.GENERATE_SQL,
            {
                "question": state.question[: DisplayLimits.INPUT_SUMMARY],
                "retry_count": state.retry_count,
            },
        )

        if not self.config.is_step_enabled(WorkflowSteps.GENERATE_SQL):
            return {
                "sql_query": "",
                "sql_reason": "Query generation disabled",
                "retry_count": 0,
            }

        question = state.question
        parsed_question = state.parsed_question
        unique_nouns = state.unique_nouns or []
        messages = state.messages or []
        execution_error = state.execution_error
        retry_count = state.retry_count

        if execution_error:
            retry_count += 1
            logger.info(
                f"Retrying query generation (attempt {retry_count}): {execution_error}"
            )

        if not parsed_question or not parsed_question.get("is_relevant"):
            llm_reason = (parsed_question or {}).get(
                "relevance_reason", "Question not relevant to database"
            )
            return {
                "sql_query": "NOT_RELEVANT",
                "sql_reason": llm_reason,
                "answer": llm_reason,
                "analysis": "",
                "retry_count": retry_count,
            }

        try:
            logger.info("Generating MongoDB query based on parsed question and context")
            schema = self._get_cached_schema()

            additional_context = {"database_type": "MongoDB"}

            if len(messages) > 1:
                additional_context["conversation_context"] = (
                    self._summarize_conversation_context(messages)
                )

            if execution_error and retry_count > 0:
                additional_context["previous_error"] = execution_error
                additional_context["retry_attempt"] = retry_count

            model_name = self.config.llm.model
            optimized_context = optimize_context_for_model(
                schema=schema,
                unique_nouns=unique_nouns,
                question=question,
                parsed_question=parsed_question,
                model_name=model_name,
                additional_context=additional_context,
            )

            structured_response = self.llm_manager.invoke_with_structured_output(
                "generate_sql",
                MongoQueryGenerationResponse,
                **optimized_context,
            )

            query_command = structured_response.query_command
            query_reason = structured_response.query_reason

            logger.info(f"Generated MongoDB query (attempt {retry_count + 1})")

            # Validate query safety
            self._validate_query_safety(query_command)

            self._complete_step(
                step,
                step_data={
                    "sql_query": query_command[: DisplayLimits.PROGRESS_SQL_QUERY],
                    "sql_reason": query_reason[: DisplayLimits.PROGRESS_SQL_REASON],
                    "retry_attempt": retry_count + 1,
                },
            )

            return {
                "sql_query": query_command,
                "sql_reason": query_reason,
                "retry_count": retry_count,
            }

        except Exception as e:
            logger.error(f"Error generating MongoDB query: {e}")
            max_retries = getattr(self.config.workflow, "max_retries", 3)
            if not isinstance(max_retries, int):
                max_retries = 3
            needs_clarification = retry_count >= (max_retries - 1)

            self._complete_step(step, error=str(e))

            result: Dict[str, Any] = {
                "sql_query": "ERROR",
                "sql_reason": f"Error generating query: {e}",
                "retry_count": retry_count,
            }

            if needs_clarification:
                result.update(
                    {
                        "needs_clarification": True,
                        "clarification_prompt": "I'm having trouble generating the correct query. Could you provide more details?",
                        "clarification_questions": [
                            "Can you specify which fields you want to see?",
                            "What conditions or filters should be applied?",
                        ],
                    }
                )

            return result

    def validate_and_fix_query(self, state: WorkflowState) -> dict:
        """Validate and fix the generated MongoDB query."""
        step = self._track_step(WorkflowSteps.VALIDATE_SQL)

        if not self.config.is_step_enabled(WorkflowSteps.VALIDATE_SQL):
            return {
                "sql_query": state.sql_query or "",
                "sql_valid": True,
                "sql_issues": "Validation skipped",
            }

        query_json = state.sql_query or ""

        if query_json in ("NOT_RELEVANT", "ERROR", ""):
            return {
                "sql_query": query_json,
                "sql_valid": False,
                "sql_issues": "No validation needed",
            }

        try:
            logger.info("Validating MongoDB query")
            schema = self._get_cached_schema()

            validation_response = self.llm_manager.invoke_with_structured_output(
                "validate_sql",
                MongoQueryValidationResponse,
                sql_query=query_json,
                schema=schema,
            )

            if validation_response.valid and not validation_response.issues:
                logger.info("MongoDB query is valid")
                self._complete_step(
                    step, step_data={DetailKeys.VALIDATION_STATUS: "valid"}
                )
                return {"sql_query": query_json, "sql_valid": True, "sql_issues": ""}
            else:
                logger.info(f"MongoDB query fixed: {validation_response.issues}")
                final_query = (
                    validation_response.corrected_query
                    if validation_response.corrected_query != "None"
                    else query_json
                )
                self._complete_step(
                    step, step_data={DetailKeys.VALIDATION_STATUS: "fixed"}
                )
                return {
                    "sql_query": final_query,
                    "sql_valid": True,
                    "sql_issues": validation_response.issues or "Fixed",
                }

        except Exception as e:
            logger.error(f"Error validating query: {e}")
            self._complete_step(step, error=str(e))
            return {
                "sql_query": query_json,
                "sql_valid": False,
                "sql_issues": f"Validation error: {e}",
            }

    def execute_query(self, state: WorkflowState) -> dict:
        """Execute the MongoDB query against the database."""
        query_json = state.sql_query or ""

        step = self._track_step(
            WorkflowSteps.EXECUTE_SQL,
            {
                "sql_query": query_json[: DisplayLimits.PROGRESS_SQL_QUERY],
                "sql_length": len(query_json),
            },
        )

        if not self.config.is_step_enabled(WorkflowSteps.EXECUTE_SQL):
            return {"results": [], "execution_error": None}

        if query_json in ("NOT_RELEVANT", "ERROR", ""):
            return {"results": [], "execution_error": None}

        try:
            logger.info("Executing MongoDB query against database")
            results = self.db_manager.execute_query(query_json)

            logger.info(f"Query executed successfully, returned {len(results)} results")
            self._complete_step(
                step,
                step_data={"results_count": len(results), "execution_successful": True},
            )
            return {"results": results, "execution_error": None}

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error executing MongoDB query: {error_msg}")
            self._complete_step(step, error=error_msg)
            return {"results": [], "execution_error": error_msg}

    def format_results(self, state: WorkflowState) -> dict:
        """Format query results into a human-readable response."""
        step = self._track_step(WorkflowSteps.FORMAT_RESULTS)

        if not self.config.is_step_enabled(WorkflowSteps.FORMAT_RESULTS):
            return {"answer": "Result formatting disabled"}

        question = state.question or ""
        query_json = state.sql_query or ""
        query_results = state.results or []

        try:
            if query_json == "NOT_RELEVANT":
                llm_reasoning = state.sql_reason or "Question not relevant to database"
                self._complete_step(step, step_data={"step_status": "not_relevant"})
                return {"answer": llm_reasoning, "analysis": ""}

            if not query_results:
                self._complete_step(step, step_data={"step_status": "no_results"})
                return {
                    "answer": "No results found for your question.",
                    "analysis": "The query executed successfully but returned no data.",
                }

            formatting_response = self.llm_manager.invoke_with_structured_output(
                "format_results",
                ResultsFormattingResponse,
                question=question,
                sql_query=query_json,
                query_results=query_results,
            )

            logger.info("Results formatted successfully")
            self._complete_step(step, step_data={"results_count": len(query_results)})
            return {
                "answer": formatting_response.answer,
                "analysis": formatting_response.analysis,
            }

        except Exception as e:
            logger.error(f"Error formatting results: {e}")
            self._complete_step(step, error=str(e))
            return {"answer": f"Error formatting results: {e}"}

    def choose_and_format_visualization(self, state: WorkflowState) -> dict:
        """Combined step: choose visualization AND format data in a single LLM call."""
        step = self._track_step("choose_and_format_visualization")

        if not self.config.is_step_enabled("choose_and_format_visualization"):
            return {
                "visualization": "none",
                "visualization_reason": "Visualization disabled",
                "chart_data": None,
            }

        question = state.question or ""
        query_json = state.sql_query or ""
        query_results = state.results or []

        try:
            if not query_results:
                self._complete_step(step, step_data={"visualization_type": "none"})
                return {
                    "visualization": "none",
                    "visualization_reason": "No data to visualize",
                    "chart_data": None,
                }

            sample_data = query_results[:5]
            results_limit = getattr(
                self.config.framework,
                "results_limit_for_llm",
                DisplayLimits.RESULTS_LIMIT_FOR_LLM,
            )
            full_data = query_results[:results_limit]

            combined_response = self.llm_manager.invoke_with_structured_output(
                "choose_and_format_visualization",
                CombinedVisualizationResponse,
                question=question,
                sql_query=query_json,
                query_results_sample=sample_data,
                query_results_full=full_data,
                num_rows=len(query_results),
                num_cols=len(query_results[0]) if query_results else 0,
                method="function_calling",
            )

            self._complete_step(
                step, step_data={"visualization_type": combined_response.visualization}
            )
            return {
                "visualization": combined_response.visualization,
                "visualization_reason": combined_response.visualization_reason,
                "chart_data": combined_response.universal_format,
            }

        except Exception as e:
            logger.error(f"Error in combined visualization step: {e}")
            self._complete_step(step, error=str(e))
            return {
                "visualization": "table",
                "visualization_reason": f"Error: {e}",
                "chart_data": None,
            }

    def _build_schema_context(self) -> str:
        """Return a truncated schema string for followup-question prompts."""
        try:
            schema = self._get_cached_schema()
            if schema:
                schema_lines = schema.split("\n")[:DisplayLimits.SCHEMA_DISPLAY_LINES]
                return "Available database schema:\n" + "\n".join(schema_lines)
        except Exception:
            pass
        return "Schema information not available."

    @staticmethod
    def _build_results_summary(query_results: list) -> str:
        """Return a one-line summary of query results for followup-question prompts."""
        if not (isinstance(query_results, list) and query_results):
            return ""
        row_count = len(query_results)
        first_row = query_results[0] if isinstance(query_results[0], dict) else {}
        column_names = list(first_row.keys())
        return f"Found {row_count} documents with fields: {', '.join(column_names[:5])}"

    @staticmethod
    def _clean_followup_questions(raw_questions: list) -> list:
        """Strip numbering and bullet prefixes from raw followup question strings."""
        cleaned = []
        for q in raw_questions:
            q = re.sub(r"^\s*\d+\.\s*", "", q).strip()
            q = re.sub(r"^\s*[-•]\s*", "", q).strip()
            if q:
                cleaned.append(q)
        return cleaned

    def generate_followup_questions(self, state: WorkflowState) -> dict:
        """Generate relevant follow-up questions."""
        step = self._track_step(WorkflowSteps.GENERATE_FOLLOWUP_QUESTIONS)

        if not self.config.is_step_enabled(WorkflowSteps.GENERATE_FOLLOWUP_QUESTIONS):
            return {"followup_questions": []}

        question = state.question or ""
        answer = state.answer or ""
        query_json = state.sql_query or ""
        query_results = state.results or []

        if not query_results or not answer:
            return {"followup_questions": []}

        try:
            schema_context = self._build_schema_context()
            results_summary = self._build_results_summary(query_results)

            followup_response = self.llm_manager.invoke_with_structured_output(
                "generate_followup_questions",
                FollowupQuestionsResponse,
                question=question,
                answer=answer,
                sql_query=query_json,
                results_summary=results_summary,
                context_info="This is a standalone question.",
                schema_context=schema_context,
                row_count=len(query_results) if isinstance(query_results, list) else 0,
            )

            cleaned_questions = self._clean_followup_questions(
                followup_response.followup_questions
            )
            self._complete_step(
                step, step_data={"followup_questions_generated": len(cleaned_questions)}
            )
            return {"followup_questions": cleaned_questions}

        except Exception as e:
            logger.error(f"Follow-up generation failed: {e}")
            self._complete_step(step, error=str(e))
            return {"followup_questions": []}

    # =========================================================================
    # WORKFLOW CREATION
    # =========================================================================

    def _validate_query_safety(self, query_json: str) -> None:
        """
        Validate that the generated MongoDB query is safe.

        Checks for destructive operations that should never be executed
        in a read-only analytics context.

        Args:
            query_json: JSON string of the MongoDB query

        Raises:
            ValidationError: If query contains dangerous operations
        """
        if not query_json or not isinstance(query_json, str):
            raise ValidationError("Query must be a non-empty string")

        query_upper = query_json.upper()

        # Forbidden MongoDB operations (destructive writes)
        forbidden_operations = [
            "$OUT",
            "$MERGE",  # Aggregation stages that write
            "DELETEONE",
            "DELETEMANY",
            "DELETE_ONE",
            "DELETE_MANY",
            "INSERTONE",
            "INSERTMANY",
            "INSERT_ONE",
            "INSERT_MANY",
            "UPDATEONE",
            "UPDATEMANY",
            "UPDATE_ONE",
            "UPDATE_MANY",
            "REPLACEONE",
            "REPLACE_ONE",
            "DROP",
            "RENAME",
            "CREATEINDEX",
            "CREATE_INDEX",
            "DROPINDEX",
            "DROP_INDEX",
            "BULKWRITE",
            "BULK_WRITE",
        ]

        for pattern in forbidden_operations:
            if pattern in query_upper:
                raise ValidationError(
                    f"Query contains forbidden operation: {pattern}. "
                    "Only read operations (aggregate, find, count, distinct) are allowed."
                )

        # Length check
        max_length = 50000
        if len(query_json) > max_length:
            raise ValidationError(f"Query is too long (max {max_length} characters)")

        logger.debug("MongoDB query safety validation passed")

    def _should_continue_workflow(
        self, state: WorkflowState, from_step: str = "unknown"
    ) -> str:
        """Check if workflow should continue or stop for clarification."""
        if state.needs_clarification:
            if hasattr(state, "parsed_question") and state.parsed_question:
                if not state.parsed_question.get("is_relevant", True):
                    logger.info(
                        f"✅ After {from_step}: NOT_RELEVANT but continuing for explanation"
                    )
                    return "continue"
            logger.warning(
                f"🛑 WORKFLOW STOP: After {from_step}, needs_clarification=True"
            )
            return "__end__"
        return "continue"

    def _should_retry_query_generation(self, state: WorkflowState) -> str:
        """Determine if query generation should be retried."""
        execution_error = state.execution_error
        retry_count = state.retry_count
        max_retries = getattr(self.config.workflow, "max_retries", 3)

        if state.needs_clarification:
            return "__end__"

        if execution_error and retry_count < max_retries:
            logger.info(
                f"Query execution failed (attempt {retry_count + 1}/{max_retries}), retrying"
            )
            return "generate_sql"

        if execution_error and retry_count >= max_retries:
            logger.error(f"Max retries ({max_retries}) exceeded")
            return "__end__"

        return "continue"

    def _register_workflow_nodes(self, workflow: StateGraph, workflow_config) -> None:
        """Add all enabled step nodes (plus parallel_dispatcher) to the workflow graph."""
        step_methods = {
            "pii_detection": self.pii_detection_step,
            "parse_question": self.parse_question,
            "get_unique_nouns": self.get_unique_nouns,
            "generate_sql": self.generate_query,
            "validate_and_fix_sql": self.validate_and_fix_query,
            "execute_sql": self.execute_query,
            "format_results": self.format_results,
            "choose_and_format_visualization": self.choose_and_format_visualization,
            "generate_followup_questions": self.generate_followup_questions,
        }
        for step_name, method in step_methods.items():
            if workflow_config.steps.get(step_name, True):
                workflow.add_node(step_name, method)

        def parallel_dispatcher(state: WorkflowState) -> WorkflowState:
            """Dispatcher node for parallel execution after query execution."""
            return state.model_copy()

        workflow.add_node("parallel_dispatcher", parallel_dispatcher)

    def _add_sequential_edges(
        self, workflow: StateGraph, enabled_step_order: list
    ) -> None:
        """Wire sequential edges with conditional clarification checks where needed."""
        steps_that_check_clarification = {"parse_question", "get_unique_nouns", "generate_sql"}
        for i in range(len(enabled_step_order) - 1):
            current_step = enabled_step_order[i]
            next_step = enabled_step_order[i + 1]
            if current_step in steps_that_check_clarification:
                def make_checker(step_name):
                    return lambda state: self._should_continue_workflow(state, step_name)
                workflow.add_conditional_edges(
                    current_step,
                    make_checker(current_step),
                    {"continue": next_step, "__end__": END},
                )
            else:
                workflow.add_edge(current_step, next_step)

    def _add_post_execute_edges(self, workflow: StateGraph, workflow_config) -> None:
        """Wire execute_sql → dispatcher → parallel steps → followup → end nodes."""
        if not workflow_config.steps.get("execute_sql", True):
            return

        if workflow_config.steps.get("generate_sql", True):
            workflow.add_conditional_edges(
                "execute_sql",
                self._should_retry_query_generation,
                {"generate_sql": "generate_sql", "continue": "parallel_dispatcher", "__end__": END},
            )
        else:
            workflow.add_edge("execute_sql", "parallel_dispatcher")

        for ps in ("format_results", "choose_and_format_visualization"):
            if workflow_config.steps.get(ps, True):
                workflow.add_edge("parallel_dispatcher", ps)

        if workflow_config.steps.get("generate_followup_questions", True) and workflow_config.steps.get("format_results", True):
            workflow.add_edge("format_results", "generate_followup_questions")

    def _add_end_edges(self, workflow: StateGraph, workflow_config) -> None:
        """Wire final end-point edges."""
        followup_enabled = workflow_config.steps.get("generate_followup_questions", True)
        format_enabled = workflow_config.steps.get("format_results", True)

        if followup_enabled and format_enabled:
            workflow.add_edge("generate_followup_questions", END)
        elif format_enabled:
            workflow.add_edge("format_results", END)

        if workflow_config.steps.get("choose_and_format_visualization", True):
            workflow.add_edge("choose_and_format_visualization", END)

    def _create_workflow(self) -> StateGraph:
        """Create and configure the NoSQL workflow graph."""
        logger.info("Creating NoSQL workflow graph with configuration")
        workflow = StateGraph(state_schema=WorkflowState)
        workflow_config = self.config.workflow

        enabled_steps = [step for step, enabled in workflow_config.steps.items() if enabled]
        logger.info(f"Enabled workflow steps: {', '.join(enabled_steps)}")

        self._register_workflow_nodes(workflow, workflow_config)

        step_order = [
            "pii_detection", "parse_question", "get_unique_nouns",
            "generate_sql", "validate_and_fix_sql", "execute_sql",
        ]
        enabled_step_order = [s for s in step_order if workflow_config.steps.get(s, True)]

        self._add_sequential_edges(workflow, enabled_step_order)
        self._add_post_execute_edges(workflow, workflow_config)
        self._add_end_edges(workflow, workflow_config)

        # Entry point
        if enabled_step_order:
            workflow.set_entry_point(enabled_step_order[0])
        else:
            workflow.add_node(
                "dummy", lambda state: {"answer": "No workflow steps enabled"}
            )
            workflow.add_edge("dummy", END)
            workflow.set_entry_point("dummy")

        return workflow

    def _summarize_conversation_context(self, messages: list) -> str:
        """Summarize conversation context for query generation."""
        if len(messages) <= 1:
            return ""

        context_parts = []
        recent_messages = messages[-6:]

        for msg in recent_messages:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                if content:
                    context_parts.append(
                        f"Previous response touched on: {content[:100]}"
                    )
                break

        user_messages = [m for m in recent_messages if m.get("role") == "user"]
        if len(user_messages) >= 2:
            prev_q = user_messages[-2].get("content", "")
            if prev_q:
                context_parts.append(f"Previous question was: {prev_q}")

        return (
            "Conversation context: " + ". ".join(context_parts) + "."
            if context_parts
            else ""
        )
