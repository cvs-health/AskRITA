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
#   langchain-core (MIT)

"""Utility functions for token counting and context management."""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage

from .constants import CONTEXT_SAFETY_MARGIN, MODEL_CONTEXT_LIMITS

logger = logging.getLogger(__name__)


def estimate_token_count(text: str) -> int:
    """
    Estimate token count for text using a simple heuristic.

    This is a rough approximation: 1 token ≈ 4 characters for English text.
    For more accurate counting, consider using tiktoken for OpenAI models.

    Args:
        text: Input text to count tokens for

    Returns:
        Estimated token count
    """
    if not text:
        return 0

    # Simple heuristic: roughly 4 characters per token
    # This tends to overestimate slightly, which is safer
    return len(text) // 4 + 1


def estimate_messages_token_count(messages: List[BaseMessage]) -> int:
    """
    Estimate token count for a list of messages.

    Args:
        messages: List of chat messages

    Returns:
        Estimated total token count
    """
    total_tokens = 0

    for message in messages:
        # Add tokens for the message content
        if hasattr(message, "content") and message.content:
            total_tokens += estimate_token_count(str(message.content))

        # Add overhead for message structure (role, formatting, etc.)
        total_tokens += 10  # Rough estimate for message overhead

    return total_tokens


def get_model_context_limit(model_name: str) -> int:
    """
    Get the context limit for a specific model.

    Args:
        model_name: Name of the LLM model

    Returns:
        Context limit in tokens, or default if model not found
    """
    # Clean up model name to handle variations
    clean_model = model_name.lower().strip()

    # Try exact match first
    if clean_model in MODEL_CONTEXT_LIMITS:
        return MODEL_CONTEXT_LIMITS[clean_model]

    # Try partial matches for common patterns
    for model_key, limit in MODEL_CONTEXT_LIMITS.items():
        if model_key in clean_model or clean_model.startswith(model_key):
            return limit

    # Default to a conservative limit if model not found
    logger.warning(f"Unknown model '{model_name}', using conservative context limit")
    return 8192  # Conservative default


def get_safe_context_limit(model_name: str) -> int:
    """
    Get the safe context limit (with safety margin) for a model.

    Args:
        model_name: Name of the LLM model

    Returns:
        Safe context limit in tokens
    """
    max_limit = get_model_context_limit(model_name)
    return int(max_limit * CONTEXT_SAFETY_MARGIN)


def truncate_text_to_tokens(
    text: str, max_tokens: int, truncate_from: str = "middle"
) -> str:
    """
    Truncate text to fit within a token limit.

    Args:
        text: Text to truncate
        max_tokens: Maximum number of tokens allowed
        truncate_from: Where to truncate from ("start", "middle", "end")

    Returns:
        Truncated text
    """
    if not text:
        return text

    current_tokens = estimate_token_count(text)
    if current_tokens <= max_tokens:
        return text

    # Calculate target character length (rough approximation)
    target_chars = max_tokens * 4

    if truncate_from == "start":
        # Keep the end
        truncated = text[-target_chars:]
        return f"...[truncated from start]...\n{truncated}"

    elif truncate_from == "end":
        # Keep the beginning
        truncated = text[:target_chars]
        return f"{truncated}\n...[truncated from end]..."

    else:  # middle (default)
        # Keep beginning and end
        keep_chars = target_chars // 2
        beginning = text[:keep_chars]
        end = text[-keep_chars:]
        return f"{beginning}\n...[truncated from middle]...\n{end}"


def truncate_list_to_tokens(
    items: List[str], max_tokens: int, item_separator: str = ", "
) -> str:
    """
    Truncate a list of items to fit within a token limit.

    Args:
        items: List of string items to include
        max_tokens: Maximum number of tokens allowed
        item_separator: Separator between items

    Returns:
        Truncated string representation of the list
    """
    if not items:
        return ""

    result_parts = []
    current_tokens = 0
    truncated_count = 0

    for item in items:
        item_str = str(item)
        item_tokens = estimate_token_count(item_str + item_separator)

        if current_tokens + item_tokens <= max_tokens:
            result_parts.append(item_str)
            current_tokens += item_tokens
        else:
            truncated_count = len(items) - len(result_parts)
            break

    result = item_separator.join(result_parts)

    if truncated_count > 0:
        result += f"{item_separator}...[{truncated_count} items truncated]"

    return result


def optimize_context_for_model(
    schema: str,
    unique_nouns: List[str],
    question: str,
    parsed_question: Dict[str, Any],
    model_name: str,
    additional_context: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Optimize context size to fit within model limits by intelligently truncating.

    Args:
        schema: Database schema
        unique_nouns: List of unique nouns from database
        question: User question
        parsed_question: Parsed question structure
        model_name: LLM model name
        additional_context: Optional additional context to include

    Returns:
        Optimized context dictionary
    """
    safe_limit = get_safe_context_limit(model_name)

    # Estimate token usage for each component
    question_tokens = estimate_token_count(question)
    parsed_question_tokens = estimate_token_count(str(parsed_question))
    schema_tokens = estimate_token_count(schema)
    nouns_tokens = estimate_token_count(", ".join(unique_nouns))

    additional_tokens = 0
    if additional_context:
        for value in additional_context.values():
            additional_tokens += estimate_token_count(str(value))

    # Reserve tokens for prompts and response (estimated)
    prompt_overhead = 2000  # Conservative estimate for system prompt + formatting
    total_used = (
        question_tokens
        + parsed_question_tokens
        + schema_tokens
        + nouns_tokens
        + additional_tokens
        + prompt_overhead
    )

    logger.info(
        f"Token usage estimate: Question={question_tokens}, Schema={schema_tokens}, "
        f"Nouns={nouns_tokens}, Additional={additional_tokens}, "
        f"Total={total_used}, Limit={safe_limit}"
    )

    # If we're within limits, return as-is
    if total_used <= safe_limit:
        result = {
            "schema": schema,
            "unique_nouns": unique_nouns,
            "question": question,
            "parsed_question": parsed_question,
        }
        if additional_context:
            result.update(additional_context)
        return result

    # We need to truncate - prioritize based on importance
    available_tokens = (
        safe_limit
        - question_tokens
        - parsed_question_tokens
        - additional_tokens
        - prompt_overhead
    )

    # Split available tokens between schema and nouns
    # Prioritize schema over nouns (60/40 split)
    schema_budget = int(available_tokens * 0.6)
    nouns_budget = available_tokens - schema_budget

    # Truncate schema if needed
    optimized_schema = schema
    if schema_tokens > schema_budget:
        logger.warning(
            f"Truncating schema from {schema_tokens} to {schema_budget} tokens"
        )
        optimized_schema = truncate_text_to_tokens(schema, schema_budget, "middle")

    # Truncate nouns if needed
    optimized_nouns = unique_nouns
    if nouns_tokens > nouns_budget:
        logger.warning(
            f"Truncating unique nouns from {len(unique_nouns)} items to fit {nouns_budget} tokens"
        )
        nouns_str = truncate_list_to_tokens(unique_nouns, nouns_budget)
        optimized_nouns = nouns_str.split(", ") if nouns_str else []

    result = {
        "schema": optimized_schema,
        "unique_nouns": optimized_nouns,
        "question": question,
        "parsed_question": parsed_question,
    }

    if additional_context:
        result.update(additional_context)

    # Log the optimization results
    final_tokens = estimate_token_count(str(result))
    logger.info(f"Context optimized from {total_used} to ~{final_tokens} tokens")

    return result
