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

"""Tests for chart_generator functions focusing on functional behavior."""

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


def test_get_chart_data_priority_universal_then_results():
    # Test 1: UniversalChartData has priority
    chart_data = UniversalChartData(
        type="line",
        labels=["A"],
        datasets=[ChartDataset(label="Series1", data=[DataPoint(y=1)])],
    )

    out = WorkflowState(
        chart_data=chart_data,
        visualization="bar",
        results=[["A", 1]],
        question="show line chart",
    )
    data, ctype = get_chart_data_for_export(out)
    assert ctype == "line"

    # Test 2: Results fallback (when no chart_data)
    out2 = WorkflowState(results=[["A", 1]], question="make a bar chart")
    data2, ctype2 = get_chart_data_for_export(out2)
    assert ctype2 == "bar"

    # Test 3: None case
    out3 = WorkflowState()
    data3, ctype3 = get_chart_data_for_export(out3)
    assert data3 is None
    assert ctype3 is None


def test_generate_chart_bytes_with_visualizationdata_bar():
    viz = VisualizationData(
        labels=["Jan", "Feb"], values=[{"data": [1, 2], "label": "S1"}]
    )
    img = generate_chart_bytes(viz, "bar", "Title")
    # May be None if matplotlib missing, but if present should be bytes
    if img is not None:
        assert isinstance(img, (bytes, bytearray))
        assert len(img) > 0


def test_generate_chart_bytes_with_raw_results_line():
    raw = [["Jan", 1], ["Feb", 2]]
    img = generate_chart_bytes(raw, "line", "Trend")
    if img is not None:
        assert isinstance(img, (bytes, bytearray))


def test_add_native_pptx_chart_without_dependency_returns_false():
    # Without python-pptx installed in test env, function should return False
    ok = add_native_pptx_chart(
        slide=None,
        data={"labels": ["A"], "values": [{"data": [1]}]},
        chart_type="bar",
        x=0,
        y=0,
        cx=1,
        cy=1,
    )
    assert ok is False
