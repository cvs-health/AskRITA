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

"""Simple tests for database_strategies - just boost coverage."""

import pytest
from unittest.mock import Mock
from askrita.sqlagent.database.database_strategies import (
    BigQueryStrategy,
    PostgreSQLStrategy,
    SnowflakeStrategy
)


class TestBigQueryStrategy:
    """Test BigQueryStrategy basics."""

    def test_get_connection_type(self):
        """Test get_connection_type."""
        strategy = BigQueryStrategy()
        assert strategy.get_connection_type() == "bigquery"

    def test_enhance_schema_basic(self):
        """Test basic schema enhancement."""
        strategy = BigQueryStrategy()
        schema = "CREATE TABLE users (id INT)"
        mock_config = Mock()
        mock_config.database.cross_project_access.enabled = False

        result = strategy.enhance_schema(schema, mock_config)
        assert isinstance(result, str)

    def test_get_safe_connection_info(self):
        """Test getting safe connection info."""
        strategy = BigQueryStrategy()
        conn_str = "bigquery://my-project/my-dataset"

        result = strategy.get_safe_connection_info(conn_str)
        assert isinstance(result, str)
        assert "my-project" in result


class TestPostgreSQLStrategy:
    """Test PostgreSQLStrategy basics."""

    def test_get_connection_type(self):
        """Test get_connection_type."""
        strategy = PostgreSQLStrategy()
        assert strategy.get_connection_type() == "postgresql"

    def test_setup_auth(self):
        """Test setup_auth (should be no-op)."""
        strategy = PostgreSQLStrategy()
        mock_config = Mock()

        # Should not raise
        strategy.setup_auth(mock_config)

    def test_enhance_schema(self):
        """Test schema enhancement."""
        strategy = PostgreSQLStrategy()
        schema = "CREATE TABLE users (id INT)"
        mock_config = Mock()

        result = strategy.enhance_schema(schema, mock_config)
        assert isinstance(result, str)


class TestSnowflakeStrategy:
    """Test SnowflakeStrategy basics."""

    def test_get_connection_type(self):
        """Test get_connection_type."""
        strategy = SnowflakeStrategy()
        assert strategy.get_connection_type() == "snowflake"

    def test_setup_auth(self):
        """Test setup_auth (should be no-op)."""
        strategy = SnowflakeStrategy()
        mock_config = Mock()

        # Should not raise
        strategy.setup_auth(mock_config)

    def test_enhance_schema(self):
        """Test schema enhancement."""
        strategy = SnowflakeStrategy()
        schema = "CREATE TABLE users (id INT)"
        mock_config = Mock()

        result = strategy.enhance_schema(schema, mock_config)
        assert isinstance(result, str)


def test_safe_connection_info_defaults():
    """Test safe connection info helpers for strategies."""
    assert BigQueryStrategy().get_safe_connection_info('bigquery://test-project/test-dataset').startswith('BigQuery:')
    assert SnowflakeStrategy().get_safe_connection_info('snowflake://test-account/test-db').startswith('Snowflake:')
    assert 'configured database' not in PostgreSQLStrategy().get_safe_connection_info('postgresql://test-user:test-pass@localhost:5432/test-db')


def test_pg_snow_basic_paths():
    """Test basic auth/test/enhance for Postgres and Snowflake."""
    pg = PostgreSQLStrategy()
    sf = SnowflakeStrategy()
    cfg = Mock(); db = Mock()

    # setup_auth logs don't throw
    pg.setup_auth(cfg); sf.setup_auth(cfg)

    # test_connection success and failure through run_no_throw
    db.run_no_throw.return_value = "OK"
    assert pg.test_connection(db, cfg) is True
    assert sf.test_connection(db, cfg) is True

    db.run_no_throw.return_value = "Error: boom"
    assert pg.test_connection(db, cfg) is False
    assert sf.test_connection(db, cfg) is False

    # enhance_schema no-op
    assert pg.enhance_schema('schema', cfg) == 'schema'
    assert sf.enhance_schema('schema', cfg) == 'schema'


def test_database_factory_is_nosql():
    """Test DatabaseStrategyFactory.is_nosql() detects MongoDB connection strings."""
    from askrita.sqlagent.database.database_factory import DatabaseStrategyFactory

    assert DatabaseStrategyFactory.is_nosql("mongodb://host:27017/db") is True
    assert DatabaseStrategyFactory.is_nosql("mongodb+srv://user:pass@cluster.mongodb.net/db") is True
    assert DatabaseStrategyFactory.is_nosql("MONGODB://HOST:27017/DB") is True
    assert DatabaseStrategyFactory.is_nosql("postgresql://host:5432/db") is False
    assert DatabaseStrategyFactory.is_nosql("bigquery://project/dataset") is False
    assert DatabaseStrategyFactory.is_nosql("") is False
    assert DatabaseStrategyFactory.is_nosql(None) is False


# ---------------------------------------------------------------------------
# DatabaseStrategyFactory – additional coverage (lines 71, 75, 82-85, 103, 132-138)
# ---------------------------------------------------------------------------

class TestDatabaseStrategyFactory:
    """Tests for DatabaseStrategyFactory missing coverage lines."""

    def setup_method(self):
        from askrita.sqlagent.database.database_factory import DatabaseStrategyFactory
        self.factory = DatabaseStrategyFactory

    def test_create_strategy_raises_for_empty_string(self):
        """Line 71: empty string raises DatabaseError."""
        from askrita.exceptions import DatabaseError
        with pytest.raises(DatabaseError, match="non-empty string"):
            self.factory.create_strategy("")

    def test_create_strategy_raises_for_none(self):
        """Line 71: None raises DatabaseError."""
        from askrita.exceptions import DatabaseError
        with pytest.raises(DatabaseError, match="non-empty string"):
            self.factory.create_strategy(None)

    def test_create_strategy_raises_for_non_string(self):
        """Line 71: non-string raises DatabaseError."""
        from askrita.exceptions import DatabaseError
        with pytest.raises(DatabaseError, match="non-empty string"):
            self.factory.create_strategy(12345)

    def test_create_strategy_raises_for_missing_scheme_separator(self):
        """Line 75: connection string without '://' raises DatabaseError."""
        from askrita.exceptions import DatabaseError
        with pytest.raises(DatabaseError, match="Invalid connection string format"):
            self.factory.create_strategy("no-scheme-separator")

    def test_create_strategy_fallback_for_unknown_db_type(self):
        """Lines 82-85: unsupported db type falls back to PostgreSQL strategy."""
        from askrita.sqlagent.database.database_strategies import PostgreSQLStrategy
        strategy = self.factory.create_strategy("mysql+asyncpg://host/db")
        assert isinstance(strategy, PostgreSQLStrategy)

    def test_get_supported_types_returns_list(self):
        """Line 103: get_supported_types returns a non-empty list of strings."""
        types = self.factory.get_supported_types()
        assert isinstance(types, list)
        assert len(types) > 0
        assert "bigquery" in types
        assert "snowflake" in types
        assert "postgresql" in types

    def test_register_strategy_adds_new_type(self):
        """Lines 132-138: register_strategy stores a new strategy class."""
        from askrita.sqlagent.database.database_strategies import PostgreSQLStrategy

        # Register a custom alias using an existing concrete strategy class
        self.factory.register_strategy("custom_db_test", PostgreSQLStrategy)
        assert "custom_db_test" in self.factory.get_supported_types()
        # Clean up so test isolation is preserved
        del self.factory._strategies["custom_db_test"]

    def test_register_strategy_normalises_to_lowercase(self):
        """Lines 132-138: register_strategy normalises db_type to lowercase."""
        from askrita.sqlagent.database.database_strategies import PostgreSQLStrategy

        self.factory.register_strategy("MixedCase_DB", PostgreSQLStrategy)
        assert "mixedcase_db" in self.factory.get_supported_types()
        del self.factory._strategies["mixedcase_db"]

    def test_register_strategy_raises_for_invalid_class(self):
        """Lines 132-133: register_strategy raises ValueError for non-strategy class."""
        with pytest.raises(ValueError, match="DatabaseConnectionStrategy"):
            self.factory.register_strategy("bad_type", object)

    def test_create_strategy_known_types(self):
        """Smoke-test that known database types return the correct strategy."""
        from askrita.sqlagent.database.database_strategies import (
            BigQueryStrategy,
            SnowflakeStrategy,
            PostgreSQLStrategy,
            DB2Strategy,
        )
        cases = [
            ("bigquery://project/dataset", BigQueryStrategy),
            ("snowflake://account/db", SnowflakeStrategy),
            ("postgresql://host/db", PostgreSQLStrategy),
            ("postgres://host/db", PostgreSQLStrategy),
            ("mysql://host/db", PostgreSQLStrategy),
            ("sqlite:///test.db", PostgreSQLStrategy),
            ("db2://host/db", DB2Strategy),
            ("ibm_db_sa://host/db", DB2Strategy),
        ]
        for conn_str, expected_cls in cases:
            strategy = self.factory.create_strategy(conn_str)
            assert isinstance(strategy, expected_cls), (
                f"Expected {expected_cls.__name__} for '{conn_str}', "
                f"got {type(strategy).__name__}"
            )
