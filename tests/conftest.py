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
#   PyYAML (MIT)
#   pytest (MIT)

"""Pytest configuration and fixtures for AskRITA test suite."""

import os
import tempfile
from unittest.mock import Mock, patch

import pytest
import yaml

# ---------------------------------------------------------------------------
# Test-data string constants (used 3+ times — defined once to avoid duplication)
# ---------------------------------------------------------------------------
_GROUP_A = "Group A"
_GROUP_B = "Group B"
_PRODUCT_A = "Product A"
_PRODUCT_B = "Product B"
_CUSTOMER_A = "Customer A"
_CUSTOMER_B = "Customer B"
_CUSTOMER_C = "Customer C"
_MOCKED_ANSWER = "Mocked answer"
_TEST_REASON = "Test reason"
_MOCKED_LLM_RESPONSE = "Mocked LLM response"
_TEST_CHART = "Test Chart"
_REGION_A = "Region A"
_REGION_B = "Region B"
_STEP_PARSE_QUESTION = "parse_question"
_STEP_GENERATE_SQL = "generate_sql"
_STEP_FORMAT_RESULTS = "format_results"
_STEP_CHOOSE_VISUALIZATION = "choose_visualization"

from askrita.config_manager import ConfigManager, reset_config
from askrita.sqlagent.database.DatabaseManager import DatabaseManager
from askrita.sqlagent.formatters.DataFormatter import DataFormatter
from askrita.sqlagent.State import WorkflowState
from askrita.sqlagent.workflows.SQLAgentWorkflow import SQLAgentWorkflow
from askrita.utils.LLMManager import LLMManager


def _build_legacy_format(visualization, sample_data):
    """Return the legacy_format dict for the given visualization type and sample data."""
    if visualization == "scatter":
        if _GROUP_A in sample_data and _GROUP_B in sample_data:
            return {
                "series": [
                    {
                        "name": _GROUP_A,
                        "label": _GROUP_A,
                        "data": [
                            {"x": 10, "y": 100, "id": 0},
                            {"x": 20, "y": 150, "id": 1},
                        ],
                        "marker": {"enabled": True},
                    },
                    {
                        "name": _GROUP_B,
                        "label": _GROUP_B,
                        "data": [
                            {"x": 15, "y": 120, "id": 2},
                            {"x": 25, "y": 180, "id": 3},
                        ],
                        "marker": {"enabled": True},
                    },
                ]
            }
        return {
            "series": [
                {
                    "name": "Test Series",
                    "label": "Data Points",
                    "data": [
                        {"x": 10, "y": 100, "id": 0},
                        {"x": 20, "y": 150, "id": 1},
                        {"x": 30, "y": 200, "id": 2},
                    ],
                    "marker": {"enabled": True},
                }
            ]
        }
    if visualization == "pie":
        return {
            "data": [
                {"name": "Category A", "value": 30},
                {"name": "Category B", "value": 70},
            ]
        }
    if visualization in ["bar", "horizontal_bar"]:
        if "Q1" in sample_data and "Q2" in sample_data:
            return {
                "labels": [_PRODUCT_A, _PRODUCT_B],
                "values": [
                    {"label": "Q1", "data": [1000.0, 800.0]},
                    {"label": "Q2", "data": [1200.0, 900.0]},
                ],
            }
        return {
            "labels": [_PRODUCT_A, _PRODUCT_B, "Product C"],
            "values": [{"label": "Sales", "data": [100.0, 150.0, 80.0]}],
        }
    if visualization == "line":
        if _REGION_A in sample_data and _REGION_B in sample_data:
            return {
                "xValues": ["2023-01", "2023-02"],
                "yValues": [
                    {"label": "Region A Series 1", "data": [1000.0]},
                    {"label": "Region A Series 2", "data": [1200.0]},
                    {"label": "Region B Series 1", "data": [800.0]},
                    {"label": "Region B Series 2", "data": [900.0]},
                ],
                "yAxisLabel": "Revenue",
            }
        return {
            "xValues": ["2023-01", "2023-02", "2023-03"],
            "yValues": [{"label": "Revenue", "data": [1000.0, 1200.0, 1100.0]}],
        }
    return {"series": [{"data": [10, 20, 30]}], "labels": ["A", "B", "C"]}


def _mock_structured_output(system_prompt, human_prompt, response_model, **kwargs):
    """Module-level mock for structured output used by mock_llm_manager fixture."""
    from unittest.mock import Mock

    from askrita.sqlagent.formatters.DataFormatter import (
        ChartDataset,
        DataPoint,
        DualVisualizationResponse,
        UniversalChartData,
    )

    visualization = kwargs.get("visualization", "bar")
    sample_data = kwargs.get("sample_data", "")

    mock_response = Mock(spec=DualVisualizationResponse)
    mock_response.legacy_format = _build_legacy_format(visualization, sample_data)

    universal_chart = UniversalChartData(
        type=visualization,
        title=_TEST_CHART,
        datasets=[
            ChartDataset(
                label="Test Series",
                data=[DataPoint(value=10), DataPoint(value=20), DataPoint(value=30)],
            )
        ],
        labels=["A", "B", "C"],
    )
    mock_response.universal_format = universal_chart

    return mock_response


@pytest.fixture(autouse=True)
def reset_global_config():
    """Reset global config before each test."""
    reset_config()
    yield
    reset_config()


@pytest.fixture
def sample_config_data():
    """Sample configuration data for testing."""
    return {
        "database": {
            "connection_string": "sqlite:///test.db",
            "query_timeout": 30,
            "max_results": 100,
            "cache_schema": True,
            "schema_refresh_interval": 3600,
        },
        "llm": {
            "provider": "openai",
            "model": "gpt-4o",
            "temperature": 0.1,
            "max_tokens": 4000,
            "timeout": 60,
        },
        "workflow": {
            "steps": {
                _STEP_PARSE_QUESTION: True,
                "get_unique_nouns": True,
                _STEP_GENERATE_SQL: True,
                "validate_and_fix_sql": True,
                "execute_sql": True,
                _STEP_FORMAT_RESULTS: True,
                # New combined visualization step (default)
                "choose_and_format_visualization": True,
                # Legacy separate steps (disabled by default)
                _STEP_CHOOSE_VISUALIZATION: False,
                "format_data_for_visualization": False,
            },
            "max_retries": 3,
            "output_format": "json",
        },
        "framework": {"default_output_format": "text", "show_metadata": True},
        "business_rules": {
            "data_validation": {
                "skip_null_values": True,
                "skip_empty_strings": True,
                "skip_na_values": True,
            }
        },
        "prompts": {
            _STEP_PARSE_QUESTION: {
                "system": "You are a data analyst. Parse the question.",
                "human": "Question: {question}\nSchema: {schema}",
            },
            _STEP_GENERATE_SQL: {
                "system": "Generate SQL for {database_type}.",
                "human": "Question: {question}",
            },
            "validate_sql": {
                "system": "Validate SQL query.",
                "human": "Query: {sql_query}",
            },
            _STEP_FORMAT_RESULTS: {
                "system": "Format query results.",
                "human": "Results: {query_results}",
            },
            _STEP_CHOOSE_VISUALIZATION: {
                "system": "Choose visualization type.",
                "human": "Data: {query_results}",
            },
            "choose_and_format_visualization": {
                "system": "Choose visualization type AND format data in single response.",
                "human": "Question: {question}\nSQL: {sql_query}\nRows: {num_rows} x {num_cols}\nSample: {query_results_sample}\nFull: {query_results_full}",
            },
        },
    }


@pytest.fixture
def temp_config_file(sample_config_data):
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(sample_config_data, f)
        temp_path = f.name

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def mock_config(sample_config_data, monkeypatch):
    """Create a mock ConfigManager instance."""
    # Set OPENAI_API_KEY to prevent validation failures
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-12345")

    config = Mock(spec=ConfigManager)
    config._config_data = sample_config_data

    # Mock properties
    from askrita.config_manager import (
        DatabaseConfig,
        FrameworkConfig,
        LLMConfig,
        WorkflowConfig,
    )

    config.database = DatabaseConfig(**sample_config_data["database"])
    config.llm = LLMConfig(**sample_config_data["llm"])
    config.workflow = WorkflowConfig(**sample_config_data["workflow"])
    config.framework = FrameworkConfig(**sample_config_data["framework"])

    # Mock methods
    config.get_database_type.return_value = "SQLite"
    config.is_step_enabled.return_value = True

    def get_prompt_mock(name, template_type):
        return sample_config_data["prompts"].get(name, {}).get(template_type, "")

    config.get_prompt.side_effect = get_prompt_mock
    config.get_business_rule.return_value = sample_config_data["business_rules"][
        "data_validation"
    ]
    config.validate_config.return_value = True
    config.get_schema_cache.return_value = None
    config.set_schema_cache = Mock()

    return config


@pytest.fixture
def mock_database():
    """Create a mock database instance."""
    db = Mock()
    db.run_no_throw.return_value = [
        ("John Doe", 1000),
        ("Jane Smith", 1500),
        ("Bob Johnson", 800),
    ]
    db.get_table_info.return_value = "Tables: customers, orders, products"
    return db


@pytest.fixture
def mock_llm():
    """Create a mock LLM instance."""
    llm = Mock()
    llm.invoke.return_value = Mock(content=_MOCKED_LLM_RESPONSE)
    return llm


@pytest.fixture
def mock_database_manager(mock_config, mock_database):
    """Create a mock DatabaseManager."""
    with patch("langchain_community.utilities.SQLDatabase", create=True) as mock_sql_db:
        mock_sql_db.from_uri.return_value = mock_database

        db_manager = Mock(spec=DatabaseManager)
        db_manager.config = mock_config
        db_manager.db = mock_database

        # Mock methods
        db_manager.get_schema.return_value = """
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100),
            email VARCHAR(100),
            created_at TIMESTAMP
        );
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            amount DECIMAL(10,2),
            order_date DATE
        );
        """

        db_manager.execute_query.return_value = [
            ("Customer 1", 1000.0),
            ("Customer 2", 1500.0),
            ("Customer 3", 800.0),
        ]

        db_manager.test_connection.return_value = True
        db_manager.get_table_names.return_value = ["customers", "orders", "products"]
        db_manager.get_connection_info.return_value = {
            "database_type": "SQLite",
            "host": "localhost",
            "database_name": "test.db",
        }

        return db_manager


@pytest.fixture
def mock_llm_manager(mock_config, mock_llm):
    """Create a mock LLMManager."""
    llm_manager = Mock(spec=LLMManager)
    llm_manager.config = mock_config
    llm_manager.llm = mock_llm

    # Mock methods with realistic responses
    def mock_invoke_with_config_prompt(prompt_name, **kwargs):
        if prompt_name == _STEP_PARSE_QUESTION:
            return '{"is_relevant": true, "relevant_tables": [{"table_name": "customers", "noun_columns": ["name"]}]}'
        elif prompt_name == _STEP_GENERATE_SQL:
            return "SELECT name, amount FROM customers JOIN orders ON customers.id = orders.customer_id ORDER BY amount DESC LIMIT 10"
        elif prompt_name == "validate_sql":
            return '{"corrected_query": "SELECT name, amount FROM customers JOIN orders ON customers.id = orders.customer_id ORDER BY amount DESC LIMIT 10", "issues_found": []}'
        elif prompt_name == _STEP_FORMAT_RESULTS:
            return "Here are the top customers by order amount: Customer 1 ($1000), Customer 2 ($1500), Customer 3 ($800)"
        elif prompt_name == _STEP_CHOOSE_VISUALIZATION:
            return '{"chart_type": "bar", "reason": "Bar chart is best for comparing values across categories"}'
        else:
            return _MOCKED_LLM_RESPONSE

    llm_manager.invoke_with_config_prompt.side_effect = mock_invoke_with_config_prompt
    llm_manager.invoke.return_value = _MOCKED_LLM_RESPONSE
    llm_manager.test_connection.return_value = True
    llm_manager.get_model_info.return_value = {
        "provider": "openai",
        "model": "gpt-4o",
        "temperature": 0.1,
    }

    llm_manager.invoke_with_structured_output_direct.side_effect = (
        _mock_structured_output
    )
    llm_manager.invoke_with_structured_output.side_effect = _mock_structured_output

    return llm_manager


@pytest.fixture
def sample_query_results():
    """Sample query results for testing."""
    return [
        (_CUSTOMER_A, 1000.0),
        (_CUSTOMER_B, 1500.0),
        (_CUSTOMER_C, 800.0),
        ("Customer D", 1200.0),
        ("Customer E", 950.0),
    ]


@pytest.fixture
def sample_state():
    """Sample workflow state for testing."""
    return {
        "question": "What are the top 5 customers by order amount?",
        "parsed_question": {
            "is_relevant": True,
            "relevant_tables": [{"table_name": "customers", "noun_columns": ["name"]}],
        },
        "unique_nouns": [_CUSTOMER_A, _CUSTOMER_B, _CUSTOMER_C],
        "sql_query": "SELECT name, amount FROM customers JOIN orders ON customers.id = orders.customer_id ORDER BY amount DESC LIMIT 5",
        "query_results": [
            (_CUSTOMER_A, 1000.0),
            (_CUSTOMER_B, 1500.0),
            (_CUSTOMER_C, 800.0),
        ],
        "answer": "Top customers: Customer B ($1500), Customer A ($1000), Customer C ($800)",
        "visualization": "bar",
        "visualization_reason": "Bar chart is best for comparing values",
        "chart_data": {
            "labels": [_CUSTOMER_A, _CUSTOMER_B, _CUSTOMER_C],
            "values": [{"data": [1000.0, 1500.0, 800.0], "label": "Order Amount"}],
        },
    }


@pytest.fixture
def mock_sql_agent_workflow(mock_config, mock_database_manager, mock_llm_manager):
    """Create a mock SQLAgentWorkflow."""
    # Create a mock workflow without running the actual initialization
    workflow = Mock(spec=SQLAgentWorkflow)
    workflow.config = mock_config
    workflow.db_manager = mock_database_manager
    workflow.llm_manager = mock_llm_manager
    workflow.data_formatter = Mock()

    from askrita.sqlagent.formatters.DataFormatter import (
        ChartDataset,
        DataPoint,
        UniversalChartData,
    )

    # Mock the key methods with proper return values
    mock_chart_data = UniversalChartData(
        type="bar",
        title=_TEST_CHART,
        datasets=[ChartDataset(label="Test", data=[DataPoint(label="A", value=1)])],
    )

    workflow.query.return_value = WorkflowState(
        answer=_MOCKED_ANSWER,
        visualization="bar",
        visualization_reason=_TEST_REASON,
        chart_data=mock_chart_data,
    )

    workflow.run.return_value = WorkflowState(
        answer=_MOCKED_ANSWER,
        visualization="bar",
        visualization_reason=_TEST_REASON,
        chart_data=mock_chart_data,
    )

    workflow.run_sql_agent.return_value = WorkflowState(
        answer=_MOCKED_ANSWER,
        visualization="bar",
        visualization_reason=_TEST_REASON,
        chart_data=mock_chart_data,
    )

    workflow.get_graph.return_value = Mock()
    workflow.save_workflow_diagram.return_value = None
    workflow.create_workflow.return_value = Mock()

    return workflow


@pytest.fixture
def mock_data_formatter(mock_config, mock_llm_manager):
    """Create a mock DataFormatter."""
    # Create DataFormatter and set the LLM manager directly
    data_formatter = DataFormatter(mock_config, test_llm_connection=False)
    data_formatter.llm_manager = mock_llm_manager

    # Mock the llm.with_structured_output method for the new single LLM call approach
    # This returns a mock LLM that will invoke with the mocked structured output
    def mock_with_structured_output(response_model, method="json_schema"):
        mock_structured_llm = Mock()

        # When invoked, return the mock response from the existing mock function
        def mock_invoke(messages):
            # Extract the visualization type from messages
            user_content = messages[1]["content"] if len(messages) > 1 else ""
            viz_type = "bar"  # default
            if "scatter" in user_content.lower():
                viz_type = "scatter"
            elif "pie" in user_content.lower():
                viz_type = "pie"
            elif "line" in user_content.lower():
                viz_type = "line"

            # Call the existing mock function
            return mock_llm_manager.invoke_with_structured_output_direct.side_effect(
                "",
                "",
                response_model,
                visualization=viz_type,
                sample_data=user_content,
                data=user_content,
            )

        mock_structured_llm.invoke = mock_invoke
        return mock_structured_llm

    mock_llm_manager.llm.with_structured_output = mock_with_structured_output

    return data_formatter


# Legacy fixture name for backward compatibility in tests
@pytest.fixture
def mock_sql_agent(mock_sql_agent_workflow):
    """Legacy fixture name - returns SQLAgentWorkflow for backward compatibility."""
    return mock_sql_agent_workflow


@pytest.fixture
def mock_workflow_manager(mock_sql_agent_workflow):
    """Legacy fixture name - returns SQLAgentWorkflow for backward compatibility."""
    return mock_sql_agent_workflow


@pytest.fixture
def mock_sql_agent_workflow_class():
    """Mock the SQLAgentWorkflow class constructor to avoid workflow compilation."""
    with patch(
        "askrita.sqlagent.workflows.SQLAgentWorkflow.SQLAgentWorkflow", create=True
    ) as mock_class:
        mock_instance = Mock(spec=SQLAgentWorkflow)

        from askrita.sqlagent.formatters.DataFormatter import (
            ChartDataset,
            DataPoint,
            UniversalChartData,
        )

        # Set up default return values for all key methods
        mock_chart_data = UniversalChartData(
            type="bar",
            title=_TEST_CHART,
            datasets=[ChartDataset(label="Test", data=[DataPoint(label="A", value=1)])],
        )

        mock_instance.query.return_value = WorkflowState(
            answer=_MOCKED_ANSWER,
            visualization="bar",
            visualization_reason=_TEST_REASON,
            chart_data=mock_chart_data,
        )

        mock_instance.run.return_value = mock_instance.query.return_value
        mock_instance.run_sql_agent.return_value = mock_instance.query.return_value
        mock_instance.get_graph.return_value = Mock()
        mock_instance.save_workflow_diagram.return_value = None
        mock_instance.create_workflow.return_value = Mock()

        # Make the class constructor return our mock instance
        mock_class.return_value = mock_instance

        yield mock_class, mock_instance


# Test data fixtures
@pytest.fixture
def invalid_sql_queries():
    """Collection of invalid/dangerous SQL queries for security testing."""
    return [
        "DROP TABLE customers",
        "DELETE FROM orders WHERE 1=1",
        "INSERT INTO customers VALUES ('hacker', 'hack@evil.com')",
        "UPDATE customers SET name = 'hacked'",
        "EXEC xp_cmdshell 'dir'",
        "SELECT * FROM customers; DROP TABLE orders;",
        "SELECT * FROM customers WHERE name = ''; DELETE FROM orders; --'",
    ]


@pytest.fixture
def valid_sql_queries():
    """Collection of valid SQL queries for testing."""
    return [
        "SELECT * FROM customers",
        "SELECT name, email FROM customers WHERE created_at > '2023-01-01'",
        "SELECT c.name, SUM(o.amount) FROM customers c JOIN orders o ON c.id = o.customer_id GROUP BY c.name",
        "WITH top_customers AS (SELECT customer_id, SUM(amount) as total FROM orders GROUP BY customer_id) SELECT * FROM top_customers",
    ]


@pytest.fixture
def visualization_test_data():
    """Test data for different visualization types."""
    return {
        "bar_chart_2_cols": [(_PRODUCT_A, 100), (_PRODUCT_B, 150), ("Product C", 80)],
        "bar_chart_3_cols": [
            ("Q1", _PRODUCT_A, 100),
            ("Q1", _PRODUCT_B, 150),
            ("Q2", _PRODUCT_A, 120),
            ("Q2", _PRODUCT_B, 180),
        ],
        "line_chart_2_cols": [("2023-01", 1000), ("2023-02", 1200), ("2023-03", 1100)],
        "line_chart_3_cols": [
            ("2023-01", _REGION_A, 1000),
            ("2023-01", _REGION_B, 800),
            ("2023-02", _REGION_A, 1200),
            ("2023-02", _REGION_B, 900),
        ],
        "scatter_plot_2_cols": [(10, 100), (20, 150), (30, 200)],
        "scatter_plot_3_cols": [
            (_GROUP_A, 10, 100),
            (_GROUP_A, 20, 150),
            (_GROUP_B, 15, 120),
            (_GROUP_B, 25, 180),
        ],
    }


@pytest.fixture
def error_scenarios():
    """Common error scenarios for testing exception handling."""
    return {
        "database_connection_error": "Database connection failed",
        "llm_api_error": "LLM API rate limit exceeded",
        "invalid_config_error": "Invalid configuration format",
        "query_timeout_error": "Query execution timeout",
        "validation_error": "Input validation failed",
    }
