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

"""Tests for NoSQLAgentWorkflow."""

import pytest
from unittest.mock import Mock, patch

from askrita.sqlagent.workflows.NoSQLAgentWorkflow import (
    NoSQLAgentWorkflow,
    MongoQueryGenerationResponse,
    MongoQueryValidationResponse,
    ParseQuestionResponse,
    TableInfo,
    FollowupQuestionsResponse,
    ResultsFormattingResponse,
)
from askrita.sqlagent.State import WorkflowState
from askrita.exceptions import ValidationError


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_config():
    """Create a mock ConfigManager for NoSQL workflow."""
    config = Mock()
    config.database.connection_string = "mongodb://user:pass@localhost:27017/testdb"
    config.database.cache_schema = True
    config.database.query_timeout = 30
    config.database.max_results = 1000
    config.database.schema_refresh_interval = 3600
    config.get_database_type.return_value = "MongoDB"
    config.get_schema_descriptions.return_value = None

    config.llm.model = "gpt-4o"
    config.llm.provider = "openai"

    config.workflow.max_retries = 3
    config.workflow.steps = {
        "pii_detection": False,
        "parse_question": True,
        "get_unique_nouns": True,
        "generate_sql": True,
        "validate_and_fix_sql": True,
        "execute_sql": True,
        "format_results": True,
        "choose_and_format_visualization": True,
        "generate_followup_questions": True,
    }
    config.is_step_enabled = lambda step: config.workflow.steps.get(step, True)

    config.chain_of_thoughts = Mock()
    config.chain_of_thoughts.enabled = False

    config.pii_detection = Mock()
    config.pii_detection.enabled = False

    config.framework = Mock()
    config.framework.results_limit_for_llm = 100

    config.get_input_validation_settings = lambda: {
        "max_question_length": 10000,
        "blocked_substrings": ["<script", "javascript:"],
    }

    config.get_schema_cache.return_value = None
    config.set_schema_cache = Mock()

    return config


@pytest.fixture
def mock_nosql_workflow(mock_config):
    """Create a NoSQLAgentWorkflow with all dependencies mocked."""
    with patch(
        "askrita.sqlagent.workflows.NoSQLAgentWorkflow.NoSQLDatabaseManager"
    ) as MockDBManager, patch(
        "askrita.sqlagent.workflows.NoSQLAgentWorkflow.LLMManager"
    ) as MockLLM, patch(
        "askrita.sqlagent.workflows.NoSQLAgentWorkflow.DataFormatter"
    ) as MockFormatter, patch(
        "askrita.sqlagent.workflows.NoSQLAgentWorkflow.create_pii_detector"
    ) as MockPII, patch.object(
        NoSQLAgentWorkflow, "_create_workflow"
    ) as mock_create_wf:
        # Setup mock DB manager
        mock_db = Mock()
        mock_db.get_schema.return_value = "Collection: orders\nFields: _id, amount, date"
        mock_db.execute_query.return_value = [{"_id": "1", "amount": 100}]
        mock_db.db = Mock()
        mock_db.db.run_no_throw.return_value = [{"_id": "active"}]
        mock_db._normalize_result.return_value = [{"_id": "active"}]
        MockDBManager.return_value = mock_db

        # Setup mock LLM manager
        mock_llm = Mock()
        MockLLM.return_value = mock_llm

        # Setup mock data formatter
        mock_formatter = Mock()
        MockFormatter.return_value = mock_formatter

        # Setup mock PII detector
        MockPII.return_value = None

        # Setup mock workflow graph
        mock_graph = Mock()
        mock_create_wf.return_value = mock_graph
        mock_graph.compile.return_value = Mock()

        workflow = NoSQLAgentWorkflow(
            mock_config,
            test_llm_connection=False,
            test_db_connection=False,
            init_schema_cache=False,
        )
        workflow.db_manager = mock_db
        workflow.llm_manager = mock_llm
        workflow.data_formatter = mock_formatter

        yield workflow


# =============================================================================
# PYDANTIC MODEL TESTS
# =============================================================================


class TestPydanticModels:
    """Test NoSQL-specific Pydantic response models."""

    def test_mongo_query_generation_response(self):
        """Test MongoQueryGenerationResponse model."""
        response = MongoQueryGenerationResponse(
            query_command='db.orders.aggregate([{$group: {_id: "$status", count: {$sum: 1}}}])',
            query_reason="Grouped by status to count orders",
        )
        assert "aggregate" in response.query_command
        assert response.query_reason

    def test_mongo_query_validation_response_valid(self):
        """Test MongoQueryValidationResponse for valid query."""
        response = MongoQueryValidationResponse(
            valid=True,
            corrected_query='db.orders.aggregate([{$count: "total"}])',
            issues="",
        )
        assert response.valid is True
        assert response.issues == ""

    def test_mongo_query_validation_response_invalid(self):
        """Test MongoQueryValidationResponse for invalid query."""
        response = MongoQueryValidationResponse(
            valid=False,
            corrected_query='db.orders.aggregate([{$count: "total"}])',
            issues="Missing $match stage",
        )
        assert response.valid is False
        assert "Missing" in response.issues

    def test_parse_question_response(self):
        """Test ParseQuestionResponse model."""
        response = ParseQuestionResponse(
            is_relevant=True,
            relevant_tables=[
                TableInfo(table_name="orders", noun_columns=["status"], relevance_score=0.9)
            ],
        )
        assert response.is_relevant is True
        assert len(response.relevant_tables) == 1

    def test_followup_questions_response(self):
        """Test FollowupQuestionsResponse model."""
        response = FollowupQuestionsResponse(
            followup_questions=["What is the trend?", "Which region?"]
        )
        assert len(response.followup_questions) == 2


# =============================================================================
# WORKFLOW INITIALIZATION TESTS
# =============================================================================


class TestNoSQLWorkflowInit:
    """Test NoSQLAgentWorkflow initialization."""

    def test_initialization_success(self, mock_nosql_workflow):
        """Test successful workflow initialization."""
        assert mock_nosql_workflow is not None
        assert mock_nosql_workflow.db_manager is not None
        assert mock_nosql_workflow.llm_manager is not None
        assert mock_nosql_workflow.data_formatter is not None

    def test_initialization_stores_config(self, mock_nosql_workflow, mock_config):
        """Test that config is stored."""
        assert mock_nosql_workflow.config == mock_config


# =============================================================================
# QUERY VALIDATION TESTS
# =============================================================================


class TestQueryValidation:
    """Test input validation in query() and chat()."""

    def test_query_rejects_non_string(self, mock_nosql_workflow):
        """Test that non-string input raises ValidationError."""
        with pytest.raises(ValidationError, match="must be a string"):
            mock_nosql_workflow.query(123)

    def test_query_rejects_empty_string(self, mock_nosql_workflow):
        """Test that empty string raises ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            mock_nosql_workflow.query("")

    def test_query_rejects_whitespace_only(self, mock_nosql_workflow):
        """Test that whitespace-only string raises ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            mock_nosql_workflow.query("   ")

    def test_chat_rejects_empty_messages(self, mock_nosql_workflow):
        """Test that empty messages list raises ValidationError."""
        with pytest.raises(ValidationError, match="non-empty list"):
            mock_nosql_workflow.chat([])

    def test_chat_rejects_non_list(self, mock_nosql_workflow):
        """Test that non-list messages raises ValidationError."""
        with pytest.raises(ValidationError, match="non-empty list"):
            mock_nosql_workflow.chat("not a list")

    def test_chat_rejects_no_user_message(self, mock_nosql_workflow):
        """Test that messages without user role raises ValidationError."""
        with pytest.raises(ValidationError, match="No user question found"):
            mock_nosql_workflow.chat([{"role": "assistant", "content": "Hello"}])


# =============================================================================
# SAFETY VALIDATION TESTS
# =============================================================================


class TestQuerySafety:
    """Test MongoDB query safety validation."""

    def test_validate_safe_aggregate_query(self, mock_nosql_workflow):
        """Test that safe aggregate queries pass validation."""
        mock_nosql_workflow._validate_query_safety(
            'db.orders.aggregate([{$match: {status: "active"}}, {$group: {_id: "$category", total: {$sum: 1}}}])'
        )

    def test_validate_blocks_out_stage(self, mock_nosql_workflow):
        """Test that $out stage is blocked."""
        with pytest.raises(ValidationError, match="forbidden operation"):
            mock_nosql_workflow._validate_query_safety(
                'db.orders.aggregate([{$match: {}}, {$out: "output_collection"}])'
            )

    def test_validate_blocks_merge_stage(self, mock_nosql_workflow):
        """Test that $merge stage is blocked."""
        with pytest.raises(ValidationError, match="forbidden operation"):
            mock_nosql_workflow._validate_query_safety(
                'db.orders.aggregate([{$merge: {into: "target"}}])'
            )

    def test_validate_blocks_delete(self, mock_nosql_workflow):
        """Test that delete operations are blocked."""
        with pytest.raises(ValidationError, match="forbidden operation"):
            mock_nosql_workflow._validate_query_safety("db.orders.deleteMany({})")

    def test_validate_blocks_insert(self, mock_nosql_workflow):
        """Test that insert operations are blocked."""
        with pytest.raises(ValidationError, match="forbidden operation"):
            mock_nosql_workflow._validate_query_safety('db.orders.insertOne({name: "test"})')

    def test_validate_blocks_update(self, mock_nosql_workflow):
        """Test that update operations are blocked."""
        with pytest.raises(ValidationError, match="forbidden operation"):
            mock_nosql_workflow._validate_query_safety('db.orders.updateMany({}, {$set: {status: "done"}})')

    def test_validate_blocks_drop(self, mock_nosql_workflow):
        """Test that drop operations are blocked."""
        with pytest.raises(ValidationError, match="forbidden operation"):
            mock_nosql_workflow._validate_query_safety("db.orders.drop()")

    def test_validate_blocks_bulk_write(self, mock_nosql_workflow):
        """Test that bulkWrite operations are blocked."""
        with pytest.raises(ValidationError, match="forbidden operation"):
            mock_nosql_workflow._validate_query_safety("db.orders.bulkWrite([])")

    def test_validate_rejects_empty_query(self, mock_nosql_workflow):
        """Test that empty query raises ValidationError."""
        with pytest.raises(ValidationError, match="non-empty string"):
            mock_nosql_workflow._validate_query_safety("")

    def test_validate_rejects_none_query(self, mock_nosql_workflow):
        """Test that None query raises ValidationError."""
        with pytest.raises(ValidationError, match="non-empty string"):
            mock_nosql_workflow._validate_query_safety(None)

    def test_validate_rejects_too_long_query(self, mock_nosql_workflow):
        """Test that overly long queries are rejected."""
        with pytest.raises(ValidationError, match="too long"):
            mock_nosql_workflow._validate_query_safety("a" * 50001)


# =============================================================================
# WORKFLOW STEP TESTS
# =============================================================================


class TestParseQuestion:
    """Test parse_question step."""

    def test_parse_question_success(self, mock_nosql_workflow):
        """Test successful question parsing."""
        mock_nosql_workflow.llm_manager.invoke_with_structured_output.return_value = (
            ParseQuestionResponse(
                is_relevant=True,
                relevant_tables=[TableInfo(table_name="orders", noun_columns=["status"])],
            )
        )

        state = WorkflowState(question="How many orders per month?")
        result = mock_nosql_workflow.parse_question(state)

        assert result["parsed_question"]["is_relevant"] is True
        assert len(result["parsed_question"]["relevant_tables"]) == 1

    def test_parse_question_not_relevant(self, mock_nosql_workflow):
        """Test question parsing when not relevant."""
        mock_nosql_workflow.llm_manager.invoke_with_structured_output.return_value = (
            ParseQuestionResponse(
                is_relevant=False,
                relevant_tables=[],
                relevance_reason="Question is about weather, not database data",
            )
        )

        state = WorkflowState(question="What's the weather today?")
        result = mock_nosql_workflow.parse_question(state)

        assert result["parsed_question"]["is_relevant"] is False
        assert result.get("needs_clarification") is True

    def test_parse_question_disabled(self, mock_nosql_workflow, mock_config):
        """Test parse_question when step is disabled."""
        mock_config.is_step_enabled = lambda step: step != "parse_question"

        state = WorkflowState(question="Test question")
        result = mock_nosql_workflow.parse_question(state)

        assert result["parsed_question"]["is_relevant"] is True

    def test_parse_question_error_handling(self, mock_nosql_workflow):
        """Test parse_question error handling."""
        mock_nosql_workflow.llm_manager.invoke_with_structured_output.side_effect = Exception("LLM error")

        state = WorkflowState(question="Test question")
        result = mock_nosql_workflow.parse_question(state)

        assert result["parsed_question"]["is_relevant"] is False


class TestGetUniqueNouns:
    """Test get_unique_nouns step."""

    def test_get_unique_nouns_success(self, mock_nosql_workflow):
        """Test successful unique nouns extraction."""
        state = WorkflowState(
            question="Show orders by status",
            parsed_question={
                "is_relevant": True,
                "relevant_tables": [
                    {"table_name": "orders", "noun_columns": ["status"]}
                ],
            },
        )

        result = mock_nosql_workflow.get_unique_nouns(state)
        assert "unique_nouns" in result

    def test_get_unique_nouns_not_relevant(self, mock_nosql_workflow):
        """Test unique nouns when question is not relevant."""
        state = WorkflowState(
            question="Test",
            parsed_question={"is_relevant": False, "relevant_tables": []},
        )

        result = mock_nosql_workflow.get_unique_nouns(state)
        assert result["unique_nouns"] == []

    def test_get_unique_nouns_disabled(self, mock_nosql_workflow, mock_config):
        """Test unique nouns when step is disabled."""
        mock_config.is_step_enabled = lambda step: step != "get_unique_nouns"

        state = WorkflowState(question="Test")
        result = mock_nosql_workflow.get_unique_nouns(state)
        assert result["unique_nouns"] == []


class TestGenerateQuery:
    """Test generate_query step."""

    def test_generate_query_success(self, mock_nosql_workflow):
        """Test successful query generation."""
        mock_nosql_workflow.llm_manager.invoke_with_structured_output.return_value = (
            MongoQueryGenerationResponse(
                query_command='db.orders.aggregate([{$group: {_id: "$status", count: {$sum: 1}}}])',
                query_reason="Grouped orders by status",
            )
        )

        state = WorkflowState(
            question="How many orders per status?",
            parsed_question={"is_relevant": True, "relevant_tables": [{"table_name": "orders"}]},
            unique_nouns=["active", "pending"],
        )

        result = mock_nosql_workflow.generate_query(state)
        assert "aggregate" in result["sql_query"]
        assert result["sql_reason"]
        assert result["retry_count"] == 0

    def test_generate_query_not_relevant(self, mock_nosql_workflow):
        """Test query generation when question is not relevant."""
        state = WorkflowState(
            question="What's the weather?",
            parsed_question={"is_relevant": False, "relevance_reason": "Not relevant"},
        )

        result = mock_nosql_workflow.generate_query(state)
        assert result["sql_query"] == "NOT_RELEVANT"

    def test_generate_query_retry_increments_count(self, mock_nosql_workflow):
        """Test that retry increments the retry count."""
        mock_nosql_workflow.llm_manager.invoke_with_structured_output.return_value = (
            MongoQueryGenerationResponse(
                query_command='db.orders.aggregate([{$count: "total"}])',
                query_reason="Count all orders",
            )
        )

        state = WorkflowState(
            question="Count orders",
            parsed_question={"is_relevant": True, "relevant_tables": []},
            execution_error="Previous error",
            retry_count=1,
        )

        result = mock_nosql_workflow.generate_query(state)
        assert result["retry_count"] == 2

    def test_generate_query_disabled(self, mock_nosql_workflow, mock_config):
        """Test query generation when step is disabled."""
        mock_config.is_step_enabled = lambda step: step != "generate_sql"

        state = WorkflowState(question="Test")
        result = mock_nosql_workflow.generate_query(state)
        assert result["sql_query"] == ""


class TestValidateAndFixQuery:
    """Test validate_and_fix_query step."""

    def test_validate_valid_query(self, mock_nosql_workflow):
        """Test validation of a valid query."""
        mock_nosql_workflow.llm_manager.invoke_with_structured_output.return_value = (
            MongoQueryValidationResponse(
                valid=True,
                corrected_query="None",
                issues="",
            )
        )

        state = WorkflowState(
            question="Test",
            sql_query='db.orders.aggregate([{$count: "total"}])',
        )

        result = mock_nosql_workflow.validate_and_fix_query(state)
        assert result["sql_valid"] is True
        assert result["sql_issues"] == ""

    def test_validate_and_fix_invalid_query(self, mock_nosql_workflow):
        """Test validation that fixes an invalid query."""
        mock_nosql_workflow.llm_manager.invoke_with_structured_output.return_value = (
            MongoQueryValidationResponse(
                valid=False,
                corrected_query='db.orders.aggregate([{$count: "total"}])',
                issues="Fixed collection name",
            )
        )

        state = WorkflowState(
            question="Test",
            sql_query='db.order.aggregate([{$count: "total"}])',
        )

        result = mock_nosql_workflow.validate_and_fix_query(state)
        assert result["sql_valid"] is True
        assert "Fixed" in result["sql_issues"]
        assert "orders" in result["sql_query"]

    def test_validate_skips_not_relevant(self, mock_nosql_workflow):
        """Test validation skips NOT_RELEVANT queries."""
        state = WorkflowState(question="Test", sql_query="NOT_RELEVANT")
        result = mock_nosql_workflow.validate_and_fix_query(state)
        assert result["sql_valid"] is False

    def test_validate_skips_error(self, mock_nosql_workflow):
        """Test validation skips ERROR queries."""
        state = WorkflowState(question="Test", sql_query="ERROR")
        result = mock_nosql_workflow.validate_and_fix_query(state)
        assert result["sql_valid"] is False


class TestExecuteQuery:
    """Test execute_query step."""

    def test_execute_query_success(self, mock_nosql_workflow):
        """Test successful query execution."""
        mock_nosql_workflow.db_manager.execute_query.return_value = [
            {"_id": "active", "count": 42},
            {"_id": "pending", "count": 10},
        ]

        state = WorkflowState(
            question="Test",
            sql_query='db.orders.aggregate([{$group: {_id: "$status", count: {$sum: 1}}}])',
        )

        result = mock_nosql_workflow.execute_query(state)
        assert len(result["results"]) == 2
        assert result["execution_error"] is None

    def test_execute_query_error(self, mock_nosql_workflow):
        """Test query execution error handling."""
        mock_nosql_workflow.db_manager.execute_query.side_effect = Exception("Timeout")

        state = WorkflowState(
            question="Test",
            sql_query='db.orders.aggregate([{$count: "total"}])',
        )

        result = mock_nosql_workflow.execute_query(state)
        assert result["results"] == []
        assert "Timeout" in result["execution_error"]

    def test_execute_query_skips_not_relevant(self, mock_nosql_workflow):
        """Test execution skips NOT_RELEVANT queries."""
        state = WorkflowState(question="Test", sql_query="NOT_RELEVANT")
        result = mock_nosql_workflow.execute_query(state)
        assert result["results"] == []
        assert result["execution_error"] is None


class TestFormatResults:
    """Test format_results step."""

    def test_format_results_success(self, mock_nosql_workflow):
        """Test successful result formatting."""
        mock_nosql_workflow.llm_manager.invoke_with_structured_output.return_value = (
            ResultsFormattingResponse(
                answer="There are 42 active orders and 10 pending.",
                analysis="The majority of orders are active.",
            )
        )

        state = WorkflowState(
            question="How many orders per status?",
            sql_query='db.orders.aggregate([...])',
            results=[{"_id": "active", "count": 42}, {"_id": "pending", "count": 10}],
        )

        result = mock_nosql_workflow.format_results(state)
        assert "42 active" in result["answer"]

    def test_format_results_no_data(self, mock_nosql_workflow):
        """Test formatting with no results."""
        state = WorkflowState(question="Test", sql_query="db.orders.aggregate([])", results=[])
        result = mock_nosql_workflow.format_results(state)
        assert "No results" in result["answer"]

    def test_format_results_not_relevant(self, mock_nosql_workflow):
        """Test formatting for NOT_RELEVANT queries."""
        state = WorkflowState(
            question="Test",
            sql_query="NOT_RELEVANT",
            sql_reason="Question about weather",
        )
        result = mock_nosql_workflow.format_results(state)
        assert "weather" in result["answer"]


class TestGenerateFollowupQuestions:
    """Test generate_followup_questions step."""

    def test_generate_followup_success(self, mock_nosql_workflow):
        """Test successful follow-up question generation."""
        mock_nosql_workflow.llm_manager.invoke_with_structured_output.return_value = (
            FollowupQuestionsResponse(
                followup_questions=[
                    "What is the trend over time?",
                    "Which category has the most orders?",
                ]
            )
        )

        state = WorkflowState(
            question="How many orders per status?",
            answer="There are 42 active orders.",
            sql_query="db.orders.aggregate([...])",
            results=[{"_id": "active", "count": 42}],
        )

        result = mock_nosql_workflow.generate_followup_questions(state)
        assert len(result["followup_questions"]) == 2

    def test_generate_followup_no_results(self, mock_nosql_workflow):
        """Test follow-up generation with no results."""
        state = WorkflowState(question="Test", answer="", results=[])
        result = mock_nosql_workflow.generate_followup_questions(state)
        assert result["followup_questions"] == []


class TestChooseAndFormatVisualization:
    """Test choose_and_format_visualization step."""

    def test_visualization_success(self, mock_nosql_workflow):
        """Test successful visualization choice and formatting."""
        mock_chart_data = Mock()
        mock_nosql_workflow.llm_manager.invoke_with_structured_output.return_value = Mock(
            visualization="bar",
            visualization_reason="Categorical comparison",
            universal_format=mock_chart_data,
        )

        state = WorkflowState(
            question="Orders by status",
            sql_query="db.orders.aggregate([...])",
            results=[{"_id": "active", "count": 42}, {"_id": "pending", "count": 10}],
        )

        result = mock_nosql_workflow.choose_and_format_visualization(state)
        assert result["visualization"] == "bar"
        assert result["chart_data"] is not None

    def test_visualization_no_data(self, mock_nosql_workflow):
        """Test visualization with no data."""
        state = WorkflowState(question="Test", sql_query="db.test.aggregate([])", results=[])
        result = mock_nosql_workflow.choose_and_format_visualization(state)
        assert result["visualization"] == "none"


# =============================================================================
# WORKFLOW ROUTING TESTS
# =============================================================================


class TestWorkflowRouting:
    """Test workflow routing and conditional edges."""

    def test_should_continue_workflow_normal(self, mock_nosql_workflow):
        """Test workflow continues normally."""
        state = WorkflowState(question="Test", needs_clarification=False)
        result = mock_nosql_workflow._should_continue_workflow(state)
        assert result == "continue"

    def test_should_continue_workflow_needs_clarification(self, mock_nosql_workflow):
        """Test workflow stops for clarification."""
        state = WorkflowState(question="Test", needs_clarification=True)
        result = mock_nosql_workflow._should_continue_workflow(state)
        assert result == "__end__"

    def test_should_continue_not_relevant_continues(self, mock_nosql_workflow):
        """Test workflow continues for not-relevant questions (to provide explanation)."""
        state = WorkflowState(
            question="Test",
            needs_clarification=True,
            parsed_question={"is_relevant": False},
        )
        result = mock_nosql_workflow._should_continue_workflow(state)
        assert result == "continue"

    def test_should_retry_on_error(self, mock_nosql_workflow):
        """Test retry routing on execution error."""
        state = WorkflowState(
            question="Test",
            execution_error="Syntax error",
            retry_count=0,
        )
        result = mock_nosql_workflow._should_retry_query_generation(state)
        assert result == "generate_sql"

    def test_should_not_retry_max_reached(self, mock_nosql_workflow):
        """Test no retry when max retries reached."""
        state = WorkflowState(
            question="Test",
            execution_error="Syntax error",
            retry_count=3,
        )
        result = mock_nosql_workflow._should_retry_query_generation(state)
        assert result == "__end__"

    def test_should_continue_after_success(self, mock_nosql_workflow):
        """Test continue routing after successful execution."""
        state = WorkflowState(
            question="Test",
            execution_error=None,
            retry_count=0,
        )
        result = mock_nosql_workflow._should_retry_query_generation(state)
        assert result == "continue"

    def test_should_end_on_clarification(self, mock_nosql_workflow):
        """Test end routing when clarification needed."""
        state = WorkflowState(
            question="Test",
            needs_clarification=True,
        )
        result = mock_nosql_workflow._should_retry_query_generation(state)
        assert result == "__end__"


# =============================================================================
# COT AND PROGRESS TESTS
# =============================================================================


class TestCotAndProgress:
    """Test Chain-of-Thoughts and progress tracking."""

    def test_register_cot_listener(self, mock_nosql_workflow):
        """Test registering a CoT listener."""
        listener = Mock()
        mock_nosql_workflow.register_cot_listener(listener)
        assert listener in mock_nosql_workflow._cot_listeners

    def test_unregister_cot_listener(self, mock_nosql_workflow):
        """Test unregistering a CoT listener."""
        listener = Mock()
        mock_nosql_workflow.register_cot_listener(listener)
        mock_nosql_workflow.unregister_cot_listener(listener)
        assert listener not in mock_nosql_workflow._cot_listeners

    def test_clear_cot_listeners(self, mock_nosql_workflow):
        """Test clearing all CoT listeners."""
        mock_nosql_workflow.register_cot_listener(Mock())
        mock_nosql_workflow.register_cot_listener(Mock())
        mock_nosql_workflow.clear_cot_listeners()
        assert len(mock_nosql_workflow._cot_listeners) == 0

    def test_clear_schema_cache(self, mock_nosql_workflow):
        """Test clearing the schema cache."""
        mock_nosql_workflow._workflow_schema_cache = "cached schema"
        mock_nosql_workflow.clear_schema_cache()
        assert mock_nosql_workflow._workflow_schema_cache is None

    def test_get_graph(self, mock_nosql_workflow):
        """Test getting the compiled graph."""
        graph = mock_nosql_workflow.get_graph()
        assert graph is not None


# =============================================================================
# PII DETECTION STEP TESTS
# =============================================================================


class TestPIIDetection:
    """Test PII detection step in NoSQL workflow."""

    def test_pii_detection_disabled(self, mock_nosql_workflow):
        """Test PII detection when detector is None."""
        mock_nosql_workflow.pii_detector = None
        state = WorkflowState(question="Show me John Doe's orders")
        result = mock_nosql_workflow.pii_detection_step(state)
        assert result == {}

    def test_pii_detection_no_pii(self, mock_nosql_workflow):
        """Test PII detection when no PII found."""
        mock_detector = Mock()
        mock_result = Mock()
        mock_result.has_pii = False
        mock_detector.detect_pii_in_text.return_value = mock_result
        mock_nosql_workflow.pii_detector = mock_detector

        state = WorkflowState(question="How many orders per month?")
        result = mock_nosql_workflow.pii_detection_step(state)
        assert result == {}

    def test_pii_detection_blocked(self, mock_nosql_workflow):
        """Test PII detection when PII is found and blocked."""
        mock_detector = Mock()
        mock_result = Mock()
        mock_result.has_pii = True
        mock_result.blocked = True
        mock_result.entity_types = ["PERSON", "EMAIL_ADDRESS"]
        mock_detector.detect_pii_in_text.return_value = mock_result
        mock_nosql_workflow.pii_detector = mock_detector

        state = WorkflowState(question="Show orders for john@example.com")
        result = mock_nosql_workflow.pii_detection_step(state)
        assert result.get("needs_clarification") is True


# =============================================================================
# CONVERSATION CONTEXT TESTS
# =============================================================================


class TestConversationContext:
    """Test conversation context summarization."""

    def test_summarize_empty_messages(self, mock_nosql_workflow):
        """Test summarization with single message."""
        result = mock_nosql_workflow._summarize_conversation_context(
            [{"role": "user", "content": "Hello"}]
        )
        assert result == ""

    def test_summarize_with_context(self, mock_nosql_workflow):
        """Test summarization with conversation history."""
        messages = [
            {"role": "user", "content": "How many orders?"},
            {"role": "assistant", "content": "There are 100 orders."},
            {"role": "user", "content": "Break down by status"},
        ]
        result = mock_nosql_workflow._summarize_conversation_context(messages)
        assert "Conversation context" in result
