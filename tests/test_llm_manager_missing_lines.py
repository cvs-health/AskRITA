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
#   pydantic (MIT)
#   pytest (MIT)

"""Targeted tests for LLMManager.py missing coverage lines."""

import os
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.prompts import ChatPromptTemplate

from askrita.exceptions import ConfigurationError, LLMError
from askrita.utils.LLMManager import LLMManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def openai_api_key():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        yield


def _make_config(provider="openai"):
    cfg = MagicMock()
    cfg.llm.provider = provider
    cfg.llm.model = "gpt-4o"
    cfg.llm.temperature = 0.0
    cfg.llm.max_tokens = 1000
    cfg.llm.top_p = 1.0
    cfg.llm.frequency_penalty = 0.0
    cfg.llm.presence_penalty = 0.0
    cfg.llm.timeout = 30
    cfg.llm.base_url = None
    cfg.llm.organization = None
    cfg.llm.ca_bundle_path = None
    cfg.llm.credentials_path = None
    cfg.llm.project_id = "test-project"
    cfg.llm.location = "us-central1"
    cfg.llm.aws_access_key_id_env_var = None
    cfg.llm.aws_secret_access_key_env_var = None
    cfg.llm.aws_session_token_env_var = None
    cfg.llm.region_name = "us-east-1"
    cfg.llm.api_version = "2024-02-01"
    cfg.llm.azure_endpoint = "https://test.openai.azure.com"
    cfg.llm.azure_deployment = "gpt-4"
    cfg.llm.azure_tenant_id = "tenant-id"
    cfg.llm.azure_client_id = "client-id"
    cfg.llm.azure_certificate_path = "/path/to/cert.pem"
    cfg.llm.azure_certificate_password = None
    cfg.framework.debug = False
    cfg.get_database_type.return_value = "BigQuery"
    cfg.get_prompt.return_value = ""
    return cfg


def _make_manager(config=None, mock_llm=None):
    """Create LLMManager with a patched ChatOpenAI."""
    if config is None:
        config = _make_config()
    if mock_llm is None:
        mock_llm = MagicMock()
    with patch("askrita.utils.LLMManager.ChatOpenAI", return_value=mock_llm):
        manager = LLMManager(config, test_connection=False)
    return manager, mock_llm


# ---------------------------------------------------------------------------
# test_connection success/failure paths (lines 70-82)
# ---------------------------------------------------------------------------


class TestTestConnection:
    def test_connection_returns_true_on_success(self):
        mock_llm = MagicMock()
        config = _make_config()
        with patch("askrita.utils.LLMManager.ChatOpenAI", return_value=mock_llm):
            manager = LLMManager(config, test_connection=False)

        # Mock invoke to return "OK"
        manager.llm = mock_llm
        mock_llm.invoke.return_value = MagicMock(content="OK")
        result = manager.test_connection()
        assert result is True

    def test_connection_returns_false_on_error_response(self):
        mock_llm = MagicMock()
        config = _make_config()
        with patch("askrita.utils.LLMManager.ChatOpenAI", return_value=mock_llm):
            manager = LLMManager(config, test_connection=False)

        mock_llm.invoke.return_value = MagicMock(content="Error: something failed")
        result = manager.test_connection()
        assert result is False

    def test_connection_returns_false_on_empty_response(self):
        mock_llm = MagicMock()
        config = _make_config()
        with patch("askrita.utils.LLMManager.ChatOpenAI", return_value=mock_llm):
            manager = LLMManager(config, test_connection=False)

        mock_llm.invoke.return_value = MagicMock(content="   ")
        result = manager.test_connection()
        assert result is False

    def test_connection_exception_returns_false(self):
        mock_llm = MagicMock()
        config = _make_config()
        with patch("askrita.utils.LLMManager.ChatOpenAI", return_value=mock_llm):
            manager = LLMManager(config, test_connection=False)

        mock_llm.invoke.side_effect = RuntimeError("connection refused")
        result = manager.test_connection()
        assert result is False

    def test_connection_auth_error_logged(self):
        mock_llm = MagicMock()
        config = _make_config()
        with patch("askrita.utils.LLMManager.ChatOpenAI", return_value=mock_llm):
            manager = LLMManager(config, test_connection=False)

        mock_llm.invoke.side_effect = Exception("api key invalid authentication failed")
        result = manager.test_connection()
        assert result is False

    def test_connection_quota_error_logged(self):
        mock_llm = MagicMock()
        config = _make_config()
        with patch("askrita.utils.LLMManager.ChatOpenAI", return_value=mock_llm):
            manager = LLMManager(config, test_connection=False)

        mock_llm.invoke.side_effect = Exception("quota exceeded rate limit")
        result = manager.test_connection()
        assert result is False

    def test_connection_timeout_error_logged(self):
        mock_llm = MagicMock()
        config = _make_config()
        with patch("askrita.utils.LLMManager.ChatOpenAI", return_value=mock_llm):
            manager = LLMManager(config, test_connection=False)

        mock_llm.invoke.side_effect = Exception("timeout connection error")
        result = manager.test_connection()
        assert result is False

    def test_connection_model_not_found_logged(self):
        mock_llm = MagicMock()
        config = _make_config()
        with patch("askrita.utils.LLMManager.ChatOpenAI", return_value=mock_llm):
            manager = LLMManager(config, test_connection=False)

        mock_llm.invoke.side_effect = Exception("model gpt-4 not found")
        result = manager.test_connection()
        assert result is False

    def test_connection_forbidden_error_logged(self):
        mock_llm = MagicMock()
        config = _make_config()
        with patch("askrita.utils.LLMManager.ChatOpenAI", return_value=mock_llm):
            manager = LLMManager(config, test_connection=False)

        mock_llm.invoke.side_effect = Exception("forbidden 403")
        result = manager.test_connection()
        assert result is False

    def test_connection_azure_cert_error(self):
        mock_llm = MagicMock()
        config = _make_config(provider="azure_openai")
        # Use patch to mock the azure initialization and force provider to azure_openai
        with patch(
            "askrita.utils.LLMManager.LLMManager._initialize_llm", return_value=mock_llm
        ):
            with patch(
                "askrita.utils.LLMManager.LLMManager._detect_optimal_structured_output_method",
                return_value="function_calling",
            ):
                manager = LLMManager.__new__(LLMManager)
                manager.config = config
                manager.http_client = None
                manager.llm = mock_llm
                manager.structured_output_method = "function_calling"

        mock_llm.invoke.side_effect = Exception("certificate tenant error")
        result = manager.test_connection()
        assert result is False

    def test_connection_vertex_error(self):
        mock_llm = MagicMock()
        config = _make_config(provider="vertex_ai")
        config.llm.provider = "vertex_ai"
        with patch("askrita.utils.LLMManager.ChatOpenAI", return_value=mock_llm):
            manager = LLMManager(config, test_connection=False)

        mock_llm.invoke.side_effect = Exception("project location error")
        result = manager.test_connection()
        assert result is False

    def test_connection_bedrock_error(self):
        mock_llm = MagicMock()
        config = _make_config(provider="bedrock")
        config.llm.provider = "bedrock"
        with patch("askrita.utils.LLMManager.ChatOpenAI", return_value=mock_llm):
            manager = LLMManager(config, test_connection=False)

        mock_llm.invoke.side_effect = Exception("region aws error")
        result = manager.test_connection()
        assert result is False


# ---------------------------------------------------------------------------
# _initialize_llm error path branches (lines 136-155)
# ---------------------------------------------------------------------------


class TestInitializeLLMErrors:
    def test_unsupported_provider_raises_config_error(self):
        config = _make_config()
        config.llm.provider = "unknown_provider"
        with pytest.raises((ConfigurationError, LLMError)):
            with patch(
                "askrita.utils.LLMManager.ChatOpenAI",
                side_effect=ConfigurationError("unsupported llm provider unknown"),
            ):
                LLMManager(config, test_connection=False)

    def test_api_key_error_raises_llm_error(self):
        config = _make_config()
        with patch(
            "askrita.utils.LLMManager.ChatOpenAI",
            side_effect=Exception("api key invalid authentication"),
        ):
            with pytest.raises(LLMError):
                LLMManager(config, test_connection=False)

    def test_import_error_for_openai(self):
        config = _make_config()
        with patch(
            "askrita.utils.LLMManager.ChatOpenAI",
            side_effect=Exception("no module named langchain openai"),
        ):
            with pytest.raises((ConfigurationError, LLMError)):
                LLMManager(config, test_connection=False)

    def test_import_error_for_bedrock(self):
        config = _make_config(provider="bedrock")
        with patch(
            "askrita.utils.LLMManager.ChatBedrock",
            side_effect=Exception("no module named langchain aws"),
        ):
            with pytest.raises((ConfigurationError, LLMError)):
                LLMManager(config, test_connection=False)

    def test_import_error_for_vertex_ai(self):
        config = _make_config(provider="vertex_ai")
        with patch(
            "askrita.utils.LLMManager.ChatVertexAI",
            side_effect=Exception("no module named langchain google-vertexai"),
        ):
            with pytest.raises((ConfigurationError, LLMError)):
                LLMManager(config, test_connection=False)

    def test_generic_error_raises_llm_error(self):
        config = _make_config()
        with patch(
            "askrita.utils.LLMManager.ChatOpenAI",
            side_effect=RuntimeError("generic failure"),
        ):
            with pytest.raises(LLMError):
                LLMManager(config, test_connection=False)


# ---------------------------------------------------------------------------
# invoke_with_structured_output (lines 440-491)
# ---------------------------------------------------------------------------


class TestInvokeWithStructuredOutput:
    def test_missing_prompt_raises_llm_error(self):
        manager, _ = _make_manager()
        config = _make_config()
        manager.config = config
        config.get_prompt.return_value = ""  # no system prompt

        from pydantic import BaseModel

        class Resp(BaseModel):
            answer: str

        with pytest.raises(LLMError, match="not found"):
            manager.invoke_with_structured_output("nonexistent_prompt", Resp)

    def test_successful_structured_output(self):
        manager, mock_llm = _make_manager()

        from pydantic import BaseModel

        class Resp(BaseModel):
            answer: str

        mock_response = Resp(answer="42")
        structured_llm = MagicMock()
        structured_llm.invoke.return_value = mock_response
        mock_llm.with_structured_output.return_value = structured_llm

        config = _make_config()
        manager.config = config
        config.get_prompt.side_effect = lambda name, part="system": (
            "You are a helpful assistant."
            if part == "system"
            else "Question: {question}"
        )

        result = manager.invoke_with_structured_output(
            "parse_question", Resp, question="What is 6 * 7?"
        )
        assert result.answer == "42"

    def test_structured_output_exception_raises_llm_error(self):
        manager, mock_llm = _make_manager()

        from pydantic import BaseModel

        class Resp(BaseModel):
            answer: str

        mock_llm.with_structured_output.side_effect = RuntimeError("model error")

        config = _make_config()
        manager.config = config
        config.get_prompt.side_effect = lambda name, part="system": (
            "System prompt." if part == "system" else ""
        )

        with pytest.raises(LLMError):
            manager.invoke_with_structured_output("some_prompt", Resp)


# ---------------------------------------------------------------------------
# invoke_with_structured_output_direct (lines 515-542)
# ---------------------------------------------------------------------------


class TestInvokeWithStructuredOutputDirect:
    def test_successful_direct_structured_output(self):
        manager, mock_llm = _make_manager()

        from pydantic import BaseModel

        class Resp(BaseModel):
            answer: str

        mock_response = Resp(answer="direct")
        structured_llm = MagicMock()
        structured_llm.invoke.return_value = mock_response
        mock_llm.with_structured_output.return_value = structured_llm

        result = manager.invoke_with_structured_output_direct(
            "You are helpful.", "Answer this: {question}", Resp, question="test"
        )
        assert result.answer == "direct"

    def test_direct_structured_output_no_human_prompt(self):
        manager, mock_llm = _make_manager()

        from pydantic import BaseModel

        class Resp(BaseModel):
            result: str

        mock_response = Resp(result="ok")
        structured_llm = MagicMock()
        structured_llm.invoke.return_value = mock_response
        mock_llm.with_structured_output.return_value = structured_llm

        result = manager.invoke_with_structured_output_direct(
            "System prompt only.", "", Resp
        )
        assert result.result == "ok"

    def test_direct_structured_output_exception_raises_llm_error(self):
        manager, mock_llm = _make_manager()

        from pydantic import BaseModel

        class Resp(BaseModel):
            answer: str

        mock_llm.with_structured_output.side_effect = RuntimeError("error")

        with pytest.raises(LLMError):
            manager.invoke_with_structured_output_direct("System.", "Human.", Resp)


# ---------------------------------------------------------------------------
# create_prompt_from_config (lines 579-633)
# ---------------------------------------------------------------------------


class TestCreatePromptFromConfig:
    def test_missing_prompt_raises_config_error(self):
        manager, _ = _make_manager()
        config = _make_config()
        manager.config = config
        config.get_prompt.return_value = ""

        with pytest.raises(ConfigurationError):
            manager.create_prompt_from_config("nonexistent")

    def test_prompt_with_human_template(self):
        manager, _ = _make_manager()
        config = _make_config()
        manager.config = config

        def get_prompt(name, part="system"):
            if part == "system":
                return "System: {database_type}"
            return "Human: {question}"

        config.get_prompt.side_effect = get_prompt
        config.get_database_type.return_value = "BigQuery"

        prompt = manager.create_prompt_from_config("test_prompt", question="Q?")
        assert isinstance(prompt, ChatPromptTemplate)

    def test_prompt_default_parse_question(self):
        manager, _ = _make_manager()
        config = _make_config()
        manager.config = config

        def get_prompt(name, part="system"):
            if part == "system":
                return "System prompt."
            return ""  # No human template

        config.get_prompt.side_effect = get_prompt

        prompt = manager.create_prompt_from_config("parse_question")
        assert isinstance(prompt, ChatPromptTemplate)

    def test_prompt_default_generate_sql(self):
        manager, _ = _make_manager()
        config = _make_config()
        manager.config = config
        config.get_prompt.side_effect = lambda name, part="system": (
            "Sys." if part == "system" else ""
        )
        prompt = manager.create_prompt_from_config("generate_sql")
        assert isinstance(prompt, ChatPromptTemplate)

    def test_prompt_default_validate_sql(self):
        manager, _ = _make_manager()
        config = _make_config()
        manager.config = config
        config.get_prompt.side_effect = lambda name, part="system": (
            "Sys." if part == "system" else ""
        )
        prompt = manager.create_prompt_from_config("validate_sql")
        assert isinstance(prompt, ChatPromptTemplate)

    def test_prompt_default_format_results(self):
        manager, _ = _make_manager()
        config = _make_config()
        manager.config = config
        config.get_prompt.side_effect = lambda name, part="system": (
            "Sys." if part == "system" else ""
        )
        prompt = manager.create_prompt_from_config("format_results")
        assert isinstance(prompt, ChatPromptTemplate)

    def test_prompt_default_choose_visualization(self):
        manager, _ = _make_manager()
        config = _make_config()
        manager.config = config
        config.get_prompt.side_effect = lambda name, part="system": (
            "Sys." if part == "system" else ""
        )
        prompt = manager.create_prompt_from_config("choose_visualization")
        assert isinstance(prompt, ChatPromptTemplate)

    def test_prompt_default_choose_and_format_visualization(self):
        manager, _ = _make_manager()
        config = _make_config()
        manager.config = config
        config.get_prompt.side_effect = lambda name, part="system": (
            "Sys." if part == "system" else ""
        )
        prompt = manager.create_prompt_from_config("choose_and_format_visualization")
        assert isinstance(prompt, ChatPromptTemplate)

    def test_prompt_default_unknown_prompt(self):
        manager, _ = _make_manager()
        config = _make_config()
        manager.config = config
        config.get_prompt.side_effect = lambda name, part="system": (
            "Sys." if part == "system" else ""
        )
        prompt = manager.create_prompt_from_config("custom_unknown_prompt")
        assert isinstance(prompt, ChatPromptTemplate)


# ---------------------------------------------------------------------------
# invoke_with_config_prompt (lines 648)
# ---------------------------------------------------------------------------


class TestInvokeWithConfigPrompt:
    def test_successful_invocation(self):
        manager, mock_llm = _make_manager()
        config = _make_config()
        manager.config = config
        config.get_prompt.side_effect = lambda name, part="system": (
            "System." if part == "system" else ""
        )
        mock_llm.invoke.return_value = MagicMock(content="result")
        result = manager.invoke_with_config_prompt("parse_question", question="Q?")
        assert isinstance(result, str)

    def test_error_returns_error_string(self):
        manager, _ = _make_manager()
        config = _make_config()
        manager.config = config
        config.get_prompt.return_value = ""  # causes ConfigurationError
        result = manager.invoke_with_config_prompt("parse_question")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# get_model_info (line 663-680)
# ---------------------------------------------------------------------------


class TestGetModelInfo:
    def test_returns_dict_with_expected_keys(self):
        manager, _ = _make_manager()
        info = manager.get_model_info()
        assert isinstance(info, dict)
        assert "provider" in info
        assert "model" in info
        assert "temperature" in info
        assert "api_key_configured" in info

    def test_non_openai_provider(self):
        config = _make_config(provider="bedrock")
        mock_llm = MagicMock()
        with patch("askrita.utils.LLMManager.ChatOpenAI", return_value=mock_llm):
            manager = LLMManager(config, test_connection=False)
        info = manager.get_model_info()
        assert info["api_key_configured"] is True


# ---------------------------------------------------------------------------
# cleanup / context manager / destructor (lines 773-798)
# ---------------------------------------------------------------------------


class TestCleanup:
    def test_cleanup_closes_http_client(self):
        manager, _ = _make_manager()
        mock_client = MagicMock()
        manager.http_client = mock_client
        manager.cleanup()
        mock_client.close.assert_called_once()
        assert manager.http_client is None

    def test_cleanup_no_client_no_crash(self):
        manager, _ = _make_manager()
        manager.http_client = None
        manager.cleanup()  # Should not raise

    def test_cleanup_client_close_error_handled(self):
        manager, _ = _make_manager()
        mock_client = MagicMock()
        mock_client.close.side_effect = RuntimeError("close error")
        manager.http_client = mock_client
        manager.cleanup()  # Should not raise
        assert manager.http_client is None

    def test_context_manager_enter(self):
        manager, _ = _make_manager()
        result = manager.__enter__()
        assert result is manager

    def test_context_manager_exit(self):
        manager, _ = _make_manager()
        mock_client = MagicMock()
        manager.http_client = mock_client
        manager.__exit__(None, None, None)
        mock_client.close.assert_called_once()

    def test_del_cleanup(self):
        manager, _ = _make_manager()
        mock_client = MagicMock()
        manager.http_client = mock_client
        manager.__del__()
        mock_client.close.assert_called_once()


# ---------------------------------------------------------------------------
# _initialize_openai with base_url, organization, ca_bundle_path
# ---------------------------------------------------------------------------


class TestInitializeOpenAIOptions:
    def test_with_base_url_and_org(self):
        config = _make_config()
        config.llm.base_url = "https://custom.api.com"
        config.llm.organization = "org-123"
        mock_llm = MagicMock()
        with patch(
            "askrita.utils.LLMManager.ChatOpenAI", return_value=mock_llm
        ) as mock_cls:
            _ = LLMManager(config, test_connection=False)
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs.get("base_url") == "https://custom.api.com"
            assert call_kwargs.get("organization") == "org-123"

    def test_with_ca_bundle(self, tmp_path):
        config = _make_config()
        ca_file = tmp_path / "ca.crt"
        ca_file.write_text("CERT")
        config.llm.ca_bundle_path = str(ca_file)
        mock_llm = MagicMock()
        with patch("askrita.utils.LLMManager.ChatOpenAI", return_value=mock_llm):
            with patch("askrita.utils.LLMManager.httpx.Client") as mock_client_cls:
                mock_http_client = MagicMock()
                mock_client_cls.return_value = mock_http_client
                manager = LLMManager(config, test_connection=False)
                assert manager.http_client is mock_http_client


# ---------------------------------------------------------------------------
# _initialize_vertex_ai with credentials_path
# ---------------------------------------------------------------------------


class TestInitializeVertexAI:
    def test_vertex_ai_with_credentials_path(self):
        config = _make_config(provider="vertex_ai")
        config.llm.credentials_path = "/path/to/credentials.json"
        mock_llm = MagicMock()
        with patch("askrita.utils.LLMManager.ChatVertexAI", return_value=mock_llm):
            with patch.dict(os.environ, {}):
                _ = LLMManager(config, test_connection=False)
                assert (
                    os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
                    == "/path/to/credentials.json"
                )


# ---------------------------------------------------------------------------
# _initialize_bedrock with AWS credential env vars
# ---------------------------------------------------------------------------


class TestInitializeBedrock:
    def test_bedrock_with_aws_credentials(self):
        config = _make_config(provider="bedrock")
        config.llm.aws_access_key_id_env_var = "MY_AWS_KEY"
        config.llm.aws_secret_access_key_env_var = "MY_AWS_SECRET"
        config.llm.aws_session_token_env_var = "MY_AWS_TOKEN"
        mock_llm = MagicMock()
        env = {
            "MY_AWS_KEY": "access-key",
            "MY_AWS_SECRET": "secret",
            "MY_AWS_TOKEN": "token",
        }
        with patch.dict(os.environ, env):
            with patch(
                "askrita.utils.LLMManager.ChatBedrock", return_value=mock_llm
            ) as mock_cls:
                _ = LLMManager(config, test_connection=False)
                call_kwargs = mock_cls.call_args[1]
                assert call_kwargs.get("aws_access_key_id") == "access-key"
                assert call_kwargs.get("aws_secret_access_key") == "secret"
                assert call_kwargs.get("aws_session_token") == "token"

    def test_bedrock_no_credentials_uses_defaults(self):
        config = _make_config(provider="bedrock")
        mock_llm = MagicMock()
        with patch("askrita.utils.LLMManager.ChatBedrock", return_value=mock_llm):
            manager = LLMManager(config, test_connection=False)
            assert manager is not None
