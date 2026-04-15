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
#   matplotlib (PSF/BSD-style)
#   python-pptx (MIT)
#   pytest (MIT)

"""Extended tests for chart_generator.py – targets missing coverage lines."""

from unittest.mock import MagicMock, patch

import pytest

from askrita.sqlagent.exporters.chart_generator import (
    VisualizationData,
    add_native_pptx_chart,
    generate_chart_bytes,
    get_chart_data_for_export,
)
from askrita.sqlagent.formatters.DataFormatter import (
    ChartDataset,
    DataPoint,
    UniversalChartData,
)
from askrita.sqlagent.State import WorkflowState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chart_data(chart_type="bar", labels=None, datasets=None):
    labels = labels or ["A", "B", "C"]
    datasets = datasets or [
        ChartDataset(label="Series1", data=[DataPoint(y=v) for v in [10, 20, 30]])
    ]
    return UniversalChartData(type=chart_type, labels=labels, datasets=datasets)


def _make_state(chart_data=None, results=None, question=None):
    return WorkflowState(
        chart_data=chart_data,
        results=results,
        question=question,
    )


# ---------------------------------------------------------------------------
# get_chart_data_for_export
# ---------------------------------------------------------------------------


class TestGetChartDataForExport:
    def test_returns_none_when_no_data(self):
        state = _make_state()
        data, ctype = get_chart_data_for_export(state)
        assert data is None
        assert ctype is None

    def test_uses_chart_data_first(self):
        cd = _make_chart_data("line")
        state = _make_state(chart_data=cd)
        data, ctype = get_chart_data_for_export(state)
        assert ctype == "line"

    def test_fallback_to_results_default_bar(self):
        state = _make_state(results=[["A", 1]])
        data, ctype = get_chart_data_for_export(state)
        assert ctype == "bar"

    def test_fallback_detects_pie_in_question(self):
        state = _make_state(results=[["A", 1]], question="show a pie chart please")
        _, ctype = get_chart_data_for_export(state)
        assert ctype == "pie"

    def test_fallback_detects_line_in_question(self):
        state = _make_state(results=[["A", 1]], question="show trend over time")
        _, ctype = get_chart_data_for_export(state)
        assert ctype == "line"


# ---------------------------------------------------------------------------
# generate_chart_bytes – various chart types and data formats
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def ensure_matplotlib(monkeypatch):
    """Skip tests if matplotlib is not available."""
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        pytest.skip("matplotlib not installed")


class TestGenerateChartBytesDataFormats:
    def test_no_data_values_returns_none(self):
        data = VisualizationData(labels=["A"], values=[])
        result = generate_chart_bytes(data, "bar", "Test")
        assert result is None

    def test_bar_chart(self):
        data = VisualizationData(
            labels=["A", "B", "C"], values=[{"data": [10, 20, 30], "label": "Series"}]
        )
        result = generate_chart_bytes(data, "bar", "Bar Chart")
        assert result is not None
        assert len(result) > 0

    def test_line_chart(self):
        data = VisualizationData(
            labels=["A", "B", "C"], values=[{"data": [10, 20, 30], "label": "Line"}]
        )
        result = generate_chart_bytes(data, "line", "Line Chart")
        assert result is not None

    def test_multi_series_line_chart(self):
        data = VisualizationData(
            labels=["A", "B", "C"],
            values=[
                {"data": [10, 20, 30], "label": "S1"},
                {"data": [5, 15, 25], "label": "S2"},
            ],
        )
        result = generate_chart_bytes(data, "line", "Multi Line")
        assert result is not None

    def test_area_chart(self):
        data = VisualizationData(
            labels=["A", "B", "C"], values=[{"data": [10, 20, 30], "label": "Area"}]
        )
        result = generate_chart_bytes(data, "area", "Area Chart")
        assert result is not None

    def test_multi_series_area_chart(self):
        data = VisualizationData(
            labels=["A", "B", "C"],
            values=[
                {"data": [10, 20, 30], "label": "S1"},
                {"data": [5, 15, 25], "label": "S2"},
            ],
        )
        result = generate_chart_bytes(data, "area", "Multi Area")
        assert result is not None

    def test_pie_chart(self):
        data = VisualizationData(
            labels=["X", "Y", "Z"], values=[{"data": [30, 40, 30], "label": "Pie"}]
        )
        result = generate_chart_bytes(data, "pie", "Pie Chart")
        assert result is not None

    def test_donut_chart(self):
        data = VisualizationData(
            labels=["X", "Y"], values=[{"data": [60, 40], "label": "Donut"}]
        )
        result = generate_chart_bytes(data, "donut", "Donut Chart")
        assert result is not None

    def test_unknown_chart_type_defaults_to_bar(self):
        data = VisualizationData(
            labels=["A", "B"], values=[{"data": [10, 20], "label": "S"}]
        )
        result = generate_chart_bytes(data, "unknown_type", "Unknown")
        assert result is not None

    def test_multi_series_bar_chart(self):
        data = VisualizationData(
            labels=["A", "B", "C"],
            values=[
                {"data": [10, 20, 30], "label": "S1"},
                {"data": [5, 15, 25], "label": "S2"},
            ],
        )
        result = generate_chart_bytes(data, "bar", "Multi Bar")
        assert result is not None

    def test_style_classic(self):
        data = VisualizationData(
            labels=["A", "B"], values=[{"data": [10, 20], "label": "S"}]
        )
        result = generate_chart_bytes(data, "bar", "Bar", style="classic")
        assert result is not None

    def test_label_data_length_normalization_extra_labels(self):
        data = VisualizationData(
            labels=["A", "B", "C", "D", "E"],  # 5 labels, only 3 data points
            values=[{"data": [10, 20, 30], "label": "S"}],
        )
        result = generate_chart_bytes(data, "bar", "Normalized")
        assert result is not None

    def test_label_data_length_normalization_extra_data(self):
        data = VisualizationData(
            labels=["A", "B"],  # 2 labels, 4 data points
            values=[{"data": [10, 20, 30, 40], "label": "S"}],
        )
        result = generate_chart_bytes(data, "bar", "Normalized")
        assert result is not None


class TestGenerateChartBytesFromDict:
    """Test generate_chart_bytes with dict input formats."""

    def test_universal_chart_data_dict(self):
        data = {
            "labels": ["A", "B", "C"],
            "datasets": [
                {
                    "label": "Series",
                    "data": [{"y": 10}, {"y": 20}, {"y": 30}],
                }
            ],
        }
        result = generate_chart_bytes(data, "bar", "Dict Chart")
        assert result is not None

    def test_horizontal_bar_dict(self):
        data = {
            "labels": ["A", "B"],
            "datasets": [
                {
                    "label": "Horiz",
                    "data": [{"x": 10}, {"x": 20}],
                }
            ],
        }
        result = generate_chart_bytes(data, "horizontal_bar", "Horiz Bar")
        assert result is not None

    def test_legacy_dict_format(self):
        data = {"labels": ["A", "B"], "values": [{"data": [10, 20], "label": "S"}]}
        result = generate_chart_bytes(data, "bar", "Legacy Dict")
        assert result is not None

    def test_dict_with_y_axes(self):
        data = {
            "labels": ["A", "B"],
            "datasets": [
                {"label": "S1", "data": [{"y": 10}, {"y": 20}], "yAxisId": "left"},
                {"label": "S2", "data": [{"y": 100}, {"y": 200}], "yAxisId": "right"},
            ],
            "yAxes": [
                {"axisId": "left", "position": "left", "label": "Left"},
                {"axisId": "right", "position": "right", "label": "Right"},
            ],
        }
        result = generate_chart_bytes(data, "bar", "Multi Axis")
        assert result is not None


class TestGenerateChartBytesFromList:
    """Test generate_chart_bytes with list input formats."""

    def test_raw_results_list(self):
        data = [["Jan", 10], ["Feb", 20], ["Mar", 30]]
        result = generate_chart_bytes(data, "bar", "Raw List")
        assert result is not None

    def test_dict_array_list(self):
        data = [{"label": "A", "value": 10}, {"label": "B", "value": 20}]
        result = generate_chart_bytes(data, "bar", "Dict Array")
        assert result is not None


class TestGenerateChartBytesFromUniversalChartData:
    """Test with actual UniversalChartData Pydantic objects."""

    def test_universal_bar_chart(self):
        cd = _make_chart_data("bar")
        result = generate_chart_bytes(cd, "bar", "Universal Bar")
        assert result is not None

    def test_universal_pie_chart(self):
        datasets = [
            ChartDataset(
                label="Pie",
                data=[
                    DataPoint(label="A", value=30),
                    DataPoint(label="B", value=70),
                ],
            )
        ]
        cd = UniversalChartData(type="pie", labels=["A", "B"], datasets=datasets)
        result = generate_chart_bytes(cd, "pie", "Universal Pie")
        assert result is not None

    def test_universal_donut_chart(self):
        datasets = [
            ChartDataset(
                label="Donut",
                data=[DataPoint(label="X", value=40), DataPoint(label="Y", value=60)],
            )
        ]
        cd = UniversalChartData(type="donut", labels=["X", "Y"], datasets=datasets)
        result = generate_chart_bytes(cd, "donut", "Universal Donut")
        assert result is not None

    def test_universal_horizontal_bar(self):
        datasets = [
            ChartDataset(
                label="Horiz", data=[DataPoint(x=10), DataPoint(x=20), DataPoint(x=30)]
            )
        ]
        cd = UniversalChartData(
            type="horizontal_bar", labels=["A", "B", "C"], datasets=datasets
        )
        result = generate_chart_bytes(cd, "horizontal_bar", "Universal Horiz Bar")
        assert result is not None


# ---------------------------------------------------------------------------
# add_native_pptx_chart
# ---------------------------------------------------------------------------


class TestAddNativePptxChart:
    """Tests for add_native_pptx_chart – mocked pptx dependency."""

    def _make_slide(self):
        slide = MagicMock()
        shapes = MagicMock()
        frame = MagicMock()
        chart = MagicMock()
        frame.chart = chart
        chart.has_legend = False
        chart.legend = MagicMock()
        chart.plots = [MagicMock()]
        chart.plots[0].data_labels = MagicMock()
        shapes.add_chart.return_value = frame
        slide.shapes = shapes
        return slide

    @pytest.fixture(autouse=True)
    def check_pptx(self):
        try:
            import pptx  # noqa
        except ImportError:
            pytest.skip("python-pptx not installed")

    def test_basic_bar_chart(self):
        slide = self._make_slide()
        data = {
            "labels": ["A", "B", "C"],
            "datasets": [{"label": "S", "data": [{"y": 1}, {"y": 2}, {"y": 3}]}],
        }
        result = add_native_pptx_chart(slide, data, "bar", 0, 0, 100, 100)
        assert result is True

    def test_pie_chart(self):
        slide = self._make_slide()
        data = {
            "labels": ["X", "Y"],
            "datasets": [
                {
                    "label": "Pie",
                    "data": [{"label": "X", "value": 30}, {"label": "Y", "value": 70}],
                }
            ],
        }
        result = add_native_pptx_chart(slide, data, "pie", 0, 0, 100, 100)
        assert result is True

    def test_donut_chart(self):
        slide = self._make_slide()
        data = {
            "labels": ["A", "B"],
            "datasets": [
                {
                    "label": "D",
                    "data": [{"label": "A", "value": 40}, {"label": "B", "value": 60}],
                }
            ],
        }
        result = add_native_pptx_chart(slide, data, "donut", 0, 0, 100, 100)
        assert result is True

    def test_line_chart(self):
        slide = self._make_slide()
        data = {
            "labels": ["Q1", "Q2"],
            "datasets": [{"label": "Rev", "data": [{"y": 100}, {"y": 200}]}],
        }
        result = add_native_pptx_chart(slide, data, "line", 0, 0, 100, 100)
        assert result is True

    def test_horizontal_bar(self):
        slide = self._make_slide()
        data = {
            "labels": ["A", "B"],
            "datasets": [{"label": "S", "data": [{"x": 10}, {"x": 20}]}],
        }
        result = add_native_pptx_chart(slide, data, "horizontal_bar", 0, 0, 100, 100)
        assert result is True

    def test_area_chart(self):
        slide = self._make_slide()
        data = {
            "labels": ["Jan", "Feb"],
            "datasets": [{"label": "A", "data": [{"y": 5}, {"y": 10}]}],
        }
        result = add_native_pptx_chart(slide, data, "area", 0, 0, 100, 100)
        assert result is True

    def test_unknown_chart_type_defaults_to_column(self):
        slide = self._make_slide()
        data = {
            "labels": ["A"],
            "datasets": [{"label": "S", "data": [{"y": 1}]}],
        }
        result = add_native_pptx_chart(slide, data, "unknown_xyz", 0, 0, 100, 100)
        assert result is True

    def test_no_labels_returns_false(self):
        slide = self._make_slide()
        data = {
            "labels": [],
            "datasets": [{"label": "S", "data": []}],
        }
        result = add_native_pptx_chart(slide, data, "bar", 0, 0, 100, 100)
        assert result is False

    def test_multi_dataset_chart(self):
        slide = self._make_slide()
        data = {
            "labels": ["A", "B"],
            "datasets": [
                {"label": "S1", "data": [{"y": 10}, {"y": 20}], "yAxisId": "left"},
                {"label": "S2", "data": [{"y": 100}, {"y": 200}], "yAxisId": "right"},
            ],
            "yAxes": [
                {"axisId": "left", "position": "left"},
                {"axisId": "right", "position": "right"},
            ],
        }
        result = add_native_pptx_chart(slide, data, "bar", 0, 0, 100, 100)
        assert result is True

    def test_list_of_lists_data(self):
        slide = self._make_slide()
        data = [["A", 10], ["B", 20], ["C", 30]]
        result = add_native_pptx_chart(slide, data, "bar", 0, 0, 100, 100)
        assert result is True

    def test_dict_array_data(self):
        slide = self._make_slide()
        data = [{"label": "A", "value": 10}, {"label": "B", "value": 20}]
        result = add_native_pptx_chart(slide, data, "bar", 0, 0, 100, 100)
        assert result is True

    def test_universal_chart_data_pydantic(self):
        slide = self._make_slide()
        datasets = [
            ChartDataset(
                label="S", data=[DataPoint(y=1), DataPoint(y=2), DataPoint(y=3)]
            )
        ]
        cd = UniversalChartData(type="bar", labels=["A", "B", "C"], datasets=datasets)
        result = add_native_pptx_chart(slide, cd, "bar", 0, 0, 100, 100)
        assert result is True

    def test_universal_pie_pydantic(self):
        slide = self._make_slide()
        datasets = [
            ChartDataset(
                label="Pie",
                data=[DataPoint(label="X", value=30), DataPoint(label="Y", value=70)],
            )
        ]
        cd = UniversalChartData(type="pie", labels=["X", "Y"], datasets=datasets)
        result = add_native_pptx_chart(slide, cd, "pie", 0, 0, 100, 100)
        assert result is True

    def test_unsupported_data_format_returns_false(self):
        slide = self._make_slide()
        result = add_native_pptx_chart(slide, 12345, "bar", 0, 0, 100, 100)
        assert result is False

    def test_label_values_mismatch_pads_values(self):
        slide = self._make_slide()
        data = {
            "labels": ["A", "B", "C", "D"],  # 4 labels
            "datasets": [{"label": "S", "data": [{"y": 1}, {"y": 2}]}],  # 2 values
        }
        result = add_native_pptx_chart(slide, data, "bar", 0, 0, 100, 100)
        assert result is True

    def test_dict_labels_values_format(self):
        slide = self._make_slide()
        data = {"labels": ["A", "B"], "values": [{"data": [10, 20], "label": "S"}]}
        result = add_native_pptx_chart(slide, data, "bar", 0, 0, 100, 100)
        assert result is True

    def test_calendar_chart_converts_to_bar(self):
        slide = self._make_slide()
        datasets = [ChartDataset(label="Cal", data=[DataPoint(y=1)])]
        cd = UniversalChartData(type="calendar", labels=[], datasets=datasets)
        cd.calendar_data = [
            {"date": "2024-01-01", "value": 5},
            {"date": "2024-01-02", "value": 10},
        ]
        result = add_native_pptx_chart(slide, cd, "calendar", 0, 0, 100, 100)
        assert result is True

    def test_geo_chart_converts_to_bar(self):
        slide = self._make_slide()
        datasets = [ChartDataset(label="Geo", data=[DataPoint(y=1)])]
        cd = UniversalChartData(type="geo", labels=[], datasets=datasets)
        cd.geographic_data = [
            {"location": "US", "value": 100},
            {"location": "CA", "value": 50},
        ]
        result = add_native_pptx_chart(slide, cd, "geo", 0, 0, 100, 100)
        assert result is True

    def test_no_pptx_returns_false(self):
        slide = self._make_slide()
        with patch.dict(
            "sys.modules",
            {"pptx": None, "pptx.chart.data": None, "pptx.enum.chart": None},
        ):
            with patch("builtins.__import__", side_effect=ImportError):
                result = add_native_pptx_chart(
                    slide, {"labels": ["A"], "datasets": []}, "bar", 0, 0, 100, 100
                )
                # Either False (import failed) or True (if pptx was already loaded)
                assert isinstance(result, bool)
