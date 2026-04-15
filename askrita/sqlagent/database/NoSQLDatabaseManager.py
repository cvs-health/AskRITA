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
#   langchain-mongodb (MIT)

"""
NoSQL Database Manager for AskRITA.

Provides MongoDB connection management, schema retrieval, and query execution
using langchain-mongodb — the official LangChain MongoDB integration.

This mirrors the architecture of DatabaseManager (which uses langchain's
SQLDatabase + SQLDatabaseToolkit) so that NoSQLAgentWorkflow can use it
as a drop-in replacement.
"""

import ast
import json
import logging
import re
from typing import Any, Dict, List, Optional

from ...config_manager import get_config
from ...exceptions import DatabaseError
from ...utils.constants import DisplayLimits
from .nosql_strategies import MongoDBStrategy, NoSQLConnectionStrategy

logger = logging.getLogger(__name__)


class NoSQLDatabaseManager:
    """
    Database manager for NoSQL databases (currently MongoDB).

    Uses langchain-mongodb's MongoDBDatabase wrapper — the same pattern
    that DatabaseManager uses with langchain's SQLDatabase. This gives us:
      - get_usable_collection_names() → like sql_db_list_tables
      - get_collection_info()         → like sql_db_schema
      - db.run(command)               → like db.run(sql_query)
      - db.run_no_throw(command)      → safe execution with error strings
    """

    def __init__(
        self,
        config_manager: Any = None,
        test_db_connection: bool = True,
    ):
        """
        Initialize NoSQLDatabaseManager with configuration.

        Args:
            config_manager: Optional ConfigManager instance. If None, uses global config.
            test_db_connection: Whether to test connection during initialization.
        """
        self.config = config_manager or get_config()
        self.db = None  # langchain_mongodb MongoDBDatabase instance
        self._client = None  # underlying pymongo MongoClient
        self.schema: Optional[str] = None

        # Determine strategy based on connection string
        self.db_strategy = self._create_strategy()
        logger.info(f"Using {self.db_strategy.__class__.__name__} for NoSQL operations")

        # Initialize database connection
        self._initialize_database()

        # Validate connection
        if test_db_connection:
            db_type = self.db_strategy.get_connection_type()
            logger.info(
                f"🔍 Testing {db_type} database connection during initialization..."
            )
            if not self.test_connection():
                logger.error(
                    f"❌ {db_type} database initialization failed - connection test failed"
                )
                raise DatabaseError(
                    "NoSQL database connection test failed after initialization. "
                    "Please verify your connection string, credentials, and database availability."
                )
            logger.info(f"✅ {db_type} database initialization completed successfully")
        else:
            logger.info(
                "⚠️ Database connection test skipped (test_db_connection=False)"
            )

    def _create_strategy(self) -> NoSQLConnectionStrategy:
        """Create the appropriate NoSQL strategy based on connection string."""
        connection_string = self.config.database.connection_string

        if not connection_string or not isinstance(connection_string, str):
            raise DatabaseError("Connection string must be a non-empty string")

        conn_lower = connection_string.lower()
        if conn_lower.startswith("mongodb://") or conn_lower.startswith(
            "mongodb+srv://"
        ):
            return MongoDBStrategy()

        raise DatabaseError(
            f"Unsupported NoSQL connection string: {connection_string}. "
            "Supported prefixes: mongodb://, mongodb+srv://"
        )

    def _initialize_database(self) -> None:
        """
        Initialize the NoSQL database connection using langchain-mongodb.

        Uses MongoDBDatabase.from_connection_string() — the same pattern
        as SQLDatabase.from_uri() in the SQL DatabaseManager.
        """
        try:
            from langchain_mongodb.agent_toolkit import MongoDBDatabase

            connection_string = self.config.database.connection_string
            safe_info = self.db_strategy.get_safe_connection_info(connection_string)
            logger.info(f"Connecting to NoSQL database: {safe_info}")

            # Setup authentication (strategy-specific)
            self.db_strategy.setup_auth(self.config)

            # Extract database name from connection string
            db_name = self.db_strategy._extract_database_name(self.config)

            # Create MongoDBDatabase using langchain-mongodb
            # This mirrors: self.db = SQLDatabase.from_uri(connection_string)
            self.db = MongoDBDatabase.from_connection_string(
                connection_string=connection_string,
                database=db_name,
            )

            # Keep a reference to the underlying client for strategy operations
            self._client = self.db._client

            logger.info(
                f"NoSQL database connection established to '{db_name}' via langchain-mongodb"
            )

        except ImportError:
            raise DatabaseError(
                "langchain-mongodb is required for MongoDB support. "
                "Install it with: pip install langchain-mongodb"
            )
        except Exception as e:
            logger.error(f"Failed to initialize NoSQL database connection: {e}")
            error_msg = str(e).lower()
            if "authentication" in error_msg or "auth" in error_msg:
                raise DatabaseError(
                    f"MongoDB authentication failed: {e}\n"
                    "Please check your username, password, and authSource."
                )
            elif "connection refused" in error_msg or "could not connect" in error_msg:
                raise DatabaseError(
                    f"Cannot connect to MongoDB: {e}\n"
                    "Please check that the MongoDB server is running and accessible."
                )
            elif "timeout" in error_msg:
                raise DatabaseError(
                    f"MongoDB connection timeout: {e}\n"
                    "The server is not responding. Check network connectivity."
                )
            raise DatabaseError(f"NoSQL database connection failed: {e}")

    def test_connection(self) -> bool:
        """Test the database connection."""
        try:
            return self.db_strategy.test_connection(self._client, self.config)
        except Exception as e:
            logger.error(f"❌ NoSQL database connection test failed: {e}")
            return False

    def get_schema(self) -> str:
        """
        Retrieve the database schema using langchain-mongodb's get_collection_info().

        This mirrors DatabaseManager.get_schema() which uses SQLDatabaseToolkit's
        sql_db_schema tool. The langchain-mongodb equivalent provides collection
        names, field types, sample documents, and indexes.

        Returns:
            Schema description string suitable for LLM consumption
        """
        # Check cache
        if self.config.database.cache_schema:
            cached = self.config.get_schema_cache()
            if cached:
                logger.debug("Using cached NoSQL database schema")
                return cached

        try:
            logger.info("Fetching NoSQL database schema via langchain-mongodb")

            # Get collection names (like sql_db_list_tables)
            collection_names = list(self.db.get_usable_collection_names())
            logger.info(f"Found {len(collection_names)} collections")

            # Get collection info (like sql_db_schema)
            schema = self.db.get_collection_info(collection_names)

            # Enhance schema with strategy-specific information
            schema = self.db_strategy.enhance_schema(schema, self.config)

            # Cache if enabled
            if self.config.database.cache_schema:
                self.config.set_schema_cache(schema)
                logger.info("NoSQL database schema cached successfully")

            self.schema = schema
            return schema

        except Exception as e:
            logger.error(f"Error fetching schema: {e}")
            raise DatabaseError(f"Error fetching schema: {e}")

    # Compiled patterns for MongoDB JS-to-Python key conversion
    _MONGO_KEY_PATTERN = re.compile(r'(?<!["\w])(\$?\w+)\s*:')
    _MONGO_JS_LITERAL_PATTERN = re.compile(r"\btrue\b|\bfalse\b|\bnull\b")
    _MONGO_JS_TO_PYTHON = {"true": "True", "false": "False", "null": "None"}

    @staticmethod
    def _toggle_quote_state(
        ch: str, prev: str, in_single: bool, in_double: bool
    ) -> tuple:
        """Return updated (in_single, in_double) state after processing character."""
        if ch == '"' and not in_single and prev != "\\":
            return in_single, not in_double
        if ch == "'" and not in_double and prev != "\\":
            return not in_single, in_double
        return in_single, in_double

    @staticmethod
    def _tokenize_quoted_segments(text: str) -> list:
        """Split text into (type, content) tuples, respecting quoted strings."""
        segments: list = []
        in_single = False
        in_double = False
        current: list = []

        for i, ch in enumerate(text):
            prev = text[i - 1] if i > 0 else ""
            in_single, in_double = NoSQLDatabaseManager._toggle_quote_state(
                ch, prev, in_single, in_double
            )
            if not in_single and not in_double:
                current.append(ch)
            else:
                if current:
                    segments.append(("unquoted", "".join(current)))
                    current = []
                segments.append(("quoted", ch))

        if current:
            segments.append(("unquoted", "".join(current)))
        return segments

    @staticmethod
    def _fix_unquoted_mongo_segment(text: str) -> str:
        """Quote bare MongoDB keys and convert JS boolean/null literals to Python."""

        def key_replacer(m: re.Match) -> str:
            key = m.group(1)
            if key in ("True", "False", "None", "true", "false", "null"):
                return m.group(0)
            return f'"{key}":'

        text = NoSQLDatabaseManager._MONGO_KEY_PATTERN.sub(key_replacer, text)
        text = NoSQLDatabaseManager._MONGO_JS_LITERAL_PATTERN.sub(
            lambda m: NoSQLDatabaseManager._MONGO_JS_TO_PYTHON[m.group(0)], text
        )
        return text

    @staticmethod
    def _fix_mongo_js_keys(command: str) -> str:
        """
        Convert JavaScript-style MongoDB syntax to valid Python/JSON syntax.

        langchain-mongodb's _parse_command uses eval() to parse the aggregation
        pipeline, but it does NOT quote bare $-prefixed keys or unquoted regular
        keys. LLMs frequently generate JS-style syntax like:
            {$count: 'total'}  or  {$group: {_id: "$field"}}

        This method converts those to valid Python dict syntax:
            {"$count": "total"}  or  {"$group": {"_id": "$field"}}

        Args:
            command: Raw MongoDB command string

        Returns:
            Command with properly quoted keys for Python eval()
        """
        # Only process the pipeline portion inside .aggregate(...)
        agg_match = re.search(r"\.aggregate\(", command)
        if not agg_match:
            return command

        prefix = command[: agg_match.end()]
        rest = command[agg_match.end() :]

        segments = NoSQLDatabaseManager._tokenize_quoted_segments(rest)
        result_parts = [
            (
                NoSQLDatabaseManager._fix_unquoted_mongo_segment(seg_text)
                if seg_type == "unquoted"
                else seg_text
            )
            for seg_type, seg_text in segments
        ]
        return prefix + "".join(result_parts)

    def execute_query(self, command: str) -> List[Dict[str, Any]]:
        """
        Execute a MongoDB command and return the results.

        Uses MongoDBDatabase.run() which expects commands in the form:
            db.collectionName.aggregate([...])

        This mirrors DatabaseManager.execute_query() which uses db.run(sql_query).

        Args:
            command: MongoDB command string (e.g. db.orders.aggregate([...]))

        Returns:
            Query results as List[Dict[str, Any]]

        Raises:
            DatabaseError: On execution failure
        """
        try:
            # Clean the command — strip markdown code fences if LLM wrapped it
            cleaned = command.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [line for line in lines if not line.strip().startswith("```")]
                cleaned = "\n".join(lines).strip()

            # Fix JavaScript-style unquoted keys for Python eval() compatibility
            cleaned = self._fix_mongo_js_keys(cleaned)

            logger.info(
                f"Executing MongoDB command: "
                f"{cleaned[:DisplayLimits.QUESTION_PREVIEW]}"
                f"{'...' if len(cleaned) > DisplayLimits.QUESTION_PREVIEW else ''}"
            )

            # Execute using langchain-mongodb's run() method
            # This mirrors: raw_result = self.db.run(sql_query)
            raw_result = self.db.run(cleaned)

            # Normalize to standard format
            normalized = self._normalize_result(raw_result)

            # Apply result limit from configuration
            max_results = self.config.database.max_results
            if len(normalized) > max_results:
                logger.warning(
                    f"Query returned {len(normalized)} results, limiting to {max_results}"
                )
                normalized = normalized[:max_results]

            logger.info(
                f"Query executed successfully, returned {len(normalized)} results"
            )
            return normalized

        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Error executing MongoDB command: {e}")
            raise DatabaseError(f"Error executing query: {e}")

    def _normalize_list_result(self, raw_result: list) -> List[Dict[str, Any]]:
        """Normalize a list result from MongoDB."""
        if isinstance(raw_result[0], dict):
            return [self._serialize_document(doc) for doc in raw_result]
        return [
            {"col_" + str(i): val for i, val in enumerate(row)} for row in raw_result
        ]

    def _normalize_string_result(self, raw_result: str) -> List[Dict[str, Any]]:
        """Normalize a string result from MongoDB, attempting to parse it."""
        if raw_result.startswith("Error:"):
            raise DatabaseError(raw_result)
        try:
            parsed = ast.literal_eval(raw_result)
            return self._normalize_result(parsed)
        except (ValueError, SyntaxError):
            pass
        try:
            parsed = json.loads(raw_result)
            return self._normalize_result(parsed)
        except json.JSONDecodeError:
            return [{"result": raw_result}]

    def _normalize_result(self, raw_result: Any) -> List[Dict[str, Any]]:
        """
        Normalize MongoDB results to always return List[Dict[str, Any]].

        Handles the various return types from MongoDBDatabase.run():
        string representations, cursors, lists, etc.

        Args:
            raw_result: Raw result from MongoDBDatabase.run()

        Returns:
            Normalized result as List[Dict[str, Any]]
        """
        if not raw_result:
            return []
        if isinstance(raw_result, list):
            return self._normalize_list_result(raw_result)
        if isinstance(raw_result, dict):
            return [self._serialize_document(raw_result)]
        if isinstance(raw_result, str):
            return self._normalize_string_result(raw_result)
        if hasattr(raw_result, "__iter__"):
            try:
                return self._normalize_result(list(raw_result))
            except Exception:
                return [{"result": str(raw_result)}]
        return [{"result": str(raw_result)}]

    def _serialize_document(self, doc: dict) -> Dict[str, Any]:
        """
        Serialize a MongoDB document for JSON compatibility.

        Converts ObjectId, datetime, Decimal128, etc. to strings.
        """
        result = {}
        for key, value in doc.items():
            if key == "_id":
                result[key] = str(value)
            elif isinstance(value, dict):
                result[key] = self._serialize_document(value)
            elif isinstance(value, list):
                result[key] = [
                    (
                        self._serialize_document(v)
                        if isinstance(v, dict)
                        else self._serialize_value(v)
                    )
                    for v in value
                ]
            else:
                result[key] = self._serialize_value(value)
        return result

    def _serialize_value(self, value: Any) -> Any:
        """Serialize a single value for JSON compatibility."""
        if value is None:
            return None
        type_name = type(value).__name__
        if type_name == "ObjectId":
            return str(value)
        if type_name == "Decimal128":
            return float(str(value))
        if type_name == "datetime":
            return value.isoformat()
        if type_name in ("bytes", "Binary"):
            return "<binary data>"
        return value

    def get_collection_names(self) -> List[str]:
        """
        Get list of collection names in the database.

        Returns:
            List of collection names
        """
        try:
            names = list(self.db.get_usable_collection_names())
            logger.info(f"Found {len(names)} collections in database")
            return sorted(names)
        except Exception as e:
            logger.error(f"Error getting collection names: {e}")
            return []

    def get_sample_data(self, limit: int = 100) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch sample data from collections for PII validation.

        Args:
            limit: Maximum number of documents to sample per collection

        Returns:
            Dictionary mapping collection names to sample document lists
        """
        try:
            sample_data = {}
            max_collections = 10

            for coll_name in self.get_collection_names()[:max_collections]:
                try:
                    command = f'db.{coll_name}.aggregate([{{"$limit": {limit}}}])'
                    result = self.db.run_no_throw(command)
                    if result and not (
                        isinstance(result, str) and result.startswith("Error")
                    ):
                        normalized = self._normalize_result(result)
                        if normalized:
                            sample_data[coll_name] = normalized
                except Exception as e:
                    logger.debug(f"Failed to sample collection {coll_name}: {e}")
                    continue

            logger.info(f"Collected sample data from {len(sample_data)} collections")
            return sample_data

        except Exception as e:
            logger.error(f"Failed to collect sample data: {e}")
            return {}

    def get_connection_info(self) -> dict:
        """Get information about the current database connection."""
        connection_string = self.config.database.connection_string
        return {
            "connection_string": connection_string,
            "database_type": self.config.get_database_type(),
            "cache_enabled": self.config.database.cache_schema,
            "query_timeout": self.config.database.query_timeout,
            "max_results": self.config.database.max_results,
        }
