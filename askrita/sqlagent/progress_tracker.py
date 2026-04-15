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
Progress tracking interfaces and utilities for SQLAgentWorkflow.

This module provides optional progress tracking capabilities that can be used
by FastAPI clients or other applications to monitor workflow step execution.
"""

import time
from enum import Enum
from typing import Any, Callable, Dict, Optional


class ProgressStatus(Enum):
    """Progress status enumeration for workflow steps."""

    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# User-friendly progress messages for each workflow step
PROGRESS_MESSAGES = {
    "parse_question": "🔍 Analyzing your question...",
    "get_unique_nouns": "📝 Extracting key terms...",
    "generate_sql": "⚡ Generating SQL query...",
    "validate_and_fix_sql": "✅ Validating SQL query...",
    "execute_sql": "🚀 Executing query...",
    "format_results": "📊 Formatting results...",
    "choose_visualization": "📈 Choosing visualization...",
    "format_data_for_visualization": "🎨 Formatting data for visualization...",
    "choose_and_format_visualization": "📈 Preparing visualization...",
    "generate_followup_questions": "💡 Generating follow-up questions...",
    "parallel_dispatcher": "🔄 Processing results...",
}


class ProgressData:
    """Progress data structure passed to progress callbacks with optional step outcomes."""

    def __init__(
        self,
        step_name: str,
        status: ProgressStatus,
        message: Optional[str] = None,
        error: Optional[str] = None,
        step_index: Optional[int] = None,
        total_steps: Optional[int] = None,
        step_data: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize progress data with optional step outcomes.

        Args:
            step_name: Name of the workflow step
            status: Current status of the step
            message: Human-readable progress message
            error: Error message if step failed
            step_index: Current step index (optional)
            total_steps: Total number of steps (optional)
            step_data: Dictionary containing step outcomes and results (optional)
        """
        self.step_name = step_name
        self.status = status
        self.message = message or PROGRESS_MESSAGES.get(
            step_name, f"{step_name} {status.value}"
        )
        self.error = error
        self.step_index = step_index
        self.total_steps = total_steps
        self.step_data = step_data or {}  # Store step outcomes here
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert progress data to dictionary for JSON serialization."""
        return {
            "step_name": self.step_name,
            "status": self.status.value,
            "message": self.message,
            "error": self.error,
            "step_index": self.step_index,
            "total_steps": self.total_steps,
            "step_data": self.step_data,  # Include step outcomes
            "timestamp": self.timestamp,
        }


# Type alias for progress callback functions
ProgressCallback = Callable[[ProgressData], None]


def create_simple_progress_callback() -> ProgressCallback:
    """
    Create a simple progress callback that logs to console.
    Useful for testing or simple applications.
    """

    def callback(progress: ProgressData):
        status_emoji = {
            ProgressStatus.STARTED: "🟡",
            ProgressStatus.COMPLETED: "🟢",
            ProgressStatus.FAILED: "🔴",
            ProgressStatus.SKIPPED: "⚪",
        }
        emoji = status_emoji.get(progress.status, "⚫")
        print(f"{emoji} {progress.message}")
        if progress.error:
            print(f"   Error: {progress.error}")

    return callback
