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
NoSQL database connection strategy implementations.

This module provides NoSQL-specific strategies following the same pattern
as the SQL DatabaseConnectionStrategy, enabling the factory pattern to
support both SQL and NoSQL databases.

The schema inference is handled by langchain-mongodb's MongoDBDatabase
(via get_collection_info()), so strategies here focus on authentication,
connection testing, and optional schema enhancement.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

from ...exceptions import DatabaseError

logger = logging.getLogger(__name__)


class NoSQLConnectionStrategy(ABC):
    """
    Abstract base class for NoSQL database connection strategies.

    Mirrors the DatabaseConnectionStrategy interface but adapted for
    document/key-value stores that use langchain-mongodb instead of SQLAlchemy.
    """

    @abstractmethod
    def setup_auth(self, config: Any) -> None:
        """Setup database-specific authentication."""

    @abstractmethod
    def test_connection(self, client: Any, config: Any) -> bool:
        """Test the database connection and return success status."""

    @abstractmethod
    def get_connection_type(self) -> str:
        """Return connection type identifier (e.g. 'mongodb')."""

    def enhance_schema(self, schema: str, _config: Any) -> str:
        """
        Enhance schema with database-specific information.

        Override in subclasses to add custom schema enhancements.
        Default implementation returns schema unchanged.

        Args:
            schema: Base schema string from langchain-mongodb
            _config: Configuration object (unused in default implementation)

        Returns:
            Enhanced schema string
        """
        return schema

    def get_safe_connection_info(self, connection_string: str) -> str:
        """Get safe connection info for logging (hide credentials)."""
        if "@" in connection_string:
            return connection_string.split("@")[-1]
        if "://" in connection_string:
            return f"{self.get_connection_type().title()}: {connection_string.split('://')[1]}"
        return "configured database"


class MongoDBStrategy(NoSQLConnectionStrategy):
    """
    MongoDB-specific connection strategy.

    Handles MongoDB authentication, connection testing, and optional
    schema enhancement. Schema inference itself is delegated to
    langchain-mongodb's MongoDBDatabase.get_collection_info().
    """

    def get_connection_type(self) -> str:
        """Get MongoDB connection type identifier."""
        return "mongodb"

    def setup_auth(self, config: Any) -> None:
        """
        Setup MongoDB authentication.

        MongoDB authentication is handled via the connection string
        (mongodb://user:pass@host:port/db?authSource=admin) so no
        additional setup is needed beyond what pymongo handles.
        """
        logger.info("Using MongoDB connection string authentication")

    def test_connection(self, client: Any, config: Any) -> bool:
        """
        Test MongoDB connection by issuing a ping command.

        Args:
            client: pymongo.MongoClient instance
            config: Configuration object

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            logger.info("Testing MongoDB connection...")
            client.admin.command("ping")
            logger.info("✅ MongoDB connection test passed")
            return True
        except Exception as e:
            logger.error(f"❌ MongoDB connection test failed: {e}")
            return False

    def enhance_schema(self, schema: str, config: Any) -> str:
        """
        Enhance MongoDB schema with additional context.

        Adds database type header and any project context from configuration.

        Args:
            schema: Base schema from langchain-mongodb's get_collection_info()
            config: Configuration object

        Returns:
            Enhanced schema string
        """
        enhancements = []

        # Add database type context for the LLM
        enhancements.append("Database Type: MongoDB (NoSQL Document Store)")
        enhancements.append(
            "Query Language: MongoDB aggregation pipelines "
            "(use db.collectionName.aggregate([...]) syntax)"
        )
        enhancements.append("")

        # Add project context if configured
        desc_config = getattr(config, "get_schema_descriptions", None)
        if desc_config:
            try:
                descriptions = desc_config()
                if descriptions and descriptions.project_context:
                    enhancements.append(
                        f"Project Context: {descriptions.project_context}"
                    )
                    enhancements.append("")
            except Exception:
                pass

        if enhancements:
            return "\n".join(enhancements) + schema

        return schema

    def _extract_database_name(self, config: Any) -> str:
        """
        Extract the database name from the MongoDB connection string.

        Supports formats:
            mongodb://host:port/dbname
            mongodb+srv://user:pass@cluster/dbname?options
        """
        connection_string = config.database.connection_string
        try:
            # Remove query parameters
            base = connection_string.split("?")[0]
            # Extract path after host
            after_protocol = base.split("://", 1)[1]
            # Get everything after the last slash (database name)
            parts = after_protocol.split("/")
            if len(parts) >= 2 and parts[-1]:
                return parts[-1]
        except (IndexError, AttributeError):
            pass

        raise DatabaseError(
            "Could not extract database name from MongoDB connection string. "
            "Expected format: mongodb://host:port/database_name"
        )

    def get_safe_connection_info(self, connection_string: str) -> str:
        """Get safe MongoDB connection info for logging."""
        if "@" in connection_string:
            safe_part = connection_string.split("@")[-1]
            return f"MongoDB: {safe_part}"
        return connection_string.replace("mongodb://", "MongoDB: ").replace(
            "mongodb+srv://", "MongoDB Atlas: "
        )
