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
#   PyYAML (MIT)
#   pytest (MIT)

"""Tests for ConfigManager functionality."""

import os
import tempfile

import pytest
import yaml

_YAML_SUFFIX = ".yaml"
from unittest.mock import patch

from askrita.config_manager import ConfigManager, get_config, reset_config
from askrita.exceptions import ConfigurationError


@pytest.fixture(autouse=True)
def mock_openai_api_key():
    """Automatically mock OPENAI_API_KEY for all config tests."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
        yield


class TestConfigManager:
    """Test cases for ConfigManager class."""

    def test_load_config_from_file(self, temp_config_file, sample_config_data):
        """Test loading configuration from a valid YAML file."""
        config = ConfigManager(temp_config_file)

        assert config.config_path == temp_config_file
        assert (
            config.database.connection_string
            == sample_config_data["database"]["connection_string"]
        )
        assert config.llm.provider == sample_config_data["llm"]["provider"]
        assert config.llm.model == sample_config_data["llm"]["model"]
        assert config.workflow.steps["parse_question"] is True

    def test_load_config_with_defaults(self):
        """Test loading configuration with built-in defaults when no file provided."""
        config = ConfigManager(None)

        assert config.config_path is None
        assert config.database.connection_string == "sqlite:///./askrita_demo.db"
        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-4o"
        assert config.workflow.steps["parse_question"] is True

    def test_load_config_file_not_found(self):
        """Test error handling when config file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            ConfigManager("/nonexistent/config.yaml")

    def test_load_config_invalid_yaml(self):
        """Test error handling for invalid YAML syntax."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=_YAML_SUFFIX, delete=False
        ) as f:
            f.write("invalid: yaml: content: [")
            temp_path = f.name

        try:
            with pytest.raises(ConfigurationError, match="Invalid YAML syntax"):
                ConfigManager(temp_path)
        finally:
            os.unlink(temp_path)

    def test_config_validation_success(self, mock_config):
        """Test successful configuration validation."""
        assert mock_config.validate_config() is True

    def test_config_validation_missing_connection_string(self, sample_config_data):
        """Test validation failure for missing database connection."""
        # Remove connection string
        sample_config_data["database"]["connection_string"] = ""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=_YAML_SUFFIX, delete=False
        ) as f:
            yaml.dump(sample_config_data, f)
            temp_path = f.name

        try:
            with pytest.raises(
                ConfigurationError, match="Configuration validation failed"
            ):
                ConfigManager(temp_path)
        finally:
            os.unlink(temp_path)

    def test_database_config_properties(self, mock_config):
        """Test database configuration properties."""
        db_config = mock_config.database

        assert db_config.connection_string == "sqlite:///test.db"
        assert db_config.query_timeout == 30
        assert db_config.max_results == 100
        assert db_config.cache_schema is True

    def test_llm_config_properties(self, mock_config):
        """Test LLM configuration properties."""
        llm_config = mock_config.llm

        assert llm_config.provider == "openai"
        assert llm_config.model == "gpt-4o"
        assert llm_config.temperature == 0.1
        assert llm_config.max_tokens == 4000
        # api_key is now read from OPENAI_API_KEY environment variable

    def test_workflow_config_properties(self, mock_config):
        """Test workflow configuration properties."""
        workflow_config = mock_config.workflow

        assert workflow_config.steps["parse_question"] is True
        assert workflow_config.steps["generate_sql"] is True
        assert workflow_config.max_retries == 3
        assert workflow_config.output_format == "json"

    def test_get_database_type(self, mock_config):
        """Test database type detection."""
        assert mock_config.get_database_type() == "SQLite"

    def test_get_database_type_postgresql(self, sample_config_data):
        """Test PostgreSQL database type detection."""
        sample_config_data["database"][
            "connection_string"
        ] = "postgresql://user:pass@host:5432/db"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=_YAML_SUFFIX, delete=False
        ) as f:
            yaml.dump(sample_config_data, f)
            temp_path = f.name

        try:
            config = ConfigManager(temp_path)
            assert config.get_database_type() == "PostgreSQL"
        finally:
            os.unlink(temp_path)

    def test_get_database_type_mysql(self, sample_config_data):
        """Test MySQL database type detection."""
        sample_config_data["database"][
            "connection_string"
        ] = "mysql://user:pass@host:3306/db"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=_YAML_SUFFIX, delete=False
        ) as f:
            yaml.dump(sample_config_data, f)
            temp_path = f.name

        try:
            config = ConfigManager(temp_path)
            assert config.get_database_type() == "MySQL"
        finally:
            os.unlink(temp_path)

    def test_get_database_type_bigquery(self, sample_config_data):
        """Test BigQuery database type detection."""
        sample_config_data["database"][
            "connection_string"
        ] = "bigquery://project/dataset"
        sample_config_data["database"][
            "bigquery_gcloud_cli_auth"
        ] = True  # Add required auth

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=_YAML_SUFFIX, delete=False
        ) as f:
            yaml.dump(sample_config_data, f)
            temp_path = f.name

        try:
            config = ConfigManager(temp_path)
            assert config.get_database_type() == "BigQuery"
        finally:
            os.unlink(temp_path)

    def test_get_database_type_mongodb(self, sample_config_data):
        """Test MongoDB database type detection."""
        sample_config_data["database"][
            "connection_string"
        ] = "mongodb://user:pass@host:27017/mydb"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=_YAML_SUFFIX, delete=False
        ) as f:
            yaml.dump(sample_config_data, f)
            temp_path = f.name

        try:
            config = ConfigManager(temp_path)
            assert config.get_database_type() == "MongoDB"
        finally:
            os.unlink(temp_path)

    def test_get_database_type_mongodb_atlas(self, sample_config_data):
        """Test MongoDB Atlas SRV database type detection."""
        sample_config_data["database"][
            "connection_string"
        ] = "mongodb+srv://user:pass@cluster.mongodb.net/mydb"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=_YAML_SUFFIX, delete=False
        ) as f:
            yaml.dump(sample_config_data, f)
            temp_path = f.name

        try:
            config = ConfigManager(temp_path)
            assert config.get_database_type() == "MongoDB"
        finally:
            os.unlink(temp_path)

    def test_is_step_enabled(self, mock_config):
        """Test workflow step enablement checking."""
        assert mock_config.is_step_enabled("parse_question") is True
        assert mock_config.is_step_enabled("generate_sql") is True

    def test_get_prompt(self, mock_config):
        """Test prompt template retrieval."""
        system_prompt = mock_config.get_prompt("parse_question", "system")
        human_prompt = mock_config.get_prompt("parse_question", "human")

        assert "data analyst" in system_prompt.lower()
        assert "question" in human_prompt.lower()

    def test_get_business_rule(self, mock_config):
        """Test business rule retrieval."""
        rule = mock_config.get_business_rule("data_validation")

        assert rule["skip_null_values"] is True
        assert rule["skip_empty_strings"] is True

    def test_schema_caching(self, mock_config):
        """Test schema caching functionality."""
        # Initially no cache
        assert mock_config.get_schema_cache() is None

        # Set cache
        test_schema = "CREATE TABLE test (id INT)"
        mock_config.set_schema_cache(test_schema)
        mock_config.set_schema_cache.assert_called_once_with(test_schema)

    def test_config_reload(self, temp_config_file):
        """Test configuration reloading."""
        config = ConfigManager(temp_config_file)

        # Modify the config file
        with open(temp_config_file, "r") as f:
            config_data = yaml.safe_load(f)

        config_data["database"]["query_timeout"] = 60

        with open(temp_config_file, "w") as f:
            yaml.dump(config_data, f)

        # Reload config
        config.reload_config()

        assert config.database.query_timeout == 60

    def test_environment_detection(self, temp_config_file):
        """Test environment detection from env var."""
        with patch.dict(os.environ, {"ASKRITA_ENV": "production"}):
            config = ConfigManager(temp_config_file)
            assert config.environment == "production"

    def test_deep_merge_defaults(self, sample_config_data):
        """Test deep merging of user config with defaults."""
        # Partial config with only database settings
        partial_config = {
            "database": {"connection_string": "postgresql://test:test@localhost/test"}
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=_YAML_SUFFIX, delete=False
        ) as f:
            yaml.dump(partial_config, f)
            temp_path = f.name

        try:
            config = ConfigManager(temp_path)

            # Should have custom database connection
            assert (
                config.database.connection_string
                == "postgresql://test:test@localhost/test"
            )
            # Should have default LLM settings
            assert config.llm.provider == "openai"
            assert config.llm.model == "gpt-4o"
        finally:
            os.unlink(temp_path)


class TestGlobalConfigManager:
    """Test cases for global configuration management."""

    def test_get_config_singleton(self, temp_config_file):
        """Test that get_config returns singleton instance."""
        config1 = get_config(temp_config_file)
        config2 = get_config()  # Should return same instance

        assert config1 is config2

    def test_reset_config(self, temp_config_file):
        """Test resetting global configuration."""
        config1 = get_config(temp_config_file)
        reset_config()
        config2 = get_config()

        assert config1 is not config2

    def test_get_config_without_path(self):
        """Test getting config without providing path uses defaults."""
        reset_config()
        config = get_config()

        assert config.config_path is None
        assert config.database.connection_string == "sqlite:///./askrita_demo.db"


class TestConfigManagerEdgeCases:
    """Test edge cases and error scenarios."""

    def test_permission_denied_error(self):
        """Test handling of permission denied errors."""
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", side_effect=PermissionError("Permission denied")),
        ):
            with pytest.raises(ConfigurationError, match="Permission denied"):
                ConfigManager("/some/file.yaml")

    def test_empty_config_file(self):
        """Test handling of empty config file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=_YAML_SUFFIX, delete=False
        ) as f:
            f.write("")  # Empty file
            temp_path = f.name

        try:
            config = ConfigManager(temp_path)
            # Should fall back to defaults
            assert config.llm.provider == "openai"
        finally:
            os.unlink(temp_path)

    def test_config_with_null_values(self):
        """Test handling of config with null values."""
        config_data = {
            "database": {
                "connection_string": "sqlite:///./test.db"  # Provide valid connection
            },
            "llm": {
                "provider": "openai",
                "model": "gpt-4o",
                # api_key is now read from OPENAI_API_KEY environment variable
            },
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=_YAML_SUFFIX, delete=False
        ) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            with patch("os.getenv") as mock_getenv:
                mock_getenv.return_value = "test-env-key"  # Mock OPENAI_API_KEY
                config = ConfigManager(temp_path)
            # Should load properly with provided values
            assert config.database.connection_string == "sqlite:///./test.db"
            assert config.llm.model == "gpt-4o"
            assert config.llm.provider == "openai"
        finally:
            os.unlink(temp_path)

    def test_config_with_extra_fields(self, sample_config_data):
        """Test handling of config with unknown fields."""
        sample_config_data["unknown_section"] = {"unknown_field": "value"}

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=_YAML_SUFFIX, delete=False
        ) as f:
            yaml.dump(sample_config_data, f)
            temp_path = f.name

        try:
            config = ConfigManager(temp_path)
            # Should load successfully and ignore unknown fields
            assert config.llm.provider == "openai"
        finally:
            os.unlink(temp_path)

    def test_missing_api_key_validation(self, sample_config_data):
        """Test validation failure for missing API key."""
        # Remove api_key from config since it's now read from environment variable
        if "api_key" in sample_config_data["llm"]:
            del sample_config_data["llm"]["api_key"]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=_YAML_SUFFIX, delete=False
        ) as f:
            yaml.dump(sample_config_data, f)
            temp_path = f.name

        try:
            # Should fail validation due to missing API key for OpenAI (no env var set)
            with patch("os.getenv") as mock_getenv:
                mock_getenv.return_value = None  # No OPENAI_API_KEY env var
                with pytest.raises(
                    ConfigurationError, match="Configuration validation failed"
                ):
                    ConfigManager(temp_path)
        finally:
            os.unlink(temp_path)
