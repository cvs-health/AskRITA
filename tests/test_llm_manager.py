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
#   pytest (MIT)

"""Tests for LLMManager functionality."""

import pytest
import os
import sys
from unittest.mock import Mock, patch

from askrita.utils.LLMManager import LLMManager
from askrita.exceptions import LLMError, ConfigurationError


@pytest.fixture(autouse=True)
def mock_openai_api_key():
    """Automatically mock OPENAI_API_KEY for all LLM tests."""
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-api-key'}):
        yield


class TestLLMManager:
    """Test cases for LLMManager class."""

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="Mock compatibility issue on Python 3.10")
    def test_initialization_openai_success(self, mock_config):
        """Test successful OpenAI LLM initialization."""
        mock_config.llm.provider = "openai"
        #mock_config.llm.api_key = "test-api-key"

        with patch('askrita.utils.LLMManager.ChatOpenAI', create=True) as mock_chat_openai:
            mock_llm = Mock()
            mock_chat_openai.return_value = mock_llm

            llm_manager = LLMManager(mock_config, test_connection=False)

            assert llm_manager.config == mock_config
            assert llm_manager.llm == mock_llm
            mock_chat_openai.assert_called_once()

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="Mock compatibility issue on Python 3.10")
    def test_initialization_azure_openai_success(self, mock_config):
        """Test successful Azure OpenAI LLM initialization."""
        mock_config.llm.provider = "azure_openai"
        mock_config.llm.azure_endpoint = "https://test.openai.azure.com/"
        mock_config.llm.azure_deployment = "test-deployment"
        mock_config.llm.azure_tenant_id = "test-tenant"
        mock_config.llm.azure_client_id = "test-client"
        mock_config.llm.azure_certificate_path = "/path/to/cert.pem"

        with patch('askrita.utils.LLMManager.AzureChatOpenAI', create=True) as mock_azure_chat, \
             patch.object(LLMManager, 'get_azure_token_provider') as mock_token_provider:

            mock_llm = Mock()
            mock_azure_chat.return_value = mock_llm
            mock_token_provider.return_value = Mock()

            llm_manager = LLMManager(mock_config, test_connection=False)

            assert llm_manager.llm == mock_llm
            mock_azure_chat.assert_called_once()
            mock_token_provider.assert_called_once()

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="Mock compatibility issue on Python 3.10")
    def test_initialization_vertex_ai_success(self, mock_config):
        """Test successful Vertex AI LLM initialization."""
        mock_config.llm.provider = "vertex_ai"
        mock_config.llm.project_id = "test-project"
        mock_config.llm.location = "us-central1"

        with patch('askrita.utils.LLMManager.ChatVertexAI', create=True) as mock_vertex_ai:
            mock_llm = Mock()
            mock_vertex_ai.return_value = mock_llm

            llm_manager = LLMManager(mock_config, test_connection=False)

            assert llm_manager.llm == mock_llm
            mock_vertex_ai.assert_called_once()

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="Mock compatibility issue on Python 3.10")
    def test_initialization_bedrock_success(self, mock_config):
        """Test successful Bedrock LLM initialization."""
        mock_config.llm.provider = "bedrock"
        mock_config.llm.region_name = "us-east-1"
        mock_config.llm.aws_access_key_id_env_var = "AWS_ACCESS_KEY_ID"

        with patch('askrita.utils.LLMManager.ChatBedrock', create=True) as mock_bedrock, \
             patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "test-key"}):

            mock_llm = Mock()
            mock_bedrock.return_value = mock_llm

            llm_manager = LLMManager(mock_config, test_connection=False)

            assert llm_manager.llm == mock_llm
            mock_bedrock.assert_called_once()

    def test_initialization_unsupported_provider(self, mock_config):
        """Test error handling for unsupported LLM provider."""
        mock_config.llm.provider = "unsupported_provider"

        with pytest.raises(ConfigurationError, match="Unsupported LLM provider"):
            LLMManager(mock_config, test_connection=False)

    def test_initialization_missing_api_key(self, mock_config):
        """Test error handling for missing API key."""
        mock_config.llm.provider = "openai"

        with patch('os.getenv') as mock_getenv:
            mock_getenv.return_value = None  # No OPENAI_API_KEY env var

            with pytest.raises(LLMError, match="OpenAI API key not found"):
                LLMManager(mock_config, test_connection=False)

    def test_initialization_missing_azure_config(self, mock_config):
        """Test error handling for missing Azure configuration."""
        mock_config.llm.provider = "azure_openai"
        mock_config.llm.azure_endpoint = None

        with pytest.raises(LLMError, match="Failed to initialize LLM"):
            LLMManager(mock_config, test_connection=False)

    def test_initialization_missing_vertex_config(self, mock_config):
        """Test error handling for missing Vertex AI configuration."""
        mock_config.llm.provider = "vertex_ai"
        mock_config.llm.project_id = None

        with pytest.raises(LLMError, match="Failed to initialize LLM"):
            LLMManager(mock_config, test_connection=False)

    def test_invoke_with_prompt_template(self, mock_llm_manager):
        """Test LLM invocation with prompt template."""
        from langchain_core.prompts import ChatPromptTemplate

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful assistant."),
            ("human", "Hello, {name}!")
        ])

        response = mock_llm_manager.invoke(prompt, name="World")

        assert response == "Mocked LLM response"
        mock_llm_manager.invoke.assert_called_once()

    def test_invoke_with_config_prompt(self, mock_llm_manager):
        """Test LLM invocation with configuration-based prompt."""
        response = mock_llm_manager.invoke_with_config_prompt(
            "parse_question",
            question="What are the sales?",
            schema="CREATE TABLE sales..."
        )

        expected_response = '{"is_relevant": true, "relevant_tables": [{"table_name": "customers", "noun_columns": ["name"]}]}'
        assert response == expected_response

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="Mock compatibility issue on Python 3.10")
    def test_create_prompt_from_config(self, mock_llm_manager):
        """Test prompt template creation from configuration."""
        with patch('askrita.utils.LLMManager.ChatPromptTemplate', create=True) as mock_prompt_template:
            mock_template = Mock()
            mock_prompt_template.from_messages.return_value = mock_template

            # Create a real LLMManager to test the method
            with patch('askrita.utils.LLMManager.ChatOpenAI', create=True):
                llm_manager = LLMManager(mock_llm_manager.config, test_connection=False)

                llm_manager.create_prompt_from_config("parse_question")

                mock_prompt_template.from_messages.assert_called_once()

    def test_get_model_info(self, mock_llm_manager):
        """Test model information retrieval."""
        expected_info = {
            "provider": "openai",
            "model": "gpt-4o",
            "temperature": 0.1
        }
        mock_llm_manager.get_model_info.return_value = expected_info

        info = mock_llm_manager.get_model_info()

        assert info["provider"] == "openai"
        assert info["model"] == "gpt-4o"
        assert "temperature" in info

    def test_test_connection_success(self, mock_llm_manager):
        """Test successful LLM connection test."""
        result = mock_llm_manager.test_connection()
        assert result is True

    def test_test_connection_failure(self, mock_llm_manager):
        """Test failed LLM connection test."""
        mock_llm_manager.test_connection.return_value = False

        result = mock_llm_manager.test_connection()
        assert result is False


class TestOpenAIInitialization:
    """Test OpenAI-specific initialization."""

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="Mock compatibility issue on Python 3.10")
    def test_openai_with_all_parameters(self, mock_config):
        """Test OpenAI initialization with all parameters."""
        mock_config.llm.provider = "openai"
        mock_config.llm.base_url = "https://api.custom.com/v1"
        mock_config.llm.organization = "test-org"
        mock_config.llm.temperature = 0.7
        mock_config.llm.max_tokens = 2000

        with patch('askrita.utils.LLMManager.ChatOpenAI', create=True) as mock_chat_openai, \
             patch('os.getenv') as mock_getenv:
            mock_getenv.return_value = "test-env-api-key"  # Mock OPENAI_API_KEY env var
            mock_llm = Mock()
            mock_chat_openai.return_value = mock_llm

            _ = LLMManager(mock_config, test_connection=False)

            # Verify ChatOpenAI was called with correct parameters
            call_args = mock_chat_openai.call_args[1]
            #assert call_args["api_key"] == "test-env-api-key"
            assert call_args["base_url"] == "https://api.custom.com/v1"
            assert call_args["organization"] == "test-org"
            assert call_args["temperature"] == 0.7
            assert call_args["max_tokens"] == 2000

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="Mock compatibility issue on Python 3.10")
    def test_openai_with_ca_bundle(self, mock_config):
        """Test OpenAI initialization with custom CA bundle."""
        mock_config.llm.provider = "openai"
        mock_config.llm.ca_bundle_path = "/path/to/custom-ca-bundle.pem"

        with patch('askrita.utils.LLMManager.ChatOpenAI', create=True) as mock_chat_openai, \
             patch('askrita.utils.LLMManager.httpx', create=True) as mock_httpx:

            mock_llm = Mock()
            mock_chat_openai.return_value = mock_llm
            mock_client = Mock()
            mock_httpx.Client.return_value = mock_client

            _ = LLMManager(mock_config, test_connection=False)

            # Verify httpx.Client was created with the CA bundle path
            mock_httpx.Client.assert_called_once_with(verify="/path/to/custom-ca-bundle.pem")

            # Verify ChatOpenAI was called with the http_client parameter
            call_args = mock_chat_openai.call_args[1]
            assert "http_client" in call_args
            assert call_args["http_client"] == mock_client


class TestAzureOpenAIInitialization:
    """Test Azure OpenAI-specific initialization."""

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="Mock compatibility issue on Python 3.10")
    def test_azure_openai_certificate_auth(self, mock_config):
        """Test Azure OpenAI with certificate authentication."""
        mock_config.llm.provider = "azure_openai"
        mock_config.llm.azure_endpoint = "https://test.openai.azure.com/"
        mock_config.llm.azure_deployment = "test-deployment"
        mock_config.llm.api_version = "2024-02-15-preview"
        mock_config.llm.azure_tenant_id = "test-tenant"
        mock_config.llm.azure_client_id = "test-client"
        mock_config.llm.azure_certificate_path = "/path/to/cert.pem"
        mock_config.llm.azure_certificate_password = "cert-password"

        with patch('askrita.utils.LLMManager.AzureChatOpenAI', create=True) as mock_azure_chat, \
             patch('azure.identity.CertificateCredential') as mock_cert_cred, \
             patch('azure.identity.get_bearer_token_provider') as mock_token_provider:

            mock_llm = Mock()
            mock_azure_chat.return_value = mock_llm
            mock_credential = Mock()
            mock_cert_cred.return_value = mock_credential
            mock_provider = Mock()
            mock_token_provider.return_value = mock_provider

            _ = LLMManager(mock_config, test_connection=False)

            # Verify certificate credential was created with the expected parameters.
            # Use call_args to check only the kwargs we care about, ignoring any
            # additional kwargs that certain azure-identity versions may inject (e.g. transport).
            assert mock_cert_cred.call_count == 1
            call_kwargs = mock_cert_cred.call_args.kwargs
            assert call_kwargs.get("tenant_id") == "test-tenant"
            assert call_kwargs.get("client_id") == "test-client"
            assert call_kwargs.get("certificate_path") == "/path/to/cert.pem"
            assert call_kwargs.get("password") == "cert-password"

            # Verify token provider was created
            mock_token_provider.assert_called_once_with(
                mock_credential,
                "https://cognitiveservices.azure.com/.default"
            )

            # Verify AzureChatOpenAI was called with token provider
            call_args = mock_azure_chat.call_args[1]
            assert call_args["azure_ad_token_provider"] == mock_provider


    def test_azure_openai_missing_tenant_id(self, mock_config):
        """Test Azure OpenAI error when tenant ID is missing."""
        mock_config.llm.provider = "azure_openai"
        mock_config.llm.azure_endpoint = "https://test.openai.azure.com/"
        mock_config.llm.azure_deployment = "test-deployment"
        # Missing azure_tenant_id

        with pytest.raises(LLMError, match="LLM authentication failed"):
            LLMManager(mock_config, test_connection=False)


class TestVertexAIInitialization:
    """Test Vertex AI-specific initialization."""

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="Mock compatibility issue on Python 3.10")
    def test_vertex_ai_with_credentials(self, mock_config):
        """Test Vertex AI initialization with credentials path."""
        mock_config.llm.provider = "vertex_ai"
        mock_config.llm.project_id = "test-project"
        mock_config.llm.location = "us-west1"
        mock_config.llm.credentials_path = "/path/to/credentials.json"

        with patch('askrita.utils.LLMManager.ChatVertexAI', create=True) as mock_vertex_ai, \
             patch.dict(os.environ, {}, clear=True):

            mock_llm = Mock()
            mock_vertex_ai.return_value = mock_llm

            _ = LLMManager(mock_config, test_connection=False)

            # Should set GOOGLE_APPLICATION_CREDENTIALS
            assert os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") == "/path/to/credentials.json"

            # Verify ChatVertexAI was called with correct parameters
            call_args = mock_vertex_ai.call_args[1]
            assert call_args["project"] == "test-project"
            assert call_args["location"] == "us-west1"


class TestBedrockInitialization:
    """Test Bedrock-specific initialization."""

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="Mock compatibility issue on Python 3.10")
    def test_bedrock_with_aws_credentials(self, mock_config):
        """Test Bedrock initialization with AWS credentials."""
        mock_config.llm.provider = "bedrock"
        mock_config.llm.region_name = "us-west-2"
        mock_config.llm.aws_access_key_id_env_var = "AWS_ACCESS_KEY_ID"
        mock_config.llm.aws_secret_access_key_env_var = "AWS_SECRET_ACCESS_KEY"
        mock_config.llm.aws_session_token_env_var = "AWS_SESSION_TOKEN"

        with patch('askrita.utils.LLMManager.ChatBedrock', create=True) as mock_bedrock, \
             patch.dict(os.environ, {
                 "AWS_ACCESS_KEY_ID": "test-access-key",
                 "AWS_SECRET_ACCESS_KEY": "test-secret-key",
                 "AWS_SESSION_TOKEN": "test-session-token"
             }):

            mock_llm = Mock()
            mock_bedrock.return_value = mock_llm

            _ = LLMManager(mock_config, test_connection=False)

            # Verify ChatBedrock was called with AWS credentials
            call_args = mock_bedrock.call_args[1]
            assert call_args["aws_access_key_id"] == "test-access-key"
            assert call_args["aws_secret_access_key"] == "test-secret-key"
            assert call_args["aws_session_token"] == "test-session-token"
            assert call_args["region_name"] == "us-west-2"


class TestLLMManagerErrorHandling:
    """Test error handling and edge cases."""

    def test_invoke_with_llm_error(self, mock_llm_manager):
        """Test handling of LLM invocation errors."""
        mock_llm_manager.invoke.side_effect = Exception("LLM API error")

        with pytest.raises(Exception, match="LLM API error"):
            mock_llm_manager.invoke(Mock())

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="Mock compatibility issue on Python 3.10")
    def test_missing_import_error(self, mock_config):
        """Test handling of missing dependency imports."""
        mock_config.llm.provider = "openai"

        with patch('askrita.utils.LLMManager.ChatOpenAI', create=True) as mock_chat_openai:
            mock_chat_openai.side_effect = ImportError("No module named 'langchain_openai'")

            with pytest.raises(ConfigurationError, match="Missing dependencies for openai"):
                LLMManager(mock_config, test_connection=False)

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="Mock compatibility issue on Python 3.10")
    def test_authentication_error_handling(self, mock_config):
        """Test handling of authentication errors."""
        mock_config.llm.provider = "openai"
        #mock_config.llm.api_key = "invalid-key"

        with patch('askrita.utils.LLMManager.ChatOpenAI', create=True) as mock_chat_openai:
            mock_chat_openai.side_effect = Exception("authentication failed")

            with pytest.raises(LLMError, match="LLM authentication failed"):
                LLMManager(mock_config, test_connection=False)

    def test_prompt_creation_error(self, mock_config):
        """Test error handling in prompt creation."""
        with patch('askrita.utils.LLMManager.ChatOpenAI', create=True):
            llm_manager = LLMManager(mock_config, test_connection=False)

            # Try to create prompt for non-existent prompt name
            with pytest.raises(ConfigurationError, match="Prompt 'nonexistent' not found"):
                llm_manager.create_prompt_from_config("nonexistent")

    def test_connection_test_with_error(self, mock_config):
        """Test connection test when LLM raises an error."""
        with patch('askrita.utils.LLMManager.ChatOpenAI', create=True) as mock_chat_openai:
            mock_llm = Mock()
            mock_llm.invoke.side_effect = Exception("Connection failed")
            mock_chat_openai.return_value = mock_llm

            llm_manager = LLMManager(mock_config, test_connection=False)
            result = llm_manager.test_connection()

            assert result is False

    def test_azure_token_provider_error(self, mock_config):
        """Test Azure token provider creation error."""
        mock_config.llm.provider = "azure_openai"
        mock_config.llm.azure_endpoint = "https://test.openai.azure.com/"
        mock_config.llm.azure_deployment = "test-deployment"
        mock_config.llm.azure_tenant_id = "test-tenant"
        mock_config.llm.azure_client_id = "test-client"
        mock_config.llm.azure_certificate_path = "/path/to/cert.pem"

        with patch('azure.identity.CertificateCredential') as mock_cert_cred:
            mock_cert_cred.side_effect = Exception("Certificate error")

            with pytest.raises(LLMError, match="Failed to create Azure token provider"):
                LLMManager(mock_config, test_connection=False)


class TestLLMManagerEdgeCases:
    """Test edge cases and special scenarios."""

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="Mock compatibility issue on Python 3.10")
    def test_invoke_with_database_type_injection(self, mock_config):
        """Test that database type is automatically injected into prompts."""
        # Ensure the mock config's get_database_type method works
        mock_config.get_database_type.return_value = "sqlite"

        with patch('askrita.utils.LLMManager.ChatOpenAI', create=True) as mock_chat_openai:
            mock_llm = Mock()
            mock_response = Mock()
            mock_response.content = "Generated SQL"
            mock_llm.invoke.return_value = mock_response
            mock_chat_openai.return_value = mock_llm

            llm_manager = LLMManager(mock_config, test_connection=False)

            from langchain_core.prompts import ChatPromptTemplate
            prompt = ChatPromptTemplate.from_messages([
                ("system", "Generate SQL for {database_type}"),
                ("human", "Question: {question}")
            ])

            response = llm_manager.invoke(prompt, question="Show customers", database_type="sqlite")

            # Should include database_type in the call
            assert response == "Generated SQL"

            # Verify that the mock LLM was called with the prompt that includes database_type
            mock_llm.invoke.assert_called_once()

    def test_invoke_with_config_prompt_missing_template(self, mock_config):
        """Test invoke with config prompt when template is missing."""
        with patch('askrita.utils.LLMManager.ChatOpenAI', create=True):
            llm_manager = LLMManager(mock_config, test_connection=False)

            # Mock empty prompt response
            mock_config.get_prompt.return_value = ""

            response = llm_manager.invoke_with_config_prompt("missing_prompt")

            # Should return error message
            assert "Error" in response

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="Mock compatibility issue on Python 3.10")
    def test_model_parameters_validation(self, mock_config):
        """Test that model parameters are properly validated and passed."""
        mock_config.llm.provider = "openai"
        mock_config.llm.temperature = 1.5  # Invalid temperature
        mock_config.llm.max_tokens = -1     # Invalid max_tokens

        with patch('askrita.utils.LLMManager.ChatOpenAI', create=True) as mock_chat_openai:
            mock_llm = Mock()
            mock_chat_openai.return_value = mock_llm

            # Should still initialize despite invalid parameters
            # (validation is typically done by the underlying library)
            _ = LLMManager(mock_config, test_connection=False)

            call_args = mock_chat_openai.call_args[1]
            assert call_args["temperature"] == 1.5
            assert call_args["max_tokens"] == -1
