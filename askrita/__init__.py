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

"""AskRITA - Reasoning Interface for Text-to-Analytics - Natural language SQL and NoSQL query framework powered by LangChain and LLMs."""

__version__ = "0.13.14"
__author__ = "AskRITA Contributors"
__description__ = "AskRITA - Reasoning Interface for Text-to-Analytics - Natural language SQL and NoSQL query framework powered by LangChain and LLMs"

from .config_manager import ConfigManager
from .dataclassifier.DataClassificationWorkflow import DataClassificationWorkflow
from .exceptions import (
    AskRITAError,
    ConfigurationError,
    DatabaseError,
    ExportError,
    LLMError,
    QueryError,
    ResearchError,
    TimeoutError,
    ValidationError,
)

# Research capabilities (New in v0.11.0)
from .research import (
    ColumnAnalysis,
    DescriptiveStats,
    EvaluationOutput,
    ResearchAgent,
    ResearchWorkflowState,
    SchemaAnalysisReport,
    SchemaAnalyzer,
    StatisticalAnalyzer,
    StatisticalResult,
    TableAnalysis,
)

# Export settings for export functionality
from .sqlagent.exporters.models import ExportSettings

# Export Pydantic models for downstream application integration
from .sqlagent.formatters.DataFormatter import (
    AxisConfig,
    ChartDataset,
    DataPoint,
    DualVisualizationResponse,
    UniversalChartData,
)

# Export TypedDict state models for workflow integration
from .sqlagent.State import WorkflowState
from .sqlagent.workflows.NoSQLAgentWorkflow import NoSQLAgentWorkflow

# Public API - only expose what users need
from .sqlagent.workflows.SQLAgentWorkflow import SQLAgentWorkflow

__all__ = [
    # Core workflows
    "SQLAgentWorkflow",
    "NoSQLAgentWorkflow",
    "DataClassificationWorkflow",
    "ConfigManager",
    "create_sql_agent",
    "create_nosql_agent",
    "create_data_classifier",
    # Research Agent - CRISP-DM workflow (New in v0.11.0)
    "ResearchAgent",
    "ResearchWorkflowState",
    "EvaluationOutput",
    "SchemaAnalyzer",
    "SchemaAnalysisReport",
    "TableAnalysis",
    "ColumnAnalysis",
    "StatisticalAnalyzer",
    "StatisticalResult",
    "DescriptiveStats",
    # Exceptions
    "AskRITAError",
    "ConfigurationError",
    "DatabaseError",
    "LLMError",
    "ValidationError",
    "QueryError",
    "TimeoutError",
    "ExportError",
    "ResearchError",
    # Pydantic models for chart data (for downstream integration)
    "DataPoint",
    "ChartDataset",
    "UniversalChartData",
    "AxisConfig",
    "DualVisualizationResponse",
    # TypedDict models for workflow state (for downstream integration)
    "WorkflowState",
    # Export settings
    "ExportSettings",
]


# Convenience function for quick usage
def create_sql_agent(config_path=None):
    """
    Create a configured SQL agent workflow for immediate use.

    Args:
        config_path: Path to YAML configuration file (if None, uses built-in defaults)

    Returns:
        SQLAgentWorkflow: Ready-to-use SQL agent workflow with pre-compiled graph

    Examples:
        Basic usage (zero setup):
        >>> workflow = create_sql_agent()
        >>> result = workflow.query("What are the top 10 customers?")
        >>> print(result['answer'])

        Production with config:
        >>> workflow = create_sql_agent("config.yaml")
        >>> result = workflow.query("Show me monthly sales trends")

        Direct instantiation (preferred):
        >>> from askrita import SQLAgentWorkflow, ConfigManager
        >>> config = ConfigManager("config.yaml")
        >>> workflow = SQLAgentWorkflow(config)
        >>> result = workflow.query("Show me sales data")

    Raises:
        ConfigurationError: If config file is invalid
        ValueError: If required configuration is missing
    """
    try:
        config = ConfigManager(config_path)
        if not config.validate_config():
            raise ConfigurationError(
                "Configuration validation failed. Check your config file."
            )
        return SQLAgentWorkflow(config)
    except FileNotFoundError as e:
        raise ConfigurationError(f"Configuration file not found: {e}")
    except (ConfigurationError, DatabaseError, LLMError):
        # Re-raise framework exceptions as-is
        raise
    except Exception as e:
        raise ConfigurationError(f"Failed to create SQL agent workflow: {e}")


def create_nosql_agent(config_path=None):
    """
    Create a configured NoSQL agent workflow for immediate use.

    Args:
        config_path: Path to YAML configuration file (if None, uses built-in defaults)

    Returns:
        NoSQLAgentWorkflow: Ready-to-use NoSQL agent workflow with pre-compiled graph

    Examples:
        Basic usage:
        >>> workflow = create_nosql_agent("mongodb_config.yaml")
        >>> result = workflow.query("How many orders were placed last month?")
        >>> print(result['answer'])

        Direct instantiation (preferred):
        >>> from askrita import NoSQLAgentWorkflow, ConfigManager
        >>> config = ConfigManager("mongodb_config.yaml")
        >>> workflow = NoSQLAgentWorkflow(config)
        >>> result = workflow.query("Show me top customers by order count")

    Raises:
        ConfigurationError: If config file is invalid
        ValueError: If required configuration is missing
    """
    try:
        config = ConfigManager(config_path)
        if not config.validate_config():
            raise ConfigurationError(
                "Configuration validation failed. Check your config file."
            )
        return NoSQLAgentWorkflow(config)
    except FileNotFoundError as e:
        raise ConfigurationError(f"Configuration file not found: {e}")
    except (ConfigurationError, DatabaseError, LLMError):
        raise
    except Exception as e:
        raise ConfigurationError(f"Failed to create NoSQL agent workflow: {e}")


def create_data_classifier(config_path=None):
    """
    Create a configured data classification workflow for immediate use.

    Args:
        config_path: Path to YAML configuration file (if None, uses built-in defaults)

    Returns:
        DataClassificationWorkflow: Ready-to-use data classification workflow

    Examples:
        Basic usage:
        >>> workflow = create_data_classifier("classification_config.yaml")
        >>> result = workflow.run_workflow()
        >>> print(f"Processed {result['statistics']['processed_rows']} rows")

        Single text classification:
        >>> workflow = create_data_classifier("config.yaml")
        >>> result = workflow.classify_text("Customer service was terrible!")
        >>> print(result['sentiment_analysis'])

        Direct instantiation (preferred):
        >>> from askrita import DataClassificationWorkflow, ConfigManager
        >>> config = ConfigManager("config.yaml")
        >>> workflow = DataClassificationWorkflow(config)
        >>> result = workflow.run_workflow()

    Raises:
        ConfigurationError: If config file is invalid
        ValueError: If required configuration is missing
    """
    try:
        config = ConfigManager(config_path)
        return DataClassificationWorkflow(config)
    except FileNotFoundError as e:
        raise ConfigurationError(f"Configuration file not found: {e}")
    except (ConfigurationError, LLMError):
        # Re-raise framework exceptions as-is
        raise
    except Exception as e:
        raise ConfigurationError(f"Failed to create data classification workflow: {e}")
