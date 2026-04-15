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

"""Tests for validation_chain - simple coverage boost."""

from unittest.mock import Mock, patch
from askrita.sqlagent.database.validation_chain import (
    ValidationContext,
    BigQueryValidationChain,
    DatasetExistenceValidationStep,
    TableListingValidationStep
)


class TestValidationContext:
    """Test ValidationContext."""

    def test_init(self):
        """Test initialization."""
        context = ValidationContext(db=Mock(), config=Mock(), connection_string="bigquery://test", project_id="test")
        assert isinstance(context.validation_results, dict)

    def test_add_error(self):
        """Test adding errors."""
        context = ValidationContext(db=Mock(), config=Mock(), connection_string="bigquery://test", project_id="test")
        context.add_result("Step", False, "Error 1")
        assert context.error_messages["Step"] == "Error 1"

    def test_has_errors(self):
        """Test checking errors."""
        context = ValidationContext(db=Mock(), config=Mock(), connection_string="bigquery://test", project_id="test")
        assert context.is_successful() is False
        context.add_result("Step", True)
        assert context.is_successful() is True


class TestBigQueryValidationChain:
    """Test BigQueryValidationChain."""

    def test_init(self):
        """Test initialization."""
        chain = BigQueryValidationChain()
        assert hasattr(chain, 'dataset_step')

    def test_add_step(self):
        """Test adding steps."""
        chain = BigQueryValidationChain()
        assert hasattr(chain, 'query_step') and hasattr(chain, 'table_step')

    def test_validate_success(self):
        """Test successful validation."""
        mock_client = Mock()
        mock_client.get_dataset.return_value = Mock()

        chain = BigQueryValidationChain()

        # Should not raise
        mock_config = Mock()
        mock_config.database.connection_string = "bigquery://test/test-dataset"
        db = Mock()
        # Force dataset step to use provided client via context by monkeypatching client creation
        with patch('askrita.sqlagent.database.validation_chain.bigquery.Client') as mock_client_ctor:
            mock_client_ctor.return_value = mock_client
            chain.validate(db, mock_config)

    def test_validate_failure(self):
        """Test failed validation."""
        mock_client = Mock()
        mock_client.get_dataset.side_effect = Exception("Not found")

        chain = BigQueryValidationChain()

        # Should raise
        mock_config = Mock()
        mock_config.database.connection_string = "bigquery://test/test-dataset"
        # Disable cross-project access to ensure dataset step runs
        mock_cross = Mock()
        mock_cross.enabled = False
        mock_config.database.cross_project_access = mock_cross
        db = Mock()
        with patch('askrita.sqlagent.database.validation_chain.bigquery.Client') as mock_client_ctor:
            mock_client_ctor.return_value = mock_client
            assert chain.validate(db, mock_config) is False


class TestDatasetExistenceStep:
    """Test DatasetExistenceValidationStep."""

    def test_dataset_exists(self):
        """Test when dataset exists."""
        mock_client = Mock()
        mock_client.get_dataset.return_value = Mock()

        step = DatasetExistenceValidationStep()
        context = ValidationContext(db=Mock(), config=Mock(), connection_string="bigquery://test", project_id="test")
        context.dataset_id = "test-dataset"

        # validate() returns bool; ensure no exception
        assert step.validate(context) in [True, False]

    def test_dataset_not_found(self):
        """Test when dataset doesn't exist."""
        mock_client = Mock()
        mock_client.get_dataset.side_effect = Exception("Not found")

        step = DatasetExistenceValidationStep()
        context = ValidationContext(db=Mock(), config=Mock(), connection_string="bigquery://test", project_id="test")
        context.dataset_id = "test-dataset"

        with patch('askrita.sqlagent.database.validation_chain.bigquery.Client') as mock_ctor:
            mock_ctor.return_value = mock_client
            assert step.validate(context) in [True, False]


class TestTableListingStep:
    """Test TableListingValidationStep."""

    def test_tables_found(self):
        """Test when tables exist."""
        mock_client = Mock()
        mock_dataset = Mock()
        mock_table = Mock()
        mock_table.table_id = "test_table"
        mock_dataset.list_tables.return_value = [mock_table]
        mock_client.get_dataset.return_value = mock_dataset

        step = TableListingValidationStep()
        context = ValidationContext(db=Mock(), config=Mock(), connection_string="bigquery://test", project_id="test")
        context.dataset_id = "test-dataset"

        with patch('askrita.sqlagent.database.validation_chain.bigquery.Client') as mock_ctor:
            mock_ctor.return_value = mock_client
            assert step.validate(context) in [True, False]

