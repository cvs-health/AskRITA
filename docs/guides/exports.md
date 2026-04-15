<!--
  © 2026 CVS Health and/or one of its affiliates. All rights reserved.

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.
-->
# Export to PPTX, PDF, and Excel

Ask RITA can export query results to presentation-ready PowerPoint, PDF reports, and Excel spreadsheets — complete with charts, data tables, and branded formatting.

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [ExportSettings](#exportsettings)
- [PPTX Export](#pptx-export)
- [PDF Export](#pdf-export)
- [Excel Export](#excel-export)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)

## Overview

| Export | Package | Charts | Data Table | Branding |
|---|---|---|---|---|
| **PPTX** | `python-pptx` | Native PowerPoint charts | Up to 15 rows | Primary + secondary colors |
| **PDF** | `reportlab` | Matplotlib PNG images | Up to 20 rows | Primary color header |
| **Excel** | `xlsxwriter` | Native Excel charts | Full dataset | Branded cell formatting |

All three export methods are available on `SQLAgentWorkflow` and return `bytes` that you can write to a file or stream to a client.

## Installation

Export dependencies are optional. Install them as needed:

```bash
# All export dependencies
pip install python-pptx reportlab xlsxwriter matplotlib

# Or individually
pip install python-pptx    # For PPTX
pip install reportlab      # For PDF
pip install matplotlib     # For PDF charts
pip install xlsxwriter     # For Excel
```

## Quick Start

```python
from askrita import SQLAgentWorkflow, ConfigManager

config = ConfigManager("config.yaml")
workflow = SQLAgentWorkflow(config)

# Run a query
result = workflow.query("What are total sales by region?")

# Export to PowerPoint
pptx_bytes = workflow.export_to_pptx(result, title="Sales Report")
with open("report.pptx", "wb") as f:
    f.write(pptx_bytes)

# Export to PDF
pdf_bytes = workflow.export_to_pdf(result, title="Sales Report")
with open("report.pdf", "wb") as f:
    f.write(pdf_bytes)

# Export to Excel
excel_bytes = workflow.export_to_excel(result, title="Sales Report")
with open("report.xlsx", "wb") as f:
    f.write(excel_bytes)
```

## ExportSettings

All export methods accept the same set of parameters, which are converted to an `ExportSettings` object internally:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `title` | `str` | `"Query Results"` | Report title (cover slide, header) |
| `company_name` | `str` | `"Data Analytics"` | Company name for branding |
| `include_sql` | `bool` | `False` | Include the generated SQL in the export |
| `include_data_table` | `bool` | `True` | Include a data table (PPTX and PDF only) |
| `chart_style` | `str` | `"modern"` | Chart style for PDF: `"modern"` or `"classic"` |
| `brand_colors` | `dict` | — | Custom brand colors (PPTX and Excel only) |

### Brand Colors

Pass custom brand colors as RGB tuples:

```python
pptx_bytes = workflow.export_to_pptx(
    result,
    title="Quarterly Report",
    brand_colors={
        "primary": (0, 47, 135),     # Header and accent color
        "secondary": (204, 9, 47),   # Title highlights
    }
)
```

Default colors:

- **Primary**: `(0, 47, 135)` — dark blue
- **Secondary**: `(204, 9, 47)` — red

### ExportSettings Model

```python
from askrita import ExportSettings

settings = ExportSettings(
    title="My Report",
    company_name="Acme Corp",
    include_sql=True,
    include_data_table=True,
    chart_style="modern",
    brand_primary_color=(0, 47, 135),
    brand_secondary_color=(204, 9, 47),
)
```

## PPTX Export

PowerPoint exports create a multi-slide presentation:

### Slides

| Slide | Content | Condition |
|---|---|---|
| **Title** | Report title, company name | Always |
| **Executive Summary** | Question, answer, SQL reasoning, visualization reasoning | Always |
| **Visualization** | Native PowerPoint chart from `chart_data` | When chart data available |
| **Data Table** | First 15 rows of results | When `include_data_table=True` and results exist |
| **SQL Query** | The generated SQL | When `include_sql=True` and SQL exists |
| **Follow-Up Questions** | Suggested next questions | When follow-ups exist |
| **Closing** | "Thank you" slide | Always |

### Chart Types

The PPTX exporter creates native PowerPoint charts (not images). Supported chart type mappings:

- Bar, Column, Stacked Bar/Column
- Line, Area
- Pie, Donut
- Scatter
- Multi-axis / dual-axis charts

### Example

```python
result = workflow.query("Show monthly revenue trends for 2025")

pptx_bytes = workflow.export_to_pptx(
    result,
    title="Revenue Analysis — 2025",
    company_name="Acme Corp",
    include_sql=True,
    include_data_table=True,
    brand_colors={"primary": (25, 25, 112), "secondary": (220, 20, 60)},
)

with open("revenue_2025.pptx", "wb") as f:
    f.write(pptx_bytes)
```

## PDF Export

PDF exports create an A4 document with sections:

### Sections

| Section | Content | Condition |
|---|---|---|
| **Title Block** | Report title, company name, date | Always |
| **Query Analysis** | Question and answer | Always |
| **SQL Query** | The generated SQL | When `include_sql=True` and SQL exists |
| **Chart** | Matplotlib-rendered chart as PNG | When chart data available |
| **Data Table** | First 20 rows of results | When `include_data_table=True` and results are dicts |
| **Follow-Up Questions** | Suggested next questions | When follow-ups exist |

### Chart Styles

| Style | Description |
|---|---|
| `"modern"` | Clean, minimal style with modern colors |
| `"classic"` | Traditional chart styling |

### Example

```python
result = workflow.query("Customer distribution by state")

pdf_bytes = workflow.export_to_pdf(
    result,
    title="Customer Geography Report",
    chart_style="modern",
    include_sql=False,
)

with open("customers_by_state.pdf", "wb") as f:
    f.write(pdf_bytes)
```

## Excel Export

Excel exports create a workbook with data and charts:

### Sheets

| Sheet | Content | Condition |
|---|---|---|
| **Data** | Title, question, answer, optional SQL, full results table, chart | Always |
| **Summary** | Follow-up questions | When follow-ups exist |

### Features

- **Full dataset** — Unlike PPTX (15 rows) and PDF (20 rows), Excel includes all result rows
- **Native Excel charts** — Bar, column, line, pie, and multi-axis chart types
- **Formatted headers** — Branded colors on header row and title cells
- **Chart-aware columns** — When `chart_data` exists, column headers are derived from the chart metadata

### Example

```python
result = workflow.query("All orders from the last 30 days with customer details")

excel_bytes = workflow.export_to_excel(
    result,
    title="Recent Orders Export",
    company_name="Acme Corp",
    include_sql=True,
    brand_colors={"primary": (0, 100, 0)},
)

with open("recent_orders.xlsx", "wb") as f:
    f.write(excel_bytes)
```

## API Reference

### SQLAgentWorkflow.export_to_pptx()

```python
def export_to_pptx(
    self,
    output_state: WorkflowState,
    title: str = "Query Results",
    company_name: str = "Data Analytics",
    include_sql: bool = False,
    include_data_table: bool = True,
    chart_style: str = "modern",
    brand_colors: Dict[str, tuple] = None,
) -> bytes:
    """
    Export query results to a PowerPoint presentation.

    Raises:
        ImportError: If python-pptx is not installed
        ExportError: If export fails
    """
```

### SQLAgentWorkflow.export_to_pdf()

```python
def export_to_pdf(
    self,
    output_state: WorkflowState,
    title: str = "Query Results",
    company_name: str = "Data Analytics",
    include_sql: bool = False,
    include_data_table: bool = True,
    chart_style: str = "modern",
) -> bytes:
    """
    Export query results to a PDF document.

    Raises:
        ImportError: If reportlab is not installed
        ExportError: If export fails
    """
```

### SQLAgentWorkflow.export_to_excel()

```python
def export_to_excel(
    self,
    output_state: WorkflowState,
    title: str = "Query Results",
    company_name: str = "Data Analytics",
    include_sql: bool = False,
    include_data_table: bool = True,
    chart_style: str = "modern",
    brand_colors: Dict[str, tuple] = None,
) -> bytes:
    """
    Export query results to an Excel workbook.

    Raises:
        ExportError: If xlsxwriter is not installed or export fails
    """
```

### Lower-Level Functions

These are available for advanced use cases:

```python
from askrita.sqlagent.exporters.core import create_pptx_export, create_pdf_export
from askrita.sqlagent.exporters.excel_exporter import create_excel_export
from askrita.sqlagent.exporters.chart_generator import (
    generate_chart_bytes,        # PNG bytes via matplotlib
    get_chart_data_for_export,   # Extract chart data from WorkflowState
    add_native_pptx_chart,       # Add native chart to a PPTX slide
)
```

## Troubleshooting

### ImportError: Missing Export Dependencies

**Symptom**: `ImportError: python-pptx is required for PPTX export`

Install the required package:

```bash
pip install python-pptx   # For PPTX
pip install reportlab      # For PDF
pip install xlsxwriter     # For Excel
pip install matplotlib     # For PDF charts
```

### Empty Charts in Export

**Symptom**: Export has no chart, only data table.

- Ensure the query result has `chart_data` (enable the `choose_and_format_visualization` workflow step)
- Check that `visualization` is not empty in the result
- Some queries return data that is not suitable for charting

### ExportError

**Symptom**: `ExportError` during export.

- Check that the `output_state` contains valid data (`results`, `answer`)
- Use `--verbose` when querying to see if the workflow completed successfully
- Verify chart data is well-formed (non-empty labels and values)

### PDF Charts Missing

**Symptom**: PDF exports have no chart even when chart data exists.

- Install matplotlib: `pip install matplotlib`
- The PDF exporter uses matplotlib to render charts as PNG images

---

**See also:**

- [Configuration Guide](../configuration/overview.md) — Complete YAML configuration reference
- [Chart Documentation](../charts/README.md) — Chart types and visualization data format
- [Usage Examples](../usage-examples.md) — Query workflow examples
