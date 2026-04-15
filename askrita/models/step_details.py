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
Pydantic model for chain of thoughts step details.

Replaces Dict[str, Any] with properly validated structure.
"""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class StepDetails(BaseModel):
    """
    Strongly typed model for chain of thoughts step details.

    Provides validation for common step detail fields while remaining
    flexible for workflow-specific data.
    """

    # Pydantic v2 configuration
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "llm_calls": 2,
                "tokens_used": 1250,
                "llm_latency_ms": 850.5,
                "database_calls": 1,
                "rows_processed": 150,
                "query_time_ms": 320.8,
                "cache_hit": True,
                "cache_key": "schema:bigquery:project123",
                "retries": 0,
                "input_data": {"question": "What is the NPS?"},
                "output_data": {"tables": ["nps_scores"]},
                "extra": {"custom_field": "custom_value"},
            }
        }
    )

    # LLM-related metrics
    llm_calls: int = Field(
        default=0, ge=0, description="Number of LLM calls made in this step"
    )
    tokens_used: int = Field(
        default=0, ge=0, description="Total tokens used by LLM calls"
    )
    llm_latency_ms: Optional[float] = Field(
        None, ge=0, description="Total LLM call latency"
    )

    # Database-related metrics
    database_calls: int = Field(
        default=0, ge=0, description="Number of database queries"
    )
    rows_processed: Optional[int] = Field(
        None, ge=0, description="Rows processed/returned"
    )
    query_time_ms: Optional[float] = Field(
        None, ge=0, description="Database query execution time"
    )

    # Cache metrics
    cache_hit: bool = Field(default=False, description="Whether cache was hit")
    cache_key: Optional[str] = Field(None, description="Cache key used")

    # Retry information
    retries: int = Field(default=0, ge=0, description="Number of retries attempted")
    retry_strategy: Optional[str] = Field(None, description="Retry strategy used")

    # Input/Output data
    input_data: Optional[Any] = Field(None, description="Input data for the step")
    output_data: Optional[Any] = Field(None, description="Output data from the step")

    # Additional flexible fields
    extra: Optional[dict] = Field(
        default_factory=dict, description="Additional workflow-specific data"
    )
