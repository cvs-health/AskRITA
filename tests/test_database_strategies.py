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

"""Tests for database_strategies.py – targets missing coverage lines."""

import os
from unittest.mock import MagicMock, patch

import pytest

from askrita.exceptions import DatabaseError
from askrita.sqlagent.database.database_strategies import (
    BigQueryStrategy,
    DB2Strategy,
    PostgreSQLStrategy,
    SnowflakeStrategy,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(credentials_path=None):
    config = MagicMock()
    config.database.bigquery_credentials_path = credentials_path
    cross = MagicMock()
    cross.enabled = False
    cross.datasets = []
    cross.include_tables = []
    cross.exclude_tables = []
    config.database.cross_project_access = cross
    desc = MagicMock()
    desc.automatic_extraction.enabled = False
    desc.columns = {}
    desc.project_context = None
    config.get_schema_descriptions.return_value = desc
    return config


def _make_db(run_result="[(1,)]"):
    db = MagicMock()
    db.run_no_throw.return_value = run_result
    return db


# ---------------------------------------------------------------------------
# BigQueryStrategy
# ---------------------------------------------------------------------------


class TestBigQueryStrategy:
    def test_get_connection_type(self):
        assert BigQueryStrategy().get_connection_type() == "bigquery"

    def test_setup_auth_with_valid_credentials(self, tmp_path):
        cred_file = tmp_path / "creds.json"
        cred_file.write_text("{}")
        config = _make_config(credentials_path=str(cred_file))

        with patch(
            "askrita.sqlagent.database.database_strategies.default"
        ) as mock_default:
            mock_default.return_value = (MagicMock(), "my-project")
            BigQueryStrategy().setup_auth(config)
            assert os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") == str(cred_file)

    def test_setup_auth_missing_credentials_path_falls_back_to_adc(self):
        config = _make_config(credentials_path="/nonexistent/creds.json")
        with patch(
            "askrita.sqlagent.database.database_strategies.default"
        ) as mock_default:
            mock_default.return_value = (MagicMock(), "proj")
            BigQueryStrategy().setup_auth(config)  # Should not raise

    def test_setup_auth_no_credentials_uses_adc(self):
        config = _make_config(credentials_path=None)
        with patch(
            "askrita.sqlagent.database.database_strategies.default"
        ) as mock_default:
            mock_default.return_value = (MagicMock(), "proj")
            BigQueryStrategy().setup_auth(config)

    def test_setup_auth_adc_fails_raises_database_error(self):
        config = _make_config(credentials_path=None)
        with patch(
            "askrita.sqlagent.database.database_strategies.default",
            side_effect=Exception("auth failed"),
        ):
            with pytest.raises(DatabaseError, match="BigQuery authentication failed"):
                BigQueryStrategy().setup_auth(config)

    def test_setup_auth_outer_exception_raises_database_error(self):
        config = MagicMock()
        config.database = None  # Will cause AttributeError
        with pytest.raises(DatabaseError):
            BigQueryStrategy().setup_auth(config)

    def test_test_connection_success(self):
        db = _make_db()
        config = _make_config()
        with patch(
            "askrita.sqlagent.database.database_strategies.BigQueryValidationChain"
        ) as mock_chain:
            mock_chain.return_value.validate.return_value = True
            result = BigQueryStrategy().test_connection(db, config)
        assert result is True

    def test_test_connection_failure(self):
        db = _make_db()
        config = _make_config()
        with patch(
            "askrita.sqlagent.database.database_strategies.BigQueryValidationChain"
        ) as mock_chain:
            mock_chain.return_value.validate.return_value = False
            result = BigQueryStrategy().test_connection(db, config)
        assert result is False

    def test_test_connection_exception_returns_false(self):
        db = _make_db()
        config = _make_config()
        with patch(
            "askrita.sqlagent.database.database_strategies.BigQueryValidationChain",
            side_effect=RuntimeError("bq error"),
        ):
            result = BigQueryStrategy().test_connection(db, config)
        assert result is False

    def test_test_connection_auth_error_logged(self):
        db = _make_db()
        config = _make_config()
        with patch(
            "askrita.sqlagent.database.database_strategies.BigQueryValidationChain",
            side_effect=Exception("authentication access denied"),
        ):
            result = BigQueryStrategy().test_connection(db, config)
        assert result is False

    def test_test_connection_project_error_logged(self):
        db = _make_db()
        config = _make_config()
        with patch(
            "askrita.sqlagent.database.database_strategies.BigQueryValidationChain",
            side_effect=Exception("project not found"),
        ):
            result = BigQueryStrategy().test_connection(db, config)
        assert result is False

    def test_test_connection_jobs_create_error_logged(self):
        db = _make_db()
        config = _make_config()
        with patch(
            "askrita.sqlagent.database.database_strategies.BigQueryValidationChain",
            side_effect=Exception("bigquery.jobs.create permission denied"),
        ):
            result = BigQueryStrategy().test_connection(db, config)
        assert result is False

    def test_enhance_schema_basic(self):
        config = _make_config()
        config.database.bigquery_project_id = "my-project"
        strategy = BigQueryStrategy()
        result = strategy.enhance_schema("CREATE TABLE foo (id INT);", config)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_enhance_schema_exception_returns_original(self):
        config = MagicMock()
        config.get_schema_descriptions.side_effect = RuntimeError("error")
        strategy = BigQueryStrategy()
        result = strategy.enhance_schema("ORIGINAL SCHEMA", config)
        assert result == "ORIGINAL SCHEMA"

    def test_get_safe_connection_info(self):
        result = BigQueryStrategy().get_safe_connection_info(
            "bigquery://project/dataset"
        )
        assert "bigquery://" not in result


# ---------------------------------------------------------------------------
# SnowflakeStrategy
# ---------------------------------------------------------------------------


class TestSnowflakeStrategy:
    def test_get_connection_type(self):
        assert SnowflakeStrategy().get_connection_type() == "snowflake"

    def test_setup_auth_no_crash(self):
        config = _make_config()
        SnowflakeStrategy().setup_auth(config)  # Should not raise

    def test_test_connection_success(self):
        db = _make_db("[(1,)]")
        config = _make_config()
        result = SnowflakeStrategy().test_connection(db, config)
        assert result is True

    def test_test_connection_error_string(self):
        db = _make_db("error: connection refused")
        config = _make_config()
        result = SnowflakeStrategy().test_connection(db, config)
        assert result is False

    def test_test_connection_exception_string(self):
        db = _make_db("exception: timeout")
        config = _make_config()
        result = SnowflakeStrategy().test_connection(db, config)
        assert result is False

    def test_test_connection_exception(self):
        db = MagicMock()
        db.run_no_throw.side_effect = RuntimeError("db crash")
        config = _make_config()
        result = SnowflakeStrategy().test_connection(db, config)
        assert result is False

    def test_enhance_schema_returns_original(self):
        result = SnowflakeStrategy().enhance_schema("SCHEMA", None)
        assert result == "SCHEMA"

    def test_get_safe_connection_info(self):
        result = SnowflakeStrategy().get_safe_connection_info(
            "snowflake://user:pass@account/db"
        )
        assert "snowflake://" not in result


# ---------------------------------------------------------------------------
# PostgreSQLStrategy
# ---------------------------------------------------------------------------


class TestPostgreSQLStrategy:
    def test_get_connection_type(self):
        assert PostgreSQLStrategy().get_connection_type() == "postgresql"

    def test_setup_auth_no_crash(self):
        PostgreSQLStrategy().setup_auth(_make_config())

    def test_test_connection_success(self):
        db = _make_db("[(1,)]")
        result = PostgreSQLStrategy().test_connection(db, _make_config())
        assert result is True

    def test_test_connection_error_string(self):
        db = _make_db("error: connection refused")
        result = PostgreSQLStrategy().test_connection(db, _make_config())
        assert result is False

    def test_test_connection_exception(self):
        db = MagicMock()
        db.run_no_throw.side_effect = RuntimeError("crash")
        result = PostgreSQLStrategy().test_connection(db, _make_config())
        assert result is False

    def test_enhance_schema_returns_original(self):
        result = PostgreSQLStrategy().enhance_schema("SCHEMA", None)
        assert result == "SCHEMA"

    def test_get_safe_connection_info_with_at(self):
        result = PostgreSQLStrategy().get_safe_connection_info(
            "postgresql://user:pass@host:5432/db"
        )
        assert "user" not in result
        assert "pass" not in result

    def test_get_safe_connection_info_without_at(self):
        result = PostgreSQLStrategy().get_safe_connection_info(
            "postgresql://host:5432/db"
        )
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# DB2Strategy
# ---------------------------------------------------------------------------


class TestDB2Strategy:
    def test_get_connection_type(self):
        assert DB2Strategy().get_connection_type() == "db2"

    def test_setup_auth_no_crash(self):
        DB2Strategy().setup_auth(_make_config())

    def test_test_connection_success(self):
        db = _make_db("[(1,)]")
        result = DB2Strategy().test_connection(db, _make_config())
        assert result is True

    def test_test_connection_error_string(self):
        db = _make_db("error: connection failed")
        result = DB2Strategy().test_connection(db, _make_config())
        assert result is False

    def test_test_connection_exception_string(self):
        db = _make_db("exception: timeout")
        result = DB2Strategy().test_connection(db, _make_config())
        assert result is False

    def test_test_connection_exception(self):
        db = MagicMock()
        db.run_no_throw.side_effect = RuntimeError("db2 crash")
        result = DB2Strategy().test_connection(db, _make_config())
        assert result is False

    def test_enhance_schema_returns_original(self):
        result = DB2Strategy().enhance_schema("SCHEMA", None)
        assert result == "SCHEMA"

    def test_get_safe_connection_info_db2_prefix(self):
        result = DB2Strategy().get_safe_connection_info(
            "db2://user:pass@host:50000/SAMPLE"
        )
        assert "user" not in result
        assert "pass" not in result
        assert "host:50000/SAMPLE" in result

    def test_get_safe_connection_info_ibm_db_sa_prefix(self):
        result = DB2Strategy().get_safe_connection_info(
            "ibm_db_sa://user:pass@host:50000/DB"
        )
        assert "user" not in result
        assert "host:50000/DB" in result

    def test_get_safe_connection_info_unknown_prefix(self):
        result = DB2Strategy().get_safe_connection_info("jdbc://host/db")
        assert "DB2:" in result

    def test_get_safe_connection_info_no_at_sign(self):
        result = DB2Strategy().get_safe_connection_info("db2://host:50000/DB")
        assert isinstance(result, str)
        assert "DB2:" in result

    def test_get_safe_connection_info_exception_handled(self):
        # Should not raise even for weird inputs
        result = DB2Strategy().get_safe_connection_info(None)
        assert isinstance(result, str)
