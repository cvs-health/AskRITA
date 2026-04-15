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

"""Tests for DataFormatter functionality."""

import pytest
import os
from unittest.mock import Mock, patch

from askrita.sqlagent.State import WorkflowState
from askrita.sqlagent.formatters.DataFormatter import DataFormatter

_TEST_QUESTION = "Test question"
_SELECT_ALL_SQL = "SELECT * FROM test"
_PRODUCT_A = "Product A"
_PRODUCT_B = "Product B"
_CATEGORY_A = "Category A"
_CATEGORY_B = "Category B"
_STRUCTURED_OUTPUT_FAILED = "Structured output failed"
_LABEL_A = "Label A"
_LABEL_B = "Label B"
_REGION_A = "Region A"
_REGION_B = "Region B"


@pytest.fixture(autouse=True)
def mock_openai_api_key():
    """Automatically mock OPENAI_API_KEY for all data formatter tests."""
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-api-key'}):
        yield


class TestDataFormatter:
    """Test cases for DataFormatter class."""

    def test_initialization(self, mock_config, mock_llm_manager):
        """Test DataFormatter initialization."""
        with patch('askrita.sqlagent.formatters.DataFormatter.LLMManager', create=True) as mock_llm_class:
            mock_llm_class.return_value = mock_llm_manager

            data_formatter = DataFormatter(mock_config, test_llm_connection=False)

            # Verify basic initialization without strict object comparison
            assert data_formatter.config == mock_config
            assert hasattr(data_formatter, 'llm_manager')
            assert data_formatter.llm_manager is not None

class TestFormatDataForVisualization:
    """Test data formatting for different visualization types."""

    def test_format_data_none_visualization(self, mock_data_formatter):
        """Test formatting when visualization is 'none'."""
        state = WorkflowState(
            visualization="none",
            results=[],
            question=_TEST_QUESTION,
            sql_query=_SELECT_ALL_SQL
        )

        result = mock_data_formatter.format_data_for_visualization(state)

        assert result["chart_data"] is None

    def test_format_data_scatter_plot_two_columns(self, mock_data_formatter, visualization_test_data):
        """Test scatter plot formatting with 2 columns."""
        state = WorkflowState(
            visualization="scatter",
            results=visualization_test_data["scatter_plot_2_cols"],
            question="Test scatter plot",
            sql_query="SELECT x, y FROM data"
        )

        result = mock_data_formatter.format_data_for_visualization(state)

        # Only check chart_data (legacy format completely removed)
        assert result["chart_data"] is not None

        # Check UniversalChartData structure
        chart_data = result["chart_data"]
        # Handle both Pydantic object and dict formats
        if hasattr(chart_data, 'model_dump'):
            chart_dict = chart_data.model_dump()
        else:
            chart_dict = chart_data

        # Verify we get a valid scatter chart structure
        assert chart_dict["type"] == "scatter"
        assert "datasets" in chart_dict
        assert len(chart_dict["datasets"]) >= 1

        # Check that datasets contain data points
        first_dataset = chart_dict["datasets"][0]
        assert "data" in first_dataset
        assert len(first_dataset["data"]) >= 1

    def test_format_data_scatter_plot_three_columns(self, mock_data_formatter, visualization_test_data):
        """Test scatter plot formatting with 3 columns (grouped data)."""
        state = WorkflowState(
            visualization="scatter",
            results=visualization_test_data["scatter_plot_3_cols"],
            question="Test grouped scatter plot",
            sql_query="SELECT group, x, y FROM data"
        )

        result = mock_data_formatter.format_data_for_visualization(state)

        # Only check chart_data (legacy format completely removed)
        assert result["chart_data"] is not None

        # Check UniversalChartData structure
        chart_data = result["chart_data"]
        # Handle both Pydantic object and dict formats
        if hasattr(chart_data, 'model_dump'):
            chart_dict = chart_data.model_dump()
        else:
            chart_dict = chart_data

        # Verify we get a valid scatter chart structure
        assert chart_dict["type"] == "scatter"
        assert "datasets" in chart_dict
        assert len(chart_dict["datasets"]) >= 1

    def test_format_data_bar_chart_two_columns(self, mock_data_formatter, visualization_test_data):
        """Test bar chart formatting with 2 columns."""
        state = WorkflowState(
            visualization="bar",
            results=visualization_test_data["bar_chart_2_cols"],
            question="Product sales",
            sql_query="SELECT product, sales FROM products"
        )

        # Mock LLM response for UniversalChartData generation
        from askrita.sqlagent.formatters.DataFormatter import UniversalChartData, ChartDataset, DataPoint
        mock_chart_data = UniversalChartData(
            type="bar",
            title="Product Sales",
            datasets=[
                ChartDataset(
                    label="Sales",
                    data=[
                        DataPoint(label=_PRODUCT_A, value=100.0),
                        DataPoint(label=_PRODUCT_B, value=150.0),
                        DataPoint(label="Product C", value=80.0)
                    ]
                )
            ],
            labels=[_PRODUCT_A, _PRODUCT_B, "Product C"]
        )

        # Set up the mock chain properly
        mock_llm = Mock()
        mock_llm.invoke.return_value = type('MockResponse', (), {
            'universal_format': mock_chart_data
        })()
        mock_data_formatter.llm_manager.llm.with_structured_output.return_value = mock_llm

        result = mock_data_formatter.format_data_for_visualization(state)

        # Only check chart_data (legacy format completely removed)
        assert result["chart_data"] is not None

        # Check UniversalChartData structure
        chart_data = result["chart_data"]
        # Handle both Pydantic object and dict formats
        if hasattr(chart_data, 'model_dump'):
            chart_dict = chart_data.model_dump()
        else:
            chart_dict = chart_data

        # Verify we get a valid bar chart structure (values may come from fixture mock)
        assert chart_dict["type"] == "bar"
        assert "title" in chart_dict
        assert "datasets" in chart_dict
        assert len(chart_dict["datasets"]) >= 1
        assert "labels" in chart_dict

    def test_format_data_bar_chart_three_columns(self, mock_data_formatter, visualization_test_data):
        """Test bar chart formatting with 3 columns (grouped data)."""
        state = WorkflowState(
            visualization="bar",
            results=visualization_test_data["bar_chart_3_cols"],
            question="Quarterly product sales",
            sql_query="SELECT quarter, product, sales FROM quarterly_sales"
        )

        # Mock LLM response for UniversalChartData generation
        from askrita.sqlagent.formatters.DataFormatter import UniversalChartData, ChartDataset, DataPoint
        mock_chart_data = UniversalChartData(
            type="bar",
            title="Quarterly Product Sales",
            datasets=[
                ChartDataset(
                    label="Q1",
                    data=[DataPoint(label=_PRODUCT_A, value=100.0), DataPoint(label=_PRODUCT_B, value=150.0)]
                ),
                ChartDataset(
                    label="Q2",
                    data=[DataPoint(label=_PRODUCT_A, value=120.0), DataPoint(label=_PRODUCT_B, value=180.0)]
                )
            ],
            labels=[_PRODUCT_A, _PRODUCT_B]
        )

        # Set up the mock chain properly
        mock_llm = Mock()
        mock_llm.invoke.return_value = type('MockResponse', (), {
            'universal_format': mock_chart_data
        })()
        mock_data_formatter.llm_manager.llm.with_structured_output.return_value = mock_llm

        result = mock_data_formatter.format_data_for_visualization(state)

        # Only check chart_data (legacy format completely removed)
        assert result["chart_data"] is not None

        # Check UniversalChartData structure
        chart_data = result["chart_data"]
        # Handle both Pydantic object and dict formats
        if hasattr(chart_data, 'model_dump'):
            chart_dict = chart_data.model_dump()
        else:
            chart_dict = chart_data

        # Verify we get a valid bar chart structure (values may come from fixture mock)
        assert chart_dict["type"] == "bar"
        assert "datasets" in chart_dict
        assert len(chart_dict["datasets"]) >= 1

    def test_format_data_line_chart_two_columns(self, mock_data_formatter, visualization_test_data):
        """Test line chart formatting with 2 columns."""
        state = WorkflowState(
            visualization="line",
            results=visualization_test_data["line_chart_2_cols"],
            question="Monthly revenue trend",
            sql_query="SELECT month, revenue FROM monthly_revenue"
        )

        # Mock LLM response for UniversalChartData generation
        from askrita.sqlagent.formatters.DataFormatter import UniversalChartData, ChartDataset, DataPoint
        mock_chart_data = UniversalChartData(
            type="line",
            title="Monthly Revenue Trend",
            datasets=[
                ChartDataset(
                    label="Revenue",
                    data=[
                        DataPoint(label="2023-01", value=1000.0),
                        DataPoint(label="2023-02", value=1200.0),
                        DataPoint(label="2023-03", value=1100.0)
                    ]
                )
            ],
            labels=["2023-01", "2023-02", "2023-03"]
        )

        # Set up the mock chain properly
        mock_llm = Mock()
        mock_llm.invoke.return_value = type('MockResponse', (), {
            'universal_format': mock_chart_data
        })()
        mock_data_formatter.llm_manager.llm.with_structured_output.return_value = mock_llm

        result = mock_data_formatter.format_data_for_visualization(state)

        # Only check chart_data (legacy format completely removed)
        assert result["chart_data"] is not None

        # Check UniversalChartData structure
        chart_data = result["chart_data"]
        # Handle both Pydantic object and dict formats
        if hasattr(chart_data, 'model_dump'):
            chart_dict = chart_data.model_dump()
        else:
            chart_dict = chart_data

        # Verify we get a valid line chart structure (values may come from fixture mock)
        assert chart_dict["type"] == "line"
        assert "datasets" in chart_dict
        assert len(chart_dict["datasets"]) >= 1

    def test_format_data_line_chart_three_columns(self, mock_data_formatter, visualization_test_data):
        """Test line chart formatting with 3 columns (multi-series)."""
        state = WorkflowState(
            visualization="line",
            results=visualization_test_data["line_chart_3_cols"],
            question="Regional revenue trends",
            sql_query="SELECT month, region, revenue FROM regional_revenue"
        )

        # Mock LLM response for y-axis label
        mock_data_formatter.llm_manager.invoke.return_value = "Revenue"

        result = mock_data_formatter.format_data_for_visualization(state)

        # Only check chart_data (legacy format completely removed)
        assert result["chart_data"] is not None

        # Check UniversalChartData structure
        chart_data = result["chart_data"]
        # Handle both Pydantic object and dict formats
        if hasattr(chart_data, 'model_dump'):
            chart_dict = chart_data.model_dump()
        else:
            chart_dict = chart_data

        # Verify we get a valid line chart structure (values may come from fixture mock)
        assert chart_dict["type"] == "line"
        assert "datasets" in chart_dict
        assert len(chart_dict["datasets"]) >= 1

    def test_format_data_horizontal_bar(self, mock_data_formatter, visualization_test_data):
        """Test horizontal bar chart formatting."""
        state = WorkflowState(
            visualization="horizontal_bar",
            results=visualization_test_data["bar_chart_2_cols"],
            question="Product sales",
            sql_query="SELECT product, sales FROM products"
        )

        # Mock LLM response for label generation
        mock_data_formatter.llm_manager.invoke.return_value = "Sales"

        result = mock_data_formatter.format_data_for_visualization(state)

        # Only check chart_data (legacy format completely removed)
        assert result["chart_data"] is not None

        # Check UniversalChartData structure - should be treated as bar chart
        chart_data = result["chart_data"]
        # Handle both Pydantic object and dict formats
        if hasattr(chart_data, 'model_dump'):
            chart_dict = chart_data.model_dump()
        else:
            chart_dict = chart_data

        # Verify we get a valid chart structure (horizontal_bar treated as bar)
        assert chart_dict["type"] in ["bar", "horizontal_bar"]
        assert "datasets" in chart_dict

    def test_format_data_other_visualization_types(self, mock_data_formatter):
        """Test formatting for other visualization types using LLM."""
        state = WorkflowState(
            visualization="pie",
            results=[(_CATEGORY_A, 30), (_CATEGORY_B, 70)],
            question="Category distribution",
            sql_query="SELECT category, count FROM categories"
        )

        # Mock the combined LLM response for the current single-call approach
        from unittest.mock import Mock
        mock_response = Mock()
        mock_response.legacy_format = {
            "data": [{"name": _CATEGORY_A, "value": 30}, {"name": _CATEGORY_B, "value": 70}]
        }
        mock_response.universal_format = Mock()
        mock_response.universal_format.type = "pie"
        mock_response.universal_format.datasets = [
            Mock(label="Data", data=[
                Mock(value=30, label=_CATEGORY_A),
                Mock(value=70, label=_CATEGORY_B)
            ])
        ]
        mock_response.universal_format.model_dump = Mock(return_value={
            "type": "pie",
            "datasets": [{"label": "Data", "data": [{"value": 30, "label": _CATEGORY_A}, {"value": 70, "label": _CATEGORY_B}]}]
        })

        mock_data_formatter.llm_manager.invoke_with_structured_output.return_value = mock_response

        result = mock_data_formatter.format_data_for_visualization(state)

        # Both formats should be present
        assert result["chart_data"] is not None
        assert result["chart_data"] is not None
class TestDataFormatterErrorHandling:
    """Test error handling in data formatting."""

    def test_format_data_invalid_json_results(self, mock_data_formatter):
        """Test handling of invalid data in results."""
        state = WorkflowState(
            visualization="bar",
            results=[],  # Empty results to trigger error handling
            question=_TEST_QUESTION,
            sql_query=_SELECT_ALL_SQL
        )

        result = mock_data_formatter.format_data_for_visualization(state)

        # Should return None for invalid/empty results (legacy format completely removed)
        assert result["chart_data"] is None

    @pytest.mark.skip(reason="disabled")
    def test_format_data_scatter_unexpected_columns(self, mock_data_formatter):
        """Test scatter plot with unexpected number of columns - should return None gracefully."""
        state = WorkflowState(
            visualization="scatter",
            results=[("A", "B", "C", "D")],  # 4 columns instead of 2 or 3
            question=_TEST_QUESTION,
            sql_query=_SELECT_ALL_SQL
        )

        # Mock structured output failure then fallback to manual JSON parsing
        mock_data_formatter.llm_manager.invoke_with_structured_output_direct.side_effect = Exception(_STRUCTURED_OUTPUT_FAILED)
        mock_data_formatter.llm_manager.invoke.return_value = '{"error": "fallback"}'

        result = mock_data_formatter.format_data_for_visualization(state)

        # With fail-fast architecture, unexpected data returns None (caught at outer level)
        assert result["chart_data"] is None

    @pytest.mark.skip(reason="disabled")
    def test_format_data_bar_chart_unexpected_columns(self, mock_data_formatter):
        """Test bar chart with unexpected number of columns."""
        state = WorkflowState(
            visualization="bar",
            results=[("A", "B", "C", "D")],  # 4 columns instead of 2 or 3
            question=_TEST_QUESTION,
            sql_query=_SELECT_ALL_SQL
        )

        # Mock structured output failure then fallback to manual JSON parsing
        mock_data_formatter.llm_manager.invoke_with_structured_output_direct.side_effect = Exception(_STRUCTURED_OUTPUT_FAILED)
        mock_data_formatter.llm_manager.invoke.return_value = '{"error": "fallback"}'

        result = mock_data_formatter.format_data_for_visualization(state)

        # With fail-fast architecture, unexpected data returns None (caught at outer level)
        assert result["chart_data"] is None

    @pytest.mark.skip(reason="disabled")
    def test_format_data_llm_invalid_json_response(self, mock_data_formatter):
        """Test handling of invalid JSON response from LLM."""
        state = WorkflowState(
            visualization="pie",
            results=[("A", 1), ("B", 2)],
            question=_TEST_QUESTION,
            sql_query=_SELECT_ALL_SQL
        )

        # Mock structured output failure and invalid JSON fallback
        mock_data_formatter.llm_manager.invoke_with_structured_output_direct.side_effect = Exception(_STRUCTURED_OUTPUT_FAILED)
        mock_data_formatter.llm_manager.invoke.return_value = "invalid json response"

        result = mock_data_formatter.format_data_for_visualization(state)

        # Should return None when JSON parsing fails
        assert result["chart_data"] is None

    @pytest.mark.skip(reason="disabled")
    def test_format_data_scatter_exception_fallback(self, mock_data_formatter):
        """Test scatter plot formatting with bad data - fail-fast architecture returns None."""
        state = WorkflowState(
            visualization="scatter",
            results=[("A", 1), ("B", 2)],  # String "A" can't be converted to float
            question=_TEST_QUESTION,
            sql_query=_SELECT_ALL_SQL
        )

        # Mock single LLM call to fail, triggering fallback to dual-call approach
        mock_data_formatter.llm_manager.invoke_with_structured_output_direct.side_effect = Exception(_STRUCTURED_OUTPUT_FAILED)

        # Mock the fallback dual-call approach
        mock_data_formatter.llm_manager.invoke.return_value = '{"series": [{"data": [{"x": 1, "y": 100}]}]}'

        result = mock_data_formatter.format_data_for_visualization(state)

        # Fail-fast: bad data results in None (outer layer handles this)
        assert result["chart_data"] is None
        assert "chart_data" in result  # Both fields should be present

    @pytest.mark.skip(reason="disabled")
    def test_format_data_bar_exception_fallback(self, mock_data_formatter):
        """Test bar chart formatting exception fallback."""
        state = WorkflowState(
            visualization="bar",
            results=[("A", 1), ("B", 2)],
            question=_TEST_QUESTION,
            sql_query=_SELECT_ALL_SQL
        )

        # Mock single LLM call to fail, triggering fallback to dual-call approach
        mock_data_formatter.llm_manager.invoke_with_structured_output_direct.side_effect = Exception(_STRUCTURED_OUTPUT_FAILED)

        # Mock the fallback dual-call approach
        mock_data_formatter.llm_manager.invoke.return_value = '{"labels": ["A", "B"], "values": [{"data": [1, 2]}]}'

        result = mock_data_formatter.format_data_for_visualization(state)

        # Should complete successfully using fallback approach
        chart_data = result["chart_data"]
        assert chart_data is not None  # Fallback should still populate data
        assert "chart_data" in result  # Both fields should be present

    @pytest.mark.skip(reason="disabled")
    def test_format_data_line_exception_fallback(self, mock_data_formatter):
        """Test line chart formatting exception fallback."""
        state = WorkflowState(
            visualization="line",
            results=[("A", 1), ("B", 2)],
            question=_TEST_QUESTION,
            sql_query=_SELECT_ALL_SQL
        )

        # Mock single LLM call to fail, triggering fallback to dual-call approach
        mock_data_formatter.llm_manager.invoke_with_structured_output_direct.side_effect = Exception(_STRUCTURED_OUTPUT_FAILED)

        # Mock the fallback dual-call approach
        mock_data_formatter.llm_manager.invoke.return_value = '{"xValues": ["A", "B"], "yValues": [{"data": [1, 2]}]}'

        result = mock_data_formatter.format_data_for_visualization(state)

        # Should complete successfully using fallback approach
        chart_data = result["chart_data"]
        assert chart_data is not None  # Fallback should still populate data
        assert "chart_data" in result  # Both fields should be present


class TestSpecificDataFormats:
    """Test specific data formatting scenarios."""

    def test_line_chart_label_detection(self, mock_data_formatter):
        """Test label detection in line chart with mixed data types (adapted for single LLM call)."""
        # Data where string labels could be in different positions
        results_label_first = [
            (_LABEL_A, "2023-01", 100),
            (_LABEL_B, "2023-01", 150),
            (_LABEL_A, "2023-02", 120),
            (_LABEL_B, "2023-02", 180)
        ]

        state = WorkflowState(
            visualization="line",
            results=results_label_first,
            question="Multi-series trend",
            sql_query="SELECT label, month, value FROM data"
        )

        # Mock structured output with realistic multi-series line chart data
        from unittest.mock import Mock
        mock_response = Mock()
        mock_response.legacy_format = {
            "labels": ["2023-01", "2023-02"],
            "values": [
                {"label": _LABEL_A, "data": [100, 120]},
                {"label": _LABEL_B, "data": [150, 180]}
            ]
        }
        mock_response.universal_format = Mock()
        mock_response.universal_format.type = "line"
        mock_response.universal_format.labels = ["2023-01", "2023-02"]
        mock_response.universal_format.datasets = [
            Mock(label=_LABEL_A, data=[Mock(x="2023-01", y=100), Mock(x="2023-02", y=120)]),
            Mock(label=_LABEL_B, data=[Mock(x="2023-01", y=150), Mock(x="2023-02", y=180)])
        ]
        mock_response.universal_format.model_dump = Mock(return_value={
            "type": "line",
            "labels": ["2023-01", "2023-02"],
            "datasets": [
                {"label": _LABEL_A, "data": [{"x": "2023-01", "y": 100}, {"x": "2023-02", "y": 120}]},
                {"label": _LABEL_B, "data": [{"x": "2023-01", "y": 150}, {"x": "2023-02", "y": 180}]}
            ]
        })

        mock_data_formatter.llm_manager.invoke_with_structured_output.return_value = mock_response

        result = mock_data_formatter.format_data_for_visualization(state)

        # Should detect labels correctly and create multi-series data
        chart_data = result["chart_data"]
        assert chart_data is not None
        # Legacy format checks removed - using UniversalChartData only or "labels" in formatted_data
        # Legacy format checks removed - using UniversalChartData only or "values" in formatted_data

        # Universal format should also be populated
        assert result["chart_data"] is not None
    def test_scatter_plot_label_detection(self, mock_data_formatter):
        """Test label detection in scatter plot with mixed data types."""
        # Test with string labels in first position
        results = [
            ("Group A", 10, 100),
            ("Group A", 20, 150),
            ("Group B", 15, 120)
        ]

        state = WorkflowState(
            visualization="scatter",
            results=results,
            question="Grouped scatter",
            sql_query="SELECT group, x, y FROM data"
        )

        result = mock_data_formatter.format_data_for_visualization(state)

        # Only check chart_data (legacy format completely removed)
        assert result["chart_data"] is not None

        # Check UniversalChartData structure
        chart_data = result["chart_data"]
        # Handle both Pydantic object and dict formats
        if hasattr(chart_data, 'model_dump'):
            chart_dict = chart_data.model_dump()
        else:
            chart_dict = chart_data

        # Verify we get a valid scatter chart structure with grouped data
        assert chart_dict["type"] == "scatter"
        assert "datasets" in chart_dict
        assert len(chart_dict["datasets"]) >= 1

    @pytest.mark.skip(reason="disabled")
    def test_bar_chart_with_string_conversion(self, mock_data_formatter):
        """Test bar chart with values that need string conversion (adapted for single LLM call)."""
        results = [
            (123, 100.5),  # Numeric labels
            (456, 200.3),
            (789, 150.7)
        ]

        state = WorkflowState(
            visualization="bar",
            results=results,
            question="Numeric categories",
            sql_query="SELECT id, value FROM data"
        )

        # Reset and mock structured output with converted numeric labels to strings
        from unittest.mock import Mock
        mock_data_formatter.llm_manager.invoke_with_structured_output_direct.reset_mock()
        mock_data_formatter.llm_manager.invoke_with_structured_output_direct.side_effect = None
        mock_response = Mock()
        mock_response.legacy_format = {
            "labels": ["123", "456", "789"],  # Converted to strings
            "values": [{"label": "Value", "data": [100.5, 200.3, 150.7]}]
        }
        mock_response.universal_format = Mock()
        mock_response.universal_format.dict.return_value = {"type": "bar", "datasets": []}
        mock_data_formatter.llm_manager.invoke_with_structured_output_direct.return_value = mock_response

        result = mock_data_formatter.format_data_for_visualization(state)

        chart_data = result["chart_data"]

        # Labels should be converted to strings
        expected_labels = ["123", "456", "789"]
        assert chart_data["labels"] == expected_labels

        # Values should be converted to floats
        expected_values = [100.5, 200.3, 150.7]
        assert chart_data["values"][0]["data"] == expected_values

    def test_line_chart_date_string_handling(self, mock_data_formatter):
        """Test line chart with date strings that shouldn't be treated as labels (adapted for single LLM call)."""
        results = [
            ("2023-01-01", _REGION_A, 1000),
            ("2023-01-01", _REGION_B, 800),
            ("2023-02-01", _REGION_A, 1200),
            ("2023-02-01", _REGION_B, 900)
        ]

        state = WorkflowState(
            visualization="line",
            results=results,
            question="Regional trends over time",
            sql_query="SELECT date, region, value FROM data"
        )

        # Mock structured output with date-based x-axis and region-based series
        from unittest.mock import Mock
        mock_response = Mock()
        mock_response.legacy_format = {
            "labels": ["2023-01-01", "2023-02-01"],
            "values": [
                {"label": _REGION_A, "data": [1000, 1200]},
                {"label": _REGION_B, "data": [800, 900]}
            ]
        }
        mock_response.universal_format = Mock()
        mock_response.universal_format.type = "line"
        mock_response.universal_format.labels = ["2023-01-01", "2023-02-01"]
        mock_response.universal_format.datasets = [
            Mock(label=_REGION_A, data=[Mock(x="2023-01-01", y=1000), Mock(x="2023-02-01", y=1200)]),
            Mock(label=_REGION_B, data=[Mock(x="2023-01-01", y=800), Mock(x="2023-02-01", y=900)])
        ]
        mock_response.universal_format.model_dump = Mock(return_value={
            "type": "line",
            "labels": ["2023-01-01", "2023-02-01"],
            "datasets": [
                {"label": _REGION_A, "data": [{"x": "2023-01-01", "y": 1000}, {"x": "2023-02-01", "y": 1200}]},
                {"label": _REGION_B, "data": [{"x": "2023-01-01", "y": 800}, {"x": "2023-02-01", "y": 900}]}
            ]
        })

        mock_data_formatter.llm_manager.invoke_with_structured_output.return_value = mock_response

        result = mock_data_formatter.format_data_for_visualization(state)

        # Should handle dates as x-axis values, not as series labels
        chart_data = result["chart_data"]
        assert chart_data is not None

        # Check UniversalChartData structure
        # Handle both Pydantic object and dict formats
        if hasattr(chart_data, 'model_dump'):
            chart_dict = chart_data.model_dump()
        else:
            chart_dict = chart_data

        # Verify we get a valid line chart structure with date handling
        assert chart_dict["type"] == "line"
        assert "datasets" in chart_dict
        assert len(chart_dict["datasets"]) >= 1
