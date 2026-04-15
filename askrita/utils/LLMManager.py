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
#   azure-core (MIT)
#   azure-identity (MIT)
#   httpx (BSD-3-Clause)
#   langchain-aws (MIT)
#   langchain-core (MIT)
#   langchain-google-vertexai (MIT)
#   langchain-openai (MIT)
#   pydantic (MIT)
#   requests (Apache-2.0)

"""LLM provider management with multi-provider support and structured output."""

import logging
import os
from typing import Any, Dict, NoReturn, Optional, Type

import httpx
from langchain_aws import ChatBedrock
from langchain_core.globals import set_debug
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_vertexai import ChatVertexAI
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from pydantic import BaseModel

from ..config_manager import get_config
from ..exceptions import ConfigurationError, LLMError
from .token_utils import estimate_messages_token_count, get_safe_context_limit

# Azure Identity imports are now conditional - moved to get_azure_token_provider method

logger = logging.getLogger(__name__)


class LLMManager:
    """Manages LLM provider initialization, prompt execution, and structured output.

    Supports OpenAI, Azure OpenAI, Google Vertex AI, and AWS Bedrock with
    automatic provider detection, token management, and connection testing.
    """

    def __init__(self, config_manager=None, test_connection=True):
        """
        Initialize LLMManager with configuration.

        Args:
            config_manager: Optional ConfigManager instance. If None, uses global config.
            test_connection: Whether to test LLM connection after initialization (default: True)
        """
        self.config = config_manager or get_config()
        # Set langchain debug mode from config
        set_debug(self.config.framework.debug)
        self.http_client = None  # Track HTTP client for proper cleanup
        self.llm = self._initialize_llm()

        # Determine optimal structured output method based on provider (NO MORE FALLBACKS!)
        self.structured_output_method = self._detect_optimal_structured_output_method(
            self.config.llm.provider
        )
        logger.info(
            f"Using structured output method: {self.structured_output_method} for {self.config.llm.provider}"
        )

        # Validate LLM connection immediately after initialization (unless disabled for testing)
        if test_connection:
            logger.info(
                f"🔍 Testing {self.config.llm.provider} LLM connection during initialization..."
            )
            if not self.test_connection():
                logger.error(
                    f"❌ {self.config.llm.provider} LLM initialization failed - connection test failed"
                )
                raise LLMError(
                    "LLM connection test failed after initialization. "
                    "Please verify your LLM configuration, credentials, and network connectivity."
                )
            else:
                logger.info(
                    f"✅ {self.config.llm.provider} LLM initialization completed successfully"
                )
        else:
            logger.info(
                f"⚠️ {self.config.llm.provider} LLM connection test skipped (test_connection=False)"
            )

    def _detect_optimal_structured_output_method(self, provider: str) -> str:
        """Detect the optimal structured output method for the LLM provider."""
        # OpenAI models work better with function_calling
        if provider in ["openai", "azure_openai"]:
            return "function_calling"
        # Other providers default to json_schema
        return "json_schema"

    @staticmethod
    def _llm_provider_install_hint(provider: str) -> str:
        """Return the pip install hint for a given provider."""
        _hints = {
            "openai": "pip install langchain-openai",
            "azure_openai": "pip install langchain-openai",
            "vertex_ai": "pip install langchain-google-vertexai",
            "bedrock": "pip install langchain-aws",
        }
        return _hints.get(provider, "pip install --upgrade askrita")

    @staticmethod
    def _is_missing_langchain_dep(error_msg: str) -> bool:
        """Return True if the error indicates a missing langchain dependency."""
        return ("import" in error_msg and "langchain" in error_msg) or (
            "no module named" in error_msg and "langchain" in error_msg
        )

    def _raise_init_error(self, exc: Exception) -> NoReturn:
        """Translate a raw LLM init exception into a typed ConfigurationError or LLMError."""
        error_msg = str(exc).lower()
        llm_config = self.config.llm

        if "api key" in error_msg or "authentication" in error_msg:
            raise LLMError(
                f"LLM authentication failed: {exc}\n"
                f"Please check your {llm_config.provider} API key in the configuration."
            )
        if self._is_missing_langchain_dep(error_msg):
            provider = llm_config.provider
            extra = self._llm_provider_install_hint(provider)
            raise ConfigurationError(
                f"Missing dependencies for {provider}: {exc}\n"
                f"Please install required packages: {extra}"
            )
        if "unsupported" in error_msg or "unknown provider" in error_msg:
            raise ConfigurationError(
                f"Unsupported LLM provider '{llm_config.provider}': {exc}\n"
                "Supported providers: openai, azure_openai, vertex_ai, bedrock"
            )
        raise LLMError(f"Failed to initialize LLM: {str(exc)}")

    def _initialize_llm(self) -> BaseChatModel:
        """Initialize the LLM with configuration settings for any supported provider."""
        try:
            llm_config = self.config.llm
            provider = llm_config.provider.lower()

            logger.info(f"Initializing {provider} LLM with model: {llm_config.model}")

            if provider == "openai":
                return self._initialize_openai()
            if provider == "azure_openai":
                return self._initialize_azure_openai()
            if provider == "vertex_ai":
                return self._initialize_vertex_ai()
            if provider == "bedrock":
                return self._initialize_bedrock()
            raise ConfigurationError(f"Unsupported LLM provider: {llm_config.provider}")

        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            self._raise_init_error(e)

    @staticmethod
    def _build_azure_credential_with_ca_bundle(
        tenant_id: str,
        client_id: str,
        certificate_path: str,
        certificate_password: Optional[str],
        ca_bundle_path: str,
    ):
        """Build a CertificateCredential configured with a custom CA bundle transport."""
        import requests
        from azure.core.pipeline.transport import RequestsTransport
        from azure.identity import CertificateCredential

        os.environ["AZURE_AUTHORITY_HOST"] = "https://login.microsoftonline.com/"
        session = requests.Session()
        session.verify = ca_bundle_path
        transport = RequestsTransport(session=session)
        credential = CertificateCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            certificate_path=certificate_path,
            password=certificate_password,
            transport=transport,
        )
        logger.info(
            "✅ Configured Azure CertificateCredential with custom transport and CA bundle"
        )
        return credential

    @staticmethod
    def _build_azure_credential_default(
        tenant_id: str,
        client_id: str,
        certificate_path: str,
        certificate_password: Optional[str],
    ):
        """Build a CertificateCredential using default SSL verification."""
        from azure.identity import CertificateCredential

        logger.warning(
            "⚠️ No CA bundle found for Azure Identity - SSL verification may fail"
        )
        return CertificateCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            certificate_path=certificate_path,
            password=certificate_password,
        )

    def get_azure_token_provider(
        self,
        tenant_id: str,
        client_id: str,
        certificate_path: str,
        certificate_password: Optional[str] = None,
    ):
        """Get Azure token provider for certificate-based authentication.

        Imports Azure identity libraries only when needed for Azure authentication.
        """
        try:
            logger.info("🔐 Importing Azure identity components for token provider")
            from azure.identity import get_bearer_token_provider

            ca_bundle_path = os.environ.get("SSL_CERT_FILE")
            if ca_bundle_path and os.path.exists(ca_bundle_path):
                credential = self._build_azure_credential_with_ca_bundle(
                    tenant_id,
                    client_id,
                    certificate_path,
                    certificate_password,
                    ca_bundle_path,
                )
            else:
                credential = self._build_azure_credential_default(
                    tenant_id, client_id, certificate_path, certificate_password
                )

            return get_bearer_token_provider(
                credential, "https://cognitiveservices.azure.com/.default"
            )
        except Exception as e:
            logger.error(f"❌ Azure token provider error: {e}")
            raise LLMError(f"Failed to create Azure token provider: {e}")

    def _initialize_openai(self) -> BaseChatModel:
        """Initialize OpenAI LLM."""

        llm_config = self.config.llm

        # Get API key from environment variable
        import os

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise LLMError(
                "OpenAI API key not found. "
                "Please set the OPENAI_API_KEY environment variable."
            )

        # Configure OpenAI parameters
        params = {
            "model": llm_config.model,
            "temperature": llm_config.temperature,
            "max_tokens": llm_config.max_tokens,
            "top_p": llm_config.top_p,
            "frequency_penalty": llm_config.frequency_penalty,
            "presence_penalty": llm_config.presence_penalty,
            "api_key": api_key,
            "timeout": llm_config.timeout,
        }

        # Add optional OpenAI parameters
        if llm_config.base_url:
            params["base_url"] = llm_config.base_url
        if llm_config.organization:
            params["organization"] = llm_config.organization

        # Configure custom CA bundle if provided
        if llm_config.ca_bundle_path:
            try:
                # Create httpx.Client with custom CA bundle for certificate verification
                self.http_client = httpx.Client(verify=llm_config.ca_bundle_path)
                params["http_client"] = self.http_client
                logger.info(f"Using custom CA bundle from: {llm_config.ca_bundle_path}")
            except Exception as e:
                raise LLMError(f"Failed to configure custom CA bundle: {e}")

        return ChatOpenAI(**params)  # type: ignore[arg-type]

    def _initialize_azure_openai(self) -> BaseChatModel:
        """Initialize Azure OpenAI LLM with certificate-based authentication."""

        llm_config = self.config.llm

        # Validate required Azure certificate authentication fields
        if not llm_config.azure_endpoint:
            raise ConfigurationError("azure_endpoint is required for Azure OpenAI")
        if not llm_config.azure_deployment:
            raise ConfigurationError("azure_deployment is required for Azure OpenAI")
        if not hasattr(llm_config, "azure_tenant_id") or not llm_config.azure_tenant_id:
            raise ConfigurationError(
                "azure_tenant_id is required for Azure OpenAI certificate authentication"
            )
        if not hasattr(llm_config, "azure_client_id") or not llm_config.azure_client_id:
            raise ConfigurationError(
                "azure_client_id is required for Azure OpenAI certificate authentication"
            )
        if (
            not hasattr(llm_config, "azure_certificate_path")
            or not llm_config.azure_certificate_path
        ):
            raise ConfigurationError(
                "azure_certificate_path is required for Azure OpenAI certificate authentication"
            )

        # Get certificate password if provided
        certificate_password = getattr(llm_config, "azure_certificate_password", None)

        # Get Azure token provider using certificate authentication
        token_provider = self.get_azure_token_provider(
            tenant_id=llm_config.azure_tenant_id,
            client_id=llm_config.azure_client_id,
            certificate_path=llm_config.azure_certificate_path,
            certificate_password=certificate_password,
        )

        # Configure Azure OpenAI parameters with certificate authentication
        params = {
            "azure_deployment": llm_config.azure_deployment,
            "azure_endpoint": llm_config.azure_endpoint,
            "api_version": llm_config.api_version,
            "azure_ad_token_provider": token_provider,
            "temperature": llm_config.temperature,
            "max_tokens": llm_config.max_tokens,
            "top_p": llm_config.top_p,
            "frequency_penalty": llm_config.frequency_penalty,
            "presence_penalty": llm_config.presence_penalty,
            "timeout": llm_config.timeout,
            "verbose": True,
        }

        return AzureChatOpenAI(**params)  # type: ignore[arg-type]

    def _initialize_vertex_ai(self) -> BaseChatModel:
        """Initialize GCP Vertex AI LLM."""

        llm_config = self.config.llm

        if not llm_config.project_id:
            raise ConfigurationError("project_id is required for Vertex AI")

        # Configure Vertex AI parameters
        params = {
            "model_name": llm_config.model,
            "project": llm_config.project_id,
            "location": llm_config.location,
            "temperature": llm_config.temperature,
            "max_output_tokens": llm_config.max_tokens,
            "top_p": llm_config.top_p,
        }

        # Add credentials if specified
        if llm_config.credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = llm_config.credentials_path

        return ChatVertexAI(**params)  # type: ignore[arg-type]

    def _initialize_bedrock(self) -> BaseChatModel:
        """Initialize AWS Bedrock LLM."""

        llm_config = self.config.llm

        # Configure AWS credentials
        aws_credentials = {}
        if llm_config.aws_access_key_id_env_var:
            aws_access_key = os.getenv(llm_config.aws_access_key_id_env_var)
            if aws_access_key:
                aws_credentials["aws_access_key_id"] = aws_access_key

        if llm_config.aws_secret_access_key_env_var:
            aws_secret = os.getenv(llm_config.aws_secret_access_key_env_var)
            if aws_secret:
                aws_credentials["aws_secret_access_key"] = aws_secret

        if llm_config.aws_session_token_env_var:
            aws_token = os.getenv(llm_config.aws_session_token_env_var)
            if aws_token:
                aws_credentials["aws_session_token"] = aws_token

        # Configure Bedrock parameters
        params = {
            "model_id": llm_config.model,
            "region_name": llm_config.region_name,
            "model_kwargs": {
                "temperature": llm_config.temperature,
                "max_tokens": llm_config.max_tokens,
                "top_p": llm_config.top_p,
            },
            **aws_credentials,
        }

        return ChatBedrock(**params)  # type: ignore[arg-type]

    def invoke(self, prompt: ChatPromptTemplate, **kwargs) -> str:
        """
        Invoke the LLM with a prompt template and variables.

        Args:
            prompt: ChatPromptTemplate to use
            **kwargs: Variables to format into the prompt

        Returns:
            LLM response as string
        """
        try:
            logger.debug(
                f"Invoking LLM with prompt template and {len(kwargs)} variables"
            )

            # Format the prompt with provided variables
            messages = prompt.format_messages(**kwargs)

            # Check token count before sending to LLM
            self._check_token_limit(messages)

            # Add database type to kwargs if not provided (for prompts that need it)
            if "database_type" not in kwargs:
                kwargs["database_type"] = self.config.get_database_type()

            # Invoke the LLM
            response = self.llm.invoke(messages)

            logger.debug(
                f"LLM response received, length: {len(response.content)} characters"
            )
            return response.content

        except Exception as e:
            logger.error(f"LLM invocation failed: {e}")
            return f"Error: {str(e)}"

    def invoke_with_structured_output(
        self,
        prompt_name: str,
        response_model: Type[BaseModel],
        method: str = "json_schema",
        **kwargs,
    ) -> BaseModel:
        """
        Invoke the LLM with structured output using LangChain's with_structured_output method.

        Args:
            prompt_name: Name of the prompt in configuration
            response_model: Pydantic model class for structured output
            method: Structured output method - "json_schema" (default) or "function_calling" (better for nested models)
            **kwargs: Variables to format into the prompt

        Returns:
            Instance of response_model with LLM response

        Raises:
            LLMError: If LLM invocation fails or response parsing fails
        """
        try:
            # Get prompt configuration using ConfigManager's get_prompt method
            system_template = self.config.get_prompt(prompt_name, "system")
            human_template = self.config.get_prompt(prompt_name, "human")

            if not system_template:
                raise LLMError(f"Prompt '{prompt_name}' not found in configuration")

            # Create prompt template (without manual JSON schema instructions)
            messages = [("system", system_template)]
            if human_template:
                messages.append(("human", human_template))

            prompt = ChatPromptTemplate.from_messages(messages)

            # Add database type to kwargs if not provided
            if "database_type" not in kwargs:
                kwargs["database_type"] = self.config.get_database_type()

            # Add current datetime to kwargs if not provided
            if "current_datetime" not in kwargs:
                from datetime import datetime

                kwargs["current_datetime"] = datetime.now().strftime(
                    "%m-%d-%Y %I:%M %p"
                )

            # Format messages
            messages = prompt.format_messages(**kwargs)
            self._check_token_limit(messages)

            # Use specified method or fall back to pre-configured optimal method
            output_method = method if method else self.structured_output_method
            structured_llm = self.llm.with_structured_output(
                response_model, method=output_method
            )

            logger.debug(
                f"Invoking LLM with structured output (method={output_method}) for prompt '{prompt_name}'"
            )
            structured_response = structured_llm.invoke(messages)
            logger.debug(
                f"Successfully received structured response for '{prompt_name}'"
            )

            return structured_response

        except Exception as e:
            logger.error(
                f"Structured output invocation failed for '{prompt_name}': {e}"
            )
            raise LLMError(f"Structured output failed: {str(e)}")

    def invoke_with_structured_output_direct(
        self,
        system_prompt: str,
        human_prompt: str,
        response_model: Type[BaseModel],
        **kwargs,
    ) -> BaseModel:
        """
        Invoke the LLM with structured output using direct prompts (not from config).

        Args:
            system_prompt: System prompt string
            human_prompt: Human prompt string
            response_model: Pydantic model class for structured output
            **kwargs: Variables to format into the prompts

        Returns:
            Instance of response_model with LLM response

        Raises:
            LLMError: If LLM invocation fails or response parsing fails
        """
        try:
            # Create prompt template from direct strings
            messages = [("system", system_prompt)]
            if human_prompt:
                messages.append(("human", human_prompt))

            prompt = ChatPromptTemplate.from_messages(messages)

            # Format messages
            formatted_messages = prompt.format_messages(**kwargs)
            self._check_token_limit(formatted_messages)

            # Use function_calling method for direct prompts (flexible with complex schemas)
            structured_llm = self.llm.with_structured_output(
                response_model, method="function_calling"
            )

            logger.debug(
                "Invoking LLM with structured output (direct prompts, function_calling method)"
            )
            structured_response = structured_llm.invoke(formatted_messages)
            logger.debug("Successfully received structured response (direct prompts)")

            return structured_response

        except Exception as e:
            logger.error(f"Direct structured output invocation failed: {e}")
            raise LLMError(f"Structured output failed: {str(e)}")

    def _check_token_limit(self, messages):
        """
        Check if the messages exceed the model's token limit.

        Args:
            messages: List of formatted messages

        Raises:
            LLMError: If token count exceeds the safe limit
        """
        try:
            # Estimate token count
            token_count = estimate_messages_token_count(messages)

            # Get safe limit for current model
            model_name = self.config.llm.model
            safe_limit = get_safe_context_limit(model_name)

            logger.debug(
                f"Token count check: {token_count} tokens, safe limit: {safe_limit}"
            )

            if token_count > safe_limit:
                error_msg = (
                    f"Context too large: {token_count} tokens exceeds safe limit of {safe_limit} "
                    f"for model {model_name}. Consider reducing schema size, limiting unique nouns, "
                    f"or using a model with larger context window."
                )
                logger.error(error_msg)
                raise LLMError(error_msg)

        except Exception as e:
            # If token checking fails, log warning but don't block the request
            logger.warning(f"Failed to check token limit: {e}")

    _DEFAULT_HUMAN_TEMPLATES = {
        "parse_question": (
            "===Database schema:\n{schema}\n\n===User question:\n{question}\n\n"
            "Identify relevant tables and columns:"
        ),
        "generate_sql": (
            "===Database schema:\n{schema}\n\n===User question:\n{question}\n\n"
            "===Relevant tables and columns:\n{parsed_question}\n\n"
            "===Unique nouns in relevant tables:\n{unique_nouns}\n\n"
            "Generate SQL query string"
        ),
        "validate_sql": (
            "===Database schema:\n{schema}\n\n===Generated SQL query:\n{sql_query}\n\n"
            "Validate and fix if needed:"
        ),
        "format_results": (
            "User question: {question}\n\nQuery results: {query_results}\n\nFormatted response:"
        ),
        "choose_visualization": (
            "User question: {question}\nSQL query: {sql_query}\nQuery results: {query_results}\n\n"
            "Recommend a visualization:"
        ),
        "choose_and_format_visualization": (
            "Question: {question}\nSQL Query: {sql_query}\n"
            "Data: {num_rows} rows x {num_cols} columns\n"
            "Sample: {query_results_sample}\nFull: {query_results_full}\n\n"
            "Choose visualization and format data:"
        ),
    }

    def create_prompt_from_config(
        self, prompt_name: str, **kwargs
    ) -> ChatPromptTemplate:
        """
        Create a ChatPromptTemplate from configuration.

        Args:
            prompt_name: Name of the prompt in configuration
            **kwargs: Additional variables for prompt formatting

        Returns:
            Configured ChatPromptTemplate
        """
        try:
            system_template = self.config.get_prompt(prompt_name, "system")
            human_template = self.config.get_prompt(prompt_name, "human")

            if not system_template:
                raise ConfigurationError(
                    f"Prompt '{prompt_name}' not found in configuration"
                )

            # Add database type to templates if they contain the placeholder
            if "{database_type}" in system_template:
                kwargs["database_type"] = self.config.get_database_type()

            # Create the chat prompt template directly - let LangChain handle variable detection
            messages = [("system", system_template)]

            if human_template:
                messages.append(("human", human_template))
            else:
                default_human = self._DEFAULT_HUMAN_TEMPLATES.get(
                    prompt_name, "{question}"
                )
                messages.append(("human", default_human))

            return ChatPromptTemplate.from_messages(messages)

        except Exception as e:
            logger.error(f"Failed to create prompt '{prompt_name}' from config: {e}")
            raise

    def invoke_with_config_prompt(self, prompt_name: str, **kwargs) -> str:
        """
        Invoke LLM using a prompt template from configuration.

        Args:
            prompt_name: Name of the prompt in configuration
            **kwargs: Variables to format into the prompt

        Returns:
            LLM response as string
        """
        try:
            prompt = self.create_prompt_from_config(prompt_name, **kwargs)
            return self.invoke(prompt, **kwargs)

        except Exception as e:
            logger.error(
                f"Failed to invoke LLM with config prompt '{prompt_name}': {e}"
            )
            return f"Error: {str(e)}"

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current LLM configuration.

        Returns:
            Dictionary with LLM configuration info
        """
        llm_config = self.config.llm

        return {
            "provider": llm_config.provider,
            "model": llm_config.model,
            "temperature": llm_config.temperature,
            "max_tokens": llm_config.max_tokens,
            "top_p": llm_config.top_p,
            "frequency_penalty": llm_config.frequency_penalty,
            "presence_penalty": llm_config.presence_penalty,
            "timeout": llm_config.timeout,
            "base_url": llm_config.base_url,
            "api_key_configured": (
                bool(os.getenv("OPENAI_API_KEY"))
                if llm_config.provider == "openai"
                else True
            ),
        }

    def _log_generic_connection_hint(self, error_msg: str, provider: str) -> bool:
        """Log a hint for generic (non-provider-specific) connection errors.

        Returns True if a hint was logged, False otherwise.
        """
        if (
            "api key" in error_msg
            or "authentication" in error_msg
            or "unauthorized" in error_msg
        ):
            logger.error(
                f"Authentication issue - check your {provider} API key or credentials"
            )
            return True
        if "quota" in error_msg or "rate limit" in error_msg:
            logger.error(f"{provider} rate limit or quota exceeded")
            return True
        if "timeout" in error_msg or "connection" in error_msg:
            logger.error(
                f"Network connectivity issue - check your internet connection and {provider} service status"
            )
            return True
        if "model" in error_msg and "not found" in error_msg:
            logger.error(
                f"Model '{self.config.llm.model}' not found - check if the model name is correct for {provider}"
            )
            return True
        if "forbidden" in error_msg or "403" in error_msg:
            logger.error(
                f"Access forbidden - check your {provider} permissions and subscription"
            )
            return True
        return False

    @staticmethod
    def _log_provider_connection_hint(error_msg: str, provider: str) -> None:
        """Log a provider-specific diagnostic hint for a connection failure."""
        if provider == "azure_openai" and (
            "certificate" in error_msg or "tenant" in error_msg
        ):
            logger.error(
                "Azure certificate authentication issue - verify certificate path and tenant/client IDs"
            )
        elif provider == "vertex_ai" and (
            "project" in error_msg or "location" in error_msg
        ):
            logger.error(
                "Google Cloud project/location issue - verify project ID and region settings"
            )
        elif provider == "bedrock" and ("region" in error_msg or "aws" in error_msg):
            logger.error("AWS Bedrock access issue - verify region and AWS credentials")

    def _log_connection_error_hint(self, error_msg: str, provider: str) -> None:
        """Log a diagnostic hint for a connection failure."""
        if not self._log_generic_connection_hint(error_msg, provider):
            self._log_provider_connection_hint(error_msg, provider)

    def test_connection(self) -> bool:
        """
        Test the LLM connection with a simple query.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            provider = self.config.llm.provider
            logger.debug(f"Running {provider} LLM connection test...")

            # Use a simple test prompt that should work with any LLM
            test_prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "You are a helpful assistant. Respond with exactly 'OK' if you can process this request.",
                    ),
                    ("human", "Test connection"),
                ]
            )

            response = self.invoke(test_prompt)

            # Check if response was successful (not an error message)
            if response.startswith("Error:"):
                logger.error(f"{provider} LLM connection test failed: {response}")
                return False

            # Check if we got any response (LLM is accessible)
            if response and len(response.strip()) > 0:
                logger.info(
                    f"{provider} LLM connection test successful (response: '{response.strip()[:20]}...')"
                )
                return True

            logger.error(f"{provider} LLM connection test failed: empty response")
            return False

        except Exception as e:
            logger.error(f"LLM connection test failed: {e}")
            self._log_connection_error_hint(
                str(e).lower(), self.config.llm.provider.lower()
            )
            return False

    def cleanup(self):
        """Clean up HTTP client connections to prevent connection pool warnings."""
        if hasattr(self, "http_client") and self.http_client:
            try:
                self.http_client.close()
                logger.debug("HTTP client connections closed successfully")
            except Exception as e:
                logger.warning(f"Error closing HTTP client: {e}")
            finally:
                self.http_client = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup."""
        self.cleanup()

    def __del__(self):
        """Destructor - ensures cleanup on garbage collection."""
        try:
            self.cleanup()
        except Exception:
            # Silently ignore cleanup errors during garbage collection
            pass
