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
#   pytest (MIT)

"""Additional targeted tests for config_manager.py missing coverage lines."""

import os
from unittest.mock import patch

import pytest

from askrita.config_manager import ConfigManager

_BIGQUERY_CONN = "bigquery://project/dataset"


@pytest.fixture(autouse=True)
def openai_env():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        yield


# ---------------------------------------------------------------------------
# get_database_type
# ---------------------------------------------------------------------------


class TestGetDatabaseType:
    def test_postgresql(self):
        cm = ConfigManager(None)
        cm._config_data["database"][
            "connection_string"
        ] = "postgresql://user:pass@host/db"
        assert cm.get_database_type() == "PostgreSQL"

    def test_mysql(self):
        cm = ConfigManager(None)
        cm._config_data["database"]["connection_string"] = "mysql://user:pass@host/db"
        assert cm.get_database_type() == "MySQL"

    def test_sqlite(self):
        cm = ConfigManager(None)
        assert cm.get_database_type() == "SQLite"

    def test_bigquery(self):
        cm = ConfigManager(None)
        cm._config_data["database"]["connection_string"] = _BIGQUERY_CONN
        assert cm.get_database_type() == "BigQuery"

    def test_snowflake(self):
        cm = ConfigManager(None)
        cm._config_data["database"]["connection_string"] = "snowflake://account/db"
        assert cm.get_database_type() == "Snowflake"

    def test_mongodb(self):
        cm = ConfigManager(None)
        cm._config_data["database"]["connection_string"] = "mongodb://host:27017/db"
        assert cm.get_database_type() == "MongoDB"

    def test_mongodb_srv(self):
        cm = ConfigManager(None)
        cm._config_data["database"]["connection_string"] = "mongodb+srv://host/db"
        assert cm.get_database_type() == "MongoDB"

    def test_unknown_defaults_to_sql(self):
        cm = ConfigManager(None)
        cm._config_data["database"]["connection_string"] = "mssql://server/db"
        assert cm.get_database_type() == "SQL"


# ---------------------------------------------------------------------------
# _validate_required_prompts
# ---------------------------------------------------------------------------


class TestValidateRequiredPrompts:
    def test_returns_true_with_all_required_prompts(self):
        cm = ConfigManager(None)
        # Default config has all required prompts
        result = cm._validate_required_prompts()
        assert result is True

    def test_returns_false_when_prompt_missing(self):
        cm = ConfigManager(None)
        # Remove a core required prompt
        del cm._config_data["prompts"]["parse_question"]
        result = cm._validate_required_prompts()
        assert result is False

    def test_returns_false_when_prompt_invalid_format(self):
        cm = ConfigManager(None)
        # Replace with non-dict
        cm._config_data["prompts"]["parse_question"] = "just a string"
        result = cm._validate_required_prompts()
        assert result is False

    def test_returns_false_when_system_template_missing(self):
        cm = ConfigManager(None)
        # Remove system key from a prompt
        cm._config_data["prompts"]["parse_question"] = {"human": "Template"}
        result = cm._validate_required_prompts()
        assert result is False

    def test_optional_prompts_not_checked_when_step_disabled(self):
        cm = ConfigManager(None)
        # ensure followup step is disabled (default is False)
        cm._config_data["workflow"]["steps"]["generate_followup_questions"] = False
        # Should not fail even if the prompt is missing
        if "generate_followup_questions" in cm._config_data["prompts"]:
            del cm._config_data["prompts"]["generate_followup_questions"]
        result = cm._validate_required_prompts()
        assert result is True

    def test_optional_prompts_checked_when_step_enabled(self):
        cm = ConfigManager(None)
        cm._config_data["workflow"]["steps"]["generate_followup_questions"] = True
        # Remove the prompt to trigger failure
        cm._config_data["prompts"].pop("generate_followup_questions", None)
        result = cm._validate_required_prompts()
        assert result is False

    def test_format_data_universal_checked_when_step_enabled(self):
        cm = ConfigManager(None)
        cm._config_data["workflow"]["steps"]["format_data_for_visualization"] = True
        # Remove the prompt
        cm._config_data["prompts"].pop("format_data_universal", None)
        result = cm._validate_required_prompts()
        assert result is False


# ---------------------------------------------------------------------------
# _validate_llm_config
# ---------------------------------------------------------------------------


class TestValidateLlmConfig:
    def test_openai_valid(self):
        cm = ConfigManager(None)
        result = cm._validate_llm_config()
        assert result is True

    def test_openai_missing_api_key(self):
        cm = ConfigManager(None)
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OPENAI_API_KEY", None)
            result = cm._validate_llm_config()
            assert result is False

    def test_openai_missing_model(self):
        cm = ConfigManager(None)
        cm._config_data["llm"]["model"] = ""
        result = cm._validate_llm_config()
        assert result is False

    def test_azure_openai_missing_required_fields(self):
        cm = ConfigManager(None)
        cm._config_data["llm"]["provider"] = "azure_openai"
        cm._config_data["llm"]["azure_endpoint"] = None
        cm._config_data["llm"]["azure_deployment"] = None
        result = cm._validate_llm_config()
        assert result is False

    def test_azure_openai_missing_cert_auth(self):
        cm = ConfigManager(None)
        cm._config_data["llm"]["provider"] = "azure_openai"
        cm._config_data["llm"]["azure_endpoint"] = "https://test.openai.azure.com"
        cm._config_data["llm"]["azure_deployment"] = "gpt-4"
        cm._config_data["llm"]["azure_tenant_id"] = None
        cm._config_data["llm"]["azure_client_id"] = None
        cm._config_data["llm"]["azure_certificate_path"] = None
        result = cm._validate_llm_config()
        assert result is False

    def test_azure_openai_valid_cert_auth(self):
        cm = ConfigManager(None)
        cm._config_data["llm"]["provider"] = "azure_openai"
        cm._config_data["llm"]["azure_endpoint"] = "https://test.openai.azure.com"
        cm._config_data["llm"]["azure_deployment"] = "gpt-4"
        cm._config_data["llm"]["azure_tenant_id"] = "tenant-id"
        cm._config_data["llm"]["azure_client_id"] = "client-id"
        cm._config_data["llm"]["azure_certificate_path"] = "/path/to/cert.pem"
        result = cm._validate_llm_config()
        assert result is True

    def test_vertex_ai_missing_project_id(self):
        cm = ConfigManager(None)
        cm._config_data["llm"]["provider"] = "vertex_ai"
        cm._config_data["llm"]["project_id"] = None
        cm._config_data["llm"]["credentials_path"] = None
        cm._config_data["llm"]["gcloud_cli_auth"] = False
        result = cm._validate_llm_config()
        assert result is False

    def test_vertex_ai_missing_auth(self):
        cm = ConfigManager(None)
        cm._config_data["llm"]["provider"] = "vertex_ai"
        cm._config_data["llm"]["project_id"] = "my-project"
        cm._config_data["llm"]["credentials_path"] = None
        cm._config_data["llm"]["gcloud_cli_auth"] = False
        result = cm._validate_llm_config()
        assert result is False

    def test_vertex_ai_with_gcloud_auth(self):
        cm = ConfigManager(None)
        cm._config_data["llm"]["provider"] = "vertex_ai"
        cm._config_data["llm"]["project_id"] = "my-project"
        cm._config_data["llm"]["credentials_path"] = None
        cm._config_data["llm"]["gcloud_cli_auth"] = True
        result = cm._validate_llm_config()
        assert result is True

    def test_vertex_ai_with_credentials_path(self):
        cm = ConfigManager(None)
        cm._config_data["llm"]["provider"] = "vertex_ai"
        cm._config_data["llm"]["project_id"] = "my-project"
        cm._config_data["llm"]["credentials_path"] = "/path/to/creds.json"
        cm._config_data["llm"]["gcloud_cli_auth"] = False
        result = cm._validate_llm_config()
        assert result is True


# ---------------------------------------------------------------------------
# validate_config
# ---------------------------------------------------------------------------


class TestValidateConfig:
    def test_validate_with_defaults_returns_true(self):
        cm = ConfigManager(None)
        result = cm.validate_config()
        assert result is True

    def test_validate_missing_required_section(self):
        cm = ConfigManager(None)
        del cm._config_data["database"]
        result = cm.validate_config()
        assert result is False

    def test_validate_missing_connection_string(self):
        cm = ConfigManager(None)
        cm._config_data["database"]["connection_string"] = ""
        result = cm.validate_config()
        assert result is False

    def test_validate_bigquery_no_auth(self):
        cm = ConfigManager(None)
        cm._config_data["database"]["connection_string"] = _BIGQUERY_CONN
        cm._config_data["database"]["bigquery_credentials_path"] = None
        cm._config_data["database"]["bigquery_gcloud_cli_auth"] = False
        result = cm.validate_config()
        assert result is False

    def test_validate_bigquery_with_service_account(self):
        cm = ConfigManager(None)
        cm._config_data["database"]["connection_string"] = _BIGQUERY_CONN
        cm._config_data["database"]["bigquery_credentials_path"] = "/path/to/sa.json"
        cm._config_data["database"]["bigquery_gcloud_cli_auth"] = False
        result = cm.validate_config()
        assert result is True

    def test_validate_bigquery_with_gcloud_auth(self):
        cm = ConfigManager(None)
        cm._config_data["database"]["connection_string"] = _BIGQUERY_CONN
        cm._config_data["database"]["bigquery_credentials_path"] = None
        cm._config_data["database"]["bigquery_gcloud_cli_auth"] = True
        result = cm.validate_config()
        assert result is True

    def test_validate_exception_returns_false(self):
        cm = ConfigManager(None)
        # Force an exception in validate_config by deleting required section key
        # so the section loop raises KeyError (won't happen; test the exception path another way)
        # Patch _validate_llm_config to raise
        with patch.object(
            cm, "_validate_llm_config", side_effect=RuntimeError("unexpected")
        ):
            result = cm.validate_config()
            assert result is False


# ---------------------------------------------------------------------------
# Schema cache methods
# ---------------------------------------------------------------------------


class TestSchemaCacheMethods:
    def test_should_cache_schema_false_when_disabled(self):
        cm = ConfigManager(None)
        cm._config_data["database"]["cache_schema"] = False
        assert cm.should_cache_schema() is False

    def test_should_cache_schema_true_when_no_cache_yet(self):
        cm = ConfigManager(None)
        cm._config_data["database"]["cache_schema"] = True
        cm._schema_cache_time = None
        assert cm.should_cache_schema() is True

    def test_set_and_get_schema_cache(self):
        cm = ConfigManager(None)
        cm._config_data["database"]["cache_schema"] = True
        cm.set_schema_cache("CREATE TABLE foo (id INT);")
        result = cm.get_schema_cache()
        assert result == "CREATE TABLE foo (id INT);"

    def test_clear_schema_cache(self):
        cm = ConfigManager(None)
        cm.set_schema_cache("SCHEMA")
        cm.clear_schema_cache()
        assert cm._schema_cache is None
        assert cm._schema_cache_time is None

    def test_get_schema_cache_info_disabled(self):
        cm = ConfigManager(None)
        cm._config_data["database"]["cache_schema"] = False
        info = cm.get_schema_cache_info()
        assert info["enabled"] is False
        assert info["cached"] is False

    def test_get_schema_cache_info_no_cache_yet(self):
        cm = ConfigManager(None)
        cm._config_data["database"]["cache_schema"] = True
        cm._schema_cache_time = None
        info = cm.get_schema_cache_info()
        assert info["enabled"] is True
        assert info["cached"] is False

    def test_get_schema_cache_info_with_cache(self):
        cm = ConfigManager(None)
        cm._config_data["database"]["cache_schema"] = True
        cm.set_schema_cache("SCHEMA")
        info = cm.get_schema_cache_info()
        assert info["enabled"] is True
        assert info["cached"] is True
        assert "age_seconds" in info
        assert "remaining_seconds" in info


# ---------------------------------------------------------------------------
# reload_config / get_parse_overrides / get_sql_safety_settings / etc.
# ---------------------------------------------------------------------------


class TestWorkflowHelperMethods:
    def test_get_parse_overrides_default(self):
        cm = ConfigManager(None)
        result = cm.get_parse_overrides()
        assert isinstance(result, list)

    def test_get_parse_overrides_null_workflow(self):
        cm = ConfigManager(None)
        cm._config_data["workflow"] = None
        result = cm.get_parse_overrides()
        assert result == []

    def test_get_sql_safety_settings(self):
        cm = ConfigManager(None)
        result = cm.get_sql_safety_settings()
        assert isinstance(result, dict)

    def test_get_conversation_context_settings(self):
        cm = ConfigManager(None)
        result = cm.get_conversation_context_settings()
        assert isinstance(result, dict)

    def test_is_step_enabled_known_step(self):
        cm = ConfigManager(None)
        # parse_question is enabled by default
        result = cm.is_step_enabled("parse_question")
        assert result is True

    def test_is_step_enabled_unknown_step_defaults_true(self):
        cm = ConfigManager(None)
        result = cm.is_step_enabled("nonexistent_step")
        assert result is True

    def test_reload_config(self):
        cm = ConfigManager(None)
        cm.reload_config()  # Should not raise

    def test_get_schema_descriptions_returns_config(self):
        cm = ConfigManager(None)
        result = cm.get_schema_descriptions()
        assert result is not None
