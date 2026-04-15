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

"""Constants for LLM configuration and model parameters."""

# Model names
GPT_4o = "gpt-4o"
GPT_4o_MINI = "gpt-4o-mini"
GPT_4_1 = "gpt-4.1"
GPT_4_TURBO = "gpt-4-turbo"
GPT_3_5_TURBO = "gpt-3.5-turbo"  # legacy — kept for backward compatibility

# Model parameters
TEMPERATURE = 0.1
MAX_TOKENS = 4000
TOP_P = 1.0
FREQUENCY_PENALTY = 0.0
PRESENCE_PENALTY = 0.0

# Default model configuration
DEFAULT_MODEL = GPT_4o
DEFAULT_TEMPERATURE = TEMPERATURE
DEFAULT_MAX_TOKENS = MAX_TOKENS

# Context length limits for different models
MODEL_CONTEXT_LIMITS = {
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4.1": 128000,  # Azure OpenAI GPT-4 variant with large context
    "gpt-4": 8192,
    "gpt-3.5-turbo": 16384,
    "gpt-3.5-turbo-16k": 16384,
    "claude-4-opus": 200000,
    "claude-4-sonnet": 200000,
    "claude-4.6-sonnet": 200000,
    "claude-4.6-haiku": 200000,
    "claude-3-opus": 200000,
    "claude-3-sonnet": 200000,
    "claude-3-haiku": 200000,
    "gemini-pro": 30720,
    "gemini-1.5-pro": 2097152,
    "gemini-2.5-pro": 1048576,
    "gemini-2.5-flash": 1048576,
}

# Safety margin for context length (leave room for response)
CONTEXT_SAFETY_MARGIN = 0.8  # Use only 80% of available context


# ============================================================================
# DISPLAY LIMITS CONSTANTS
# ============================================================================


class DisplayLimits:
    """Constants for truncation limits used throughout the codebase for display and logging."""

    # Question and input previews
    QUESTION_PREVIEW = 100  # Characters for question previews in logs/progress
    INPUT_SUMMARY = 200  # Characters for input summaries in chain of thoughts

    # SQL query previews
    SQL_PREVIEW_SHORT = 200  # Short SQL previews (for error messages)
    SQL_PREVIEW_MEDIUM = 300  # Medium SQL previews (for progress tracking)
    SQL_PREVIEW_LONG = 500  # Long SQL previews (for detailed progress)

    # Reasoning and explanation previews
    REASONING_PREVIEW = 200  # Characters for reasoning text previews
    VISUALIZATION_REASON = 200  # Characters for visualization reasoning

    # Error and status messages
    ERROR_MESSAGE = 200  # Characters for error messages in progress/CoT
    ANSWER_PREVIEW = 300  # Characters for answer previews

    # Data processing limits
    RESULTS_LIMIT_FOR_LLM = (
        100  # Max rows to send to LLM for formatting (token efficiency)
    )
    SCHEMA_DISPLAY_LINES = 100  # Max lines of schema to display
    SCHEMA_LINE_LENGTH = 100  # Max characters per schema line
    SCHEMA_FULL_DISPLAY = 10000  # Max characters for full schema display

    # Progress tracking limits
    PROGRESS_SQL_QUERY = 500  # SQL query length in progress data
    PROGRESS_SQL_REASON = 200  # SQL reasoning length in progress data


# ============================================================================
# CHAIN OF THOUGHTS CONSTANTS
# ============================================================================


class ConfidenceScores:
    """Confidence score thresholds for Chain of Thoughts step completion."""

    # High confidence scores (0.85 - 1.0)
    VERY_HIGH = 0.95  # SQL validation passed without issues
    HIGH = 0.9  # Parse relevant question, extract nouns, execute query, format viz data
    GOOD = 0.85  # Format results successfully

    # Medium confidence scores (0.6 - 0.84)
    MEDIUM_HIGH = (
        0.8  # SQL generation first attempt, choose visualization, LLM followup
    )
    MEDIUM_WITH_FIXES = 0.8  # SQL validation with fixes applied
    MEDIUM = 0.6  # SQL generation with retries, fallback followup questions

    # Low confidence scores (0.3 - 0.5)
    LOW = 0.5  # Disabled steps, skipped steps, no results, no data
    VERY_LOW = 0.3  # Question not relevant to database

    # Error condition
    ZERO = 0.0  # Error occurred during step execution

    @classmethod
    def get_sql_confidence(cls, retry_count: int) -> float:
        """Get confidence score for SQL generation based on retry count."""
        return cls.MEDIUM_HIGH if retry_count == 0 else cls.MEDIUM

    @classmethod
    def get_parse_confidence(cls, is_relevant: bool) -> float:
        """Get confidence score for question parsing based on relevance."""
        return cls.HIGH if is_relevant else cls.VERY_LOW


class WorkflowSteps:
    """Workflow step name constants (single source of truth)."""

    PARSE_QUESTION = "parse_question"
    GET_UNIQUE_NOUNS = "get_unique_nouns"
    GENERATE_SQL = "generate_sql"
    VALIDATE_SQL = "validate_and_fix_sql"
    EXECUTE_SQL = "execute_sql"
    FORMAT_RESULTS = "format_results"
    CHOOSE_VISUALIZATION = "choose_visualization"
    FORMAT_DATA_FOR_VISUALIZATION = "format_data_for_visualization"
    GENERATE_FOLLOWUP_QUESTIONS = "generate_followup_questions"


class StatusMessages:
    """Standard status messages for Chain of Thoughts step completion."""

    # Disabled/Skipped states
    DISABLED = "Step disabled in configuration"
    NO_QUERY = "No SQL query to validate"
    NO_RESULTS = "No results to format"
    NO_DATA = "No results or answer available, skipping follow-up generation"

    # Relevance states
    IRRELEVANT_NO_SQL = "Question not relevant to database, no SQL generated"
    IRRELEVANT_NO_NOUNS = "Question not relevant to database, no nouns extracted"

    # Success states
    PARSING_FAILED = "Parsing failed, using default fallback response"
    SQL_VALIDATION_FAILED = "Failed to validate SQL query"
    QUERY_EXECUTION_FAILED = "Query execution failed with exception"


class DetailKeys:
    """Standard detail dictionary keys for Chain of Thoughts step metadata."""

    # Status keys
    STEP_STATUS = "step_status"
    REASON = "reason"
    ERROR_TYPE = "error_type"

    # Parsing details
    IS_RELEVANT = "is_relevant"
    TABLE_COUNT = "table_count"
    PARSE_METHOD = "parse_method"

    # Nouns extraction details
    NOUNS_COUNT = "nouns_count"
    TABLES_PROCESSED = "tables_processed"

    # SQL generation details
    SQL_LENGTH = "sql_length"
    RETRY_COUNT = "retry_count"
    VALIDATION_FAILED = "validation_failed"

    # SQL validation details
    VALIDATION_STATUS = "validation_status"
    FIXES_APPLIED = "fixes_applied"
    ISSUES = "issues"

    # Query execution details
    ROW_COUNT = "row_count"
    EXECUTION_TIME_MS = "execution_time_ms"
    HEADERS = "headers"

    # Result formatting details
    ANSWER_LENGTH = "answer_length"
    FORMATTING_METHOD = "formatting_method"
    FORMATTING_TIME_MS = "formatting_time_ms"

    # Follow-up questions details
    QUESTION_COUNT = "question_count"
    GENERATION_METHOD = "generation_method"
    FALLBACK_REASON = "fallback_reason"

    # Visualization details
    VISUALIZATION_TYPE = "visualization_type"
    DATA_POINTS = "data_points"
    HAS_FORMATTED_DATA = "has_formatted_data"

    # Status values
    STATUS_DISABLED = "disabled"
    STATUS_SKIPPED = "skipped"
    STATUS_FAILED = "failed"
    STATUS_SUCCESS = "success"

    # Reason values
    REASON_DISABLED = "disabled"
    REASON_IRRELEVANT = "irrelevant_question"
    REASON_NO_QUERY = "no_query"
    REASON_NO_RESULTS = "no_results"
    REASON_NO_DATA = "no_data"

    # Method values
    METHOD_LLM = "llm"
    METHOD_LLM_TEMPLATE = "llm_template"
    METHOD_LLM_STRUCTURED = "llm_structured_output"
    METHOD_RULE_BASED = "rule_based"
    METHOD_OVERRIDE = "override"
