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

"""Tests for NoSQL database connection strategies."""

import pytest
from unittest.mock import Mock

from askrita.sqlagent.database.nosql_strategies import (
    NoSQLConnectionStrategy,
    MongoDBStrategy,
)
from askrita.exceptions import DatabaseError


class TestNoSQLConnectionStrategy:
    """Test the abstract NoSQLConnectionStrategy base class."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that NoSQLConnectionStrategy cannot be instantiated directly."""
        with pytest.raises(TypeError):
            NoSQLConnectionStrategy()

    def test_enhance_schema_default_returns_unchanged(self):
        """Test default enhance_schema returns schema unchanged."""

        class MinimalStrategy(NoSQLConnectionStrategy):
            def setup_auth(self, config):
                pass

            def test_connection(self, client, config):
                return True

            def get_connection_type(self):
                return "test"

        strategy = MinimalStrategy()
        assert strategy.enhance_schema("original schema", None) == "original schema"

    def test_get_safe_connection_info_with_credentials(self):
        """Test safe connection info hides credentials."""

        class MinimalStrategy(NoSQLConnectionStrategy):
            def setup_auth(self, config):
                pass

            def test_connection(self, client, config):
                return True

            def get_connection_type(self):
                return "test"

        strategy = MinimalStrategy()
        result = strategy.get_safe_connection_info("mongodb://user:pass@host:27017/db")
        assert "user" not in result
        assert "pass" not in result
        assert "host:27017/db" in result

    def test_get_safe_connection_info_without_credentials(self):
        """Test safe connection info with no credentials."""

        class MinimalStrategy(NoSQLConnectionStrategy):
            def setup_auth(self, config):
                pass

            def test_connection(self, client, config):
                return True

            def get_connection_type(self):
                return "test"

        strategy = MinimalStrategy()
        result = strategy.get_safe_connection_info("mongodb://localhost:27017/db")
        assert "Test: localhost:27017/db" in result

    def test_get_safe_connection_info_no_protocol(self):
        """Test safe connection info with no protocol prefix."""

        class MinimalStrategy(NoSQLConnectionStrategy):
            def setup_auth(self, config):
                pass

            def test_connection(self, client, config):
                return True

            def get_connection_type(self):
                return "test"

        strategy = MinimalStrategy()
        result = strategy.get_safe_connection_info("just-a-string")
        assert result == "configured database"


class TestMongoDBStrategy:
    """Test the MongoDBStrategy implementation."""

    def test_get_connection_type(self):
        """Test that connection type is 'mongodb'."""
        strategy = MongoDBStrategy()
        assert strategy.get_connection_type() == "mongodb"

    def test_setup_auth_logs_info(self):
        """Test that setup_auth runs without error."""
        strategy = MongoDBStrategy()
        strategy.setup_auth(Mock())

    def test_test_connection_success(self):
        """Test successful connection test via ping."""
        strategy = MongoDBStrategy()
        mock_client = Mock()
        mock_client.admin.command.return_value = {"ok": 1}

        result = strategy.test_connection(mock_client, Mock())
        assert result is True
        mock_client.admin.command.assert_called_once_with("ping")

    def test_test_connection_failure(self):
        """Test failed connection test."""
        strategy = MongoDBStrategy()
        mock_client = Mock()
        mock_client.admin.command.side_effect = Exception("Connection refused")

        result = strategy.test_connection(mock_client, Mock())
        assert result is False

    def test_enhance_schema_adds_database_type(self):
        """Test that enhance_schema adds MongoDB type context."""
        strategy = MongoDBStrategy()
        mock_config = Mock()
        mock_config.get_schema_descriptions = None

        result = strategy.enhance_schema("Collection: orders\nFields: ...", mock_config)
        assert "MongoDB" in result
        assert "NoSQL Document Store" in result
        assert "aggregation pipelines" in result
        assert "Collection: orders" in result

    def test_enhance_schema_with_project_context(self):
        """Test enhance_schema includes project context when configured."""
        strategy = MongoDBStrategy()
        mock_config = Mock()
        mock_descriptions = Mock()
        mock_descriptions.project_context = "E-commerce analytics database"
        mock_config.get_schema_descriptions.return_value = mock_descriptions

        result = strategy.enhance_schema("schema data", mock_config)
        assert "E-commerce analytics database" in result
        assert "MongoDB" in result

    def test_enhance_schema_handles_missing_descriptions(self):
        """Test enhance_schema handles missing description config gracefully."""
        strategy = MongoDBStrategy()
        mock_config = Mock(spec=[])

        result = strategy.enhance_schema("schema data", mock_config)
        assert "MongoDB" in result
        assert "schema data" in result

    def test_enhance_schema_handles_description_error(self):
        """Test enhance_schema handles errors in description retrieval."""
        strategy = MongoDBStrategy()
        mock_config = Mock()
        mock_config.get_schema_descriptions.side_effect = Exception("Config error")

        result = strategy.enhance_schema("schema data", mock_config)
        assert "MongoDB" in result
        assert "schema data" in result

    def test_extract_database_name_standard_uri(self):
        """Test database name extraction from standard MongoDB URI."""
        strategy = MongoDBStrategy()
        mock_config = Mock()
        mock_config.database.connection_string = "mongodb://user:pass@host:27017/mydb"

        result = strategy._extract_database_name(mock_config)
        assert result == "mydb"

    def test_extract_database_name_atlas_uri(self):
        """Test database name extraction from Atlas SRV URI."""
        strategy = MongoDBStrategy()
        mock_config = Mock()
        mock_config.database.connection_string = "mongodb+srv://user:pass@cluster.mongodb.net/analytics"

        result = strategy._extract_database_name(mock_config)
        assert result == "analytics"

    def test_extract_database_name_with_query_params(self):
        """Test database name extraction with query parameters."""
        strategy = MongoDBStrategy()
        mock_config = Mock()
        mock_config.database.connection_string = "mongodb://host:27017/testdb?authSource=admin&retryWrites=true"

        result = strategy._extract_database_name(mock_config)
        assert result == "testdb"

    def test_extract_database_name_missing_raises_error(self):
        """Test that missing database name raises DatabaseError."""
        strategy = MongoDBStrategy()
        mock_config = Mock()
        mock_config.database.connection_string = "mongodb://host:27017/"

        with pytest.raises(DatabaseError, match="Could not extract database name"):
            strategy._extract_database_name(mock_config)

    def test_extract_database_name_no_path_raises_error(self):
        """Test that connection string without path raises DatabaseError."""
        strategy = MongoDBStrategy()
        mock_config = Mock()
        mock_config.database.connection_string = "mongodb://host:27017"

        with pytest.raises(DatabaseError, match="Could not extract database name"):
            strategy._extract_database_name(mock_config)

    def test_get_safe_connection_info_with_credentials(self):
        """Test safe connection info masks credentials."""
        strategy = MongoDBStrategy()
        result = strategy.get_safe_connection_info("mongodb://admin:secret@cluster.mongodb.net/mydb")
        assert "admin" not in result
        assert "secret" not in result
        assert "MongoDB:" in result
        assert "cluster.mongodb.net/mydb" in result

    def test_get_safe_connection_info_atlas(self):
        """Test safe connection info for Atlas SRV."""
        strategy = MongoDBStrategy()
        result = strategy.get_safe_connection_info("mongodb+srv://user:pass@cluster.mongodb.net/db")
        assert "user" not in result
        assert "pass" not in result
        assert "MongoDB:" in result

    def test_get_safe_connection_info_no_credentials(self):
        """Test safe connection info without credentials."""
        strategy = MongoDBStrategy()
        result = strategy.get_safe_connection_info("mongodb://localhost:27017/testdb")
        assert "MongoDB:" in result
        assert "localhost:27017/testdb" in result
