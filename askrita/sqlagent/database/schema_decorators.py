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
#   google-cloud-bigquery (Apache-2.0)

"""
Schema enhancement decorators using Decorator pattern.

This module provides decorators for enhancing database schemas with additional
information like cross-project tables, metadata, and other database-specific enhancements.
"""

import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from google.cloud import bigquery

logger = logging.getLogger(__name__)


class SchemaProvider(ABC):
    """
    Abstract base class for schema providers.
    Can be a base schema provider or a decorator.
    """

    @abstractmethod
    def get_schema(self, config: Any) -> str:
        """
        Get the schema string.

        Args:
            config: Configuration object

        Returns:
            Schema string
        """
        pass


class BaseSchemaProvider(SchemaProvider):
    """
    Base schema provider that returns the original schema without any enhancements.
    """

    def __init__(self, base_schema: str):
        """
        Initialize with base schema.

        Args:
            base_schema: The original schema string
        """
        self.base_schema = base_schema

    def get_schema(self, config: Any) -> str:
        """Return the base schema without modifications."""
        return self.base_schema


class SchemaDecorator(SchemaProvider, ABC):
    """
    Abstract base class for schema decorators.

    Decorators wrap a schema provider and add additional functionality
    while maintaining the same interface.
    """

    def __init__(self, schema_provider: SchemaProvider):
        """
        Initialize decorator with a schema provider.

        Args:
            schema_provider: The schema provider to decorate
        """
        self.schema_provider = schema_provider

    def get_schema(self, config: Any) -> str:
        """
        Get schema from wrapped provider and apply decorations.

        Args:
            config: Configuration object

        Returns:
            Enhanced schema string
        """
        base_schema = self.schema_provider.get_schema(config)
        return self.enhance_schema(base_schema, config)

    @abstractmethod
    def enhance_schema(self, schema: str, config: Any) -> str:
        """
        Enhance the schema with decorator-specific functionality.

        Args:
            schema: Base schema string
            config: Configuration object

        Returns:
            Enhanced schema string
        """
        pass


class CrossProjectSchemaDecorator(SchemaDecorator):
    """
    Decorator for adding cross-project tables to BigQuery schemas.

    This decorator fetches metadata from cross-project datasets and appends
    them to the base schema as additional table definitions.
    """

    def enhance_schema(self, schema: str, config: Any) -> str:
        """
        Enhance BigQuery schema with cross-project tables.

        Args:
            schema: Base schema string from standard extraction
            config: Database configuration object

        Returns:
            Enhanced schema string including cross-project tables
        """
        try:
            logger.info(
                "============== CROSS-PROJECT SCHEMA ENHANCEMENT =============="
            )
            logger.info("Original schema length: %s characters", len(schema))

            # Get the project ID from config
            project_id = config.database.bigquery_project_id
            logger.info("Using BigQuery project ID: %s", project_id)

            if not project_id:
                logger.warning(
                    "No BigQuery project ID specified in config, skipping cross-project enhancement"
                )
                return schema

            # Initialize BigQuery client with the project from config
            bigquery_client = bigquery.Client(project=project_id)

            # Check if cross-project access is enabled and configured
            cross_project_config = config.database.cross_project_access
            if not cross_project_config.enabled or not cross_project_config.datasets:
                logger.info(
                    "Cross-project access is disabled or no datasets configured, skipping enhancement"
                )
                return schema

            logger.info(
                f"Cross-project access enabled with {len(cross_project_config.datasets)} datasets"
            )

            # Process each configured cross-project dataset
            enhanced_schema = schema
            for cross_project_dataset in cross_project_config.datasets:
                try:
                    dataset_enhancement = self._enhance_with_dataset(
                        cross_project_dataset, bigquery_client, config
                    )
                    if dataset_enhancement:
                        enhanced_schema += dataset_enhancement

                except Exception as e:
                    logger.error(
                        f"Error fetching cross-project metadata from {cross_project_dataset}: {e}"
                    )
                    # Continue processing other datasets on error
                    continue

            logger.info(
                f"Cross-project schema enhancement complete. Final length: {len(enhanced_schema)} characters"
            )
            return enhanced_schema

        except Exception as e:
            logger.error(f"Error in cross-project schema enhancement: {e}")
            # Fall back to original schema on error
            return schema

    def _enhance_with_dataset(
        self, cross_project_dataset: str, bigquery_client: bigquery.Client, config: Any
    ) -> str:
        """
        Enhance schema with tables from a specific cross-project dataset.

        Args:
            cross_project_dataset: Dataset identifier (project.dataset format)
            bigquery_client: BigQuery client instance
            config: Configuration object

        Returns:
            Schema enhancement string for this dataset
        """
        logger.info(
            f"Fetching metadata for cross-project dataset: {cross_project_dataset}"
        )

        # SQL query to get table information
        metadata_query = f"""
        SELECT table_name, column_name, data_type
        FROM `{cross_project_dataset}.INFORMATION_SCHEMA.COLUMNS`
        ORDER BY table_name, column_name
        """

        # Execute query to get table metadata
        metadata_df = bigquery_client.query(metadata_query).to_dataframe()

        if metadata_df.empty:
            logger.warning(
                f"No metadata found for cross-project dataset: {cross_project_dataset}"
            )
            return ""

        # Group by table and format table definitions
        tables_metadata = {}
        for _, row in metadata_df.iterrows():
            table = row["table_name"]
            column = row["column_name"]
            data_type = row["data_type"]

            if table not in tables_metadata:
                tables_metadata[table] = []
            tables_metadata[table].append(f"{column} {data_type}")

        # Apply include/exclude filters if configured
        filtered_tables = self._apply_table_filters(tables_metadata, config)

        # Format cross-project tables into schema string for this dataset
        cross_project_schema = (
            f"\n\n-- CROSS-PROJECT TABLES FROM {cross_project_dataset} --\n"
        )
        cross_project_schema += (
            "-- IMPORTANT: Always use FULLY QUALIFIED table names in queries --\n"
        )
        for table, columns in filtered_tables.items():
            qualified_table = f"{cross_project_dataset}.{table}"
            cross_project_schema += (
                f"\n\n-- Table: {table} (ALWAYS USE FULL NAME: {qualified_table})\n"
            )
            cross_project_schema += f"CREATE TABLE {qualified_table} (\n"
            cross_project_schema += ",\n".join(f"  {col}" for col in columns)
            cross_project_schema += "\n);\n"
            cross_project_schema += f"-- REMINDER: Use `{qualified_table}` in ALL queries, NOT just `{table}` --\n"

        logger.info(
            f"Successfully enhanced schema with {len(filtered_tables)} tables from {cross_project_dataset}"
        )
        return cross_project_schema

    def _apply_table_filters(
        self, tables_metadata: Dict[str, List[str]], config: Any
    ) -> Dict[str, List[str]]:
        """
        Apply include/exclude filters to table metadata.

        Args:
            tables_metadata: Dictionary of table name to column definitions
            config: Configuration object

        Returns:
            Filtered tables metadata
        """
        cross_project_config = config.database.cross_project_access

        # Apply include filters if specified
        include_tables = getattr(cross_project_config, "include_tables", [])
        if include_tables:
            logger.info(
                f"Applying include_tables filter with patterns: {include_tables}"
            )
            # If include list is specified, only include matching tables
            filtered_tables = {}
            for table_name, columns in tables_metadata.items():
                matches = [
                    self._matches_pattern(table_name, pattern)
                    for pattern in include_tables
                ]
                if any(matches):
                    logger.info(f"✅ Table '{table_name}' matched include patterns")
                    filtered_tables[table_name] = columns
                else:
                    logger.debug(
                        f"❌ Table '{table_name}' did not match any include patterns: {include_tables}"
                    )
            logger.info(
                f"Include filter result: {len(filtered_tables)} tables included out of {len(tables_metadata)} total"
            )
            tables_metadata = filtered_tables

        # Apply exclude filters if specified
        exclude_tables = getattr(cross_project_config, "exclude_tables", [])
        if exclude_tables:
            # Remove tables that match exclude patterns
            filtered_tables = {}
            for table_name, columns in tables_metadata.items():
                if not any(
                    self._matches_pattern(table_name, pattern)
                    for pattern in exclude_tables
                ):
                    filtered_tables[table_name] = columns
            tables_metadata = filtered_tables

        return tables_metadata

    def _matches_pattern(self, table_name: str, pattern: str) -> bool:
        """
        Check if table name matches a pattern (supports wildcards).

        Smart matching logic:
        1. If pattern contains dots (project.dataset.table), extract just the table part
        2. Support wildcards in both full paths and table names
        3. Case-insensitive matching

        Args:
            table_name: Name of the table (just the table name, no project/dataset)
            pattern: Pattern to match (can be full path or just table name, supports * wildcard)

        Returns:
            True if table matches pattern, False otherwise
        """
        import fnmatch

        table_name_lower = table_name.lower()
        pattern_lower = pattern.lower()

        logger.debug(
            f"Pattern matching: table='{table_name_lower}' vs pattern='{pattern_lower}'"
        )

        # If pattern contains dots, try matching the table-name portion first (BigQuery project.dataset.table)
        if "." in pattern_lower:
            pattern_parts = pattern_lower.split(".")
            if len(pattern_parts) >= 3:
                pattern_table_name = pattern_parts[-1]
                logger.debug(
                    f"Extracted table name from pattern: '{pattern_table_name}'"
                )
                if fnmatch.fnmatch(table_name_lower, pattern_table_name):
                    logger.debug(
                        f"✅ Match found: table '{table_name_lower}' matches pattern table name '{pattern_table_name}'"
                    )
                    return True

        # Direct match against the full pattern (handles both dotted and simple patterns)
        result = fnmatch.fnmatch(table_name_lower, pattern_lower)
        if result:
            logger.debug(
                f"MATCH Direct match: table '{table_name_lower}' vs pattern '{pattern_lower}' = {result}"
            )
        else:
            logger.debug(
                f"NO MATCH Direct match: table '{table_name_lower}' vs pattern '{pattern_lower}' = {result}"
            )
        return result


class SchemaMetadataDecorator(SchemaDecorator):
    """
    Decorator for adding metadata information to schemas.

    This decorator can add comments, timestamps, or other metadata
    to help with schema documentation and debugging.
    """

    def enhance_schema(self, schema: str, config: Any) -> str:
        """
        Enhance schema with metadata information.

        Args:
            schema: Base schema string
            config: Configuration object

        Returns:
            Schema with added metadata
        """
        from datetime import datetime

        metadata_header = f"""
-- Schema Generated: {datetime.now().isoformat()}
-- Database Type: {config.get_database_type()}
-- Schema Caching: {'Enabled' if config.database.cache_schema else 'Disabled'}
-- Query Timeout: {config.database.query_timeout}s
-- Max Results: {config.database.max_results}
"""

        # Add BigQuery-specific warnings for table qualification
        if config.get_database_type() == "BigQuery":
            metadata_header += """
-- ⚠️  BIGQUERY IMPORTANT: Always use FULLY QUALIFIED table names in queries
-- ⚠️  Format: `project.dataset.table` (with backticks)
-- ⚠️  NEVER use just table names like 'table_name' - this will cause errors
"""

        # Check if cross-project access is configured
        cross_project_config = getattr(config.database, "cross_project_access", None)
        if cross_project_config and getattr(cross_project_config, "enabled", False):
            metadata_header += f"-- Cross-project Access: Enabled ({len(getattr(cross_project_config, 'datasets', []))} datasets)\n"
        else:
            metadata_header += "-- Cross-project Access: Disabled\n"

        metadata_header += "--" + "=" * 70 + "\n"

        return metadata_header + schema


class SchemaFormattingDecorator(SchemaDecorator):
    """
    Decorator for improving schema formatting and readability.

    This decorator can clean up formatting, add proper indentation,
    and organize schema sections for better readability.
    """

    def enhance_schema(self, schema: str, config: Any) -> str:
        """
        Enhance schema formatting for better readability.

        Args:
            schema: Base schema string
            config: Configuration object

        Returns:
            Formatted schema string
        """
        # Split schema into lines for processing
        lines = schema.split("\n")
        formatted_lines = []

        in_create_table = False

        for line in lines:
            stripped = line.strip()

            # Handle CREATE TABLE statements
            if stripped.upper().startswith("CREATE TABLE"):
                if formatted_lines:  # Add spacing before new tables
                    formatted_lines.append("")
                formatted_lines.append(stripped)
                in_create_table = True
                continue

            # Handle table closing
            if in_create_table and stripped == ");":
                formatted_lines.append(stripped)
                in_create_table = False
                continue

            # Handle column definitions
            if in_create_table and stripped and not stripped.startswith("--"):
                # Clean up column definition formatting
                cleaned = stripped.rstrip(",")
                if stripped.endswith(","):
                    cleaned += ","
                formatted_lines.append("  " + cleaned)  # Indent columns
                continue

            # Handle comments and other lines
            formatted_lines.append(line)

        return "\n".join(formatted_lines)


class AutoDescriptionExtractor:
    """Extracts descriptions from database metadata automatically."""

    @staticmethod
    def _build_bq_queries(cross_project_dataset: str) -> List[str]:
        """Return the ordered list of INFORMATION_SCHEMA queries to try."""
        return [
            f"""
            SELECT table_name, column_name, data_type, description, is_nullable
            FROM `{cross_project_dataset}.INFORMATION_SCHEMA.COLUMNS`
            WHERE description IS NOT NULL AND description != ''
            ORDER BY table_name, ordinal_position
            """,
            f"""
            SELECT table_name, column_name, data_type,
                   CAST(NULL AS STRING) as description, is_nullable
            FROM `{cross_project_dataset}.INFORMATION_SCHEMA.COLUMNS`
            WHERE 1=2
            """,
        ]

    @staticmethod
    def _populate_descriptions_from_df(
        metadata_df, cross_project_dataset: str, descriptions: Dict[str, Dict[str, str]]
    ) -> None:
        """Fill *descriptions* in-place from a query result dataframe."""
        for _, row in metadata_df.iterrows():
            table_key = f"{cross_project_dataset}.{row['table_name']}"
            if table_key not in descriptions:
                descriptions[table_key] = {}
            raw = row["description"]
            # Coerce to plain str here — BigQuery / pyarrow may return non-str
            # scalar types whose .description attribute would cause downstream
            # recursion in DescriptionMerger._extract_string_value.
            # Also guard against pandas NaN (which passes `is not None`).
            descriptions[table_key][row["column_name"]] = (
                str(raw) if raw is not None and raw == raw else ""
            )
        logger.info(
            f"Extracted {len(descriptions)} table descriptions with "
            f"{sum(len(c) for c in descriptions.values())} column descriptions"
        )

    @staticmethod
    def _handle_bq_query_error(
        e: Exception, error_msg: str, attempt: int, cross_project_dataset: str
    ) -> bool:
        """Log the error and return True if the caller should *continue* to the next query."""
        if "unrecognized name: description" in error_msg and attempt == 0:
            logger.info(
                f"Dataset {cross_project_dataset} INFORMATION_SCHEMA doesn't include "
                "description column - this is normal for some BigQuery projects"
            )
            return True  # try fallback query
        logger.warning(
            f"Could not extract BigQuery descriptions from {cross_project_dataset}: {e}"
        )
        if "permission" in error_msg or "access denied" in error_msg:
            logger.warning(
                f"Insufficient permissions to access INFORMATION_SCHEMA in {cross_project_dataset}"
            )
        return False  # stop trying

    @staticmethod
    def extract_bigquery_descriptions(
        cross_project_dataset: str, bigquery_client
    ) -> Dict[str, Dict[str, str]]:
        """Extract column descriptions from BigQuery INFORMATION_SCHEMA."""
        descriptions: Dict[str, Dict[str, str]] = {}
        queries = AutoDescriptionExtractor._build_bq_queries(cross_project_dataset)

        for i, query in enumerate(queries):
            log_msg = (
                f"Extracting BigQuery descriptions from {cross_project_dataset}"
                if i == 0
                else f"Attempting fallback query for {cross_project_dataset} (description column not supported)"
            )
            logger.info(log_msg)

            try:
                metadata_df = bigquery_client.query(query).to_dataframe()
                if i == 0 and len(metadata_df) > 0:
                    AutoDescriptionExtractor._populate_descriptions_from_df(
                        metadata_df, cross_project_dataset, descriptions
                    )
                else:
                    logger.info(
                        f"Dataset {cross_project_dataset} does not support column descriptions "
                        "or has no descriptions available"
                    )
                break  # query executed successfully

            except Exception as e:
                should_continue = AutoDescriptionExtractor._handle_bq_query_error(
                    e, str(e).lower(), i, cross_project_dataset
                )
                if not should_continue:
                    break

        return descriptions

    @staticmethod
    def extract_postgresql_descriptions(
        connection_string: str,
    ) -> Dict[str, Dict[str, str]]:
        """Extract descriptions from PostgreSQL pg_description."""
        logger.debug("PostgreSQL description extraction not yet implemented")
        return {}

    @staticmethod
    def extract_mysql_descriptions(connection_string: str) -> Dict[str, Dict[str, str]]:
        """Extract descriptions from MySQL COLUMN_COMMENT."""
        logger.debug("MySQL description extraction not yet implemented")
        return {}


class DescriptionMerger:
    """Merges automatic and manual descriptions based on priority rules."""

    def __init__(self, manual_config):
        """Initialize with manual configuration."""
        self.manual_config = manual_config

    def _extract_string_value(self, value) -> str:
        """
        Safely extract a plain string from a value.

        Handles three cases:
        - str / None  → returned as-is (most common path after source-level coercion)
        - ColumnDescriptionConfig-like object → read .description (one level only;
          the field is typed str so no further unwrapping is needed)
        - anything else → str(value)
        """
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        # ColumnDescriptionConfig duck-type: description + mode + business_context
        if (
            hasattr(value, "description")
            and hasattr(value, "mode")
            and hasattr(value, "business_context")
        ):
            desc = getattr(value, "description", "")
            return desc if isinstance(desc, str) else str(desc)
        try:
            return str(value)
        except Exception:
            return ""

    @staticmethod
    def _combine_text_and_context(text: str, context: str) -> str:
        """Join manual text with optional business context."""
        if context:
            return f"{text} | {context}"
        return text

    def _auto_or_column_fallback(
        self, auto_desc, column_name: str
    ) -> Optional[str]:
        """Return auto description, column-name fallback, or None."""
        if auto_desc:
            return self._extract_string_value(auto_desc)
        if self.manual_config.automatic_extraction.fallback_to_column_name:
            return self._format_column_name_as_description(column_name)
        return None

    def _merge_supplement(
        self, auto_desc, manual_text: str, business_context: str, column_name: str
    ) -> Optional[str]:
        """Combine auto + manual parts for supplement mode."""
        parts = []
        if auto_desc:
            parts.append(self._extract_string_value(auto_desc))
        if manual_text:
            parts.append(manual_text)
        if business_context:
            parts.append(business_context)
        if parts:
            return " | ".join(parts)
        if self.manual_config.automatic_extraction.fallback_to_column_name:
            return self._format_column_name_as_description(column_name)
        return None

    def merge_column_description(
        self,
        auto_descriptions: Dict[str, Dict[str, str]],
        table_name: str,
        column_name: str,
    ) -> Optional[str]:
        """
        Merge descriptions using priority system:
        1. Manual override (highest priority)
        2. Manual supplement (auto + manual)
        3. Automatic fallback
        4. Default fallback (column name)
        """
        manual_desc = self.manual_config.columns.get(column_name)
        auto_desc = auto_descriptions.get(table_name, {}).get(column_name)

        if manual_desc is not None:
            logger.debug(
                f"Column {column_name}: manual_desc type = {type(manual_desc)}, value = {manual_desc}"
            )
        if auto_desc is not None:
            logger.debug(
                f"Column {column_name}: auto_desc type = {type(auto_desc)}, value = {auto_desc}"
            )

        if manual_desc is None:
            return self._auto_or_column_fallback(auto_desc, column_name)

        mode = getattr(manual_desc, "mode", "supplement")
        manual_text = self._extract_string_value(getattr(manual_desc, "description", ""))
        business_context = self._extract_string_value(
            getattr(manual_desc, "business_context", "")
        )

        logger.debug(
            f"Column {column_name}: mode={mode}, manual_text='{manual_text[:50]}...', "
            f"business_context='{business_context[:50]}...'"
        )

        if mode == "override" and manual_text:
            return self._combine_text_and_context(manual_text, business_context)
        if mode == "supplement":
            return self._merge_supplement(auto_desc, manual_text, business_context, column_name)
        if mode == "fallback" and not auto_desc and manual_text:
            return self._combine_text_and_context(manual_text, business_context)
        if mode == "auto_only":
            return self._extract_string_value(auto_desc) if auto_desc else None

        return self._auto_or_column_fallback(auto_desc, column_name)

    def _format_column_name_as_description(self, column_name: str) -> str:
        """Convert column name to readable description."""
        # Convert snake_case or camelCase to readable format
        formatted = re.sub(r"[_-]", " ", column_name)
        formatted = re.sub(r"([a-z])([A-Z])", r"\1 \2", formatted)
        formatted = formatted.replace("_", " ").title()

        # Clean up common patterns
        formatted = re.sub(r"\bId\b", "ID", formatted)
        formatted = re.sub(r"\bCd\b", "Code", formatted)
        formatted = re.sub(r"\bTxt\b", "Text", formatted)
        formatted = re.sub(r"\bDt\b", "Date", formatted)

        return f"{formatted} (auto-generated)"


class HybridDescriptionDecorator(SchemaDecorator):
    """
    Decorator for adding hybrid automatic + manual schema descriptions.

    This decorator combines automatic description extraction from database metadata
    with manual descriptions from configuration, using a priority system to merge them.
    """

    def enhance_schema(self, schema: str, config: Any) -> str:
        """Enhance schema with hybrid descriptions."""
        try:
            logger.info(
                "============== ENHANCING SCHEMA WITH HYBRID DESCRIPTIONS =============="
            )

            # Get schema descriptions configuration
            desc_config = config.get_schema_descriptions()

            if not desc_config.automatic_extraction.enabled and not desc_config.columns:
                logger.info("Description enhancement disabled - skipping")
                return schema

            # Extract automatic descriptions if enabled
            auto_descriptions = {}
            if desc_config.automatic_extraction.enabled:
                auto_descriptions = self._extract_automatic_descriptions(config)

            # Create description merger
            merger = DescriptionMerger(desc_config)

            # Add project context header
            enhanced_schema = schema
            if desc_config.project_context:
                enhanced_schema = (
                    f"-- PROJECT: {desc_config.project_context}\n\n{enhanced_schema}"
                )

            # Enhance schema with descriptions
            enhanced_schema = self._add_descriptions_to_schema(
                enhanced_schema, auto_descriptions, merger
            )

            # Add business terms glossary
            if desc_config.business_terms:
                glossary = self._create_business_glossary(desc_config.business_terms)
                enhanced_schema = f"{enhanced_schema}\n\n{glossary}"

            logger.info("Schema enhancement complete. Added descriptions to schema.")
            return enhanced_schema

        except Exception as e:
            logger.error(f"Error enhancing schema with descriptions: {e}")
            return schema

    def _extract_automatic_descriptions(self, config: Any) -> Dict[str, Dict[str, str]]:
        """Extract automatic descriptions based on database type."""
        db_type = config.get_database_type()
        descriptions = {}

        if db_type == "BigQuery":
            try:
                # Get BigQuery client
                from google.cloud import bigquery

                client = bigquery.Client()

                # Extract from cross-project datasets if configured
                cross_project_config = getattr(
                    config.database, "cross_project_access", None
                )
                if cross_project_config and getattr(
                    cross_project_config, "enabled", False
                ):
                    datasets = getattr(cross_project_config, "datasets", [])
                    for dataset in datasets:
                        dataset_descriptions = (
                            AutoDescriptionExtractor.extract_bigquery_descriptions(
                                dataset, client
                            )
                        )
                        descriptions.update(dataset_descriptions)

                # Also extract from main project if configured
                if (
                    hasattr(config.database, "bigquery_project_id")
                    and config.database.bigquery_project_id
                ):
                    # Extract from default dataset or all datasets in main project
                    # This would need additional implementation based on requirements
                    pass

            except Exception as e:
                logger.warning(f"Could not extract BigQuery descriptions: {e}")

        elif db_type == "PostgreSQL":
            descriptions = AutoDescriptionExtractor.extract_postgresql_descriptions(
                config.database.connection_string
            )
        elif db_type == "MySQL":
            descriptions = AutoDescriptionExtractor.extract_mysql_descriptions(
                config.database.connection_string
            )

        return descriptions

    @staticmethod
    def _extract_table_name(stripped_line: str) -> Optional[str]:
        """Return table name from a CREATE TABLE line, or None."""
        match = re.search(r"CREATE TABLE\s+([^\s(]+)", stripped_line)
        return match.group(1).strip('`"') if match else None

    @staticmethod
    def _annotate_column_line(line: str, description: str) -> str:
        """Append an inline SQL comment with the description to a column line."""
        base = line.rstrip()
        if base.endswith(","):
            return f"{base[:-1]}, -- {description}"
        return f"{base}, -- {description}"

    def _process_column_line(
        self,
        line: str,
        stripped_line: str,
        current_table: str,
        auto_descriptions: Dict[str, Dict[str, str]],
        merger: DescriptionMerger,
    ) -> str:
        """Return the (possibly annotated) line for a column definition."""
        col_match = re.search(r"^\s*([^\s,]+)\s+", stripped_line)
        if not col_match:
            return line
        column_name = col_match.group(1).strip('`"')
        description = merger.merge_column_description(
            auto_descriptions, current_table, column_name
        )
        if description:
            return self._annotate_column_line(line, description)
        return line

    def _add_descriptions_to_schema(
        self,
        schema: str,
        auto_descriptions: Dict[str, Dict[str, str]],
        merger: DescriptionMerger,
    ) -> str:
        """Add descriptions to schema CREATE TABLE statements."""
        enhanced_lines = []
        current_table: Optional[str] = None
        in_create_table = False

        for line in schema.split("\n"):
            stripped_line = line.strip()

            if stripped_line.startswith("CREATE TABLE"):
                in_create_table = True
                current_table = self._extract_table_name(stripped_line)
                enhanced_lines.append(line)
                continue

            if in_create_table and stripped_line.endswith(");"):
                in_create_table = False
                current_table = None
                enhanced_lines.append(line)
                continue

            is_column_line = (
                in_create_table
                and current_table
                and stripped_line
                and not stripped_line.startswith("--")
            )
            if is_column_line:
                enhanced_lines.append(
                    self._process_column_line(
                        line, stripped_line, current_table, auto_descriptions, merger
                    )
                )
                continue

            enhanced_lines.append(line)

        return "\n".join(enhanced_lines)

    def _create_business_glossary(self, business_terms: Dict[str, str]) -> str:
        """Create a business terms glossary."""
        glossary = ["-- BUSINESS TERMS GLOSSARY --"]
        for term, definition in business_terms.items():
            # Ensure definition is a string
            if isinstance(definition, str):
                glossary.append(f"-- {term}: {definition}")
            else:
                logger.warning(
                    f"Invalid business term definition for '{term}': expected string, got {type(definition)}. Skipping."
                )
                # Convert to string as fallback
                str_definition = (
                    str(definition)
                    if definition is not None
                    else "No definition provided"
                )
                glossary.append(f"-- {term}: {str_definition}")
        return "\n".join(glossary)


class SchemaDecoratorBuilder:
    """
    Builder class for constructing schema decorator chains.

    Provides a fluent interface for combining multiple decorators.
    """

    def __init__(self, base_schema: str):
        """
        Initialize builder with base schema.

        Args:
            base_schema: The original schema string
        """
        self.schema_provider = BaseSchemaProvider(base_schema)

    def with_cross_project_enhancement(self) -> "SchemaDecoratorBuilder":
        """Add cross-project enhancement decorator."""
        self.schema_provider = CrossProjectSchemaDecorator(self.schema_provider)
        return self

    def with_hybrid_descriptions(self) -> "SchemaDecoratorBuilder":
        """Add hybrid automatic + manual description decorator."""
        self.schema_provider = HybridDescriptionDecorator(self.schema_provider)
        return self

    def with_metadata(self) -> "SchemaDecoratorBuilder":
        """Add metadata decorator."""
        self.schema_provider = SchemaMetadataDecorator(self.schema_provider)
        return self

    def with_formatting(self) -> "SchemaDecoratorBuilder":
        """Add formatting decorator."""
        self.schema_provider = SchemaFormattingDecorator(self.schema_provider)
        return self

    def build(self) -> SchemaProvider:
        """
        Build the final decorated schema provider.

        Returns:
            Decorated schema provider
        """
        return self.schema_provider
