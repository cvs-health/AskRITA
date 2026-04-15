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
#   langchain-openai (MIT)

"""Utility functions for creating and managing LLM model instances."""

import os
from typing import Optional

from langchain_openai import ChatOpenAI

from .constants import MAX_TOKENS, TEMPERATURE, GPT_4o


def get_llm_model(
    model_name: str = GPT_4o,
    temperature: float = TEMPERATURE,
    max_tokens: int = MAX_TOKENS,
    api_key: Optional[str] = None,
) -> ChatOpenAI:
    """
    Get an LLM model instance with the specified configuration.

    Args:
        model_name: The name of the model to use (default: GPT_4o)
        temperature: The temperature setting for the model (default: TEMPERATURE)
        max_tokens: Maximum number of tokens for the response (default: MAX_TOKENS)
        api_key: OpenAI API key (if not provided, will use OPENAI_API_KEY env var)

    Returns:
        ChatOpenAI: Configured LLM model instance

    Raises:
        ValueError: If no API key is provided or found in environment
    """
    if api_key is None:
        api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError(
            "OpenAI API key is required. Either pass it as api_key parameter "
            "or set the OPENAI_API_KEY environment variable."
        )

    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=api_key,
    )
