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
#   google-auth (Apache-2.0)

"""
Database connection strategy pattern implementation.

This module provides database-specific strategies for handling different database types
with their unique connection, authentication, and validation requirements.
"""

import logging
import os
from abc import ABC, abstractmethod

from google.auth import default

from ...exceptions import DatabaseError
from .schema_decorators import SchemaDecoratorBuilder
from .validation_chain import BigQueryValidationChain

logger = logging.getLogger(__name__)


class DatabaseConnectionStrategy(ABC):
    """
    Abstract base class for database-specific connection strategies.

    Each database type (BigQuery, Snowflake, PostgreSQL, etc.) implements
    this interface to provide database-specific functionality.
    """

    @abstractmethod
    def setup_auth(self, config) -> None:
        """
        Setup database-specific authentication.

        Args:
            config: Database configuration object
        """
        pass

    @abstractmethod
    def test_connection(self, db, config) -> bool:
        """
        Test the database connection with database-specific validation.

        Args:
            db: Database connection object
            config: Database configuration object

        Returns:
            True if connection is successful, False otherwise
        """
        pass

    @abstractmethod
    def enhance_schema(self, schema: str, config) -> str:
        """
        Enhance schema with database-specific information.

        Args:
            schema: Base schema string
            config: Database configuration object

        Returns:
            Enhanced schema string
        """
        pass

    @abstractmethod
    def get_connection_type(self) -> str:
        """
        Get the connection type identifier for this strategy.

        Returns:
            Connection type string (e.g., 'bigquery', 'snowflake', 'postgresql')
        """
        pass

    def get_safe_connection_info(self, connection_string: str) -> str:
        """
        Get safe connection info for logging (hide credentials).
        Default implementation, can be overridden by specific strategies.

        Args:
            connection_string: Database connection string

        Returns:
            Safe connection string for logging
        """
        if "@" in connection_string:
            return connection_string.split("@")[-1]
        else:
            return f"{self.get_connection_type().title()}: {connection_string.split('://')[1] if '://' in connection_string else 'configured database'}"


class BigQueryStrategy(DatabaseConnectionStrategy):
    """
    BigQuery-specific database connection strategy.

    Handles BigQuery authentication, connection testing with 3-step validation,
    and cross-project schema enhancement.
    """

    def get_connection_type(self) -> str:
        """Get BigQuery connection type identifier."""
        return "bigquery"

    def setup_auth(self, config) -> None:
        """Setup BigQuery authentication using configuration."""
        try:
            # Get authentication settings from config
            db_config = config.database

            # Check for explicit credentials path in config
            credentials_path = db_config.bigquery_credentials_path

            if credentials_path and os.path.exists(credentials_path):
                logger.info(
                    f"Using service account credentials from config: {credentials_path}"
                )
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
            elif credentials_path:
                logger.warning(
                    f"Configured credentials path does not exist: {credentials_path}"
                )
                logger.info("Falling back to Application Default Credentials (ADC)")

            # Test authentication by creating a client
            try:
                # This will use either the explicit credentials or ADC
                _, project_id = default()
                logger.info(
                    f"BigQuery authentication successful (Project: {project_id})"
                )
            except Exception as auth_e:
                logger.error(f"BigQuery authentication failed: {auth_e}")
                logger.error("To fix BigQuery authentication:")
                logger.error(
                    "   1. Set 'bigquery_credentials_path' in your config file"
                )
                logger.error("   2. Run: gcloud auth application-default login")
                logger.error("   3. Deploy to Google Cloud (ADC works automatically)")
                raise DatabaseError(f"BigQuery authentication failed: {auth_e}")

            logger.info("BigQuery authentication setup completed")

        except Exception as e:
            logger.error(f"Failed to setup BigQuery authentication: {e}")
            raise DatabaseError(f"BigQuery setup failed: {str(e)}")

    def test_connection(self, db, config) -> bool:
        """
        Test BigQuery connection with comprehensive 3-step validation using Chain of Responsibility pattern.
        Supports both specific dataset validation and cross-project access scenarios.

        Args:
            db: Database connection object
            config: Database configuration object

        Returns:
            True if connection and query permissions are accessible, False otherwise
        """
        try:
            # Use validation chain for comprehensive testing
            validation_chain = BigQueryValidationChain()
            return validation_chain.validate(db, config)

        except Exception as e:
            logger.error(f"❌ BigQuery connection test failed: {e}")

            # Provide specific BigQuery error diagnostics
            error_msg = str(e).lower()
            if "authentication" in error_msg or "access denied" in error_msg:
                logger.error(
                    "💡 BigQuery authentication issue - check your service account credentials"
                )
            elif "project" in error_msg:
                logger.error(
                    "💡 BigQuery project issue - verify project ID and permissions"
                )
            elif "bigquery.jobs.create" in error_msg:
                logger.error(
                    "💡 Missing bigquery.jobs.create permission - grant 'BigQuery Job User' role"
                )

            return False

    def enhance_schema(self, schema: str, config) -> str:
        """
        Enhance BigQuery schema using decorator pattern.
        Applies cross-project enhancement, metadata, and formatting decorators as needed.

        Args:
            schema: Current schema string from standard extraction
            config: Database configuration object

        Returns:
            Enhanced schema string with all applicable decorators applied
        """
        try:
            logger.info(
                "============== ENHANCING BIGQUERY SCHEMA (Decorator Pattern) =============="
            )
            logger.info("Original schema length: %s characters", len(schema))

            # Build decorator chain using fluent builder pattern
            decorator_builder = SchemaDecoratorBuilder(schema)

            # Add cross-project enhancement if enabled
            cross_project_config = getattr(
                config.database, "cross_project_access", None
            )
            if cross_project_config and getattr(cross_project_config, "enabled", False):
                logger.info("Adding cross-project enhancement decorator")
                decorator_builder.with_cross_project_enhancement()

            # Add hybrid descriptions decorator (automatic + manual)
            desc_config = config.get_schema_descriptions()
            if (
                desc_config.automatic_extraction.enabled
                or desc_config.columns
                or desc_config.project_context
            ):
                logger.info("Adding hybrid descriptions decorator (automatic + manual)")
                decorator_builder.with_hybrid_descriptions()

            # Add metadata decorator for documentation
            logger.info("Adding metadata decorator")
            decorator_builder.with_metadata()

            # Add formatting decorator for better readability
            logger.info("Adding formatting decorator")
            decorator_builder.with_formatting()

            # Build and apply the decorator chain
            schema_provider = decorator_builder.build()
            enhanced_schema = schema_provider.get_schema(config)

            logger.info(
                f"Schema enhancement complete. Final length: {len(enhanced_schema)} characters"
            )
            return enhanced_schema

        except Exception as e:
            logger.error(f"Error enhancing BigQuery schema with decorators: {e}")
            # Fall back to original schema on error
            return schema

    def get_safe_connection_info(self, connection_string: str) -> str:
        """Get safe BigQuery connection info for logging."""
        return connection_string.replace("bigquery://", "BigQuery: ")


class SnowflakeStrategy(DatabaseConnectionStrategy):
    """
    Snowflake-specific database connection strategy.
    Basic implementation that can be extended with Snowflake-specific features.
    """

    def get_connection_type(self) -> str:
        """Get Snowflake connection type identifier."""
        return "snowflake"

    def setup_auth(self, config) -> None:
        """Setup Snowflake authentication. Currently uses connection string auth."""
        logger.info("Using Snowflake connection string authentication")

    def test_connection(self, db, config) -> bool:
        """Test Snowflake connection with basic query."""
        try:
            logger.info("Testing Snowflake connection...")
            test_result = db.run_no_throw("SELECT 1 as test")

            if isinstance(test_result, str) and (
                "error" in test_result.lower() or "exception" in test_result.lower()
            ):
                logger.error(f"❌ Snowflake connection test failed: {test_result}")
                return False

            logger.info("✅ Snowflake connection test passed")
            return True

        except Exception as e:
            logger.error(f"❌ Snowflake connection test failed: {e}")
            return False

    def enhance_schema(self, schema: str, config) -> str:
        """No specific schema enhancement for Snowflake currently."""
        return schema

    def get_safe_connection_info(self, connection_string: str) -> str:
        """Get safe Snowflake connection info for logging."""
        return connection_string.replace("snowflake://", "Snowflake: ")


class PostgreSQLStrategy(DatabaseConnectionStrategy):
    """
    PostgreSQL-specific database connection strategy.
    Basic implementation that can be extended with PostgreSQL-specific features.
    """

    def get_connection_type(self) -> str:
        """Get PostgreSQL connection type identifier."""
        return "postgresql"

    def setup_auth(self, config) -> None:
        """Setup PostgreSQL authentication. Currently uses connection string auth."""
        logger.info("Using PostgreSQL connection string authentication")

    def test_connection(self, db, config) -> bool:
        """Test PostgreSQL connection with basic query."""
        try:
            logger.info("Testing PostgreSQL connection...")
            test_result = db.run_no_throw("SELECT 1 as test")

            if isinstance(test_result, str) and (
                "error" in test_result.lower() or "exception" in test_result.lower()
            ):
                logger.error(f"❌ PostgreSQL connection test failed: {test_result}")
                return False

            logger.info("✅ PostgreSQL connection test passed")
            return True

        except Exception as e:
            logger.error(f"❌ PostgreSQL connection test failed: {e}")
            return False

    def enhance_schema(self, schema: str, config) -> str:
        """No specific schema enhancement for PostgreSQL currently."""
        return schema


class DB2Strategy(DatabaseConnectionStrategy):
    """
    DB2-specific database connection strategy.
    Basic implementation that can be extended with DB2-specific features.
    """

    def get_connection_type(self) -> str:
        """Get DB2 connection type identifier."""
        return "db2"

    def setup_auth(self, config) -> None:
        """Setup DB2 authentication. Currently uses connection string auth."""
        logger.info("Using DB2 connection string authentication")

    def test_connection(self, db, config) -> bool:
        """Test DB2 connection with basic query."""
        try:
            logger.info("Testing DB2 connection...")
            # SYSIBM.SYSDUMMY1 is the standard DB2 dummy table (similar to Oracle's DUAL).
            test_result = db.run_no_throw("SELECT 1 FROM SYSIBM.SYSDUMMY1")

            if isinstance(test_result, str) and (
                "error" in test_result.lower() or "exception" in test_result.lower()
            ):
                logger.error(f"❌ DB2 connection test failed: {test_result}")
                return False

            logger.info("✅ DB2 connection test passed")
            return True

        except Exception as e:
            logger.error(f"❌ DB2 connection test failed: {e}")
            return False

    def enhance_schema(self, schema: str, config) -> str:
        """No specific schema enhancement for DB2 currently."""
        return schema

    def get_safe_connection_info(self, connection_string: str) -> str:
        """
        Get safe DB2 connection info for logging with masked credentials.

        Args:
            connection_string: Full DB2 connection string with credentials

        Returns:
            Safe connection string with credentials masked
        """
        try:
            # DB2 connection string format: db2://username:password@hostname:port/database
            # or ibm_db_sa://username:password@hostname:port/database

            # Remove protocol prefix
            if connection_string.startswith("db2://"):
                clean_string = connection_string.replace("db2://", "")
                prefix = "DB2: "
            elif connection_string.startswith("ibm_db_sa://"):
                clean_string = connection_string.replace("ibm_db_sa://", "")
                prefix = "DB2: "
            else:
                # Fallback for unknown format
                return "DB2: [connection configured]"

            # Extract everything after @ (hostname:port/database)
            if "@" in clean_string:
                # Split on @ to remove username:password
                safe_part = clean_string.split("@", 1)[1]
                return f"{prefix}{safe_part}"
            else:
                # No credentials in string (unusual but handle it)
                return f"{prefix}{clean_string}"

        except Exception:
            # If parsing fails, return generic safe message
            return "DB2: [connection configured]"
