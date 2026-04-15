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
Validation chain implementation using Chain of Responsibility pattern.

This module provides a chain of validation steps for database connection testing,
allowing for flexible, configurable, and extensible validation processes.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from google.cloud import bigquery

logger = logging.getLogger(__name__)


@dataclass
class ValidationContext:
    """
    Context object passed through the validation chain.
    Contains all necessary information for validation steps.
    """

    db: Any  # Database connection object
    config: Any  # Configuration object
    connection_string: str
    project_id: str
    dataset_id: Optional[str] = None
    bigquery_client: Optional[bigquery.Client] = None
    is_cross_project_enabled: bool = False
    validation_results: Optional[Dict[str, bool]] = None
    error_messages: Optional[Dict[str, str]] = None

    def __post_init__(self):
        if self.validation_results is None:
            self.validation_results = {}
        if self.error_messages is None:
            self.error_messages = {}

    def add_result(self, step_name: str, success: bool, error_message: str = None):
        """Add validation result for a step."""
        self.validation_results[step_name] = success
        if error_message:
            self.error_messages[step_name] = error_message

    def is_successful(self) -> bool:
        """Check if all validation steps have been successful."""
        return (
            all(self.validation_results.values()) if self.validation_results else False
        )


class ValidationStep(ABC):
    """
    Abstract base class for validation steps in the chain.

    Each step can process the validation and optionally pass control to the next step.
    """

    def __init__(self):
        self._next_step: Optional["ValidationStep"] = None

    def set_next(self, step: "ValidationStep") -> "ValidationStep":
        """
        Set the next step in the chain.

        Args:
            step: The next validation step

        Returns:
            The next step (for method chaining)
        """
        self._next_step = step
        return step

    @abstractmethod
    def get_step_name(self) -> str:
        """Get the name of this validation step."""
        pass

    @abstractmethod
    def is_enabled(self, context: ValidationContext) -> bool:
        """
        Check if this validation step should be executed.

        Args:
            context: Validation context

        Returns:
            True if step should be executed, False to skip
        """
        pass

    @abstractmethod
    def validate(self, context: ValidationContext) -> bool:
        """
        Perform the validation for this step.

        Args:
            context: Validation context

        Returns:
            True if validation passed, False if failed
        """
        pass

    def handle(self, context: ValidationContext) -> bool:
        """
        Handle validation request and potentially pass to next step.

        Args:
            context: Validation context

        Returns:
            True if all enabled validations passed, False if any failed
        """
        success = True

        if self.is_enabled(context):
            logger.info(f"Executing {self.get_step_name()}...")
            step_success = self.validate(context)
            context.add_result(self.get_step_name(), step_success)

            if not step_success:
                success = False
                logger.error(f"❌ {self.get_step_name()} failed")
            else:
                logger.info(f"✅ {self.get_step_name()} passed")
        else:
            logger.info(
                f"Skipping {self.get_step_name()} (disabled for current configuration)"
            )
            context.add_result(
                self.get_step_name(), True
            )  # Mark as passed since it's disabled

        # Continue to next step if this one passed or is disabled
        if success and self._next_step:
            return self._next_step.handle(context)

        return success


class DatasetExistenceValidationStep(ValidationStep):
    """
    Validation step to check if BigQuery dataset exists and is accessible.
    Step 1 in the BigQuery validation chain.
    """

    def get_step_name(self) -> str:
        return "Step 1: Dataset Existence Check"

    def is_enabled(self, context: ValidationContext) -> bool:
        """
        Enable only when we have a specific dataset and cross-project is not enabled.
        """
        return (
            context.dataset_id
            and context.dataset_id != "CROSS_PROJECT_ACCESS"
            and not context.is_cross_project_enabled
        )

    def validate(self, context: ValidationContext) -> bool:
        """Validate that the dataset exists and is accessible."""
        try:
            if not context.bigquery_client:
                context.bigquery_client = bigquery.Client(project=context.project_id)

            # Try to get the dataset
            dataset_ref = context.bigquery_client.dataset(context.dataset_id)
            dataset = context.bigquery_client.get_dataset(dataset_ref)

            if dataset:
                logger.info(
                    f"✅ Dataset '{context.dataset_id}' exists and is accessible"
                )
                return True
            else:
                context.add_result(
                    self.get_step_name(),
                    False,
                    f"Dataset '{context.dataset_id}' not found",
                )
                return False

        except Exception as dataset_error:
            error_msg = str(dataset_error).lower()
            if "404" in error_msg or "not found" in error_msg:
                context.add_result(
                    self.get_step_name(),
                    False,
                    f"Dataset '{context.dataset_id}' not found in project '{context.project_id}' - verify dataset name",
                )
            elif "403" in error_msg or "access denied" in error_msg:
                context.add_result(
                    self.get_step_name(),
                    False,
                    "Access denied to dataset - grant 'BigQuery Data Viewer' role to your service account",
                )
            elif "authentication" in error_msg:
                context.add_result(
                    self.get_step_name(),
                    False,
                    "Authentication failed - check your service account credentials",
                )
            elif "permission" in error_msg:
                context.add_result(
                    self.get_step_name(),
                    False,
                    "Insufficient BigQuery permissions - check IAM roles",
                )
            else:
                context.add_result(
                    self.get_step_name(),
                    False,
                    f"Dataset existence check failed: {dataset_error}",
                )

            logger.error(f"❌ Dataset existence check failed: {dataset_error}")
            return False


class QueryExecutionValidationStep(ValidationStep):
    """
    Validation step to test query execution permissions.
    Step 2 in the BigQuery validation chain - always enabled.
    """

    def get_step_name(self) -> str:
        return "Step 2: Query Execution Test"

    def is_enabled(self, context: ValidationContext) -> bool:
        """Always enabled - this is essential for any BigQuery operations."""
        return True

    def validate(self, context: ValidationContext) -> bool:
        """Test query execution permissions with a simple SELECT query."""
        try:
            test_result = context.db.run_no_throw("SELECT 1 as test")

            # Check if the result indicates an error
            if isinstance(test_result, str) and (
                "error" in test_result.lower() or "exception" in test_result.lower()
            ):
                if "bigquery.jobs.create" in test_result:
                    context.add_result(
                        self.get_step_name(),
                        False,
                        "Missing bigquery.jobs.create permission - grant 'BigQuery Job User' role",
                    )
                else:
                    context.add_result(
                        self.get_step_name(),
                        False,
                        f"Query execution test failed: {test_result}",
                    )
                return False

            return True

        except Exception as e:
            context.add_result(
                self.get_step_name(), False, f"Query execution test failed: {e}"
            )
            logger.error(f"❌ Query execution test failed: {e}")
            return False


class TableListingValidationStep(ValidationStep):
    """
    Validation step to test table listing permissions.
    Step 3 in the BigQuery validation chain.
    """

    def get_step_name(self) -> str:
        return "Step 3: Table Listing Test"

    def is_enabled(self, context: ValidationContext) -> bool:
        """
        Enable only when we have a specific dataset and cross-project is not primary focus.
        """
        return (
            context.dataset_id
            and context.dataset_id != "CROSS_PROJECT_ACCESS"
            and not context.is_cross_project_enabled
        )

    def validate(self, context: ValidationContext) -> bool:
        """Test ability to list tables in the dataset."""
        try:
            if not context.bigquery_client:
                context.bigquery_client = bigquery.Client(project=context.project_id)

            dataset_ref = context.bigquery_client.dataset(context.dataset_id)
            tables = list(context.bigquery_client.list_tables(dataset_ref))
            logger.info(f"✅ Found {len(tables)} tables in dataset")
            return True

        except Exception as table_error:
            error_msg = str(table_error).lower()
            if "403" in error_msg or "access denied" in error_msg:
                context.add_result(
                    self.get_step_name(),
                    False,
                    "Access denied to list tables - grant 'BigQuery Data Viewer' role to your service account",
                )
            elif "permission" in error_msg:
                context.add_result(
                    self.get_step_name(),
                    False,
                    "Insufficient permissions to list tables - check IAM roles",
                )
            else:
                context.add_result(
                    self.get_step_name(),
                    False,
                    f"Table listing test failed: {table_error}",
                )

            logger.error(f"❌ Table listing test failed: {table_error}")
            return False


class BigQueryValidationChain:
    """
    Main validation chain coordinator for BigQuery connections.

    Sets up and manages the chain of validation steps.
    """

    def __init__(self):
        """Initialize the BigQuery validation chain."""
        # Create validation steps
        self.dataset_step = DatasetExistenceValidationStep()
        self.query_step = QueryExecutionValidationStep()
        self.table_step = TableListingValidationStep()

        # Chain the steps together
        self.dataset_step.set_next(self.query_step).set_next(self.table_step)

    def validate(self, db, config) -> bool:
        """
        Run the complete validation chain.

        Args:
            db: Database connection object
            config: Configuration object

        Returns:
            True if all enabled validations passed, False if any failed
        """
        # Parse connection string
        connection_string = config.database.connection_string
        parts = connection_string.replace("bigquery://", "").split("/")

        if len(parts) < 1:
            logger.error(
                "❌ Invalid BigQuery connection string format. Expected at least: bigquery://project_id"
            )
            return False

        project_id = parts[0]
        dataset_id = parts[1] if len(parts) > 1 else "CROSS_PROJECT_ACCESS"

        # Check if cross-project access is enabled
        cross_project_config = getattr(config.database, "cross_project_access", None)
        is_cross_project_enabled = cross_project_config and getattr(
            cross_project_config, "enabled", False
        )

        # Create validation context
        context = ValidationContext(
            db=db,
            config=config,
            connection_string=connection_string,
            project_id=project_id,
            dataset_id=dataset_id,
            is_cross_project_enabled=is_cross_project_enabled,
        )

        logger.info(f"Testing BigQuery connection to project '{project_id}'...")
        if is_cross_project_enabled:
            logger.info(
                "Cross-project access enabled - some validation steps will be skipped"
            )

        # Execute the validation chain
        success = self.dataset_step.handle(context)

        # Provide appropriate success messages based on configuration and results
        if success:
            if is_cross_project_enabled:
                logger.info("✅ BigQuery connection validated for cross-project access")
                logger.info(
                    "✅ You can query tables across projects using fully qualified names like:"
                )
                logger.info("   `other-project.dataset_name.table_name`")
            else:
                logger.info(
                    f"✅ BigQuery connection fully validated for project '{project_id}'"
                )
                if dataset_id and dataset_id != "CROSS_PROJECT_ACCESS":
                    logger.info(
                        f"✅ Dataset '{dataset_id}' is accessible with full permissions"
                    )
        else:
            # Log specific error messages from failed steps
            for step_name, error_msg in context.error_messages.items():
                logger.error(f"💡 {step_name}: {error_msg}")

        return success
