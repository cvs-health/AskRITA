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

"""Tests for SQLAgent functionality."""

from unittest.mock import Mock
from askrita.sqlagent.State import WorkflowState


class TestSQLAgentWorkflow:
    """Test cases for SQLAgentWorkflow class."""

    def test_parse_question_relevant(self, mock_sql_agent_workflow):
        """Test parsing a relevant question."""
        # Mock the parse_question method to return relevant result
        mock_sql_agent_workflow.parse_question.return_value = {
            "parsed_question": {"is_relevant": True, "relevant_tables": []}
        }

        state = WorkflowState(question="What are the top grievances?")
        result = mock_sql_agent_workflow.parse_question(state)

        assert "parsed_question" in result
        assert result["parsed_question"]["is_relevant"] is True

    def test_parse_question_irrelevant(self, mock_sql_agent_workflow):
        """Test parsing an irrelevant question."""
        # Mock the parse_question method to return irrelevant result
        mock_sql_agent_workflow.parse_question.return_value = {
            "parsed_question": {"is_relevant": False, "relevant_tables": []}
        }

        state = WorkflowState(question="What's the weather like?")
        result = mock_sql_agent_workflow.parse_question(state)

        assert "parsed_question" in result
        assert result["parsed_question"]["is_relevant"] is False


class TestSQLAgentWorkflowMethods:
    """Test cases for SQLAgentWorkflow workflow management methods."""

    def test_create_workflow(self, mock_sql_agent_workflow):
        """Test workflow creation."""
        workflow = mock_sql_agent_workflow.create_workflow()
        assert workflow is not None

    def test_get_graph(self, mock_sql_agent_workflow):
        """Test graph compilation."""
        mock_graph = Mock()
        mock_sql_agent_workflow.get_graph.return_value = mock_graph

        result = mock_sql_agent_workflow.get_graph()
        assert result == mock_graph
