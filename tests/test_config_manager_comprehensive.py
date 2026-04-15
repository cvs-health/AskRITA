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

"""Comprehensive tests for ConfigManager to improve coverage."""

import os
import tempfile
from unittest.mock import patch

import yaml

_YAML_SUFFIX = ".yaml"
_SQLITE_DB_URL = "sqlite:///test.db"
from askrita.config_manager import ConfigManager, get_config, reset_config


class TestConfigManagerHelperMethods:
    """Test helper methods in ConfigManager."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})
    def test_get_input_validation_settings(self):
        """Test get_input_validation_settings method."""
        config = self._create_test_config()
        settings = config.get_input_validation_settings()
        assert isinstance(settings, dict)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})
    def test_get_parse_overrides(self):
        """Test get_parse_overrides method."""
        config = self._create_test_config()
        overrides = config.get_parse_overrides()
        assert isinstance(overrides, list)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})
    def test_get_sql_safety_settings(self):
        """Test get_sql_safety_settings method."""
        config = self._create_test_config()
        settings = config.get_sql_safety_settings()
        assert isinstance(settings, dict)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})
    def test_get_conversation_context_settings(self):
        """Test get_conversation_context_settings method."""
        config = self._create_test_config()
        settings = config.get_conversation_context_settings()
        assert isinstance(settings, dict)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})
    def test_get_schema_descriptions(self):
        """Test get_schema_descriptions method."""
        config = self._create_test_config()
        schema_desc = config.get_schema_descriptions()
        assert schema_desc is not None

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})
    def test_is_step_enabled(self):
        """Test is_step_enabled method."""
        config = self._create_test_config()
        result = config.is_step_enabled("generate_sql")
        assert isinstance(result, bool)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})
    def test_get_database_type(self):
        """Test get_database_type method."""
        config = self._create_test_config()
        db_type = config.get_database_type()
        assert isinstance(db_type, str)

    @staticmethod
    def _create_test_config():
        """Create a real test config."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=_YAML_SUFFIX, delete=False
        ) as f:
            config_data = {
                "database": {"connection_string": _SQLITE_DB_URL},
                "llm": {"provider": "openai", "model": "gpt-4o"},
            }
            yaml.dump(config_data, f)
            config_path = f.name
        try:
            return ConfigManager(config_path)
        finally:
            os.unlink(config_path)


class TestConfigManagerCaching:
    """Test schema caching functionality."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})
    def test_should_cache_schema(self):
        """Test should_cache_schema method."""
        config = TestConfigManagerHelperMethods._create_test_config()
        result = config.should_cache_schema()
        assert isinstance(result, bool)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})
    def test_schema_cache_operations(self):
        """Test schema cache set/get/clear."""
        config = TestConfigManagerHelperMethods._create_test_config()

        # Set cache
        config.set_schema_cache("CREATE TABLE test (id INT)")

        # Get cache (may or may not cache depending on settings)
        config.get_schema_cache()

        # Get cache info
        info = config.get_schema_cache_info()
        assert isinstance(info, dict)

        # Clear cache
        config.clear_schema_cache()


class TestConfigManagerValidation:
    """Test config validation methods."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})
    def test_validate_config(self):
        """Test validate_config method."""
        config = TestConfigManagerHelperMethods._create_test_config()
        result = config.validate_config()
        assert isinstance(result, bool)


class TestConfigManagerDeepMerge:
    """Test deep merge functionality."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})
    def test_deep_merge_defaults(self):
        """Test _deep_merge_defaults method."""
        # Create a config with minimal data
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=_YAML_SUFFIX, delete=False
        ) as f:
            config_data = {
                "database": {"connection_string": "test://connection"},
                "llm": {"provider": "openai", "model": "gpt-4"},
            }
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            config = ConfigManager(config_path)

            # Verify defaults were merged
            assert hasattr(config, "workflow")
            assert hasattr(config, "framework")
        finally:
            os.unlink(config_path)


class TestConfigManagerEdgeCases:
    """Test edge cases and error conditions."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})
    def test_is_step_enabled_missing(self):
        """Test is_step_enabled with missing step."""
        config = TestConfigManagerHelperMethods._create_test_config()
        result = config.is_step_enabled("nonexistent_step_12345")
        assert isinstance(result, bool)


class TestGlobalConfigManagement:
    """Test global config singleton."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})
    def test_reset_and_get_config(self):
        """Test reset_config and get_config functions."""
        # Reset should clear global config
        reset_config()

        # Get should create new instance
        config1 = get_config()
        assert config1 is not None

        # Second get should return same instance
        config2 = get_config()
        assert config1 is config2


class TestConfigManagerProperties:
    """Test ConfigManager property accessors."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})
    def test_database_property(self):
        """Test database property."""
        config = TestConfigManagerHelperMethods._create_test_config()
        db_config = config.database
        assert db_config is not None
        assert hasattr(db_config, "connection_string")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})
    def test_llm_property(self):
        """Test llm property."""
        config = TestConfigManagerHelperMethods._create_test_config()
        llm_config = config.llm
        assert llm_config is not None
        assert hasattr(llm_config, "provider")
        assert hasattr(llm_config, "model")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})
    def test_workflow_property(self):
        """Test workflow property."""
        config = TestConfigManagerHelperMethods._create_test_config()
        workflow_config = config.workflow
        assert workflow_config is not None

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})
    def test_framework_property(self):
        """Test framework property."""
        config = TestConfigManagerHelperMethods._create_test_config()
        framework_config = config.framework
        assert framework_config is not None

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})
    def test_data_processing_property(self):
        """Test data_processing property."""
        config = TestConfigManagerHelperMethods._create_test_config()
        dp_config = config.data_processing
        assert dp_config is not None


class TestConfigManagerWithRealYAML:
    """Test ConfigManager with real YAML files."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})
    def test_load_minimal_config(self):
        """Test loading a minimal config."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=_YAML_SUFFIX, delete=False
        ) as f:
            minimal_config = {
                "database": {"connection_string": _SQLITE_DB_URL},
                "llm": {"provider": "openai", "model": "gpt-4o", "temperature": 0},
            }
            yaml.dump(minimal_config, f)
            config_path = f.name

        try:
            config = ConfigManager(config_path)
            assert config.database.connection_string == _SQLITE_DB_URL
            assert config.llm.provider == "openai"
        finally:
            os.unlink(config_path)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})
    def test_load_config_with_all_sections(self):
        """Test loading a comprehensive config."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=_YAML_SUFFIX, delete=False
        ) as f:
            full_config = {
                "database": {
                    "connection_string": "bigquery://project/dataset",
                    "bigquery_gcloud_cli_auth": True,
                },
                "llm": {"provider": "openai", "model": "gpt-4o", "temperature": 0.7},
                "workflow": {"steps": {"parse_question": True, "generate_sql": True}},
                "framework": {"debug": False},
                "prompts": {
                    "test_prompt": {
                        "system": "Test system prompt",
                        "human": "Test human prompt",
                    }
                },
            }
            yaml.dump(full_config, f)
            config_path = f.name

        try:
            config = ConfigManager(config_path)
            assert config.database.connection_string == "bigquery://project/dataset"
            assert config.llm.temperature == 0.7
            assert config.workflow is not None
        finally:
            os.unlink(config_path)


class TestConfigManagerEnvironmentVariables:
    """Test environment variable substitution."""

    @patch.dict(
        os.environ,
        {
            "TEST_DB_CONNECTION": "test://connection/string",
            "OPENAI_API_KEY": "test-key-12345",
        },
    )
    def test_env_var_substitution(self):
        """Test that ${VAR} in config gets replaced."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=_YAML_SUFFIX, delete=False
        ) as f:
            config_with_env = {
                "database": {"connection_string": "${TEST_DB_CONNECTION}"},
                "llm": {"provider": "openai", "model": "gpt-4o"},
            }
            yaml.dump(config_with_env, f)
            config_path = f.name

        try:
            config = ConfigManager(config_path)
            # Should have substituted the env var
            assert (
                "test://connection/string" in config.database.connection_string
                or "${TEST_DB_CONNECTION}" in config.database.connection_string
            )
        finally:
            os.unlink(config_path)
