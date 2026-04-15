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
Database strategy factory for creating appropriate database connection strategies.

This module provides a factory pattern implementation to create the correct
database strategy based on the connection string type.
"""

import logging

from ...exceptions import DatabaseError
from .database_strategies import (
    BigQueryStrategy,
    DatabaseConnectionStrategy,
    DB2Strategy,
    PostgreSQLStrategy,
    SnowflakeStrategy,
)

logger = logging.getLogger(__name__)


class DatabaseStrategyFactory:
    """
    Factory class for creating appropriate database connection strategies.

    Uses the connection string to determine which database type is being used
    and returns the appropriate strategy implementation.
    """

    # Registry of supported database strategies
    _strategies = {
        "bigquery": BigQueryStrategy,
        "snowflake": SnowflakeStrategy,
        "postgresql": PostgreSQLStrategy,
        "postgres": PostgreSQLStrategy,  # Alias for postgresql
        "mysql": PostgreSQLStrategy,  # Can use basic strategy for now
        "sqlite": PostgreSQLStrategy,  # Can use basic strategy for now
        "db2": DB2Strategy,
        "ibm_db_sa": DB2Strategy,  # Alias for DB2 (SQLAlchemy driver)
    }

    @classmethod
    def create_strategy(cls, connection_string: str) -> DatabaseConnectionStrategy:
        """
        Create the appropriate database strategy based on connection string.

        Args:
            connection_string: Database connection string (e.g., 'bigquery://...', 'snowflake://...')

        Returns:
            DatabaseConnectionStrategy: Appropriate strategy instance

        Raises:
            DatabaseError: If connection string format is invalid or database type not supported
        """
        if not connection_string or not isinstance(connection_string, str):
            raise DatabaseError("Connection string must be a non-empty string")

        # Extract database type from connection string
        if "://" not in connection_string:
            raise DatabaseError(
                f"Invalid connection string format: {connection_string}"
            )

        db_type = connection_string.split("://")[0].lower()

        if db_type not in cls._strategies:
            logger.warning(
                f"Database type '{db_type}' not specifically supported, using PostgreSQL strategy as fallback"
            )
            db_type = "postgresql"  # Fallback to generic strategy

        strategy_class = cls._strategies[db_type]
        strategy_instance = strategy_class()

        logger.debug(
            f"Created {strategy_instance.__class__.__name__} for connection type '{db_type}'"
        )
        return strategy_instance

    @classmethod
    def get_supported_types(cls) -> list:
        """
        Get list of supported database types.

        Returns:
            List of supported database type strings
        """
        return list(cls._strategies.keys())

    @classmethod
    def is_nosql(cls, connection_string: str) -> bool:
        """
        Check if a connection string refers to a NoSQL database.

        Args:
            connection_string: Database connection string

        Returns:
            True if the connection string is for a NoSQL database
        """
        if not connection_string or not isinstance(connection_string, str):
            return False
        conn_lower = connection_string.lower()
        return conn_lower.startswith("mongodb://") or conn_lower.startswith(
            "mongodb+srv://"
        )

    @classmethod
    def register_strategy(cls, db_type: str, strategy_class: type) -> None:
        """
        Register a new database strategy.

        Args:
            db_type: Database type identifier (e.g., 'bigquery', 'snowflake')
            strategy_class: Strategy class that implements DatabaseConnectionStrategy
        """
        if not issubclass(strategy_class, DatabaseConnectionStrategy):
            raise ValueError(
                "Strategy class must inherit from DatabaseConnectionStrategy"
            )

        cls._strategies[db_type.lower()] = strategy_class
        logger.debug(f"Registered new strategy: {db_type} -> {strategy_class.__name__}")
