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
#   pydantic (MIT)

"""Data formatting and visualization chart data generation using LLM-driven analysis."""

import logging
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from ...utils.LLMManager import LLMManager

logger = logging.getLogger(__name__)


class DataPoint(BaseModel):
    """Universal data point that can represent any chart type."""

    x: Optional[Union[str, int, float]] = Field(
        default=None, description="X-axis value for scatter/line charts"
    )
    y: Optional[Union[int, float]] = Field(
        default=None, description="Y-axis value for most charts"
    )
    value: Optional[Union[int, float]] = Field(
        default=None, description="Value for pie charts"
    )
    label: Optional[str] = Field(
        default=None, description="Label for pie charts or individual points"
    )
    id: Optional[Union[str, int]] = Field(default=None, description="Unique identifier")
    category: Optional[str] = Field(
        default=None, description="Category/group for the data point"
    )


class AxisConfig(BaseModel):
    """Configuration for a chart axis - supports MUI X Charts multi-axis features."""

    axisId: Optional[str] = Field(
        default=None,
        description="Unique identifier for this axis (e.g., 'left-axis', 'right-axis')",
    )
    scaleType: Optional[str] = Field(
        default="linear",
        description="Scale type: 'linear', 'log', 'band', 'point', 'time', 'symlog', etc.",
    )
    position: Optional[str] = Field(
        default=None,
        description="Position: 'left'/'right' for Y-axis, 'top'/'bottom' for X-axis",
    )
    label: Optional[str] = Field(default=None, description="Axis label text")
    min: Optional[Union[int, float]] = Field(
        default=None, description="Minimum value for the axis"
    )
    max: Optional[Union[int, float]] = Field(
        default=None, description="Maximum value for the axis"
    )
    tickFormat: Optional[str] = Field(
        default=None, description="Tick format string (e.g., '.2f' for 2 decimals)"
    )


class ChartDataset(BaseModel):
    """Dataset within a chart - can contain multiple data points."""

    label: str = Field(description="Label for this dataset/series")
    data: List[DataPoint] = Field(description="Array of data points")
    backgroundColor: Optional[List[str]] = Field(
        default=None, description="Background colors for data points"
    )
    borderColor: Optional[List[str]] = Field(
        default=None, description="Border colors for data points"
    )
    yAxisId: Optional[str] = Field(
        default=None,
        description="ID of the Y-axis this series should use (for multi-axis charts)",
    )
    xAxisId: Optional[str] = Field(
        default=None,
        description="ID of the X-axis this series should use (for multi-axis charts)",
    )


class UniversalChartData(BaseModel):
    """
    Universal chart data structure that works for any chart type.
    Supports multi-axis charts for complex visualizations (e.g., combining metrics with different scales).
    Extended to support specialized Google Charts formats.
    """

    type: str = Field(
        description="Chart type: bar, line, pie, scatter, area, combo, gauge, geo, sankey, treemap, timeline, calendar, histogram, table"
    )
    title: Optional[str] = Field(default=None, description="Chart title")
    datasets: List[ChartDataset] = Field(
        default_factory=list,
        description="Array of datasets/series. Empty for specialized chart types (calendar, gauge, geo, sankey, treemap, timeline, histogram) which use their own dedicated fields.",
    )
    labels: Optional[List[Optional[str]]] = Field(
        default=None, description="Category labels (None values will be filtered)"
    )

    # Simple axis labels (for single-axis charts - backward compatible)
    xAxisLabel: Optional[str] = Field(
        default=None, description="X-axis label (simple charts)"
    )
    yAxisLabel: Optional[str] = Field(
        default=None, description="Y-axis label (simple charts)"
    )

    # Advanced multi-axis configuration (for complex charts)
    xAxes: Optional[List[AxisConfig]] = Field(
        default=None, description="Multiple X-axis configurations (advanced)"
    )
    yAxes: Optional[List[AxisConfig]] = Field(
        default=None, description="Multiple Y-axis configurations (advanced)"
    )

    # Specialized chart data structures
    gauge_value: Optional[Union[int, float]] = Field(
        default=None, description="Single value for gauge charts"
    )
    gauge_min: Optional[Union[int, float]] = Field(
        default=0, description="Minimum value for gauge"
    )
    gauge_max: Optional[Union[int, float]] = Field(
        default=100, description="Maximum value for gauge"
    )

    # Geographic data for GeoChart
    geographic_data: Optional[List[Dict[str, Union[str, int, float]]]] = Field(
        default=None,
        description="Geographic data as [{'location': 'US', 'value': 100}]",
    )

    # Hierarchical data for TreeMap
    hierarchical_data: Optional[List[Dict[str, Union[str, int, float]]]] = Field(
        default=None,
        description="Hierarchical data as [{'parent': 'Root', 'child': 'Branch', 'value': 50}]",
    )

    # Flow data for Sankey diagrams
    flow_data: Optional[List[Dict[str, Union[str, int, float]]]] = Field(
        default=None,
        description="Flow data as [{'from': 'A', 'to': 'B', 'weight': 10}]",
    )

    # Timeline events
    timeline_events: Optional[List[Dict[str, Union[str, int]]]] = Field(
        default=None,
        description="Timeline events as [{'id': 'Event1', 'label': 'Description', 'start': timestamp, 'end': timestamp}]",
    )

    # Calendar data (date-value pairs)
    calendar_data: Optional[List[Dict[str, Union[str, int, float]]]] = Field(
        default=None,
        description="Calendar data as [{'date': '2024-01-01', 'value': 50}]",
    )

    # Raw values for histogram
    raw_values: Optional[List[Union[int, float]]] = Field(
        default=None, description="Raw numeric values for histogram distribution"
    )

    # Table data with sparklines
    table_data: Optional[
        List[Dict[str, Union[str, int, float, List[Union[int, float]], None]]]
    ] = Field(
        default=None,
        description="Table rows with embedded sparkline data (None values allowed for missing data)",
    )

    def model_post_init(self, __context):
        """Filter out None values from labels after validation."""
        if self.labels:
            self.labels = [label for label in self.labels if label is not None]


class DualVisualizationResponse(BaseModel):
    """Simplified response model that generates only universal chart format."""

    model_config = {"extra": "forbid"}  # OpenAI structured output requirement

    universal_format: UniversalChartData = Field(
        description="Universal chart data structure for modern chart libraries"
    )


class VisualizationDataResult(BaseModel):
    """Type-safe result from format_data_for_visualization."""

    chart_data: Optional[Union[Dict[str, Any], UniversalChartData]] = Field(
        default=None, description="Universal chart data"
    )


class DataFormatter:
    """Transforms query results into structured chart data for visualization.

    Uses LLM-driven analysis to select appropriate chart types and format data
    into the UniversalChartData schema compatible with Google Charts, MUI X Charts,
    and other frontend charting libraries.
    """

    def __init__(self, config_manager=None, test_llm_connection=True):
        """
        Initialize DataFormatter with configuration.

        Args:
            config_manager: Optional ConfigManager instance. If None, uses global config.
            test_llm_connection: Whether to test LLM connection during initialization (default: True)
        """
        self.config = config_manager
        self.llm_manager = LLMManager(
            config_manager, test_connection=test_llm_connection
        )

    def format_data_for_visualization(self, state) -> Dict[str, Any]:
        """Format the data for the chosen visualization type."""
        # Handle both WorkflowState objects and dict inputs for backward compatibility
        if hasattr(state, "visualization"):
            # WorkflowState object
            visualization = state.visualization or "none"
            results = state.results or []
            question = state.question or ""
            sql_query = state.sql_query or ""
        else:
            # Dict input (for tests and backward compatibility)
            visualization = state.get("visualization") or "none"
            results = state.get("results") or []
            question = state.get("question") or ""
            sql_query = state.get("sql_query") or ""

        # If no visualization is requested or no results available
        if visualization == "none" or not results:
            return {"chart_data": None}

        # Database now ALWAYS returns List[Dict], no string parsing needed!
        # Just validate the format
        if not results or not isinstance(results, list):
            return {"chart_data": None}

        # Use a helper method to ensure chart_data is always populated consistently
        return self._format_with_single_llm_call(
            visualization, question, sql_query, results
        )

    def _get_chart_example_for_visualization(self, visualization: str) -> str:
        """
        Generate chart-specific examples dynamically based on visualization type.
        This is injected as {chart_example} parameter into the prompt template.

        Can return one or more examples depending on the chart type:
        - Simple charts (bar, line, pie): Return single example
        - Combo/multi-axis: Return multiple related examples (bar + line)

        Args:
            visualization: The target chart type (e.g., 'bar', 'line', 'gauge', etc.)

        Returns:
            Chart-specific example(s) in markdown format
        """
        viz_type = visualization.lower()

        # Chart examples library - individual examples that can be combined
        chart_examples = {
            "bar": """**Bar Chart Example:**
```json
{
  "type": "bar",
  "title": "Sales by Product Category",
  "datasets": [
    {
      "label": "2023 Sales",
      "data": [
        {"y": 15000, "category": "Electronics"},
        {"y": 12000, "category": "Clothing"},
        {"y": 8500, "category": "Home"}
      ]
    }
  ],
  "labels": ["Electronics", "Clothing", "Home"],
  "xAxisLabel": "Product Category",
  "yAxisLabel": "Sales ($)"
}
```
**Key Points:** Categories on X-axis, values on Y-axis, use datasets array with DataPoint objects.""",
            "line": """**Line Chart Example:**
```json
{
  "type": "line",
  "title": "Monthly Revenue Trend",
  "datasets": [
    {
      "label": "Revenue",
      "data": [
        {"x": "Jan", "y": 50000},
        {"x": "Feb", "y": 55000},
        {"x": "Mar", "y": 52000}
      ]
    }
  ],
  "labels": ["Jan", "Feb", "Mar"],
  "xAxisLabel": "Month",
  "yAxisLabel": "Revenue ($)"
}
```
**Key Points:** Time/sequential data on X-axis, values on Y-axis, good for trends.""",
            "pie": """**Pie Chart Example:**
```json
{
  "type": "pie",
  "title": "Market Share Distribution",
  "datasets": [
    {
      "label": "Market Share",
      "data": [
        {"label": "Company A", "value": 45},
        {"label": "Company B", "value": 30},
        {"label": "Company C", "value": 25}
      ]
    }
  ],
  "labels": []
}
```
**Key Points:** Proportions of a whole, use label/value pairs in datasets.""",
            "scatter": """**Scatter Chart Example:**
```json
{
  "type": "scatter",
  "title": "Price vs. Sales Correlation",
  "datasets": [
    {
      "label": "Products",
      "data": [
        {"x": 10.5, "y": 150, "id": "Product1"},
        {"x": 15.2, "y": 120, "id": "Product2"},
        {"x": 8.9, "y": 200, "id": "Product3"}
      ]
    }
  ],
  "labels": [],
  "xAxisLabel": "Price ($)",
  "yAxisLabel": "Units Sold"
}
```
**Key Points:** Two numeric variables (X,Y coordinates), good for correlations.""",
            "gauge": """**Gauge Chart Example:**
```json
{
  "type": "gauge",
  "title": "Customer Satisfaction Score",
  "datasets": [],
  "labels": [],
  "gauge_value": 87.5,
  "gauge_min": 0,
  "gauge_max": 100
}
```
**CRITICAL:** For gauge charts, set datasets=[] and use gauge_value, gauge_min, gauge_max fields.""",
            "geo": """**Geographic Chart Example:**
```json
{
  "type": "geo",
  "title": "Sales by Region",
  "datasets": [],
  "labels": [],
  "geographic_data": [
    {"location": "US", "value": 150000},
    {"location": "CA", "value": 85000},
    {"location": "GB", "value": 65000},
    {"location": "DE", "value": 55000}
  ]
}
```
**CRITICAL:** For geo charts, set datasets=[] and use geographic_data. Location can be ISO country codes or region names.""",
            "calendar": """**Calendar Chart Example:**
```json
{
  "type": "calendar",
  "title": "Daily Activity Heatmap",
  "datasets": [],
  "labels": [],
  "calendar_data": [
    {"date": "2024-01-01", "value": 45},
    {"date": "2024-01-02", "value": 67},
    {"date": "2024-01-03", "value": 23},
    {"date": "2024-01-04", "value": 89}
  ]
}
```
**CRITICAL:** For calendar charts, set datasets=[] and use calendar_data. Date must be in YYYY-MM-DD format.""",
            "histogram": """**Histogram Chart Example:**
```json
{
  "type": "histogram",
  "title": "Age Distribution",
  "datasets": [],
  "labels": [],
  "raw_values": [23, 25, 27, 29, 31, 33, 35, 37, 39, 41, 43, 45],
  "xAxisLabel": "Age",
  "yAxisLabel": "Frequency"
}
```
**CRITICAL:** For histogram charts, set datasets=[] and use raw_values. Provide raw numeric values; frontend will bin them.""",
            "sankey": """**Sankey Diagram Example:**
```json
{
  "type": "sankey",
  "title": "Customer Journey Flow",
  "datasets": [],
  "labels": [],
  "flow_data": [
    {"from": "Homepage", "to": "Product Page", "weight": 5000},
    {"from": "Product Page", "to": "Cart", "weight": 2500},
    {"from": "Cart", "to": "Checkout", "weight": 1800},
    {"from": "Checkout", "to": "Purchase", "weight": 1500}
  ]
}
```
**CRITICAL:** For sankey charts, set datasets=[] and use flow_data. from/to are node names, weight is flow amount.""",
            "treemap": """**Treemap Chart Example:**
```json
{
  "type": "treemap",
  "title": "Revenue Breakdown by Category",
  "datasets": [],
  "labels": [],
  "hierarchical_data": [
    {"parent": "Total", "child": "Electronics", "value": 50000},
    {"parent": "Electronics", "child": "Phones", "value": 30000},
    {"parent": "Electronics", "child": "Laptops", "value": 20000},
    {"parent": "Total", "child": "Clothing", "value": 35000}
  ]
}
```
**CRITICAL:** For treemap charts, set datasets=[] and use hierarchical_data. parent/child define hierarchy, value is size.""",
            "timeline": """**Timeline Chart Example:**
```json
{
  "type": "timeline",
  "title": "Project Timeline",
  "datasets": [],
  "labels": [],
  "timeline_events": [
    {"id": "phase1", "label": "Design Phase", "start": 1704067200, "end": 1706745600},
    {"id": "phase2", "label": "Development", "start": 1706745600, "end": 1712016000},
    {"id": "phase3", "label": "Testing", "start": 1712016000, "end": 1714694400}
  ]
}
```
**CRITICAL:** For timeline charts, set datasets=[] and use timeline_events. start/end are Unix timestamps.""",
            "combo": """**Combo Chart Example (Multi-Axis):**
```json
{
  "type": "combo",
  "title": "Response Count vs NPS Score",
  "datasets": [
    {
      "label": "Response Count",
      "data": [{"x": "Q1", "y": 5000}, {"x": "Q2", "y": 6500}],
      "yAxisId": "left-axis"
    },
    {
      "label": "NPS Score",
      "data": [{"x": "Q1", "y": 45}, {"x": "Q2", "y": 52}],
      "yAxisId": "right-axis"
    }
  ],
  "labels": ["Q1", "Q2"],
  "xAxisLabel": "Quarter",
  "yAxes": [
    {"axisId": "left-axis", "position": "left", "label": "Responses"},
    {"axisId": "right-axis", "position": "right", "label": "NPS Score"}
  ]
}
```
**CRITICAL:** For combo/multi-axis charts, use yAxes array and assign datasets to appropriate yAxisId.""",
        }

        # Chart families - each base type has its variants
        # Structure: 'base_type': (['example', 'types'], ['variant1', 'variant2', ...])
        chart_families = {
            "bar": (
                ["bar"],
                [
                    "horizontal_bar",
                    "column",
                    "grouped_bar",
                    "stacked_bar",
                    "vertical_bar",
                ],
            ),
            "line": (["line"], ["area", "spline", "stepped_line", "multi_line"]),
            "pie": (["pie"], ["donut", "doughnut", "ring"]),
            "scatter": (["scatter"], ["bubble", "point"]),
            "gauge": (["gauge"], ["speedometer", "meter", "kpi"]),
            "geo": (["geo"], ["map", "choropleth", "geochart", "geographic"]),
            "calendar": (["calendar"], ["heatmap", "activity"]),
            "histogram": (["histogram"], ["distribution", "frequency"]),
            "sankey": (["sankey"], ["flow", "alluvial"]),
            "treemap": (["treemap"], ["hierarchy", "sunburst"]),
            "timeline": (["timeline"], ["gantt", "schedule"]),
            "combo": (
                ["combo", "bar", "line"],
                ["mixed", "dual_axis", "multi_axis"],
            ),  # Multi-example type
        }

        # Find which family this chart type belongs to
        example_keys = [viz_type]  # Default fallback
        for base_type, (examples, variants) in chart_families.items():
            if viz_type == base_type or viz_type in variants:
                example_keys = examples
                break

        # Build the combined examples
        selected_examples = []
        for key in example_keys:
            if key in chart_examples:
                selected_examples.append(chart_examples[key])

        # If no examples found, return generic message
        if not selected_examples:
            result = f"**{visualization.upper()} Chart:** Follow standard chart structure with appropriate data fields."
            logger.warning(
                f"No specific example found for '{visualization}', using generic template"
            )
        else:
            result = "\n\n".join(selected_examples)
            logger.info(
                f"Generated {len(selected_examples)} chart example(s) for '{visualization}' ({len(result)} chars)"
            )

        return result

    _HARDCODED_SYSTEM_PROMPT = """You are an expert data visualization formatter. Your task is to analyze the provided query results and generate a universal chart data structure.

**CRITICAL REQUIREMENTS:**
- Generate ONLY the universal_format field in your response
- Analyze the data structure to determine appropriate grouping and labeling
- For {visualization} charts, follow the specific format requirements below
- Ensure data types are correct (numbers as numbers, strings as strings)
- Generate meaningful labels and titles based on the question and data

**Chart Type Guidelines:**
- **Bar Charts**: Categories on X-axis, values on Y-axis, good for comparisons
  - Use datasets array with DataPoint objects
- **Line Charts**: Time/sequential data on X-axis, values on Y-axis, good for trends
  - Use datasets array with DataPoint objects
- **Scatter Charts**: Two numeric values (X,Y coordinates), good for correlations
  - Use datasets array with DataPoint objects (x, y values)
- **Pie Charts**: Category/value pairs where values represent parts of a whole
  - Use datasets array with DataPoint objects (label, value)
- **Advanced Charts (calendar, gauge, geo, sankey, treemap, timeline, histogram)**: Use specialized formats
  - Set datasets = [] (empty array)
  - Use appropriate specialized field (calendar_data, geographic_data, etc.)

**Data Analysis Rules:**
1. If data has 2 columns: Usually category + value (bar/pie) or X + Y (line/scatter)
2. If data has 3+ columns: First column typically categories, others are series/values
3. Detect numeric vs categorical data automatically
4. Generate appropriate axis labels based on column names/content
5. Create meaningful chart titles from the question context
6. **CRITICAL**: For advanced charts (calendar, gauge, geo, etc.), use datasets=[] and populate specialized fields

**Multi-Axis Charts (IMPORTANT):**
When data contains multiple metrics with VASTLY DIFFERENT SCALES, you MUST generate multi-axis configuration:
- Example: Response Count (thousands) vs. NPS Score (-100 to +100)
- Example: Revenue ($millions) vs. Customer Count (hundreds)
- Example: Percentage (0-100) vs. Absolute Values (thousands/millions)

For universal_format when multi-axis is needed:
1. Create yAxes array with 2 AxisConfig objects (left and right):
   yAxes: [
     {{"axisId": "left-axis", "position": "left", "label": "Metric 1 Label"}},
     {{"axisId": "right-axis", "position": "right", "label": "Metric 2 Label"}}
   ]
2. Assign each dataset to its appropriate axis via yAxisId:
   datasets: [
     {{"label": "Metric 1", "data": [...], "yAxisId": "left-axis"}},
     {{"label": "Metric 2", "data": [...], "yAxisId": "right-axis"}}
   ]

**How to detect need for multi-axis:**
- Check magnitude difference: If series differ by 10x or more (e.g., 10,000 vs 50)
- Check value ranges: If one is 0-100 (%) and another is thousands
- Check semantics: Different units (count vs score, $ vs %, etc.)"""

    _HARDCODED_HUMAN_PROMPT = """**Analysis Request:**
Question: {question}
SQL Query: {sql_query}
Chart Type: {visualization}
Data Structure: {num_rows} rows x {num_cols} columns

**Sample Data:**
{sample_data}

**Full Data (first 100 rows):**
{data}

**YOUR TASK:**
Generate the universal_format field for this {visualization} chart. Analyze the data and create appropriate chart structure with meaningful labels and proper data formatting."""

    def _load_prompts(self, visualization: str) -> tuple:
        """Load system and human prompts from config or fall back to hardcoded defaults.

        Returns (system_prompt, human_prompt, chart_example, uses_dynamic_examples).
        """
        system_prompt = (
            self.config.get_prompt("format_data_universal", "system")
            if self.config
            else ""
        )
        human_prompt = (
            self.config.get_prompt("format_data_universal", "human")
            if self.config
            else ""
        )
        chart_example = self._get_chart_example_for_visualization(visualization)
        uses_dynamic_examples = (
            "{chart_example}" in system_prompt if system_prompt else False
        )

        if not system_prompt:
            logger.warning(
                "Using hardcoded system prompt for format_data_universal - consider adding to config"
            )
            system_prompt = self._HARDCODED_SYSTEM_PROMPT

        if not human_prompt:
            logger.warning(
                "Using hardcoded human prompt for format_data_universal - consider adding to config"
            )
            human_prompt = self._HARDCODED_HUMAN_PROMPT

        return system_prompt, human_prompt, chart_example, uses_dynamic_examples

    def _build_llm_messages(
        self,
        system_prompt: str,
        human_prompt: str,
        chart_example: str,
        uses_dynamic_examples: bool,
        visualization: str,
        question: str,
        sql_query: str,
        num_rows: int,
        num_cols: int,
        sample_data,
        full_data,
    ) -> list:
        """Assemble the message list for the structured LLM call."""
        base_user_params = dict(
            question=question,
            sql_query=sql_query,
            visualization=visualization,
            num_rows=num_rows,
            num_cols=num_cols,
            sample_data=str(sample_data),
            data=str(full_data),
        )
        if uses_dynamic_examples:
            logger.info(f"Using dynamic chart example injection for '{visualization}'")
            return [
                {
                    "role": "system",
                    "content": system_prompt.format(
                        visualization=visualization, chart_example=chart_example
                    ),
                },
                {
                    "role": "user",
                    "content": human_prompt.format(
                        **base_user_params, chart_example=chart_example
                    ),
                },
            ]
        logger.info(
            f"Using legacy config with all chart examples for '{visualization}'"
        )
        system_content = (
            system_prompt.format(visualization=visualization)
            if "{visualization}" in system_prompt
            else system_prompt
        )
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": human_prompt.format(**base_user_params)},
        ]

    @staticmethod
    def _extract_chart_data_from_response(response) -> Optional[dict]:
        """Pull the universal_format out of the LLM response."""
        if not response.universal_format:
            return None
        if hasattr(response.universal_format, "model_dump"):
            return response.universal_format.model_dump()
        return response.universal_format

    def _format_with_single_llm_call(
        self, visualization: str, question: str, sql_query: str, results: list
    ) -> dict:
        """Generate universal chart format in a single efficient LLM call - no more legacy format."""
        try:
            sample_data = results[:5] if len(results) > 5 else results
            system_prompt, human_prompt, chart_example, uses_dynamic_examples = (
                self._load_prompts(visualization)
            )

            num_rows = len(results)
            num_cols = len(results[0]) if results else 0
            results_limit = (
                getattr(self.config.framework, "results_limit_for_llm", 100)
                if self.config
                else 100
            )
            full_data = (
                results[:results_limit] if len(results) > results_limit else results
            )

            structured_llm = self.llm_manager.llm.with_structured_output(
                DualVisualizationResponse,
                method="function_calling",
            )

            messages = self._build_llm_messages(
                system_prompt,
                human_prompt,
                chart_example,
                uses_dynamic_examples,
                visualization,
                question,
                sql_query,
                num_rows,
                num_cols,
                sample_data,
                full_data,
            )

            response = structured_llm.invoke(messages)
            chart_data = self._extract_chart_data_from_response(response)

            logger.info(
                f"Single LLM call generated universal format for {visualization} chart"
            )
            return {"chart_data": chart_data}

        except Exception as e:
            logger.error(f"Single LLM call formatting failed: {e}")
            raise
