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

"""Tests for askrita/utils/llm_models.py – covers all branches."""

from unittest.mock import MagicMock, patch

import pytest


class TestGetLlmModel:
    """Tests for the get_llm_model utility function."""

    def test_raises_when_no_api_key_and_no_env_var(self, monkeypatch):
        """Raise ValueError when neither api_key nor OPENAI_API_KEY is set."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        from askrita.utils.llm_models import get_llm_model

        with pytest.raises(ValueError, match="OpenAI API key is required"):
            get_llm_model()

    def test_raises_when_api_key_is_empty_string(self, monkeypatch):
        """Raise ValueError when api_key is an empty string."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        from askrita.utils.llm_models import get_llm_model

        with pytest.raises(ValueError, match="OpenAI API key is required"):
            get_llm_model(api_key="")

    def test_uses_env_var_when_api_key_not_provided(self, monkeypatch):
        """Read API key from OPENAI_API_KEY env var when api_key is None."""
        monkeypatch.setenv("OPENAI_API_KEY", "env-test-key")
        from askrita.utils.llm_models import get_llm_model

        with patch("askrita.utils.llm_models.ChatOpenAI") as mock_openai:
            mock_instance = MagicMock()
            mock_openai.return_value = mock_instance

            result = get_llm_model()

            mock_openai.assert_called_once()
            call_kwargs = mock_openai.call_args[1]
            assert call_kwargs["api_key"] == "env-test-key"
            assert result is mock_instance

    def test_default_model_and_params_forwarded(self, monkeypatch):
        """Default model name, temperature, and max_tokens are passed to ChatOpenAI."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        from askrita.utils.constants import MAX_TOKENS, TEMPERATURE, GPT_4o
        from askrita.utils.llm_models import get_llm_model

        with patch("askrita.utils.llm_models.ChatOpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()

            get_llm_model()

            call_kwargs = mock_openai.call_args[1]
            assert call_kwargs["model"] == GPT_4o
            assert call_kwargs["temperature"] == TEMPERATURE
            assert call_kwargs["max_tokens"] == MAX_TOKENS

    def test_custom_model_and_params_forwarded(self, monkeypatch):
        """Custom model name, temperature, and max_tokens are forwarded correctly."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        from askrita.utils.llm_models import get_llm_model

        with patch("askrita.utils.llm_models.ChatOpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()

            get_llm_model(model_name="gpt-4-turbo", temperature=0.5, max_tokens=512)

            call_kwargs = mock_openai.call_args[1]
            assert call_kwargs["model"] == "gpt-4-turbo"
            assert call_kwargs["temperature"] == 0.5
            assert call_kwargs["max_tokens"] == 512
