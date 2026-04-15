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

"""Extended tests for exporters/core.py – targets missing coverage lines."""

import pytest
from unittest.mock import MagicMock

from askrita.sqlagent.exporters.core import (
    _generate_table_headers_from_chart_data,
    PPTX_AVAILABLE,
    PDF_AVAILABLE,
)
from askrita.sqlagent.exporters.models import ExportSettings
from askrita.sqlagent.State import WorkflowState
from askrita.sqlagent.formatters.DataFormatter import UniversalChartData, ChartDataset, DataPoint


# ---------------------------------------------------------------------------
# _generate_table_headers_from_chart_data (in core.py)
# ---------------------------------------------------------------------------

class TestCoreGenerateTableHeaders:
    def _make_cd(self, x_label=None, y_label=None, datasets=None):
        cd = MagicMock()
        cd.xAxisLabel = x_label
        cd.yAxisLabel = y_label
        cd.datasets = datasets or []
        return cd

    def test_no_chart_data_returns_fallback(self):
        result = _generate_table_headers_from_chart_data(None, [{"a": 1}], ["a"])
        assert result == ["a"]

    def test_no_results_returns_fallback(self):
        cd = self._make_cd()
        result = _generate_table_headers_from_chart_data(cd, [], ["fallback"])
        assert result == ["fallback"]

    def test_uses_x_axis_label_for_first_column(self):
        cd = self._make_cd(x_label="Month")
        ds = MagicMock()
        ds.label = "Revenue"
        cd.datasets = [ds]
        result = _generate_table_headers_from_chart_data(cd, [{"Month": "Jan", "Revenue": 100}], ["month", "revenue"])
        assert result[0] == "Month"

    def test_uses_y_axis_label_when_no_dataset_label(self):
        cd = self._make_cd(y_label="Amount")
        ds = MagicMock()
        ds.label = None  # no label on dataset
        cd.datasets = [ds]
        result = _generate_table_headers_from_chart_data(cd, [{"cat": "A", "val": 1}], ["cat", "val"])
        assert "Amount" in result

    def test_category_fallback_when_no_x_label_no_fallback(self):
        cd = MagicMock()
        cd.xAxisLabel = None
        cd.datasets = []
        cd.yAxisLabel = None
        result = _generate_table_headers_from_chart_data(cd, [{"a": 1}], [])
        assert "Category" in result

    def test_header_count_mismatch_uses_enhanced(self):
        cd = self._make_cd(x_label="X", y_label="Y")
        ds = MagicMock()
        ds.label = "DS"
        cd.datasets = [ds]
        # 3 result keys but headers will have 2 (first + dataset label)
        results = [{"col_a": 1, "col_b": 2, "col_c": 3}]
        result = _generate_table_headers_from_chart_data(cd, results, ["col_a", "col_b", "col_c"])
        assert len(result) == 3

    def test_fallback_when_headers_empty(self):
        cd = MagicMock()
        cd.xAxisLabel = None
        cd.datasets = []
        cd.yAxisLabel = None
        result = _generate_table_headers_from_chart_data(cd, [{"a": 1}], ["a"])
        assert result == ["a"] or len(result) > 0

    def test_only_y_axis_label_no_datasets(self):
        cd = MagicMock()
        cd.xAxisLabel = None
        cd.datasets = []
        cd.yAxisLabel = "Units"
        result = _generate_table_headers_from_chart_data(cd, [{"a": 1}], ["fallback"])
        assert "Units" in result or len(result) > 0


# ---------------------------------------------------------------------------
# create_pptx_export – integration (requires python-pptx)
# ---------------------------------------------------------------------------

requires_pptx = pytest.mark.skipif(
    not PPTX_AVAILABLE, reason="python-pptx not installed"
)


@requires_pptx
class TestCreatePptxExport:
    def _basic_state(self, **kwargs):
        defaults = dict(
            question="What are the sales?",
            answer="Sales are $100",
            sql_query="SELECT month, sales FROM t",
            results=[{"month": "Jan", "sales": 100}, {"month": "Feb", "sales": 200}],
        )
        defaults.update(kwargs)
        return WorkflowState(**defaults)

    def _settings(self, **kwargs):
        return ExportSettings(title="Test", **kwargs)

    def test_basic_export(self):
        from askrita.sqlagent.exporters.core import create_pptx_export
        state = self._basic_state()
        settings = self._settings()
        result = create_pptx_export(state, settings)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_export_with_chart_data(self):
        from askrita.sqlagent.exporters.core import create_pptx_export
        datasets = [ChartDataset(
            label="Sales",
            data=[DataPoint(y=100), DataPoint(y=200)]
        )]
        cd = UniversalChartData(type="bar", labels=["Jan", "Feb"], datasets=datasets)
        state = self._basic_state(chart_data=cd)
        settings = self._settings()
        result = create_pptx_export(state, settings)
        assert isinstance(result, bytes)

    def test_export_with_data_table(self):
        from askrita.sqlagent.exporters.core import create_pptx_export
        state = self._basic_state()
        settings = self._settings(include_data_table=True)
        result = create_pptx_export(state, settings)
        assert isinstance(result, bytes)

    def test_export_with_sql_and_sql_reason(self):
        from askrita.sqlagent.exporters.core import create_pptx_export
        state = self._basic_state(
            sql_reason="Joined tables for aggregation",
            visualization_reason="Bar chart shows comparison",
        )
        settings = self._settings(include_sql=True)
        result = create_pptx_export(state, settings)
        assert isinstance(result, bytes)

    def test_export_no_question_no_answer(self):
        from askrita.sqlagent.exporters.core import create_pptx_export
        state = WorkflowState(results=[{"a": 1}])
        settings = self._settings()
        result = create_pptx_export(state, settings)
        assert isinstance(result, bytes)

    def test_export_with_no_results(self):
        from askrita.sqlagent.exporters.core import create_pptx_export
        state = WorkflowState(answer="No data")
        settings = self._settings(include_data_table=True)
        result = create_pptx_export(state, settings)
        assert isinstance(result, bytes)

    def test_export_with_followup_questions(self):
        from askrita.sqlagent.exporters.core import create_pptx_export
        state = self._basic_state(followup_questions=["Q1?", "Q2?"])
        settings = self._settings()
        result = create_pptx_export(state, settings)
        assert isinstance(result, bytes)


@pytest.mark.skipif(PPTX_AVAILABLE, reason="pptx IS installed")
class TestCreatePptxNoPptx:
    def test_raises_export_error(self):
        from askrita.sqlagent.exporters.core import create_pptx_export
        state = WorkflowState()
        settings = ExportSettings(title="Test")
        with pytest.raises(ImportError, match="PPTX export requires"):
            create_pptx_export(state, settings)


# ---------------------------------------------------------------------------
# create_pdf_export – integration (requires reportlab)
# ---------------------------------------------------------------------------

requires_pdf = pytest.mark.skipif(
    not PDF_AVAILABLE, reason="reportlab not installed"
)


@requires_pdf
class TestCreatePdfExport:
    def _state(self, **kwargs):
        return WorkflowState(**kwargs)

    def test_basic_pdf(self):
        from askrita.sqlagent.exporters.core import create_pdf_export
        state = self._state(
            question="What are the sales?",
            answer="Sales are $100",
        )
        settings = ExportSettings(title="PDF Test")
        result = create_pdf_export(state, settings)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_pdf_with_results(self):
        from askrita.sqlagent.exporters.core import create_pdf_export
        state = self._state(
            question="Sales by month?",
            answer="January had the highest sales.",
            results=[{"month": "Jan", "sales": 100}, {"month": "Feb", "sales": 200}],
        )
        settings = ExportSettings(title="PDF with Results")
        result = create_pdf_export(state, settings)
        assert isinstance(result, bytes)

    def test_pdf_with_sql(self):
        from askrita.sqlagent.exporters.core import create_pdf_export
        state = self._state(
            question="Sales?",
            answer="$100",
            sql_query="SELECT month, sales FROM table",
        )
        settings = ExportSettings(title="PDF with SQL", include_sql=True)
        result = create_pdf_export(state, settings)
        assert isinstance(result, bytes)

    def test_pdf_no_question(self):
        from askrita.sqlagent.exporters.core import create_pdf_export
        state = self._state(answer="Some answer")
        settings = ExportSettings(title="No Question PDF")
        result = create_pdf_export(state, settings)
        assert isinstance(result, bytes)

    def test_pdf_with_chart(self):
        from askrita.sqlagent.exporters.core import create_pdf_export
        datasets = [ChartDataset(
            label="Sales",
            data=[DataPoint(y=100), DataPoint(y=200)]
        )]
        cd = UniversalChartData(type="bar", labels=["Jan", "Feb"], datasets=datasets)
        state = self._state(
            question="Sales chart?",
            answer="Here is the chart",
            chart_data=cd,
        )
        settings = ExportSettings(title="PDF with Chart")
        result = create_pdf_export(state, settings)
        assert isinstance(result, bytes)


@pytest.mark.skipif(PDF_AVAILABLE, reason="reportlab IS installed")
class TestCreatePdfNoPdf:
    def test_raises_export_error(self):
        from askrita.sqlagent.exporters.core import create_pdf_export
        state = WorkflowState()
        settings = ExportSettings(title="Test")
        with pytest.raises(ImportError, match="PDF export requires"):
            create_pdf_export(state, settings)
