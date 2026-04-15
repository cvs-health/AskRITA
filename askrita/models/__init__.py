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
Pydantic models for AskRITA.

Provides strongly typed models to replace Dict[str, Any] usage.
"""

from .chain_of_thoughts import (
    ChainOfThoughtsOutput,
    ClarificationQuestion,
    ExecutionResult,
    ReasoningSummary,
    SqlCorrection,
    SqlDraft,
    UserQuestion,
    VisualizationSpec,
    VizOptions,
)
from .recommendations import RecommendedAction
from .step_details import StepDetails

__all__ = [
    "StepDetails",
    "RecommendedAction",
    # Chain-of-Thoughts models
    "UserQuestion",
    "ReasoningSummary",
    "SqlDraft",
    "SqlCorrection",
    "ClarificationQuestion",
    "ExecutionResult",
    "VizOptions",
    "VisualizationSpec",
    "ChainOfThoughtsOutput",
]
