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
Pydantic model for recommended actions.

Replaces Dict[str, Any] for recommendation data.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RecommendedAction(BaseModel):
    """
    Strongly typed model for recommended user actions.

    Provides clear guidance when queries fail or need clarification.
    """

    # Pydantic v2 configuration
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "add_timeframe",
                "title": "Add a time period",
                "guidance": "Specify when: 'in October 2023', 'last quarter', or 'from April to September'",
                "priority": 1,
                "action_type": "clarify",
            }
        }
    )

    id: str = Field(..., min_length=1, description="Unique identifier for the action")
    title: str = Field(
        ..., min_length=1, max_length=100, description="Short action title (5-7 words)"
    )
    guidance: str = Field(
        ..., min_length=1, description="Specific, actionable advice with examples"
    )
    priority: int = Field(
        default=1, ge=1, le=5, description="Priority level (1=highest, 5=lowest)"
    )
    action_type: Optional[str] = Field(
        None,
        description="Type of action: 'clarify', 'retry', 'escalate', 'modify', etc.",
    )

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        """Ensure title is not empty after stripping whitespace."""
        if not v or not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()

    @field_validator("guidance")
    @classmethod
    def guidance_not_empty(cls, v: str) -> str:
        """Ensure guidance is not empty after stripping whitespace."""
        if not v or not v.strip():
            raise ValueError("Guidance cannot be empty")
        return v.strip()
