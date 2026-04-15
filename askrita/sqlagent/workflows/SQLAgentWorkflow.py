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

"""SQL Agent workflow orchestration using LangGraph state machines."""

import logging
from typing import Any, Callable, Dict, List, NoReturn, Optional, Union

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from ...config_manager import ChainOfThoughtsConfig, get_config
from ...exceptions import DatabaseError, LLMError, QueryError, ValidationError
from ...models.chain_of_thoughts import (
    ChainOfThoughtsOutput,
    ClarificationQuestion,
    ExecutionResult,
    ReasoningSummary,
    VisualizationSpec,
    VizOptions,
)
from ...utils.chain_of_thoughts import (
    create_step_reasoning_templates,
    get_step_type,
)
from ...utils.constants import (
    ConfidenceScores,
    DetailKeys,
    DisplayLimits,
    WorkflowSteps,
)
from ...utils.enhanced_chain_of_thoughts import EnhancedChainOfThoughtsTracker
from ...utils.LLMManager import LLMManager
from ...utils.pii_detector import create_pii_detector
from ...utils.token_utils import optimize_context_for_model
from ..database.DatabaseManager import DatabaseManager
from ..formatters.DataFormatter import DataFormatter, UniversalChartData
from ..progress_tracker import ProgressData, ProgressStatus
from ..State import WorkflowState
from .langgraph_callback_handler import ChainOfThoughtsCallbackHandler

logger = logging.getLogger(__name__)


class SQLGenerationResponse(BaseModel):
    """Structured response model for SQL generation with reasoning."""

    sql_query: str = Field(description="The generated SQL query")
    sql_reason: str = Field(
        description="Explanation of why this SQL approach was chosen, including table/column choices and important considerations"
    )


class TableInfo(BaseModel):
    """Table information structure."""

    table_name: str = Field(description="Name of the table")
    noun_columns: List[str] = Field(
        description="List of noun column names", default_factory=list
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
        description="List of relevant table information", default_factory=list
    )
    relevance_reason: Optional[str] = Field(
        default=None,
        description="Brief explanation of why question is/isn't relevant to the database",
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


# No more legacy format models - using only UniversalChartData now


class CombinedVisualizationResponse(BaseModel):
    """Combined response model for visualization choice AND data formatting in a single LLM call.

    Simplified to use only UniversalChartData - no more legacy format complexity.
    """

    model_config = {"extra": "forbid"}  # Strict mode for OpenAI structured output

    visualization: str = Field(
        description="Recommended visualization type: bar, line, pie, donut, scatter, area, calendar, geo, gauge, or none"
    )
    visualization_reason: str = Field(description="Reason for the visualization choice")
    universal_format: UniversalChartData = Field(
        description="Universal chart data structure with full Pydantic validation"
    )


class SQLValidationResponse(BaseModel):
    """Structured response model for SQL validation."""

    valid: bool = Field(description="Whether the SQL query is valid")
    corrected_query: str = Field(
        description="The corrected SQL query if fixes were needed"
    )
    issues: str = Field(description="Description of any issues found", default="")


class ResultsFormattingResponse(BaseModel):
    """Structured response model for results formatting."""

    answer: Optional[str] = Field(
        default=None,
        description="short paragraph to summarize the results and analysis",
    )
    analysis: Optional[str] = Field(
        default=None, description="detailed analysis of the question and results"
    )


# Workflow Step Response Models (for type safety)
class ParsedQuestionResult(BaseModel):
    """Result from parse_question step."""

    parsed_question: ParseQuestionResponse


class UniqueNounsResult(BaseModel):
    """Result from get_unique_nouns step."""

    unique_nouns: List[str]


class SQLGenerationResult(BaseModel):
    """Result from generate_sql step."""

    sql_query: str
    sql_reason: str


class SQLValidationResult(BaseModel):
    """Result from validate_and_fix_sql step."""

    sql_query: str
    sql_valid: bool
    sql_issues: str


class SQLExecutionResult(BaseModel):
    """Result from execute_sql step."""

    results: List[Dict[str, Any]]
    error: Optional[str] = None


class FormattedResultsResult(BaseModel):
    """Result from format_results step."""

    answer: str
    analysis: str


class VisualizationChoiceResult(BaseModel):
    """Result from choose_visualization step."""

    visualization: str
    visualization_reason: str


class FollowupQuestionsResult(BaseModel):
    """Result from generate_followup_questions step."""

    followup_questions: List[str]


# Module-level constants to avoid string duplication
_MSG_NOT_RELEVANT = "Question not relevant to database schema"
_DEFAULT_REPORT_TITLE = "Query Results"
_DEFAULT_COMPANY_NAME = "Data Analytics"


def _trunc(s, n: int) -> str:
    """Truncate a string to n chars, appending '...' if it was longer."""
    s = str(s)
    return s[:n] + "..." if len(s) > n else s


class SQLAgentWorkflow:
    """
    Unified SQL Agent that handles both individual steps and workflow orchestration.

    This class combines the functionality of SQLAgent and WorkflowManager into a single,
    simplified interface that creates and manages the complete workflow.
    """

    def __init__(
        self,
        config_manager=None,
        test_llm_connection=True,
        test_db_connection=True,
        init_schema_cache=True,
        progress_callback=None,
    ):
        """
        Initialize SQLAgentWorkflow with configuration and create compiled workflow.

        Args:
            config_manager: Optional ConfigManager instance. If None, uses global config.
            test_llm_connection: Whether to test LLM connection during initialization (default: True)
            test_db_connection: Whether to test database connection during initialization (default: True)
            init_schema_cache: Whether to preload schema cache during initialization (default: True)
            progress_callback: Optional callback function for progress tracking. If provided, enables step-by-step progress notifications.
        """
        self.config = config_manager or get_config()

        # Store progress callback (enables progress tracking if provided)
        self.progress_callback = progress_callback
        self._chain_of_thoughts_config = getattr(
            self.config, "chain_of_thoughts", ChainOfThoughtsConfig()
        )
        self._cot_tracker: Optional[EnhancedChainOfThoughtsTracker] = None
        self._cot_listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._reasoning_templates = create_step_reasoning_templates()
        self._last_callback_handler: Optional[ChainOfThoughtsCallbackHandler] = None

        logger.info("🚀 Initializing SQL Agent Workflow components...")
        self.db_manager = DatabaseManager(
            self.config,
            test_llm_connection=test_llm_connection,
            test_db_connection=test_db_connection,
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

        logger.info("✅ All SQL Agent Workflow components initialized successfully")

        # Determine database type for database-specific SQL syntax
        self._db_type = self._get_database_type()

        # Cache schema at workflow level to avoid multiple database calls per query
        # This cache is managed by ConfigManager time-based expiry, not manual clearing
        self._workflow_schema_cache = None
        self._workflow_schema_cache_time = None

        # Create and compile the workflow once during initialization
        logger.info("Creating and compiling SQL agent workflow during initialization")
        self._compiled_graph = self._create_workflow().compile()
        logger.info("SQL agent workflow compiled and ready for use")

        # Optionally preload schema cache during initialization
        if init_schema_cache:
            self.preload_schema()

        # Validate sample data for PII if enabled
        if self.pii_detector and self.config.pii_detection.validate_sample_data:
            self._validate_sample_data_for_pii()

    def _track_step(self, step_name: str, details: dict = None, step_data: dict = None):
        """
        Track step execution with optional progress callback support and step outcomes.

        This method maintains backward compatibility while adding optional progress tracking.

        Args:
            step_name: Name of the workflow step
            details: Legacy details dict (for backward compatibility)
            step_data: Dictionary containing step outcomes and results for progress tracking
        """
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

        # New optional progress callback functionality
        if self.progress_callback:
            progress_data = ProgressData(
                step_name=step_name,
                status=ProgressStatus.STARTED,
                step_data=step_data or {},
            )
            try:
                self.progress_callback(progress_data)
            except Exception as e:
                # Don't let progress callback errors break the workflow
                logger.warning(f"Progress callback error: {e}")

        # Return step for backward compatibility (existing code expects this)
        return step_name

    @staticmethod
    def _extract_output_summary(combined_details: dict) -> str:
        """Pull a short output summary from a combined details dict."""
        for key in ("output", "answer", "answer_preview"):
            if key in combined_details:
                return str(combined_details[key])[: DisplayLimits.INPUT_SUMMARY]
        return ""

    def _complete_cot_step(self, step_name: str, details, error, step_data) -> None:
        """Drive the CoT tracker to close the current step and notify listeners."""
        reasoning_template = self._reasoning_templates.get(step_name, {})
        combined_details: Dict[str, Any] = {}
        if details:
            combined_details.update(details)
        if step_data:
            combined_details.setdefault("progress_data", step_data)

        output_summary = self._extract_output_summary(combined_details)

        try:
            if error:
                self._cot_tracker.complete_current_step(
                    step_name=step_name,
                    reasoning=reasoning_template.get(
                        "failure", f"{step_name} failed: {error}"
                    ),
                    output_summary=output_summary,
                    details=combined_details,
                    confidence_score=0.0,
                    error_message=error,
                )
            else:
                self._cot_tracker.complete_current_step(
                    step_name=step_name,
                    reasoning=reasoning_template.get(
                        "success", f"Completed {step_name}"
                    ),
                    output_summary=output_summary,
                    details=combined_details,
                    confidence_score=0.9,
                )
        except Exception:
            logger.exception("Failed to complete chain-of-thought step '%s'", step_name)

        try:
            cot_step_payload = (
                self._cot_tracker.steps[-1].to_dict() if self._cot_tracker.steps else {}
            )
        except Exception:
            cot_step_payload = {}

        self._notify_cot_listeners(
            {
                "event_type": "cot_step_completed",
                "step_name": step_name,
                "error": error,
                "details": combined_details,
                "progress_data": step_data or {},
                "cot_step": cot_step_payload,
            }
        )

    def _complete_step(
        self,
        step_name: str,
        details: dict = None,
        error: str = None,
        step_data: dict = None,
    ):
        """
        Complete step tracking with optional progress callback support and step outcomes.
            details: Legacy details dict (for backward compatibility)
            error: Error message if step failed
            step_data: Dictionary containing step outcomes and results for progress tracking
        """
        # New optional progress callback functionality
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
                # Don't let progress callback errors break the workflow
                logger.warning(f"Progress callback error: {e}")

        cot_enabled = self._cot_tracker is not None and getattr(
            self._cot_tracker, "enabled", False
        )
        if cot_enabled:
            self._complete_cot_step(step_name, details, error, step_data)

    def _notify_cot_listeners(self, event: Dict[str, Any]) -> None:
        """Send Chain of Thoughts events to registered listeners (e.g., SSE/WebSocket streams)."""
        if not self._cot_listeners:
            return
        for listener in tuple(self._cot_listeners):
            try:
                listener(event)
            except Exception:
                logger.exception("Chain of Thoughts listener raised an exception")

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

    def _get_database_type(self) -> str:
        """Detect the database type from connection string."""
        connection_string = self.config.database.connection_string

        # Handle Mock objects in tests
        if not isinstance(connection_string, str):
            logger.debug(
                "Connection string is not a string (likely a Mock in tests), returning 'unknown'"
            )
            return "unknown"

        connection_string = connection_string.lower()
        if "bigquery://" in connection_string:
            return "bigquery"
        elif "snowflake://" in connection_string:
            return "snowflake"
        elif "postgresql://" in connection_string or "postgres://" in connection_string:
            return "postgresql"
        elif "mysql://" in connection_string:
            return "mysql"
        elif "mssql://" in connection_string or "sqlserver://" in connection_string:
            return "sqlserver"
        elif "db2://" in connection_string or "ibm_db_sa://" in connection_string:
            return "db2"
        else:
            return "unknown"

    def _get_cast_to_string_syntax(self, column_name: str) -> str:
        """
        Get database-specific CAST to string syntax from configuration.

        Args:
            column_name: The column name to cast (should be backtick-quoted if needed)

        Returns:
            Database-specific CAST expression
        """
        sql_syntax_config = self.config.database.sql_syntax

        # Option 1: Explicit override in configuration
        if sql_syntax_config.cast_to_string:
            cast_type = sql_syntax_config.cast_to_string
            logger.debug(f"Using configured CAST type: {cast_type}")
            return f"CAST({column_name} AS {cast_type})"

        # Option 2: Use default mapping based on detected database type
        cast_type = sql_syntax_config.default_cast_types.get(self._db_type)

        if cast_type:
            logger.debug(f"Using default CAST type for {self._db_type}: {cast_type}")
            return f"CAST({column_name} AS {cast_type})"

        # Fallback: Use standard VARCHAR (may not work for all databases)
        logger.warning(
            f"Unknown database type '{self._db_type}' and no explicit cast_to_string configured. "
            f"Using VARCHAR as fallback. Consider adding database.sql_syntax.cast_to_string to your config."
        )
        return f"CAST({column_name} AS VARCHAR)"

    def _finalize_cot(
        self, success: bool, final_answer: str, error: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Finalize Chain of Thoughts tracker and emit completion event."""
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

    def get_graph(self):
        """
        Get the compiled workflow graph.

        Returns:
            Compiled StateGraph ready for execution
        """
        return self._compiled_graph

    def save_workflow_diagram(
        self, output_path: str = "./example-configs/askrita-workflow.png"
    ):
        """
        Save workflow diagram to PNG file.

        Args:
            output_path: Path where to save the PNG diagram
        """
        self._compiled_graph.get_graph().draw_png(output_file_path=output_path)
        logger.info(f"Workflow diagram saved to {output_path}")

    def chat(self, messages: list) -> WorkflowState:
        """
        Chat interface using LangGraph messages pattern for conversational queries.

        Args:
            messages: List of conversation messages in format:
                [
                    {"role": "user", "content": "Show me sales data"},
                    {"role": "assistant", "content": "Here are your sales..."},
                    {"role": "user", "content": "What about last month?"}
                ]

        Returns:
            WorkflowState: Complete workflow output with question, answer, SQL, results, visualization, and chart data.
                Type-safe dictionary conforming to WorkflowState TypedDict for downstream integration.

        Raises:
            ValidationError: If messages are invalid or unsafe
            DatabaseError: If database connection or query fails
            LLMError: If LLM provider fails
            QueryError: If SQL generation or execution fails
        """

        # Validate messages input
        if not messages or not isinstance(messages, list):
            raise ValidationError("Messages must be a non-empty list")

        # Extract current question from last user message
        current_question = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                current_question = msg.get("content", "")
                break

        if not current_question or not current_question.strip():
            raise ValidationError("No user question found in messages")

        # Use common query execution with messages context
        return self._execute_query(current_question, messages=messages)

    def query_with_cot(
        self, question: str
    ) -> Union[ChainOfThoughtsOutput, ClarificationQuestion]:
        """
        Query the database and return ChainOfThoughtsOutput with Pydantic models.

        This method returns the typed ChainOfThoughtsOutput model as specified in AC1/AC4,
        which includes ReasoningSummary, ExecutionResult, and VisualizationSpec.

        Args:
            question: Natural language question to convert to SQL and execute

        Returns:
            ChainOfThoughtsOutput if successful, ClarificationQuestion if clarification needed

        Raises:
            ValidationError: If question is invalid or unsafe
            DatabaseError: If database connection or query fails
            LLMError: If LLM provider fails
            QueryError: If SQL generation or execution fails
        """
        state = self.query(question)
        return self.to_chain_of_thoughts_output(state)

    def query(self, question: str) -> WorkflowState:
        """
        Query the database using natural language and return formatted results with visualization recommendations.

        Args:
            question: Natural language question to convert to SQL and execute

        Returns:
            WorkflowState: Complete workflow output with question, answer, SQL, results, visualization, and chart data.
                Type-safe dictionary conforming to WorkflowState TypedDict for downstream integration.

        Raises:
            ValidationError: If question is invalid or unsafe
            DatabaseError: If database connection or query fails
            LLMError: If LLM provider fails
            QueryError: If SQL generation or execution fails
        """

        # Validate input at framework boundary
        if not isinstance(question, str):
            raise ValidationError("Question must be a string")

        if not question.strip():
            raise ValidationError("Question cannot be empty")

        # Detect prompt injection attempts before the question reaches the LLM
        self._detect_prompt_injection(question)

        # Use common query execution without messages context
        return self._execute_query(question)

    def _get_cached_schema(self) -> str:
        """
        Get database schema with time-based caching for performance.

        PERFORMANCE OPTIMIZATION:
        Without caching, each query makes 3 expensive database calls:
        1. parse_question() -> get_schema()
        2. generate_sql() -> get_schema()
        3. validate_and_fix_sql() -> get_schema()

        With this optimization:
        1. First call: Fetches from database (or uses cached if within expiry)
        2. Subsequent calls: Use workflow-level cache until ConfigManager expiry

        Time-based caching strategy managed by ConfigManager:
        - Cache expires based on schema_refresh_interval (default: 1 hour)
        - Workflow-level cache respects ConfigManager expiry timing
        - Automatic cache invalidation when schema_refresh_interval exceeded

        Returns:
            str: Database schema
        """
        from datetime import datetime

        # Check if workflow cache is still valid based on ConfigManager expiry
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
                logger.info(
                    f"Workflow schema cache expired after {elapsed:.1f}s (limit: {self.config.database.schema_refresh_interval}s)"
                )
                self._workflow_schema_cache = None
                self._workflow_schema_cache_time = None

        # Get schema from database manager (which has its own configurable caching)
        logger.debug("Fetching fresh schema from DatabaseManager")
        schema = self.db_manager.get_schema()

        # Cache at workflow level with timestamp for expiry checking
        if self.config.database.cache_schema:
            self._workflow_schema_cache = schema
            self._workflow_schema_cache_time = datetime.now()
            logger.debug(
                f"Schema cached at workflow level (expires in {self.config.database.schema_refresh_interval}s)"
            )

        return schema

    def clear_schema_cache(self):
        """
        Manually clear the workflow schema cache.

        This is typically not needed as the cache automatically expires based on
        schema_refresh_interval configuration. Use this only when you know the
        schema has changed and want to force a refresh before the normal expiry.
        """
        if self._workflow_schema_cache is not None:
            logger.info("Manually clearing workflow schema cache")
            self._workflow_schema_cache = None
            self._workflow_schema_cache_time = None
        else:
            logger.debug("Workflow schema cache already empty")

    def preload_schema(self):
        """
        Preload schema cache during initialization.

        This method forces a schema fetch and caches it for subsequent use.
        Useful when you want to avoid the first-query latency by pre-warming the cache.
        """
        logger.info("Preloading schema cache...")
        try:
            schema = self._get_cached_schema()
            logger.info(
                f"✅ Schema cache preloaded successfully ({len(schema)} characters)"
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to preload schema cache: {e}")

    @property
    def schema(self) -> str:
        """
        Get the cached database schema.

        This property provides convenient access to the schema string.
        The schema is fetched from cache if available, or loaded fresh if needed.

        Returns:
            str: Database schema in SQL DDL format
        """
        return self._get_cached_schema()

    @property
    def structured_schema(self) -> dict:
        """
        Get structured representation of the database schema.

        Parses the SQL DDL schema into a structured dictionary format
        for programmatic access to tables, columns, types, etc.

        Returns:
            dict: Structured schema with format:
                {
                    'tables': {
                        'table_name': {
                            'columns': {
                                'column_name': {
                                    'type': 'data_type',
                                    'nullable': bool,
                                    'description': 'optional_description'
                                }
                            },
                            'description': 'optional_table_description'
                        }
                    }
                }
        """
        schema = self._get_cached_schema()
        return self._parse_schema_to_dict(schema)

    @staticmethod
    def _extract_table_desc_from_schema(schema: str, match_start: int) -> Optional[str]:
        """Return the table description from a comment line preceding a CREATE TABLE block."""
        import re

        lines_before = schema[:match_start].split("\n")
        for line in reversed(lines_before[-10:]):
            if line.strip().startswith("-- Table:"):
                desc_match = re.search(r"-- Table:\s*([^(]+)(?:\(([^)]+)\))?", line)
                if desc_match:
                    table_desc = (
                        desc_match.group(2)
                        if desc_match.group(2)
                        else desc_match.group(1).strip()
                    )
                    return table_desc.replace("ALWAYS USE FULL NAME:", "").strip()
        return None

    @staticmethod
    def _parse_column_lines(columns_text: str) -> dict:
        """Parse a column-definition block into a {col_name: {type, nullable, ?description}} dict."""
        import re

        if "\n" in columns_text:
            raw_lines = [
                line.strip() for line in columns_text.split("\n") if line.strip()
            ]
        else:
            raw_lines = [
                line.strip() for line in columns_text.split(",") if line.strip()
            ]

        columns = {}
        col_pattern = re.compile(r"`?([^`\s]+)`?\s+([\w\[\]<>]+(?:\([^)]*\))?)")
        for col_line in raw_lines:
            col_line = col_line.strip().rstrip(",")
            if not col_line or col_line.startswith("--"):
                continue
            col_match = col_pattern.match(col_line)
            if col_match:
                col_name = col_match.group(1).strip('`"')
                col_type = col_match.group(2)
                nullable = "NOT NULL" not in col_line.upper()
                entry: dict = {"type": col_type, "nullable": nullable}
                if "--" in col_line:
                    desc_part = col_line.split("--", 1)[1].strip()
                    if desc_part:
                        entry["description"] = desc_part.replace(
                            "(auto-generated)", ""
                        ).strip()
                columns[col_name] = entry
        return columns

    def _parse_schema_to_dict(self, schema: str) -> dict:
        """
        Parse SQL DDL schema string into structured dictionary.

        Handles various schema formats including BigQuery with qualified table names.

        Args:
            schema: SQL DDL schema string

        Returns:
            dict: Structured representation of schema
        """
        import re

        result = {"tables": {}}
        table_pattern = r'CREATE TABLE\s+([`"]?[\w.-]+[`"]?)\s*\((.*?)(?:\);|(?=\n\n)|(?=CREATE TABLE)|$)'

        for match in re.finditer(table_pattern, schema, re.DOTALL | re.IGNORECASE):
            full_table_name = match.group(1).strip('`"')
            table_name = (
                full_table_name.split(".")[-1]
                if "." in full_table_name
                else full_table_name
            )
            table_desc = self._extract_table_desc_from_schema(schema, match.start())
            columns = self._parse_column_lines(match.group(2))

            table_info = {
                "columns": columns,
                "full_name": full_table_name,
                "simple_name": table_name,
            }
            if table_desc:
                table_info["description"] = table_desc
            result["tables"][full_table_name] = table_info

        return result

    def get_cache_status(self) -> dict:
        """
        Get comprehensive schema cache status information.

        Returns:
            dict: Cache status including config-level and workflow-level information
        """
        from datetime import datetime

        # Get config-level cache info
        config_cache = self.config.get_schema_cache_info()

        # Get workflow-level cache info
        workflow_cache = {
            "cached": self._workflow_schema_cache is not None,
            "cache_time": self._workflow_schema_cache_time,
        }

        if self._workflow_schema_cache_time:
            elapsed = (
                datetime.now() - self._workflow_schema_cache_time
            ).total_seconds()
            remaining = max(0, self.config.database.schema_refresh_interval - elapsed)
            workflow_cache.update(
                {
                    "age_seconds": elapsed,
                    "remaining_seconds": remaining,
                    "valid": elapsed < self.config.database.schema_refresh_interval,
                }
            )

        return {
            "config_level_cache": config_cache,
            "workflow_level_cache": workflow_cache,
            "refresh_interval": self.config.database.schema_refresh_interval,
        }

    def _validate_question_input(self, question: str) -> None:
        """Validate the raw question string against configured length and substring rules."""
        validation_settings = (
            getattr(self.config, "get_input_validation_settings", lambda: {})() or {}
        )
        max_q_len = int(validation_settings.get("max_question_length", 10000))
        if len(question) > max_q_len:
            raise ValidationError(f"Question too long (max {max_q_len} characters)")

        suspicious_patterns = validation_settings.get(
            "blocked_substrings", ["<script", "javascript:", "data:", "vbscript:", "@@"]
        )
        q_lower = question.lower()
        for pattern in suspicious_patterns:
            if pattern in q_lower:
                raise ValidationError(
                    f"Question contains potentially unsafe content: {pattern}"
                )

    def _init_cot_tracker(self, question: str) -> None:
        """Initialise (or clear) the Chain-of-Thoughts tracker and wire up the step listener."""
        if not self._chain_of_thoughts_config.enabled:
            self._cot_tracker = None
            return

        self._cot_tracker = EnhancedChainOfThoughtsTracker(
            enabled=True, config=self._chain_of_thoughts_config
        )
        self._cot_tracker.question = question.strip()

        def tracker_step_listener(step_data):
            self._notify_cot_listeners(
                {
                    "event_type": "cot_step_completed",
                    "step_name": step_data.get("step_name"),
                    "status": step_data.get("status"),
                    "reasoning": step_data.get("reasoning"),
                    "output_summary": step_data.get("output_summary"),
                    "duration_ms": step_data.get("duration_ms"),
                    "confidence_score": step_data.get("confidence_score"),
                    "error_message": step_data.get("error_message"),
                    "cot_step": step_data,
                }
            )

        self._cot_tracker.register_step_listener(tracker_step_listener)

    def _invoke_graph(self, initial_state: WorkflowState):
        """Invoke the compiled LangGraph workflow with an optional callback handler."""
        callback_handler = None
        try:
            callback_handler = ChainOfThoughtsCallbackHandler(
                cot_tracker=self._cot_tracker,
                progress_callback=self.progress_callback,
                cot_listeners=self._cot_listeners,
                enable_streaming=True,
            )
        except Exception as e:
            logger.warning(
                f"Failed to create callback handler, continuing without it: {e}"
            )

        if callback_handler:
            result = self._compiled_graph.invoke(
                initial_state, config={"callbacks": [callback_handler]}
            )
        else:
            result = self._compiled_graph.invoke(initial_state)

        self._last_callback_handler = callback_handler
        return result

    @staticmethod
    def _build_workflow_state(
        result: dict, initial_state: WorkflowState
    ) -> WorkflowState:
        """Construct a WorkflowState from the raw LangGraph result dict."""
        return WorkflowState(
            question=result.get("question", initial_state.question),
            answer=result.get("answer", "Unable to generate answer"),
            analysis=result.get("analysis", ""),
            visualization=result.get("visualization", "none"),
            visualization_reason=result.get(
                "visualization_reason", "No visualization generated"
            ),
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

    def _reraise_as_framework_error(self, exc: Exception) -> NoReturn:
        """Convert an unexpected exception into a typed framework error and raise it."""
        error_msg = str(exc).lower()
        if "database" in error_msg or "connection" in error_msg:
            raise DatabaseError(f"Database error: {exc}")
        if "llm" in error_msg or "api" in error_msg or "openai" in error_msg:
            raise LLMError(f"LLM provider error: {exc}")
        raise QueryError(f"Query processing error: {exc}")

    def _execute_query(self, question: str, messages: list = None) -> dict:
        """
        Common query execution logic for both query() and chat() methods.

        Args:
            question: The current question to process
            messages: Optional conversation messages for context

        Returns:
            dict: Contains answer, visualization, sql_query, etc.

        Raises:
            ValidationError: If question is invalid or unsafe
            DatabaseError: If database connection or query fails
            LLMError: If LLM provider fails
            QueryError: If SQL generation or execution fails
        """
        self._validate_question_input(question)

        try:
            initial_state = WorkflowState(
                question=question.strip(),
                retry_count=0,
                execution_error=None,
                messages=messages if messages else [],
            )

            self._init_cot_tracker(question)
            result = self._invoke_graph(initial_state)

            if not isinstance(result, dict):
                raise QueryError(
                    "Workflow returned invalid result format - expected dict from LangGraph"
                )

            workflow_state = self._build_workflow_state(result, initial_state)

            if self._cot_tracker:
                cot_payload = self._finalize_cot(
                    success=workflow_state.execution_error is None,
                    final_answer=workflow_state.answer or "",
                )
                if cot_payload is not None:
                    workflow_state_dict = workflow_state.model_dump()
                    workflow_state_dict["chain_of_thoughts"] = cot_payload
                    workflow_state = WorkflowState(**workflow_state_dict)

            return workflow_state

        except ValidationError:
            raise
        except Exception as e:
            if self._cot_tracker:
                self._finalize_cot(success=False, final_answer="", error=str(e))
            self._reraise_as_framework_error(e)
        finally:
            if self._cot_tracker:
                if getattr(self._cot_tracker, "enabled", False):
                    self._finalize_cot(
                        success=False, final_answer="", error="Workflow aborted"
                    )
                self._cot_tracker = None

    def _convert_results_to_execution_result(
        self, results: List[Any]
    ) -> ExecutionResult:
        """
        Convert database results (List[Dict[str, Any]]) to ExecutionResult model.

        Args:
            results: Query results from database (List[Dict[str, Any]])

        Returns:
            ExecutionResult with rows, columns, and row_count
        """
        if not results:
            return ExecutionResult(rows=[], columns=[], row_count=0)

        # Extract columns from first row if it's a dict
        if isinstance(results[0], dict):
            columns = list(results[0].keys())
            rows = [[row.get(col) for col in columns] for row in results]
        elif isinstance(results[0], list):
            # Already in row format, need to infer columns
            # This is less common but handle it
            if results and len(results[0]) > 0:
                columns = [f"column_{i+1}" for i in range(len(results[0]))]
            else:
                columns = []
            rows = results
        else:
            # Fallback: treat as single column
            columns = ["value"]
            rows = [[row] for row in results]

        return ExecutionResult(rows=rows, columns=columns, row_count=len(rows))

    @staticmethod
    def _extract_viz_axes(chart_data) -> tuple:
        """Return (x, y) inferred from chart_data datasets and labels."""
        x, y = None, None
        if hasattr(chart_data, "datasets") and chart_data.datasets:
            first_dataset = chart_data.datasets[0]
            if hasattr(first_dataset, "label"):
                y = first_dataset.label
            if hasattr(chart_data, "labels") and chart_data.labels:
                x = chart_data.labels[0]
        return x, y

    @staticmethod
    def _extract_viz_options(chart_data) -> "Optional[VizOptions]":
        """Return VizOptions built from chart_data title, or None."""
        options_dict = {}
        if hasattr(chart_data, "title") and chart_data.title:
            options_dict["title"] = chart_data.title
        return VizOptions(**options_dict) if options_dict else None

    def _convert_visualization_to_spec(self, state: WorkflowState) -> VisualizationSpec:
        """
        Convert WorkflowState visualization fields to VisualizationSpec model.

        Args:
            state: WorkflowState with visualization information

        Returns:
            VisualizationSpec model
        """
        viz_kind = state.visualization or "table"
        x, y, series, options = None, None, None, None

        if state.chart_data:
            x, y = self._extract_viz_axes(state.chart_data)
            options = self._extract_viz_options(state.chart_data)

        return VisualizationSpec(
            kind=viz_kind, x=x, y=y, series=series, options=options
        )

    def to_chain_of_thoughts_output(
        self,
        state: WorkflowState,
        callback_handler: Optional[ChainOfThoughtsCallbackHandler] = None,
    ) -> Union[ChainOfThoughtsOutput, ClarificationQuestion]:
        """
        Convert WorkflowState to ChainOfThoughtsOutput Pydantic model.

        Args:
            state: WorkflowState from query execution
            callback_handler: Optional callback handler to get breadcrumbs

        Returns:
            ChainOfThoughtsOutput if successful, ClarificationQuestion if clarification needed
        """
        # Check if clarification is needed
        if state.needs_clarification and state.clarification_prompt:
            return ClarificationQuestion(
                question=state.clarification_prompt,
                rationale=(
                    state.clarification_questions[0]
                    if state.clarification_questions
                    else "Additional information needed"
                ),
            )

        # Get breadcrumbs from callback handler
        breadcrumbs = []
        if callback_handler:
            breadcrumbs = callback_handler.get_breadcrumbs(max_items=5)
        elif hasattr(self, "_last_callback_handler") and self._last_callback_handler:
            breadcrumbs = self._last_callback_handler.get_breadcrumbs(max_items=5)

        # If no breadcrumbs, create default ones
        if not breadcrumbs:
            breadcrumbs = [
                "Analyzed your question",
                "Generated SQL query",
                "Executed query against database",
                "Formatted results",
            ]

        reasoning = ReasoningSummary(steps=breadcrumbs)

        # Convert results to ExecutionResult
        execution_result = self._convert_results_to_execution_result(
            state.results or []
        )

        # Convert visualization to VisualizationSpec
        viz_spec = self._convert_visualization_to_spec(state)

        # Get final SQL (use corrected SQL if available)
        final_sql = state.sql_query or ""

        return ChainOfThoughtsOutput(
            reasoning=reasoning, sql=final_sql, result=execution_result, viz=viz_spec
        )

    # =============================================================================
    # WORKFLOW STEP METHODS
    # =============================================================================

    def pii_detection_step(self, state: WorkflowState) -> dict:
        """
        PII/PHI detection step - scans user question for personally identifiable information.
        This is the first step in the workflow to ensure privacy compliance.
        """
        step = self._track_step(
            "pii_detection",
            {"question_length": len(state.question) if state.question else 0},
        )

        try:
            # Skip if PII detection is disabled
            if not self.pii_detector:
                logger.debug("PII detection disabled, skipping step")
                step.complete(success=True, result_summary="PII detection disabled")
                return {}

            logger.info("🔍 Scanning user question for PII/PHI content")

            # Detect PII in user question
            pii_result = self.pii_detector.detect_pii_in_text(
                state.question, context="user_query"
            )

            # Log detection results
            if pii_result.has_pii:
                entity_summary = ", ".join(pii_result.entity_types)
                logger.warning(
                    f"⚠️  PII detected in user question! "
                    f"Entities: {entity_summary} "
                    f"(confidence: {pii_result.max_confidence:.2f})"
                )

                if pii_result.blocked:
                    logger.error("🚫 Query blocked due to PII detection")
                    step.complete(
                        success=False,
                        result_summary=f"Query blocked - PII detected: {entity_summary}",
                        error="Query contains personally identifiable information and has been blocked for privacy protection",
                    )

                    # Set clarification needed to stop workflow
                    return {
                        "needs_clarification": True,
                        "clarification_reason": (
                            f"Your question contains personally identifiable information ({entity_summary}) "
                            f"and cannot be processed for privacy protection. "
                            f"Please rephrase your question without including personal data such as "
                            f"names, phone numbers, email addresses, or other sensitive information."
                        ),
                        "pii_detection_result": {
                            "blocked": True,
                            "detected_entities": pii_result.entity_types,
                            "confidence": pii_result.max_confidence,
                        },
                    }
                else:
                    logger.warning(
                        "⚠️  PII detected but not blocking (configuration allows)"
                    )
            else:
                logger.info("✅ No PII detected in user question")

            step.complete(
                success=True,
                result_summary=f"PII scan complete - {'PII detected' if pii_result.has_pii else 'No PII found'}",
                confidence=ConfidenceScores.HIGH,
            )

            return {
                "pii_detection_result": {
                    "blocked": pii_result.blocked,
                    "detected_entities": pii_result.entity_types,
                    "confidence": pii_result.max_confidence,
                    "analysis_time_ms": pii_result.analysis_time_ms,
                }
            }

        except Exception as e:
            error_msg = f"PII detection failed: {str(e)}"
            logger.error(error_msg)
            step.complete(success=False, error=error_msg)

            # Don't block workflow on PII detection errors - log and continue
            logger.warning("Continuing workflow despite PII detection error")
            return {
                "pii_detection_result": {
                    "blocked": False,
                    "detected_entities": [],
                    "confidence": 0.0,
                    "error": error_msg,
                }
            }

    def _validate_sample_data_for_pii(self) -> None:
        """Validate database sample data for PII during workflow initialization."""
        if not self.pii_detector:
            return

        try:
            logger.info("🔍 Validating database sample data for PII/PHI content...")
            validation_results = self.pii_detector.validate_sample_data(self.db_manager)

            if validation_results.get("has_pii_violations", False):
                pii_count = len(validation_results.get("pii_detections", []))
                affected_tables = len(
                    set(
                        [
                            detection["table"]
                            for detection in validation_results.get(
                                "pii_detections", []
                            )
                        ]
                    )
                )

                logger.warning(
                    f"⚠️  PII detected in database sample data! "
                    f"{pii_count} detections across {affected_tables} tables. "
                    f"Consider reviewing your data privacy controls."
                )
            else:
                logger.info("✅ No PII detected in database sample data")

        except Exception as e:
            logger.warning(f"Sample data PII validation failed: {e}")

    def _check_parse_overrides(self, question: str) -> Optional[dict]:
        """Return a parsed_question override dict if a configured rule matches, else None."""
        try:
            overrides = self.config.get_parse_overrides()
        except Exception:
            overrides = []
        q_lower = question.lower()
        for rule in overrides:
            if not isinstance(rule, dict) or not rule.get("enabled", True):
                continue
            keywords = [str(k).lower() for k in rule.get("match_any_keywords", [])]
            if keywords and any(k in q_lower for k in keywords):
                logger.info("Parse override matched - using configured parsed response")
                return rule.get("parsed_response", {})
        return None

    @staticmethod
    def _parse_clarification(parsed_response) -> tuple:
        """Return (needs_clarification, clarification_prompt, clarification_questions) for a parsed response."""
        if not parsed_response.is_relevant:
            return (
                True,
                "I couldn't identify any relevant database tables for your question. "
                "Could you provide more details to help me understand what data you're looking for?",
                [
                    "Which specific data or metrics are you interested in?",
                    "Are there particular tables or datasets you'd like to query?",
                    "Can you rephrase your question with more specific terms?",
                ],
            )
        if not parsed_response.relevant_tables:
            return (
                True,
                "I understood your question but couldn't identify the specific tables to query. "
                "Could you clarify which data sources or tables you want to analyze?",
                [
                    "Which table or dataset contains the data you need?",
                    "What specific entities are you asking about (e.g., customers, orders, products)?",
                ],
            )
        return False, None, None

    def parse_question(self, state: WorkflowState) -> dict:
        """
        Parse the user's question to identify relevant tables and columns.
        Returns dict with only the fields this node updates.
        """
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
            result = ParsedQuestionResult(
                parsed_question=ParseQuestionResponse(
                    is_relevant=True, relevant_tables=[]
                )
            )
            return {"parsed_question": result.model_dump()["parsed_question"]}

        question = state.question
        schema = self._get_cached_schema()

        try:
            logger.info("Parsing user question to identify relevant tables and columns")

            override = self._check_parse_overrides(question)
            if override is not None:
                return {"parsed_question": override}

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

            logger.info(
                f"Original LLM parsing result: relevant={parsed_response.is_relevant}"
            )
            if (
                hasattr(parsed_response, "relevance_reason")
                and parsed_response.relevance_reason
            ):
                logger.info(
                    f"LLM provided relevance reasoning: {parsed_response.relevance_reason}"
                )

            result = ParsedQuestionResult(parsed_question=parsed_response)
            needs_clarification, clarification_prompt, clarification_questions = (
                self._parse_clarification(parsed_response)
            )

            self._complete_step(
                WorkflowSteps.PARSE_QUESTION,
                step_data={
                    "question_length": len(question),
                    DetailKeys.IS_RELEVANT: parsed_response.is_relevant,
                    "tables_identified": len(parsed_response.relevant_tables),
                    "table_names": (
                        [table.table_name for table in parsed_response.relevant_tables]
                        if parsed_response.relevant_tables
                        else []
                    ),
                    "needs_clarification": needs_clarification,
                    "clarification_prompt": (
                        clarification_prompt if needs_clarification else None
                    ),
                },
            )

            response = {"parsed_question": result.model_dump()["parsed_question"]}

            if (
                hasattr(parsed_response, "relevance_reason")
                and parsed_response.relevance_reason
            ):
                response["parsed_question"][
                    "relevance_reason"
                ] = parsed_response.relevance_reason
                logger.info(
                    f"Including LLM relevance reasoning in response: {parsed_response.relevance_reason}"
                )

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
            self._complete_step(
                WorkflowSteps.PARSE_QUESTION,
                error=str(e),
                step_data={
                    "question_length": len(question) if question else 0,
                    DetailKeys.ERROR_TYPE: type(e).__name__,
                },
            )
            result = ParsedQuestionResult(
                parsed_question=ParseQuestionResponse(
                    is_relevant=False,
                    relevant_tables=[],
                    relevance_reason="I encountered an error while analyzing your question. Please try rephrasing your question or ask about the available data in this database.",
                )
            )
            return {"parsed_question": result.model_dump()["parsed_question"]}

    def _get_identifier_quote(self) -> str:
        """Return the identifier quote character appropriate for the configured database.

        BigQuery and MySQL use backticks; standard SQL uses double quotes.
        """
        db_type = self.config.get_database_type().lower()
        if db_type in ("bigquery", "mysql"):
            return "`"
        return '"'

    def _quote_identifier(self, name: str) -> str:
        """Quote a SQL identifier, handling dotted names (schema.table, project.dataset.table).

        Each dot-separated component is quoted individually so the result is
        valid across all supported dialects:
          BigQuery :  ``project``.``dataset``.``table``
          PostgreSQL: "schema"."table"
          MySQL     : `db`.`table`
          SQLite    : "table"
        """
        q = self._get_identifier_quote()
        return ".".join(f"{q}{part}{q}" for part in name.split("."))

    def _build_noun_where_clause(self, noun_columns: list) -> str:
        """Build the WHERE clause for the unique-noun extraction query from business rules."""
        business_rules = self.config.get_business_rule("data_validation") or {}
        skip_null = business_rules.get("skip_null_values", True)
        skip_empty = business_rules.get("skip_empty_strings", True)
        skip_na = business_rules.get("skip_na_values", True)

        q = self._get_identifier_quote()
        conditions = []
        if skip_null:
            conditions.extend(f"{q}{col}{q} IS NOT NULL" for col in noun_columns)
        if skip_empty:
            conditions.extend(
                f"{self._get_cast_to_string_syntax(f'{q}{col}{q}')} != ''"
                for col in noun_columns
            )
        if skip_na:
            conditions.extend(
                f"{self._get_cast_to_string_syntax(f'{q}{col}{q}')} != 'N/A'"
                for col in noun_columns
            )
        return " AND ".join(conditions)

    def get_unique_nouns(self, state: WorkflowState) -> dict:
        """
        Extract unique nouns from the database using parsed tables.
        Returns dict with only the unique_nouns field.
        """
        # Track this step
        self._track_step(WorkflowSteps.GET_UNIQUE_NOUNS)

        if not self.config.is_step_enabled(WorkflowSteps.GET_UNIQUE_NOUNS):
            logger.info("get_unique_nouns step is disabled, skipping")
            return {"unique_nouns": []}

        parsed_question = state.parsed_question

        if not parsed_question["is_relevant"]:
            logger.info(
                "Question not relevant to database, skipping unique nouns extraction"
            )
            return {"unique_nouns": []}

        try:
            logger.info("Extracting unique nouns from relevant tables")
            unique_nouns = set()

            for table_info in parsed_question["relevant_tables"]:
                table_name = table_info["table_name"]
                noun_columns = table_info["noun_columns"]

                if noun_columns:
                    q = self._get_identifier_quote()
                    column_names = ", ".join(f"{q}{col}{q}" for col in noun_columns)
                    query = f"SELECT DISTINCT {column_names} FROM {self._quote_identifier(table_name)}"
                    where_clause = self._build_noun_where_clause(noun_columns)
                    if where_clause:
                        query += " WHERE " + where_clause

                    results = self.db_manager.execute_query(query)
                    for row in results:
                        unique_nouns.update(str(value) for value in row if value)

            logger.info(f"Extracted {len(unique_nouns)} unique nouns from database")
            self._complete_step(
                WorkflowSteps.GET_UNIQUE_NOUNS,
                step_data={
                    DetailKeys.NOUNS_COUNT: len(unique_nouns),
                    "sample_nouns": list(unique_nouns)[:10],  # First 10 as sample
                    DetailKeys.TABLES_PROCESSED: (
                        len(parsed_question["relevant_tables"])
                        if parsed_question.get("relevant_tables")
                        else 0
                    ),
                },
            )
            return {"unique_nouns": list(unique_nouns)}

        except Exception as e:
            logger.error(f"Error extracting unique nouns: {e}")
            self._complete_step(
                WorkflowSteps.GET_UNIQUE_NOUNS,
                error=str(e),
                step_data={
                    DetailKeys.NOUNS_COUNT: 0,
                    DetailKeys.ERROR_TYPE: type(e).__name__,
                },
            )
            return {"unique_nouns": []}

    def _build_sql_additional_context(
        self,
        has_conversation_context: bool,
        messages: list,
        execution_error,
        retry_count: int,
    ) -> dict:
        """Build the additional_context dict passed to the SQL generation LLM call."""
        additional_context = {"database_type": self.config.get_database_type()}
        if has_conversation_context:
            additional_context["conversation_context"] = (
                self._summarize_conversation_context(messages)
            )
            logger.info("Including conversation context for SQL generation")
        if execution_error and retry_count > 0:
            additional_context["previous_error"] = execution_error
            additional_context["retry_attempt"] = retry_count
            logger.info(
                f"Including previous error in context for retry: {execution_error}"
            )
        return additional_context

    def _not_relevant_response(self, parsed_question: dict, retry_count: int) -> dict:
        """Return the generate_sql response for a question that is not relevant to the schema."""
        llm_reason = parsed_question.get("relevance_reason") or _MSG_NOT_RELEVANT
        logger.info(
            "Question not relevant, returning NOT_RELEVANT with user explanation"
        )
        logger.info(f"Using LLM reasoning for NOT_RELEVANT: {llm_reason}")
        logger.debug(f"Full parsed_question content: {parsed_question}")
        logger.info(f"Generated user explanation: {llm_reason[:100]}...")
        return {
            "sql_query": "NOT_RELEVANT",
            "sql_reason": llm_reason,
            "answer": llm_reason,
            "analysis": "",
            "retry_count": retry_count,
        }

    def generate_sql(self, state: WorkflowState) -> dict:
        """Generate SQL query based on parsed question and unique nouns."""
        # Track SQL generation step
        step = self._track_step(
            WorkflowSteps.GENERATE_SQL,
            {
                "question": state.question[: DisplayLimits.INPUT_SUMMARY],
                "retry_count": state.retry_count,
                "has_execution_error": bool(state.execution_error),
            },
        )

        if not self.config.is_step_enabled(WorkflowSteps.GENERATE_SQL):
            logger.info("generate_sql step is disabled, skipping")
            self._complete_step(
                step, {DetailKeys.STEP_STATUS: DetailKeys.STATUS_DISABLED}
            )
            return {
                "sql_query": "",
                "sql_reason": "SQL generation step disabled",
                "retry_count": 0,
            }

        question = state.question
        parsed_question = state.parsed_question
        # If get_unique_nouns step is disabled, unique_nouns may be None.
        # Downstream token optimization expects an iterable.
        unique_nouns = state.unique_nouns or []

        # Check for conversation context from chat() method
        messages = state.messages or []
        has_conversation_context = len(messages) > 1

        # Get error information for retry attempts
        execution_error = state.execution_error
        retry_count = state.retry_count

        # Increment retry count if this is a retry due to execution error
        if execution_error:
            retry_count += 1
            logger.info(
                f"Retrying SQL generation due to execution error (attempt {retry_count}): {execution_error}"
            )

        if not parsed_question["is_relevant"]:
            return self._not_relevant_response(parsed_question, retry_count)

        try:
            return self._generate_sql_core(
                step,
                question,
                parsed_question,
                unique_nouns,
                messages,
                has_conversation_context,
                execution_error,
                retry_count,
            )
        except Exception as e:
            return self._handle_generate_sql_error(step, e, retry_count)

    def _generate_sql_core(
        self,
        step,
        question,
        parsed_question,
        unique_nouns,
        messages,
        has_conversation_context,
        execution_error,
        retry_count,
    ) -> dict:
        """Inner body of generate_sql — calls LLM and returns the result dict."""
        logger.info("Generating SQL query based on parsed question and context")
        schema = self._get_cached_schema()

        additional_context = self._build_sql_additional_context(
            has_conversation_context, messages, execution_error, retry_count
        )

        optimized_context = optimize_context_for_model(
            schema=schema,
            unique_nouns=unique_nouns,
            question=question,
            parsed_question=parsed_question,
            model_name=self.config.llm.model,
            additional_context=additional_context,
        )

        structured_response = self.llm_manager.invoke_with_structured_output(
            prompt_name="generate_sql",
            response_model=SQLGenerationResponse,
            **optimized_context,
        )
        sql_query = structured_response.sql_query
        sql_reason = structured_response.sql_reason
        logger.info("Successfully used structured output for SQL generation")
        logger.info(
            f"Generated SQL query (attempt {retry_count + 1}): "
            f"{_trunc(sql_query, DisplayLimits.QUESTION_PREVIEW)}"
        )
        logger.info(
            f"SQL reasoning: {_trunc(sql_reason, DisplayLimits.QUESTION_PREVIEW)}"
        )

        self._validate_sql_safety(sql_query)
        self._complete_step(
            step,
            {
                "sql_query": sql_query,
                "sql_reason": sql_reason,
                DetailKeys.SQL_LENGTH: len(sql_query),
                DetailKeys.IS_RELEVANT: True,
                DetailKeys.RETRY_COUNT: retry_count,
            },
            step_data={
                "sql_query": _trunc(sql_query, DisplayLimits.PROGRESS_SQL_QUERY),
                "sql_reason": _trunc(sql_reason, DisplayLimits.PROGRESS_SQL_REASON),
                "sql_length": len(sql_query),
                "retry_attempt": retry_count + 1,
                "generation_method": "structured_output",
            },
        )
        return {
            "sql_query": sql_query,
            "sql_reason": sql_reason,
            "retry_count": retry_count,
        }

    def _handle_generate_sql_error(
        self, step, exc: Exception, retry_count: int
    ) -> dict:
        """Handle an exception from _generate_sql_core and return an error result dict."""
        logger.error(f"Error generating SQL: {exc}")

        failed_sql = None
        max_retries = getattr(self.config.workflow, "max_retries", 3)
        if not isinstance(max_retries, int):
            max_retries = 3
        needs_clarification = retry_count >= (max_retries - 1)

        clarification_prompt = (
            "I'm having trouble generating the correct SQL query for your question. "
            "Could you help me by providing more specific details?"
        )
        clarification_questions = [
            "Can you specify which columns or fields you want to see?",
            "What conditions or filters should be applied to the data?",
            "Could you provide an example of the output you're expecting?",
        ]

        self._complete_step(
            step,
            {
                "failed_sql": failed_sql,
                DetailKeys.SQL_LENGTH: 0,
                DetailKeys.RETRY_COUNT: retry_count,
                DetailKeys.VALIDATION_FAILED: "validate_sql_safety" in str(exc),
                "needs_clarification": needs_clarification,
                "clarification_prompt": (
                    clarification_prompt if needs_clarification else None
                ),
            },
            error=str(exc),
            step_data={
                "failed_sql": failed_sql,
                "error_type": type(exc).__name__,
                "retry_attempt": retry_count + 1,
                "generation_failed": True,
            },
        )

        result = {
            "sql_query": "ERROR",
            "sql_reason": f"Error generating SQL: {str(exc)}",
            "retry_count": retry_count,
        }
        if needs_clarification:
            result["needs_clarification"] = needs_clarification
            result["clarification_prompt"] = clarification_prompt
            result["clarification_questions"] = clarification_questions
            logger.warning(
                f"Setting needs_clarification = True in generate_sql error handler. "
                f"Prompt: {clarification_prompt[:DisplayLimits.QUESTION_PREVIEW]}..."
            )
        return result

    def _validate_sql_valid_result(self, step, sql_query: str) -> dict:
        """Complete the validate step for a query that is already valid."""
        logger.info("SQL query is valid")
        self._complete_step(
            step,
            {"sql_query": sql_query, DetailKeys.VALIDATION_STATUS: "valid"},
            step_data={
                DetailKeys.VALIDATION_STATUS: "valid",
                "sql_query": _trunc(sql_query, DisplayLimits.SQL_PREVIEW_MEDIUM),
                DetailKeys.ISSUES: None,
                DetailKeys.FIXES_APPLIED: 0,
            },
        )
        return {"sql_query": sql_query, "sql_valid": True, "sql_issues": ""}

    def _validate_sql_fixed_result(
        self, step, sql_query: str, corrected_query: str, issues
    ) -> dict:
        """Complete the validate step for a query that needed correction."""
        logger.info(f"SQL query fixed: {issues}")
        final_query = corrected_query if corrected_query != "None" else sql_query

        sql_correction = None
        if final_query != sql_query:
            from ...models.chain_of_thoughts import SqlCorrection

            sql_correction = SqlCorrection(
                original_sql=sql_query,
                corrected_sql=final_query,
                reason=issues or "SQL validation issues corrected",
            )

        self._complete_step(
            step,
            {
                "sql_query": final_query,
                DetailKeys.VALIDATION_STATUS: "fixed",
                DetailKeys.ISSUES: issues,
            },
            step_data={
                DetailKeys.VALIDATION_STATUS: "fixed",
                "original_sql": _trunc(sql_query, DisplayLimits.SQL_PREVIEW_SHORT),
                "corrected_sql": _trunc(final_query, DisplayLimits.SQL_PREVIEW_SHORT),
                DetailKeys.ISSUES: issues,
                DetailKeys.FIXES_APPLIED: 1 if final_query != sql_query else 0,
            },
        )
        result: dict = {
            "sql_query": final_query,
            "sql_valid": True,
            "sql_issues": issues or "Fixed",
        }
        if sql_correction:
            result["sql_correction"] = sql_correction
        return result

    def _validate_sql_error_result(self, step, sql_query: str, e: Exception) -> dict:
        """Complete the validate step after an exception."""
        logger.error(f"Error validating SQL: {e}")
        self._complete_step(
            step,
            error=str(e),
            step_data={
                DetailKeys.VALIDATION_STATUS: "error",
                "sql_query": _trunc(sql_query, DisplayLimits.SQL_PREVIEW_SHORT),
                DetailKeys.ERROR_TYPE: type(e).__name__,
                "error_message": _trunc(e, DisplayLimits.ERROR_MESSAGE),
            },
        )
        return {
            "sql_query": sql_query,
            "sql_valid": False,
            "sql_issues": f"Validation error: {str(e)}",
        }

    def validate_and_fix_sql(self, state: WorkflowState) -> dict:
        """Validate and fix the generated SQL query."""
        # Add progress tracking for this step
        step = self._track_step(WorkflowSteps.VALIDATE_SQL)

        if not self.config.is_step_enabled(WorkflowSteps.VALIDATE_SQL):
            logger.info("validate_and_fix_sql step is disabled, skipping")
            self._complete_step(
                step, {DetailKeys.STEP_STATUS: DetailKeys.STATUS_DISABLED}
            )
            return {
                "sql_query": state.sql_query or "",
                "sql_valid": True,  # Assume valid if validation is disabled
                "sql_issues": "Validation skipped",
            }

        sql_query = state.sql_query or ""

        if sql_query in ["NOT_RELEVANT", "ERROR", ""]:
            logger.info("Skipping validation for non-query response")
            self._complete_step(
                step,
                {
                    DetailKeys.STEP_STATUS: DetailKeys.STATUS_SKIPPED,
                    DetailKeys.REASON: "non_query_response",
                },
            )
            return {
                "sql_query": sql_query,
                "sql_valid": False,
                "sql_issues": "No validation needed",
            }

        try:
            logger.info("Validating and potentially fixing SQL query")
            schema = self._get_cached_schema()

            # Use structured output for reliable parsing
            validation_response = self.llm_manager.invoke_with_structured_output(
                "validate_sql",
                SQLValidationResponse,
                sql_query=sql_query,
                schema=schema,
            )

            is_valid = validation_response.valid
            corrected_query = validation_response.corrected_query
            issues = validation_response.issues

            if is_valid and (issues is None or issues == ""):
                return self._validate_sql_valid_result(step, sql_query)
            return self._validate_sql_fixed_result(
                step, sql_query, corrected_query, issues
            )

        except Exception as e:
            return self._validate_sql_error_result(step, sql_query, e)

    @staticmethod
    def _classify_sql_execution_error(error_msg: str) -> tuple:
        """Return (needs_clarification, prompt, questions) for a SQL execution error message."""
        error_lower = error_msg.lower()
        if any(
            pattern in error_lower
            for pattern in ["column", "field", "not found", "does not exist"]
        ):
            return (
                True,
                (
                    "The query failed because some columns or fields don't exist in the database. "
                    "Could you help me understand which specific data you're looking for?"
                ),
                [
                    "Which exact column names or fields do you want to retrieve?",
                    "Can you verify the table and column names you're referring to?",
                ],
            )
        if "syntax" in error_lower or "parse" in error_lower:
            return (
                True,
                "The SQL query has a syntax error. Could you provide more details to help me understand your request?",
                [
                    "Can you rephrase your question in simpler terms?",
                    "What specific data are you trying to analyze?",
                ],
            )
        if (
            "permission" in error_lower
            or "access" in error_lower
            or "denied" in error_lower
        ):
            return (
                True,
                (
                    "I don't have permission to access some of the data you requested. "
                    "Could you specify which tables or datasets you have access to?"
                ),
                [
                    "Which tables or datasets do you have permission to query?",
                    "Can you provide alternative data sources that are accessible?",
                ],
            )
        return False, None, None

    def _execute_sql_success(self, step, sql_query: str, results) -> dict:
        """Complete step tracking after a successful SQL execution and return result dict."""
        logger.info(
            f"Query executed successfully, returned {len(results) if isinstance(results, list) else 'N/A'} results"
        )
        result_count = len(results) if isinstance(results, list) else 0
        self._complete_step(
            step,
            {
                "results_count": result_count,
                "results_type": type(results).__name__,
                "execution_status": "success",
            },
            step_data={
                "results_count": result_count,
                "sql_query": _trunc(sql_query, DisplayLimits.SQL_PREVIEW_SHORT),
                "execution_successful": True,
                "data_preview": (
                    results[:3] if isinstance(results, list) and results else []
                ),
                "has_data": bool(results) if isinstance(results, list) else False,
            },
        )
        return {"results": results, "execution_error": None}

    def _execute_sql_exception(self, step, sql_query: str, e: Exception) -> dict:
        """Complete step tracking after an execution exception and return result dict."""
        error_msg = str(e)
        logger.error(f"Error executing SQL: {error_msg}")
        needs_clarification, clarification_prompt, clarification_questions = (
            self._classify_sql_execution_error(error_msg)
        )
        self._complete_step(
            step,
            {
                "results_count": 0,
                "error_source": "exception",
                "error_type": type(e).__name__,
                "needs_clarification": needs_clarification,
                "clarification_prompt": (
                    clarification_prompt if needs_clarification else None
                ),
            },
            error=error_msg,
            step_data={
                "results_count": 0,
                "sql_query": _trunc(sql_query, DisplayLimits.SQL_PREVIEW_SHORT),
                "execution_successful": False,
                "error_type": type(e).__name__,
                "error_message": _trunc(e, DisplayLimits.ERROR_MESSAGE),
            },
        )
        response: dict = {"results": [], "execution_error": error_msg}
        if needs_clarification:
            response.update(
                {
                    "needs_clarification": needs_clarification,
                    "clarification_prompt": clarification_prompt,
                    "clarification_questions": clarification_questions,
                }
            )
        return response

    def execute_sql(self, state: WorkflowState) -> dict:
        """Execute the SQL query against the database."""
        sql_query = state.sql_query or ""

        # Track SQL execution step
        step = self._track_step(
            WorkflowSteps.EXECUTE_SQL,
            {
                "sql_query": (
                    sql_query[: DisplayLimits.PROGRESS_SQL_QUERY]
                    if sql_query
                    else "None"
                ),
                "sql_length": len(sql_query) if sql_query else 0,
            },
        )

        if not self.config.is_step_enabled(WorkflowSteps.EXECUTE_SQL):
            logger.info("execute_sql step is disabled, skipping")
            self._complete_step(
                step, {DetailKeys.STEP_STATUS: DetailKeys.STATUS_DISABLED}
            )
            return {"results": [], "execution_error": None}

        if sql_query in ["NOT_RELEVANT", "ERROR", ""]:
            logger.info("Skipping execution for non-query response")
            self._complete_step(
                step,
                {
                    DetailKeys.STEP_STATUS: DetailKeys.STATUS_SKIPPED,
                    DetailKeys.REASON: "non_query_response",
                },
            )
            return {"results": [], "execution_error": None}

        try:
            logger.info("Executing SQL query against database")
            results = self.db_manager.execute_query(sql_query)

            # Check if the result is an error string (when using run_no_throw)
            if isinstance(results, str) and results.startswith("Error:"):
                logger.error(f"SQL execution failed: {results}")
                self._complete_step(
                    step,
                    {
                        "results_count": 0,
                        "execution_method": "run_no_throw",
                        "error_source": "database",
                    },
                    error=results,
                )
                return {"results": [], "execution_error": results}

            return self._execute_sql_success(step, sql_query, results)

        except Exception as e:
            return self._execute_sql_exception(step, sql_query, e)

    def format_results(self, state: WorkflowState) -> dict:
        """Format query results into a human-readable response."""
        # Add progress tracking for this step
        step = self._track_step(WorkflowSteps.FORMAT_RESULTS)

        if not self.config.is_step_enabled(WorkflowSteps.FORMAT_RESULTS):
            logger.info("format_results step is disabled, skipping")
            self._complete_step(step, {"step_status": "disabled"})
            return {"answer": "Result formatting disabled"}

        question = state.question or ""
        sql_query = state.sql_query or ""
        query_results = state.results or []

        try:
            logger.info("Formatting query results for human consumption")

            # Handle NOT_RELEVANT case with helpful feedback
            if sql_query == "NOT_RELEVANT":
                # sql_reason already contains LLM reasoning from generate_sql step
                llm_reasoning = state.sql_reason or _MSG_NOT_RELEVANT

                # If no LLM reasoning was provided, give helpful fallback
                if llm_reasoning == _MSG_NOT_RELEVANT:
                    llm_reasoning = "This database contains business data, but your question asks about information that isn't available in our tables."

                logger.info(
                    "Question marked as NOT_RELEVANT, providing helpful feedback"
                )
                logger.info(f"Using reasoning: {llm_reasoning}")

                self._complete_step(
                    step,
                    {"step_status": "not_relevant"},
                    step_data={
                        "question": _trunc(question, DisplayLimits.QUESTION_PREVIEW),
                        "reasoning": _trunc(
                            llm_reasoning, DisplayLimits.REASONING_PREVIEW
                        ),
                        "feedback_provided": True,
                    },
                )
                return {
                    "answer": llm_reasoning,
                    "analysis": f"I couldn't generate a SQL query for your question: '{question}' because {llm_reasoning.lower() if not llm_reasoning.endswith('.') else llm_reasoning[:-1].lower()}. Please try asking about the data that is available in this database.",
                }

            # Handle empty results (but SQL was attempted)
            if not query_results:
                self._complete_step(step, {"step_status": "no_results"})
                return {
                    "answer": "No results found for your question.",
                    "analysis": "The query executed successfully but returned no data. This might mean the criteria didn't match any records, or the requested data doesn't exist in the database.",
                }

            # Use structured output for reliable parsing
            formatting_response = self.llm_manager.invoke_with_structured_output(
                "format_results",
                ResultsFormattingResponse,
                question=question,
                sql_query=sql_query,
                query_results=query_results,
            )

            logger.info("Results formatted successfully")
            self._complete_step(
                step,
                {
                    "results_count": len(query_results),
                    "answer_length": len(formatting_response.answer),
                },
                step_data={
                    "results_count": len(query_results),
                    "answer_preview": _trunc(
                        formatting_response.answer, DisplayLimits.ANSWER_PREVIEW
                    ),
                    "answer_length": len(formatting_response.answer),
                    "formatting_successful": True,
                    "question": _trunc(question, DisplayLimits.QUESTION_PREVIEW),
                },
            )
            return {
                "answer": formatting_response.answer,
                "analysis": formatting_response.analysis,
            }

        except Exception as e:
            logger.error(f"Error formatting results: {e}")
            self._complete_step(
                step,
                error=str(e),
                step_data={
                    "results_count": len(query_results) if query_results else 0,
                    "formatting_successful": False,
                    "error_type": type(e).__name__,
                    "error_message": _trunc(e, DisplayLimits.ERROR_MESSAGE),
                },
            )
            return {"answer": f"Error formatting results: {str(e)}"}

    def _build_schema_context_for_followup(self) -> str:
        """Build a schema context string for follow-up question generation."""
        try:
            schema = self._get_cached_schema()
            if not schema:
                return "Schema information not available."
            schema_lines = schema.split("\n")
            table_info = []
            for line in schema_lines[: DisplayLimits.SCHEMA_DISPLAY_LINES]:
                line_upper = line.upper()
                if "CREATE TABLE" in line_upper or "TABLE" in line_upper:
                    table_info.append(line.strip())
                elif any(kw in line_upper for kw in ["COLUMN", "FIELD", "--"]):
                    table_info.append(line.strip()[: DisplayLimits.SCHEMA_LINE_LENGTH])
            if table_info:
                limited = table_info[:50]
                logger.info(
                    f"Added schema context for follow-up generation ({len(limited)} lines)"
                )
                return (
                    "Available database schema (tables and key columns):\n"
                    + "\n".join(limited)
                )
            return "Database schema is available with multiple tables and columns for analysis."
        except Exception as schema_error:
            logger.warning(
                f"Could not retrieve schema for follow-up questions: {schema_error}"
            )
            return "Schema information not available."

    def _build_results_summary(self, query_results: list) -> str:
        """Build a short textual summary of query results for follow-up context."""
        if not (isinstance(query_results, list) and query_results):
            return ""
        row_count = len(query_results)
        first_row = query_results[0] if isinstance(query_results[0], dict) else {}
        column_names = list(first_row.keys()) if first_row else []
        summary = f"Found {row_count} rows with columns: {', '.join(column_names[:5])}"
        if len(column_names) > 5:
            summary += f" (and {len(column_names) - 5} more)"
        return summary

    def _clean_followup_questions(self, raw_questions: list) -> list:
        """Strip any numbering/bullet prefixes added by the LLM."""
        import re

        cleaned = []
        for q in raw_questions:
            q = re.sub(r"^\s*\d+\.\s*", "", q).strip()
            q = re.sub(r"^\s*[-•]\s*", "", q).strip()
            if q:
                cleaned.append(q)
        return cleaned

    def _invoke_followup_llm(
        self,
        step: str,
        question: str,
        answer: str,
        sql_query: str,
        query_results: list,
        messages: list,
    ) -> dict:
        """Call the LLM to generate follow-up questions, returning the workflow result dict."""
        schema_context = self._build_schema_context_for_followup()
        results_summary = self._build_results_summary(query_results)
        row_count = len(query_results) if isinstance(query_results, list) else 0
        context_info = (
            f"This is part of an ongoing conversation with {len(messages)} messages."
            if len(messages) > 1
            else "This is a standalone question."
        )
        try:
            followup_response = self.llm_manager.invoke_with_structured_output(
                "generate_followup_questions",
                FollowupQuestionsResponse,
                question=question,
                answer=answer,
                sql_query=sql_query,
                results_summary=results_summary,
                context_info=context_info,
                schema_context=schema_context,
                row_count=row_count,
            )
            cleaned_questions = self._clean_followup_questions(
                followup_response.followup_questions
            )
            logger.info(
                f"Generated {len(cleaned_questions)} follow-up questions using LLM"
            )
            self._complete_step(
                step,
                {"questions_generated": len(cleaned_questions), "method": "llm"},
                step_data={
                    "followup_questions_generated": len(cleaned_questions),
                    "generation_method": "llm",
                    "question_preview": cleaned_questions[:3],
                    "context_used": bool(schema_context),
                    "results_count": row_count,
                },
            )
            return {"followup_questions": cleaned_questions}
        except Exception as llm_error:
            logger.error(f"LLM-based follow-up generation failed: {llm_error}")
            logger.info("Returning empty follow-up questions (LLM unavailable)")
            self._complete_step(
                step,
                {"step_status": "failed", "reason": "llm_error"},
                error=str(llm_error),
                step_data={
                    "followup_questions_generated": 0,
                    "generation_method": "llm_failed",
                    "error_type": type(llm_error).__name__,
                    "error_message": _trunc(llm_error, DisplayLimits.ERROR_MESSAGE),
                },
            )
            return {"followup_questions": []}

    def generate_followup_questions(self, state: WorkflowState) -> dict:
        """Generate relevant follow-up questions based on the query results and context."""
        step = self._track_step(WorkflowSteps.GENERATE_FOLLOWUP_QUESTIONS)

        if not self.config.is_step_enabled(WorkflowSteps.GENERATE_FOLLOWUP_QUESTIONS):
            logger.info("generate_followup_questions step is disabled, skipping")
            self._complete_step(
                step,
                {DetailKeys.STEP_STATUS: DetailKeys.STATUS_DISABLED},
                step_data={
                    "followup_questions_generated": 0,
                    "step_status": "disabled",
                },
            )
            return {"followup_questions": []}

        question = state.question or ""
        answer = state.answer or ""
        sql_query = state.sql_query or ""
        query_results = state.results or []
        messages = state.messages or []

        try:
            logger.info("Generating follow-up questions based on query context")
            logger.info(
                f"Follow-up generation state: question={bool(question)}, answer={bool(answer)}, "
                f"sql_query={bool(sql_query)}, results_count={len(query_results) if isinstance(query_results, list) else 'N/A'}"
            )

            if not query_results or not answer:
                logger.info(
                    f"No results or answer available, skipping follow-up generation. "
                    f"query_results={query_results}, answer='{answer[:50] if answer else 'None'}...'"
                )
                self._complete_step(
                    step,
                    {"step_status": "skipped", "reason": "no_results_or_answer"},
                    step_data={
                        "followup_questions_generated": 0,
                        "skip_reason": "no_results_or_answer",
                        "has_answer": bool(answer),
                        "has_results": bool(query_results),
                    },
                )
                return {"followup_questions": []}

            return self._invoke_followup_llm(
                step, question, answer, sql_query, query_results, messages
            )

        except Exception as e:
            logger.error(f"Error in follow-up question generation: {e}")
            self._complete_step(
                step,
                error=str(e),
                step_data={
                    "followup_questions_generated": 0,
                    "generation_method": "error",
                    "error_type": type(e).__name__,
                    "error_message": _trunc(e, DisplayLimits.ERROR_MESSAGE),
                },
            )
            return {"followup_questions": []}

    def choose_visualization(self, state: WorkflowState) -> dict:
        """Choose appropriate visualization for the query results."""
        # Add progress tracking for this step
        step = self._track_step(WorkflowSteps.CHOOSE_VISUALIZATION)

        if not self.config.is_step_enabled(WorkflowSteps.CHOOSE_VISUALIZATION):
            logger.info("choose_visualization step is disabled, skipping")
            self._complete_step(
                step,
                {DetailKeys.STEP_STATUS: DetailKeys.STATUS_DISABLED},
                step_data={"visualization_chosen": "none", "step_status": "disabled"},
            )
            return {
                "visualization": "none",
                "visualization_reason": "Visualization disabled",
            }

        question = state.question or ""
        sql_query = state.sql_query or ""
        query_results = state.results or []

        try:
            logger.info("Choosing appropriate visualization for results")

            if not query_results:
                self._complete_step(
                    step,
                    {"step_status": "no_data"},
                    step_data={
                        "visualization_chosen": "none",
                        "no_data_reason": "no_query_results",
                        "results_count": 0,
                    },
                )
                return {
                    "visualization": "none",
                    "visualization_reason": "No data to visualize",
                }

            # Use structured output for reliable parsing
            viz_response = self.llm_manager.invoke_with_structured_output(
                "choose_visualization",
                VisualizationResponse,
                question=question,
                sql_query=sql_query,
                query_results=query_results,
            )

            logger.info(f"Visualization chosen: {viz_response.visualization}")
            self._complete_step(
                step,
                {"visualization_chosen": viz_response.visualization},
                step_data={
                    "visualization_chosen": viz_response.visualization,
                    "visualization_reason": _trunc(
                        viz_response.visualization_reason,
                        DisplayLimits.VISUALIZATION_REASON,
                    ),
                    "results_count": len(query_results),
                    "question": _trunc(question, DisplayLimits.QUESTION_PREVIEW),
                },
            )
            return {
                "visualization": viz_response.visualization,
                "visualization_reason": viz_response.visualization_reason,
            }

        except Exception as e:
            logger.error(f"Error choosing visualization: {e}")
            self._complete_step(
                step,
                error=str(e),
                step_data={
                    "visualization_chosen": "table",  # Fallback
                    "error_type": type(e).__name__,
                    "error_message": _trunc(e, DisplayLimits.ERROR_MESSAGE),
                    "results_count": len(query_results) if query_results else 0,
                },
            )
            return {
                "visualization": "table",
                "visualization_reason": f"Error choosing visualization: {str(e)}",
            }

    def choose_and_format_visualization(self, state: WorkflowState) -> dict:
        """
        PERFORMANCE OPTIMIZATION: Combined step that chooses visualization AND formats data in a single LLM call.

        This replaces the two-step process:
        1. choose_visualization (1 LLM call)
        2. format_data_for_visualization (1 LLM call)

        With a single combined LLM call, saving ~250-400ms and ~14% of costs.

        Returns:
            dict: Dictionary with visualization and chart_data fields populated
        """
        # Add progress tracking for this step
        step = self._track_step("choose_and_format_visualization")

        if not self.config.is_step_enabled("choose_and_format_visualization"):
            logger.info(
                "choose_and_format_visualization step is disabled, skipping combined visualization"
            )
            self._complete_step(
                step,
                {"step_status": "disabled"},
                step_data={
                    "visualization_type": "none",
                    "data_formatted": False,
                    "optimization_used": False,
                    "step_status": "disabled",
                },
            )
            # Copy state and update visualization fields
            return {
                "visualization": "none",
                "visualization_reason": "Visualization disabled",
                "chart_data": None,
            }

        question = state.question or ""
        sql_query = state.sql_query or ""
        query_results = state.results or []

        try:
            logger.info(
                "🚀 OPTIMIZED: Choosing visualization AND formatting data in single LLM call"
            )

            if not query_results:
                self._complete_step(
                    step,
                    {"step_status": "no_data"},
                    step_data={
                        "visualization_type": "none",
                        "data_formatted": False,
                        "optimization_used": False,
                        "no_data_reason": "no Query results",
                        "results_count": 0,
                    },
                )
                return {
                    "visualization": "none",
                    "visualization_reason": "No data to visualize",
                    "chart_data": None,
                }

            # Prepare sample data for efficiency (limit to first 5 rows)
            sample_data = query_results[:5] if len(query_results) > 5 else query_results
            # Use configurable limit from framework config, fallback to constant if not set
            results_limit = getattr(
                self.config.framework,
                "results_limit_for_llm",
                DisplayLimits.RESULTS_LIMIT_FOR_LLM,
            )
            full_data = (
                query_results[:results_limit]
                if len(query_results) > results_limit
                else query_results
            )
            num_rows = len(query_results)
            num_cols = len(query_results[0]) if query_results else 0

            # Use structured output with combined response model (function_calling method)
            # Note: Must use function_calling method, not json_schema, for nested Pydantic models
            combined_response = self.llm_manager.invoke_with_structured_output(
                "choose_and_format_visualization",
                CombinedVisualizationResponse,
                question=question,
                sql_query=sql_query,
                query_results_sample=sample_data,
                query_results_full=full_data,
                num_rows=num_rows,
                num_cols=num_cols,
                method="function_calling",  # CRITICAL: function_calling works with nested Pydantic models
            )

            logger.info(f"✅ Visualization chosen: {combined_response.visualization}")
            logger.info("✅ Data formatted in same call (saved 1 LLM call!)")

            # Convert Pydantic model to keep as UniversalChartData object for type safety
            chart_data_pydantic = (
                combined_response.universal_format
            )  # Keep as Pydantic object!

            # Return simplified response - no more legacy format!
            self._complete_step(
                step,
                {
                    "visualization_chosen": combined_response.visualization,
                    "optimized": True,
                    "method": "combined_call",
                },
                step_data={
                    "visualization_type": combined_response.visualization,
                    "visualization_reason": _trunc(
                        combined_response.visualization_reason,
                        DisplayLimits.VISUALIZATION_REASON,
                    ),
                    "data_formatted": True,
                    "chart_data_generated": bool(combined_response.universal_format),
                    "optimization_used": True,
                    "results_count": num_rows,
                },
            )
            return {
                "visualization": combined_response.visualization,
                "visualization_reason": combined_response.visualization_reason,
                "chart_data": chart_data_pydantic,  # Only UniversalChartData now
            }

        except Exception as e:
            logger.error(f"Error in combined visualization step: {e}")
            self._complete_step(
                step,
                error=str(e),
                step_data={
                    "visualization_type": "table",  # Fallback
                    "data_formatted": False,
                    "chart_data_generated": False,
                    "error_type": type(e).__name__,
                    "error_message": _trunc(e, DisplayLimits.ERROR_MESSAGE),
                    "optimization_used": False,
                },
            )
            # Copy input state and update specific fields
            return {
                "visualization": "table",
                "visualization_reason": f"Error in combined visualization: {str(e)}",
                "chart_data": None,
            }

    # =============================================================================
    # WORKFLOW CREATION AND MANAGEMENT
    # =============================================================================

    def _should_continue_workflow(
        self, state: WorkflowState, from_step: str = "unknown"
    ) -> str:
        """
        Universal workflow continuation check after any step.

        Args:
            state: Current workflow state
            from_step: Name of the step this is being called from (for logging)

        Returns:
            "__end__" if workflow should stop (needs clarification or critical error)
            "continue" if workflow should continue to next step
        """
        needs_clarification = state.needs_clarification

        # Check if we need user clarification, but distinguish between types
        if needs_clarification:
            # For NOT_RELEVANT questions, continue to generate_sql and format_results to provide explanations
            # Only stop for truly unclear questions that need user input
            if hasattr(state, "parsed_question") and state.parsed_question:
                is_relevant = state.parsed_question.get("is_relevant", True)
                if not is_relevant:
                    logger.info(
                        f"✅ After {from_step}: Question is NOT_RELEVANT but continuing to provide explanation. "
                        f"Clarification available but will generate helpful response first."
                    )
                    return "continue"

            # For other unclear questions, stop and ask for clarification
            logger.warning(
                f"🛑 WORKFLOW STOP: After {from_step}, needs_clarification=True for unclear question. "
                f"Clarification prompt: {state.clarification_prompt or 'None'}"
            )
            return "__end__"

        # Otherwise continue with normal flow
        logger.info(
            f"✅ After {from_step}: needs_clarification=False, continuing to next step"
        )
        return "continue"

    def _should_retry_sql_generation(self, state: WorkflowState) -> str:
        """
        Determine if SQL generation should be retried based on execution error and retry count.

        Returns:
            "generate_sql" if should retry
            "continue" if should continue normally
            "__end__" if needs clarification (stops workflow and returns clarification to user)
        """
        execution_error = state.execution_error
        retry_count = state.retry_count
        needs_clarification = state.needs_clarification
        max_retries = getattr(self.config.workflow, "max_retries", 3)

        # Check if we need user clarification - this should stop the workflow
        if needs_clarification:
            logger.info(
                "Clarification needed from user, ending workflow to request clarification"
            )
            return "__end__"

        # If there's an execution error and we haven't exceeded max retries, retry SQL generation
        if execution_error and retry_count < max_retries:
            logger.info(
                f"SQL execution failed (attempt {retry_count + 1}/{max_retries}), routing back to generate_sql"
            )
            return "generate_sql"

        # If we've exceeded max retries, stop the workflow (don't continue with empty results)
        if execution_error and retry_count >= max_retries:
            logger.error(
                f"Max retries ({max_retries}) exceeded for SQL generation. "
                f"Stopping workflow and returning error to user."
            )
            return "__end__"

        # Otherwise continue with normal flow
        logger.info("SQL execution completed, continuing with normal workflow")
        return "continue"

    def _add_pre_execute_edges(
        self,
        workflow: StateGraph,
        enabled_step_order: list,
        steps_that_check_clarification: set,
    ) -> None:
        """Add edges between pre-execute steps, with conditional routing where needed."""
        for i in range(len(enabled_step_order) - 1):
            current_step = enabled_step_order[i]
            next_step = enabled_step_order[i + 1]

            if current_step in steps_that_check_clarification:

                def make_checker(step_name):
                    return lambda state: self._should_continue_workflow(
                        state, step_name
                    )

                workflow.add_conditional_edges(
                    current_step,
                    make_checker(current_step),
                    {"continue": next_step, "__end__": END},
                )
                logger.info(
                    f"Added conditional routing for {current_step} → {next_step} or END"
                )
            else:
                workflow.add_edge(current_step, next_step)
                logger.debug(f"Added direct edge: {current_step} → {next_step}")

    def _setup_execute_sql_routing(self, workflow: StateGraph, workflow_config) -> None:
        """Configure post-execute_sql routing to the parallel dispatcher and beyond."""
        if not workflow_config.steps.get("execute_sql", True):
            return

        if workflow_config.steps.get("generate_sql", True):
            workflow.add_conditional_edges(
                "execute_sql",
                self._should_retry_sql_generation,
                {
                    "generate_sql": "generate_sql",
                    "continue": "parallel_dispatcher",
                    "__end__": END,
                },
            )
        else:
            workflow.add_edge("execute_sql", "parallel_dispatcher")

        parallel_steps = []
        if workflow_config.steps.get("format_results", True):
            parallel_steps.append("format_results")

        use_combined = workflow_config.steps.get(
            "choose_and_format_visualization", True
        )
        use_separate_choose = workflow_config.steps.get("choose_visualization", False)

        if use_combined:
            parallel_steps.append("choose_and_format_visualization")
            logger.info(
                "🚀 OPTIMIZATION: Using combined choose_and_format_visualization step"
            )
        elif use_separate_choose:
            parallel_steps.append("choose_visualization")
            logger.info("Using separate visualization steps (legacy mode)")

        for step in parallel_steps:
            workflow.add_edge("parallel_dispatcher", step)

        if workflow_config.steps.get(
            "generate_followup_questions", True
        ) and workflow_config.steps.get("format_results", True):
            workflow.add_edge("format_results", "generate_followup_questions")

    def _get_workflow_end_nodes(self, workflow_config) -> list:
        """Determine which nodes are terminal (connect to END) based on config."""
        end_nodes = []

        if workflow_config.steps.get(
            "generate_followup_questions", True
        ) and workflow_config.steps.get("format_results", True):
            end_nodes.append("generate_followup_questions")
        elif workflow_config.steps.get("format_results", True):
            end_nodes.append("format_results")

        use_combined = workflow_config.steps.get(
            "choose_and_format_visualization", True
        )
        use_separate_choose = workflow_config.steps.get("choose_visualization", False)
        use_separate_format = workflow_config.steps.get(
            "format_data_for_visualization", False
        )

        if use_combined:
            end_nodes.append("choose_and_format_visualization")
        elif use_separate_format:
            end_nodes.append("format_data_for_visualization")
        elif use_separate_choose:
            end_nodes.append("choose_visualization")

        return end_nodes

    def _create_workflow(self) -> StateGraph:
        """Create and configure the workflow graph based on configuration."""
        logger.info("Creating workflow graph with configuration")
        workflow = StateGraph(state_schema=WorkflowState)

        # Get enabled steps from configuration
        workflow_config = self.config.workflow
        enabled_steps = [
            step for step, enabled in workflow_config.steps.items() if enabled
        ]

        logger.info(f"Enabled workflow steps: {', '.join(enabled_steps)}")

        # Add nodes to the graph (only enabled ones)
        step_methods = {
            "pii_detection": self.pii_detection_step,  # NEW: PII detection as first step
            "parse_question": self.parse_question,
            "get_unique_nouns": self.get_unique_nouns,
            "generate_sql": self.generate_sql,
            "validate_and_fix_sql": self.validate_and_fix_sql,
            "execute_sql": self.execute_sql,
            "format_results": self.format_results,
            "choose_visualization": self.choose_visualization,
            "format_data_for_visualization": self.data_formatter.format_data_for_visualization,
            "choose_and_format_visualization": self.choose_and_format_visualization,  # OPTIMIZED: Combined step
            "generate_followup_questions": self.generate_followup_questions,
        }

        # Add a dispatcher node to handle parallel routing after execute_sql
        def parallel_dispatcher(state: WorkflowState) -> WorkflowState:
            """Dispatcher node that passes state through unchanged for parallel execution."""
            return state.model_copy()

        step_methods["parallel_dispatcher"] = parallel_dispatcher

        # Add enabled nodes (dispatcher always added; others only if enabled)
        for step_name, method in step_methods.items():
            if step_name == "parallel_dispatcher" or workflow_config.steps.get(
                step_name, True
            ):
                workflow.add_node(step_name, method)

        # Define standard step order before execute_sql
        step_order = [
            "pii_detection",  # NEW: PII detection as first step
            "parse_question",
            "get_unique_nouns",
            "generate_sql",
            "validate_and_fix_sql",
            "execute_sql",
        ]

        # Filter to only enabled steps
        enabled_step_order = [
            step for step in step_order if workflow_config.steps.get(step, True)
        ]

        # Add conditional edges for steps that might need clarification
        steps_that_check_clarification = {
            "parse_question",
            "get_unique_nouns",
            "generate_sql",
        }
        self._add_pre_execute_edges(
            workflow, enabled_step_order, steps_that_check_clarification
        )

        # Handle execute_sql routing with conditional retry logic and parallel dispatch
        self._setup_execute_sql_routing(workflow, workflow_config)

        # Handle separate visualization steps if using legacy mode
        use_separate_choose = workflow_config.steps.get("choose_visualization", False)
        use_separate_format = workflow_config.steps.get(
            "format_data_for_visualization", False
        )
        if use_separate_choose and use_separate_format:
            workflow.add_edge("choose_visualization", "format_data_for_visualization")
            logger.info("Added edge between separate visualization steps (legacy mode)")

        # Set end points
        for end_node in self._get_workflow_end_nodes(workflow_config):
            workflow.add_edge(end_node, END)

        # Set entry point to first enabled step
        if enabled_step_order:
            workflow.set_entry_point(enabled_step_order[0])
        else:
            logger.warning("No workflow steps enabled!")
            # Create a minimal workflow
            workflow.add_node(
                "dummy", lambda state: {"answer": "No workflow steps enabled"}
            )
            workflow.add_edge("dummy", END)
            workflow.set_entry_point("dummy")

        return workflow

    _INSTRUCTION_OVERRIDE_PATTERNS = [
        r"ignore\s+(\w+\s+)*(instructions?|prompts?|rules?|constraints?)",
        r"disregard\s+(\w+\s+)*(instructions?|prompts?|rules?|constraints?)",
        r"forget\s+(\w+\s+)*(instructions?|prompts?|rules?|training)",
        r"override\s+(\w+\s+)*(instructions?|prompts?|rules?|constraints?)",
        r"new\s+instructions?\s*:",
        r"system\s*prompt\s*:",
        r"you\s+are\s+now\s+(an?\s+)?(different|new|another|unrestricted)",
        r"act\s+as\s+(an?\s+)?(different|new|another|unrestricted|jailbreak)",
        r"pretend\s+(you\s+are|to\s+be)\s+",
        r"do\s+anything\s+now",
        r"dan\s+mode",
        r"jailbreak",
    ]

    _DANGEROUS_SQL_PATTERNS = [
        r"\bdrop\s+table\b",
        r"\bdelete\s+from\b",
        r"\btruncate\s+table\b",
        r"\binsert\s+into\b",
        r"\bupdate\s+\w+\s+set\b",
        r"\balter\s+table\b",
        r"\bcreate\s+table\b",
        r"\bgrant\s+\w+\s+on\b",
        r"\brevoke\s+\w+\s+on\b",
        r"\bexec(ute)?\s*\(",
        r"\bxp_\w+",
        r"\bdbms_\w+",
    ]

    _SQL_SELECT_PATTERNS = [
        r"\bselect\s+(?:\*|`?\w+`?(?:\s*,\s*`?\w+`?)*)\s+from\b",
        r"\bselect\s+`\w",
        r"\b(execute|run|perform)\s+(this\s+)?(sql|query|statement)\b",
        r"\bfrom\s+\w[\w.]*\s+where\s+\w+\s*[=<>!]",
    ]

    @staticmethod
    def _check_patterns(
        normalized: str, patterns: list, log_prefix: str, error_msg: str
    ) -> None:
        """Raise ValidationError if any regex pattern matches the normalised text."""
        import re

        for pattern in patterns:
            if re.search(pattern, normalized):
                logger.warning(f"{log_prefix}: pattern='{pattern}'")
                raise ValidationError(error_msg)

    def _detect_prompt_injection(self, question: str) -> None:
        """
        Detect prompt injection attempts in the user's natural-language question.

        This runs BEFORE the question reaches the LLM.  It looks for patterns
        that try to override the system prompt, hijack the model's role, or
        smuggle SQL/DML commands directly into the prompt.

        Args:
            question: Raw user question string

        Raises:
            ValidationError: If a prompt injection pattern is detected
        """
        normalized = question.lower()

        self._check_patterns(
            normalized,
            self._INSTRUCTION_OVERRIDE_PATTERNS,
            "Prompt injection attempt detected in user question",
            "Your question contains patterns that are not allowed. Please ask a plain data question.",
        )
        self._check_patterns(
            normalized,
            self._DANGEROUS_SQL_PATTERNS,
            "SQL injection via prompt detected in user question",
            "Your question appears to contain SQL commands. Please describe what data you want in plain language.",
        )
        self._check_patterns(
            normalized,
            self._SQL_SELECT_PATTERNS,
            "SQL SELECT injection via prompt detected in user question",
            (
                "Please ask your question in natural language. "
                "Do not provide SQL queries directly — describe what data you need "
                "and the system will generate the query for you."
            ),
        )

    @staticmethod
    def _strip_sql_comments(sql: str) -> str:
        """Remove -- line comments and /* */ block comments from an upper-cased SQL string."""
        # Remove line comments
        sql = " ".join(line.split("--")[0] for line in sql.split("\n"))
        # Remove block comments
        while "/*" in sql and "*/" in sql:
            start = sql.find("/*")
            end = sql.find("*/", start)
            if end != -1:
                sql = sql[:start] + " " + sql[end + 2 :]
            else:
                sql = sql[:start]
                break
        return sql

    def _validate_sql_safety(self, sql_query: str) -> None:
        """
        Validate that generated SQL is safe for framework execution.

        Args:
            sql_query: The SQL query to validate

        Raises:
            ValidationError: If SQL contains dangerous operations
        """
        if not sql_query or not isinstance(sql_query, str):
            raise ValidationError("SQL query must be a non-empty string")

        sql_normalized = self._strip_sql_comments(sql_query.upper().strip())

        words = [w for w in sql_normalized.split() if w.strip()]
        if not words:
            raise ValidationError("SQL query appears to be empty")

        safety_settings = (
            getattr(self.config, "get_sql_safety_settings", lambda: {})() or {}
        )

        allowed_types = set(
            safety_settings.get("allowed_query_types", ["SELECT", "WITH"])
        )
        if words[0] not in allowed_types:
            raise ValidationError(
                f"SQL query type '{words[0]}' not allowed. Only {', '.join(sorted(allowed_types))} queries are permitted."
            )

        forbidden_patterns = safety_settings.get(
            "forbidden_patterns",
            [
                "DROP",
                "DELETE",
                "TRUNCATE",
                "ALTER",
                "CREATE",
                "INSERT",
                "UPDATE",
                "GRANT",
                "REVOKE",
                "EXEC",
                "EXECUTE",
                "MERGE",
                "REPLACE",
                "LOAD",
                "IMPORT",
                "EXPORT",
                "BACKUP",
                "RESTORE",
                "SHUTDOWN",
            ],
        )
        for pattern in forbidden_patterns:
            if pattern in sql_normalized:
                raise ValidationError(f"SQL contains forbidden operation: {pattern}")

        suspicious_functions = safety_settings.get(
            "suspicious_functions",
            [
                "OPENROWSET",
                "OPENDATASOURCE",
                "XP_",
                "SP_",
                "DBMS_",
                "UTL_FILE",
                "UTL_HTTP",
                "BULK",
                "OUTFILE",
                "DUMPFILE",
            ],
        )
        for func in suspicious_functions:
            if func in sql_normalized:
                raise ValidationError(
                    f"SQL contains potentially dangerous function: {func}"
                )

        if not safety_settings.get("allow_select_star", False):
            import re

            if re.search(r"SELECT\s+\*|\.\*", sql_normalized):
                raise ValidationError(
                    "SELECT * is not allowed. Please specify the columns you need. "
                    "Selecting all columns can return extremely large result sets that "
                    "exceed the model's context limits. "
                    "Ask the user to specify which columns they want, or use a targeted query."
                )

        max_sql_length = int(safety_settings.get("max_sql_length", 50000))
        if len(sql_query) > max_sql_length:
            raise ValidationError(
                f"SQL query is too long (max {max_sql_length} characters)"
            )

        logger.debug("SQL safety validation passed")

    @staticmethod
    def _extract_assistant_context_hints(content: str) -> list:
        """Extract context hints from a single assistant message."""
        hints = []
        lower = content.lower()
        if "sales" in lower:
            hints.append("Previous analysis involved sales data")
        if "customers" in lower:
            hints.append("Previous analysis involved customer data")
        if "last month" in lower:
            hints.append("User has been looking at monthly timeframes")
        if "$" in content or "revenue" in lower:
            hints.append("Previous analysis involved financial metrics")
        return hints

    def _summarize_conversation_context(self, messages: list) -> str:
        """
        Summarize conversation context for use in existing prompts.

        Args:
            messages: List of conversation messages

        Returns:
            str: Summarized context that can be included in existing prompts
        """
        if len(messages) <= 1:
            return ""

        context_settings = (
            getattr(self.config, "get_conversation_context_settings", lambda: {})()
            or {}
        )
        window = int(context_settings.get("max_history_messages", 6))
        recent_messages = messages[-window:]
        context_parts: list = []

        for msg in recent_messages:
            if msg.get("role") == "assistant":
                context_parts.extend(
                    self._extract_assistant_context_hints(msg.get("content", ""))
                )
                break

        user_messages = [m for m in recent_messages if m.get("role") == "user"]
        if len(user_messages) >= 2:
            previous_question = user_messages[-2].get("content", "")
            if previous_question:
                context_parts.append(f"Previous question was: {previous_question}")

        return (
            ("Conversation context: " + ". ".join(context_parts) + ".")
            if context_parts
            else ""
        )

    # =============================================================================
    # BACKWARD COMPATIBILITY METHODS
    # =============================================================================

    def create_workflow(self):
        """
        Create and return the workflow graph (for backward compatibility).

        Returns:
            StateGraph (not compiled)
        """
        logger.warning(
            "create_workflow() is deprecated, workflow is now pre-compiled during initialization"
        )
        return self._create_workflow()

    def run(self, question: str) -> dict:
        """Legacy method - use query() instead."""
        logger.warning("run() is deprecated, use query() instead")
        return self.query(question)

    def run_sql_agent(self, question: str) -> dict:
        """Legacy method - use query() instead."""
        logger.warning("run_sql_agent() is deprecated, use query() instead")
        return self.query(question)

    # =============================================================================
    # EXPORT METHODS (New in v0.6.0)
    # =============================================================================

    def export_to_pptx(
        self,
        output_state: WorkflowState,
        title: str = _DEFAULT_REPORT_TITLE,
        company_name: str = _DEFAULT_COMPANY_NAME,
        include_sql: bool = False,
        include_data_table: bool = True,
        chart_style: str = "modern",
        brand_colors: Dict[str, tuple] = None,
    ) -> bytes:
        """
        Export query results to PowerPoint presentation (bytes).

        Args:
            output_state: Complete WorkflowState from query() or chat()
            title: Presentation title (default: "Query Results")
            company_name: Company name for branding (default: "Data Analytics")
            include_sql: Include SQL query slide (default: False)
            include_data_table: Include data table slide (default: True)
            chart_style: Chart visual style - "modern" or "classic" (default: "modern")
            brand_colors: Custom brand colors {"primary": (r,g,b), "secondary": (r,g,b)}

        Returns:
            bytes: PPTX file bytes that can be saved or streamed

        Raises:
            ExportError: If export fails
            ImportError: If required dependencies not installed

        Example:
            >>> from askrita import SQLAgentWorkflow, ConfigManager
            >>> config = ConfigManager("config.yaml")
            >>> workflow = SQLAgentWorkflow(config)
            >>>
            >>> # Get results
            >>> result = workflow.query("Show me sales by region")
            >>>
            >>> # Export to PPTX
            >>> pptx_bytes = workflow.export_to_pptx(
            ...     result,
            ...     title="Q4 Sales Report",
            ...     company_name="Acme Corp",
            ...     include_sql=True,
            ...     brand_colors={
            ...         "primary": (0, 47, 135),
            ...         "secondary": (204, 9, 47)
            ...     }
            ... )
            >>>
            >>> # Save to file
            >>> with open("sales_report.pptx", "wb") as f:
            ...     f.write(pptx_bytes)
            >>> print("Report saved to sales_report.pptx")
        """
        # Lazy import to avoid requiring export dependencies for core functionality
        from ..exporters.core import create_pptx_export
        from ..exporters.models import ExportSettings

        # Build settings
        settings = ExportSettings(
            title=title,
            company_name=company_name,
            include_sql=include_sql,
            include_data_table=include_data_table,
            chart_style=chart_style,
        )

        # Apply custom brand colors if provided
        if brand_colors:
            if "primary" in brand_colors:
                settings.brand_primary_color = brand_colors["primary"]
            if "secondary" in brand_colors:
                settings.brand_secondary_color = brand_colors["secondary"]

        logger.info(f"Exporting to PPTX: {title}")
        return create_pptx_export(output_state, settings)

    def export_to_pdf(
        self,
        output_state: WorkflowState,
        title: str = _DEFAULT_REPORT_TITLE,
        company_name: str = _DEFAULT_COMPANY_NAME,
        include_sql: bool = False,
        include_data_table: bool = True,
        chart_style: str = "modern",
    ) -> bytes:
        """
        Export query results to PDF report (bytes).

        Args:
            output_state: Complete WorkflowState from query() or chat()
            title: Report title (default: "Query Results")
            company_name: Company name for header (default: "Data Analytics")
            include_sql: Include SQL query in report (default: False)
            include_data_table: Include data table (default: True)
            chart_style: Chart visual style - "modern" or "classic" (default: "modern")

        Returns:
            bytes: PDF file bytes that can be saved or streamed

        Raises:
            ExportError: If export fails
            ImportError: If required dependencies not installed

        Example:
            >>> from askrita import SQLAgentWorkflow, ConfigManager
            >>> config = ConfigManager("config.yaml")
            >>> workflow = SQLAgentWorkflow(config)
            >>>
            >>> # Get results
            >>> result = workflow.query("Show me sales by region")
            >>>
            >>> # Export to PDF
            >>> pdf_bytes = workflow.export_to_pdf(
            ...     result,
            ...     title="Q4 Sales Report",
            ...     company_name="Acme Corp",
            ...     include_sql=True,
            ...     chart_style="modern"
            ... )
            >>>
            >>> # Save to file
            >>> with open("sales_report.pdf", "wb") as f:
            ...     f.write(pdf_bytes)
            >>> print("Report saved to sales_report.pdf")
        """
        # Lazy import to avoid requiring export dependencies for core functionality
        from ..exporters.core import create_pdf_export
        from ..exporters.models import ExportSettings

        # Build settings
        settings = ExportSettings(
            title=title,
            company_name=company_name,
            include_sql=include_sql,
            include_data_table=include_data_table,
            chart_style=chart_style,
        )

        logger.info(f"Exporting to PDF: {title}")
        return create_pdf_export(output_state, settings)

    def export_to_excel(
        self,
        output_state: WorkflowState,
        title: str = _DEFAULT_REPORT_TITLE,
        company_name: str = _DEFAULT_COMPANY_NAME,
        include_sql: bool = False,
        include_data_table: bool = True,
        chart_style: str = "modern",
        brand_colors: Dict[str, tuple] = None,
    ) -> bytes:
        """
        Export query results to Excel workbook with native multi-axis charts (bytes).

        Excel export provides:
        - Native Excel charts (fully editable, supports multi-axis)
        - Data tables with professional formatting
        - Optional SQL query
        - Follow-up questions on separate worksheet

        Args:
            output_state: Complete WorkflowState from query() or chat()
            title: Report title (default: "Query Results")
            company_name: Company name for header (default: "Data Analytics")
            include_sql: Include SQL query in workbook (default: False)
            include_data_table: Include data table (default: True)
            chart_style: Chart visual style - "modern" or "classic" (default: "modern")
            brand_colors: Optional brand colors {"primary": (R,G,B), "secondary": (R,G,B)}

        Returns:
            bytes: Excel file bytes that can be saved or streamed

        Raises:
            ExportError: If export fails
            ImportError: If required dependencies not installed (xlsxwriter)

        Example:
            >>> from askrita import SQLAgentWorkflow, ConfigManager
            >>> config = ConfigManager("config.yaml")
            >>> workflow = SQLAgentWorkflow(config)
            >>>
            >>> # Get results with multi-axis chart
            >>> result = workflow.query("Show me revenue and customer count by region")
            >>>
            >>> # Export to Excel with native multi-axis chart
            >>> excel_bytes = workflow.export_to_excel(
            ...     result,
            ...     title="Regional Analysis",
            ...     company_name="Acme Corp",
            ...     include_sql=True,
            ...     brand_colors={
            ...         "primary": (0, 47, 135),
            ...         "secondary": (204, 9, 47)
            ...     }
            ... )
            >>>
            >>> # Save to file
            >>> with open("analysis.xlsx", "wb") as f:
            ...     f.write(excel_bytes)
            >>> print("Excel workbook saved to analysis.xlsx")
            >>>
            >>> # Chart will have:
            >>> # - Primary Y-axis for Revenue
            >>> # - Secondary Y-axis for Customer Count
            >>> # - Fully editable in Excel
        """
        # Lazy import to avoid requiring export dependencies for core functionality
        from ..exporters.excel_exporter import create_excel_export
        from ..exporters.models import ExportSettings

        # Build settings
        settings = ExportSettings(
            title=title,
            company_name=company_name,
            include_sql=include_sql,
            include_data_table=include_data_table,
            chart_style=chart_style,
        )

        # Apply brand colors if provided
        if brand_colors:
            if "primary" in brand_colors:
                settings.brand_primary_color = brand_colors["primary"]
            if "secondary" in brand_colors:
                settings.brand_secondary_color = brand_colors["secondary"]

        logger.info(f"Exporting to Excel: {title}")
        return create_excel_export(output_state, settings)
