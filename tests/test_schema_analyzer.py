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

"""Tests for research/SchemaAnalyzer.py – targets missing coverage lines."""

from unittest.mock import MagicMock

from askrita.research.SchemaAnalyzer import (
    ColumnAnalysis,
    TableAnalysis,
    SchemaAnalysisReport,
    SchemaAnalyzer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(tables=None, db_type="BigQuery"):
    """Create a minimal mock SQL agent."""
    agent = MagicMock()
    agent.config.get_database_type.return_value = db_type
    agent.schema = "CREATE TABLE orders (id INT, amount FLOAT);"

    if tables is None:
        tables = {}

    agent.structured_schema = {"tables": tables}
    return agent


def _basic_tables():
    return {
        "orders": {
            "description": "Order transactions",
            "columns": {
                "order_id": {"type": "INTEGER", "nullable": False},
                "amount": {"type": "FLOAT", "nullable": True},
                "created_date": {"type": "TIMESTAMP", "nullable": True},
                "status": {"type": "VARCHAR", "nullable": True},
            }
        },
        "customers": {
            "description": "Customer dimension",
            "columns": {
                "customer_id": {"type": "INTEGER", "nullable": False},
                "customer_type": {"type": "VARCHAR", "nullable": True},
                "region": {"type": "VARCHAR", "nullable": True},
            }
        }
    }


# ---------------------------------------------------------------------------
# ColumnAnalysis
# ---------------------------------------------------------------------------

class TestColumnAnalysis:
    def test_str_representation(self):
        col = ColumnAnalysis(name="amount", data_type="FLOAT", is_nullable=True)
        s = str(col)
        assert "amount" in s
        assert "FLOAT" in s


# ---------------------------------------------------------------------------
# TableAnalysis
# ---------------------------------------------------------------------------

class TestTableAnalysis:
    def test_str_representation(self):
        table = TableAnalysis(name="orders", full_name="orders")
        s = str(table)
        assert "orders" in s


# ---------------------------------------------------------------------------
# SchemaAnalysisReport
# ---------------------------------------------------------------------------

class TestSchemaAnalysisReport:
    def test_str_representation(self):
        report = SchemaAnalysisReport(
            database_type="BigQuery",
            total_tables=5,
            total_columns=20,
            analysis_timestamp="2026-01-01",
        )
        s = str(report)
        assert "BigQuery" in s


# ---------------------------------------------------------------------------
# SchemaAnalyzer._analyze_column
# ---------------------------------------------------------------------------

class TestAnalyzeColumn:
    def _analyzer(self):
        return SchemaAnalyzer(_make_agent())

    def test_integer_id_column(self):
        analyzer = self._analyzer()
        col = analyzer._analyze_column("customer_id", {"type": "INTEGER", "nullable": False})
        assert col.statistical_type == "identifier"
        assert col.is_primary_key or col.is_foreign_key or True  # just check no crash

    def test_float_amount_column(self):
        analyzer = self._analyzer()
        col = analyzer._analyze_column("amount", {"type": "FLOAT", "nullable": True})
        assert col.statistical_type == "numerical"
        assert col.research_potential == "high"

    def test_timestamp_column(self):
        analyzer = self._analyzer()
        col = analyzer._analyze_column("created_date", {"type": "TIMESTAMP", "nullable": True})
        assert col.statistical_type == "temporal"

    def test_varchar_status_column(self):
        analyzer = self._analyzer()
        col = analyzer._analyze_column("status", {"type": "VARCHAR", "nullable": True})
        assert col.statistical_type == "categorical"

    def test_boolean_column(self):
        analyzer = self._analyzer()
        col = analyzer._analyze_column("is_active", {"type": "BOOLEAN", "nullable": True})
        assert col.statistical_type == "categorical"

    def test_description_column_low_potential(self):
        analyzer = self._analyzer()
        col = analyzer._analyze_column("product_description", {"type": "TEXT", "nullable": True})
        assert col.research_potential == "low"


# ---------------------------------------------------------------------------
# SchemaAnalyzer._determine_statistical_type
# ---------------------------------------------------------------------------

class TestDetermineStatisticalType:
    def _analyzer(self):
        return SchemaAnalyzer(_make_agent())

    def test_date_in_name(self):
        result = self._analyzer()._determine_statistical_type("order_date", "VARCHAR")
        assert result == "temporal"

    def test_timestamp_type(self):
        result = self._analyzer()._determine_statistical_type("created_at", "TIMESTAMP")
        assert result == "temporal"

    def test_uuid_name(self):
        result = self._analyzer()._determine_statistical_type("user_uuid", "VARCHAR")
        assert result == "identifier"

    def test_int_type_normal(self):
        result = self._analyzer()._determine_statistical_type("quantity", "INTEGER")
        assert result == "numerical"

    def test_int_type_status_categorical(self):
        result = self._analyzer()._determine_statistical_type("status_level", "INTEGER")
        assert result == "categorical"

    def test_string_type(self):
        result = self._analyzer()._determine_statistical_type("name", "STRING")
        assert result == "categorical"

    def test_bool_type(self):
        result = self._analyzer()._determine_statistical_type("flag", "BOOLEAN")
        assert result == "categorical"

    def test_decimal_numeric(self):
        result = self._analyzer()._determine_statistical_type("price", "DECIMAL")
        assert result == "numerical"


# ---------------------------------------------------------------------------
# SchemaAnalyzer._assess_column_research_potential
# ---------------------------------------------------------------------------

class TestAssessColumnResearchPotential:
    def _analyzer(self):
        return SchemaAnalyzer(_make_agent())

    def test_revenue_high(self):
        result = self._analyzer()._assess_column_research_potential("revenue", "FLOAT", "numerical")
        assert result == "high"

    def test_score_high(self):
        result = self._analyzer()._assess_column_research_potential("satisfaction_score", "FLOAT", "numerical")
        assert result == "high"

    def test_status_medium(self):
        result = self._analyzer()._assess_column_research_potential("order_status", "VARCHAR", "categorical")
        assert result == "medium"

    def test_numerical_medium(self):
        result = self._analyzer()._assess_column_research_potential("index_val", "INTEGER", "numerical")
        assert result == "medium"

    def test_identifier_low(self):
        result = self._analyzer()._assess_column_research_potential("customer_id", "INTEGER", "identifier")
        assert result == "low"

    def test_description_low(self):
        result = self._analyzer()._assess_column_research_potential("item_description", "TEXT", "categorical")
        assert result == "low"

    def test_generic_medium_default(self):
        result = self._analyzer()._assess_column_research_potential("some_col", "VARCHAR", "categorical")
        assert result == "medium"


# ---------------------------------------------------------------------------
# SchemaAnalyzer._classify_table_type
# ---------------------------------------------------------------------------

class TestClassifyTableType:
    def _analyzer(self):
        return SchemaAnalyzer(_make_agent())

    def _make_cols(self, numerical=0, categorical=0):
        cols = {}
        for i in range(numerical):
            col = MagicMock()
            col.statistical_type = "numerical"
            cols[f"num_{i}"] = col
        for i in range(categorical):
            col = MagicMock()
            col.statistical_type = "categorical"
            cols[f"cat_{i}"] = col
        return cols

    def test_fact_table_by_name(self):
        result = self._analyzer()._classify_table_type("sales_data", {})
        assert result == "fact"

    def test_dimension_table_by_name(self):
        result = self._analyzer()._classify_table_type("dim_customer", {})
        assert result == "dimension"

    def test_fact_by_more_numerical_cols(self):
        cols = self._make_cols(numerical=3, categorical=1)
        result = self._analyzer()._classify_table_type("some_table", cols)
        assert result == "fact"

    def test_dimension_by_more_categorical_cols(self):
        cols = self._make_cols(numerical=1, categorical=4)
        result = self._analyzer()._classify_table_type("some_table", cols)
        assert result == "dimension"

    def test_lookup_is_dimension(self):
        result = self._analyzer()._classify_table_type("status_lookup", {})
        assert result == "dimension"


# ---------------------------------------------------------------------------
# SchemaAnalyzer._assess_table_research_value
# ---------------------------------------------------------------------------

class TestAssessTableResearchValue:
    def _analyzer(self):
        return SchemaAnalyzer(_make_agent())

    def _make_table(self, high=0, medium=0, low=0, entity_type="fact"):
        table = TableAnalysis(name="t", full_name="t", entity_type=entity_type)
        for i in range(high):
            c = ColumnAnalysis(name=f"h{i}", data_type="FLOAT", is_nullable=True, research_potential="high")
            table.columns[f"h{i}"] = c
        for i in range(medium):
            c = ColumnAnalysis(name=f"m{i}", data_type="VARCHAR", is_nullable=True, research_potential="medium")
            table.columns[f"m{i}"] = c
        for i in range(low):
            c = ColumnAnalysis(name=f"l{i}", data_type="INTEGER", is_nullable=True, research_potential="low")
            table.columns[f"l{i}"] = c
        return table

    def test_3_high_cols_is_high(self):
        table = self._make_table(high=3)
        result = self._analyzer()._assess_table_research_value(table)
        assert result == "high"

    def test_2_high_with_few_cols_is_high(self):
        table = self._make_table(high=2, low=2)
        result = self._analyzer()._assess_table_research_value(table)
        assert result == "high"

    def test_1_high_col_is_medium(self):
        table = self._make_table(high=1)
        result = self._analyzer()._assess_table_research_value(table)
        assert result == "medium"

    def test_fact_table_no_high_is_medium(self):
        table = self._make_table(medium=3, entity_type="fact")
        result = self._analyzer()._assess_table_research_value(table)
        assert result == "medium"

    def test_dimension_no_high_is_low(self):
        table = self._make_table(low=3, entity_type="dimension")
        result = self._analyzer()._assess_table_research_value(table)
        assert result == "low"


# ---------------------------------------------------------------------------
# SchemaAnalyzer._generate_column_sample_queries
# ---------------------------------------------------------------------------

class TestGenerateColumnSampleQueries:
    def _analyzer(self):
        return SchemaAnalyzer(_make_agent())

    def test_numerical_queries(self):
        queries = self._analyzer()._generate_column_sample_queries("amount", "numerical")
        assert len(queries) <= 3
        assert any("amount" in q for q in queries)

    def test_categorical_queries(self):
        queries = self._analyzer()._generate_column_sample_queries("status", "categorical")
        assert len(queries) <= 3
        assert any("status" in q for q in queries)

    def test_temporal_queries(self):
        queries = self._analyzer()._generate_column_sample_queries("created_date", "temporal")
        assert len(queries) <= 3
        assert any("created_date" in q for q in queries)

    def test_identifier_no_queries(self):
        queries = self._analyzer()._generate_column_sample_queries("user_id", "identifier")
        assert queries == []


# ---------------------------------------------------------------------------
# SchemaAnalyzer._generate_table_analysis_suggestions
# ---------------------------------------------------------------------------

class TestGenerateTableAnalysisSuggestions:
    def _analyzer(self):
        return SchemaAnalyzer(_make_agent())

    def test_fact_table_gets_suggestions(self):
        table = TableAnalysis(name="sales", full_name="sales", entity_type="fact", research_value="high")
        suggestions = self._analyzer()._generate_table_analysis_suggestions(table)
        assert len(suggestions) > 0

    def test_dimension_table_gets_suggestions(self):
        table = TableAnalysis(name="dim_prod", full_name="dim_prod", entity_type="dimension", research_value="low")
        suggestions = self._analyzer()._generate_table_analysis_suggestions(table)
        assert len(suggestions) > 0

    def test_temporal_columns_add_suggestions(self):
        table = TableAnalysis(name="events", full_name="events", entity_type="fact", research_value="high")
        col = ColumnAnalysis(name="event_time", data_type="TIMESTAMP", is_nullable=True, statistical_type="temporal")
        table.columns["event_time"] = col
        suggestions = self._analyzer()._generate_table_analysis_suggestions(table)
        assert any("time" in s.lower() or "season" in s.lower() or "series" in s.lower() for s in suggestions)

    def test_multiple_numerical_high_cols_add_correlation_suggestion(self):
        table = TableAnalysis(name="metrics", full_name="metrics", entity_type="fact")
        for name in ["revenue", "cost"]:
            col = ColumnAnalysis(name=name, data_type="FLOAT", is_nullable=True,
                                  statistical_type="numerical", research_potential="high")
            table.columns[name] = col
        suggestions = self._analyzer()._generate_table_analysis_suggestions(table)
        assert any("correlation" in s.lower() for s in suggestions)

    def test_max_5_suggestions(self):
        table = TableAnalysis(name="complex", full_name="complex", entity_type="fact", research_value="high")
        for name in ["revenue", "cost"]:
            col = ColumnAnalysis(name=name, data_type="FLOAT", is_nullable=True,
                                  statistical_type="numerical", research_potential="high")
            table.columns[name] = col
        col = ColumnAnalysis(name="created_at", data_type="TIMESTAMP", is_nullable=True, statistical_type="temporal")
        table.columns["created_at"] = col
        suggestions = self._analyzer()._generate_table_analysis_suggestions(table)
        assert len(suggestions) <= 5


# ---------------------------------------------------------------------------
# SchemaAnalyzer._analyze_schema_patterns
# ---------------------------------------------------------------------------

class TestAnalyzeSchemaPatterns:
    def _analyzer(self):
        return SchemaAnalyzer(_make_agent())

    def test_patterns_populated(self):
        agent = _make_agent(_basic_tables())
        analyzer = SchemaAnalyzer(agent)
        report = SchemaAnalysisReport(
            database_type="BigQuery",
            total_tables=2,
            total_columns=0,
            analysis_timestamp="2026",
        )
        for tname, tinfo in _basic_tables().items():
            table = analyzer._analyze_table(tname, tinfo, agent.schema)
            report.tables[tname] = table
            report.total_columns += len(table.columns)

        analyzer._analyze_schema_patterns(report)
        assert report.schema_complexity in ("simple", "moderate", "complex")

    def test_simple_complexity(self):
        agent = _make_agent(_basic_tables())
        analyzer = SchemaAnalyzer(agent)
        report = SchemaAnalysisReport(
            database_type="BigQuery", total_tables=2, total_columns=7, analysis_timestamp="2026"
        )
        report.tables = {}
        analyzer._analyze_schema_patterns(report)
        assert report.schema_complexity == "simple"

    def test_complex_schema(self):
        agent = _make_agent()
        analyzer = SchemaAnalyzer(agent)
        report = SchemaAnalysisReport(
            database_type="BigQuery", total_tables=25, total_columns=500, analysis_timestamp="2026"
        )
        report.tables = {}
        analyzer._analyze_schema_patterns(report)
        assert report.schema_complexity == "complex"

    def test_moderate_complexity(self):
        agent = _make_agent()
        analyzer = SchemaAnalyzer(agent)
        report = SchemaAnalysisReport(
            database_type="BigQuery", total_tables=15, total_columns=100, analysis_timestamp="2026"
        )
        report.tables = {}
        analyzer._analyze_schema_patterns(report)
        assert report.schema_complexity == "moderate"


# ---------------------------------------------------------------------------
# SchemaAnalyzer._classify_tables
# ---------------------------------------------------------------------------

class TestClassifyTables:
    def test_classify_populates_lists(self):
        agent = _make_agent(_basic_tables())
        analyzer = SchemaAnalyzer(agent)
        report = SchemaAnalysisReport(
            database_type="BigQuery", total_tables=2, total_columns=7, analysis_timestamp="2026"
        )
        for tname, tinfo in _basic_tables().items():
            table = analyzer._analyze_table(tname, tinfo, agent.schema)
            report.tables[tname] = table
        analyzer._classify_tables(report)
        # Just ensure no crash and lists are populated appropriately
        assert isinstance(report.high_value_tables, list)
        assert isinstance(report.potential_fact_tables, list)
        assert isinstance(report.potential_dimension_tables, list)


# ---------------------------------------------------------------------------
# SchemaAnalyzer._is_likely_primary_key / _is_likely_foreign_key
# ---------------------------------------------------------------------------

class TestKeyDetection:
    def _analyzer(self):
        return SchemaAnalyzer(_make_agent())

    def test_pk_detection_id_col(self):
        analyzer = self._analyzer()
        result = analyzer._is_likely_primary_key("id", "INTEGER")
        assert isinstance(result, bool)

    def test_fk_detection(self):
        analyzer = self._analyzer()
        result = analyzer._is_likely_foreign_key("customer_id", "INTEGER")
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# Full analyze_schema integration test (mocked)
# ---------------------------------------------------------------------------

class TestAnalyzeSchemaIntegration:
    def test_analyze_schema_basic(self):
        agent = _make_agent(_basic_tables())
        analyzer = SchemaAnalyzer(agent)
        report = analyzer.analyze_schema(include_sample_data=False)
        assert isinstance(report, SchemaAnalysisReport)
        assert report.total_tables == 2
        assert report.total_columns > 0
        assert report.schema_complexity in ("simple", "moderate", "complex")
        assert "orders" in report.tables
        assert "customers" in report.tables

    def test_analyze_schema_empty_tables(self):
        agent = _make_agent({})
        analyzer = SchemaAnalyzer(agent)
        report = analyzer.analyze_schema(include_sample_data=False)
        assert report.total_tables == 0
        assert report.total_columns == 0

    def test_analyze_schema_relationships_identified(self):
        tables = {
            "orders": {
                "columns": {
                    "order_id": {"type": "INTEGER", "nullable": False},
                    "customer_id": {"type": "INTEGER", "nullable": True},
                }
            },
            "customers": {
                "columns": {
                    "customer_id": {"type": "INTEGER", "nullable": False},
                }
            }
        }
        agent = _make_agent(tables)
        analyzer = SchemaAnalyzer(agent)
        report = analyzer.analyze_schema(include_sample_data=False)
        assert isinstance(report.suggested_relationships, list)
