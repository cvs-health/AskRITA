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

"""Comprehensive tests for schema decorators - targeting 12% -> 60%+."""

from unittest.mock import Mock, patch
from askrita.sqlagent.database.schema_decorators import (
    BaseSchemaProvider,
    SchemaDecoratorBuilder,
    CrossProjectSchemaDecorator,
    SchemaMetadataDecorator,
    HybridDescriptionDecorator,
    AutoDescriptionExtractor,
    DescriptionMerger,
)


class TestBaseSchemaProvider:
    """Test BaseSchemaProvider."""

    def test_init_and_get_schema(self):
        """Test BaseSchemaProvider initialization and get_schema."""
        schema = "CREATE TABLE test (id INT)"
        provider = BaseSchemaProvider(schema)

        mock_config = Mock()
        result = provider.get_schema(mock_config)
        assert result == schema


class TestSchemaDecoratorBuilder:
    """Test SchemaDecoratorBuilder - core functionality."""

    def test_init(self):
        """Test builder initialization."""
        schema = "CREATE TABLE test (id INT)"
        builder = SchemaDecoratorBuilder(schema)
        provider = builder.build()
        assert provider.get_schema(Mock()) == schema

    def test_build_empty(self):
        """Test building with no decorators."""
        schema = "CREATE TABLE test (id INT)"
        builder = SchemaDecoratorBuilder(schema)
        result = builder.build()

        mock_config = Mock()
        schema_result = result.get_schema(mock_config)
        assert isinstance(schema_result, str)

    def test_with_cross_project_enhancement(self):
        """Test adding cross project enhancement."""
        schema = "CREATE TABLE test (id INT)"
        builder = SchemaDecoratorBuilder(schema)

        result_builder = builder.with_cross_project_enhancement()
        assert result_builder is builder  # Should return self for chaining

    def test_with_hybrid_descriptions(self):
        """Test adding hybrid descriptions."""
        schema = "CREATE TABLE test (id INT)"
        builder = SchemaDecoratorBuilder(schema)

        result_builder = builder.with_hybrid_descriptions()
        assert result_builder is builder

    def test_with_metadata(self):
        """Test adding metadata enhancement."""
        schema = "CREATE TABLE test (id INT)"
        builder = SchemaDecoratorBuilder(schema)

        result_builder = builder.with_metadata()
        assert result_builder is builder

    def test_with_formatting(self):
        """Test adding formatting enhancement."""
        schema = "CREATE TABLE test (id INT)"
        builder = SchemaDecoratorBuilder(schema)

        result_builder = builder.with_formatting()
        assert result_builder is builder

    def test_chaining(self):
        """Test method chaining."""
        schema = "CREATE TABLE test (id INT)"
        result = (SchemaDecoratorBuilder(schema)
                 .with_cross_project_enhancement()
                 .with_hybrid_descriptions()
                 .with_metadata()
                 .with_formatting()
                 .build())

        assert result is not None

    def test_builder_with_formatting_returns_provider(self):
        schema = "CREATE TABLE users (id INT, name TEXT);"
        provider = (SchemaDecoratorBuilder(schema)
                    .with_formatting()
                    .build())
        out = provider.get_schema(Mock())
        assert isinstance(out, str)
        assert "CREATE TABLE" in out


class TestCrossProjectSchemaDecorator:
    """Test CrossProjectSchemaDecorator."""

    def test_enhance_schema_disabled(self):
        """Test when cross project is disabled."""
        mock_provider = Mock()
        mock_provider.get_schema.return_value = "CREATE TABLE test (id INT)"

        decorator = CrossProjectSchemaDecorator(mock_provider)

        mock_config = Mock()
        mock_config.database.cross_project_access.enabled = False

        result = decorator.enhance_schema("CREATE TABLE test (id INT)", mock_config)
        assert isinstance(result, str)

    def test_enhance_schema_enabled_no_datasets(self):
        """Test when enabled but no datasets configured."""
        mock_provider = Mock()
        mock_provider.get_schema.return_value = "CREATE TABLE test (id INT)"

        decorator = CrossProjectSchemaDecorator(mock_provider)

        mock_config = Mock()
        mock_config.database.cross_project_access.enabled = True
        mock_config.database.cross_project_access.datasets = []

        result = decorator.enhance_schema("CREATE TABLE test (id INT)", mock_config)
        assert isinstance(result, str)

    def test_matches_pattern(self):
        """Test _matches_pattern method."""
        mock_provider = Mock()
        decorator = CrossProjectSchemaDecorator(mock_provider)

        # Test exact match
        assert decorator._matches_pattern("users", "users") is True

        # Test wildcard
        assert decorator._matches_pattern("user_data", "user*") is True

        # Test no match
        assert decorator._matches_pattern("orders", "user*") is False


class TestSchemaMetadataDecorator:
    """Test SchemaMetadataDecorator."""

    def test_enhance_schema(self):
        """Test schema enhancement."""
        mock_provider = Mock()
        mock_provider.get_schema.return_value = "CREATE TABLE test (id INT)"

        decorator = SchemaMetadataDecorator(mock_provider)

        mock_config = Mock()
        mock_config.get_database_type.return_value = "BigQuery"
        mock_cross = Mock()
        mock_cross.enabled = False
        mock_cross.datasets = []
        mock_config.database.cross_project_access = mock_cross
        mock_config.database.cache_schema = False
        mock_config.database.query_timeout = 30
        mock_config.database.max_results = 1000

        result = decorator.enhance_schema("CREATE TABLE test (id INT)", mock_config)
        assert isinstance(result, str)


class TestAutoDescriptionExtractor:
    """Test AutoDescriptionExtractor."""

    def test_extract_bigquery_descriptions(self):
        """Test BigQuery description extraction."""
        with patch('askrita.sqlagent.database.schema_decorators.bigquery'):
            mock_client = Mock()

            # Mock dataset and tables
            mock_dataset = Mock()
            mock_table = Mock()
            mock_table.table_id = "test_table"
            mock_table.description = "Test table description"
            mock_table.schema = [
                Mock(name="id", description="ID column"),
                Mock(name="name", description="Name column")
            ]

            mock_dataset.list_tables.return_value = [mock_table]
            mock_client.get_dataset.return_value = mock_dataset
            mock_client.get_table.return_value = mock_table

            result = AutoDescriptionExtractor.extract_bigquery_descriptions("project.dataset", mock_client)
            assert isinstance(result, dict)

    def test_non_bq_extractors_return_dict(self):
        res_pg = AutoDescriptionExtractor.extract_postgresql_descriptions("postgresql://...")
        res_my = AutoDescriptionExtractor.extract_mysql_descriptions("mysql://...")
        assert isinstance(res_pg, dict)
        assert isinstance(res_my, dict)


class TestDescriptionMerger:
    """Test DescriptionMerger."""

    def test_init(self):
        """Test merger initialization."""
        mock_config = Mock()
        merger = DescriptionMerger(mock_config)
        assert merger.manual_config == mock_config

    def test_extract_string_value(self):
        """Test string value extraction."""
        mock_config = Mock()
        merger = DescriptionMerger(mock_config)

        # Test string input
        result = merger._extract_string_value("test string")
        assert result == "test string"

        # Test dict input
        result = merger._extract_string_value({"key": "value"})
        assert isinstance(result, str)

        # Test None input
        result = merger._extract_string_value(None)
        assert result == ""

    def test_format_column_name_as_description(self):
        """Test formatting column name as description."""
        mock_config = Mock()
        merger = DescriptionMerger(mock_config)

        # Test snake_case via merger's helper
        result = merger._format_column_name_as_description("user_name")
        assert "User Name" in result

    def test_merge_column_description(self):
        """Test merging column descriptions."""
        mock_config = Mock()
        mock_config.columns = {}
        mock_config.automatic_extraction.fallback_to_column_name = True

        merger = DescriptionMerger(mock_config)

        auto = {"test_table": {"test_column": "Auto description"}}
        result = merger.merge_column_description(auto, "test_table", "test_column")

        assert isinstance(result, str)
        assert len(result) > 0


class TestHybridDescriptionDecorator:
    """Test HybridDescriptionDecorator."""

    def test_enhance_schema(self):
        """Test enhancing schema."""
        mock_provider = Mock()
        mock_provider.get_schema.return_value = "CREATE TABLE test (id INT)"

        decorator = HybridDescriptionDecorator(mock_provider)

        mock_config = Mock()
        mock_config.database.schema_descriptions.manual = {}
        mock_config.database.schema_descriptions.automatic_extraction.enabled = False

        result = decorator.enhance_schema("CREATE TABLE test (id INT)", mock_config)
        assert isinstance(result, str)

    def test_extract_automatic_descriptions(self):
        """Test extracting automatic descriptions."""
        mock_provider = Mock()
        decorator = HybridDescriptionDecorator(mock_provider)

        mock_config = Mock()
        mock_config.database.schema_descriptions.automatic_extraction.enabled = False

        result = decorator._extract_automatic_descriptions(mock_config)
        assert isinstance(result, dict)

    def test_create_business_glossary(self):
        """Test creating business glossary."""
        mock_provider = Mock()
        decorator = HybridDescriptionDecorator(mock_provider)

        business_terms = {
            "customer": "A person who purchases products",
            "order": "A request to purchase products"
        }

        result = decorator._create_business_glossary(business_terms)
        assert isinstance(result, str)
        assert "customer" in result
        assert "order" in result

    def test_hybrid_extract_automatic_descriptions_non_bigquery(self):
        decorator = HybridDescriptionDecorator(Mock())
        cfg = Mock()
        cfg.get_database_type.return_value = "PostgreSQL"
        res = decorator._extract_automatic_descriptions(cfg)
        assert isinstance(res, dict)

    def test_hybrid_enhance_schema_when_disabled_returns_original(self):
        decorator = HybridDescriptionDecorator(Mock())
        cfg = Mock()
        desc_cfg = Mock()
        desc_cfg.automatic_extraction.enabled = False
        desc_cfg.columns = {}
        desc_cfg.project_context = None
        desc_cfg.business_terms = {}
        cfg.get_schema_descriptions.return_value = desc_cfg
        schema = "CREATE TABLE t (id INT)"
        out = decorator.enhance_schema(schema, cfg)
        assert out == schema
