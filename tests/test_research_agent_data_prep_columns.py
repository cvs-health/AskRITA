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

"""Tests for ResearchAgent column name parsing from SQL."""
from unittest.mock import Mock

from askrita.research.ResearchAgent import ResearchAgent, ResearchWorkflowState


def test_extract_column_names_from_sql_simple():
    """Test parsing simple column names from SELECT clause."""
    agent = ResearchAgent.__new__(ResearchAgent)

    # Simple columns
    names = agent._extract_column_names_from_sql(
        "SELECT business_line, ltr FROM some_table", 2
    )
    assert names == ["business_line", "ltr"]


def test_extract_column_names_from_sql_with_alias():
    """Test parsing columns with AS aliases."""
    agent = ResearchAgent.__new__(ResearchAgent)

    names = agent._extract_column_names_from_sql(
        "SELECT AVG(ltr) AS average_ltr, member_role FROM table", 2
    )
    assert names == ["average_ltr", "member_role"]


def test_extract_column_names_from_sql_with_functions():
    """Test parsing aggregate functions with implicit aliases."""
    agent = ResearchAgent.__new__(ResearchAgent)

    names = agent._extract_column_names_from_sql(
        "SELECT COUNT(*) AS cnt, business_line FROM table GROUP BY business_line", 2
    )
    assert names == ["cnt", "business_line"]


def test_extract_column_names_from_sql_with_backticks():
    """Test parsing columns with backtick quoting (BigQuery style)."""
    agent = ResearchAgent.__new__(ResearchAgent)

    names = agent._extract_column_names_from_sql(
        "SELECT `member_role`, `ltr` FROM `project.dataset.table`", 2
    )
    assert names == ["member_role", "ltr"]


def test_extract_column_names_returns_none_for_mismatch():
    """Test returns None when parsed count doesn't match expected."""
    agent = ResearchAgent.__new__(ResearchAgent)

    # Expecting 3 but SQL has 2
    names = agent._extract_column_names_from_sql(
        "SELECT a, b FROM table", 3
    )
    assert names is None


def test_extract_column_names_returns_none_for_star():
    """Test returns None for SELECT * queries."""
    agent = ResearchAgent.__new__(ResearchAgent)

    names = agent._extract_column_names_from_sql(
        "SELECT * FROM table", 5
    )
    assert names is None


def test_data_preparation_parses_columns_from_sql():
    """
    Phase A: sql_agent.query() returns the SQL string.
    Phase B: db_manager.execute_query() returns tuple rows.
    ResearchAgent should parse column names from the SQL SELECT clause.
    """
    agent = ResearchAgent.__new__(ResearchAgent)

    agent.sql_agent = Mock()

    # Phase A mock: SQL generation returns sql_query string
    mock_gen = Mock()
    mock_gen.sql_query = "SELECT business_line, ltr FROM some_table"
    agent.sql_agent.query = Mock(return_value=mock_gen)

    # Phase B mock: db_manager executes the SQL and returns raw rows
    agent.sql_agent.db_manager = Mock()
    agent.sql_agent.db_manager.execute_query = Mock(
        return_value=[("Medicare", 42), ("Commercial", 35)]
    )

    state = ResearchWorkflowState(
        evidence_queries=["dummy question"],
        current_query_index=0,
    )

    update = agent._data_preparation(state)

    stored = update["collected_data"]["query_1"]["data"]
    assert isinstance(stored, list)
    assert stored[0].get("business_line") == "Medicare"
    assert stored[0].get("ltr") == 42
    assert stored[1].get("business_line") == "Commercial"
    assert stored[1].get("ltr") == 35


def test_data_preparation_falls_back_to_col_i():
    """
    When SQL parsing fails or count doesn't match, fall back to col_i naming.
    """
    agent = ResearchAgent.__new__(ResearchAgent)

    agent.sql_agent = Mock()
    mock_gen = Mock()
    mock_gen.sql_query = "SELECT * FROM table"  # Can't parse *
    agent.sql_agent.query = Mock(return_value=mock_gen)

    agent.sql_agent.db_manager = Mock()
    agent.sql_agent.db_manager.execute_query = Mock(return_value=[("A", "B", "C")])

    state = ResearchWorkflowState(evidence_queries=["dummy question"], current_query_index=0)
    update = agent._data_preparation(state)

    stored = update["collected_data"]["query_1"]["data"]
    assert stored[0] == {"col_0": "A", "col_1": "B", "col_2": "C"}


def test_data_preparation_handles_dict_rows_directly():
    """When db_manager returns dicts with proper column names, use them directly."""
    agent = ResearchAgent.__new__(ResearchAgent)

    agent.sql_agent = Mock()
    mock_gen = Mock()
    mock_gen.sql_query = "SELECT ltr, role FROM table"
    agent.sql_agent.query = Mock(return_value=mock_gen)

    agent.sql_agent.db_manager = Mock()
    agent.sql_agent.db_manager.execute_query = Mock(
        return_value=[{"ltr": 42, "role": "Medicare"}]
    )

    state = ResearchWorkflowState(evidence_queries=["dummy question"], current_query_index=0)
    update = agent._data_preparation(state)

    stored = update["collected_data"]["query_1"]["data"]
    assert stored[0] == {"ltr": 42, "role": "Medicare"}


def test_data_preparation_remaps_col_i_dicts():
    """
    When DatabaseManager returns dicts with col_i keys, ResearchAgent should
    parse SQL and remap to real column names.
    """
    agent = ResearchAgent.__new__(ResearchAgent)

    agent.sql_agent = Mock()
    mock_gen = Mock()
    mock_gen.sql_query = (
        "SELECT member_role, AVG(ltr) AS average_ltr FROM table GROUP BY member_role"
    )
    agent.sql_agent.query = Mock(return_value=mock_gen)

    agent.sql_agent.db_manager = Mock()
    # Simulates what DatabaseManager._normalize_result produces
    agent.sql_agent.db_manager.execute_query = Mock(
        return_value=[
            {"col_0": "Medicare", "col_1": 42.5},
            {"col_0": "Commercial", "col_1": 35.2},
        ]
    )

    state = ResearchWorkflowState(evidence_queries=["dummy question"], current_query_index=0)
    update = agent._data_preparation(state)

    stored = update["collected_data"]["query_1"]["data"]
    # Should have remapped col_0->member_role, col_1->average_ltr
    assert stored[0].get("member_role") == "Medicare"
    assert stored[0].get("average_ltr") == 42.5
    assert stored[1].get("member_role") == "Commercial"
    assert stored[1].get("average_ltr") == 35.2
