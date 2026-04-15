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

"""
State definitions for the SQL Agent workflow using Pydantic models.
Provides type safety and validation for all workflow states.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .formatters.DataFormatter import UniversalChartData

# Import Chain-of-Thoughts models for state tracking
try:
    from ...models.chain_of_thoughts import SqlCorrection
except ImportError:
    # Fallback if models not available
    SqlCorrection = None


class WorkflowState(BaseModel):
    """
    Complete workflow state for SQL Agent using Pydantic for type safety.

    This single state model handles all phases of the workflow:
    - Input (question, messages)
    - Processing (parsed_question, unique_nouns, sql_query, etc.)
    - Output (answer, visualization, chart_data, etc.)
    """

    # Core input fields
    question: Optional[str] = Field(default=None, description="Original user question")
    messages: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Chat message history"
    )

    # Processing fields (populated during workflow execution)
    parsed_question: Optional[Dict[str, Any]] = Field(
        default=None, description="Parsed question components"
    )
    unique_nouns: Optional[List[str]] = Field(
        default=None, description="Extracted nouns from question"
    )
    sql_query: Optional[str] = Field(default=None, description="Generated SQL query")
    sql_reason: Optional[str] = Field(
        default=None, description="Reasoning for SQL generation"
    )
    sql_valid: Optional[bool] = Field(
        default=None, description="Whether SQL query is valid"
    )
    sql_issues: Optional[str] = Field(default=None, description="SQL validation issues")
    sql_correction: Optional[Any] = Field(
        default=None,
        description="SqlCorrection model if SQL was corrected during validation",
    )
    results: Optional[List[Any]] = Field(
        default=None, description="Query execution results"
    )

    # Output fields
    answer: Optional[str] = Field(
        default=None,
        description="short paragraph to summarize the results and analysis",
    )
    analysis: Optional[str] = Field(
        default=None, description="detailed analysis of the question and results"
    )
    error: Optional[str] = Field(default=None, description="Error message if any")
    visualization: Optional[str] = Field(
        default=None, description="Chosen visualization type"
    )
    visualization_reason: Optional[str] = Field(
        default=None, description="Reasoning for visualization choice"
    )

    # Chart data - UniversalChartData only (legacy format removed)
    chart_data: Optional[UniversalChartData] = Field(
        default=None,
        description="UniversalChartData Pydantic object for type-safe chart rendering",
    )

    followup_questions: Optional[List[str]] = Field(
        default=None, description="Suggested follow-up questions"
    )
    chain_of_thoughts: Optional[Dict[str, Any]] = Field(
        default=None, description="Detailed chain-of-thought tracking data"
    )

    # Error handling and workflow control
    execution_error: Optional[str] = Field(
        default=None, description="Execution error details"
    )
    retry_count: int = Field(default=0, description="Number of retries attempted")
    is_relevant: Optional[bool] = Field(
        default=None, description="Whether question is relevant to database"
    )
    needs_clarification: bool = Field(
        default=False,
        description="Whether workflow requires additional input from the user",
    )
    clarification_prompt: Optional[str] = Field(
        default=None, description="Message asking the user for clarification"
    )
    clarification_questions: Optional[List[str]] = Field(
        default=None,
        description="Specific questions to ask the user when clarification is needed",
    )

    # Pydantic v2 configuration
    model_config = ConfigDict(
        # Allow arbitrary types for chart_data to support UniversalChartData objects
        arbitrary_types_allowed=True,
        # Validate assignment to catch issues early
        validate_assignment=True,
    )

    def to_output_dict(self) -> Dict[str, Any]:
        """
        Convert to output dictionary with proper defaults for client consumption.
        This ensures all fields have sensible defaults for API responses.
        """
        return {
            "question": self.question,
            "parsed_question": self.parsed_question or {},
            "unique_nouns": self.unique_nouns or [],
            "sql_query": self.sql_query or "",
            "sql_reason": self.sql_reason or "",
            "sql_valid": self.sql_valid or False,
            "sql_issues": self.sql_issues or "",
            "results": self.results or [],
            "answer": self.answer or "",
            "analysis": self.analysis or "",
            "error": self.error or "",
            "visualization": self.visualization or "none",
            "visualization_reason": self.visualization_reason or "",
            "chart_data": self.chart_data,  # Only UniversalChartData now
            "followup_questions": self.followup_questions or [],
            "execution_error": self.execution_error,
            "retry_count": self.retry_count,
            "needs_clarification": self.needs_clarification,
            "clarification_prompt": self.clarification_prompt or "",
            "clarification_questions": self.clarification_questions or [],
        }
