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

"""Tests for graph_instructions module – ensures all instruction strings are loaded."""

from askrita.sqlagent import graph_instructions as gi


class TestGraphInstructions:
    """Test that all chart instruction strings exist and are non-empty."""

    def test_module_level_dict_exists(self):
        assert hasattr(gi, "graph_instructions")
        assert isinstance(gi.graph_instructions, dict)

    def test_all_expected_chart_types_present(self):
        expected = [
            "bar",
            "horizontal_bar",
            "line",
            "pie",
            "scatter",
            "area",
            "donut",
            "radar",
            "heatmap",
            "bubble",
            "gauge",
            "funnel",
            "treemap",
            "waterfall",
            "histogram",
            "box",
            "candlestick",
            "polar",
            "sankey",
            "sunburst",
        ]
        for chart_type in expected:
            assert (
                chart_type in gi.graph_instructions
            ), f"Missing chart type: {chart_type}"

    def test_all_instructions_are_strings(self):
        for chart_type, instruction in gi.graph_instructions.items():
            assert isinstance(
                instruction, str
            ), f"{chart_type} instruction is not a string"

    def test_all_instructions_non_empty(self):
        for chart_type, instruction in gi.graph_instructions.items():
            assert len(instruction.strip()) > 0, f"{chart_type} instruction is empty"

    # Individual instruction string sanity checks
    def test_bar_instruction_has_labels(self):
        assert "labels" in gi.barGraphIntstruction

    def test_horizontal_bar_instruction_has_values(self):
        assert "values" in gi.horizontalBarGraphIntstruction

    def test_line_instruction_has_x_values(self):
        assert "xValues" in gi.lineGraphIntstruction

    def test_pie_instruction_has_data(self):
        assert "data" in gi.pieChartIntstruction

    def test_scatter_instruction_has_series(self):
        assert "series" in gi.scatterPlotIntstruction

    def test_area_instruction_has_fill(self):
        assert "fill" in gi.areaGraphInstruction

    def test_donut_instruction_has_inner_radius(self):
        assert "innerRadius" in gi.donutChartInstruction

    def test_radar_instruction_has_datasets(self):
        assert "datasets" in gi.radarChartInstruction

    def test_heatmap_instruction_has_x_labels(self):
        assert "xLabels" in gi.heatmapInstruction

    def test_bubble_instruction_has_size(self):
        assert "size" in gi.bubbleChartInstruction

    def test_gauge_instruction_has_thresholds(self):
        assert "thresholds" in gi.gaugeChartInstruction

    def test_funnel_instruction_has_percentage(self):
        assert "percentage" in gi.funnelChartInstruction

    def test_treemap_instruction_has_children(self):
        assert "children" in gi.treemapInstruction

    def test_waterfall_instruction_has_type(self):
        assert "type" in gi.waterfallInstruction

    def test_histogram_instruction_has_bins(self):
        assert "bins" in gi.histogramInstruction

    def test_box_instruction_has_median(self):
        assert "median" in gi.boxPlotInstruction

    def test_candlestick_instruction_has_ohlc(self):
        instr = gi.candlestickInstruction
        assert (
            "open" in instr and "high" in instr and "low" in instr and "close" in instr
        )

    def test_polar_instruction_has_background_color(self):
        assert "backgroundColor" in gi.polarAreaInstruction

    def test_sankey_instruction_has_nodes_and_links(self):
        assert "nodes" in gi.sankeyInstruction
        assert "links" in gi.sankeyInstruction

    def test_sunburst_instruction_has_children(self):
        assert "children" in gi.sunburstInstruction

    def test_dict_maps_to_module_level_variables(self):
        assert gi.graph_instructions["bar"] is gi.barGraphIntstruction
        assert gi.graph_instructions["line"] is gi.lineGraphIntstruction
        assert gi.graph_instructions["pie"] is gi.pieChartIntstruction
