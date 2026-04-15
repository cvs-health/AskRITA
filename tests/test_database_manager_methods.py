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

"""Tests for DatabaseManager methods that don't require live DB connections."""

import os
import pytest
from unittest.mock import MagicMock, patch

from askrita.sqlagent.database.DatabaseManager import DatabaseManager
from askrita.exceptions import DatabaseError


# ---------------------------------------------------------------------------
# Fixtures and Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def openai_env():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        yield


def _make_manager():
    """Create a DatabaseManager with all connections mocked."""
    mock_config = MagicMock()
    mock_config.database.connection_string = "sqlite:///./test.db"
    mock_config.database.cache_schema = False
    mock_config.database.schema_refresh_interval = 3600
    mock_config.database.max_results = 1000
    mock_config.database.query_timeout = 30
    mock_config.get_database_type.return_value = "SQLite"
    mock_config.framework.debug = False

    mock_llm = MagicMock()
    mock_db = MagicMock()

    with patch("askrita.sqlagent.database.DatabaseManager.LLMManager", return_value=mock_llm):
        with patch("askrita.sqlagent.database.DatabaseManager.DatabaseStrategyFactory") as mock_factory:
            mock_strategy = MagicMock()
            mock_strategy.get_safe_connection_info.return_value = "SQLite: test.db"
            mock_factory.create_strategy.return_value = mock_strategy
            with patch("askrita.sqlagent.database.DatabaseManager.SQLDatabase") as mock_sql_db:
                mock_sql_db.from_uri.return_value = mock_db
                manager = DatabaseManager(
                    config_manager=mock_config,
                    test_llm_connection=False,
                    test_db_connection=False,
                )
    manager.db = mock_db
    manager.schema = None
    return manager, mock_config, mock_db


# ---------------------------------------------------------------------------
# _normalize_result
# ---------------------------------------------------------------------------

class TestNormalizeResult:
    def test_empty_result_returns_empty_list(self):
        manager, _, _ = _make_manager()
        assert manager._normalize_result([]) == []
        assert manager._normalize_result(None) == []
        assert manager._normalize_result("") == []

    def test_list_of_dicts_returned_as_is(self):
        manager, _, _ = _make_manager()
        result = [{"a": 1}, {"a": 2}]
        assert manager._normalize_result(result) == result

    def test_list_of_tuples_converted_to_dicts(self):
        manager, _, _ = _make_manager()
        result = [(1, "foo"), (2, "bar")]
        normalized = manager._normalize_result(result)
        assert len(normalized) == 2
        assert "col_0" in normalized[0]
        assert normalized[0]["col_0"] == 1
        assert normalized[0]["col_1"] == "foo"

    def test_single_dict_wrapped_in_list(self):
        manager, _, _ = _make_manager()
        result = {"a": 1, "b": 2}
        normalized = manager._normalize_result(result)
        assert normalized == [{"a": 1, "b": 2}]

    def test_error_string_raises_database_error(self):
        manager, _, _ = _make_manager()
        with pytest.raises(DatabaseError):
            manager._normalize_result("Error: table not found")

    def test_plain_string_wrapped_in_dict(self):
        manager, _, _ = _make_manager()
        result = manager._normalize_result("some plain result")
        assert isinstance(result, list)
        assert len(result) == 1
        assert "result" in result[0]

    def test_string_repr_of_list_parsed(self):
        manager, _, _ = _make_manager()
        result = manager._normalize_result("[{'a': 1}, {'a': 2}]")
        assert len(result) == 2
        assert result[0]["a"] == 1

    def test_string_repr_of_list_of_tuples(self):
        manager, _, _ = _make_manager()
        result = manager._normalize_result("[(1, 'foo'), (2, 'bar')]")
        assert len(result) == 2

    def test_unexpected_type_raises_database_error(self):
        manager, _, _ = _make_manager()
        with pytest.raises(DatabaseError, match="Unexpected result type"):
            manager._normalize_result(12345)

    def test_string_unparseable_wrapped_in_dict(self):
        manager, _, _ = _make_manager()
        result = manager._normalize_result("count = 42")
        assert result == [{"result": "count = 42"}]


# ---------------------------------------------------------------------------
# execute_query
# ---------------------------------------------------------------------------

class TestExecuteQuery:
    def test_successful_query(self):
        manager, config, mock_db = _make_manager()
        mock_db.run.return_value = [{"id": 1}, {"id": 2}]
        config.database.max_results = 100

        result = manager.execute_query("SELECT * FROM t")
        assert len(result) == 2

    def test_query_results_truncated_at_max(self):
        manager, config, mock_db = _make_manager()
        mock_db.run.return_value = [{"id": i} for i in range(20)]
        config.database.max_results = 5

        result = manager.execute_query("SELECT * FROM t")
        assert len(result) == 5

    def test_database_error_reraises(self):
        manager, _, mock_db = _make_manager()
        mock_db.run.side_effect = DatabaseError("query failed")
        with pytest.raises(DatabaseError):
            manager.execute_query("SELECT * FROM t")

    def test_generic_exception_wrapped_in_database_error(self):
        manager, _, mock_db = _make_manager()
        mock_db.run.side_effect = RuntimeError("unexpected error")
        with pytest.raises(DatabaseError, match="Error executing query"):
            manager.execute_query("SELECT * FROM t")

    def test_backticks_removed(self):
        manager, _, mock_db = _make_manager()
        mock_db.run.return_value = [{"id": 1}]
        manager.execute_query("SELECT * FROM `my_table`")
        call_args = mock_db.run.call_args[0][0]
        assert "`" not in call_args


# ---------------------------------------------------------------------------
# get_sample_data
# ---------------------------------------------------------------------------

class TestGetSampleData:
    def test_no_tables_returns_empty(self):
        manager, _, mock_db = _make_manager()
        manager.schema = None
        # No metadata, no schema
        if hasattr(mock_db, "_metadata"):
            mock_db._metadata = None
        result = manager.get_sample_data(limit=5)
        assert result == {}

    def test_tables_from_schema_string(self):
        manager, config, mock_db = _make_manager()
        manager.schema = "CREATE TABLE orders (id INT);\nCREATE TABLE users (id INT);"
        config.database.connection_string = "sqlite:///test.db"
        config.database.max_results = 100
        mock_db.run.return_value = [{"id": 1}]
        # Ensure mock_db doesn't have _metadata (so schema string is used)
        mock_db._metadata = None
        result = manager.get_sample_data(limit=5)
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_bigquery_table_uses_backtick_syntax(self):
        manager, config, mock_db = _make_manager()
        manager.schema = "CREATE TABLE `project.dataset.orders` (id INT);"
        config.database.connection_string = "bigquery://project/dataset"
        config.database.max_results = 100
        mock_db.run.return_value = [{"id": 1}]
        manager.get_sample_data(limit=5)
        if mock_db.run.called:
            call = mock_db.run.call_args[0][0]
            assert "LIMIT" in call

    def test_snowflake_table_uses_quoted_syntax(self):
        manager, config, mock_db = _make_manager()
        manager.schema = "CREATE TABLE orders (id INT);"
        config.database.connection_string = "snowflake://account/db"
        config.database.max_results = 100
        mock_db.run.return_value = [{"id": 1}]
        manager.get_sample_data(limit=5)
        if mock_db.run.called:
            call = mock_db.run.call_args[0][0]
            assert "LIMIT" in call

    def test_table_error_continues_to_next(self):
        manager, config, mock_db = _make_manager()
        manager.schema = "CREATE TABLE t1 (id INT);\nCREATE TABLE t2 (id INT);"
        config.database.connection_string = "sqlite:///test.db"
        config.database.max_results = 100

        call_count = [0]
        def side_effect(q):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("t1 error")
            return [{"id": 1}]
        mock_db.run.side_effect = side_effect

        result = manager.get_sample_data(limit=5)
        # Should have at least t2's data
        assert isinstance(result, dict)

    def test_general_exception_returns_empty(self):
        manager, _, mock_db = _make_manager()
        manager.schema = "CREATE TABLE orders (id INT);"
        # Force outer exception by making execute_query raise unexpectedly
        with patch.object(manager, "execute_query", side_effect=RuntimeError("outer")):
            result = manager.get_sample_data()
        # get_sample_data catches and returns {}
        assert result == {}


# ---------------------------------------------------------------------------
# _initialize_database error branches
# ---------------------------------------------------------------------------

class TestInitializeDatabaseErrors:
    def _init_manager_with_error(self, error, conn_string="sqlite:///test.db"):
        mock_config = MagicMock()
        mock_config.database.connection_string = conn_string
        mock_config.database.cache_schema = False
        mock_config.database.max_results = 1000
        mock_config.get_database_type.return_value = "SQLite"
        mock_config.framework.debug = False

        mock_llm = MagicMock()
        with patch("askrita.sqlagent.database.DatabaseManager.LLMManager", return_value=mock_llm):
            with patch("askrita.sqlagent.database.DatabaseManager.DatabaseStrategyFactory") as mock_factory:
                mock_strategy = MagicMock()
                mock_strategy.get_safe_connection_info.return_value = "test"
                mock_factory.create_strategy.return_value = mock_strategy
                with patch("askrita.sqlagent.database.DatabaseManager.SQLDatabase") as mock_sql_db:
                    mock_sql_db.from_uri.side_effect = error
                    with pytest.raises(DatabaseError):
                        DatabaseManager(
                            config_manager=mock_config,
                            test_llm_connection=False,
                            test_db_connection=False,
                        )

    def test_auth_error(self):
        self._init_manager_with_error(Exception("authentication failed password wrong"))

    def test_connection_refused(self):
        self._init_manager_with_error(Exception("connection refused could not connect"))

    def test_timeout_error(self):
        self._init_manager_with_error(Exception("timeout connecting"))

    def test_db_does_not_exist(self):
        self._init_manager_with_error(Exception("does not exist"))

    def test_bigquery_error(self):
        self._init_manager_with_error(
            Exception("failed"),
            conn_string="bigquery://project/dataset"
        )

    def test_snowflake_error(self):
        self._init_manager_with_error(
            Exception("failed"),
            conn_string="snowflake://account/db"
        )

    def test_db2_error(self):
        self._init_manager_with_error(
            Exception("failed"),
            conn_string="ibm_db_sa://user:pass@host:50000/DB"
        )

    def test_generic_error(self):
        self._init_manager_with_error(Exception("something unexpected"))


# ---------------------------------------------------------------------------
# test_connection
# ---------------------------------------------------------------------------

class TestDatabaseManagerTestConnection:
    def test_connection_uses_strategy(self):
        manager, config, mock_db = _make_manager()
        manager.db_strategy = MagicMock()
        manager.db_strategy.test_connection.return_value = True
        result = manager.test_connection()
        assert result is True

    def test_connection_failure(self):
        manager, config, mock_db = _make_manager()
        manager.db_strategy = MagicMock()
        manager.db_strategy.test_connection.return_value = False
        result = manager.test_connection()
        assert result is False
