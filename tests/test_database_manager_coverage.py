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

"""Additional DatabaseManager tests targeting previously uncovered code paths."""

import os
from unittest.mock import MagicMock, call, patch

import pytest

from askrita.exceptions import DatabaseError
from askrita.sqlagent.database.DatabaseManager import DatabaseManager

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def openai_env():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        yield


def _make_manager(conn_string="sqlite:///./test.db"):
    """Create a DatabaseManager with all external dependencies mocked."""
    mock_config = MagicMock()
    mock_config.database.connection_string = conn_string
    mock_config.database.cache_schema = False
    mock_config.database.schema_refresh_interval = 3600
    mock_config.database.max_results = 1000
    mock_config.database.query_timeout = 30
    mock_config.get_database_type.return_value = "SQLite"
    mock_config.framework.debug = False

    mock_llm = MagicMock()
    mock_db = MagicMock()

    with patch(
        "askrita.sqlagent.database.DatabaseManager.LLMManager", return_value=mock_llm
    ):
        with patch(
            "askrita.sqlagent.database.DatabaseManager.DatabaseStrategyFactory"
        ) as mock_factory:
            mock_strategy = MagicMock()
            mock_strategy.get_safe_connection_info.return_value = "SQLite: test.db"
            mock_strategy.test_connection.return_value = True
            mock_factory.create_strategy.return_value = mock_strategy
            with patch(
                "askrita.sqlagent.database.DatabaseManager.SQLDatabase"
            ) as mock_sql_db:
                mock_sql_db.from_uri.return_value = mock_db
                manager = DatabaseManager(
                    config_manager=mock_config,
                    test_llm_connection=False,
                    test_db_connection=False,
                )
    manager.db = mock_db
    manager.schema = None
    manager.db_strategy = mock_strategy
    return manager, mock_config, mock_db, mock_strategy


# ---------------------------------------------------------------------------
# test_db_connection=True branch (lines 78-91)
# ---------------------------------------------------------------------------


class TestInitWithConnectionTest:
    def _create_with_connection_test(
        self, test_connection_return_value, conn_string="sqlite:///test.db"
    ):
        mock_config = MagicMock()
        mock_config.database.connection_string = conn_string
        mock_config.database.cache_schema = False
        mock_config.database.max_results = 1000
        mock_config.get_database_type.return_value = "SQLite"
        mock_config.framework.debug = False

        mock_llm = MagicMock()
        mock_db = MagicMock()

        with patch(
            "askrita.sqlagent.database.DatabaseManager.LLMManager",
            return_value=mock_llm,
        ):
            with patch(
                "askrita.sqlagent.database.DatabaseManager.DatabaseStrategyFactory"
            ) as mock_factory:
                mock_strategy = MagicMock()
                mock_strategy.get_safe_connection_info.return_value = "SQLite: test.db"
                mock_strategy.test_connection.return_value = (
                    test_connection_return_value
                )
                mock_factory.create_strategy.return_value = mock_strategy
                with patch(
                    "askrita.sqlagent.database.DatabaseManager.SQLDatabase"
                ) as mock_sql_db:
                    mock_sql_db.from_uri.return_value = mock_db
                    return DatabaseManager(
                        config_manager=mock_config,
                        test_llm_connection=False,
                        test_db_connection=True,
                    )

    def test_init_passes_when_connection_test_succeeds(self):
        """Lines 78-91: no exception when test_db_connection=True and test_connection succeeds."""
        manager = self._create_with_connection_test(test_connection_return_value=True)
        assert manager is not None

    def test_init_raises_when_connection_test_fails(self):
        """Lines 78-91: DatabaseError raised when test_db_connection=True but connection fails."""
        with pytest.raises(DatabaseError, match="Database connection test failed"):
            self._create_with_connection_test(test_connection_return_value=False)


# ---------------------------------------------------------------------------
# _extract_db_host (line 103)
# ---------------------------------------------------------------------------


class TestExtractDbHost:
    def test_with_at_sign_returns_host_part(self):
        """Line 103: when '@' is in string, return the host portion."""
        result = DatabaseManager._extract_db_host("postgresql://user@myhost:5432/db")
        assert result == "myhost:5432"

    def test_without_at_sign_returns_generic_string(self):
        """Returns 'database host' when '@' is absent (covers the fallback)."""
        result = DatabaseManager._extract_db_host("bigquery://project/dataset")
        assert result == "database host"


# ---------------------------------------------------------------------------
# test_connection exception paths (lines 512-524)
# ---------------------------------------------------------------------------


class TestConnectionExceptionPaths:
    def test_test_connection_returns_false_on_exception(self):
        """Lines 512-524: exception in db_strategy.test_connection returns False."""
        manager, config, mock_db, mock_strategy = _make_manager()
        mock_strategy.test_connection.side_effect = RuntimeError("boom")
        result = manager.test_connection()
        assert result is False

    def test_test_connection_auth_error_hint(self):
        """Lines 517-518: authentication error in test_connection returns False."""
        manager, config, mock_db, mock_strategy = _make_manager()
        mock_strategy.test_connection.side_effect = RuntimeError(
            "authentication failed: access denied"
        )
        result = manager.test_connection()
        assert result is False

    def test_test_connection_connection_refused_hint(self):
        """Lines 519-520: connection refused error hint is logged."""
        manager, config, mock_db, mock_strategy = _make_manager()
        mock_strategy.test_connection.side_effect = RuntimeError("connection refused")
        result = manager.test_connection()
        assert result is False

    def test_test_connection_timeout_hint(self):
        """Lines 521-522: timeout error hint is logged."""
        manager, config, mock_db, mock_strategy = _make_manager()
        mock_strategy.test_connection.side_effect = RuntimeError("timeout connecting")
        result = manager.test_connection()
        assert result is False


# ---------------------------------------------------------------------------
# BigQuery static/instance helper methods (lines 529-602)
# ---------------------------------------------------------------------------


class TestBigQueryHelpers:
    def test_bq_check_dataset_exists_returns_true_on_success(self):
        """Lines 529-536: returns True when client.get_dataset succeeds."""
        mock_client = MagicMock()
        mock_dataset = MagicMock()
        mock_client.get_dataset.return_value = mock_dataset
        mock_client.dataset.return_value = MagicMock()

        result = DatabaseManager._bq_check_dataset_exists(
            mock_client, "my_dataset", "my_project"
        )
        assert result is True

    def test_bq_check_dataset_exists_returns_false_on_404(self):
        """Lines 537-548: returns False on dataset-not-found error (404 code)."""
        mock_client = MagicMock()
        mock_client.dataset.return_value = MagicMock()
        mock_client.get_dataset.side_effect = Exception("404 not found")

        result = DatabaseManager._bq_check_dataset_exists(
            mock_client, "missing_ds", "my_project"
        )
        assert result is False

    def test_bq_check_dataset_exists_returns_false_on_403(self):
        """Lines 537-548: returns False on access denied (403) error."""
        mock_client = MagicMock()
        mock_client.dataset.return_value = MagicMock()
        mock_client.get_dataset.side_effect = Exception("403 access denied")

        result = DatabaseManager._bq_check_dataset_exists(mock_client, "ds", "proj")
        assert result is False

    def test_bq_check_dataset_exists_returns_false_on_auth_error(self):
        """Lines 537-548: authentication error in dataset check."""
        mock_client = MagicMock()
        mock_client.dataset.return_value = MagicMock()
        mock_client.get_dataset.side_effect = Exception("authentication failed")

        result = DatabaseManager._bq_check_dataset_exists(mock_client, "ds", "proj")
        assert result is False

    def test_bq_check_dataset_exists_returns_false_on_permission_error(self):
        """Lines 537-548: permission error in dataset check."""
        mock_client = MagicMock()
        mock_client.dataset.return_value = MagicMock()
        mock_client.get_dataset.side_effect = Exception("insufficient permission")

        result = DatabaseManager._bq_check_dataset_exists(mock_client, "ds", "proj")
        assert result is False

    def test_bq_test_query_execution_returns_true_on_success(self):
        """Lines 552-562: returns True when query returns non-error string."""
        manager, config, mock_db, mock_strategy = _make_manager()
        mock_db.run_no_throw.return_value = "[(1,)]"

        result = manager._bq_test_query_execution()
        assert result is True

    def test_bq_test_query_execution_returns_false_on_error_string(self):
        """Lines 552-562: returns False when result contains 'error'."""
        manager, config, mock_db, mock_strategy = _make_manager()
        mock_db.run_no_throw.return_value = "Error: permission denied"

        result = manager._bq_test_query_execution()
        assert result is False

    def test_bq_test_query_execution_returns_false_on_jobs_permission(self):
        """Lines 552-562: returns False on bigquery.jobs.create permission error."""
        manager, config, mock_db, mock_strategy = _make_manager()
        mock_db.run_no_throw.return_value = (
            "Error: bigquery.jobs.create permission denied"
        )

        result = manager._bq_test_query_execution()
        assert result is False

    def test_bq_test_table_listing_returns_true_on_success(self):
        """Lines 567-580: returns True when tables can be listed."""
        mock_client = MagicMock()
        mock_client.dataset.return_value = MagicMock()
        mock_client.list_tables.return_value = [MagicMock(), MagicMock()]

        result = DatabaseManager._bq_test_table_listing(mock_client, "my_dataset")
        assert result is True

    def test_bq_test_table_listing_returns_false_on_403(self):
        """Lines 567-580: returns False on access-denied error."""
        mock_client = MagicMock()
        mock_client.dataset.return_value = MagicMock()
        mock_client.list_tables.side_effect = Exception("403 access denied")

        result = DatabaseManager._bq_test_table_listing(mock_client, "ds")
        assert result is False

    def test_bq_test_table_listing_returns_false_on_permission_error(self):
        """Lines 567-580: returns False on permission error."""
        mock_client = MagicMock()
        mock_client.dataset.return_value = MagicMock()
        mock_client.list_tables.side_effect = Exception("insufficient permissions")

        result = DatabaseManager._bq_test_table_listing(mock_client, "ds")
        assert result is False

    def test_bq_log_success_non_cross_project(self, caplog):
        """Lines 585-592: log success for standard (non-cross-project) connection."""
        import logging

        with caplog.at_level(logging.INFO):
            DatabaseManager._bq_log_success(False, "my-project", "my-dataset")
        assert "my-project" in caplog.text

    def test_bq_log_success_cross_project(self, caplog):
        """Lines 585-592: log success for cross-project connection."""
        import logging

        with caplog.at_level(logging.INFO):
            DatabaseManager._bq_log_success(True, "my-project", "CROSS_PROJECT_ACCESS")
        assert "cross-project" in caplog.text.lower()

    def test_bq_log_outer_error_authentication(self, caplog):
        """Lines 597-602: authentication error hint is logged."""
        import logging

        with caplog.at_level(logging.ERROR):
            DatabaseManager._bq_log_outer_error("authentication issue")
        assert "authentication" in caplog.text.lower()

    def test_bq_log_outer_error_project(self, caplog):
        """Lines 597-602: project error hint is logged."""
        import logging

        with caplog.at_level(logging.ERROR):
            DatabaseManager._bq_log_outer_error("project not found")
        assert "project" in caplog.text.lower()

    def test_bq_log_outer_error_jobs_create(self, caplog):
        """Lines 597-602: bigquery.jobs.create permission hint is logged."""
        import logging

        with caplog.at_level(logging.ERROR):
            DatabaseManager._bq_log_outer_error(
                "bigquery.jobs.create permission denied"
            )
        assert "bigquery.jobs.create" in caplog.text


# ---------------------------------------------------------------------------
# get_table_names exception path (lines 680-682)
# ---------------------------------------------------------------------------


class TestGetTableNames:
    def test_returns_empty_list_on_toolkit_exception(self):
        """Lines 680-682: exception in SQLDatabaseToolkit returns []."""
        manager, config, mock_db, mock_strategy = _make_manager()

        with patch(
            "askrita.sqlagent.database.DatabaseManager.SQLDatabaseToolkit",
            side_effect=RuntimeError("toolkit failed"),
        ):
            result = manager.get_table_names()
        assert result == []


# ---------------------------------------------------------------------------
# _get_safe_connection_info (line 693)
# ---------------------------------------------------------------------------


class TestGetSafeConnectionInfo:
    def test_bigquery_prefix_replaced(self):
        """Covers BigQuery-specific path in _get_safe_connection_info."""
        manager, _, _, _ = _make_manager()
        result = manager._get_safe_connection_info("bigquery://my-project/dataset")
        assert "BigQuery:" in result

    def test_at_sign_strips_credentials(self):
        """Covers @ path: returns host portion only."""
        manager, _, _, _ = _make_manager()
        result = manager._get_safe_connection_info("postgresql://user@myhost:5432/db")
        assert "myhost" in result
        assert "pass" not in result

    def test_plain_string_returns_configured_database(self):
        """Line 693: returns 'configured database' for plain connection strings."""
        manager, _, _, _ = _make_manager()
        result = manager._get_safe_connection_info("sqlite:///test.db")
        assert result == "configured database"


# ---------------------------------------------------------------------------
# get_connection_info with various connection string formats (lines 729, 731)
# ---------------------------------------------------------------------------


class TestGetConnectionInfo:
    def test_connection_string_with_at_and_port(self):
        """Lines 724-728: parses host and port from connection string with '@'."""
        manager, config, _, _ = _make_manager(
            conn_string="postgresql://user@myhost:5432/mydb"
        )
        config.database.connection_string = "postgresql://user@myhost:5432/mydb"
        info = manager.get_connection_info()
        assert info["host"] == "myhost"
        assert info["port"] == "5432"
        assert info["database_name"] == "mydb"

    def test_connection_string_with_at_but_no_port(self):
        """Line 729: parses host without port when no ':' in host segment."""
        manager, config, _, _ = _make_manager(
            conn_string="postgresql://user@myhost/mydb"
        )
        config.database.connection_string = "postgresql://user@myhost/mydb"
        info = manager.get_connection_info()
        assert info["host"] == "myhost"
        assert info.get("database_name") == "mydb"
        assert "port" not in info

    def test_connection_string_without_at_sign(self):
        """get_connection_info returns basic info when no '@' in string."""
        manager, config, _, _ = _make_manager(conn_string="sqlite:///test.db")
        config.database.connection_string = "sqlite:///test.db"
        info = manager.get_connection_info()
        assert "connection_string" in info
        assert "database_type" in info

    def test_get_schema_raises_database_error_on_exception(self):
        """Lines 329-331: get_schema wraps toolkit exception in DatabaseError."""
        manager, config, _, _ = _make_manager()
        config.database.cache_schema = False
        config.get_schema_cache.return_value = None

        with patch(
            "askrita.sqlagent.database.DatabaseManager.SQLDatabaseToolkit",
            side_effect=RuntimeError("schema fetch failed"),
        ):
            with pytest.raises(DatabaseError, match="Error fetching schema"):
                manager.get_schema()


# ---------------------------------------------------------------------------
# _build_sample_query – BigQuery and Snowflake branches (lines 446, 448)
# ---------------------------------------------------------------------------


class TestBuildSampleQuery:
    def test_bigquery_uses_backtick_syntax(self):
        """Line 446: BigQuery connection strings use backtick-quoted table names."""
        manager, config, _, _ = _make_manager(conn_string="bigquery://project/dataset")
        config.database.connection_string = "bigquery://project/dataset"
        query = manager._build_sample_query("my_table", 50)
        assert query == "SELECT * FROM `my_table` LIMIT 50"

    def test_snowflake_uses_quoted_syntax(self):
        """Line 448: Snowflake connection strings use double-quoted table names."""
        manager, config, _, _ = _make_manager(conn_string="snowflake://account/db")
        config.database.connection_string = "snowflake://account/db"
        query = manager._build_sample_query("my_table", 25)
        assert query == 'SELECT * FROM "my_table" LIMIT 25'

    def test_generic_db_uses_plain_syntax(self):
        """Default: plain SELECT statement for non-BigQuery/Snowflake databases."""
        manager, config, _, _ = _make_manager(conn_string="postgresql://host/db")
        config.database.connection_string = "postgresql://host/db"
        query = manager._build_sample_query("my_table", 10)
        assert query == "SELECT * FROM my_table LIMIT 10"


# ---------------------------------------------------------------------------
# _sample_single_table – exception branch (lines 463-466)
# ---------------------------------------------------------------------------


class TestSampleSingleTable:
    def test_exception_returns_empty_dict(self):
        """Lines 464-466: exception in execute_query returns empty dict."""
        manager, config, mock_db, _ = _make_manager()
        config.database.connection_string = "sqlite:///test.db"
        config.database.max_results = 100
        mock_db.run.side_effect = RuntimeError("query failed")

        result = manager._sample_single_table("orders", 10)
        assert result == {}


# ---------------------------------------------------------------------------
# get_sample_data – outer exception branch (lines 494-496)
# ---------------------------------------------------------------------------


class TestGetSampleDataOuterException:
    def test_outer_exception_returns_empty_dict(self):
        """Lines 494-496: outer exception in get_sample_data returns {}."""
        manager, config, _, _ = _make_manager()
        # Make _discover_table_names itself raise to trigger the outer except
        with patch.object(
            manager, "_discover_table_names", side_effect=RuntimeError("meta boom")
        ):
            result = manager.get_sample_data()
        assert result == {}
