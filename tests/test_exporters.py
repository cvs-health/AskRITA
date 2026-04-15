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
#   python-pptx (MIT)
#   reportlab (BSD-3-Clause)

"""Tests for export functionality (PPTX, PDF, Excel)."""

import pytest

from askrita.sqlagent.exporters.models import ExportSettings
from askrita.sqlagent.exporters.core import create_pptx_export, create_pdf_export
from askrita.sqlagent.exporters.excel_exporter import create_excel_export, XLSXWRITER_AVAILABLE
from askrita.sqlagent.State import WorkflowState

# Check availability of optional export dependencies
try:
    import pptx  # noqa: F401
    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False

try:
    import reportlab  # noqa: F401
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

requires_pptx = pytest.mark.skipif(
    not PPTX_AVAILABLE,
    reason="python-pptx not installed (optional export dependency)"
)
requires_reportlab = pytest.mark.skipif(
    not REPORTLAB_AVAILABLE,
    reason="reportlab not installed (optional export dependency)"
)
requires_xlsxwriter = pytest.mark.skipif(
    not XLSXWRITER_AVAILABLE,
    reason="xlsxwriter not installed (optional export dependency)"
)


@pytest.fixture
def sample_output_state():
    """Sample OutputState for testing exports."""
    return WorkflowState(
        answer="The total sales for 2024 is $1,500,000",
        chart_data={
            "type": "bar",
            "title": "Sales by Quarter",
            "datasets": [
                {
                    "label": "Sales",
                    "data": [
                        {"category": "Q1", "y": 300000},
                        {"category": "Q2", "y": 400000},
                        {"category": "Q3", "y": 350000},
                        {"category": "Q4", "y": 450000}
                    ]
                }
            ],
            "labels": ["Q1", "Q2", "Q3", "Q4"],
            "xAxisLabel": "Quarter",
            "yAxisLabel": "Sales ($)"
        },
        sql_query="SELECT quarter, SUM(sales) FROM sales_data WHERE year = 2024 GROUP BY quarter",
        results=[
            {"quarter": "Q1", "sum": 300000},
            {"quarter": "Q2", "sum": 400000},
            {"quarter": "Q3", "sum": 350000},
            {"quarter": "Q4", "sum": 450000}
        ],
        followup_questions=[
            "What was the average sale per quarter?",
            "How does this compare to 2023?"
        ]
    )


@pytest.fixture
def export_settings():
    """Default export settings."""
    return ExportSettings(
        company_name="Test Company",
        brand_primary_color=(31, 119, 180)
    )


class TestExportSettings:
    """Test ExportSettings model."""

    def test_default_settings(self):
        """Test default export settings."""
        settings = ExportSettings()
        assert settings.brand_primary_color == (0, 47, 135)
        assert settings.brand_secondary_color == (204, 9, 47)
        assert settings.company_name == "Data Analytics"
        assert settings.chart_style == "modern"

    def test_custom_settings(self):
        """Test custom export settings."""
        settings = ExportSettings(
            brand_primary_color=(255, 0, 0),
            company_name="Custom Corp",
            include_sql=True
        )
        assert settings.brand_primary_color == (255, 0, 0)
        assert settings.company_name == "Custom Corp"
        assert settings.include_sql is True


@requires_pptx
class TestPPTXExport:
    """Test PPTX export functionality."""

    def test_create_pptx_export_basic(self, sample_output_state, export_settings):
        """Test basic PPTX export creation."""
        result = create_pptx_export(sample_output_state, export_settings)

        # Should return bytes
        assert isinstance(result, bytes)
        assert len(result) > 0

        # Should be a valid PPTX file (starts with PK for ZIP)
        assert result[:2] == b'PK'

    def test_create_pptx_export_no_chart(self, export_settings):
        """Test PPTX export without chart data."""
        state = WorkflowState(
            answer="Test answer without chart",
            chart_data=None,
            sql_query="SELECT * FROM test",
            results=[{"col1": "value1"}],
            followup_questions=[]
        )

        result = create_pptx_export(state, export_settings)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_create_pptx_export_minimal_state(self, export_settings):
        """Test PPTX export with minimal state."""
        state = WorkflowState(
            answer="Minimal answer",
            sql_query=None,
            results=None,
            chart_data=None,
            followup_questions=None
        )

        result = create_pptx_export(state, export_settings)
        assert isinstance(result, bytes)
        assert len(result) > 0


@requires_reportlab
class TestPDFExport:
    """Test PDF export functionality."""

    def test_create_pdf_export_basic(self, sample_output_state, export_settings):
        """Test basic PDF export creation."""
        result = create_pdf_export(sample_output_state, export_settings)

        # Should return bytes
        assert isinstance(result, bytes)
        assert len(result) > 0

        # Should be a valid PDF file
        assert result[:4] == b'%PDF'

    def test_create_pdf_export_no_chart(self, export_settings):
        """Test PDF export without chart data."""
        state = WorkflowState(
            answer="Test answer without chart",
            chart_data=None,
            sql_query="SELECT * FROM test",
            results=[{"col1": "value1"}],
            followup_questions=[]
        )

        result = create_pdf_export(state, export_settings)
        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result[:4] == b'%PDF'

    def test_create_pdf_export_with_multi_axis(self, export_settings):
        """Test PDF export with multi-axis chart."""
        state = WorkflowState(
            answer="Multi-axis chart test",
            chart_data={
                "type": "bar",
                "title": "Multi-Axis Chart",
                "datasets": [
                    {
                        "label": "Revenue",
                        "data": [{"category": "A", "y": 100}],
                        "yAxisId": "left-axis"
                    },
                    {
                        "label": "Profit %",
                        "data": [{"category": "A", "y": 20}],
                        "yAxisId": "right-axis"
                    }
                ],
                "labels": ["A"],
                "yAxes": [
                    {"axisId": "left-axis", "position": "left"},
                    {"axisId": "right-axis", "position": "right"}
                ]
            },
            sql_query="SELECT * FROM test",
            results=[{"category": "A", "revenue": 100, "profit_pct": 20}],
            followup_questions=[]
        )

        result = create_pdf_export(state, export_settings)
        assert isinstance(result, bytes)
        assert len(result) > 0


@requires_xlsxwriter
class TestExcelExport:
    """Test Excel export functionality."""

    def test_create_excel_export_basic(self, sample_output_state, export_settings):
        """Test basic Excel export creation."""
        result = create_excel_export(sample_output_state, export_settings)

        # Should return bytes
        assert isinstance(result, bytes)
        assert len(result) > 0

        # Should be a valid Excel file (ZIP format)
        assert result[:2] == b'PK'

    def test_create_excel_export_no_chart(self, export_settings):
        """Test Excel export without chart data."""
        state = WorkflowState(
            answer="Test answer without chart",
            chart_data=None,
            sql_query="SELECT * FROM test",
            results=[{"col1": "value1", "col2": 123}],
            followup_questions=[]
        )

        result = create_excel_export(state, export_settings)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_create_excel_export_empty_results(self, export_settings):
        """Test Excel export with empty results."""
        state = WorkflowState(
            answer="No data found",
            chart_data=None,
            sql_query="SELECT * FROM test WHERE 1=0",
            results=[],
            followup_questions=[]
        )

        result = create_excel_export(state, export_settings)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_create_excel_export_multi_axis(self, export_settings):
        """Test Excel export with multi-axis chart."""
        state = WorkflowState(
            answer="Multi-axis chart test",
            chart_data={
                "type": "bar",
                "title": "Multi-Axis Chart",
                "datasets": [
                    {
                        "label": "Revenue",
                        "data": [{"category": "A", "y": 100}, {"category": "B", "y": 200}],
                        "yAxisId": "left-axis"
                    },
                    {
                        "label": "Profit %",
                        "data": [{"category": "A", "y": 20}, {"category": "B", "y": 25}],
                        "yAxisId": "right-axis"
                    }
                ],
                "labels": ["A", "B"],
                "yAxes": [
                    {"axisId": "left-axis", "position": "left", "label": "Revenue ($)"},
                    {"axisId": "right-axis", "position": "right", "label": "Profit (%)"}
                ]
            },
            sql_query="SELECT * FROM test",
            results=[
                {"category": "A", "revenue": 100, "profit_pct": 20},
                {"category": "B", "revenue": 200, "profit_pct": 25}
            ],
            followup_questions=[]
        )

        result = create_excel_export(state, export_settings)
        assert isinstance(result, bytes)
        assert len(result) > 0


class TestExportEdgeCases:
    """Test edge cases and error handling."""

    @requires_pptx
    def test_pptx_with_special_characters(self, export_settings):
        """Test PPTX export with special characters."""
        state = WorkflowState(
            answer="Test with special chars: <>&\"'",
            chart_data=None,
            sql_query="SELECT * FROM test WHERE name = 'O''Reilly'",
            results=[{"name": "O'Reilly & Co."}],
            followup_questions=["What about <tags>?"]
        )

        result = create_pptx_export(state, export_settings)
        assert isinstance(result, bytes)
        assert len(result) > 0

    @requires_reportlab
    def test_pdf_with_long_text(self, export_settings):
        """Test PDF export with very long text."""
        state = WorkflowState(
            answer="A" * 10000,  # Very long answer
            chart_data=None,
            sql_query="SELECT * FROM test",
            results=[{"col": "value"}],
            followup_questions=[]
        )

        result = create_pdf_export(state, export_settings)
        assert isinstance(result, bytes)
        assert len(result) > 0

    @requires_xlsxwriter
    def test_excel_with_various_data_types(self, export_settings):
        """Test Excel export with various data types."""
        state = WorkflowState(
            answer="Mixed data types",
            chart_data=None,
            sql_query="SELECT * FROM test",
            results=[
                {"int_col": 123, "float_col": 45.67, "str_col": "text", "bool_col": True},
                {"int_col": 456, "float_col": 89.01, "str_col": "more", "bool_col": False}
            ],
            followup_questions=[]
        )

        result = create_excel_export(state, export_settings)
        assert isinstance(result, bytes)
        assert len(result) > 0

