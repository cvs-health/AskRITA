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

"""Extended tests for excel_exporter.py – targets missing coverage lines."""

from unittest.mock import MagicMock

import pytest

from askrita.sqlagent.exporters.excel_exporter import (
    XLSXWRITER_AVAILABLE,
    _build_enhanced_headers,
    _col_to_excel,
    _extract_fallback_headers,
    _find_secondary_series_idx,
    _find_value_columns,
    _first_column_header,
    _generate_table_headers_from_chart_data,
    _get_cell_value,
    _resolve_value_columns,
    _rgb_to_hex,
    _value_column_headers,
    _write_cell_value,
)
from askrita.sqlagent.exporters.models import ExportSettings
from askrita.sqlagent.State import WorkflowState

# ---------------------------------------------------------------------------
# _col_to_excel
# ---------------------------------------------------------------------------


class TestColToExcel:
    def test_first_column(self):
        assert _col_to_excel(0) == "A"

    def test_second_column(self):
        assert _col_to_excel(1) == "B"

    def test_26th_column(self):
        assert _col_to_excel(25) == "Z"

    def test_27th_column(self):
        assert _col_to_excel(26) == "AA"

    def test_52nd_column(self):
        assert _col_to_excel(51) == "AZ"


# ---------------------------------------------------------------------------
# _rgb_to_hex
# ---------------------------------------------------------------------------


class TestRgbToHex:
    def test_black(self):
        assert _rgb_to_hex((0, 0, 0)) == "#000000"

    def test_white(self):
        assert _rgb_to_hex((255, 255, 255)) == "#ffffff"

    def test_red(self):
        assert _rgb_to_hex((255, 0, 0)) == "#ff0000"

    def test_custom_color(self):
        assert _rgb_to_hex((16, 32, 48)) == "#102030"


# ---------------------------------------------------------------------------
# _extract_fallback_headers
# ---------------------------------------------------------------------------


class TestExtractFallbackHeaders:
    def _make_state(self, sql_query=None):
        return WorkflowState(sql_query=sql_query)

    def test_empty_results(self):
        state = self._make_state()
        assert _extract_fallback_headers([], state) == []

    def test_dict_results(self):
        state = self._make_state()
        results = [{"col_a": 1, "col_b": 2}]
        headers = _extract_fallback_headers(results, state)
        assert headers == ["col_a", "col_b"]

    def test_non_tuple_non_dict(self):
        state = self._make_state()
        results = [42]  # not a dict or tuple
        assert _extract_fallback_headers(results, state) == []

    def test_tuple_results_with_sql(self):
        state = self._make_state(sql_query="SELECT name, age FROM users")
        results = [("Alice", 30)]
        headers = _extract_fallback_headers(results, state)
        assert headers == ["name", "age"]

    def test_tuple_results_sql_column_count_mismatch(self):
        state = self._make_state(sql_query="SELECT name, age, city FROM users")
        results = [("Alice", 30)]  # only 2 columns in result
        headers = _extract_fallback_headers(results, state)
        # Mismatch → fallback to Column_1, Column_2
        assert headers == ["Column_1", "Column_2"]

    def test_tuple_results_no_sql(self):
        state = self._make_state()
        results = [("Alice", 30)]
        headers = _extract_fallback_headers(results, state)
        assert headers == ["Column_1", "Column_2"]


# ---------------------------------------------------------------------------
# _get_cell_value
# ---------------------------------------------------------------------------


class TestGetCellValue:
    def test_dict_row(self):
        row = {"name": "Alice", "age": 30}
        val = _get_cell_value(row, 0, ["name", "age"], ["name", "age"])
        assert val == "Alice"

    def test_list_row(self):
        row = ["Alice", 30]
        val = _get_cell_value(row, 1, [], ["col1", "col2"])
        assert val == 30

    def test_out_of_bounds(self):
        row = ["Alice"]
        # When col_idx is beyond both fallback_headers and headers, an IndexError is raised
        with pytest.raises(IndexError):
            _get_cell_value(row, 5, [], ["col1"])

    def test_dict_missing_key(self):
        row = {"name": "Alice"}
        val = _get_cell_value(row, 1, ["name", "age"], ["name", "age"])
        assert val is None


# ---------------------------------------------------------------------------
# _write_cell_value
# ---------------------------------------------------------------------------


class TestWriteCellValue:
    def test_writes_float(self):
        ws = MagicMock()
        formats = {"decimal": "dec_fmt", "number": "num_fmt", "data": "data_fmt"}
        _write_cell_value(ws, 0, 0, 3.14, formats)
        ws.write.assert_called_once_with(0, 0, 3.14, "dec_fmt")

    def test_writes_int(self):
        ws = MagicMock()
        formats = {"decimal": "dec_fmt", "number": "num_fmt", "data": "data_fmt"}
        _write_cell_value(ws, 0, 0, 42, formats)
        ws.write.assert_called_once_with(0, 0, 42, "num_fmt")

    def test_writes_string(self):
        ws = MagicMock()
        formats = {"decimal": "dec_fmt", "number": "num_fmt", "data": "data_fmt"}
        _write_cell_value(ws, 0, 0, "hello", formats)
        ws.write.assert_called_once_with(0, 0, "hello", "data_fmt")


# ---------------------------------------------------------------------------
# _build_enhanced_headers
# ---------------------------------------------------------------------------


class TestBuildEnhancedHeaders:
    def _make_chart_data(self, x_label=None, y_label=None, datasets=None):
        cd = MagicMock()
        cd.xAxisLabel = x_label
        cd.yAxisLabel = y_label
        cd.datasets = datasets or []
        return cd

    def test_uses_x_label_for_first(self):
        dataset = MagicMock()
        dataset.label = "Revenue"
        cd = self._make_chart_data(x_label="Month", datasets=[dataset])
        headers = _build_enhanced_headers(["col0", "col1"], cd)
        assert headers[0] == "Month"
        assert headers[1] == "Revenue"

    def test_uses_y_axis_label_for_remaining(self):
        cd = self._make_chart_data(y_label="Units", datasets=[])
        headers = _build_enhanced_headers(["col0", "col1", "col2"], cd)
        assert headers[2] == "Units"

    def test_title_fallback(self):
        cd = self._make_chart_data()
        headers = _build_enhanced_headers(["some_key"], cd)
        assert headers[0] == "Some_Key"


# ---------------------------------------------------------------------------
# _first_column_header
# ---------------------------------------------------------------------------


class TestFirstColumnHeader:
    def test_uses_x_axis_label(self):
        cd = MagicMock()
        cd.xAxisLabel = "Month"
        assert _first_column_header(cd, ["fallback"]) == "Month"

    def test_uses_fallback_headers(self):
        cd = MagicMock()
        cd.xAxisLabel = None
        assert _first_column_header(cd, ["col_a"]) == "col_a"

    def test_default_category(self):
        cd = MagicMock()
        cd.xAxisLabel = None
        assert _first_column_header(cd, []) == "Category"


# ---------------------------------------------------------------------------
# _value_column_headers
# ---------------------------------------------------------------------------


class TestValueColumnHeaders:
    def test_from_datasets(self):
        ds1 = MagicMock()
        ds1.label = "Revenue"
        ds2 = MagicMock()
        ds2.label = None
        cd = MagicMock()
        cd.datasets = [ds1, ds2]
        cd.yAxisLabel = "Y Axis"
        headers = _value_column_headers(cd)
        assert headers[0] == "Revenue"
        assert headers[1] == "Y Axis"

    def test_from_y_axis_label_no_datasets(self):
        cd = MagicMock()
        cd.datasets = []
        cd.yAxisLabel = "Units"
        headers = _value_column_headers(cd)
        assert headers == ["Units"]

    def test_empty_no_datasets_no_y_label(self):
        cd = MagicMock()
        cd.datasets = []
        cd.yAxisLabel = None
        assert _value_column_headers(cd) == []


# ---------------------------------------------------------------------------
# _generate_table_headers_from_chart_data
# ---------------------------------------------------------------------------


class TestGenerateTableHeaders:
    def _make_cd(self, x_label=None, y_label=None, datasets=None):
        cd = MagicMock()
        cd.xAxisLabel = x_label
        cd.yAxisLabel = y_label
        cd.datasets = datasets or []
        return cd

    def test_no_chart_data(self):
        result = _generate_table_headers_from_chart_data(None, [{"a": 1}], ["a"])
        assert result == ["a"]

    def test_no_results(self):
        cd = self._make_cd()
        result = _generate_table_headers_from_chart_data(cd, [], ["fallback"])
        assert result == ["fallback"]

    def test_header_count_matches(self):
        ds = MagicMock()
        ds.label = "Val"
        cd = self._make_cd(x_label="Cat", datasets=[ds])
        results = [{"Cat": "A", "Val": 10}]
        result = _generate_table_headers_from_chart_data(cd, results, ["Cat", "Val"])
        assert result[0] == "Cat"

    def test_header_count_mismatch_uses_enhanced(self):
        ds = MagicMock()
        ds.label = "V"
        cd = self._make_cd(x_label="C", datasets=[ds])
        # 3 columns in results but headers produces 2
        results = [{"a": 1, "b": 2, "c": 3}]
        result = _generate_table_headers_from_chart_data(cd, results, ["a", "b", "c"])
        assert len(result) == 3

    def test_non_dict_results_returns_headers(self):
        ds = MagicMock()
        ds.label = "V"
        cd = self._make_cd(x_label="C", datasets=[ds])
        results = [["A", 10]]  # list, not dict
        result = _generate_table_headers_from_chart_data(
            cd, results, ["fallback1", "fallback2"]
        )
        # headers generated should be returned if not empty
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# _find_value_columns
# ---------------------------------------------------------------------------


class TestFindValueColumns:
    def _make_dataset(self, label):
        ds = MagicMock()
        ds.label = label
        return ds

    def test_exact_match(self):
        datasets = [self._make_dataset("revenue")]
        headers = ["category", "revenue", "cost"]
        cols = _find_value_columns(datasets, headers)
        assert 1 in cols

    def test_partial_match(self):
        datasets = [self._make_dataset("rev")]
        headers = ["category", "total_revenue"]
        cols = _find_value_columns(datasets, headers)
        assert 1 in cols

    def test_no_match_warns(self):
        datasets = [self._make_dataset("zzz_nonexistent")]
        headers = ["category", "value"]
        cols = _find_value_columns(datasets, headers)
        assert cols == []


# ---------------------------------------------------------------------------
# _find_secondary_series_idx
# ---------------------------------------------------------------------------


class TestFindSecondarySeriesIdx:
    def _make_axis(self, axis_id=None, position=None):
        ax = MagicMock()
        ax.axisId = axis_id
        ax.id = None
        ax.axis_id = None
        ax.position = position
        return ax

    def _make_dataset(self, y_axis_id=None):
        ds = MagicMock()
        ds.yAxisId = y_axis_id
        return ds

    def test_default_second_series(self):
        datasets = [self._make_dataset(), self._make_dataset()]
        idx = _find_secondary_series_idx(datasets, [])
        assert idx == 1

    def test_finds_secondary_axis(self):
        datasets = [
            self._make_dataset(y_axis_id=None),
            self._make_dataset(y_axis_id="right_axis"),
        ]
        axes = [self._make_axis(axis_id="right_axis", position="right")]
        idx = _find_secondary_series_idx(datasets, axes)
        assert idx == 1


# ---------------------------------------------------------------------------
# _resolve_value_columns
# ---------------------------------------------------------------------------


class TestResolveValueColumns:
    def _make_dataset(self, label):
        ds = MagicMock()
        ds.label = label
        return ds

    def test_finds_columns_by_label(self):
        datasets = [self._make_dataset("revenue")]
        headers = ["category", "revenue"]
        cols = _resolve_value_columns(datasets, headers, False)
        assert 1 in cols

    def test_fallback_positional(self):
        datasets = [self._make_dataset("zzz"), self._make_dataset("xxx")]
        headers = ["cat", "val1", "val2"]
        cols = _resolve_value_columns(datasets, headers, has_secondary_axis=True)
        assert cols == [1, 2]  # positional fallback


# ---------------------------------------------------------------------------
# create_excel_export (integration) – requires xlsxwriter
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not XLSXWRITER_AVAILABLE, reason="xlsxwriter not installed")
class TestCreateExcelExport:
    def _basic_state(self, **kwargs):
        defaults = dict(
            question="What are the sales?",
            answer="Sales are $100",
            sql_query="SELECT month, sales FROM table",
            results=[{"month": "Jan", "sales": 100}, {"month": "Feb", "sales": 200}],
        )
        defaults.update(kwargs)
        return WorkflowState(**defaults)

    def _settings(self, **kwargs):
        defaults = dict(
            title="Test Report",
            include_sql=True,
        )
        defaults.update(kwargs)
        return ExportSettings(**defaults)

    def test_basic_export_returns_bytes(self):
        from askrita.sqlagent.exporters.excel_exporter import create_excel_export

        state = self._basic_state()
        settings = self._settings()
        result = create_excel_export(state, settings)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_export_without_results(self):
        from askrita.sqlagent.exporters.excel_exporter import create_excel_export

        state = WorkflowState(answer="No data")
        settings = self._settings()
        result = create_excel_export(state, settings)
        assert isinstance(result, bytes)

    def test_export_with_followup_questions(self):
        from askrita.sqlagent.exporters.excel_exporter import create_excel_export

        state = self._basic_state(followup_questions=["Question 1?", "Question 2?"])
        settings = self._settings()
        result = create_excel_export(state, settings)
        assert isinstance(result, bytes)

    def test_export_with_tuple_results(self):
        from askrita.sqlagent.exporters.excel_exporter import create_excel_export

        state = WorkflowState(
            results=[("Jan", 100), ("Feb", 200)],
            sql_query="SELECT month, sales FROM t",
        )
        settings = self._settings()
        result = create_excel_export(state, settings)
        assert isinstance(result, bytes)

    def test_export_no_sql_in_settings(self):
        from askrita.sqlagent.exporters.excel_exporter import create_excel_export

        state = self._basic_state()
        settings = ExportSettings(title="Test", include_sql=False)
        result = create_excel_export(state, settings)
        assert isinstance(result, bytes)


@pytest.mark.skipif(XLSXWRITER_AVAILABLE, reason="xlsxwriter IS installed")
class TestCreateExcelExportNoXlsxwriter:
    def test_raises_export_error_when_missing(self):
        from askrita.exceptions import ExportError
        from askrita.sqlagent.exporters.excel_exporter import create_excel_export

        state = WorkflowState()
        settings = ExportSettings(title="Test")
        with pytest.raises(ExportError):
            create_excel_export(state, settings)
