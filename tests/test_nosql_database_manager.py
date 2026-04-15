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

"""Tests for NoSQLDatabaseManager."""

from unittest.mock import Mock, patch

import pytest

from askrita.exceptions import DatabaseError
from askrita.sqlagent.database.NoSQLDatabaseManager import NoSQLDatabaseManager


@pytest.fixture
def mock_config():
    """Create a mock config for MongoDB."""
    config = Mock()
    config.database.connection_string = "mongodb://user:pass@localhost:27017/testdb"
    config.database.cache_schema = False
    config.database.query_timeout = 30
    config.database.max_results = 1000
    config.database.schema_refresh_interval = 3600
    config.get_database_type.return_value = "MongoDB"
    config.get_schema_descriptions = None
    config.pii_detection = Mock()
    config.pii_detection.enabled = False
    return config


@pytest.fixture
def mock_mongodb_database():
    """Create a mock MongoDBDatabase instance."""
    mock_db = Mock()
    mock_db.get_usable_collection_names.return_value = [
        "orders",
        "customers",
        "products",
    ]
    mock_db.get_collection_info.return_value = (
        "Collection: orders\nFields: _id, amount, date"
    )
    mock_db.run.return_value = [{"_id": "1", "amount": 100}]
    mock_db.run_no_throw.return_value = [{"_id": "1", "amount": 100}]
    mock_db._client = Mock()
    mock_db._client.admin.command.return_value = {"ok": 1}
    return mock_db


class TestNoSQLDatabaseManagerInit:
    """Test NoSQLDatabaseManager initialization."""

    @patch("askrita.sqlagent.database.NoSQLDatabaseManager.MongoDBStrategy")
    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_init_with_mongodb_connection_string(
        self, mock_init_db, mock_strategy, mock_config
    ):
        """Test initialization with a MongoDB connection string."""
        mock_strategy_instance = Mock()
        mock_strategy_instance.get_connection_type.return_value = "mongodb"
        mock_strategy_instance.test_connection.return_value = True
        mock_strategy.return_value = mock_strategy_instance

        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        assert manager.config == mock_config
        assert manager.db_strategy is not None

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_init_skips_connection_test(self, mock_init_db, mock_config):
        """Test initialization with test_db_connection=False."""
        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        assert manager is not None

    def test_init_invalid_connection_string(self):
        """Test initialization with unsupported connection string raises error."""
        config = Mock()
        config.database.connection_string = "postgresql://host/db"
        with pytest.raises(DatabaseError, match="Unsupported NoSQL connection string"):
            NoSQLDatabaseManager(config, test_db_connection=False)

    def test_init_empty_connection_string(self):
        """Test initialization with empty connection string raises error."""
        config = Mock()
        config.database.connection_string = ""
        with pytest.raises(
            DatabaseError, match="Connection string must be a non-empty string"
        ):
            NoSQLDatabaseManager(config, test_db_connection=False)

    def test_init_none_connection_string(self):
        """Test initialization with None connection string raises error."""
        config = Mock()
        config.database.connection_string = None
        with pytest.raises(
            DatabaseError, match="Connection string must be a non-empty string"
        ):
            NoSQLDatabaseManager(config, test_db_connection=False)

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_init_atlas_connection_string(self, mock_init_db, mock_config):
        """Test initialization with Atlas SRV connection string."""
        mock_config.database.connection_string = (
            "mongodb+srv://user:pass@cluster.mongodb.net/mydb"
        )
        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        assert manager.db_strategy.get_connection_type() == "mongodb"


class TestNoSQLDatabaseManagerSchema:
    """Test schema retrieval methods."""

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_get_schema(self, mock_init_db, mock_config, mock_mongodb_database):
        """Test get_schema retrieves and enhances schema."""
        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        manager.db = mock_mongodb_database

        schema = manager.get_schema()
        assert "orders" in schema or "Collection" in schema
        mock_mongodb_database.get_usable_collection_names.assert_called_once()
        mock_mongodb_database.get_collection_info.assert_called_once()

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_get_schema_with_cache(
        self, mock_init_db, mock_config, mock_mongodb_database
    ):
        """Test schema caching behavior."""
        mock_config.database.cache_schema = True
        mock_config.get_schema_cache.return_value = "cached schema"

        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        manager.db = mock_mongodb_database

        schema = manager.get_schema()
        assert schema == "cached schema"
        mock_mongodb_database.get_usable_collection_names.assert_not_called()

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_get_schema_cache_miss(
        self, mock_init_db, mock_config, mock_mongodb_database
    ):
        """Test schema retrieval on cache miss."""
        mock_config.database.cache_schema = True
        mock_config.get_schema_cache.return_value = None

        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        manager.db = mock_mongodb_database

        schema = manager.get_schema()
        assert schema is not None
        mock_config.set_schema_cache.assert_called_once()

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_get_schema_error_handling(
        self, mock_init_db, mock_config, mock_mongodb_database
    ):
        """Test schema retrieval error handling."""
        mock_mongodb_database.get_usable_collection_names.side_effect = Exception(
            "Connection lost"
        )

        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        manager.db = mock_mongodb_database

        with pytest.raises(DatabaseError, match="Error fetching schema"):
            manager.get_schema()


class TestNoSQLDatabaseManagerExecuteQuery:
    """Test query execution methods."""

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_execute_query_success(
        self, mock_init_db, mock_config, mock_mongodb_database
    ):
        """Test successful query execution."""
        mock_mongodb_database.run.return_value = [
            {"_id": "1", "name": "Product A", "total": 100},
            {"_id": "2", "name": "Product B", "total": 200},
        ]

        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        manager.db = mock_mongodb_database

        results = manager.execute_query(
            'db.orders.aggregate([{$group: {_id: "$product", total: {$sum: "$amount"}}}])'
        )
        assert len(results) == 2
        assert results[0]["name"] == "Product A"

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_execute_query_strips_code_fences(
        self, mock_init_db, mock_config, mock_mongodb_database
    ):
        """Test that code fences are stripped from queries."""
        mock_mongodb_database.run.return_value = [{"count": 42}]

        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        manager.db = mock_mongodb_database

        results = manager.execute_query(
            "```\ndb.orders.aggregate([{$count: 'total'}])\n```"
        )
        assert len(results) == 1
        assert results[0]["count"] == 42

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_execute_query_respects_max_results(
        self, mock_init_db, mock_config, mock_mongodb_database
    ):
        """Test that results are limited by max_results config."""
        mock_config.database.max_results = 2
        mock_mongodb_database.run.return_value = [
            {"_id": str(i), "val": i} for i in range(10)
        ]

        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        manager.db = mock_mongodb_database

        results = manager.execute_query("db.test.aggregate([])")
        assert len(results) == 2

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_execute_query_error_string_raises(
        self, mock_init_db, mock_config, mock_mongodb_database
    ):
        """Test that error string results raise DatabaseError."""
        mock_mongodb_database.run.return_value = "Error: collection not found"

        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        manager.db = mock_mongodb_database

        with pytest.raises(DatabaseError, match="collection not found"):
            manager.execute_query("db.missing.aggregate([])")

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_execute_query_exception_raises(
        self, mock_init_db, mock_config, mock_mongodb_database
    ):
        """Test that execution exceptions raise DatabaseError."""
        mock_mongodb_database.run.side_effect = Exception("Timeout")

        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        manager.db = mock_mongodb_database

        with pytest.raises(DatabaseError, match="Error executing query"):
            manager.execute_query("db.test.aggregate([])")


class TestNoSQLDatabaseManagerNormalize:
    """Test result normalization."""

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_normalize_empty_result(self, mock_init_db, mock_config):
        """Test normalization of empty results."""
        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        assert manager._normalize_result(None) == []
        assert manager._normalize_result([]) == []
        assert manager._normalize_result("") == []

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_normalize_list_of_dicts(self, mock_init_db, mock_config):
        """Test normalization of list of dictionaries."""
        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        result = manager._normalize_result([{"name": "Alice"}, {"name": "Bob"}])
        assert len(result) == 2
        assert result[0]["name"] == "Alice"

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_normalize_single_dict(self, mock_init_db, mock_config):
        """Test normalization of a single dictionary."""
        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        result = manager._normalize_result({"count": 42})
        assert len(result) == 1
        assert result[0]["count"] == 42

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_normalize_string_json(self, mock_init_db, mock_config):
        """Test normalization of JSON string result."""
        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        result = manager._normalize_result('[{"name": "Alice"}]')
        assert len(result) == 1
        assert result[0]["name"] == "Alice"

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_normalize_string_python_literal(self, mock_init_db, mock_config):
        """Test normalization of Python literal string."""
        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        result = manager._normalize_result("[{'name': 'Alice'}]")
        assert len(result) == 1
        assert result[0]["name"] == "Alice"

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_normalize_unparseable_string(self, mock_init_db, mock_config):
        """Test normalization of unparseable string returns as-is."""
        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        result = manager._normalize_result("some plain text result")
        assert len(result) == 1
        assert result[0]["result"] == "some plain text result"

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_normalize_list_of_tuples(self, mock_init_db, mock_config):
        """Test normalization of list of non-dict items."""
        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        result = manager._normalize_result([("Alice", 100), ("Bob", 200)])
        assert len(result) == 2
        assert result[0]["col_0"] == "Alice"
        assert result[0]["col_1"] == 100


class TestNoSQLDatabaseManagerSerialization:
    """Test document serialization."""

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_serialize_document_with_objectid(self, mock_init_db, mock_config):
        """Test that _id fields are converted to strings."""
        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)

        class FakeObjectId:
            def __str__(self):
                return "507f1f77bcf86cd799439011"

        doc = {"_id": FakeObjectId(), "name": "Test"}
        result = manager._serialize_document(doc)
        assert result["_id"] == "507f1f77bcf86cd799439011"
        assert result["name"] == "Test"

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_serialize_document_nested(self, mock_init_db, mock_config):
        """Test serialization of nested documents."""
        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        doc = {"_id": "1", "address": {"city": "NYC", "zip": "10001"}}
        result = manager._serialize_document(doc)
        assert result["address"]["city"] == "NYC"

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_serialize_document_with_list(self, mock_init_db, mock_config):
        """Test serialization of documents with list fields."""
        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        doc = {"_id": "1", "tags": ["a", "b"], "items": [{"name": "x"}]}
        result = manager._serialize_document(doc)
        assert result["tags"] == ["a", "b"]
        assert result["items"][0]["name"] == "x"

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_serialize_value_none(self, mock_init_db, mock_config):
        """Test serialization of None values."""
        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        assert manager._serialize_value(None) is None

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_serialize_value_regular_types(self, mock_init_db, mock_config):
        """Test serialization of regular Python types."""
        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        assert manager._serialize_value(42) == 42
        assert manager._serialize_value("hello") == "hello"
        assert manager._serialize_value(3.14) == 3.14
        assert manager._serialize_value(True) is True


class TestNoSQLDatabaseManagerCollections:
    """Test collection-related methods."""

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_get_collection_names(
        self, mock_init_db, mock_config, mock_mongodb_database
    ):
        """Test getting collection names."""
        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        manager.db = mock_mongodb_database

        names = manager.get_collection_names()
        assert "customers" in names
        assert "orders" in names
        assert names == sorted(names)

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_get_collection_names_error(
        self, mock_init_db, mock_config, mock_mongodb_database
    ):
        """Test collection names error handling."""
        mock_mongodb_database.get_usable_collection_names.side_effect = Exception(
            "Error"
        )

        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        manager.db = mock_mongodb_database

        names = manager.get_collection_names()
        assert names == []

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_get_connection_info(self, mock_init_db, mock_config):
        """Test connection info retrieval."""
        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)

        info = manager.get_connection_info()
        assert info["database_type"] == "MongoDB"
        assert info["cache_enabled"] is False
        assert info["query_timeout"] == 30
        assert info["max_results"] == 1000

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_test_connection_success(self, mock_init_db, mock_config):
        """Test successful connection test."""
        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        manager._client = Mock()
        manager._client.admin.command.return_value = {"ok": 1}

        assert manager.test_connection() is True

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_test_connection_failure(self, mock_init_db, mock_config):
        """Test failed connection test."""
        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        manager._client = Mock()
        manager._client.admin.command.side_effect = Exception("Connection refused")

        assert manager.test_connection() is False


class TestFixMongoJsKeys:
    """Test JavaScript-to-Python key conversion for MongoDB commands."""

    def test_quotes_bare_dollar_keys(self):
        """Test that bare $-prefixed keys get quoted."""
        cmd = "db.accounts.aggregate([{$count: 'total'}])"
        result = NoSQLDatabaseManager._fix_mongo_js_keys(cmd)
        assert '"$count"' in result

    def test_quotes_bare_regular_keys(self):
        """Test that bare regular keys get quoted."""
        cmd = "db.accounts.aggregate([{$group: {_id: '$field', count: {$sum: 1}}}])"
        result = NoSQLDatabaseManager._fix_mongo_js_keys(cmd)
        assert '"$group"' in result
        assert '"_id"' in result
        assert '"count"' in result
        assert '"$sum"' in result

    def test_preserves_already_quoted_keys(self):
        """Test that already-quoted keys are not double-quoted."""
        cmd = 'db.orders.aggregate([{"$match": {"status": "active"}}])'
        result = NoSQLDatabaseManager._fix_mongo_js_keys(cmd)
        assert result == cmd

    def test_converts_js_true_false_null(self):
        """Test that JavaScript true/false/null are converted to Python equivalents."""
        cmd = "db.customers.aggregate([{$match: {active: true}}, {$group: {_id: null, count: {$sum: 1}}}])"
        result = NoSQLDatabaseManager._fix_mongo_js_keys(cmd)
        assert "True" in result
        assert "None" in result
        assert " true" not in result
        assert " null" not in result

    def test_preserves_true_false_inside_strings(self):
        """Test that true/false inside quoted strings are NOT converted."""
        cmd = """db.orders.aggregate([{"$match": {"status": "true"}}])"""
        result = NoSQLDatabaseManager._fix_mongo_js_keys(cmd)
        assert '"true"' in result

    def test_no_aggregate_returns_unchanged(self):
        """Test that commands without .aggregate() are returned unchanged."""
        cmd = "db.orders.find({status: 'active'})"
        result = NoSQLDatabaseManager._fix_mongo_js_keys(cmd)
        assert result == cmd

    def test_complex_pipeline(self):
        """Test a complex aggregation pipeline with mixed quoting."""
        cmd = (
            "db.accounts.aggregate(["
            "{$unwind: '$products'},"
            "{$group: {_id: '$products', count: {$sum: 1}}},"
            "{$sort: {count: -1}}"
            "])"
        )
        result = NoSQLDatabaseManager._fix_mongo_js_keys(cmd)
        assert '"$unwind"' in result
        assert '"$group"' in result
        assert '"$sort"' in result
        assert '"count"' in result

    def test_boolean_in_match(self):
        """Test boolean conversion in $match with $in operator."""
        cmd = 'db.customers.aggregate([{"$match": {"active": {"$in": [true, false]}}}])'
        result = NoSQLDatabaseManager._fix_mongo_js_keys(cmd)
        assert "True" in result
        assert "False" in result


class TestNoSQLDatabaseManagerSampleData:
    """Test sample data retrieval."""

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_get_sample_data(self, mock_init_db, mock_config, mock_mongodb_database):
        """Test sample data retrieval from collections."""
        mock_mongodb_database.run_no_throw.return_value = [{"_id": "1", "name": "Test"}]

        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        manager.db = mock_mongodb_database

        sample = manager.get_sample_data(limit=10)
        assert isinstance(sample, dict)
        assert len(sample) > 0

    @patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
    )
    def test_get_sample_data_error_returns_empty(
        self, mock_init_db, mock_config, mock_mongodb_database
    ):
        """Test sample data returns empty dict on error."""
        mock_mongodb_database.get_usable_collection_names.side_effect = Exception(
            "Error"
        )

        manager = NoSQLDatabaseManager(mock_config, test_db_connection=False)
        manager.db = mock_mongodb_database

        sample = manager.get_sample_data()
        assert sample == {}
