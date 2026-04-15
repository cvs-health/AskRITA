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
#   langchain-community (MIT)
#   sqlalchemy (MIT)

"""Database connection management with strategy-based multi-database support."""

import logging
from typing import Any, Dict, List

from google.cloud import bigquery
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase

from ...config_manager import get_config
from ...exceptions import DatabaseError
from ...utils.constants import DisplayLimits
from ...utils.LLMManager import LLMManager
from .database_factory import DatabaseStrategyFactory

logger = logging.getLogger(__name__)

_BIGQUERY_SCHEME = "bigquery://"
_ACCESS_DENIED_MSG = "access denied"


class DatabaseManager:
    """Manages SQL database connections, schema retrieval, and query execution.

    Uses the Strategy pattern to support BigQuery, Snowflake, MySQL, PostgreSQL,
    SQLite, and other SQL databases through interchangeable connection strategies.
    """

    def __init__(
        self, config_manager=None, test_llm_connection=True, test_db_connection=True
    ):
        """
        Initialize DatabaseManager with configuration.

        Args:
            config_manager: Optional ConfigManager instance. If None, uses global config.
            test_llm_connection: Whether to test LLM connection during initialization (default: True)
            test_db_connection: Whether to test database connection during initialization (default: True)
        """
        self.config = config_manager or get_config()
        self.llm_manager = LLMManager(self.config, test_connection=test_llm_connection)

        # Initialize database strategy based on connection string
        self.db_strategy = DatabaseStrategyFactory.create_strategy(
            self.config.database.connection_string
        )
        logger.info(
            f"Using {self.db_strategy.__class__.__name__} for database operations"
        )

        # Initialize database connection
        self.db = None
        self.schema = None
        self._initialize_database()

        # Validate connection immediately after initialization (unless disabled for testing)
        if test_db_connection:
            db_type = self.config.get_database_type()
            logger.info(
                f"🔍 Testing {db_type} database connection during initialization..."
            )
            if not self.test_connection():
                logger.error(
                    f"❌ {db_type} database initialization failed - connection test failed"
                )
                raise DatabaseError(
                    "Database connection test failed after initialization. "
                    "Please verify your connection string, credentials, and database availability."
                )
            else:
                logger.info(
                    f"✅ {db_type} database initialization completed successfully"
                )
        else:
            logger.info(
                "⚠️ Database connection test skipped (test_db_connection=False)"
            )

    @staticmethod
    def _extract_db_host(connection_string: str) -> str:
        """Extract host portion from a connection string for error messages."""
        if "@" in connection_string:
            return connection_string.split("@")[1].split("/")[0]
        return "database host"

    def _raise_db_init_error(self, exc: Exception) -> None:
        """Translate a raw database init exception into a typed DatabaseError."""
        error_msg = str(exc).lower()
        connection_string = self.config.database.connection_string
        cs_lower = connection_string.lower()

        if "authentication" in error_msg or "password" in error_msg:
            raise DatabaseError(
                f"Database authentication failed: {exc}\n"
                "Please check your username, password, and connection string."
            )
        if "connection refused" in error_msg or "could not connect" in error_msg:
            host = self._extract_db_host(connection_string)
            raise DatabaseError(
                f"Cannot connect to database at {host}: {exc}\n"
                "Please check that the database server is running and accessible."
            )
        if "timeout" in error_msg:
            raise DatabaseError(
                f"Database connection timeout: {exc}\n"
                "The database server is not responding. Check network connectivity and server status."
            )
        if "does not exist" in error_msg or "unknown database" in error_msg:
            raise DatabaseError(
                f"Database not found: {exc}\n"
                "Please check that the database name in your connection string is correct."
            )
        if "bigquery" in cs_lower:
            raise DatabaseError(
                f"BigQuery connection failed: {exc}\n"
                "Please check your BigQuery project ID, credentials, and permissions.\n"
                "See: https://cloud.google.com/bigquery/docs/authentication"
            )
        if "snowflake" in cs_lower:
            raise DatabaseError(
                f"Snowflake connection failed: {exc}\n"
                "Please check your Snowflake account, credentials, warehouse, and network connectivity.\n"
                "Connection format: snowflake://${SNOWFLAKE_USER}:${SNOWFLAKE_PASSWORD}@account/database?warehouse=warehouse&schema=schema\n"
                "See: https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-api"
            )
        if "db2://" in cs_lower or "ibm_db_sa://" in cs_lower:
            raise DatabaseError(
                f"DB2 connection failed: {exc}\n"
                "Please check your DB2 hostname, port, credentials, and database name.\n"
                "Connection format: ibm_db_sa://${DB2_USER}:${DB2_PASSWORD}@hostname:port/database\n"
                "Ensure ibm-db-sa driver is installed: pip install ibm-db-sa\n"
                "See: https://github.com/ibmdb/python-ibmdb"
            )
        raise DatabaseError(f"Database connection failed: {str(exc)}")

    def _initialize_database(self) -> None:
        """Initialize database connection using configuration."""
        try:
            # Fix SQLAlchemy inherit_cache warnings at the source
            self._fix_sqlalchemy_inherit_cache_warnings()

            connection_string = self.config.database.connection_string
            logger.info(
                f"Connecting to database: {self.db_strategy.get_safe_connection_info(connection_string)}"
            )

            # Use strategy pattern for database-specific authentication setup
            self.db_strategy.setup_auth(self.config)

            self.db = SQLDatabase.from_uri(connection_string)
            logger.info("Database connection established successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database connection: {e}")
            self._raise_db_init_error(e)

    @staticmethod
    def _patch_sqlalchemy_functions() -> None:
        """Patch SQLAlchemy function classes to set inherit_cache=True."""
        try:
            from sqlalchemy.sql import functions

            if hasattr(functions, "unnest"):
                unnest_func = getattr(functions, "unnest")
                if not hasattr(unnest_func, "inherit_cache"):
                    unnest_func.inherit_cache = True
                    logger.debug("Fixed inherit_cache for 'unnest' function")

            for attr_name in dir(functions):
                attr = getattr(functions, attr_name, None)
                if (
                    hasattr(attr, "__mro__")
                    and any("Function" in cls.__name__ for cls in attr.__mro__)
                    and not hasattr(attr, "inherit_cache")
                ):
                    setattr(attr, "inherit_cache", True)
                    logger.debug(f"Set inherit_cache=True for {attr_name}")

        except Exception as e:
            logger.debug(f"Could not patch SQLAlchemy functions: {e}")

    @staticmethod
    def _patch_langchain_sql_constructs() -> None:
        """Patch LangChain SQL constructs that expose SQLAlchemy classes."""
        try:
            from langchain_community.utilities import sql_database

            for attr_name in dir(sql_database):
                if not attr_name.startswith("_"):
                    attr = getattr(sql_database, attr_name, None)
                    if (
                        hasattr(attr, "__mro__")
                        and hasattr(attr, "__module__")
                        and "sqlalchemy" in str(attr.__module__).lower()
                        and not hasattr(attr, "inherit_cache")
                    ):
                        try:
                            attr.inherit_cache = True
                            logger.debug(f"Patched inherit_cache for {attr_name}")
                        except AttributeError:
                            pass

        except ImportError:
            logger.debug("Could not import langchain SQL utilities for patching")

    _SQL_PATCH_KEYWORDS = ("sql", "column", "function", "unnest", "query")

    @staticmethod
    def _is_patchable_sql_class(attr, attr_name: str, patched_classes: set) -> bool:
        """Return True if attr is an unpatched SQL-related class that needs inherit_cache."""
        return (
            hasattr(attr, "__mro__")
            and hasattr(attr, "__name__")
            and attr.__name__ not in patched_classes
            and not hasattr(attr, "inherit_cache")
            and any(kw in attr.__name__.lower() for kw in DatabaseManager._SQL_PATCH_KEYWORDS)
        )

    @staticmethod
    def _patch_module_attrs(module, patched_classes: set) -> None:
        """Patch SQL-related classes found in a single module."""
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            try:
                attr = getattr(module, attr_name, None)
                if DatabaseManager._is_patchable_sql_class(attr, attr_name, patched_classes):
                    attr.inherit_cache = True
                    patched_classes.add(attr.__name__)
                    logger.debug(f"Patched inherit_cache for {attr.__name__}")
            except (AttributeError, TypeError):
                continue

    @staticmethod
    def _patch_loaded_modules() -> None:
        """Patch SQL-related classes in all already-loaded langchain/sqlalchemy modules."""
        try:
            import sys

            patched_classes: set = set()

            for module_name, module in sys.modules.items():
                if (
                    module
                    and (
                        "langchain" in module_name.lower()
                        or "sqlalchemy" in module_name.lower()
                    )
                    and hasattr(module, "__dict__")
                ):
                    DatabaseManager._patch_module_attrs(module, patched_classes)

        except Exception as e:
            logger.debug(f"Could not perform comprehensive patching: {e}")

    def _fix_sqlalchemy_inherit_cache_warnings(self) -> None:
        """
        Fix SQLAlchemy inherit_cache warnings by patching problematic classes.

        This addresses the specific warning:
        'Class unnest will not make use of SQL compilation caching as it does not set the inherit_cache attribute'
        """
        try:
            logger.debug("Applying SQLAlchemy inherit_cache fixes...")
            self._patch_sqlalchemy_functions()
            self._patch_langchain_sql_constructs()
            self._patch_loaded_modules()
            logger.debug("SQLAlchemy inherit_cache fixes completed")

        except Exception as e:
            logger.debug(f"Could not patch SQLAlchemy inherit_cache warnings: {e}")

    def get_schema(self) -> str:
        """Retrieve the database schema, with configurable caching."""
        # Check if we should use cached schema
        if self.config.database.cache_schema:
            cached_schema = self.config.get_schema_cache()
            if cached_schema:
                logger.debug("Using cached database schema")
                return cached_schema

        try:
            logger.info("Fetching database schema from database")
            toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm_manager.llm)
            tools = toolkit.get_tools()

            sql_db_schema_tool = next(
                tool for tool in tools if tool.name == "sql_db_schema"
            )
            list_tables_tool = next(
                tool for tool in tools if tool.name == "sql_db_list_tables"
            )

            # Fetch table names and use them to retrieve the schema
            table_names = list_tables_tool.invoke("")
            schema = sql_db_schema_tool.invoke(table_names)

            # Use strategy pattern for database-specific schema enhancement
            schema = self.db_strategy.enhance_schema(schema, self.config)

            # Cache the schema if caching is enabled
            if self.config.database.cache_schema:
                self.config.set_schema_cache(schema)
                logger.info("Database schema cached successfully")

            self.schema = schema
            return schema

        except Exception as e:
            logger.error(f"Error fetching schema: {e}")
            raise DatabaseError(f"Error fetching schema: {str(e)}")

    def _normalize_result(self, raw_result: Any) -> List[Dict[str, Any]]:
        """
        Normalize database results to always return List[Dict[str, Any]].

        Args:
            raw_result: Raw result from database (can be list, tuple, dict, str, etc.)

        Returns:
            Normalized result as List[Dict[str, Any]]

        Raises:
            DatabaseError: If result cannot be normalized
        """
        # Handle empty results
        if not raw_result:
            return []

        # Already in correct format
        if isinstance(raw_result, list):
            if not raw_result:
                return []
            if isinstance(raw_result[0], dict):
                return raw_result
            # List of tuples/lists - need column names
            # This should be handled by getting column names from cursor
            # For now, convert to generic dict with indices
            return [
                {"col_" + str(i): val for i, val in enumerate(row)}
                for row in raw_result
            ]

        # Single dict result
        if isinstance(raw_result, dict):
            return [raw_result]

        # Error string
        if isinstance(raw_result, str):
            if raw_result.startswith("Error:"):
                raise DatabaseError(raw_result)
            # Try to parse string representation
            import ast

            try:
                parsed = ast.literal_eval(raw_result)
                return self._normalize_result(parsed)  # Recursively normalize
            except (ValueError, SyntaxError):
                # Plain string result (e.g., from COUNT(*)) - wrap in dict
                return [{"result": raw_result}]

        raise DatabaseError(f"Unexpected result type: {type(raw_result)}")

    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute an SQL query on the database and return the results.

        Args:
            query: SQL query string to execute

        Returns:
            Query results as List[Dict[str, Any]] - ALWAYS this format

        Raises:
            DatabaseError: On execution failure or normalization failure
        """
        try:
            # Clean the query - remove backticks if they cause issues for some DBs
            cleaned_query = query.replace("`", "")

            logger.info(
                f"Executing query: {cleaned_query[:DisplayLimits.QUESTION_PREVIEW]}{'...' if len(cleaned_query) > DisplayLimits.QUESTION_PREVIEW else ''}"
            )

            # Execute using db.run (raises on error, no fallback needed)
            raw_result = self.db.run(cleaned_query)

            # Normalize to standard format
            normalized_result = self._normalize_result(raw_result)

            # Apply result limit from configuration
            max_results = self.config.database.max_results
            if len(normalized_result) > max_results:
                logger.warning(
                    f"Query returned {len(normalized_result)} results, limiting to {max_results}"
                )
                normalized_result = normalized_result[:max_results]

            logger.info(
                f"Query executed successfully, returned {len(normalized_result)} results"
            )
            return normalized_result

        except DatabaseError:
            # Re-raise our own errors
            raise
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            raise DatabaseError(f"Error executing query: {str(e)}")

    def _discover_table_names(self) -> List[str]:
        """Return table names from SQLAlchemy metadata or by parsing the cached schema."""
        if hasattr(self.db, "_metadata") and self.db._metadata:
            return list(self.db._metadata.tables.keys())
        if self.schema:
            import re
            table_pattern = r'CREATE TABLE\s+([`"]?[\w.]+[`"]?)'
            matches = re.findall(table_pattern, self.schema, re.IGNORECASE)
            return [match.strip('`"') for match in matches]
        return []

    def _build_sample_query(self, clean_table_name: str, limit: int) -> str:
        """Build a SELECT * LIMIT query using the correct dialect for the current database."""
        conn_str = self.config.database.connection_string
        if conn_str.startswith(_BIGQUERY_SCHEME):
            return f"SELECT * FROM `{clean_table_name}` LIMIT {limit}"
        if conn_str.startswith("snowflake://"):
            return f'SELECT * FROM "{clean_table_name}" LIMIT {limit}'
        return f"SELECT * FROM {clean_table_name} LIMIT {limit}"

    def _sample_single_table(
        self, table_name: str, limit: int
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Sample one table and return {clean_name: rows}, or {} on error."""
        try:
            clean_table_name = table_name.strip('`"')
            query = self._build_sample_query(clean_table_name, limit)
            logger.debug(f"Sampling table {clean_table_name}")
            sample_rows = self.execute_query(query)
            if sample_rows:
                logger.debug(f"Collected {len(sample_rows)} sample rows from {clean_table_name}")
                return {clean_table_name: sample_rows}
            return {}
        except Exception as e:
            logger.debug(f"Failed to sample table {table_name}: {e}")
            return {}

    def get_sample_data(self, limit: int = 100) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch sample data from database tables for PII validation.

        Args:
            limit: Maximum number of rows to sample per table

        Returns:
            Dictionary mapping table names to lists of sample row dictionaries
        """
        try:
            logger.debug(f"Fetching sample data (max {limit} rows per table)")

            table_names = self._discover_table_names()
            if not table_names:
                logger.warning("No tables found for sample data collection")
                return {}

            max_tables_to_sample = 10
            sample_data: Dict[str, List[Dict[str, Any]]] = {}
            for table_name in table_names[:max_tables_to_sample]:
                sample_data.update(self._sample_single_table(table_name, limit))

            logger.info(f"Collected sample data from {len(sample_data)} tables")
            return sample_data

        except Exception as e:
            logger.error(f"Failed to collect sample data: {e}")
            return {}

    def test_connection(self) -> bool:
        """
        Test the database connection.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            db_type = self.config.get_database_type()
            logger.debug(f"Running {db_type} connection test...")

            # Use strategy pattern for database-specific connection testing
            return self.db_strategy.test_connection(self.db, self.config)

        except Exception as e:
            logger.error(f"❌ Database connection test failed: {e}")

            # Provide specific error diagnostics
            error_msg = str(e).lower()
            if "authentication" in error_msg or _ACCESS_DENIED_MSG in error_msg:
                logger.error("💡 Authentication issue - check your credentials")
            elif "connection refused" in error_msg:
                logger.error("💡 Connection refused - check host and port")
            elif "timeout" in error_msg:
                logger.error("💡 Connection timeout - check network connectivity")

            return False

    @staticmethod
    def _bq_check_dataset_exists(client, dataset_id: str, project_id: str) -> bool:
        """Return True if the BigQuery dataset exists and is accessible."""
        try:
            dataset_ref = client.dataset(dataset_id)
            dataset = client.get_dataset(dataset_ref)
            if dataset:
                logger.info(f"Dataset '{dataset_id}' exists and is accessible")
                return True
            logger.error(f"Dataset '{dataset_id}' not found")
            return False
        except Exception as dataset_error:
            logger.error(f"Dataset existence check failed: {dataset_error}")
            error_msg = str(dataset_error).lower()
            if "404" in error_msg or "not found" in error_msg:
                logger.error(f"Dataset '{dataset_id}' not found in project '{project_id}' - verify dataset name")
            elif "403" in error_msg or _ACCESS_DENIED_MSG in error_msg:
                logger.error("Access denied to dataset - grant 'BigQuery Data Viewer' role to your service account")
            elif "authentication" in error_msg:
                logger.error("Authentication failed - check your service account credentials")
            elif "permission" in error_msg:
                logger.error("Insufficient BigQuery permissions - check IAM roles")
            return False

    def _bq_test_query_execution(self) -> bool:
        """Return True if a simple SELECT 1 query executes without error."""
        logger.info("Step 2: Testing query execution permissions...")
        test_result = self.db.run_no_throw("SELECT 1 as test")
        if isinstance(test_result, str) and (
            "error" in test_result.lower() or "exception" in test_result.lower()
        ):
            logger.error(f"Query execution test failed: {test_result}")
            if "bigquery.jobs.create" in test_result:
                logger.error("Missing bigquery.jobs.create permission - grant 'BigQuery Job User' role")
            return False
        logger.info("Query execution test passed")
        return True

    @staticmethod
    def _bq_test_table_listing(client, dataset_id: str) -> bool:
        """Return True if tables can be listed in the given dataset."""
        logger.info("Step 3: Testing table listing permissions...")
        try:
            dataset_ref = client.dataset(dataset_id)
            tables = list(client.list_tables(dataset_ref))
            logger.info(f"Found {len(tables)} tables in dataset")
            return True
        except Exception as table_error:
            logger.error(f"Table listing test failed: {table_error}")
            error_msg = str(table_error).lower()
            if "403" in error_msg or _ACCESS_DENIED_MSG in error_msg:
                logger.error("Access denied to list tables - grant 'BigQuery Data Viewer' role to your service account")
            elif "permission" in error_msg:
                logger.error("Insufficient permissions to list tables - check IAM roles")
            return False

    @staticmethod
    def _bq_log_success(is_cross_project_enabled: bool, project_id: str, dataset_id: str) -> None:
        """Log BigQuery connection success with appropriate context."""
        if is_cross_project_enabled:
            logger.info("BigQuery connection validated for cross-project access")
            logger.info("You can query tables across projects using fully qualified names like:")
            logger.info("   `other-project.dataset_name.table_name`")
        else:
            logger.info(f"BigQuery connection fully validated for project '{project_id}'")
            if dataset_id and dataset_id != "CROSS_PROJECT_ACCESS":
                logger.info(f"Dataset '{dataset_id}' is accessible with full permissions")

    @staticmethod
    def _bq_log_outer_error(error_msg: str) -> None:
        """Log a top-level BigQuery diagnostic hint."""
        if "authentication" in error_msg or _ACCESS_DENIED_MSG in error_msg:
            logger.error("BigQuery authentication issue - check your service account credentials")
        elif "project" in error_msg:
            logger.error("BigQuery project issue - verify project ID and permissions")
        elif "bigquery.jobs.create" in error_msg:
            logger.error("Missing bigquery.jobs.create permission - grant 'BigQuery Job User' role")

    def _test_bigquery_connection(self) -> bool:
        """
        Test BigQuery connection with comprehensive validation.
        Supports both specific dataset validation and cross-project access scenarios.

        Returns:
            True if connection and query permissions are accessible, False otherwise
        """
        try:
            connection_string = self.config.database.connection_string
            parts = connection_string.replace(_BIGQUERY_SCHEME, "").split("/")

            if len(parts) < 1:
                logger.error(f"Invalid BigQuery connection string format. Expected at least: {_BIGQUERY_SCHEME}project_id")
                return False

            project_id = parts[0]
            dataset_id = parts[1] if len(parts) > 1 else "CROSS_PROJECT_ACCESS"

            logger.info(f"Testing BigQuery connection to project '{project_id}'...")
            client = bigquery.Client(project=project_id)

            cross_project_config = getattr(self.config.database, "cross_project_access", None)
            is_cross_project_enabled = cross_project_config and getattr(cross_project_config, "enabled", False)

            needs_dataset_check = dataset_id and dataset_id != "CROSS_PROJECT_ACCESS" and not is_cross_project_enabled

            # Step 1: Test dataset existence
            if needs_dataset_check:
                logger.info("Step 1: Testing dataset existence...")
                if not self._bq_check_dataset_exists(client, dataset_id, project_id):
                    return False
            elif is_cross_project_enabled:
                logger.info("Cross-project access enabled - skipping specific dataset existence check")
            else:
                logger.info("No specific dataset in connection string - skipping dataset existence check")

            # Step 2: Test query execution
            if not self._bq_test_query_execution():
                return False

            # Step 3: Test table listing
            if needs_dataset_check:
                if not self._bq_test_table_listing(client, dataset_id):
                    return False
            else:
                logger.info("Step 3: Skipped table listing test (cross-project access mode)")

            self._bq_log_success(is_cross_project_enabled, project_id, dataset_id)
            return True

        except Exception as e:
            logger.error(f"BigQuery connection test failed: {e}")
            self._bq_log_outer_error(str(e).lower())
            return False

    def get_table_names(self) -> List[str]:
        """
        Get list of table names in the database.

        Returns:
            List of table names
        """
        try:
            toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm_manager.llm)
            tools = toolkit.get_tools()
            list_tables_tool = next(
                tool for tool in tools if tool.name == "sql_db_list_tables"
            )

            table_names = list_tables_tool.invoke("")
            logger.info(
                f"Found {len(table_names.split(',')) if table_names else 0} tables in database"
            )
            return table_names.split(",") if table_names else []

        except Exception as e:
            logger.error(f"Error getting table names: {e}")
            return []

    def _get_safe_connection_info(self, connection_string: str) -> str:
        """Return a sanitized connection info string for logs (legacy API for tests)."""
        try:
            if connection_string and connection_string.lower().startswith(
                _BIGQUERY_SCHEME
            ):
                return connection_string.replace(_BIGQUERY_SCHEME, "BigQuery: ")
            if connection_string and "@" in connection_string:
                return connection_string.split("@")[-1]
            return "configured database"
        except Exception:
            return "configured database"

    def get_connection_info(self) -> dict:
        """
        Get information about the current database connection.

        Returns:
            Dictionary with connection information
        """
        connection_string = self.config.database.connection_string

        # Parse connection string to extract components (safely)
        info = {
            "connection_string": connection_string,
            "database_type": self.config.get_database_type(),
            "cache_enabled": self.config.database.cache_schema,
            "query_timeout": self.config.database.query_timeout,
            "max_results": self.config.database.max_results,
        }

        # Extract host/database info if possible
        try:
            if "@" in connection_string:
                # Format: driver://user:pass@host:port/db
                parts = connection_string.split("@")[1].split("/")
                if len(parts) >= 2:
                    host_port = parts[0]
                    database_name = parts[1]

                    if ":" in host_port:
                        host, port = host_port.split(":")
                        info["host"] = host
                        info["port"] = port
                    else:
                        info["host"] = host_port

                    info["database_name"] = database_name
        except Exception:
            # If parsing fails, just use what we have
            pass

        return info
