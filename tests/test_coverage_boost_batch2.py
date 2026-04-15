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

"""Coverage boost tests – batch 2.

Covers:
- askrita/sqlagent/database/NoSQLDatabaseManager.py
- askrita/utils/pii_detector.py
- askrita/sqlagent/database/schema_decorators.py
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

# ============================================================================
# NoSQLDatabaseManager.py
# ============================================================================


def _make_nosql_manager():
    """Create a NoSQLDatabaseManager with all connections mocked."""
    from askrita.sqlagent.database.NoSQLDatabaseManager import NoSQLDatabaseManager

    mock_config = MagicMock()
    mock_config.database.connection_string = "mongodb://localhost:27017/testdb"
    mock_config.database.cache_schema = False
    mock_config.database.max_results = 100
    mock_config.get_schema_cache.return_value = None

    mock_db = MagicMock()
    mock_client = MagicMock()

    with patch(
        "askrita.sqlagent.database.NoSQLDatabaseManager.MongoDBStrategy"
    ) as mock_strategy_cls:
        mock_strategy = MagicMock()
        mock_strategy.get_connection_type.return_value = "mongodb"
        mock_strategy.get_safe_connection_info.return_value = "MongoDB: localhost"
        mock_strategy.test_connection.return_value = True
        mock_strategy_cls.return_value = mock_strategy

        with patch(
            "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
        ):
            manager = NoSQLDatabaseManager(
                config_manager=mock_config, test_db_connection=False
            )
            manager.db = mock_db
            manager._client = mock_client
            manager.db_strategy = mock_strategy
            manager.schema = None

    return manager, mock_config, mock_db


class TestNoSQLDatabaseManagerConnectionTest:
    def test_connection_test_raises_returns_false(self):
        """Lines 181-183: exception in test_connection → False."""
        manager, _, _ = _make_nosql_manager()
        manager.db_strategy.test_connection.side_effect = RuntimeError(
            "connection failed"
        )
        result = manager.test_connection()
        assert result is False

    def test_test_db_connection_true_raises_when_fails(self):
        """Lines 82-94: test_db_connection=True raises DatabaseError when fails."""
        from askrita.exceptions import DatabaseError
        from askrita.sqlagent.database.NoSQLDatabaseManager import NoSQLDatabaseManager

        mock_config = MagicMock()
        mock_config.database.connection_string = "mongodb://localhost:27017/testdb"
        mock_config.database.cache_schema = False

        with patch(
            "askrita.sqlagent.database.NoSQLDatabaseManager.MongoDBStrategy"
        ) as mock_strategy_cls:
            mock_strategy = MagicMock()
            mock_strategy.get_connection_type.return_value = "mongodb"
            mock_strategy.get_safe_connection_info.return_value = "MongoDB: localhost"
            mock_strategy.test_connection.return_value = False  # Fails!
            mock_strategy_cls.return_value = mock_strategy

            with patch(
                "askrita.sqlagent.database.NoSQLDatabaseManager.NoSQLDatabaseManager._initialize_database"
            ):
                with pytest.raises(DatabaseError, match="connection test failed"):
                    NoSQLDatabaseManager(
                        config_manager=mock_config, test_db_connection=True
                    )


class TestNoSQLDatabaseManagerNormalizeResult:
    def test_normalize_list_of_lists(self):
        """Line 276: list with non-dict first element → list of col_N dicts."""
        manager, _, _ = _make_nosql_manager()
        result = manager._normalize_list_result([(1, "Alice"), (2, "Bob")])
        assert result[0]["col_0"] == 1
        assert result[0]["col_1"] == "Alice"

    def test_normalize_string_json_loads(self):
        """Line 402: JSON loads branch when ast.literal_eval fails."""
        manager, _, _ = _make_nosql_manager()
        result = manager._normalize_string_result('[{"a": 1}]')
        assert isinstance(result, list)
        assert result[0]["a"] == 1

    def test_normalize_result_iterable(self):
        """Lines 427-432: iterable (not list/dict/str) is converted via list()."""
        manager, _, _ = _make_nosql_manager()

        class FakeIterator:
            def __iter__(self):
                return iter([{"x": 1}])

        result = manager._normalize_result(FakeIterator())
        assert result == [{"x": 1}]

    def test_normalize_result_unknown_type(self):
        """Lines 431-432: non-iterable unknown type returns string result."""
        manager, _, _ = _make_nosql_manager()
        result = manager._normalize_result(42)
        assert isinstance(result, list)
        assert "result" in result[0]

    def test_serialize_value_object_id(self):
        """Line 465: ObjectId type → str(value)."""
        manager, _, _ = _make_nosql_manager()

        class FakeObjectId:
            __name__ = "ObjectId"

            def __str__(self):
                return "abc123"

        fake = FakeObjectId()
        fake.__class__.__name__ = "ObjectId"
        result = manager._serialize_value(fake)
        assert result == "abc123"

    def test_serialize_value_decimal128(self):
        """Line 467: Decimal128 type → float(str(value))."""
        manager, _, _ = _make_nosql_manager()

        class FakeDecimal128:
            def __str__(self):
                return "3.14"

        fake = FakeDecimal128()
        fake.__class__.__name__ = "Decimal128"
        result = manager._serialize_value(fake)
        assert abs(result - 3.14) < 0.001

    def test_serialize_value_datetime(self):
        """Line 469: datetime type → isoformat()."""
        from datetime import datetime

        manager, _, _ = _make_nosql_manager()
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = manager._serialize_value(dt)
        assert "2024" in result

    def test_serialize_value_bytes(self):
        """Line 471: bytes → '<binary data>'."""
        manager, _, _ = _make_nosql_manager()
        result = manager._serialize_value(b"\x00\x01\x02")
        assert result == "<binary data>"


class TestNoSQLDatabaseManagerGetSampleData:
    def test_sample_data_skips_error_result(self):
        """Lines 513-515: error string from run_no_throw is skipped."""
        manager, config, mock_db = _make_nosql_manager()
        manager.db.get_usable_collection_names.return_value = ["orders"]
        manager.db.run_no_throw.return_value = "Error: access denied"
        result = manager.get_sample_data(limit=5)
        # Error result should be skipped
        assert "orders" not in result

    def test_sample_data_outer_exception_returns_empty(self):
        """Lines 520-522: outer exception → {}."""
        manager, _, _ = _make_nosql_manager()
        # get_collection_names raises to trigger outer except
        with patch.object(
            manager, "get_collection_names", side_effect=RuntimeError("meta error")
        ):
            result = manager.get_sample_data()
        assert result == {}


# ============================================================================
# pii_detector.py – uncovered branches
# ============================================================================


def _make_pii_config(**kwargs):
    """Return a minimal PIIDetectionConfig."""
    from askrita.config_manager import PIIDetectionConfig

    defaults = {
        "enabled": True,
        "entities": ["PERSON", "EMAIL_ADDRESS"],
        "confidence_threshold": 0.5,
        "sample_data_rows": 10,
        "sample_data_timeout": 30,
        "log_pii_attempts": False,
        "validate_sample_data": True,
        "block_on_detection": True,
        "redact_in_logs": False,
        "audit_log_path": None,
    }
    defaults.update(kwargs)
    return PIIDetectionConfig(**defaults)


def _make_pii_detector(extra_config=None):
    """Create PIIDetector with mocked Presidio engine."""
    config = _make_pii_config(**(extra_config or {}))
    with (
        patch("askrita.utils.pii_detector.PRESIDIO_AVAILABLE", True),
        patch("askrita.utils.pii_detector.NlpEngineProvider") as mock_provider_cls,
        patch("askrita.utils.pii_detector.AnalyzerEngine") as mock_analyzer_cls,
    ):
        mock_provider = MagicMock()
        mock_provider.create_engine.return_value = MagicMock()
        mock_provider_cls.return_value = mock_provider
        mock_analyzer = MagicMock()
        mock_analyzer_cls.return_value = mock_analyzer
        from askrita.utils.pii_detector import PIIDetector

        detector = PIIDetector(config)
    return detector


class TestPIIDetectorMissingPaths:
    def test_validate_config_sample_data_rows_too_small(self):
        """Line 142: sample_data_rows < 1 → ConfigurationError."""
        from askrita.exceptions import ConfigurationError

        config = _make_pii_config(sample_data_rows=0)
        with (
            patch("askrita.utils.pii_detector.PRESIDIO_AVAILABLE", True),
            patch("askrita.utils.pii_detector.NlpEngineProvider"),
            patch("askrita.utils.pii_detector.AnalyzerEngine"),
        ):
            from askrita.utils.pii_detector import PIIDetector

            with pytest.raises(
                ConfigurationError, match="Sample data rows must be at least 1"
            ):
                PIIDetector(config)

    def test_validate_config_timeout_too_small(self):
        """Lines 141-142: sample_data_timeout < 1 → ConfigurationError."""
        from askrita.exceptions import ConfigurationError

        config = _make_pii_config(sample_data_timeout=0)
        with (
            patch("askrita.utils.pii_detector.PRESIDIO_AVAILABLE", True),
            patch("askrita.utils.pii_detector.NlpEngineProvider"),
            patch("askrita.utils.pii_detector.AnalyzerEngine"),
        ):
            from askrita.utils.pii_detector import PIIDetector

            with pytest.raises(
                ConfigurationError,
                match="Sample data timeout must be at least 1 second",
            ):
                PIIDetector(config)

    def test_init_exception_raises_configuration_error(self):
        """Lines 124-126: AnalyzerEngine init failure → ConfigurationError."""
        from askrita.exceptions import ConfigurationError

        config = _make_pii_config()
        with (
            patch("askrita.utils.pii_detector.PRESIDIO_AVAILABLE", True),
            patch("askrita.utils.pii_detector.NlpEngineProvider") as mock_p,
            patch(
                "askrita.utils.pii_detector.AnalyzerEngine",
                side_effect=RuntimeError("engine fail"),
            ),
        ):
            mock_p.return_value.create_engine.return_value = MagicMock()
            from askrita.utils.pii_detector import PIIDetector

            with pytest.raises(
                ConfigurationError, match="PII detector initialization failed"
            ):
                PIIDetector(config)

    def test_setup_audit_logging_with_path(self, tmp_path):
        """Lines 147-164: audit_log_path set → creates audit logger."""
        log_file = str(tmp_path / "audit.log")
        config = _make_pii_config(audit_log_path=log_file, log_pii_attempts=True)
        with (
            patch("askrita.utils.pii_detector.PRESIDIO_AVAILABLE", True),
            patch("askrita.utils.pii_detector.NlpEngineProvider") as mock_p,
            patch("askrita.utils.pii_detector.AnalyzerEngine") as mock_a,
        ):
            mock_p.return_value.create_engine.return_value = MagicMock()
            mock_a.return_value = MagicMock()
            from askrita.utils.pii_detector import PIIDetector

            detector = PIIDetector(config)
        assert detector.audit_logger is not None

    def test_detect_pii_exception_raises_validation_error(self):
        """Lines 247-249: exception in analyzer.analyze → ValidationError."""
        from askrita.exceptions import ValidationError

        detector = _make_pii_detector()
        detector.analyzer.analyze.side_effect = RuntimeError("analyzer failed")
        with pytest.raises(ValidationError, match="PII analysis failed"):
            detector.detect_pii_in_text("some text")

    def test_create_redacted_text_empty_results(self):
        """Line 254: if not results: return text."""
        detector = _make_pii_detector()
        result = detector._create_redacted_text("hello world", [])
        assert result == "hello world"

    def test_log_audit_event_skips_when_log_pii_attempts_false(self):
        """Line 276: log_pii_attempts=False → early return."""
        detector = _make_pii_detector()
        detector.config.log_pii_attempts = False
        mock_result = MagicMock()
        mock_result.has_pii = False
        mock_result.entity_count = 0
        mock_result.entity_types = []
        mock_result.max_confidence = 0.0
        mock_result.blocked = False
        mock_result.analysis_time_ms = 1.0
        # Should not raise and should not log anything
        detector._log_audit_event("test_context", mock_result, "some text")

    def test_log_audit_event_uses_audit_logger_when_available(self):
        """Line 291: self.audit_logger logs PII detection event."""
        detector = _make_pii_detector()
        detector.config.log_pii_attempts = True
        mock_audit = MagicMock()
        detector.audit_logger = mock_audit
        mock_result = MagicMock()
        mock_result.has_pii = True
        mock_result.entity_count = 1
        mock_result.entity_types = ["PERSON"]
        mock_result.max_confidence = 0.9
        mock_result.blocked = True
        mock_result.analysis_time_ms = 5.0
        detector._log_audit_event("user_query", mock_result, "John Doe")
        mock_audit.info.assert_called_once()

    def test_scan_table_rows_stops_at_sample_rows_limit(self):
        """Line 307: rows_checked >= sample_rows → break."""
        import time as time_module

        detector = _make_pii_detector()
        detector.config.log_pii_attempts = False

        # Fake detect_pii_in_text to return no PII
        fake_result = MagicMock()
        fake_result.has_pii = False
        fake_result.entity_types = []
        fake_result.max_confidence = 0.0
        fake_result.entity_count = 0
        detector.detect_pii_in_text = Mock(return_value=fake_result)

        table_data = [{"col": f"row_{i}"} for i in range(10)]
        validation_results = {
            "tables_with_pii": [],
            "pii_detections": [],
            "has_pii_violations": False,
            "total_rows_checked": 0,
        }
        # Use a very large start_time so no timeout fires
        timed_out = detector._scan_table_rows_for_pii(
            "my_table",
            table_data,
            sample_rows=3,
            start_time=time_module.time(),
            validation_results=validation_results,
        )
        assert timed_out is False
        assert detector.detect_pii_in_text.call_count == 3  # stopped at limit

    def test_validate_sample_data_skipped_when_disabled(self):
        """Line 344-345: validate_sample_data=False → skipped."""
        detector = _make_pii_detector({"validate_sample_data": False})
        mock_db_manager = MagicMock()
        result = detector.validate_sample_data(mock_db_manager)
        assert result.get("skipped") is True

    def test_validate_sample_data_exception_returns_error_dict(self):
        """Lines 392-394: exception in validate_sample_data → error dict."""
        detector = _make_pii_detector()
        mock_db_manager = MagicMock()
        mock_db_manager.get_sample_data.side_effect = RuntimeError("db error")
        result = detector.validate_sample_data(mock_db_manager)
        assert "error" in result
        assert result["has_pii_violations"] is False


# ============================================================================
# schema_decorators.py – DescriptionMerger uncovered paths
# ============================================================================


class TestDescriptionMerger:
    def _make_manual_config(self, columns=None, fallback=True):
        """Create a SchemaDescriptionsConfig mock."""
        manual_config = MagicMock()
        manual_config.columns = columns or {}
        manual_config.automatic_extraction.fallback_to_column_name = fallback
        return manual_config

    def test_extract_string_value_column_description_config(self):
        """Lines 617-623: ColumnDescriptionConfig duck-type → .description used."""
        from askrita.sqlagent.database.schema_decorators import DescriptionMerger

        manual_config = self._make_manual_config()
        merger = DescriptionMerger(manual_config)

        class FakeColumnConfig:
            description = "My column description"
            mode = "override"
            business_context = ""

        result = merger._extract_string_value(FakeColumnConfig())
        assert result == "My column description"

    def test_extract_string_value_fallback_str(self):
        """Lines 624-627: non-standard type → str(value)."""
        from askrita.sqlagent.database.schema_decorators import DescriptionMerger

        manual_config = self._make_manual_config()
        merger = DescriptionMerger(manual_config)
        result = merger._extract_string_value(42)
        assert result == "42"

    def test_combine_text_and_context_with_context(self):
        """Lines 632-634: context provided → joined with ' | '."""
        from askrita.sqlagent.database.schema_decorators import DescriptionMerger

        manual_config = self._make_manual_config()
        DescriptionMerger(manual_config)
        result = DescriptionMerger._combine_text_and_context("desc", "context")
        assert result == "desc | context"

    def test_auto_or_column_fallback_uses_column_name(self):
        """Lines 642-644: no auto_desc + fallback_to_column_name=True → formatted name."""
        from askrita.sqlagent.database.schema_decorators import DescriptionMerger

        manual_config = self._make_manual_config(fallback=True)
        merger = DescriptionMerger(manual_config)
        result = merger._auto_or_column_fallback(None, "customer_id")
        assert "Customer" in result or "customer" in result.lower()

    def test_merge_supplement_all_parts(self):
        """Lines 650-661: supplement mode with all parts."""
        from askrita.sqlagent.database.schema_decorators import DescriptionMerger

        manual_config = self._make_manual_config()
        merger = DescriptionMerger(manual_config)
        result = merger._merge_supplement(
            "auto desc", "manual text", "biz context", "col_name"
        )
        assert "auto desc" in result
        assert "manual text" in result
        assert "biz context" in result

    def test_merge_supplement_fallback_when_all_empty(self):
        """Lines 659-660: supplement with no parts + fallback → column name."""
        from askrita.sqlagent.database.schema_decorators import DescriptionMerger

        manual_config = self._make_manual_config(fallback=True)
        merger = DescriptionMerger(manual_config)
        result = merger._merge_supplement(None, "", "", "some_column")
        assert result is not None

    def test_merge_column_description_override_mode(self):
        """Lines 691-703: manual_desc with mode=override uses override text."""
        from askrita.sqlagent.database.schema_decorators import DescriptionMerger

        class FakeManualDesc:
            mode = "override"
            description = "Manual override description"
            business_context = ""

        manual_config = self._make_manual_config(columns={"my_col": FakeManualDesc()})
        merger = DescriptionMerger(manual_config)
        result = merger.merge_column_description({}, "my_table", "my_col")
        assert result == "Manual override description"

    def test_merge_column_description_fallback_mode(self):
        """Lines 706-707: fallback mode without auto_desc → returns manual text."""
        from askrita.sqlagent.database.schema_decorators import DescriptionMerger

        class FakeManualDesc:
            mode = "fallback"
            description = "Fallback description"
            business_context = ""

        manual_config = self._make_manual_config(columns={"my_col": FakeManualDesc()})
        merger = DescriptionMerger(manual_config)
        result = merger.merge_column_description({}, "my_table", "my_col")
        assert result == "Fallback description"

    def test_merge_column_description_auto_only_mode_no_auto(self):
        """Line 709: auto_only mode with no auto_desc → None."""
        from askrita.sqlagent.database.schema_decorators import DescriptionMerger

        class FakeManualDesc:
            mode = "auto_only"
            description = ""
            business_context = ""

        manual_config = self._make_manual_config(columns={"my_col": FakeManualDesc()})
        merger = DescriptionMerger(manual_config)
        result = merger.merge_column_description({}, "my_table", "my_col")
        assert result is None

    def test_merge_column_description_auto_only_mode_with_auto(self):
        """Line 709: auto_only mode with auto_desc → returns auto description."""
        from askrita.sqlagent.database.schema_decorators import DescriptionMerger

        class FakeManualDesc:
            mode = "auto_only"
            description = ""
            business_context = ""

        manual_config = self._make_manual_config(columns={"my_col": FakeManualDesc()})
        merger = DescriptionMerger(manual_config)
        auto_descs = {"my_table": {"my_col": "Auto description"}}
        result = merger.merge_column_description(auto_descs, "my_table", "my_col")
        assert result == "Auto description"


class TestHybridDescriptionDecorator:
    def _make_config(self, db_type="PostgreSQL"):
        config = MagicMock()
        config.get_database_type.return_value = db_type
        desc_config = MagicMock()
        desc_config.automatic_extraction.enabled = False
        desc_config.columns = {}
        desc_config.project_context = None
        desc_config.business_terms = {}
        config.get_schema_descriptions.return_value = desc_config
        config.database.connection_string = "postgresql://host/db"
        return config

    def test_extract_automatic_descriptions_postgresql(self):
        """Lines 823-826: PostgreSQL path → empty dict (not implemented)."""
        from askrita.sqlagent.database.schema_decorators import (
            HybridDescriptionDecorator,
        )

        decorator = HybridDescriptionDecorator(MagicMock())
        config = self._make_config(db_type="PostgreSQL")
        result = decorator._extract_automatic_descriptions(config)
        assert result == {}

    def test_extract_automatic_descriptions_mysql(self):
        """Lines 827-830: MySQL path → empty dict (not implemented)."""
        from askrita.sqlagent.database.schema_decorators import (
            HybridDescriptionDecorator,
        )

        decorator = HybridDescriptionDecorator(MagicMock())
        config = self._make_config(db_type="MySQL")
        config.database.connection_string = "mysql://host/db"
        result = decorator._extract_automatic_descriptions(config)
        assert result == {}

    def test_extract_table_name(self):
        """Lines 836-838: _extract_table_name parses CREATE TABLE."""
        from askrita.sqlagent.database.schema_decorators import (
            HybridDescriptionDecorator,
        )

        result = HybridDescriptionDecorator._extract_table_name("CREATE TABLE orders (")
        assert result == "orders"

    def test_extract_table_name_backtick(self):
        """_extract_table_name strips backticks."""
        from askrita.sqlagent.database.schema_decorators import (
            HybridDescriptionDecorator,
        )

        result = HybridDescriptionDecorator._extract_table_name(
            "CREATE TABLE `my.dataset.orders` ("
        )
        assert result == "my.dataset.orders"

    def test_annotate_column_line_no_comma(self):
        """Lines 844-846: line without trailing comma gets comment appended."""
        from askrita.sqlagent.database.schema_decorators import (
            HybridDescriptionDecorator,
        )

        decorator = HybridDescriptionDecorator(MagicMock())
        result = decorator._annotate_column_line("  `col` INTEGER", "A description")
        assert "-- A description" in result

    def test_process_column_line_with_description(self):
        """Lines 857-865: _process_column_line adds description when available."""
        from askrita.sqlagent.database.schema_decorators import (
            DescriptionMerger,
            HybridDescriptionDecorator,
        )

        decorator = HybridDescriptionDecorator(MagicMock())
        manual_config = MagicMock()
        manual_config.columns = {}
        manual_config.automatic_extraction.fallback_to_column_name = False
        merger = DescriptionMerger(manual_config)
        auto_descriptions = {"orders": {"amount": "Order amount in USD"}}
        line = "  amount FLOAT,"
        result = decorator._process_column_line(
            line, "amount FLOAT,", "orders", auto_descriptions, merger
        )
        assert "Order amount in USD" in result

    def test_add_descriptions_to_schema(self):
        """Lines 868-910: _add_descriptions_to_schema processes a CREATE TABLE."""
        from askrita.sqlagent.database.schema_decorators import (
            DescriptionMerger,
            HybridDescriptionDecorator,
        )

        decorator = HybridDescriptionDecorator(MagicMock())

        manual_config = MagicMock()
        manual_config.columns = {}
        manual_config.automatic_extraction.fallback_to_column_name = False
        merger = DescriptionMerger(manual_config)

        schema = "CREATE TABLE orders (\n  id INTEGER,\n  amount FLOAT\n);"
        auto_descriptions = {"orders": {"amount": "Order total"}}
        result = decorator._add_descriptions_to_schema(
            schema, auto_descriptions, merger
        )
        assert isinstance(result, str)
        assert "Order total" in result

    def test_create_business_glossary_non_string_definition(self):
        """Lines 920-929: non-string definition → converted to string."""
        from askrita.sqlagent.database.schema_decorators import (
            HybridDescriptionDecorator,
        )

        decorator = HybridDescriptionDecorator(MagicMock())
        terms = {"KPI": "Key Performance Indicator", "MRR": 12345}  # int value
        result = decorator._create_business_glossary(terms)
        assert "KPI" in result
        assert "12345" in result

    def test_create_business_glossary_none_definition(self):
        """Lines 920-929: None definition → 'No definition provided'."""
        from askrita.sqlagent.database.schema_decorators import (
            HybridDescriptionDecorator,
        )

        decorator = HybridDescriptionDecorator(MagicMock())
        terms = {"TERM": None}
        result = decorator._create_business_glossary(terms)
        assert "No definition provided" in result

    def test_enhance_schema_with_project_context(self):
        """Lines 760-764: project_context adds -- PROJECT header."""
        from askrita.sqlagent.database.schema_decorators import (
            HybridDescriptionDecorator,
        )

        decorator = HybridDescriptionDecorator(MagicMock())
        config = self._make_config()
        desc_config = config.get_schema_descriptions()
        desc_config.project_context = "My Project"
        desc_config.business_terms = {}
        # Need columns to be non-empty so enhance_schema doesn't return early
        desc_config.columns = {"amount": "some_col_desc"}
        schema = "CREATE TABLE orders (id INT);"
        result = decorator.enhance_schema(schema, config)
        assert "My Project" in result

    def test_enhance_schema_with_business_terms(self):
        """Lines 772-774: business_terms adds glossary."""
        from askrita.sqlagent.database.schema_decorators import (
            HybridDescriptionDecorator,
        )

        decorator = HybridDescriptionDecorator(MagicMock())
        config = self._make_config()
        desc_config = config.get_schema_descriptions()
        desc_config.project_context = None
        desc_config.business_terms = {"KPI": "Key metric"}
        desc_config.columns = {"amount": "some_col_desc"}
        schema = "CREATE TABLE orders (id INT);"
        result = decorator.enhance_schema(schema, config)
        assert "KPI" in result
