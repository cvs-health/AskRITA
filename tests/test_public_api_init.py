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
#   pytest (MIT)

"""Tests for askrita public API in __init__.py focusing on functionality."""

from unittest.mock import Mock, patch

import pytest


def test_public_exports_available():
    import askrita as lq

    # Core classes
    assert hasattr(lq, "SQLAgentWorkflow")
    assert hasattr(lq, "NoSQLAgentWorkflow")
    assert hasattr(lq, "DataClassificationWorkflow")
    assert hasattr(lq, "ConfigManager")
    # Factory functions
    assert hasattr(lq, "create_sql_agent")
    assert hasattr(lq, "create_nosql_agent")
    assert hasattr(lq, "create_data_classifier")
    # Exceptions
    for name in [
        "AskRITAError",
        "ConfigurationError",
        "DatabaseError",
        "LLMError",
        "ValidationError",
        "QueryError",
        "TimeoutError",
        "ExportError",
    ]:
        assert hasattr(lq, name)
    # Models
    for name in [
        "DataPoint",
        "ChartDataset",
        "UniversalChartData",
        "AxisConfig",
        "DualVisualizationResponse",
        "WorkflowState",
        "ExportSettings",
    ]:
        assert hasattr(lq, name)


def test_create_sql_agent_success():
    # Mock ConfigManager and SQLAgentWorkflow to avoid real config
    with (
        patch("askrita.ConfigManager") as MockConfig,
        patch("askrita.SQLAgentWorkflow") as MockWorkflow,
    ):
        mock_config = Mock()
        mock_config.validate_config.return_value = True
        MockConfig.return_value = mock_config

        import askrita as lq

        wf = lq.create_sql_agent("dummy.yaml")
        assert MockConfig.called
        assert MockWorkflow.called
        assert wf == MockWorkflow.return_value


def test_create_sql_agent_invalid_config_raises():
    with patch("askrita.ConfigManager") as MockConfig:
        mock_config = Mock()
        mock_config.validate_config.return_value = False
        MockConfig.return_value = mock_config

        import askrita as lq

        with pytest.raises(lq.ConfigurationError):
            lq.create_sql_agent("dummy.yaml")


def test_create_sql_agent_missing_file_raises():
    with patch("askrita.ConfigManager", side_effect=FileNotFoundError("missing")):
        import askrita as lq

        with pytest.raises(lq.ConfigurationError):
            lq.create_sql_agent("missing.yaml")


def test_create_data_classifier_success():
    with (
        patch("askrita.ConfigManager") as MockConfig,
        patch("askrita.DataClassificationWorkflow") as MockDC,
    ):
        MockConfig.return_value = Mock()
        import askrita as lq

        wf = lq.create_data_classifier("dummy.yaml")
        assert MockDC.called
        assert wf == MockDC.return_value


def test_create_data_classifier_missing_file_raises():
    with patch("askrita.ConfigManager", side_effect=FileNotFoundError("missing")):
        import askrita as lq

        with pytest.raises(lq.ConfigurationError):
            lq.create_data_classifier("missing.yaml")


def test_create_nosql_agent_success():
    """Test create_nosql_agent factory function."""
    with (
        patch("askrita.ConfigManager") as MockConfig,
        patch("askrita.NoSQLAgentWorkflow") as MockWorkflow,
    ):
        mock_config = Mock()
        mock_config.validate_config.return_value = True
        MockConfig.return_value = mock_config

        import askrita as lq

        wf = lq.create_nosql_agent("mongodb.yaml")
        assert MockConfig.called
        assert MockWorkflow.called
        assert wf == MockWorkflow.return_value


def test_create_nosql_agent_invalid_config_raises():
    """Test create_nosql_agent with invalid config raises error."""
    with patch("askrita.ConfigManager") as MockConfig:
        mock_config = Mock()
        mock_config.validate_config.return_value = False
        MockConfig.return_value = mock_config

        import askrita as lq

        with pytest.raises(lq.ConfigurationError):
            lq.create_nosql_agent("bad.yaml")


def test_create_nosql_agent_missing_file_raises():
    """Test create_nosql_agent with missing file raises error."""
    with patch("askrita.ConfigManager", side_effect=FileNotFoundError("missing")):
        import askrita as lq

        with pytest.raises(lq.ConfigurationError):
            lq.create_nosql_agent("missing.yaml")
