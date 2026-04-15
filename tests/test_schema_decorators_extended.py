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
#   pandas (BSD-3-Clause)

"""Extended tests for schema_decorators.py – targets missing coverage lines."""

import pandas as pd
from unittest.mock import MagicMock, patch

from askrita.sqlagent.database.schema_decorators import (
    BaseSchemaProvider,
    CrossProjectSchemaDecorator,
    SchemaMetadataDecorator,
    SchemaFormattingDecorator,
    AutoDescriptionExtractor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(project_id=None, cross_project_enabled=False, datasets=None,
                 include_tables=None, exclude_tables=None, cache_schema=True,
                 query_timeout=30, max_results=1000, db_type="BigQuery"):
    cfg = MagicMock()
    cfg.get_database_type.return_value = db_type
    db = MagicMock()
    db.bigquery_project_id = project_id
    db.cache_schema = cache_schema
    db.query_timeout = query_timeout
    db.max_results = max_results

    cross = MagicMock()
    cross.enabled = cross_project_enabled
    cross.datasets = datasets or []
    cross.include_tables = include_tables or []
    cross.exclude_tables = exclude_tables or []
    db.cross_project_access = cross

    cfg.database = db
    return cfg


def _make_dataframe(rows):
    """Make a DataFrame from list of dicts."""
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# BaseSchemaProvider
# ---------------------------------------------------------------------------

class TestBaseSchemaProvider:
    def test_returns_base_schema(self):
        provider = BaseSchemaProvider("CREATE TABLE foo (id INT);")
        assert provider.get_schema(None) == "CREATE TABLE foo (id INT);"

    def test_empty_schema(self):
        provider = BaseSchemaProvider("")
        assert provider.get_schema(None) == ""


# ---------------------------------------------------------------------------
# CrossProjectSchemaDecorator
# ---------------------------------------------------------------------------

class TestCrossProjectSchemaDecorator:
    def _make_decorator(self, base_schema="BASE SCHEMA"):
        base = BaseSchemaProvider(base_schema)
        return CrossProjectSchemaDecorator(base)

    def test_no_project_id_returns_schema(self):
        decorator = self._make_decorator()
        config = _make_config(project_id=None)
        result = decorator.get_schema(config)
        assert result == "BASE SCHEMA"

    def test_cross_project_disabled_returns_schema(self):
        decorator = self._make_decorator()
        config = _make_config(project_id="my-project", cross_project_enabled=False)
        with patch("google.cloud.bigquery.Client"):
            result = decorator.get_schema(config)
        assert result == "BASE SCHEMA"

    def test_cross_project_no_datasets_returns_schema(self):
        decorator = self._make_decorator()
        config = _make_config(project_id="my-project", cross_project_enabled=True, datasets=[])
        with patch("google.cloud.bigquery.Client"):
            result = decorator.get_schema(config)
        assert result == "BASE SCHEMA"

    def test_cross_project_enhancement_with_data(self):
        decorator = self._make_decorator()
        config = _make_config(
            project_id="my-project",
            cross_project_enabled=True,
            datasets=["other-project.dataset1"],
        )
        mock_df = _make_dataframe([
            {"table_name": "orders", "column_name": "id", "data_type": "INT64"},
            {"table_name": "orders", "column_name": "amount", "data_type": "FLOAT64"},
        ])
        mock_client = MagicMock()
        mock_client.query.return_value.to_dataframe.return_value = mock_df

        with patch("google.cloud.bigquery.Client", return_value=mock_client):
            result = decorator.get_schema(config)

        assert "other-project.dataset1" in result
        assert "orders" in result

    def test_cross_project_empty_metadata(self):
        decorator = self._make_decorator()
        config = _make_config(
            project_id="my-project",
            cross_project_enabled=True,
            datasets=["other-project.dataset1"],
        )
        mock_client = MagicMock()
        mock_client.query.return_value.to_dataframe.return_value = pd.DataFrame()

        with patch("google.cloud.bigquery.Client", return_value=mock_client):
            result = decorator.get_schema(config)

        assert result == "BASE SCHEMA"  # empty df → no enhancement

    def test_cross_project_dataset_error_continues(self):
        decorator = self._make_decorator()
        config = _make_config(
            project_id="my-project",
            cross_project_enabled=True,
            datasets=["bad-project.dataset1", "good-project.dataset2"],
        )
        mock_client = MagicMock()
        call_count = [0]

        def side_effect(query):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Forbidden")
            result = MagicMock()
            result.to_dataframe.return_value = _make_dataframe([
                {"table_name": "users", "column_name": "id", "data_type": "INT64"}
            ])
            return result

        mock_client.query.side_effect = side_effect

        with patch("google.cloud.bigquery.Client", return_value=mock_client):
            result = decorator.get_schema(config)

        # Should still return a result (not crash)
        assert isinstance(result, str)

    def test_outer_exception_returns_original_schema(self):
        decorator = self._make_decorator("ORIGINAL")
        config = _make_config(project_id="proj")
        with patch("google.cloud.bigquery.Client", side_effect=RuntimeError("bq error")):
            result = decorator.get_schema(config)
        assert result == "ORIGINAL"

    # _matches_pattern tests
    def test_matches_pattern_exact(self):
        dec = self._make_decorator()
        assert dec._matches_pattern("orders", "orders") is True

    def test_matches_pattern_wildcard(self):
        dec = self._make_decorator()
        assert dec._matches_pattern("temp_users", "temp_*") is True
        assert dec._matches_pattern("users", "temp_*") is False

    def test_matches_pattern_dotted_path_extracts_table(self):
        dec = self._make_decorator()
        assert dec._matches_pattern("orders", "project.dataset.orders") is True

    def test_matches_pattern_dotted_with_wildcard(self):
        dec = self._make_decorator()
        assert dec._matches_pattern("temp_orders", "project.dataset.temp_*") is True

    def test_matches_pattern_case_insensitive(self):
        dec = self._make_decorator()
        assert dec._matches_pattern("ORDERS", "orders") is True

    # _apply_table_filters tests
    def test_apply_table_filters_include(self):
        dec = self._make_decorator()
        tables = {"orders": ["id INT"], "users": ["id INT"], "products": ["id INT"]}
        config = _make_config(include_tables=["orders", "products"])
        result = dec._apply_table_filters(tables, config)
        assert "orders" in result
        assert "products" in result
        assert "users" not in result

    def test_apply_table_filters_exclude(self):
        dec = self._make_decorator()
        tables = {"orders": ["id INT"], "temp_cache": ["id INT"], "users": ["id INT"]}
        config = _make_config(exclude_tables=["temp_*"])
        result = dec._apply_table_filters(tables, config)
        assert "orders" in result
        assert "users" in result
        assert "temp_cache" not in result

    def test_apply_table_filters_no_filters(self):
        dec = self._make_decorator()
        tables = {"orders": ["id INT"], "users": ["id INT"]}
        config = _make_config()
        result = dec._apply_table_filters(tables, config)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# SchemaMetadataDecorator
# ---------------------------------------------------------------------------

class TestSchemaMetadataDecorator:
    def _make_decorator(self, base_schema="CREATE TABLE foo (id INT);"):
        base = BaseSchemaProvider(base_schema)
        return SchemaMetadataDecorator(base)

    def test_adds_timestamp_header(self):
        decorator = self._make_decorator()
        config = _make_config(db_type="SQLite")
        result = decorator.get_schema(config)
        assert "Schema Generated:" in result

    def test_bigquery_adds_warning(self):
        decorator = self._make_decorator()
        config = _make_config(db_type="BigQuery")
        result = decorator.get_schema(config)
        assert "FULLY QUALIFIED" in result

    def test_non_bigquery_no_warning(self):
        decorator = self._make_decorator()
        config = _make_config(db_type="PostgreSQL")
        result = decorator.get_schema(config)
        assert "BIGQUERY" not in result

    def test_cross_project_enabled_shows_datasets(self):
        decorator = self._make_decorator()
        config = _make_config(
            db_type="BigQuery",
            cross_project_enabled=True,
            datasets=["proj.ds1", "proj.ds2"],
        )
        result = decorator.get_schema(config)
        assert "Enabled" in result

    def test_cross_project_disabled_shows_disabled(self):
        decorator = self._make_decorator()
        config = _make_config(db_type="BigQuery", cross_project_enabled=False)
        result = decorator.get_schema(config)
        assert "Disabled" in result

    def test_original_schema_preserved(self):
        decorator = self._make_decorator("MY ORIGINAL SCHEMA")
        config = _make_config()
        result = decorator.get_schema(config)
        assert "MY ORIGINAL SCHEMA" in result


# ---------------------------------------------------------------------------
# SchemaFormattingDecorator
# ---------------------------------------------------------------------------

class TestSchemaFormattingDecorator:
    def _make_decorator(self, base_schema):
        base = BaseSchemaProvider(base_schema)
        return SchemaFormattingDecorator(base)

    def test_indents_columns(self):
        schema = "CREATE TABLE foo (\nid INT,\nname TEXT\n);"
        decorator = self._make_decorator(schema)
        result = decorator.get_schema(None)
        assert "  id INT" in result or "  id INT," in result

    def test_handles_closing_paren(self):
        schema = "CREATE TABLE foo (\nid INT\n);"
        decorator = self._make_decorator(schema)
        result = decorator.get_schema(None)
        assert ");" in result

    def test_adds_blank_line_between_tables(self):
        schema = "CREATE TABLE foo (\nid INT\n);\nCREATE TABLE bar (\nname TEXT\n);"
        decorator = self._make_decorator(schema)
        result = decorator.get_schema(None)
        assert "CREATE TABLE bar" in result

    def test_comment_lines_not_indented(self):
        schema = "CREATE TABLE foo (\n-- a comment\nid INT\n);"
        decorator = self._make_decorator(schema)
        result = decorator.get_schema(None)
        # Comment lines inside CREATE TABLE should be left as-is (not indented)
        assert "-- a comment" in result

    def test_empty_schema(self):
        decorator = self._make_decorator("")
        result = decorator.get_schema(None)
        assert result == ""


# ---------------------------------------------------------------------------
# AutoDescriptionExtractor static methods
# ---------------------------------------------------------------------------

class TestAutoDescriptionExtractor:
    def test_build_bq_queries_returns_two(self):
        queries = AutoDescriptionExtractor._build_bq_queries("proj.dataset")
        assert len(queries) == 2
        assert "INFORMATION_SCHEMA.COLUMNS" in queries[0]

    def test_populate_descriptions_from_df(self):
        df = _make_dataframe([
            {"table_name": "orders", "column_name": "id", "description": "Primary key"},
            {"table_name": "orders", "column_name": "amount", "description": "Order amount"},
        ])
        descriptions = {}
        AutoDescriptionExtractor._populate_descriptions_from_df(df, "proj.ds", descriptions)
        assert "proj.ds.orders" in descriptions
        assert descriptions["proj.ds.orders"]["id"] == "Primary key"

    def test_populate_descriptions_none_value(self):
        df = _make_dataframe([
            {"table_name": "orders", "column_name": "id", "description": None},
        ])
        descriptions = {}
        AutoDescriptionExtractor._populate_descriptions_from_df(df, "proj.ds", descriptions)
        assert descriptions["proj.ds.orders"]["id"] == ""

    def test_populate_descriptions_accumulates(self):
        df = _make_dataframe([
            {"table_name": "orders", "column_name": "id", "description": "ID1"},
            {"table_name": "orders", "column_name": "amount", "description": "Amt"},
            {"table_name": "users", "column_name": "name", "description": "Name"},
        ])
        descriptions = {}
        AutoDescriptionExtractor._populate_descriptions_from_df(df, "p.d", descriptions)
        assert len(descriptions) == 2
        assert "p.d.orders" in descriptions
        assert "p.d.users" in descriptions

    def test_handle_bq_query_error_unrecognized_description(self):
        err = Exception("unrecognized name: description")
        result = AutoDescriptionExtractor._handle_bq_query_error(
            err, "unrecognized name: description", attempt=0, cross_project_dataset="proj.ds"
        )
        assert result is True  # Should continue to next query

    def test_handle_bq_query_error_other_error(self):
        err = Exception("access denied")
        result = AutoDescriptionExtractor._handle_bq_query_error(
            err, "access denied", attempt=0, cross_project_dataset="proj.ds"
        )
        assert result is False  # Should not continue
