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
Pydantic models for Chain-of-Thoughts feature.

These models replace Dict[str, Any] usage in public interfaces and provide
type safety for the Chain-of-Thoughts workflow.
"""

from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class UserQuestion(BaseModel):
    """The user's natural-language question with optional schema hints."""

    text: str = Field(..., description="The user's natural-language question")
    schema_hint: Optional[str] = Field(
        None, description="Optional table/DB hint if provided"
    )


class ReasoningSummary(BaseModel):
    """High-level bullet points explaining the approach taken."""

    steps: List[str] = Field(
        ..., description="High-level bullet points explaining the approach"
    )


class SqlDraft(BaseModel):
    """Draft SQL query with confidence score."""

    sql: str = Field(..., description="The generated SQL query")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0"
    )


class SqlCorrection(BaseModel):
    """SQL correction with original, corrected, and reason."""

    original_sql: str = Field(..., description="The original SQL query that had issues")
    corrected_sql: str = Field(..., description="The corrected SQL query")
    reason: str = Field(..., description="Explanation of why the correction was needed")


class ClarificationQuestion(BaseModel):
    """Question to ask the user for clarification."""

    question: str = Field(..., description="The clarification question to ask the user")
    rationale: str = Field(
        ..., description="Explanation of why clarification is needed"
    )


class ExecutionResult(BaseModel):
    """Query execution results with rows, columns, and count."""

    rows: List[List[Any]] = Field(
        ..., description="Query results as list of rows (each row is a list of values)"
    )
    columns: List[str] = Field(..., description="Column names for the results")
    row_count: int = Field(..., ge=0, description="Number of rows returned")


class VizOptions(BaseModel):
    """Visualization options with flexible extra fields."""

    model_config = ConfigDict(extra="allow")

    # Common options can be defined here, but extra fields are allowed


class VisualizationSpec(BaseModel):
    """Visualization specification for rendering results."""

    kind: str = Field(
        ..., description="Visualization type: e.g., 'bar', 'line', 'table', 'pie', etc."
    )
    x: Optional[str] = Field(None, description="X-axis column name")
    y: Optional[str] = Field(None, description="Y-axis column name")
    series: Optional[str] = Field(None, description="Series/grouping column name")
    options: Optional[VizOptions] = Field(
        None, description="Additional visualization options"
    )


class ChainOfThoughtsOutput(BaseModel):
    """Complete Chain-of-Thoughts output with reasoning, SQL, results, and visualization."""

    reasoning: ReasoningSummary = Field(..., description="High-level reasoning summary")
    sql: str = Field(..., description="The final SQL query that was executed")
    result: ExecutionResult = Field(..., description="Query execution results")
    viz: VisualizationSpec = Field(..., description="Visualization specification")
