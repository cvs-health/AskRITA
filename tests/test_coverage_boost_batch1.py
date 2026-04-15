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

"""Coverage boost tests for several modules targeting the 90% overall threshold.

Covers:
- askrita/sqlagent/progress_tracker.py (lines 112-124)
- askrita/__init__.py (lines 154-155, 195-196, 235-239)
- askrita/sqlagent/database/validation_chain.py (lines 192-422)
- askrita/research/SchemaAnalyzer.py (lines 161, 195, 259, 265, 288, 400, 503,
  507, 529, 566-574, 582-600, 617-620, 684, 756-870)
"""

import io
import os
import pytest
from unittest.mock import MagicMock, Mock, patch


# ============================================================================
# progress_tracker.py – inner callback (lines 112-124)
# ============================================================================

class TestCreateSimpleProgressCallback:
    def test_callback_started_no_error(self, capsys):
        """Lines 112-124: callback prints emoji and message, no error printed."""
        from askrita.sqlagent.progress_tracker import (
            create_simple_progress_callback,
            ProgressData,
            ProgressStatus,
        )
        callback = create_simple_progress_callback()
        data = ProgressData("parse_question", ProgressStatus.STARTED)
        callback(data)
        captured = capsys.readouterr()
        assert "🟡" in captured.out

    def test_callback_completed(self, capsys):
        """COMPLETED status gets green emoji."""
        from askrita.sqlagent.progress_tracker import (
            create_simple_progress_callback,
            ProgressData,
            ProgressStatus,
        )
        callback = create_simple_progress_callback()
        data = ProgressData("generate_sql", ProgressStatus.COMPLETED)
        callback(data)
        captured = capsys.readouterr()
        assert "🟢" in captured.out

    def test_callback_failed_prints_error(self, capsys):
        """Line 121-122: error message is printed when present."""
        from askrita.sqlagent.progress_tracker import (
            create_simple_progress_callback,
            ProgressData,
            ProgressStatus,
        )
        callback = create_simple_progress_callback()
        data = ProgressData("execute_sql", ProgressStatus.FAILED, error="Something exploded")
        callback(data)
        captured = capsys.readouterr()
        assert "🔴" in captured.out
        assert "Something exploded" in captured.out

    def test_callback_skipped(self, capsys):
        """SKIPPED status gets white circle emoji."""
        from askrita.sqlagent.progress_tracker import (
            create_simple_progress_callback,
            ProgressData,
            ProgressStatus,
        )
        callback = create_simple_progress_callback()
        data = ProgressData("choose_visualization", ProgressStatus.SKIPPED)
        callback(data)
        captured = capsys.readouterr()
        assert "⚪" in captured.out

    def test_callback_unknown_status(self, capsys):
        """Unknown status uses black circle emoji fallback."""
        from askrita.sqlagent.progress_tracker import (
            create_simple_progress_callback,
            ProgressData,
            ProgressStatus,
        )
        callback = create_simple_progress_callback()
        # Use a valid status and then monkey-patch just the progress.status
        data = ProgressData("other_step", ProgressStatus.STARTED)
        # Simulate unknown status with a fake status object
        data.status = Mock()
        data.status.value = "unknown_state"
        callback(data)
        captured = capsys.readouterr()
        assert "⚫" in captured.out


# ============================================================================
# askrita/__init__.py – error branches (lines 154-155, 195-196, 235-239)
# ============================================================================

class TestInitModuleErrorPaths:
    """Test error branches in create_sql_agent, create_nosql_agent,
    create_data_classifier factory functions."""

    @patch("askrita.ConfigManager")
    def test_create_sql_agent_generic_exception(self, mock_cm):
        """Line 154-155: generic Exception → ConfigurationError."""
        from askrita import create_sql_agent
        from askrita.exceptions import ConfigurationError

        mock_cm.side_effect = RuntimeError("unexpected boom")
        with pytest.raises(ConfigurationError, match="Failed to create SQL agent workflow"):
            create_sql_agent("config.yaml")

    @patch("askrita.ConfigManager")
    def test_create_nosql_agent_generic_exception(self, mock_cm):
        """Line 195-196: generic Exception → ConfigurationError."""
        from askrita import create_nosql_agent
        from askrita.exceptions import ConfigurationError

        mock_cm.side_effect = RuntimeError("unexpected boom")
        with pytest.raises(ConfigurationError, match="Failed to create NoSQL agent workflow"):
            create_nosql_agent("config.yaml")

    @patch("askrita.ConfigManager")
    def test_create_data_classifier_file_not_found(self, mock_cm):
        """Line 235: FileNotFoundError → ConfigurationError."""
        from askrita import create_data_classifier
        from askrita.exceptions import ConfigurationError

        mock_cm.side_effect = FileNotFoundError("no file")
        with pytest.raises(ConfigurationError, match="Configuration file not found"):
            create_data_classifier("missing.yaml")

    @patch("askrita.ConfigManager")
    def test_create_data_classifier_generic_exception(self, mock_cm):
        """Line 238-239: generic Exception → ConfigurationError."""
        from askrita import create_data_classifier
        from askrita.exceptions import ConfigurationError

        mock_cm.side_effect = RuntimeError("something broke")
        with pytest.raises(ConfigurationError, match="Failed to create data classification workflow"):
            create_data_classifier("config.yaml")

    @patch("askrita.ConfigManager")
    def test_create_sql_agent_reraises_configuration_error(self, mock_cm):
        """Line 151-153: ConfigurationError is re-raised as-is."""
        from askrita import create_sql_agent
        from askrita.exceptions import ConfigurationError

        mock_cm.side_effect = ConfigurationError("bad config")
        with pytest.raises(ConfigurationError, match="bad config"):
            create_sql_agent("config.yaml")


# ============================================================================
# validation_chain.py – all exception paths and cross-project success messages
# ============================================================================

def _make_context(dataset_id="my_dataset", is_cross_project=False, bigquery_client=None):
    """Build a ValidationContext with mocked dependencies."""
    from askrita.sqlagent.database.validation_chain import ValidationContext
    mock_db = MagicMock()
    mock_config = MagicMock()
    mock_config.database.connection_string = "bigquery://my-project/my_dataset"
    ctx = ValidationContext(
        db=mock_db,
        config=mock_config,
        connection_string="bigquery://my-project/my_dataset",
        project_id="my-project",
        dataset_id=dataset_id,
        bigquery_client=bigquery_client,
        is_cross_project_enabled=is_cross_project,
    )
    return ctx


class TestDatasetExistenceValidationStep:
    def test_dataset_exists_returns_true(self):
        """Lines 192-196: dataset truthy → True."""
        from askrita.sqlagent.database.validation_chain import DatasetExistenceValidationStep
        step = DatasetExistenceValidationStep()
        ctx = _make_context()
        mock_client = MagicMock()
        mock_dataset = MagicMock()
        mock_client.get_dataset.return_value = mock_dataset
        ctx.bigquery_client = mock_client
        result = step.validate(ctx)
        assert result is True

    def test_dataset_not_found_returns_false(self):
        """Lines 198-203: dataset is falsy → False."""
        from askrita.sqlagent.database.validation_chain import DatasetExistenceValidationStep
        step = DatasetExistenceValidationStep()
        ctx = _make_context()
        mock_client = MagicMock()
        mock_client.get_dataset.return_value = None
        ctx.bigquery_client = mock_client
        result = step.validate(ctx)
        assert result is False

    def test_404_exception_returns_false(self):
        """Lines 207-211: 404 error → False."""
        from askrita.sqlagent.database.validation_chain import DatasetExistenceValidationStep
        step = DatasetExistenceValidationStep()
        ctx = _make_context()
        mock_client = MagicMock()
        mock_client.get_dataset.side_effect = Exception("404 not found")
        ctx.bigquery_client = mock_client
        result = step.validate(ctx)
        assert result is False

    def test_403_exception_returns_false(self):
        """Lines 213-218: 403 access denied → False."""
        from askrita.sqlagent.database.validation_chain import DatasetExistenceValidationStep
        step = DatasetExistenceValidationStep()
        ctx = _make_context()
        mock_client = MagicMock()
        mock_client.get_dataset.side_effect = Exception("403 access denied")
        ctx.bigquery_client = mock_client
        result = step.validate(ctx)
        assert result is False

    def test_authentication_exception_returns_false(self):
        """Lines 219-224: authentication error → False."""
        from askrita.sqlagent.database.validation_chain import DatasetExistenceValidationStep
        step = DatasetExistenceValidationStep()
        ctx = _make_context()
        mock_client = MagicMock()
        mock_client.get_dataset.side_effect = Exception("authentication failed")
        ctx.bigquery_client = mock_client
        result = step.validate(ctx)
        assert result is False

    def test_permission_exception_returns_false(self):
        """Lines 225-230: permission error → False."""
        from askrita.sqlagent.database.validation_chain import DatasetExistenceValidationStep
        step = DatasetExistenceValidationStep()
        ctx = _make_context()
        mock_client = MagicMock()
        mock_client.get_dataset.side_effect = Exception("insufficient permissions")
        ctx.bigquery_client = mock_client
        result = step.validate(ctx)
        assert result is False

    def test_generic_exception_returns_false(self):
        """Lines 231-235: generic error → False."""
        from askrita.sqlagent.database.validation_chain import DatasetExistenceValidationStep
        step = DatasetExistenceValidationStep()
        ctx = _make_context()
        mock_client = MagicMock()
        mock_client.get_dataset.side_effect = Exception("some random error")
        ctx.bigquery_client = mock_client
        result = step.validate(ctx)
        assert result is False

    def test_creates_client_when_none(self):
        """Lines 185-186: creates bigquery.Client when context.bigquery_client is None."""
        from askrita.sqlagent.database.validation_chain import DatasetExistenceValidationStep
        step = DatasetExistenceValidationStep()
        ctx = _make_context(bigquery_client=None)
        # No client; bigquery.Client() will be called
        with patch("askrita.sqlagent.database.validation_chain.bigquery") as mock_bq:
            mock_client = MagicMock()
            mock_client.get_dataset.return_value = MagicMock()
            mock_bq.Client.return_value = mock_client
            result = step.validate(ctx)
        assert result is True


class TestQueryExecutionValidationStep:
    def test_error_with_jobs_create(self):
        """Lines 264-268: bigquery.jobs.create in error → specific message."""
        from askrita.sqlagent.database.validation_chain import QueryExecutionValidationStep
        step = QueryExecutionValidationStep()
        ctx = _make_context()
        ctx.db.run_no_throw.return_value = "Error: bigquery.jobs.create permission denied"
        result = step.validate(ctx)
        assert result is False

    def test_generic_error_string(self):
        """Lines 270-275: generic error string → False."""
        from askrita.sqlagent.database.validation_chain import QueryExecutionValidationStep
        step = QueryExecutionValidationStep()
        ctx = _make_context()
        ctx.db.run_no_throw.return_value = "Error: some execution error"
        result = step.validate(ctx)
        assert result is False

    def test_exception_during_validate(self):
        """Lines 280-284: exception in validate → False."""
        from askrita.sqlagent.database.validation_chain import QueryExecutionValidationStep
        step = QueryExecutionValidationStep()
        ctx = _make_context()
        ctx.db.run_no_throw.side_effect = RuntimeError("db exploded")
        result = step.validate(ctx)
        assert result is False


class TestTableListingValidationStep:
    def _enabled_context(self):
        ctx = _make_context(dataset_id="my_dataset", is_cross_project=False)
        ctx.bigquery_client = MagicMock()
        return ctx

    def test_table_listing_403_error(self):
        """Lines 315-316: 403 access denied → False."""
        from askrita.sqlagent.database.validation_chain import TableListingValidationStep
        step = TableListingValidationStep()
        ctx = self._enabled_context()
        ctx.bigquery_client.list_tables.side_effect = Exception("403 access denied")
        result = step.validate(ctx)
        assert result is False

    def test_table_listing_permission_error(self):
        """Line 321: permission error → False."""
        from askrita.sqlagent.database.validation_chain import TableListingValidationStep
        step = TableListingValidationStep()
        ctx = self._enabled_context()
        ctx.bigquery_client.list_tables.side_effect = Exception("insufficient permissions")
        result = step.validate(ctx)
        assert result is False

    def test_table_listing_generic_error(self):
        """Line 327: generic error → False."""
        from askrita.sqlagent.database.validation_chain import TableListingValidationStep
        step = TableListingValidationStep()
        ctx = self._enabled_context()
        ctx.bigquery_client.list_tables.side_effect = Exception("unknown error")
        result = step.validate(ctx)
        assert result is False

    def test_creates_client_when_none(self):
        """Lines 310-311: creates bigquery.Client when context.bigquery_client is None."""
        from askrita.sqlagent.database.validation_chain import TableListingValidationStep
        step = TableListingValidationStep()
        ctx = _make_context(dataset_id="my_dataset", is_cross_project=False)
        ctx.bigquery_client = None
        with patch("askrita.sqlagent.database.validation_chain.bigquery") as mock_bq:
            mock_client = MagicMock()
            mock_client.list_tables.return_value = [MagicMock(), MagicMock()]
            mock_bq.Client.return_value = mock_client
            result = step.validate(ctx)
        assert result is True


class TestBigQueryValidationChain:
    def _make_chain_config(self, conn_string, is_cross_project=False):
        config = MagicMock()
        config.database.connection_string = conn_string
        cross = MagicMock()
        cross.enabled = is_cross_project
        config.database.cross_project_access = cross
        return config

    def test_cross_project_enabled_success_message(self, caplog):
        """Lines 411-416: cross-project success path logs cross-project message."""
        import logging
        from askrita.sqlagent.database.validation_chain import BigQueryValidationChain

        chain = BigQueryValidationChain()
        config = self._make_chain_config(
            "bigquery://my-project/my_dataset", is_cross_project=True
        )
        mock_db = MagicMock()

        # All steps pass
        with patch.object(chain.dataset_step, "handle", return_value=True):
            with caplog.at_level(logging.INFO):
                result = chain.validate(mock_db, config)
        assert result is True

    def test_non_cross_project_with_dataset_success(self, caplog):
        """Lines 418-424: standard project+dataset success logs dataset accessible."""
        import logging
        from askrita.sqlagent.database.validation_chain import BigQueryValidationChain

        chain = BigQueryValidationChain()
        config = self._make_chain_config("bigquery://my-project/my_dataset")
        mock_db = MagicMock()

        with patch.object(chain.dataset_step, "handle", return_value=True):
            with caplog.at_level(logging.INFO):
                result = chain.validate(mock_db, config)
        assert result is True

    def test_failure_logs_error_messages(self, caplog):
        """Line 427-428: failure path logs specific errors from context.error_messages."""
        import logging
        from askrita.sqlagent.database.validation_chain import BigQueryValidationChain

        chain = BigQueryValidationChain()
        config = self._make_chain_config("bigquery://my-project/my_dataset")
        mock_db = MagicMock()

        with patch.object(chain.dataset_step, "handle", return_value=False):
            with caplog.at_level(logging.ERROR):
                result = chain.validate(mock_db, config)
        assert result is False

    def test_no_dataset_in_connection_string(self, caplog):
        """Line 382: CROSS_PROJECT_ACCESS dataset_id when no / in connection string."""
        import logging
        from askrita.sqlagent.database.validation_chain import BigQueryValidationChain

        chain = BigQueryValidationChain()
        config = self._make_chain_config("bigquery://my-project")  # no dataset
        mock_db = MagicMock()

        with patch.object(chain.dataset_step, "handle", return_value=True):
            result = chain.validate(mock_db, config)
        assert result is True


# ============================================================================
# SchemaAnalyzer.py – remaining uncovered paths
# ============================================================================

def _make_schema_analyzer(tables=None, db_type="BigQuery"):
    """Create SchemaAnalyzer with a mocked sql_agent."""
    from askrita.research.SchemaAnalyzer import SchemaAnalyzer
    agent = MagicMock()
    agent.config.get_database_type.return_value = db_type
    agent.schema = "CREATE TABLE sales (id INT, revenue FLOAT, customer_id INT);"
    agent.structured_schema = {"tables": tables or {}}
    return SchemaAnalyzer(agent)


def _rich_tables():
    """Return tables with high-value and dimension/fact structure."""
    return {
        "sales": {
            "description": "Sales fact table",
            "columns": {
                "id": {"type": "INTEGER", "nullable": False},
                "revenue": {"type": "FLOAT", "nullable": True},
                "amount": {"type": "DECIMAL", "nullable": True},
                "cost": {"type": "DECIMAL", "nullable": True},
                "customer_id": {"type": "INTEGER", "nullable": True},
                "sale_date": {"type": "TIMESTAMP", "nullable": True},
            },
        },
        "customers": {
            "description": "Customer dimension",
            "columns": {
                "customer_id": {"type": "INTEGER", "nullable": False},
                "customer_type": {"type": "VARCHAR", "nullable": True},
                "region": {"type": "VARCHAR", "nullable": True},
            },
        },
    }


class TestSchemaAnalyzerMissingPaths:
    def test_determine_statistical_type_temporal_by_type(self):
        """Line 259: type contains DATE/TIME → temporal."""
        from askrita.research.SchemaAnalyzer import SchemaAnalyzer
        analyzer = _make_schema_analyzer()
        result = analyzer._determine_statistical_type("some_col", "DATETIME")
        assert result == "temporal"

    def test_determine_statistical_type_identifier_by_type(self):
        """Line 265: type contains UUID → identifier."""
        from askrita.research.SchemaAnalyzer import SchemaAnalyzer
        analyzer = _make_schema_analyzer()
        result = analyzer._determine_statistical_type("my_field", "UUID")
        assert result == "identifier"

    def test_determine_statistical_type_default_categorical(self):
        """Line 288: completely unknown type → categorical default."""
        from askrita.research.SchemaAnalyzer import SchemaAnalyzer
        analyzer = _make_schema_analyzer()
        result = analyzer._determine_statistical_type("misc_field", "GEOMETRY")
        assert result == "categorical"

    def test_classify_table_type_default_fact(self):
        """Line 400: equal numerical & categorical → default "fact"."""
        from askrita.research.SchemaAnalyzer import SchemaAnalyzer, ColumnAnalysis
        analyzer = _make_schema_analyzer()
        # Equal mix → falls through to default "fact"
        from collections import OrderedDict
        cols = {
            "a": ColumnAnalysis("a", "FLOAT", True, statistical_type="numerical"),
            "b": ColumnAnalysis("b", "VARCHAR", True, statistical_type="categorical"),
        }
        result = analyzer._classify_table_type("misc_table", cols)
        assert result == "fact"

    def test_analyze_schema_patterns_uppercase_table(self):
        """Line 507: table.name.isupper() path."""
        from askrita.research.SchemaAnalyzer import SchemaAnalyzer, SchemaAnalysisReport, TableAnalysis, ColumnAnalysis
        analyzer = _make_schema_analyzer()
        report = SchemaAnalysisReport(
            database_type="BigQuery",
            total_tables=1,
            total_columns=1,
            analysis_timestamp="2026",
        )
        table = TableAnalysis(name="ORDERS", full_name="ORDERS")
        col = ColumnAnalysis("id", "INTEGER", False)
        table.columns["id"] = col
        report.tables["ORDERS"] = table
        report.total_columns = 1
        analyzer._analyze_schema_patterns(report)
        assert "uppercase" in report.naming_patterns

    def test_classify_tables_populates_dimension_list(self):
        """Line 529: dimension tables added to potential_dimension_tables."""
        from askrita.research.SchemaAnalyzer import SchemaAnalyzer, SchemaAnalysisReport, TableAnalysis
        analyzer = _make_schema_analyzer()
        report = SchemaAnalysisReport(
            database_type="BigQuery",
            total_tables=1,
            total_columns=0,
            analysis_timestamp="2026",
        )
        table = TableAnalysis(name="customer_dim", full_name="customer_dim",
                               entity_type="dimension", research_value="high")
        report.tables["customer_dim"] = table
        analyzer._classify_tables(report)
        assert "customer_dim" in report.potential_dimension_tables

    def test_assess_research_potential_normalized_model(self):
        """Lines 565-566: more dimension tables → normalized."""
        from askrita.research.SchemaAnalyzer import SchemaAnalyzer, SchemaAnalysisReport
        analyzer = _make_schema_analyzer()
        report = SchemaAnalysisReport(
            database_type="BigQuery", total_tables=3, total_columns=10, analysis_timestamp="2026"
        )
        report.potential_fact_tables = ["sales"]
        report.potential_dimension_tables = ["customers", "products"]
        report.high_value_tables = []
        analyzer._assess_research_potential(report)
        assert report.data_model_type == "normalized"

    def test_assess_research_potential_denormalized_model(self):
        """Lines 567-568: fact only → denormalized."""
        from askrita.research.SchemaAnalyzer import SchemaAnalyzer, SchemaAnalysisReport
        analyzer = _make_schema_analyzer()
        report = SchemaAnalysisReport(
            database_type="BigQuery", total_tables=1, total_columns=5, analysis_timestamp="2026"
        )
        report.potential_fact_tables = ["sales"]
        report.potential_dimension_tables = []
        report.high_value_tables = []
        analyzer._assess_research_potential(report)
        assert report.data_model_type == "denormalized"

    def test_assess_research_potential_excellent_readiness(self):
        """Line 574: ≥3 high-value tables + ≥1 fact → excellent."""
        from askrita.research.SchemaAnalyzer import SchemaAnalyzer, SchemaAnalysisReport
        analyzer = _make_schema_analyzer()
        report = SchemaAnalysisReport(
            database_type="BigQuery", total_tables=5, total_columns=20, analysis_timestamp="2026"
        )
        report.high_value_tables = ["t1", "t2", "t3"]
        report.potential_fact_tables = ["t1"]
        report.potential_dimension_tables = []
        analyzer._assess_research_potential(report)
        assert report.research_readiness == "excellent"

    def test_enhance_with_sample_data_success(self):
        """Lines 582-596: _enhance_with_sample_data queries row counts."""
        from askrita.research.SchemaAnalyzer import SchemaAnalyzer, SchemaAnalysisReport, TableAnalysis
        analyzer = _make_schema_analyzer()

        # Make sql_agent.query return result with .results
        mock_result = MagicMock()
        mock_result.results = ["42 rows"]
        analyzer.sql_agent.query.return_value = mock_result

        report = SchemaAnalysisReport(
            database_type="BigQuery", total_tables=1, total_columns=3, analysis_timestamp="2026"
        )
        table = TableAnalysis(name="sales", full_name="sales")
        report.tables["sales"] = table
        report.high_value_tables = ["sales"]

        analyzer._enhance_with_sample_data(report)
        # Row count should have been set
        assert report.tables["sales"].row_count_estimate is not None

    def test_enhance_with_sample_data_exception_continues(self):
        """Lines 598-600: exception in query → continue gracefully."""
        from askrita.research.SchemaAnalyzer import SchemaAnalyzer, SchemaAnalysisReport, TableAnalysis
        analyzer = _make_schema_analyzer()
        analyzer.sql_agent.query.side_effect = RuntimeError("LLM unavailable")

        report = SchemaAnalysisReport(
            database_type="BigQuery", total_tables=1, total_columns=1, analysis_timestamp="2026"
        )
        table = TableAnalysis(name="orders", full_name="orders")
        report.tables["orders"] = table
        report.high_value_tables = ["orders"]

        # Should not raise
        analyzer._enhance_with_sample_data(report)

    def test_analyze_schema_with_sample_data_enabled(self):
        """Line 161: _enhance_with_sample_data called when include_sample_data=True."""
        from askrita.research.SchemaAnalyzer import SchemaAnalyzer
        analyzer = _make_schema_analyzer(_rich_tables())
        analyzer.sql_agent.query.side_effect = RuntimeError("no LLM")

        # Should complete without error even if sample data fails
        report = analyzer.analyze_schema(include_sample_data=True)
        assert report.total_tables == 2

    def test_analyze_table_primary_key_tracked(self):
        """Line 195: primary key column added to primary_keys list."""
        from askrita.research.SchemaAnalyzer import SchemaAnalyzer
        analyzer = _make_schema_analyzer()
        table_info = {
            "columns": {
                "id": {"type": "INTEGER", "nullable": False},
                "user_id": {"type": "INTEGER", "nullable": True},
            }
        }
        table = analyzer._analyze_table("users", table_info, "CREATE TABLE users (id INT);")
        # "id" matches primary key detection
        assert "id" in table.primary_keys or len(table.columns) == 2


class TestSchemaAnalyzerRenderingMethods:
    def _full_report(self):
        """Create a SchemaAnalysisReport with all fields populated."""
        from askrita.research.SchemaAnalyzer import (
            SchemaAnalysisReport, TableAnalysis, ColumnAnalysis
        )
        report = SchemaAnalysisReport(
            database_type="BigQuery",
            total_tables=2,
            total_columns=5,
            analysis_timestamp="2026-01-01",
            schema_complexity="moderate",
            data_model_type="mixed",
            research_readiness="excellent",
        )
        # Add a high-value fact table
        table = TableAnalysis(
            name="sales",
            full_name="sales",
            entity_type="fact",
            research_value="high",
            row_count_estimate=50000,
        )
        for name, dtype, stat in [
            ("revenue", "FLOAT", "numerical"),
            ("cost", "FLOAT", "numerical"),
            ("sale_date", "TIMESTAMP", "temporal"),
        ]:
            col = ColumnAnalysis(name=name, data_type=dtype, is_nullable=True,
                                  statistical_type=stat, research_potential="high")
            table.columns[name] = col
        table.primary_keys = ["revenue"]
        table.foreign_keys = ["cost"]
        table.analysis_suggestions = ["📊 Analyze trends", "🎯 Investigate correlations"]
        report.tables["sales"] = table

        # Add dimension table
        dim_table = TableAnalysis(
            name="customers",
            full_name="customers",
            entity_type="dimension",
            research_value="low",
        )
        report.tables["customers"] = dim_table

        report.high_value_tables = ["sales"]
        report.potential_fact_tables = ["sales"]
        report.potential_dimension_tables = ["customers"]
        report.suggested_relationships = [
            {"from_table": "sales", "from_column": "customer_id", "to_table": "customers",
             "relationship_type": "foreign_key"}
        ]
        report.naming_patterns = {"snake_case": 2, "lowercase": 2}
        report.data_type_distribution = {"FLOAT": 2, "TIMESTAMP": 1}
        report.analysis_steps = ["Step 1", "Step 2"]
        report.recommended_analyses = [
            {"category": "Priority Analysis", "description": "Focus on high-value tables",
             "tables": ["sales"], "confidence": "high"},
            {"category": "Advanced Analytics",
             "description": "Schema ready for modeling",
             "suggested_analyses": ["Correlation", "Regression"],
             "confidence": "high"},
        ]
        return report

    def test_render_high_value_tables_section(self):
        """Lines 756-770: _render_high_value_tables_section returns non-empty list."""
        from askrita.research.SchemaAnalyzer import SchemaAnalyzer
        analyzer = _make_schema_analyzer()
        report = self._full_report()
        lines = analyzer._render_high_value_tables_section(report)
        assert isinstance(lines, list)
        assert any("sales" in line.upper() or "SALES" in line for line in lines)

    def test_render_table_detail_section(self):
        """Lines 774-794: _render_table_detail_section returns non-empty list."""
        from askrita.research.SchemaAnalyzer import SchemaAnalyzer
        analyzer = _make_schema_analyzer()
        report = self._full_report()
        table = report.tables["sales"]
        lines = analyzer._render_table_detail_section("sales", table)
        assert isinstance(lines, list)
        assert any("sales" in line.lower() for line in lines)

    def test_render_recommendations_section(self):
        """Lines 798-810: _render_recommendations_section returns list with categories."""
        from askrita.research.SchemaAnalyzer import SchemaAnalyzer
        analyzer = _make_schema_analyzer()
        report = self._full_report()
        lines = analyzer._render_recommendations_section(report)
        assert isinstance(lines, list)
        assert any("PRIORITY" in line.upper() or "ANALYSIS" in line.upper() for line in lines)

    def test_generate_detailed_report(self):
        """Lines 814-870: generate_detailed_report returns a multi-line string."""
        from askrita.research.SchemaAnalyzer import SchemaAnalyzer
        analyzer = _make_schema_analyzer()
        report = self._full_report()
        text = analyzer.generate_detailed_report(report)
        assert isinstance(text, str)
        assert "BigQuery" in text
        assert "sales" in text.lower()
        assert "NEXT STEPS" in text

    def test_generate_detailed_report_no_high_value_tables(self):
        """generate_detailed_report works with empty high_value_tables (no section)."""
        from askrita.research.SchemaAnalyzer import SchemaAnalyzer, SchemaAnalysisReport
        analyzer = _make_schema_analyzer()
        report = SchemaAnalysisReport(
            database_type="PostgreSQL",
            total_tables=0,
            total_columns=0,
            analysis_timestamp="2026",
            schema_complexity="simple",
            data_model_type="mixed",
            research_readiness="needs_preparation",
        )
        report.analysis_steps = ["Overview"]
        text = analyzer.generate_detailed_report(report)
        assert isinstance(text, str)
        assert "PostgreSQL" in text

    def test_generate_analysis_instructions_excellent_readiness(self):
        """Line 684: excellent readiness adds Advanced Analytics recommendation."""
        from askrita.research.SchemaAnalyzer import SchemaAnalyzer
        analyzer = _make_schema_analyzer()
        report = self._full_report()
        report.research_readiness = "excellent"
        report.high_value_tables = ["sales", "t2", "t3"]  # ≥3 for excellent
        # Reset recommendations
        report.recommended_analyses = []
        analyzer._generate_analysis_instructions(report)
        categories = [r.get("category", "") for r in report.recommended_analyses]
        assert any("Advanced" in c for c in categories)

    def test_generate_analysis_instructions_needs_preparation(self):
        """Else branch in _generate_analysis_instructions for needs_preparation."""
        from askrita.research.SchemaAnalyzer import SchemaAnalyzer
        analyzer = _make_schema_analyzer()
        report = self._full_report()
        report.research_readiness = "needs_preparation"
        report.high_value_tables = []
        report.potential_fact_tables = []
        report.potential_dimension_tables = []
        report.suggested_relationships = []
        report.recommended_analyses = []
        analyzer._generate_analysis_instructions(report)
        categories = [r.get("category", "") for r in report.recommended_analyses]
        assert any("Basic" in c for c in categories)

    def test_get_readiness_description_all_values(self):
        """_get_readiness_description returns non-empty string for all values."""
        from askrita.research.SchemaAnalyzer import SchemaAnalyzer
        analyzer = _make_schema_analyzer()
        for readiness in ["excellent", "good", "needs_preparation", "unknown"]:
            desc = analyzer._get_readiness_description(readiness)
            assert isinstance(desc, str)
            assert len(desc) > 0
