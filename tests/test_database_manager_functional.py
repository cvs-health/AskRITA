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

"""Functional tests for DatabaseManager with mocked dependencies."""

import pytest
import os
from unittest.mock import Mock, patch
from askrita.exceptions import DatabaseError


def _make_mock_config(conn_str: str = "postgresql://user:pass@localhost:5432/mydb", cache=False, max_results=100):
    cfg = Mock()
    cfg.get_database_type.return_value = "PostgreSQL"
    db = Mock()
    db.connection_string = conn_str
    db.cache_schema = cache
    db.max_results = max_results
    db.query_timeout = 30
    cfg.database = db
    # LLM config
    llm = Mock()
    llm.provider = "openai"
    llm.model = "gpt-4o"
    llm.temperature = 0.1
    llm.max_tokens = 4000
    llm.top_p = 1.0
    llm.frequency_penalty = 0.0
    llm.presence_penalty = 0.0
    llm.organization = None
    llm.base_url = None
    llm.ca_bundle_path = None
    llm.azure_endpoint = None
    llm.azure_deployment = None
    cfg.llm = llm
    # Optional cross-project for bigquery tests
    cross = Mock()
    cross.enabled = False
    cfg.database.cross_project_access = cross
    # Schema cache fns
    cfg.get_schema_cache.return_value = None
    return cfg


@patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-12345'})
def test_init_skips_connection_test():
    with patch('langchain_community.utilities.sql_database.SQLDatabase.from_uri') as mock_from_uri, \
         patch('askrita.sqlagent.database.DatabaseManager.DatabaseStrategyFactory') as mock_factory, \
         patch('askrita.utils.LLMManager.LLMManager', create=True) as mock_llm:

        mock_llm.return_value = Mock(llm=Mock())
        mock_factory.create_strategy.return_value = Mock(
            setup_auth=Mock(),
            get_safe_connection_info=lambda s: s,
            enhance_schema=lambda s, c: s,
            test_connection=Mock(return_value=True)
        )
        mock_from_uri.return_value = Mock()

        from askrita.sqlagent.database.DatabaseManager import DatabaseManager
        cfg = _make_mock_config()
        mgr = DatabaseManager(cfg, test_llm_connection=False, test_db_connection=False)

        assert mgr.db is not None
        assert mgr.db_strategy is not None
        assert mgr.llm_manager is not None


@patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-12345'})
def test_get_schema_basic():
    with patch('askrita.sqlagent.database.DatabaseManager.SQLDatabaseToolkit') as mock_toolkit_cls, \
         patch('langchain_community.utilities.sql_database.SQLDatabase.from_uri') as mock_from_uri, \
         patch('askrita.sqlagent.database.DatabaseManager.DatabaseStrategyFactory') as mock_factory, \
         patch('askrita.utils.LLMManager.LLMManager', create=True) as mock_llm:

        mock_llm.return_value = Mock(llm=Mock())
        strategy = Mock()
        strategy.get_safe_connection_info = Mock(return_value="safe_info")
        strategy.setup_auth = Mock()
        strategy.enhance_schema = Mock(side_effect=lambda schema, cfg: schema + "-enhanced")
        mock_factory.create_strategy.return_value = strategy
        mock_from_uri.return_value = Mock()

        # Mock toolkit tools
        schema_tool = Mock()
        schema_tool.name = "sql_db_schema"
        schema_tool.invoke.return_value = "RAW_SCHEMA"
        list_tool = Mock()
        list_tool.name = "sql_db_list_tables"
        list_tool.invoke.return_value = "users,orders"

        mock_toolkit = Mock()
        mock_toolkit.get_tools.return_value = [schema_tool, list_tool]
        mock_toolkit_cls.return_value = mock_toolkit

        from askrita.sqlagent.database.DatabaseManager import DatabaseManager
        cfg = _make_mock_config()
        mgr = DatabaseManager(cfg, test_llm_connection=False, test_db_connection=False)

        result = mgr.get_schema()
        assert result.endswith("-enhanced")


@patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-12345'})
def test_get_schema_with_cache():
    with patch('langchain_community.utilities.sql_database.SQLDatabase.from_uri') as mock_from_uri, \
         patch('askrita.sqlagent.database.DatabaseManager.DatabaseStrategyFactory') as mock_factory, \
         patch('askrita.utils.LLMManager.LLMManager', create=True) as mock_llm:

        mock_llm.return_value = Mock(llm=Mock())
        mock_factory.create_strategy.return_value = Mock(
            setup_auth=Mock(),
            get_safe_connection_info=lambda s: s,
            enhance_schema=lambda s, c: s
        )
        mock_from_uri.return_value = Mock()

        from askrita.sqlagent.database.DatabaseManager import DatabaseManager
        cfg = _make_mock_config(cache=True)
        cfg.get_schema_cache.return_value = "CACHED"

        mgr = DatabaseManager(cfg, test_llm_connection=False, test_db_connection=False)
        result = mgr.get_schema()
        assert result == "CACHED"


@patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-12345'})
def test_get_schema_sets_cache_when_enabled():
    with patch('askrita.sqlagent.database.DatabaseManager.SQLDatabaseToolkit') as mock_toolkit_cls, \
         patch('langchain_community.utilities.sql_database.SQLDatabase.from_uri') as mock_from_uri, \
         patch('askrita.sqlagent.database.DatabaseManager.DatabaseStrategyFactory') as mock_factory, \
         patch('askrita.utils.LLMManager.LLMManager', create=True) as mock_llm:

        mock_llm.return_value = Mock(llm=Mock())
        strategy = Mock()
        strategy.get_safe_connection_info = lambda s: s
        strategy.setup_auth = Mock()
        strategy.enhance_schema = lambda schema, cfg: schema
        mock_factory.create_strategy.return_value = strategy
        mock_from_uri.return_value = Mock()

        schema_tool = Mock(); schema_tool.name = "sql_db_schema"; schema_tool.invoke.return_value = "RAW"
        list_tool = Mock(); list_tool.name = "sql_db_list_tables"; list_tool.invoke.return_value = "users"

        mock_toolkit = Mock()
        mock_toolkit.get_tools.return_value = [schema_tool, list_tool]
        mock_toolkit_cls.return_value = mock_toolkit

        from askrita.sqlagent.database.DatabaseManager import DatabaseManager
        cfg = _make_mock_config(cache=True)
        cfg.get_schema_cache.return_value = None

        mgr = DatabaseManager(cfg, test_llm_connection=False, test_db_connection=False)
        _ = mgr.get_schema()
        cfg.set_schema_cache.assert_called_with("RAW")


def test_normalize_result_variants():
    from askrita.sqlagent.database.DatabaseManager import DatabaseManager
    mgr = object.__new__(DatabaseManager)

    # Empty
    assert DatabaseManager._normalize_result(mgr, None) == []

    # List of dicts
    res = DatabaseManager._normalize_result(mgr, [{"a": 1}])
    assert res == [{"a": 1}]

    # List of tuples
    res = DatabaseManager._normalize_result(mgr, [(1, 2)])
    assert isinstance(res[0], dict)

    # Dict
    res = DatabaseManager._normalize_result(mgr, {"k": "v"})
    assert res == [{"k": "v"}]

    # Error string
    with pytest.raises(DatabaseError):
        DatabaseManager._normalize_result(mgr, "Error: boom")

    # String literal
    res = DatabaseManager._normalize_result(mgr, "{'x': 1}")
    assert res == [{"x": 1}]

    # Plain non-literal string (should be wrapped)
    res = DatabaseManager._normalize_result(mgr, "count=42")
    assert res == [{"result": "count=42"}]

    # Unexpected type
    with pytest.raises(DatabaseError):
        DatabaseManager._normalize_result(mgr, 123)


@patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-12345'})
def test_execute_query_success_and_limit():
    with patch('langchain_community.utilities.sql_database.SQLDatabase.from_uri') as mock_from_uri, \
         patch('askrita.sqlagent.database.DatabaseManager.DatabaseStrategyFactory') as mock_factory, \
         patch('askrita.utils.LLMManager.LLMManager', create=True) as mock_llm:

        mock_llm.return_value = Mock(llm=Mock())
        mock_factory.create_strategy.return_value = Mock(
            setup_auth=Mock(),
            get_safe_connection_info=lambda s: s,
            enhance_schema=lambda s, c: s
        )
        mock_db = Mock()
        mock_db.run.return_value = [{"a": 1}, {"a": 2}, {"a": 3}]
        mock_from_uri.return_value = mock_db

        from askrita.sqlagent.database.DatabaseManager import DatabaseManager
        cfg = _make_mock_config(max_results=2)

        mgr = DatabaseManager(cfg, test_llm_connection=False, test_db_connection=False)
        out = mgr.execute_query("SELECT * FROM `t`")
        assert out == [{"a": 1}, {"a": 2}]
        mock_db.run.assert_called()
        assert "`" not in mock_db.run.call_args[0][0]


@patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-12345'})
def test_execute_query_error_string_raises():
    with patch('langchain_community.utilities.sql_database.SQLDatabase.from_uri') as mock_from_uri, \
         patch('askrita.sqlagent.database.DatabaseManager.DatabaseStrategyFactory') as mock_factory, \
         patch('askrita.utils.LLMManager.LLMManager', create=True) as mock_llm:

        mock_llm.return_value = Mock(llm=Mock())
        mock_factory.create_strategy.return_value = Mock(
            setup_auth=Mock(),
            get_safe_connection_info=lambda s: s,
            enhance_schema=lambda s, c: s
        )
        mock_db = Mock()
        mock_db.run.return_value = "Error: failed"
        mock_from_uri.return_value = mock_db

        from askrita.sqlagent.database.DatabaseManager import DatabaseManager
        cfg = _make_mock_config()

        mgr = DatabaseManager(cfg, test_llm_connection=False, test_db_connection=False)
        with pytest.raises(DatabaseError):
            mgr.execute_query("select 1")


@patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-12345'})
def test_test_connection_true_false():
    with patch('langchain_community.utilities.sql_database.SQLDatabase.from_uri') as mock_from_uri, \
         patch('askrita.sqlagent.database.DatabaseManager.DatabaseStrategyFactory') as mock_factory, \
         patch('askrita.utils.LLMManager.LLMManager', create=True) as mock_llm:

        mock_llm.return_value = Mock(llm=Mock())

        strat = Mock()
        strat.test_connection = Mock(side_effect=[True, False])
        strat.get_safe_connection_info = Mock(return_value="safe_info")
        strat.setup_auth = Mock()
        mock_factory.create_strategy = Mock(return_value=strat)
        mock_from_uri.return_value = Mock()

        from askrita.sqlagent.database.DatabaseManager import DatabaseManager
        cfg = _make_mock_config()

        mgr = DatabaseManager(cfg, test_llm_connection=False, test_db_connection=False)
        assert mgr.test_connection() is True
        assert mgr.test_connection() is False


@patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-12345'})
def test_get_table_names_success_and_exception():
    with patch('askrita.sqlagent.database.DatabaseManager.SQLDatabaseToolkit') as mock_toolkit_cls, \
         patch('langchain_community.utilities.sql_database.SQLDatabase.from_uri') as mock_from_uri, \
         patch('askrita.sqlagent.database.DatabaseManager.DatabaseStrategyFactory') as mock_factory, \
         patch('askrita.utils.LLMManager.LLMManager', create=True) as mock_llm:

        mock_llm.return_value = Mock(llm=Mock())
        mock_factory.create_strategy.return_value = Mock(
            setup_auth=Mock(), get_safe_connection_info=lambda s: s, enhance_schema=lambda s, c: s
        )
        mock_from_uri.return_value = Mock()

        # Success path
        schema_tool = Mock(); schema_tool.name = "sql_db_schema"; schema_tool.invoke.return_value = "RAW"
        list_tool = Mock(); list_tool.name = "sql_db_list_tables"; list_tool.invoke.return_value = "a,b,c"

        mock_toolkit = Mock()
        mock_toolkit.get_tools.return_value = [schema_tool, list_tool]
        mock_toolkit_cls.return_value = mock_toolkit

        from askrita.sqlagent.database.DatabaseManager import DatabaseManager
        cfg = _make_mock_config()
        mgr = DatabaseManager(cfg, test_llm_connection=False, test_db_connection=False)

        names = mgr.get_table_names()
        assert names == ["a", "b", "c"]


def test_get_connection_info_and_safe_info():
    from askrita.sqlagent.database.DatabaseManager import DatabaseManager
    mgr = object.__new__(DatabaseManager)
    cfg = _make_mock_config("postgresql://user:pass@host:5433/mydb")
    mgr.config = cfg

    info = DatabaseManager.get_connection_info(mgr)
    assert info["database_type"] == "PostgreSQL"
    assert info["host"] == "host"
    assert info["port"] == "5433"
    assert info["database_name"] == "mydb"

    safe = DatabaseManager._get_safe_connection_info(mgr, "bigquery://proj/ds")
    assert safe.startswith("BigQuery:")
