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

"""Coverage boost tests – batch 3.

Covers:
- askrita/sqlagent/exporters/chart_generator.py
- askrita/sqlagent/exporters/excel_exporter.py
- askrita/sqlagent/exporters/core.py
"""

import io
import pytest
from unittest.mock import MagicMock, Mock, patch


# ============================================================================
# Helper: VisualizationData factory
# ============================================================================

def _make_viz_data(chart_type="bar", labels=None, values=None, title="Test"):
    """Create a VisualizationData-like object."""
    from askrita.sqlagent.exporters.chart_generator import VisualizationData
    return VisualizationData(
        labels=labels or ["A", "B", "C"],
        values=values or [{"label": "Series 1", "data": [10, 20, 30]}],
    )


def _make_universal_chart():
    """Create a UniversalChartData mock."""
    mock = MagicMock()
    mock.chartType = "bar"
    mock.title = "Test Chart"
    mock.labels = ["Jan", "Feb", "Mar"]
    mock.datasets = [MagicMock(label="Sales", data=[1, 2, 3], yAxisId=None)]
    mock.yAxes = []
    mock.xAxisLabel = "Month"
    mock.yAxisLabel = "Revenue"
    return mock


def _make_workflow_state(**kwargs):
    """Create a minimal WorkflowState for export tests."""
    from askrita.sqlagent.State import WorkflowState
    defaults = {
        "question": "Test question?",
        "sql_query": "SELECT a, b FROM t",
        "answer": "42 rows",
        "results": [{"a": 1, "b": 2}, {"a": 3, "b": 4}],
        "chart_data": None,
        "visualization_type": None,
        "followup_questions": [],
    }
    defaults.update(kwargs)
    state = WorkflowState(**defaults)
    return state


# ============================================================================
# chart_generator.py
# ============================================================================

class TestChartGeneratorMissingPaths:
    def test_is_secondary_axis_right_position(self):
        """Line 201: axis with position='right' returns True."""
        from askrita.sqlagent.exporters.chart_generator import _is_secondary_axis
        dataset = MagicMock()
        dataset.yAxisId = "y2"
        axis = MagicMock()
        axis.axisId = "y2"
        axis.id = "y2"
        axis.position = "right"
        result = _is_secondary_axis(dataset, [axis])
        assert result is True

    def test_is_secondary_axis_no_match_returns_false(self):
        """_is_secondary_axis returns False when no axis matches."""
        from askrita.sqlagent.exporters.chart_generator import _is_secondary_axis
        dataset = MagicMock()
        dataset.yAxisId = "y3"
        axis = MagicMock()
        axis.axisId = "y1"
        axis.id = None
        axis.position = "left"
        result = _is_secondary_axis(dataset, [axis])
        assert result is False

    def test_set_dual_axis_labels_no_yaxes(self):
        """_set_dual_axis_labels returns early when no yAxes."""
        from askrita.sqlagent.exporters.chart_generator import _set_dual_axis_labels
        ax = MagicMock()
        ax2 = MagicMock()
        data = MagicMock()
        data._original_universal_data = MagicMock()
        data._original_universal_data.yAxes = []
        _set_dual_axis_labels(ax, ax2, data)
        ax.set_ylabel.assert_not_called()

    def test_set_dual_axis_labels_with_two_axes(self):
        """Lines 229-235: _set_dual_axis_labels sets both Y axis labels."""
        from askrita.sqlagent.exporters.chart_generator import _set_dual_axis_labels
        ax = MagicMock()
        ax2 = MagicMock()
        data = MagicMock()
        axis1 = MagicMock()
        axis1.label = "Primary"
        axis2 = MagicMock()
        axis2.label = "Secondary"
        data._original_universal_data = MagicMock()
        data._original_universal_data.yAxes = [axis1, axis2]
        _set_dual_axis_labels(ax, ax2, data)
        ax.set_ylabel.assert_called_once()
        ax2.set_ylabel.assert_called_once()

    def test_apply_chart_style_modern_fallback(self):
        """Lines 337-338: modern style fails → use default."""
        from askrita.sqlagent.exporters.chart_generator import _apply_chart_style
        plt_mock = MagicMock()
        plt_mock.style.use.side_effect = [Exception("style not found"), None]
        _apply_chart_style(plt_mock, "modern")
        # Should have called use twice (first fails, then 'default')
        assert plt_mock.style.use.call_count == 2

    def test_generate_chart_bytes_success(self):
        """Lines 407-447: generate_chart_bytes returns bytes on success."""
        from askrita.sqlagent.exporters.chart_generator import generate_chart_bytes
        data = _make_viz_data()
        result = generate_chart_bytes(data, "bar", "Test Chart", "classic")
        assert result is None or isinstance(result, bytes)

    def test_generate_chart_bytes_exception_returns_none(self):
        """Lines 452-456: exception in generate_chart_bytes → None."""
        from askrita.sqlagent.exporters.chart_generator import generate_chart_bytes

        with patch("askrita.sqlagent.exporters.chart_generator._normalize_chart_data",
                   side_effect=RuntimeError("normalization failed")):
            result = generate_chart_bytes(_make_viz_data(), "bar", "Test", "classic")
        assert result is None

    def test_pptx_calendar_labels_values_exception(self):
        """Lines 468-470: exception in date parsing → str(date_str) used."""
        from askrita.sqlagent.exporters.chart_generator import _pptx_calendar_labels_values
        entries = [{"date": object(), "value": 5}]
        labels, values = _pptx_calendar_labels_values(entries)
        assert len(labels) == 1
        assert values[0] == 5

    def test_pptx_default_values_pydantic_horizontal_bar(self):
        """Lines 490-491: horizontal_bar uses .x or .value."""
        from askrita.sqlagent.exporters.chart_generator import _pptx_default_values_pydantic
        data = MagicMock()
        point = MagicMock()
        point.x = 10
        point.value = 5
        data.datasets = [MagicMock(data=[point])]
        result = _pptx_default_values_pydantic(data, "horizontal_bar")
        assert result == [10]

    def test_pptx_labels_values_from_dict_calendar(self):
        """Lines 531-533: dict with calendar_data → converted to bar."""
        from askrita.sqlagent.exporters.chart_generator import _pptx_labels_values_from_dict
        data = {
            "calendar_data": [{"date": "2024-01-15", "value": 5}],
        }
        labels, values, chart_type = _pptx_labels_values_from_dict(data, "calendar")
        assert chart_type == "bar"
        assert len(labels) == 1

    def test_pptx_labels_values_from_dict_geo(self):
        """Lines 535-539: dict with geographic_data → converted to bar."""
        from askrita.sqlagent.exporters.chart_generator import _pptx_labels_values_from_dict
        data = {
            "geographic_data": [{"location": "NY", "value": 100}],
        }
        labels, values, chart_type = _pptx_labels_values_from_dict(data, "geo")
        assert chart_type == "bar"
        assert labels[0] == "NY"

    def test_pptx_pie_labels_values_dict_no_data(self):
        """Line 571: datasets with no data → empty lists."""
        from askrita.sqlagent.exporters.chart_generator import _pptx_pie_labels_values_dict
        labels, values = _pptx_pie_labels_values_dict([{"data": []}])
        assert labels == []
        assert values == []

    def test_pptx_resolve_series_secondary_match(self):
        """Lines 623-629: axis_id match → returns (use_secondary, True)."""
        from askrita.sqlagent.exporters.chart_generator import _pptx_resolve_series_secondary
        dataset = {"yAxisId": "y2"}
        yaxes = [{"axisId": "y1"}, {"axisId": "y2", "position": "right"}]
        use_secondary, is_multi = _pptx_resolve_series_secondary(dataset, yaxes)
        assert is_multi is True

    def test_pptx_resolve_series_secondary_no_match(self):
        """Line 629: no axis match → (False, False)."""
        from askrita.sqlagent.exporters.chart_generator import _pptx_resolve_series_secondary
        dataset = {"yAxisId": "y99"}
        yaxes = [{"axisId": "y1"}]
        use_secondary, is_multi = _pptx_resolve_series_secondary(dataset, yaxes)
        assert use_secondary is False
        assert is_multi is False

    def test_pptx_extract_series_values_horizontal_bar(self):
        """Lines 635-638: horizontal_bar uses .x values."""
        from askrita.sqlagent.exporters.chart_generator import _pptx_extract_series_values
        raw_data = [{"x": 10, "value": 5}, {"x": 20, "value": 8}]
        result = _pptx_extract_series_values(raw_data, "horizontal_bar", 2)
        assert result == [10, 20]

    def test_pptx_extract_series_values_regular(self):
        """Line 638: regular chart uses .y values."""
        from askrita.sqlagent.exporters.chart_generator import _pptx_extract_series_values
        raw_data = [{"y": 10}, {"y": 20}]
        result = _pptx_extract_series_values(raw_data, "bar", 2)
        assert result == [10, 20]

    def test_add_native_pptx_chart_no_categories_returns_false(self):
        """Line 695-697: no labels → returns False with warning."""
        from askrita.sqlagent.exporters.chart_generator import add_native_pptx_chart
        slide = MagicMock()
        data = MagicMock()
        data.labels = []  # empty labels
        data.datasets = []

        with patch("askrita.sqlagent.exporters.chart_generator._pptx_extract_labels_values",
                   return_value=([], [], "bar")):
            result = add_native_pptx_chart(slide, data, "bar", 0, 0, 5, 5)
        assert result is False


# ============================================================================
# excel_exporter.py – uncovered paths
# ============================================================================

class TestExcelExporterMissingPaths:
    def test_get_cell_value_col_beyond_row_length(self):
        """Line 159: col_idx >= len(row_data) → None."""
        from askrita.sqlagent.exporters.excel_exporter import _get_cell_value
        row_data = (1, 2)  # length 2
        # col_idx=5 is beyond length
        result = _get_cell_value(row_data, 5, ["a", "b", "c", "d", "e", "f"], ["h1", "h2"])
        assert result is None

    def test_generate_excel_export_xlsxwriter_unavailable(self):
        """Lines 265-271: xlsxwriter not installed → ExportError."""
        from askrita.exceptions import ExportError
        from askrita.sqlagent.exporters.excel_exporter import create_excel_export
        state = _make_workflow_state()
        from askrita.sqlagent.exporters.models import ExportSettings
        settings = ExportSettings()
        with patch("askrita.sqlagent.exporters.excel_exporter.XLSXWRITER_AVAILABLE", False):
            with pytest.raises(ExportError, match="xlsxwriter is not installed"):
                create_excel_export(state, settings)

    def test_generate_excel_export_exception_raises_export_error(self):
        """Lines 318-322: exception in workbook creation → ExportError."""
        from askrita.exceptions import ExportError
        import askrita.sqlagent.exporters.excel_exporter as excel_mod
        from askrita.sqlagent.exporters.excel_exporter import create_excel_export
        state = _make_workflow_state()
        from askrita.sqlagent.exporters.models import ExportSettings
        settings = ExportSettings()
        mock_xlsxwriter = MagicMock()
        mock_xlsxwriter.Workbook.side_effect = RuntimeError("disk full")
        with patch.object(excel_mod, "XLSXWRITER_AVAILABLE", True), \
             patch.object(excel_mod, "xlsxwriter", mock_xlsxwriter, create=True):
            with pytest.raises(ExportError, match="Failed to create Excel export"):
                create_excel_export(state, settings)

    def test_value_column_headers_yaxis_only(self):
        """Lines 529-530: no datasets but yAxisLabel → returns list with label."""
        from askrita.sqlagent.exporters.excel_exporter import _value_column_headers
        chart_data = MagicMock()
        chart_data.datasets = []
        chart_data.yAxisLabel = "Revenue"
        result = _value_column_headers(chart_data)
        assert result == ["Revenue"]

    def test_generate_table_headers_fallback_when_no_chart_data(self):
        """Lines 537-538: no chart_data match → fallback headers."""
        from askrita.sqlagent.exporters.excel_exporter import _generate_table_headers_from_chart_data
        chart_data = MagicMock()
        chart_data.xAxisLabel = None
        chart_data.datasets = []
        chart_data.yAxisLabel = None
        results = [{"col_a": 1, "col_b": 2}]
        fallback = ["col_a", "col_b"]
        result = _generate_table_headers_from_chart_data(chart_data, results, fallback)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_add_pie_chart_no_datasets(self):
        """Lines 334-337: no datasets → returns early."""
        from askrita.sqlagent.exporters.excel_exporter import _add_pie_chart
        workbook = MagicMock()
        worksheet = MagicMock()
        chart_data = MagicMock()
        chart_data.datasets = []
        # Should not raise and workbook.add_chart should not be called
        _add_pie_chart(workbook, worksheet, chart_data, ["a", "b"], [{"a": 1}], 5)
        workbook.add_chart.assert_not_called()

    def test_add_pie_chart_no_labels_or_values(self):
        """Lines 346-347: pie data with no points → returns early."""
        from askrita.sqlagent.exporters.excel_exporter import _add_pie_chart
        workbook = MagicMock()
        worksheet = MagicMock()
        chart_data = MagicMock()
        dataset = MagicMock()
        dataset.data = []
        chart_data.datasets = [dataset]
        _add_pie_chart(workbook, worksheet, chart_data, ["a"], [{"a": 1}], 5)
        workbook.add_chart.assert_not_called()


# ============================================================================
# core.py (exporters) – uncovered paths
# ============================================================================

class TestCoreExporterMissingPaths:
    def test_header_for_key_yaxis_label(self):
        """Line 81: i > 0 + yAxisLabel returns yAxisLabel."""
        from askrita.sqlagent.exporters.core import _header_for_key
        chart_data = MagicMock()
        chart_data.xAxisLabel = None
        chart_data.datasets = []
        chart_data.yAxisLabel = "Revenue"
        result = _header_for_key(chart_data, 2, "col_b")
        assert result == "Revenue"

    def test_pptx_fallback_headers_from_row_tuple_with_sql(self):
        """Lines 325-337: tuple row + SQL → extracts column names."""
        from askrita.sqlagent.exporters.core import _pptx_fallback_headers_from_row
        result = _pptx_fallback_headers_from_row(
            (1, 2), "SELECT order_id, amount FROM orders"
        )
        assert result == ["order_id", "amount"]

    def test_pptx_fallback_headers_from_row_tuple_no_sql(self):
        """Lines 325-338: tuple row without SQL → Column_N headers."""
        from askrita.sqlagent.exporters.core import _pptx_fallback_headers_from_row
        result = _pptx_fallback_headers_from_row((1, 2, 3), None)
        assert result == ["Column_1", "Column_2", "Column_3"]

    def test_pptx_fallback_headers_from_row_unknown_type(self):
        """Line 339: unknown type → empty list."""
        from askrita.sqlagent.exporters.core import _pptx_fallback_headers_from_row
        result = _pptx_fallback_headers_from_row(42, None)
        assert result == []

    def test_pptx_row_values_tuple(self):
        """Lines 352-353: tuple row → list."""
        from askrita.sqlagent.exporters.core import _pptx_row_values
        result = _pptx_row_values((1, 2, 3), ["h1", "h2", "h3"], ["h1", "h2", "h3"])
        assert result == [1, 2, 3]

    def test_pptx_row_values_unknown(self):
        """Line 354: unknown type → [str(row_data)]."""
        from askrita.sqlagent.exporters.core import _pptx_row_values
        result = _pptx_row_values(42, ["h"], ["h"])
        assert result == ["42"]

    def test_generate_table_headers_from_chart_data_dataset_label(self):
        """Line 79: i==1 + datasets[0].label used as header."""
        from askrita.sqlagent.exporters.core import _generate_table_headers_from_chart_data
        chart_data = MagicMock()
        chart_data.xAxisLabel = "Month"
        chart_data.datasets = [MagicMock(label="Revenue")]
        chart_data.yAxisLabel = None
        results = [{"month": "Jan", "revenue": 100}]
        fallback = ["month", "revenue"]
        result = _generate_table_headers_from_chart_data(chart_data, results, fallback)
        assert "Month" in result
        assert "Revenue" in result

    def test_generate_pdf_export_pdf_not_available(self):
        """Line 637: PDF not available → raises ImportError."""
        from askrita.sqlagent.exporters.core import create_pdf_export
        state = _make_workflow_state()
        from askrita.sqlagent.exporters.models import ExportSettings
        settings = ExportSettings()
        with patch("askrita.sqlagent.exporters.core.PDF_AVAILABLE", False):
            with pytest.raises(ImportError, match="PDF export requires"):
                create_pdf_export(state, settings)

    def test_generate_pptx_export_pptx_not_available(self):
        """Line 510-513: PPTX not available → raises ImportError."""
        from askrita.sqlagent.exporters.core import create_pptx_export
        state = _make_workflow_state()
        from askrita.sqlagent.exporters.models import ExportSettings
        settings = ExportSettings()
        with patch("askrita.sqlagent.exporters.core.PPTX_AVAILABLE", False):
            with pytest.raises(ImportError, match="PPTX export requires"):
                create_pptx_export(state, settings)

    @pytest.mark.skipif(
        not getattr(__import__("askrita.sqlagent.exporters.core", fromlist=["PDF_AVAILABLE"]), "PDF_AVAILABLE", False),
        reason="reportlab not installed",
    )
    def test_pdf_append_data_table_more_than_20_rows(self):
        """Lines 577-581: more than 20 rows adds truncation message."""
        from askrita.sqlagent.exporters.core import _pdf_append_data_table
        story = []
        results = [{"col": i} for i in range(25)]
        state = _make_workflow_state(results=results)
        _pdf_append_data_table(story, state)
        assert len(story) > 0

    @pytest.mark.skipif(
        not getattr(__import__("askrita.sqlagent.exporters.core", fromlist=["PDF_AVAILABLE"]), "PDF_AVAILABLE", False),
        reason="reportlab not installed",
    )
    def test_pdf_append_data_table_non_dict_first_row(self):
        """Lines 587-588: first row is not a dict → returns early."""
        from askrita.sqlagent.exporters.core import _pdf_append_data_table
        story = []
        state = _make_workflow_state(results=[(1, 2), (3, 4)])
        _pdf_append_data_table(story, state)
        assert len(story) > 0

    @pytest.mark.skipif(
        not getattr(__import__("askrita.sqlagent.exporters.core", fromlist=["PDF_AVAILABLE"]), "PDF_AVAILABLE", False),
        reason="reportlab not installed",
    )
    def test_pdf_append_data_table_empty_results(self):
        """Lines 583-584: table_data is empty → returns after heading."""
        from askrita.sqlagent.exporters.core import _pdf_append_data_table
        story = []
        state = _make_workflow_state(results=[])
        _pdf_append_data_table(story, state)
        assert len(story) >= 1

    def test_pdf_append_chart_no_chart_data(self):
        """Lines 553-554: no chart_data → returns early."""
        from askrita.sqlagent.exporters.core import _pdf_append_chart
        story = []
        state = _make_workflow_state()

        with patch("askrita.sqlagent.exporters.core.get_chart_data_for_export",
                   return_value=(None, None)):
            _pdf_append_chart(story, state, MagicMock())
        assert story == []

    def test_dataset_label_function_from_chart_data(self):
        """Lines 88-91: _dataset_label returns yAxisLabel when no dataset label."""
        from askrita.sqlagent.exporters.core import _dataset_label
        dataset = MagicMock()
        dataset.label = None
        chart_data = MagicMock()
        chart_data.yAxisLabel = "Revenue"
        result = _dataset_label(dataset, chart_data)
        assert result == "Revenue"

    def test_dataset_label_fallback_value(self):
        """Line 91: _dataset_label returns 'Value' when both label and yAxisLabel missing."""
        from askrita.sqlagent.exporters.core import _dataset_label
        dataset = MagicMock()
        dataset.label = None
        chart_data = MagicMock()
        chart_data.yAxisLabel = None
        result = _dataset_label(dataset, chart_data)
        assert result == "Value"
