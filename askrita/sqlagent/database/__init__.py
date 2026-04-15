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
Database management module for AskRITA SQLAgent.

This module contains all database-related components using design patterns:
- DatabaseManager: Main SQL database connection and operation manager
- NoSQLDatabaseManager: NoSQL (MongoDB) database connection and operation manager
- Strategy Pattern: Database-specific connection strategies (BigQuery, Snowflake, PostgreSQL, DB2, MongoDB)
- Chain of Responsibility: Modular validation steps
- Decorator Pattern: Composable schema enhancements
- Factory Pattern: Automatic strategy creation

Classes:
    DatabaseManager: Main SQL database management class
    NoSQLDatabaseManager: NoSQL database management class (MongoDB)
    DatabaseStrategyFactory: Factory for creating database strategies
    DatabaseConnectionStrategy: Abstract base for SQL database strategies
    NoSQLConnectionStrategy: Abstract base for NoSQL database strategies
    BigQueryStrategy, SnowflakeStrategy, PostgreSQLStrategy, DB2Strategy: SQL strategies
    MongoDBStrategy: NoSQL strategy for MongoDB
    ValidationStep: Abstract base for validation steps
    SchemaDecorator: Abstract base for schema decorators
"""

from .database_factory import DatabaseStrategyFactory
from .database_strategies import (
    BigQueryStrategy,
    DatabaseConnectionStrategy,
    DB2Strategy,
    PostgreSQLStrategy,
    SnowflakeStrategy,
)
from .DatabaseManager import DatabaseManager
from .nosql_strategies import (
    MongoDBStrategy,
    NoSQLConnectionStrategy,
)
from .NoSQLDatabaseManager import NoSQLDatabaseManager
from .schema_decorators import (
    BaseSchemaProvider,
    CrossProjectSchemaDecorator,
    SchemaDecorator,
    SchemaDecoratorBuilder,
    SchemaFormattingDecorator,
    SchemaMetadataDecorator,
    SchemaProvider,
)
from .validation_chain import (
    BigQueryValidationChain,
    DatasetExistenceValidationStep,
    QueryExecutionValidationStep,
    TableListingValidationStep,
    ValidationContext,
    ValidationStep,
)

__all__ = [
    # SQL database management
    "DatabaseManager",
    "DatabaseStrategyFactory",
    "DatabaseConnectionStrategy",
    "BigQueryStrategy",
    "SnowflakeStrategy",
    "PostgreSQLStrategy",
    "DB2Strategy",
    # NoSQL database management
    "NoSQLDatabaseManager",
    "NoSQLConnectionStrategy",
    "MongoDBStrategy",
    # Validation
    "ValidationStep",
    "ValidationContext",
    "BigQueryValidationChain",
    "DatasetExistenceValidationStep",
    "QueryExecutionValidationStep",
    "TableListingValidationStep",
    # Schema decorators
    "SchemaProvider",
    "SchemaDecorator",
    "BaseSchemaProvider",
    "CrossProjectSchemaDecorator",
    "SchemaMetadataDecorator",
    "SchemaFormattingDecorator",
    "SchemaDecoratorBuilder",
]
