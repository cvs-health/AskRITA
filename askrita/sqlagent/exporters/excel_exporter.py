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
#   xlsxwriter (BSD-2-Clause)

"""
Excel export functionality with native multi-axis chart support.

This module provides Excel (.xlsx) export with:
- Native Excel charts (fully editable)
- Multi-axis support (primary and secondary Y-axes)
- Multiple chart types (column, line, bar, area, scatter, pie)
- Data tables with SQL queries
- Professional formatting
"""

from __future__ import annotations

import logging
import re
from io import BytesIO
from typing import TYPE_CHECKING, Dict, List

from askrita.sqlagent.exporters.models import ExportSettings
from askrita.sqlagent.formatters.DataFormatter import UniversalChartData
from askrita.sqlagent.State import WorkflowState

if TYPE_CHECKING:
    from xlsxwriter.workbook import Workbook
    from xlsxwriter.worksheet import Worksheet

logger = logging.getLogger(__name__)

# Check if xlsxwriter is available
try:
    import xlsxwriter

    XLSXWRITER_AVAILABLE = True
except ImportError:
    XLSXWRITER_AVAILABLE = False
    logger.warning(
        "xlsxwriter not available. Excel export will not work. Install with: pip install xlsxwriter"
    )

# Excel chart type mapping
_CHART_TYPE_MAP = {
    "bar": "column",  # Excel calls vertical bars "column"
    "horizontal_bar": "bar",  # Excel calls horizontal bars "bar"
    "line": "line",
    "area": "area",
    "scatter": "scatter",
    "pie": "pie",
    "column": "column",
}


def _setup_workbook_formats(workbook, settings: ExportSettings) -> dict:
    """Create and return all xlsxwriter cell formats needed for the workbook."""
    primary_color = _rgb_to_hex(settings.brand_primary_color)
    return {
        "title": workbook.add_format(
            {
                "bold": True,
                "font_size": 18,
                "font_color": primary_color,
                "align": "left",
                "valign": "vcenter",
            }
        ),
        "header": workbook.add_format(
            {
                "bold": True,
                "font_size": 12,
                "bg_color": primary_color,
                "font_color": "white",
                "align": "center",
                "valign": "vcenter",
                "border": 1,
            }
        ),
        "data": workbook.add_format(
            {"align": "left", "valign": "vcenter", "border": 1}
        ),
        "number": workbook.add_format(
            {
                "align": "right",
                "valign": "vcenter",
                "border": 1,
                "num_format": "#,##0",
            }
        ),
        "decimal": workbook.add_format(
            {
                "align": "right",
                "valign": "vcenter",
                "border": 1,
                "num_format": "#,##0.00",
            }
        ),
    }


def _write_worksheet_meta(
    data_ws, workbook, output_state, settings, formats, start_row: int
) -> int:
    """Write title, question, answer, and optional SQL to worksheet. Returns updated start_row."""
    data_ws.write("A1", settings.title, formats["title"])
    if output_state.question:
        data_ws.write("A2", f"Question: {output_state.question}")
    if output_state.answer:
        data_ws.write("A4", "Answer:", workbook.add_format({"bold": True}))
        data_ws.write("B4", output_state.answer)
    if settings.include_sql and output_state.sql_query:
        data_ws.write(
            f"A{start_row}", "SQL Query:", workbook.add_format({"bold": True})
        )
        data_ws.write(
            f"A{start_row + 1}",
            output_state.sql_query,
            workbook.add_format({"font_name": "Courier New", "font_size": 10}),
        )
        start_row += 3
    return start_row


def _extract_fallback_headers(results: list, output_state) -> List[str]:
    """Extract column headers from result rows or by parsing the SQL query."""
    if not results:
        return []
    if isinstance(results[0], dict):
        return list(results[0].keys())
    if not isinstance(results[0], (tuple, list)):
        return []
    fallback_headers = [f"Column_{i + 1}" for i in range(len(results[0]))]
    sql_query = output_state.sql_query or ""
    if sql_query:
        select_match = re.search(
            r"SELECT\s+(.*?)\s+FROM", sql_query, re.IGNORECASE | re.DOTALL
        )
        if select_match:
            columns = [
                col.strip().split(" AS ")[-1].split(".")[-1].strip('`"[]')
                for col in select_match.group(1).split(",")
            ]
            if len(columns) == len(results[0]):
                logger.info(
                    f"Extracted {len(columns)} column names from SQL query: {columns}"
                )
                return columns
    return fallback_headers


def _write_cell_value(data_ws, row: int, col: int, value, formats: dict) -> None:
    """Write a value to a worksheet cell with auto-detected numeric format."""
    if isinstance(value, float):
        data_ws.write(row, col, value, formats["decimal"])
    elif isinstance(value, int):
        data_ws.write(row, col, value, formats["number"])
    else:
        data_ws.write(row, col, value, formats["data"])


def _get_cell_value(
    row_data, col_idx: int, fallback_headers: List[str], headers: List[str]
):
    """Retrieve a cell value from a result row using the appropriate key or index."""
    key = (
        fallback_headers[col_idx]
        if col_idx < len(fallback_headers)
        else headers[col_idx]
    )
    if isinstance(row_data, dict):
        return row_data.get(key)
    if col_idx < len(row_data):
        return row_data[col_idx]
    return None


def _write_data_table_content(
    data_ws,
    workbook,
    results: list,
    headers: List[str],
    fallback_headers: List[str],
    start_row: int,
    formats: dict,
) -> int:
    """Write the data table label, header row, data rows, and column widths. Returns first data row."""
    data_ws.write(f"A{start_row}", "Data Table:", workbook.add_format({"bold": True}))
    start_row += 1

    for col_idx, header in enumerate(headers):
        data_ws.write(start_row, col_idx, header, formats["header"])
    start_row += 1

    for row_idx, row_data in enumerate(results):
        for col_idx in range(len(headers)):
            value = _get_cell_value(row_data, col_idx, fallback_headers, headers)
            _write_cell_value(data_ws, start_row + row_idx, col_idx, value, formats)

    for col_idx, header in enumerate(headers):
        data_ws.set_column(col_idx, col_idx, max(len(str(header)), 15))

    return start_row


def _build_enhanced_headers(result_keys: list, chart_data) -> List[str]:
    """Build headers matching result_keys count, using chart metadata where available."""
    enhanced = []
    for i, key in enumerate(result_keys):
        if i == 0 and chart_data.xAxisLabel:
            enhanced.append(chart_data.xAxisLabel)
        elif i == 1 and chart_data.datasets and chart_data.datasets[0].label:
            enhanced.append(chart_data.datasets[0].label)
        elif chart_data.yAxisLabel and i > 0:
            enhanced.append(chart_data.yAxisLabel)
        else:
            enhanced.append(key.title())
    return enhanced


def _first_column_header(chart_data, fallback_headers: List[str]) -> str:
    """Return the best label for the first (category) column."""
    if chart_data.xAxisLabel:
        return chart_data.xAxisLabel
    if fallback_headers:
        return fallback_headers[0]
    return "Category"


def _value_column_headers(chart_data) -> List[str]:
    """Return labels for value columns from dataset labels or Y-axis label."""
    if chart_data.datasets:
        return [
            ds.label or chart_data.yAxisLabel or "Value" for ds in chart_data.datasets
        ]
    if chart_data.yAxisLabel:
        return [chart_data.yAxisLabel]
    return []


def _generate_table_headers_from_chart_data(
    chart_data: UniversalChartData, results: List[Dict], fallback_headers: List[str]
) -> List[str]:
    """
    Generate intelligent table headers using chart metadata (axis labels, dataset labels).

    Args:
        chart_data: UniversalChartData with rich metadata
        results: Raw data results
        fallback_headers: Fallback headers if chart metadata isn't available

    Returns:
        List of meaningful column headers
    """
    if not chart_data or not results:
        return fallback_headers

    headers = [
        _first_column_header(chart_data, fallback_headers)
    ] + _value_column_headers(chart_data)

    # If header count mismatches result columns, rebuild using chart metadata
    if isinstance(results[0], dict):
        result_keys = list(results[0].keys())
        if len(headers) != len(result_keys):
            return _build_enhanced_headers(result_keys, chart_data)

    return headers if headers else fallback_headers


def create_excel_export(output_state: WorkflowState, settings: ExportSettings) -> bytes:
    """
    Create Excel workbook with data, chart, and optional SQL query.

    Args:
        output_state: Complete workflow output state
        settings: Export customization settings

    Returns:
        bytes: Excel file content as bytes

    Raises:
        ExportError: If Excel generation fails
    """
    if not XLSXWRITER_AVAILABLE:
        from ...exceptions import ExportError

        raise ExportError(
            "xlsxwriter is not installed. "
            "Install it with: pip install askrita[exports] or pip install xlsxwriter"
        )

    from ...exceptions import ExportError

    try:
        excel_buffer = BytesIO()
        workbook = xlsxwriter.Workbook(excel_buffer, {"in_memory": True})
        formats = _setup_workbook_formats(workbook, settings)
        data_ws = workbook.add_worksheet("Data")

        start_row = _write_worksheet_meta(
            data_ws, workbook, output_state, settings, formats, 6
        )

        results = output_state.results or []
        headers: List[str] = []
        if results:
            fallback_headers = _extract_fallback_headers(results, output_state)

            if output_state.chart_data:
                headers = _generate_table_headers_from_chart_data(
                    output_state.chart_data, results, fallback_headers
                )
                logger.info(f"✅ Generated headers from chart metadata: {headers}")
            else:
                headers = fallback_headers
                logger.info(f"Using fallback headers: {headers}")

            start_row = _write_data_table_content(
                data_ws,
                workbook,
                results,
                headers,
                fallback_headers,
                start_row,
                formats,
            )

            if output_state.chart_data:
                _add_excel_chart(
                    workbook,
                    data_ws,
                    output_state.chart_data,
                    headers,
                    results,
                    start_row,
                )

        if output_state.followup_questions:
            summary_ws = workbook.add_worksheet("Summary")
            summary_ws.write("A1", "Follow-up Questions", formats["title"])
            for idx, question in enumerate(output_state.followup_questions, start=1):
                summary_ws.write(f"A{idx + 2}", f"{idx}. {question}")
            summary_ws.set_column("A:A", 80)

        workbook.close()
        excel_buffer.seek(0)
        logger.info(
            f"✅ Excel export created successfully: {len(excel_buffer.getvalue()):,} bytes"
        )
        return excel_buffer.getvalue()

    except Exception as e:
        logger.error(f"Excel export failed: {e}")
        from ...exceptions import ExportError

        raise ExportError(f"Failed to create Excel export: {e}")


def _add_pie_chart(
    workbook,
    worksheet,
    chart_data,
    headers: List[str],
    results: list,
    data_start_row: int,
) -> None:
    """Add a pie chart to the worksheet."""
    try:
        datasets = chart_data.datasets or []
        if not datasets:
            return
        dataset = datasets[0]
        pie_labels: List[str] = []
        pie_values: List[float] = []
        for point in dataset.data or []:
            pie_labels.append(str(point.label or point.x or f"Item {len(pie_labels)}"))
            v = point.value or point.y or 0
            pie_values.append(float(v) if v is not None else 0.0)

        if not (pie_labels and pie_values):
            return

        data_start_col = len(headers) + 2
        worksheet.write(data_start_row - 1, data_start_col, "Category")
        worksheet.write(data_start_row - 1, data_start_col + 1, "Value")
        for i, (category, value) in enumerate(zip(pie_labels, pie_values)):
            worksheet.write(data_start_row + i, data_start_col, category)
            worksheet.write(data_start_row + i, data_start_col + 1, value)

        n = len(pie_labels)
        cat_col = _col_to_excel(data_start_col)
        val_col = _col_to_excel(data_start_col + 1)
        end_row = data_start_row + n - 1
        primary_chart = workbook.add_chart({"type": "pie"})
        primary_chart.add_series(
            {
                "categories": f"=Data!${cat_col}${data_start_row}:${cat_col}${end_row}",
                "values": f"=Data!${val_col}${data_start_row}:${val_col}${end_row}",
                "data_labels": {"percentage": True},
            }
        )
        primary_chart.set_title({"name": chart_data.title or "Pie Chart"})
        primary_chart.set_size({"width": 720, "height": 400})
        worksheet.insert_chart(f"A{data_start_row + len(results) + 3}", primary_chart)
        logger.info(f"✅ Excel pie chart added with {n} categories")
    except Exception as pie_error:
        logger.error(f"Failed to add pie chart to Excel: {pie_error}")


def _find_value_columns(datasets, headers: List[str]) -> List[int]:
    """Match dataset labels to column indices via fuzzy label matching."""
    value_cols: List[int] = []
    for dataset in datasets:
        label = (dataset.label or "").lower()
        matched = False
        for idx, header in enumerate(headers):
            header_lower = header.lower()
            if (
                label
                and idx not in value_cols
                and (
                    label in header_lower
                    or header_lower in label
                    or any(
                        word in header_lower for word in label.split() if len(word) > 3
                    )
                    or any(
                        word in label for word in header_lower.split() if len(word) > 3
                    )
                )
            ):
                value_cols.append(idx)
                matched = True
                break
        if not matched:
            logger.warning(
                f"Could not match dataset label '{dataset.label}' to any column"
            )
    return value_cols


def _find_secondary_series_idx(datasets, y_axes) -> int:
    """Return the dataset index that should use the secondary (right) axis."""
    for idx, dataset in enumerate(datasets):
        y_axis_id = dataset.yAxisId or ""
        if y_axis_id and idx > 0:
            for axis in y_axes:
                axis_id = (
                    getattr(axis, "axisId", None)
                    or getattr(axis, "id", None)
                    or getattr(axis, "axis_id", None)
                )
                if axis_id == y_axis_id and getattr(axis, "position", None) == "right":
                    return idx
    return 1  # default: second series on secondary axis


def _combine_multi_axis_charts(
    workbook,
    primary_chart,
    datasets,
    value_cols: List[int],
    y_axes,
    excel_chart_type: str,
    categories_range: str,
    data_start_row: int,
    data_end_row: int,
    headers: List[str],
) -> None:
    """Create a secondary axis chart, add its series, and combine with the primary chart."""
    secondary_series_idx = _find_secondary_series_idx(datasets, y_axes)
    secondary_chart_type = "line" if excel_chart_type == "column" else excel_chart_type
    secondary_chart = workbook.add_chart({"type": secondary_chart_type})

    if secondary_series_idx < len(value_cols):
        second_col = value_cols[secondary_series_idx]
        header_row = data_start_row - 1
        sec_col_letter = _col_to_excel(second_col)
        secondary_chart.add_series(
            {
                "name": f"=Data!${sec_col_letter}${header_row}",
                "categories": categories_range,
                "values": f"=Data!${sec_col_letter}${data_start_row}:${sec_col_letter}${data_end_row}",
                "y2_axis": True,
                "marker": {"type": "automatic"},
            }
        )
        col_name = headers[second_col] if second_col < len(headers) else "unknown"
        logger.info(
            f"✅ Added secondary series: {col_name} (y2_axis=True, header at row {header_row})"
        )

    primary_chart.combine(secondary_chart)

    if len(y_axes) >= 1:
        primary_chart.set_y_axis(
            {"name": getattr(y_axes[0], "label", None) or "Primary Axis"}
        )
    if len(y_axes) >= 2:
        primary_chart.set_y2_axis(
            {"name": getattr(y_axes[1], "label", None) or "Secondary Axis"}
        )


def _resolve_value_columns(
    datasets, headers: List[str], has_secondary_axis: bool
) -> List[int]:
    """Return value column indices, falling back to positional indices if fuzzy match fails."""
    value_cols = _find_value_columns(datasets, headers)
    if not value_cols or (has_secondary_axis and len(value_cols) < len(datasets)):
        logger.warning(
            f"Fuzzy matching found {len(value_cols)} columns but need {len(datasets)}. Using column indices."
        )
        logger.warning(f"Headers: {headers}, Length: {len(headers)}")
        value_cols = list(range(1, len(headers)))
        logger.warning(f"After fallback, value_cols = {value_cols}")
    return value_cols


def _add_primary_series(
    primary_chart,
    value_cols: List[int],
    categories_range: str,
    data_start_row: int,
    data_end_row: int,
    headers: List[str],
) -> None:
    """Add the first data series to the primary chart."""
    if not value_cols:
        return
    first_col = value_cols[0]
    header_row = data_start_row - 1
    col_letter = _col_to_excel(first_col)
    primary_chart.add_series(
        {
            "name": f"=Data!${col_letter}${header_row}",
            "categories": categories_range,
            "values": f"=Data!${col_letter}${data_start_row}:${col_letter}${data_end_row}",
            "data_labels": {"value": False},
        }
    )
    logger.info(
        f"✅ Added primary series: {headers[first_col] if first_col < len(headers) else 'unknown'} (header at row {header_row})"
    )


def _add_remaining_series(
    primary_chart,
    value_cols: List[int],
    categories_range: str,
    data_start_row: int,
    data_end_row: int,
) -> None:
    """Add extra series to a single-axis primary chart."""
    header_row = data_start_row - 1
    for col_idx in value_cols[1:]:
        col_letter = _col_to_excel(col_idx)
        primary_chart.add_series(
            {
                "name": f"=Data!${col_letter}${header_row}",
                "categories": categories_range,
                "values": f"=Data!${col_letter}${data_start_row}:${col_letter}${data_end_row}",
            }
        )


def _configure_chart_appearance(
    primary_chart,
    chart_data,
    headers: List[str],
    category_col: int,
    has_secondary_axis: bool,
) -> None:
    """Set title, axis labels, legend, and size on the primary chart."""
    x_label = chart_data.xAxisLabel or (
        headers[category_col] if headers else "Categories"
    )
    primary_chart.set_title({"name": chart_data.title or "Data Visualization"})
    primary_chart.set_x_axis({"name": x_label})
    if not has_secondary_axis and chart_data.yAxisLabel:
        primary_chart.set_y_axis({"name": chart_data.yAxisLabel})
    primary_chart.set_legend({"position": "bottom"})
    primary_chart.set_size({"width": 720, "height": 400})


def _add_excel_chart(
    workbook: Workbook,
    worksheet: Worksheet,
    chart_data: UniversalChartData,
    headers: List[str],
    results: List[Dict],
    data_start_row: int,
) -> None:
    """
    Add native Excel chart with multi-axis support.

    Args:
        workbook: xlsxwriter Workbook object
        worksheet: Worksheet to add chart to
        chart_data: UniversalChartData Pydantic object
        headers: Column headers
        results: Data rows
        data_start_row: Row where data starts (1-based)
    """
    try:
        chart_type = chart_data.type.lower() if chart_data.type else "column"
        datasets = chart_data.datasets or []

        if not datasets:
            logger.warning("No datasets in chart_data, skipping chart")
            return

        logger.debug(
            f"Chart data: type={chart_type}, datasets={len(datasets)}, labels={len(chart_data.labels or [])}"
        )

        excel_chart_type = _CHART_TYPE_MAP.get(chart_type, "column")

        if chart_type == "pie":
            _add_pie_chart(
                workbook, worksheet, chart_data, headers, results, data_start_row
            )
            return

        y_axes = chart_data.yAxes or []
        has_secondary_axis = len(y_axes) > 1
        category_col = 0
        value_cols = _resolve_value_columns(datasets, headers, has_secondary_axis)

        primary_chart = workbook.add_chart({"type": excel_chart_type})
        data_end_row = data_start_row + len(results) - 1

        logger.info(
            f"📊 Chart data ranges: start_row={data_start_row}, end_row={data_end_row}, total_rows={len(results)}"
        )
        logger.info(
            f"📊 Categories column: {category_col} ({headers[category_col] if category_col < len(headers) else 'unknown'})"
        )
        logger.info(
            f"📊 Value columns: {value_cols} ({[headers[i] for i in value_cols if i < len(headers)]})"
        )

        cat_col_letter = _col_to_excel(category_col)
        categories_range = (
            f"=Data!${cat_col_letter}${data_start_row}:${cat_col_letter}${data_end_row}"
        )

        _add_primary_series(
            primary_chart,
            value_cols,
            categories_range,
            data_start_row,
            data_end_row,
            headers,
        )

        if has_secondary_axis and len(value_cols) > 1:
            _combine_multi_axis_charts(
                workbook,
                primary_chart,
                datasets,
                value_cols,
                y_axes,
                excel_chart_type,
                categories_range,
                data_start_row,
                data_end_row,
                headers,
            )
        else:
            _add_remaining_series(
                primary_chart,
                value_cols,
                categories_range,
                data_start_row,
                data_end_row,
            )

        _configure_chart_appearance(
            primary_chart, chart_data, headers, category_col, has_secondary_axis
        )
        worksheet.insert_chart(f"A{data_end_row + 3}", primary_chart)
        logger.info(
            f"✅ Excel chart added: {chart_type}, multi-axis: {has_secondary_axis}"
        )

    except Exception as e:
        logger.error(f"Failed to add Excel chart: {e}")


def _col_to_excel(col_idx: int) -> str:
    """Convert 0-based column index to Excel column letter (A, B, C, ...)."""
    result = ""
    while col_idx >= 0:
        result = chr(col_idx % 26 + ord("A")) + result
        col_idx = col_idx // 26 - 1
    return result


def _rgb_to_hex(rgb: tuple) -> str:
    """Convert RGB tuple (0-255) to hex color string."""
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
