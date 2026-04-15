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

"""
Schema Analyzer for Research Agent.

Provides comprehensive analysis of database schema structure with detailed
reporting for research purposes.
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ColumnAnalysis:
    """Analysis of a single database column."""

    name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool = False
    is_foreign_key: bool = False
    description: Optional[str] = None
    research_potential: str = ""  # "high", "medium", "low"
    statistical_type: str = ""  # "categorical", "numerical", "temporal", "identifier"
    sample_queries: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        """Safe string representation to avoid recursion."""
        return (
            f"ColumnAnalysis({self.name}: {self.data_type}, {self.research_potential})"
        )


@dataclass
class TableAnalysis:
    """Analysis of a single database table."""

    name: str
    full_name: str
    columns: Dict[str, ColumnAnalysis] = field(default_factory=dict)
    description: Optional[str] = None
    row_count_estimate: Optional[int] = None
    primary_keys: List[str] = field(default_factory=list)
    foreign_keys: List[str] = field(default_factory=list)
    research_value: str = ""  # "high", "medium", "low"
    entity_type: str = ""  # "fact", "dimension", "bridge", "staging"
    relationships: List[str] = field(default_factory=list)
    analysis_suggestions: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        """Safe string representation to avoid recursion."""
        return f"TableAnalysis({self.name}: {len(self.columns)} columns, {self.research_value})"


@dataclass
class SchemaAnalysisReport:
    """Comprehensive schema analysis report."""

    database_type: str
    total_tables: int
    total_columns: int
    analysis_timestamp: str

    # Table analysis
    tables: Dict[str, TableAnalysis] = field(default_factory=dict)

    # Schema patterns
    naming_patterns: Dict[str, int] = field(default_factory=dict)
    data_type_distribution: Dict[str, int] = field(default_factory=dict)

    # Research insights
    high_value_tables: List[str] = field(default_factory=list)
    potential_fact_tables: List[str] = field(default_factory=list)
    potential_dimension_tables: List[str] = field(default_factory=list)
    suggested_relationships: List[Dict[str, str]] = field(default_factory=list)

    # Analysis quality indicators
    schema_complexity: str = ""  # "simple", "moderate", "complex"
    data_model_type: str = ""  # "normalized", "denormalized", "mixed"
    research_readiness: str = ""  # "excellent", "good", "needs_preparation"

    # Step-by-step instructions
    analysis_steps: List[str] = field(default_factory=list)
    recommended_analyses: List[Dict[str, Any]] = field(default_factory=list)

    def __str__(self) -> str:
        """Safe string representation to avoid recursion."""
        return f"SchemaAnalysisReport({self.database_type}: {self.total_tables} tables, {self.research_readiness})"


class SchemaAnalyzer:
    """
    Comprehensive database schema analyzer for research purposes.

    Analyzes database structure and provides detailed insights for
    research design and hypothesis testing.
    """

    def __init__(self, sql_agent):
        """Initialize with SQL agent for schema access."""
        self.sql_agent = sql_agent

    def analyze_schema(self, include_sample_data: bool = True) -> SchemaAnalysisReport:
        """
        Perform comprehensive schema analysis.

        Args:
            include_sample_data: Whether to sample data for enhanced analysis

        Returns:
            SchemaAnalysisReport: Comprehensive analysis report
        """
        logger.info("🔍 Starting comprehensive schema analysis...")

        # Get schema information
        raw_schema = self.sql_agent.schema
        structured_schema = self.sql_agent.structured_schema

        # Initialize report
        report = SchemaAnalysisReport(
            database_type=self.sql_agent.config.get_database_type(),
            total_tables=len(structured_schema.get("tables", {})),
            total_columns=0,
            analysis_timestamp=datetime.now().isoformat(),
        )

        # Analyze each table
        logger.info(f"📊 Analyzing {report.total_tables} tables...")
        for table_name, table_info in structured_schema.get("tables", {}).items():
            table_analysis = self._analyze_table(table_name, table_info, raw_schema)
            report.tables[table_name] = table_analysis
            report.total_columns += len(table_analysis.columns)

        # Perform schema-wide analysis
        self._analyze_schema_patterns(report)
        self._classify_tables(report)
        self._identify_relationships(report)
        self._assess_research_potential(report)

        # Sample data if requested and feasible
        if include_sample_data and report.total_tables <= 20:  # Limit for performance
            self._enhance_with_sample_data(report)

        # Generate step-by-step instructions
        self._generate_analysis_instructions(report)

        logger.info("✅ Schema analysis completed")
        return report

    def _analyze_table(
        self, table_name: str, table_info: Dict[str, Any], raw_schema: str
    ) -> TableAnalysis:
        """Analyze individual table structure."""
        # Extract full table name from raw schema
        full_name_match = re.search(
            r'CREATE TABLE\s+([`"]?[^`"\s]+[`"]?)\s*\(', raw_schema, re.IGNORECASE
        )
        full_name = (
            full_name_match.group(1).strip('`"') if full_name_match else table_name
        )

        table_analysis = TableAnalysis(
            name=table_name,
            full_name=full_name,
            description=table_info.get("description", ""),
        )

        # Analyze columns
        columns_info = table_info.get("columns", {})
        for col_name, col_info in columns_info.items():
            col_analysis = self._analyze_column(col_name, col_info)
            table_analysis.columns[col_name] = col_analysis

            # Track keys
            if col_analysis.is_primary_key:
                table_analysis.primary_keys.append(col_name)
            if col_analysis.is_foreign_key:
                table_analysis.foreign_keys.append(col_name)

        # Classify table type
        table_analysis.entity_type = self._classify_table_type(
            table_name, table_analysis.columns
        )
        table_analysis.research_value = self._assess_table_research_value(
            table_analysis
        )

        # Generate analysis suggestions
        table_analysis.analysis_suggestions = self._generate_table_analysis_suggestions(
            table_analysis
        )

        return table_analysis

    def _analyze_column(
        self, col_name: str, col_info: Dict[str, Any]
    ) -> ColumnAnalysis:
        """Analyze individual column."""
        data_type = col_info.get("type", "UNKNOWN").upper()

        col_analysis = ColumnAnalysis(
            name=col_name,
            data_type=data_type,
            is_nullable=col_info.get("nullable", True),
            description=col_info.get("description", ""),
        )

        # Determine statistical type
        col_analysis.statistical_type = self._determine_statistical_type(
            col_name, data_type
        )

        # Assess research potential
        col_analysis.research_potential = self._assess_column_research_potential(
            col_name, data_type, col_analysis.statistical_type
        )

        # Identify keys
        col_analysis.is_primary_key = self._is_likely_primary_key(col_name, data_type)
        col_analysis.is_foreign_key = self._is_likely_foreign_key(col_name, data_type)

        # Generate sample queries
        col_analysis.sample_queries = self._generate_column_sample_queries(
            col_name, col_analysis.statistical_type
        )

        return col_analysis

    def _determine_statistical_type(self, col_name: str, data_type: str) -> str:
        """Determine statistical type of column."""
        name_lower = col_name.lower()
        type_upper = data_type.upper()

        # Temporal indicators
        if any(
            x in name_lower for x in ["date", "time", "created", "updated", "timestamp"]
        ):
            return "temporal"
        if any(x in type_upper for x in ["DATE", "TIME", "TIMESTAMP", "DATETIME"]):
            return "temporal"

        # Identifier indicators
        if any(x in name_lower for x in ["id", "_id", "key", "_key", "uuid", "guid"]):
            return "identifier"
        if "ID" in type_upper or "UUID" in type_upper:
            return "identifier"

        # Numerical indicators
        if any(
            x in type_upper
            for x in ["INT", "FLOAT", "DOUBLE", "DECIMAL", "NUMERIC", "NUMBER"]
        ):
            # Check if it's likely a categorical encoded as number
            if any(
                x in name_lower
                for x in ["status", "type", "category", "level", "rank", "grade"]
            ):
                return "categorical"
            return "numerical"

        # Categorical indicators (string types)
        if any(x in type_upper for x in ["STRING", "VARCHAR", "CHAR", "TEXT"]):
            return "categorical"

        # Boolean
        if "BOOL" in type_upper:
            return "categorical"

        return "categorical"  # Default

    def _assess_column_research_potential(
        self, col_name: str, _data_type: str, stat_type: str
    ) -> str:
        """Assess research potential of column."""
        name_lower = col_name.lower()

        # High potential indicators
        high_indicators = [
            "amount",
            "value",
            "price",
            "cost",
            "revenue",
            "profit",
            "score",
            "rating",
            "satisfaction",
            "performance",
            "conversion",
            "count",
            "quantity",
            "duration",
            "frequency",
            "percentage",
            "rate",
            "ratio",
        ]

        if any(indicator in name_lower for indicator in high_indicators):
            return "high"

        # Medium potential for good categorical/temporal variables
        if stat_type in ["categorical", "temporal"]:
            medium_indicators = [
                "status",
                "type",
                "category",
                "segment",
                "channel",
                "source",
                "region",
            ]
            if any(indicator in name_lower for indicator in medium_indicators):
                return "medium"

        # Numerical columns generally have medium research potential
        if stat_type == "numerical":
            return "medium"

        # Low potential for identifiers and generic text
        if stat_type == "identifier" or "description" in name_lower:
            return "low"

        return "medium"  # Default

    def _classify_table_type(
        self, table_name: str, columns: Dict[str, ColumnAnalysis]
    ) -> str:
        """Classify table as fact, dimension, etc."""
        name_lower = table_name.lower()

        # Fact table indicators
        fact_indicators = [
            "sales",
            "orders",
            "transactions",
            "events",
            "logs",
            "activity",
            "metrics",
            "measurements",
            "fact",
            "records",
        ]

        # Dimension table indicators
        dimension_indicators = [
            "customer",
            "product",
            "user",
            "employee",
            "location",
            "time",
            "category",
            "type",
            "lookup",
            "reference",
            "dimension",
            "dim",
        ]

        # Count numerical vs categorical columns
        numerical_count = sum(
            1 for col in columns.values() if col.statistical_type == "numerical"
        )
        categorical_count = sum(
            1 for col in columns.values() if col.statistical_type == "categorical"
        )

        # Classification logic
        if (
            any(indicator in name_lower for indicator in fact_indicators)
            or numerical_count > categorical_count
        ):
            return "fact"
        elif any(indicator in name_lower for indicator in dimension_indicators):
            return "dimension"
        elif categorical_count > numerical_count:
            return "dimension"

        return "fact"  # Default assumption

    def _assess_table_research_value(self, table_analysis: TableAnalysis) -> str:
        """Assess research value of table."""
        high_value_columns = sum(
            1
            for col in table_analysis.columns.values()
            if col.research_potential == "high"
        )
        total_columns = len(table_analysis.columns)

        if high_value_columns >= 3 or (high_value_columns >= 2 and total_columns <= 10):
            return "high"
        elif high_value_columns >= 1 or table_analysis.entity_type == "fact":
            return "medium"
        else:
            return "low"

    def _generate_table_analysis_suggestions(
        self, table_analysis: TableAnalysis
    ) -> List[str]:
        """Generate analysis suggestions for table."""
        suggestions = []

        # Fact table suggestions
        if table_analysis.entity_type == "fact":
            suggestions.append("📊 Analyze trends and patterns in numerical measures")
            suggestions.append("🎯 Investigate correlations between different metrics")

        # Dimension table suggestions
        if table_analysis.entity_type == "dimension":
            suggestions.append("📋 Use for segmentation analysis")
            suggestions.append("🔍 Analyze distribution of categorical variables")

        # High-value table suggestions
        if table_analysis.research_value == "high":
            suggestions.append("⭐ Priority table for research hypotheses")
            suggestions.append("📈 Suitable for statistical modeling")

        # Column-specific suggestions
        temporal_cols = [
            col
            for col in table_analysis.columns.values()
            if col.statistical_type == "temporal"
        ]
        if temporal_cols:
            suggestions.append("📅 Perform time-series analysis")
            suggestions.append("🕒 Investigate seasonal patterns")

        numerical_cols = [
            col
            for col in table_analysis.columns.values()
            if col.statistical_type == "numerical" and col.research_potential == "high"
        ]
        if len(numerical_cols) >= 2:
            suggestions.append(
                "🧮 Calculate correlation matrix between numerical variables"
            )

        return suggestions[:5]  # Limit to top 5 suggestions

    def _generate_column_sample_queries(
        self, col_name: str, stat_type: str
    ) -> List[str]:
        """Generate sample analysis queries for column."""
        queries = []

        if stat_type == "numerical":
            queries.extend(
                [
                    f"What is the average, min, and max {col_name}?",
                    f"Show the distribution of {col_name} values",
                    f"What are the outliers in {col_name}?",
                ]
            )
        elif stat_type == "categorical":
            queries.extend(
                [
                    f"What are the most common values in {col_name}?",
                    f"Show the distribution of {col_name} categories",
                    f"How many unique values are in {col_name}?",
                ]
            )
        elif stat_type == "temporal":
            queries.extend(
                [
                    f"What is the date range in {col_name}?",
                    f"Show trends over time using {col_name}",
                    f"What patterns exist in {col_name} by month/year?",
                ]
            )

        return queries[:3]  # Limit to 3 sample queries

    def _analyze_schema_patterns(self, report: SchemaAnalysisReport):
        """Analyze schema-wide patterns."""
        # Naming patterns
        naming_patterns = defaultdict(int)
        data_types = defaultdict(int)

        for table in report.tables.values():
            # Table naming patterns
            if "_" in table.name:
                naming_patterns["snake_case"] += 1
            if table.name.islower():
                naming_patterns["lowercase"] += 1
            if table.name.isupper():
                naming_patterns["uppercase"] += 1

            # Column data types
            for col in table.columns.values():
                data_types[col.data_type] += 1

        report.naming_patterns = dict(naming_patterns)
        report.data_type_distribution = dict(data_types)

        # Assess complexity
        avg_cols_per_table = report.total_columns / max(report.total_tables, 1)
        if report.total_tables > 20 or avg_cols_per_table > 15:
            report.schema_complexity = "complex"
        elif report.total_tables > 10 or avg_cols_per_table > 8:
            report.schema_complexity = "moderate"
        else:
            report.schema_complexity = "simple"

    def _classify_tables(self, report: SchemaAnalysisReport):
        """Classify tables by research value and type."""
        for table_name, table in report.tables.items():
            if table.research_value == "high":
                report.high_value_tables.append(table_name)

            if table.entity_type == "fact":
                report.potential_fact_tables.append(table_name)
            elif table.entity_type == "dimension":
                report.potential_dimension_tables.append(table_name)

    def _identify_relationships(self, report: SchemaAnalysisReport):
        """Identify potential relationships between tables."""
        relationships = []

        # Look for foreign key patterns
        for table_name, table in report.tables.items():
            for col_name, col in table.columns.items():
                if col.is_foreign_key:
                    # Try to find matching table
                    potential_ref = col_name.replace("_id", "").replace("id", "")
                    for other_table in report.tables.keys():
                        if potential_ref.lower() in other_table.lower():
                            relationships.append(
                                {
                                    "from_table": table_name,
                                    "from_column": col_name,
                                    "to_table": other_table,
                                    "relationship_type": "foreign_key",
                                }
                            )

        report.suggested_relationships = relationships[:10]  # Limit to 10 relationships

    def _assess_research_potential(self, report: SchemaAnalysisReport):
        """Assess overall research readiness."""
        high_value_count = len(report.high_value_tables)
        fact_table_count = len(report.potential_fact_tables)

        # Data model type
        if len(report.potential_dimension_tables) > len(report.potential_fact_tables):
            report.data_model_type = "normalized"
        elif fact_table_count > 0 and len(report.potential_dimension_tables) == 0:
            report.data_model_type = "denormalized"
        else:
            report.data_model_type = "mixed"

        # Research readiness
        if high_value_count >= 3 and fact_table_count >= 1:
            report.research_readiness = "excellent"
        elif high_value_count >= 2 or fact_table_count >= 1:
            report.research_readiness = "good"
        else:
            report.research_readiness = "needs_preparation"

    def _enhance_with_sample_data(self, report: SchemaAnalysisReport):
        """Enhance analysis with sample data (limited implementation)."""
        logger.info("🔍 Sampling data for enhanced analysis...")

        # For high-value tables, try to get row counts
        for table_name in report.high_value_tables[:5]:  # Limit to 5 tables
            try:
                count_query = f"How many rows are in the {table_name} table?"
                result = self.sql_agent.query(count_query)

                # Extract row count from answer (simplified)
                if result.results and len(result.results) > 0:
                    # Try to find a number in the first result
                    first_result = str(result.results[0])
                    numbers = re.findall(r"\d+", first_result)
                    if numbers:
                        report.tables[table_name].row_count_estimate = int(numbers[0])

            except Exception as e:
                logger.debug(f"Could not get row count for {table_name}: {e}")
                continue

    def _generate_analysis_instructions(self, report: SchemaAnalysisReport):
        """Generate step-by-step analysis instructions."""
        steps = []
        recommendations = []

        # Step 1: Schema overview
        steps.append(
            f"🏗️  **Schema Overview**: Analyzed {report.total_tables} tables with {report.total_columns} columns total"
        )
        steps.append(
            f"📊 **Complexity Assessment**: {report.schema_complexity.title()} schema with {report.data_model_type} data model"
        )

        # Step 2: High-value tables identification
        if report.high_value_tables:
            steps.append(
                f"⭐ **High-Value Tables Identified**: {', '.join(report.high_value_tables[:5])}"
            )
            recommendations.append(
                {
                    "category": "Priority Analysis",
                    "description": "Focus initial research on high-value tables",
                    "tables": report.high_value_tables[:3],
                    "confidence": "high",
                }
            )

        # Step 3: Data model structure
        if report.potential_fact_tables:
            steps.append(
                f"📈 **Fact Tables for Analysis**: {', '.join(report.potential_fact_tables[:3])}"
            )
            recommendations.append(
                {
                    "category": "Quantitative Analysis",
                    "description": "Use fact tables for metrics and trend analysis",
                    "tables": report.potential_fact_tables[:3],
                    "confidence": "high",
                }
            )

        if report.potential_dimension_tables:
            steps.append(
                f"📋 **Dimension Tables for Segmentation**: {', '.join(report.potential_dimension_tables[:3])}"
            )
            recommendations.append(
                {
                    "category": "Segmentation Analysis",
                    "description": "Use dimension tables for grouping and filtering",
                    "tables": report.potential_dimension_tables[:3],
                    "confidence": "medium",
                }
            )

        # Step 4: Relationship analysis
        if report.suggested_relationships:
            steps.append(
                f"🔗 **Relationships Identified**: {len(report.suggested_relationships)} potential table relationships"
            )
            recommendations.append(
                {
                    "category": "Relationship Analysis",
                    "description": "Explore relationships between tables for comprehensive insights",
                    "tables": list(
                        set(
                            [
                                r["from_table"]
                                for r in report.suggested_relationships[:3]
                            ]
                        )
                    ),
                    "confidence": "medium",
                }
            )

        # Step 5: Research readiness assessment
        steps.append(
            f"🎯 **Research Readiness**: {report.research_readiness.title()} - ready for {self._get_readiness_description(report.research_readiness)}"
        )

        # Generate specific recommendations based on readiness
        if report.research_readiness == "excellent":
            recommendations.append(
                {
                    "category": "Advanced Analytics",
                    "description": "Schema is ready for sophisticated statistical analysis and modeling",
                    "suggested_analyses": [
                        "Correlation analysis",
                        "Regression modeling",
                        "Segmentation analysis",
                    ],
                    "confidence": "high",
                }
            )
        elif report.research_readiness == "good":
            recommendations.append(
                {
                    "category": "Intermediate Analytics",
                    "description": "Schema supports good analytical insights with some limitations",
                    "suggested_analyses": [
                        "Trend analysis",
                        "Comparative analysis",
                        "Basic statistics",
                    ],
                    "confidence": "medium",
                }
            )
        else:
            recommendations.append(
                {
                    "category": "Basic Analytics",
                    "description": "Focus on data exploration and preparation before advanced analysis",
                    "suggested_analyses": [
                        "Data profiling",
                        "Distribution analysis",
                        "Data quality assessment",
                    ],
                    "confidence": "medium",
                }
            )

        report.analysis_steps = steps
        report.recommended_analyses = recommendations

    def _get_readiness_description(self, readiness: str) -> str:
        """Get description of research readiness level."""
        descriptions = {
            "excellent": "advanced statistical analysis and machine learning",
            "good": "intermediate analytics and trend analysis",
            "needs_preparation": "basic exploration and data preparation",
        }
        return descriptions.get(readiness, "general analysis")

    def _is_likely_primary_key(self, col_name: str, data_type: str) -> bool:
        """Determine if column is likely a primary key."""
        name_lower = col_name.lower()
        return (
            name_lower in ["id", "pk", "key"]
            or name_lower.endswith("_id")
            and "ID" in data_type.upper()
        )

    def _is_likely_foreign_key(self, col_name: str, _data_type: str) -> bool:
        """Determine if column is likely a foreign key."""
        name_lower = col_name.lower()
        return (
            name_lower.endswith("_id")
            and name_lower != "id"
            or "fk_" in name_lower
            or name_lower.endswith("_key")
        )

    def _render_high_value_tables_section(self, report: SchemaAnalysisReport) -> list:
        """Render the high-value tables section of the report."""
        lines = ["⭐ HIGH-VALUE TABLES FOR RESEARCH:", "-" * 50]
        for table_name in report.high_value_tables:
            table = report.tables[table_name]
            high_value_cols = [
                col.name
                for col in table.columns.values()
                if col.research_potential == "high"
            ]
            lines.extend(
                [
                    f"📊 {table_name.upper()}",
                    f"   Type: {table.entity_type.title()}",
                    f"   Columns: {len(table.columns)}",
                    f"   High-value columns: {', '.join(high_value_cols[:5])}",
                    f"   Row estimate: {table.row_count_estimate or 'Unknown'}",
                    "",
                ]
            )
        return lines

    def _render_table_detail_section(self, table_name: str, table) -> list:
        """Render the detail block for a single table."""
        lines = [
            f"🗂️  TABLE: {table_name}",
            f"   Full Name: {table.full_name}",
            f"   Type: {table.entity_type.title()}",
            f"   Research Value: {table.research_value.title()}",
            f"   Columns: {len(table.columns)} total",
        ]
        col_types: dict = {}
        for col in table.columns.values():
            col_types[col.statistical_type] = col_types.get(col.statistical_type, 0) + 1
        lines.append(
            f"   Column Types: {', '.join(f'{c} {t}' for t, c in col_types.items())}"
        )
        if table.primary_keys:
            lines.append(f"   Primary Keys: {', '.join(table.primary_keys)}")
        if table.foreign_keys:
            lines.append(f"   Foreign Keys: {', '.join(table.foreign_keys[:3])}")
        if table.analysis_suggestions:
            lines.append("   💡 Analysis Suggestions:")
            for suggestion in table.analysis_suggestions[:3]:
                lines.append(f"      • {suggestion}")
        lines.append("")
        return lines

    def _render_recommendations_section(self, report: SchemaAnalysisReport) -> list:
        """Render the research recommendations section."""
        lines = ["💡 RESEARCH RECOMMENDATIONS:", "-" * 50]
        for rec in report.recommended_analyses:
            lines.extend(
                [
                    f"🎯 {rec['category'].upper()}",
                    f"   Description: {rec['description']}",
                    f"   Confidence: {rec.get('confidence', 'medium').title()}",
                ]
            )
            if "tables" in rec:
                lines.append(f"   Focus Tables: {', '.join(rec['tables'])}")
            if "suggested_analyses" in rec:
                lines.append(f"   Analyses: {', '.join(rec['suggested_analyses'])}")
            lines.append("")
        return lines

    def generate_detailed_report(self, report: SchemaAnalysisReport) -> str:
        """Generate a detailed text report of the schema analysis."""
        report_lines: list = [
            "=" * 80,
            "🔬 COMPREHENSIVE DATABASE SCHEMA ANALYSIS REPORT",
            "=" * 80,
            f"📅 Analysis Date: {report.analysis_timestamp}",
            f"🗄️  Database Type: {report.database_type}",
            f"📊 Schema Overview: {report.total_tables} tables, {report.total_columns} columns",
            f"🏗️  Complexity: {report.schema_complexity.title()}",
            f"📐 Data Model: {report.data_model_type.title()}",
            f"🎯 Research Readiness: {report.research_readiness.title()}",
            "",
            "📋 ANALYSIS STEPS PERFORMED:",
            "-" * 50,
        ]
        for i, step in enumerate(report.analysis_steps, 1):
            report_lines.append(f"{i:2}. {step}")
        report_lines.append("")

        if report.high_value_tables:
            report_lines.extend(self._render_high_value_tables_section(report))

        report_lines.extend(["📈 DETAILED TABLE ANALYSIS:", "-" * 50])
        for table_name, table in list(report.tables.items())[:10]:
            report_lines.extend(self._render_table_detail_section(table_name, table))

        report_lines.extend(["🔍 SCHEMA PATTERNS & INSIGHTS:", "-" * 50])
        if report.naming_patterns:
            patterns = ", ".join(f"{p}: {c}" for p, c in report.naming_patterns.items())
            report_lines.append(f"📝 Naming Patterns: {patterns}")
        if report.data_type_distribution:
            top_types = sorted(
                report.data_type_distribution.items(), key=lambda x: x[1], reverse=True
            )[:5]
            report_lines.append(
                f"🏷️  Data Types: {', '.join(f'{t}: {c}' for t, c in top_types)}"
            )
        report_lines.append("")

        if report.suggested_relationships:
            report_lines.extend(["🔗 SUGGESTED TABLE RELATIONSHIPS:", "-" * 50])
            for rel in report.suggested_relationships[:5]:
                report_lines.append(
                    f"   {rel['from_table']}.{rel['from_column']} → {rel['to_table']} ({rel['relationship_type']})"
                )
            report_lines.append("")

        if report.recommended_analyses:
            report_lines.extend(self._render_recommendations_section(report))

        report_lines.extend(
            [
                "=" * 80,
                "🎯 NEXT STEPS:",
                "1. Focus on high-value tables for initial research",
                "2. Design hypotheses using identified relationships",
                "3. Start with recommended analysis types",
                "4. Use sample queries to explore column distributions",
                "5. Validate data quality before proceeding with analysis",
                "=" * 80,
            ]
        )
        return "\n".join(report_lines)
