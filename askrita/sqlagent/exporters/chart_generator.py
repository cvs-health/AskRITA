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
#   pydantic (MIT)
#   python-pptx (MIT)

"""Chart generation utilities for exports."""

import io
import logging
from typing import Any, List, Optional, Tuple

from pydantic import BaseModel, Field

from ..State import WorkflowState

logger = logging.getLogger(__name__)


class VisualizationData(BaseModel):
    """Legacy visualization data structure for chart generation."""

    labels: List[str] = Field(default_factory=list)
    values: List[dict] = Field(default_factory=list)


def get_chart_data_for_export(output_state: WorkflowState) -> Tuple[Any, Optional[str]]:
    """
    Get chart data for export, prioritizing new UniversalChartData over legacy format.

    Args:
        output_state: WorkflowState from workflow

    Returns:
        Tuple of (chart_data, chart_type)
    """
    # Priority 1: Use new UniversalChartData if available
    if output_state.chart_data:
        chart_data = output_state.chart_data
        # Extract chart type from UniversalChartData (should be Pydantic object)
        chart_type = chart_data.type if hasattr(chart_data, "type") else "bar"
        return chart_data, chart_type

    # Priority 2: Fallback to raw results with chart type detection
    if output_state.results:
        chart_type = "bar"  # default
        if output_state.question:
            question_lower = output_state.question.lower()
            if "pie" in question_lower:
                chart_type = "pie"
            elif "line" in question_lower or "trend" in question_lower:
                chart_type = "line"

        return output_state.results, chart_type

    return None, None


def _extract_pie_dataset_pydantic(dataset) -> Tuple[List[str], List[Any]]:
    """Extract labels and values from a pie/donut Pydantic dataset."""
    labels: List[str] = []
    values: List[Any] = []
    for point in dataset.data:
        labels.append(point.label or f"Item {len(labels)}")
        values.append(point.value or point.y or 0)
    return labels, values


def _extract_dataset_values_pydantic(dataset, chart_type_lower: str) -> List[Any]:
    """Extract numeric values from a Pydantic dataset for non-pie chart types."""
    if chart_type_lower == "horizontal_bar":
        return [
            (
                point.x
                if point.x is not None
                else (point.value if point.value is not None else 0)
            )
            for point in dataset.data
        ]
    return [point.y or point.value or 0 for point in dataset.data]


def _normalize_chart_data_from_pydantic(data, chart_type: str) -> VisualizationData:
    """Convert UniversalChartData Pydantic object into VisualizationData for rendering."""
    chart_type_lower = chart_type.lower()
    chart_labels = data.labels or []
    chart_datasets = []

    for dataset in data.datasets:
        if chart_type_lower in ["pie", "donut"]:
            chart_labels, pie_values = _extract_pie_dataset_pydantic(dataset)
            chart_datasets = [{"data": pie_values, "label": dataset.label}]
        else:
            values = _extract_dataset_values_pydantic(dataset, chart_type_lower)
            chart_datasets.append({"data": values, "label": dataset.label})

    viz_data = VisualizationData(labels=chart_labels, values=chart_datasets)
    viz_data._original_universal_data = data
    return viz_data


def _build_dict_datasets(raw_datasets: list) -> list:
    """Build a list of simple namespace objects from raw dataset dicts."""
    result = []
    for ds in raw_datasets:
        ds_obj = type("Dataset", (), {})()
        ds_obj.label = ds.get("label", "Series")
        ds_obj.yAxisId = ds.get("yAxisId")
        ds_obj.data = ds.get("data", [])
        result.append(ds_obj)
    return result


def _build_dict_yaxes(raw_yaxes: list) -> list:
    """Build a list of simple namespace objects from raw yAxes dicts."""
    result = []
    for ax in raw_yaxes or []:
        ax_obj = type("Axis", (), {})()
        ax_obj.axisId = ax.get("axisId") or ax.get("id")
        ax_obj.position = ax.get("position")
        ax_obj.label = ax.get("label")
        result.append(ax_obj)
    return result


def _make_universal_chart_data_dict(data_dict: dict):
    """Create a lightweight object mirroring UniversalChartData from a plain dict."""
    obj = type("UniversalChartDataDict", (), {})()
    obj.labels = data_dict.get("labels", [])
    obj.datasets = _build_dict_datasets(data_dict.get("datasets", []))
    obj.yAxes = _build_dict_yaxes(data_dict.get("yAxes") or [])
    return obj


def _normalize_chart_data_from_dict(data: dict, chart_type: str) -> VisualizationData:
    """Convert a UniversalChartData dict into VisualizationData for rendering."""
    chart_labels = data.get("labels", [])
    chart_datasets = []
    for dataset in data.get("datasets", []):
        if chart_type.lower() == "horizontal_bar":
            values = [
                point.get("x", point.get("value", 0))
                for point in dataset.get("data", [])
            ]
        else:
            values = [
                point.get("y", point.get("value", 0))
                for point in dataset.get("data", [])
            ]
        chart_datasets.append({"data": values, "label": dataset.get("label", "Series")})

    viz_data = VisualizationData(labels=chart_labels, values=chart_datasets)
    viz_data._original_universal_data = _make_universal_chart_data_dict(data)
    return viz_data


def _normalize_chart_data_from_list(data: list) -> VisualizationData:
    """Convert a list of raw results or dicts into VisualizationData."""
    if len(data) > 0 and isinstance(data[0], list) and len(data[0]) >= 2:
        logger.info(f"Converting raw results format data with {len(data)} items")
        labels = [str(item[0]) if item[0] is not None else "Unknown" for item in data]
        values = [
            {
                "data": [float(item[1]) if item[1] is not None else 0 for item in data],
                "label": "Data Series",
            }
        ]
    else:
        logger.info(f"Converting dictionary array format data with {len(data)} items")
        labels = [
            (
                str(item.get("label", f"Item {item.get('id', i)}"))
                if item.get("label") is not None
                else "Unknown"
            )
            for i, item in enumerate(data)
        ]
        values = [
            {"data": [item.get("value", 0) for item in data], "label": "Data Series"}
        ]
    return VisualizationData(labels=labels, values=values)


def _normalize_chart_data(data, chart_type: str) -> Optional[VisualizationData]:
    """Dispatch data normalization to the appropriate helper based on data type."""
    if hasattr(data, "datasets"):
        logger.info("Using UniversalChartData format for chart generation")
        return _normalize_chart_data_from_pydantic(data, chart_type)
    if isinstance(data, dict):
        if "labels" in data and "datasets" in data:
            return _normalize_chart_data_from_dict(data, chart_type)
        return VisualizationData(**data)
    if isinstance(data, list):
        return _normalize_chart_data_from_list(data)
    return data  # already VisualizationData


def _is_secondary_axis(dataset, yaxes: list) -> bool:
    """Return True if the dataset's yAxisId maps to a right-positioned axis."""
    if not (hasattr(dataset, "yAxisId") and dataset.yAxisId):
        return False
    for axis in yaxes:
        axis_id = getattr(axis, "axisId", None) or getattr(axis, "id", None)
        if axis_id == dataset.yAxisId and getattr(axis, "position", None) == "right":
            return True
    return False


def _detect_multi_axis(data: VisualizationData) -> Tuple[bool, List[int]]:
    """Return (has_multi_axis, secondary_series_indices) from embedded UniversalChartData."""
    if not hasattr(data, "_original_universal_data"):
        return False, []
    universal_data = data._original_universal_data
    yaxes = getattr(universal_data, "yAxes", None) or []
    if len(yaxes) <= 1:
        return False, []

    logger.info("Multi-axis chart detected for matplotlib rendering")
    secondary_series_indices = [
        i
        for i, dataset in enumerate(universal_data.datasets)
        if _is_secondary_axis(dataset, yaxes)
    ]
    return True, secondary_series_indices


def _set_dual_axis_labels(ax, ax2, data) -> None:
    """Set Y-axis labels from embedded UniversalChartData if available."""
    if not hasattr(data, "_original_universal_data"):
        return
    universal_data = data._original_universal_data
    if not (hasattr(universal_data, "yAxes") and universal_data.yAxes):
        return
    ax.set_ylabel(
        getattr(universal_data.yAxes[0], "label", ""), fontsize=12, fontweight="bold"
    )
    if len(universal_data.yAxes) > 1:
        ax2.set_ylabel(
            getattr(universal_data.yAxes[1], "label", ""),
            fontsize=12,
            fontweight="bold",
        )


def _render_dual_axis_bar(ax, data, colors, secondary_series_indices):
    """Render a dual-axis combo bar+line chart."""
    logger.info(
        f"Creating dual-axis combo chart: {len(data.values)} series, {len(secondary_series_indices)} on secondary axis"
    )
    x_pos = range(len(data.labels))
    width = 0.6
    ax2 = ax.twinx()
    for i, series in enumerate(data.values):
        color = colors[i % len(colors)]
        if i in secondary_series_indices:
            ax2.plot(
                x_pos,
                series["data"],
                marker="o",
                label=series["label"],
                linewidth=2.5,
                markersize=8,
                color=color,
            )
        else:
            ax.bar(
                x_pos,
                series["data"],
                width,
                label=series["label"],
                alpha=0.8,
                color=color,
            )
    ax.set_xticks(x_pos)
    ax.set_xticklabels(data.labels, rotation=45, ha="right")
    _set_dual_axis_labels(ax, ax2, data)
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    ax2.grid(False)


def _render_grouped_bar(ax, data, colors):
    """Render a standard grouped bar chart (single axis, multiple series)."""
    x_pos = range(len(data.labels))
    width = 0.35
    for i, series in enumerate(data.values):
        offset = (i - len(data.values) / 2 + 0.5) * width
        color = colors[i % len(colors)]
        ax.bar(
            [x + offset for x in x_pos],
            series["data"],
            width,
            label=series["label"],
            alpha=0.8,
            color=color,
        )
    ax.set_xticks(x_pos)
    ax.set_xticklabels(data.labels, rotation=45, ha="right")
    ax.legend()


def _render_bar_chart(
    ax, data, colors, has_multi_axis, secondary_series_indices, plt_module
):
    """Render bar or column chart onto ax."""
    if len(data.values) > 1:
        if has_multi_axis and secondary_series_indices:
            _render_dual_axis_bar(ax, data, colors, secondary_series_indices)
        else:
            _render_grouped_bar(ax, data, colors)
    else:
        ax.bar(data.labels, data.values[0]["data"], alpha=0.8, color=colors[0])
        plt_module.xticks(rotation=45, ha="right")


def _render_dual_axis_line(ax, data, colors, secondary_series_indices, plt_module):
    """Render a dual-axis line chart."""
    logger.info(
        f"Creating dual-axis line chart: {len(data.values)} series, {len(secondary_series_indices)} on secondary axis"
    )
    ax2 = ax.twinx()
    for i, series in enumerate(data.values):
        color = colors[i % len(colors)]
        if i in secondary_series_indices:
            ax2.plot(
                data.labels,
                series["data"],
                marker="o",
                label=series["label"],
                linewidth=2.5,
                color=color,
            )
        else:
            ax.plot(
                data.labels,
                series["data"],
                marker="o",
                label=series["label"],
                linewidth=2.5,
                color=color,
            )
    _set_dual_axis_labels(ax, ax2, data)
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    ax2.grid(False)
    plt_module.xticks(rotation=45, ha="right")


def _render_line_chart(
    ax, data, colors, has_multi_axis, secondary_series_indices, plt_module
):
    """Render line chart onto ax."""
    if has_multi_axis and secondary_series_indices:
        _render_dual_axis_line(ax, data, colors, secondary_series_indices, plt_module)
    else:
        for i, series in enumerate(data.values):
            color = colors[i % len(colors)]
            ax.plot(
                data.labels,
                series["data"],
                marker="o",
                label=series["label"],
                linewidth=2.5,
                color=color,
            )
        if len(data.values) > 1:
            ax.legend()
        plt_module.xticks(rotation=45, ha="right")


def _render_pie_donut_chart(ax, fig, data, chart_type_lower, colors):
    """Render pie or donut chart onto ax."""
    if not (data.values and len(data.values) > 0):
        return
    pie_data = data.values[0]["data"]
    pie_labels = data.labels[: len(pie_data)]
    ax.pie(pie_data, labels=pie_labels, autopct="%1.1f%%", startangle=90, colors=colors)
    if chart_type_lower == "donut":
        import matplotlib.pyplot as _plt

        inner_circle = _plt.Circle((0, 0), 0.70, fc="white")
        fig.gca().add_artist(inner_circle)


def _apply_chart_style(plt_module, style: str) -> None:
    """Apply the requested matplotlib style."""
    if style == "modern":
        try:
            plt_module.style.use("seaborn-v0_8-darkgrid")
        except Exception:
            plt_module.style.use("default")


def _normalize_series_lengths(data: VisualizationData) -> None:
    """Trim data series and labels so they have matching lengths (mutates data in place)."""
    max_data_length = max(len(series["data"]) for series in data.values)
    if max_data_length > len(data.labels):
        for series in data.values:
            series["data"] = series["data"][: len(data.labels)]
    elif len(data.labels) > max_data_length:
        data.labels = data.labels[:max_data_length]


def _dispatch_chart_render(
    ax,
    fig,
    data,
    chart_type_lower,
    colors,
    has_multi_axis,
    secondary_series_indices,
    plt_module,
) -> None:
    """Dispatch rendering to the appropriate chart-type helper."""
    if chart_type_lower in ["bar", "column"]:
        _render_bar_chart(
            ax, data, colors, has_multi_axis, secondary_series_indices, plt_module
        )
    elif chart_type_lower == "line":
        _render_line_chart(
            ax, data, colors, has_multi_axis, secondary_series_indices, plt_module
        )
    elif chart_type_lower == "area":
        _render_area_chart(ax, data, colors)
    elif chart_type_lower in ["pie", "donut"]:
        _render_pie_donut_chart(ax, fig, data, chart_type_lower, colors)
    else:
        logger.warning(
            f"Unknown chart type '{chart_type_lower}', defaulting to bar chart"
        )
        ax.bar(data.labels, data.values[0]["data"], alpha=0.8, color=colors[0])
        plt_module.xticks(rotation=45, ha="right")


def _render_area_chart(ax, data, colors) -> None:
    """Render area chart onto ax."""
    for i, series in enumerate(data.values):
        color = colors[i % len(colors)]
        ax.fill_between(
            range(len(data.labels)),
            series["data"],
            alpha=0.7,
            label=series["label"],
            color=color,
        )
    ax.set_xticks(range(len(data.labels)))
    ax.set_xticklabels(data.labels, rotation=45, ha="right")
    if len(data.values) > 1:
        ax.legend()


def _save_chart_to_bytes(plt_module) -> Optional[bytes]:
    """Save current matplotlib figure to PNG bytes and close the figure."""
    img_buffer = io.BytesIO()
    plt_module.savefig(
        img_buffer,
        format="png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
        edgecolor="none",
    )
    plt_module.close()
    img_buffer.seek(0)
    return img_buffer.getvalue() or None


def generate_chart_bytes(
    data, chart_type: str, title: str, style: str = "modern"
) -> Optional[bytes]:
    """
    Generate chart image in memory using matplotlib.

    Args:
        data: Chart data (UniversalChartData, VisualizationData, list, or dict)
        chart_type: Type of chart (bar, line, pie, area, etc.)
        title: Chart title
        style: Visual style ("modern" or "classic")

    Returns:
        bytes: PNG image bytes, or None if generation fails
    """
    try:
        import matplotlib
        import matplotlib.pyplot as plt

        matplotlib.use("Agg")  # Use non-interactive backend
    except ImportError:
        logger.error(
            "Matplotlib is required for chart generation. Install with: pip install askrita[exports]"
        )
        return None

    try:
        data = _normalize_chart_data(data, chart_type)

        logger.info(
            f"Generating {chart_type} chart with {len(data.labels)} labels and {len(data.values)} series"
        )

        if not data.values:
            logger.error("No data series provided for chart")
            return None

        _normalize_series_lengths(data)
        _apply_chart_style(plt, style)

        fig, ax = plt.subplots(figsize=(12, 8))
        chart_type_lower = chart_type.lower()
        colors = [
            "#1f77b4",
            "#ff7f0e",
            "#2ca02c",
            "#d62728",
            "#9467bd",
            "#8c564b",
            "#e377c2",
            "#7f7f7f",
            "#bcbd22",
            "#17becf",
        ]

        has_multi_axis, secondary_series_indices = _detect_multi_axis(data)
        _dispatch_chart_render(
            ax,
            fig,
            data,
            chart_type_lower,
            colors,
            has_multi_axis,
            secondary_series_indices,
            plt,
        )

        if title:
            ax.set_title(title, fontsize=16, fontweight="bold", pad=20)
        if chart_type_lower in ["bar", "column", "line", "area"]:
            ax.grid(True, alpha=0.3)

        plt.tight_layout()
        chart_bytes = _save_chart_to_bytes(plt)

        if chart_bytes:
            logger.info(f"Chart generated successfully: {len(chart_bytes)} bytes")
            return chart_bytes

        logger.error("Chart generation produced empty bytes")
        return None

    except Exception as e:
        logger.error(f"Chart generation failed: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return None


def _pptx_calendar_labels_values(entries: list) -> Tuple[list, list]:
    """Convert calendar_data entries to (labels, values) for PowerPoint."""
    labels, values = [], []
    for entry in entries[:20]:
        date_str = entry.get("date", "Unknown")
        try:
            if isinstance(date_str, str) and len(date_str) >= 10:
                labels.append(f"Day {date_str.split('-')[-1]}")
            else:
                labels.append(str(date_str))
        except Exception:
            labels.append(str(date_str))
        values.append(entry.get("value", 0))
    return labels, values


def _pptx_pie_labels_values_pydantic(data) -> Tuple[list, list]:
    """Extract pie/donut labels and values from a Pydantic dataset."""
    labels: list = []
    values: list = []
    if data.datasets and data.datasets[0].data:
        for point in data.datasets[0].data:
            labels.append(point.label or f"Item {len(labels)}")
            values.append(point.value or point.y or 0)
    return labels, values


def _pptx_default_values_pydantic(data, chart_type_lower: str) -> list:
    """Extract values for bar/line/etc from the first Pydantic dataset."""
    if not (data.datasets and data.datasets[0].data):
        return []
    if chart_type_lower == "horizontal_bar":
        return [point.x or point.value or 0 for point in data.datasets[0].data]
    return [point.y or point.value or 0 for point in data.datasets[0].data]


def _pptx_labels_values_from_pydantic(
    data, chart_type_lower: str
) -> Tuple[list, list, str]:
    """Extract (labels, values, resolved_chart_type) from a Pydantic UniversalChartData object."""
    if chart_type_lower == "calendar" and getattr(data, "calendar_data", None):
        logger.info("Converting calendar chart to bar chart for PowerPoint export")
        labels, values = _pptx_calendar_labels_values(data.calendar_data)
        return labels, values, "bar"

    if chart_type_lower == "geo" and getattr(data, "geographic_data", None):
        logger.info("Converting geo chart to bar chart for PowerPoint export")
        labels = [e.get("location", "Unknown") for e in data.geographic_data[:15]]
        values = [e.get("value", 0) for e in data.geographic_data[:15]]
        return labels, values, "bar"

    if chart_type_lower in ["pie", "donut"]:
        labels, values = _pptx_pie_labels_values_pydantic(data)
        return labels, values, chart_type_lower

    labels = data.labels or []
    values = _pptx_default_values_pydantic(data, chart_type_lower) or [0] * len(labels)
    return labels, values, chart_type_lower


def _pptx_pie_labels_values_dict(datasets: list) -> Tuple[list, list]:
    """Extract pie/donut labels and values from a dict-format dataset list."""
    labels: list = []
    values: list = []
    if datasets and datasets[0].get("data"):
        for point in datasets[0]["data"]:
            labels.append(
                point.get("label") or point.get("category") or f"Item {len(labels)}"
            )
            values.append(point.get("value") or point.get("y") or 0)
    return labels, values


def _pptx_labels_values_from_dict(
    data: dict, chart_type_lower: str
) -> Tuple[list, list, str]:
    """Extract (labels, values, resolved_chart_type) from a UniversalChartData dict."""
    if chart_type_lower == "calendar" and data.get("calendar_data"):
        logger.info("Converting calendar chart to bar chart for PowerPoint export")
        labels, values = _pptx_calendar_labels_values(data["calendar_data"])
        return labels, values, "bar"

    if chart_type_lower == "geo" and data.get("geographic_data"):
        logger.info("Converting geo chart to bar chart for PowerPoint export")
        labels = [e.get("location", "Unknown") for e in data["geographic_data"][:15]]
        values = [e.get("value", 0) for e in data["geographic_data"][:15]]
        return labels, values, "bar"

    datasets = data.get("datasets") or []
    if chart_type_lower in ["pie", "donut"]:
        labels, values = _pptx_pie_labels_values_dict(datasets)
        return labels, values, chart_type_lower

    labels = data.get("labels", [])
    if datasets and datasets[0].get("data"):
        values = [p.get("y") or p.get("value") or 0 for p in datasets[0]["data"]]
    else:
        values = [0] * len(labels)
    return labels, values, chart_type_lower


def _pptx_labels_values_from_list(
    data: list, chart_type_lower: str
) -> Tuple[list, list, str]:
    """Extract (labels, values, chart_type_lower) from a list data format."""
    if data and isinstance(data[0], list) and len(data[0]) >= 2:
        labels = [str(item[0]) if item[0] is not None else "Unknown" for item in data]
        values = [float(item[1]) if item[1] is not None else 0 for item in data]
    else:
        labels = [
            item.get("label", f"Item {item.get('id', i)}")
            for i, item in enumerate(data)
        ]
        values = [item.get("value", 0) for item in data]
    return labels, values, chart_type_lower


def _pptx_labels_values_from_viz_dict(
    data: dict, chart_type_lower: str
) -> Tuple[list, list, str]:
    """Extract (labels, values, chart_type_lower) from a VisualizationData-style dict."""
    labels = data["labels"]
    if data["values"] and "data" in data["values"][0]:
        values = data["values"][0]["data"]
    else:
        values = [0] * len(labels)
    return labels, values, chart_type_lower


def _pptx_extract_labels_values(
    data, chart_type: str
) -> Tuple[Optional[list], Optional[list], str]:
    """
    Extract (labels, values, resolved_chart_type) from any supported data format.
    Returns (None, None, chart_type) when the format is unsupported.
    """
    chart_type_lower = chart_type.lower()
    if hasattr(data, "datasets"):
        logger.info("Using UniversalChartData Pydantic model for native chart")
        return _pptx_labels_values_from_pydantic(data, chart_type_lower)

    if isinstance(data, dict) and "datasets" in data:
        logger.info("Using UniversalChartData dict format for native chart")
        return _pptx_labels_values_from_dict(data, chart_type_lower)

    if isinstance(data, list):
        return _pptx_labels_values_from_list(data, chart_type_lower)

    if isinstance(data, dict) and "labels" in data and "values" in data:
        return _pptx_labels_values_from_viz_dict(data, chart_type_lower)

    return None, None, chart_type_lower


def _pptx_resolve_xl_chart_type(chart_type_lower: str, xl_chart_type_enum):
    """Map a chart type string to the corresponding XL_CHART_TYPE constant."""
    mapping = {
        "pie": xl_chart_type_enum.PIE,
        "donut": xl_chart_type_enum.DOUGHNUT,
        "line": xl_chart_type_enum.LINE,
        "area": xl_chart_type_enum.AREA,
        "bar": xl_chart_type_enum.COLUMN_CLUSTERED,
        "column": xl_chart_type_enum.COLUMN_CLUSTERED,
        "horizontal_bar": xl_chart_type_enum.BAR_CLUSTERED,
    }
    xl_type = mapping.get(chart_type_lower)
    if xl_type is None:
        logger.warning(
            f"Chart type '{chart_type_lower}' not natively supported, using column chart"
        )
        xl_type = xl_chart_type_enum.COLUMN_CLUSTERED
    return xl_type


def _pptx_resolve_series_secondary(dataset: dict, yaxes: list) -> Tuple[bool, bool]:
    """
    Determine whether a dataset series uses the secondary axis.
    Returns (use_secondary, is_multi_axis).
    """
    y_axis_id = dataset.get("yAxisId", "")
    if len(yaxes) <= 1:
        return False, False
    for axis_idx, axis in enumerate(yaxes):
        axis_id = axis.get("axisId") or axis.get("id") or axis.get("axis_id")
        if axis_id == y_axis_id:
            use_secondary = (axis_idx > 0) or (axis.get("position") == "right")
            return use_secondary, True
    return False, False


def _pptx_extract_series_values(
    raw_data: list, chart_type_lower: str, n_labels: int
) -> list:
    """Extract numeric values from a raw dataset point list."""
    if not raw_data:
        return [0] * n_labels
    if chart_type_lower == "horizontal_bar":
        return [p.get("x") or p.get("value") or 0 for p in raw_data]
    return [p.get("y") or p.get("value") or 0 for p in raw_data]


def _pptx_build_series_info(
    data, chart_type_lower: str, labels: list
) -> Tuple[list, bool]:
    """
    Build series_info list: [(series_name, series_values, use_secondary)].
    Also returns has_multiple_axes flag.
    """
    if not (
        isinstance(data, dict)
        and "datasets" in data
        and len(data.get("datasets", [])) > 1
    ):
        return [
            ("Data", labels, False)
        ], False  # placeholder; caller replaces with real values

    logger.info(f"Multi-dataset chart detected: {len(data['datasets'])} datasets")
    series_info = []
    has_multiple_axes = False
    yaxes = data.get("yAxes") or []

    for idx, dataset in enumerate(data["datasets"]):
        series_name = dataset.get("label", f"Series {idx + 1}")
        series_values = _pptx_extract_series_values(
            dataset.get("data", []), chart_type_lower, len(labels)
        )
        use_secondary, is_multi = _pptx_resolve_series_secondary(dataset, yaxes)
        if is_multi:
            has_multiple_axes = True
        series_info.append((series_name, series_values, use_secondary))
        logger.info(
            f"  Series '{series_name}': secondary_axis={use_secondary}, yAxisId={dataset.get('yAxisId', '')}"
        )

    return series_info, has_multiple_axes


def add_native_pptx_chart(slide, data, chart_type: str, x, y, cx, cy) -> bool:
    """
    Add a native PowerPoint chart to the slide using python-pptx.

    Args:
        slide: PPTX slide object
        data: Chart data (UniversalChartData, list, or dict)
        chart_type: Type of chart
        x, y: Position in inches
        cx, cy: Size in inches

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from pptx.chart.data import CategoryChartData
        from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
    except ImportError:
        logger.error(
            "python-pptx is required. Install with: pip install askrita[exports]"
        )
        return False

    try:
        labels, values, chart_type = _pptx_extract_labels_values(data, chart_type)
        if labels is None:
            logger.error(f"Unsupported data format for native chart: {type(data)}")
            return False

        labels = [str(label) if label is not None else "Unknown" for label in labels]

        if not labels:
            logger.warning(
                "No categories found for chart - PowerPoint requires at least one category"
            )
            return False

        # Align values length with labels
        if len(values) < len(labels):
            values.extend([0] * (len(labels) - len(values)))
        elif len(values) > len(labels):
            values = values[: len(labels)]

        chart_type_lower = chart_type.lower()
        xl_chart_type = _pptx_resolve_xl_chart_type(chart_type_lower, XL_CHART_TYPE)

        chart_data = CategoryChartData()
        chart_data.categories = labels

        # Build multi-series info if applicable
        series_info, has_multiple_axes = _pptx_build_series_info(
            data, chart_type_lower, labels
        )
        # For single-series case, _pptx_build_series_info returns a placeholder; use real values
        if len(series_info) == 1 and series_info[0][0] == "Data":
            series_info = [("Data", values, False)]

        for series_name, series_values, _ in series_info:
            chart_data.add_series(series_name, tuple(series_values))

        graphic_frame = slide.shapes.add_chart(xl_chart_type, x, y, cx, cy, chart_data)
        chart = graphic_frame.chart

        if has_multiple_axes:
            logger.warning(
                f"Chart has {len(series_info)} series but python-pptx doesn't support secondary axis"
            )
            logger.warning(
                "To add secondary axis: Open PowerPoint → Right-click series → Format Data Series → Secondary Axis"
            )

        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False

        if chart_type_lower in ["pie", "donut"]:
            plot = chart.plots[0]
            plot.has_data_labels = True
            plot.data_labels.number_format = '0.0"%"'

        logger.info(
            f"Native {chart_type} chart created with {len(labels)} categories, {len(series_info)} series"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to create native PPTX chart: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return False
