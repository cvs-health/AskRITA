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

"""Pydantic models for export configuration."""

from typing import Tuple

from pydantic import BaseModel, ConfigDict, Field


class ExportSettings(BaseModel):
    """
    Export customization settings for PPTX and PDF exports.

    Attributes:
        title: Report title (default: "Query Results")
        company_name: Company name for branding (default: "Data Analytics")
        include_sql: Include SQL query in export (default: False)
        include_data_table: Include data table in export (default: True)
        chart_style: Chart visual style - "modern" or "classic" (default: "modern")
        brand_primary_color: RGB tuple for primary brand color (default: (0, 47, 135))
        brand_secondary_color: RGB tuple for secondary brand color (default: (204, 9, 47))

    Example:
        >>> settings = ExportSettings(
        ...     title="Q4 Sales Report",
        ...     company_name="Acme Corp",
        ...     include_sql=True,
        ...     chart_style="modern",
        ...     brand_primary_color=(0, 47, 135),
        ...     brand_secondary_color=(204, 9, 47)
        ... )
    """

    title: str = Field(
        default="Query Results",
        description="Report title displayed on cover slide/page",
    )

    company_name: str = Field(
        default="Data Analytics", description="Company name for branding and headers"
    )

    include_sql: bool = Field(
        default=False, description="Include SQL query in the export"
    )

    include_data_table: bool = Field(
        default=True, description="Include data table in the export"
    )

    chart_style: str = Field(
        default="modern", description="Chart visual style: 'modern' or 'classic'"
    )

    brand_primary_color: Tuple[int, int, int] = Field(
        default=(0, 47, 135),
        description="RGB tuple for primary brand color (default: dark blue)",
    )

    brand_secondary_color: Tuple[int, int, int] = Field(
        default=(204, 9, 47),
        description="RGB tuple for secondary brand color (default: red)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Q4 Sales Report",
                "company_name": "Acme Corp",
                "include_sql": True,
                "include_data_table": True,
                "chart_style": "modern",
                "brand_primary_color": (0, 47, 135),
                "brand_secondary_color": (204, 9, 47),
            }
        }
    )
