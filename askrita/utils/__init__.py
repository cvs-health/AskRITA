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

"""Utility modules for LLM models, managers, and constants."""

from .constants import (
    CONTEXT_SAFETY_MARGIN,
    MAX_TOKENS,
    MODEL_CONTEXT_LIMITS,
    TEMPERATURE,
    GPT_4o,
)
from .llm_models import get_llm_model
from .LLMManager import LLMManager
from .token_utils import (
    estimate_messages_token_count,
    estimate_token_count,
    get_model_context_limit,
    get_safe_context_limit,
    optimize_context_for_model,
    truncate_list_to_tokens,
    truncate_text_to_tokens,
)

__all__ = [
    "get_llm_model",
    "GPT_4o",
    "TEMPERATURE",
    "MAX_TOKENS",
    "MODEL_CONTEXT_LIMITS",
    "CONTEXT_SAFETY_MARGIN",
    "LLMManager",
    "estimate_token_count",
    "estimate_messages_token_count",
    "get_model_context_limit",
    "get_safe_context_limit",
    "truncate_text_to_tokens",
    "truncate_list_to_tokens",
    "optimize_context_for_model",
]
