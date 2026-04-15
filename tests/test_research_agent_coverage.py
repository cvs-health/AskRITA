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

"""Tests for ResearchAgent targeting previously uncovered code paths."""

from unittest.mock import MagicMock

from askrita.research.ResearchAgent import ResearchAgent, ResearchWorkflowState

# ---------------------------------------------------------------------------
# Helper: create a bare ResearchAgent (bypasses __init__)
# ---------------------------------------------------------------------------


def _bare_agent():
    """Return a ResearchAgent instance bypassing __init__."""
    agent = ResearchAgent.__new__(ResearchAgent)
    agent.sql_agent = MagicMock()
    agent.stats_analyzer = MagicMock()
    agent._research_max_results = 50_000
    return agent


def _make_state(**kwargs):
    defaults = {
        "research_question": "Does A affect B?",
        "hypothesis": "A increases B",
        "success_criteria": "p < 0.05",
        "relevant_columns": [],
        "data_limitations": [],
        "errors": [],
        "collected_data": {},
        "sample_sizes": {},
        "statistical_findings": [],
        "key_metrics": {},
        "conclusion": "",
        "confidence": 0,
        "evidence_queries": [],
    }
    defaults.update(kwargs)
    return ResearchWorkflowState(**defaults)


# ---------------------------------------------------------------------------
# _detect_column_remapping – empty input (line 432)
# ---------------------------------------------------------------------------


class TestDetectColumnRemapping:
    def test_empty_raw_rows_returns_false_zero(self):
        """Line 432: empty list → (False, 0)."""
        result = ResearchAgent._detect_column_remapping([])
        assert result == (False, 0)

    def test_list_row_triggers_remapping(self):
        """Tuple row → (True, n)."""
        result = ResearchAgent._detect_column_remapping([[1, 2, 3]])
        assert result == (True, 3)

    def test_dict_with_col_prefix_triggers_remapping(self):
        """Dict row with col_ keys → (True, n)."""
        result = ResearchAgent._detect_column_remapping([{"col_0": 1, "col_1": 2}])
        assert result == (True, 2)

    def test_dict_with_named_keys_no_remapping(self):
        """Dict row with real column names → (False, 0)."""
        result = ResearchAgent._detect_column_remapping([{"name": "Alice", "age": 30}])
        assert result == (False, 0)


# ---------------------------------------------------------------------------
# _remap_raw_rows – non-dict/non-list row (line 461)
# ---------------------------------------------------------------------------


class TestRemapRawRows:
    def test_scalar_row_wrapped_in_value_dict(self):
        """Line 461: scalar (str/int) rows are wrapped as {'value': row}."""
        agent = _bare_agent()
        result = agent._remap_raw_rows(["hello", "world"], None)
        assert result == [{"value": "hello"}, {"value": "world"}]

    def test_tuple_row_remapped_with_column_names(self):
        """Tuple rows are remapped to named dicts when column_names provided."""
        agent = _bare_agent()
        result = agent._remap_raw_rows([(1, "Alice"), (2, "Bob")], ["id", "name"])
        assert result == [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

    def test_tuple_row_fallback_col_prefix_when_no_names(self):
        """Tuple rows use col_N keys when column_names is None."""
        agent = _bare_agent()
        result = agent._remap_raw_rows([(1, "Alice")], None)
        assert result == [{"col_0": 1, "col_1": "Alice"}]

    def test_dict_row_with_col_prefix_remapped(self):
        """Dict rows with col_ prefix are remapped to named dicts."""
        agent = _bare_agent()
        result = agent._remap_raw_rows(
            [{"col_0": "admin", "col_1": 42}],
            column_names=["role", "score"],
        )
        assert result == [{"role": "admin", "score": 42}]


# ---------------------------------------------------------------------------
# _execute_query – no SQL path (lines 478-480) and exception (lines 496-499)
# ---------------------------------------------------------------------------


class TestExecuteQuery:
    def test_empty_sql_stores_error_entry(self):
        """Lines 478-480: no SQL in sql_map → error entry, sample_size 0."""
        agent = _bare_agent()
        collected: dict = {}
        sample_sizes: dict = {}

        agent._execute_query(0, ["what is average?"], {}, collected, sample_sizes)

        assert "query_1" in collected
        assert "error" in collected["query_1"]
        assert sample_sizes["query_1"] == 0

    def test_execute_query_exception_stored(self):
        """Lines 496-499: exception in execute_query stored as error entry."""
        agent = _bare_agent()
        agent.sql_agent.db_manager.execute_query.side_effect = RuntimeError("db error")

        collected: dict = {}
        sample_sizes: dict = {}
        sql_map = {0: "SELECT a, b FROM t"}

        agent._execute_query(0, ["my question"], sql_map, collected, sample_sizes)

        assert "error" in collected["query_1"]
        assert sample_sizes["query_1"] == 0

    def test_execute_query_success(self):
        """Happy path: result stored with correct structure."""
        agent = _bare_agent()
        agent.sql_agent.db_manager.execute_query.return_value = [
            {"group": "A", "score": 10},
            {"group": "B", "score": 20},
        ]

        collected: dict = {}
        sample_sizes: dict = {}
        sql_map = {0: "SELECT group, score FROM t"}

        agent._execute_query(
            0, ["Show group and score"], sql_map, collected, sample_sizes
        )

        assert "data" in collected["query_1"]
        assert sample_sizes["query_1"] == 2


# ---------------------------------------------------------------------------
# _data_preparation – no queries case (line 510)
# ---------------------------------------------------------------------------


class TestDataPreparation:
    def test_returns_next_phase_when_no_queries(self):
        """Line 510: empty evidence_queries skips to MODELING phase."""
        agent = _bare_agent()
        state = _make_state(evidence_queries=[])

        result = agent._data_preparation(state)
        assert result["current_phase"] == "modeling"


# ---------------------------------------------------------------------------
# _populate_best_test_metrics – bonferroni path (lines 599-602)
# ---------------------------------------------------------------------------


class TestPopulateBestTestMetrics:
    def _make_test_result(self, p_value=0.01, effect_size=0.5, bonferroni_p=None):
        tr = MagicMock()
        tr.test_name = "t-test"
        tr.test_statistic = 3.14
        tr.p_value = p_value
        tr.is_significant = True
        tr.effect_size = effect_size
        tr.effect_size_interpretation = "medium"
        tr.group_means = {"A": 10.0, "B": 12.0}
        info = {}
        if bonferroni_p is not None:
            info["bonferroni_p"] = bonferroni_p
            info["bonferroni_significant"] = bonferroni_p < 0.05
            info["n_tests_corrected_for"] = 3
        tr.additional_info = info
        return tr

    def test_bonferroni_fields_added_to_metrics(self):
        """Lines 599-602: bonferroni_p in additional_info is stored in computed_metrics."""
        best_test = self._make_test_result(bonferroni_p=0.02)
        computed_metrics: dict = {}

        ResearchAgent._populate_best_test_metrics(
            best_test, computed_metrics, n_tests=3
        )

        assert "bonferroni_p" in computed_metrics
        assert computed_metrics["bonferroni_p"] == 0.02
        assert computed_metrics["bonferroni_significant"] is True

    def test_no_bonferroni_when_absent(self):
        """bonferroni_p NOT added when not in additional_info."""
        best_test = self._make_test_result()  # no bonferroni
        computed_metrics: dict = {}

        ResearchAgent._populate_best_test_metrics(
            best_test, computed_metrics, n_tests=1
        )

        assert "bonferroni_p" not in computed_metrics


# ---------------------------------------------------------------------------
# _modeling – no data case (lines 610-619)
# ---------------------------------------------------------------------------


class TestModeling:
    def test_no_collected_data_returns_no_data_state(self):
        """Lines 610-619: empty collected_data returns 'No data' findings."""
        agent = _bare_agent()
        state = _make_state(collected_data={})

        result = agent._modeling(state)

        assert "statistical_findings" in result
        assert any("No data" in f for f in result["statistical_findings"])
        assert "errors" in result


# ---------------------------------------------------------------------------
# _get_structured_schema_summary – exception fallback (lines 935-937)
# ---------------------------------------------------------------------------


class TestGetStructuredSchemaSummary:
    def test_returns_fallback_string_on_exception(self):
        """Lines 935-937: exception in analyze_schema returns generic fallback string."""
        agent = _bare_agent()
        agent.analyze_schema = MagicMock(side_effect=RuntimeError("schema failed"))

        result = agent._get_structured_schema_summary()

        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# _business_understanding – LLM success and error paths (lines 307-338)
# ---------------------------------------------------------------------------


class TestBusinessUnderstanding:
    def test_returns_refined_hypothesis_on_success(self):
        """Lines 307-335: returns structured output on successful LLM call."""
        agent = _bare_agent()
        llm_result = MagicMock()
        llm_result.refined_hypothesis = "Refined: A increases B by 20%"
        llm_result.success_criteria = "p < 0.05"
        llm_result.key_variables = ["column_a", "column_b"]
        agent.sql_agent.llm_manager.invoke_with_structured_output_direct.return_value = (
            llm_result
        )

        state = _make_state()
        result = agent._business_understanding(state)

        assert result["hypothesis"] == "Refined: A increases B by 20%"
        assert result["relevant_columns"] == ["column_a", "column_b"]

    def test_returns_errors_on_llm_failure(self):
        """Lines 336-338: returns error entry when LLM call raises."""
        agent = _bare_agent()
        agent.sql_agent.llm_manager.invoke_with_structured_output_direct.side_effect = (
            RuntimeError("LLM unavailable")
        )

        state = _make_state()
        result = agent._business_understanding(state)

        assert "errors" in result
        assert len(result["errors"]) > 0


# ---------------------------------------------------------------------------
# _data_understanding – LLM success and error paths (lines 347-422)
# ---------------------------------------------------------------------------


class TestDataUnderstanding:
    def test_returns_evidence_queries_on_success(self):
        """Lines 402-416: returns evidence_queries when LLM succeeds."""
        agent = _bare_agent()
        agent.analyze_schema = MagicMock(side_effect=RuntimeError("skip"))
        llm_result = MagicMock()
        llm_result.relevant_columns = ["col_a", "col_b"]
        llm_result.data_quality_notes = "Good data"
        llm_result.limitations = ["Small sample"]
        llm_result.recommended_queries = ["Show col_a and col_b"]
        agent.sql_agent.llm_manager.invoke_with_structured_output_direct.return_value = (
            llm_result
        )

        state = _make_state()
        result = agent._data_understanding(state)

        assert "evidence_queries" in result
        assert result["evidence_queries"] == ["Show col_a and col_b"]

    def test_returns_empty_queries_on_llm_failure(self):
        """Lines 417-422: returns empty evidence_queries when LLM raises."""
        agent = _bare_agent()
        agent.analyze_schema = MagicMock(side_effect=RuntimeError("skip"))
        agent.sql_agent.llm_manager.invoke_with_structured_output_direct.side_effect = (
            RuntimeError("LLM failed")
        )

        state = _make_state()
        result = agent._data_understanding(state)

        assert result["evidence_queries"] == []
        assert len(result["errors"]) > 0


# ---------------------------------------------------------------------------
# _deployment – error path (lines 823-835)
# ---------------------------------------------------------------------------


class TestDeployment:
    def test_returns_defaults_on_llm_failure(self):
        """Lines 823-835: returns default insights/recommendations when LLM fails."""
        agent = _bare_agent()
        agent.sql_agent.llm_manager.invoke_with_structured_output_direct.side_effect = (
            RuntimeError("LLM down")
        )

        state = _make_state(
            conclusion="INCONCLUSIVE",
            confidence=0,
            statistical_findings=["No significant difference found"],
            data_limitations=["Small sample size"],
        )
        result = agent._deployment(state)

        assert "insights" in result
        assert "recommendations" in result
        assert "next_steps" in result
        assert "errors" in result

    def test_returns_structured_output_on_success(self):
        """Lines 809-822: returns structured insights when LLM succeeds."""
        agent = _bare_agent()
        llm_result = MagicMock()
        llm_result.insights = ["Key insight"]
        llm_result.recommendations = ["Do X"]
        llm_result.next_steps = ["Collect more data"]
        agent.sql_agent.llm_manager.invoke_with_structured_output_direct.return_value = (
            llm_result
        )

        state = _make_state(
            conclusion="SUPPORTED",
            confidence=85,
            statistical_findings=["p < 0.05"],
            data_limitations=[],
        )
        result = agent._deployment(state)

        assert result["insights"] == ["Key insight"]
        assert result["recommendations"] == ["Do X"]


# ---------------------------------------------------------------------------
# _compute_evaluation_confidence – all branches (lines 770-780)
# ---------------------------------------------------------------------------


class TestComputeEvaluationConfidence:
    def _call(
        self,
        agent,
        p_value,
        is_significant,
        bonferroni_sig=None,
        bonferroni_p=None,
        effect_size=None,
        fallback=50,
    ):
        return agent._compute_evaluation_confidence(
            p_value, is_significant, bonferroni_sig, bonferroni_p, effect_size, fallback
        )

    def test_returns_fallback_when_p_value_none(self):
        """Line 770-771: returns fallback when p_value is None."""
        agent = _bare_agent()
        assert self._call(agent, None, True, fallback=42) == 42

    def test_returns_fallback_when_is_significant_none(self):
        """Line 770-771: returns fallback when is_significant is None."""
        agent = _bare_agent()
        assert self._call(agent, 0.01, None, fallback=33) == 33

    def test_returns_90_when_significant_with_large_effect(self):
        """Lines 774-775: returns 90 when significant and |effect_size| > 0.5."""
        agent = _bare_agent()
        result = self._call(agent, 0.01, True, effect_size=0.8)
        assert result == 90

    def test_returns_75_when_significant_without_effect(self):
        """Lines 776-777: returns 75 when significant but no large effect."""
        agent = _bare_agent()
        result = self._call(agent, 0.01, True, effect_size=0.2)
        assert result == 75

    def test_returns_50_when_p_lt_0_1_but_not_significant(self):
        """Lines 778-779: returns 50 when p < 0.1 but not significant."""
        agent = _bare_agent()
        result = self._call(agent, 0.05, False)
        assert result == 50

    def test_returns_30_when_p_gte_0_1(self):
        """Line 780: returns 30 when not significant and p >= 0.1."""
        agent = _bare_agent()
        result = self._call(agent, 0.5, False)
        assert result == 30

    def test_uses_bonferroni_when_provided(self):
        """Line 772-773: uses bonferroni_sig/bonferroni_p when provided."""
        agent = _bare_agent()
        # Standard: not significant (p=0.5). But bonferroni says significant with large effect.
        result = self._call(
            agent, 0.5, False, bonferroni_sig=True, bonferroni_p=0.01, effect_size=0.9
        )
        assert result == 90


# ---------------------------------------------------------------------------
# _get_structured_schema_summary – success path (lines 912-934)
# ---------------------------------------------------------------------------


class TestGetStructuredSchemaSummarySuccess:
    def test_success_path_returns_formatted_text(self):
        """Lines 912-934: success path returns formatted schema description."""
        from unittest.mock import MagicMock

        agent = _bare_agent()

        # Build a mock SchemaAnalysisReport
        mock_col = MagicMock()
        mock_col.data_type = "INTEGER"
        mock_col.statistical_type = "continuous"
        mock_col.description = "A numeric column"

        mock_table = MagicMock()
        mock_table.full_name = "orders"
        mock_table.description = "Order data"
        mock_table.columns = {"order_id": mock_col}

        mock_analysis = MagicMock()
        mock_analysis.database_type = "PostgreSQL"
        mock_analysis.total_tables = 1
        mock_analysis.total_columns = 1
        mock_analysis.tables = {"orders": mock_table}

        agent.analyze_schema = MagicMock(return_value=mock_analysis)

        result = agent._get_structured_schema_summary()

        assert "PostgreSQL" in result
        assert "orders" in result
        assert "order_id" in result
        assert "A numeric column" in result


# ---------------------------------------------------------------------------
# Public API methods: test_hypothesis, test_assumption, query, schema,
# analyze_schema (lines 956-1019)
# ---------------------------------------------------------------------------


class TestPublicAPI:
    def test_test_hypothesis_invokes_workflow(self):
        """Lines 956-989: test_hypothesis calls workflow.invoke and returns structured dict."""
        agent = _bare_agent()
        mock_final = {
            "research_question": "Does A affect B?",
            "hypothesis": "A increases B",
            "success_criteria": "p < 0.05",
            "data_quality_assessment": "Good",
            "relevant_columns": ["a", "b"],
            "data_limitations": [],
            "statistical_findings": ["p < 0.05"],
            "key_metrics": {"p_value": 0.03},
            "stats_trace": [],
            "conclusion": "SUPPORTED",
            "confidence": 85,
            "validity_assessment": "Valid",
            "insights": ["A causes B"],
            "recommendations": ["Use A"],
            "next_steps": ["Monitor"],
            "collected_data": {"q1": {}},
            "errors": [],
            "timestamp": "2024-01-01T00:00:00",
        }
        agent.workflow = MagicMock()
        agent.workflow.invoke.return_value = mock_final

        result = agent.test_hypothesis("Does A affect B?", "A increases B")

        assert result["conclusion"] == "SUPPORTED"
        assert result["confidence"] == 85
        assert result["queries_executed"] == 1

    def test_test_assumption_delegates_to_test_hypothesis(self):
        """Line 996: test_assumption calls test_hypothesis."""
        agent = _bare_agent()
        agent.test_hypothesis = MagicMock(return_value={"conclusion": "SUPPORTED"})

        result = agent.test_assumption("My assumption", ["Show data"])

        agent.test_hypothesis.assert_called_once()
        assert result == {"conclusion": "SUPPORTED"}

    def test_query_returns_structured_result(self):
        """Lines 999-1008: query returns question, sql, answer, data."""
        agent = _bare_agent()
        mock_gen = MagicMock()
        mock_gen.sql_query = "SELECT * FROM t"
        mock_gen.answer = "42 rows"
        agent.sql_agent.query.return_value = mock_gen
        agent.sql_agent.db_manager.execute_query.return_value = [{"id": 1}]

        result = agent.query("How many rows?")

        assert result["question"] == "How many rows?"
        assert result["sql"] == "SELECT * FROM t"
        assert result["data"] == [{"id": 1}]

    def test_query_handles_empty_sql(self):
        """Lines 999-1008: query returns empty data when SQL is empty."""
        agent = _bare_agent()
        mock_gen = MagicMock()
        mock_gen.sql_query = ""
        mock_gen.answer = "No result"
        agent.sql_agent.query.return_value = mock_gen

        result = agent.query("empty?")

        assert result["data"] == []
        assert result["sql"] == ""

    def test_schema_property_delegates_to_sql_agent(self):
        """Line 1013: schema property returns sql_agent.schema."""
        agent = _bare_agent()
        agent.sql_agent.schema = "CREATE TABLE t (id INT)"

        assert agent.schema == "CREATE TABLE t (id INT)"

    def test_analyze_schema_caches_result(self):
        """Lines 1017-1019: analyze_schema caches result on second call."""
        agent = _bare_agent()
        agent._schema_analysis = None
        mock_report = MagicMock()
        agent.schema_analyzer = MagicMock()
        agent.schema_analyzer.analyze_schema.return_value = mock_report

        # First call should invoke analyzer
        result1 = agent.analyze_schema()
        assert result1 is mock_report
        agent.schema_analyzer.analyze_schema.assert_called_once()

        # Second call should use cached value
        result2 = agent.analyze_schema()
        assert result2 is mock_report
        agent.schema_analyzer.analyze_schema.assert_called_once()  # still once

    def test_analyze_schema_returns_cached_when_set(self):
        """analyze_schema returns existing cache without calling analyzer."""
        agent = _bare_agent()
        mock_cached = MagicMock()
        agent._schema_analysis = mock_cached
        agent.schema_analyzer = MagicMock()

        result = agent.analyze_schema()
        assert result is mock_cached
        agent.schema_analyzer.analyze_schema.assert_not_called()


# ---------------------------------------------------------------------------
# _modeling with actual (mocked) data (lines 621-681)
# ---------------------------------------------------------------------------


class TestModelingWithData:
    def test_modeling_with_mocked_stats(self):
        """Lines 621-681: _modeling with collected data calls stats_analyzer."""
        agent = _bare_agent()

        # Build mock stats results
        mock_desc = MagicMock()
        mock_desc.variable = "score"
        mock_desc.mean = 10.5
        mock_desc.std = 2.3
        mock_desc.count = 100
        mock_desc.to_prompt_text.return_value = "mean=10.5"

        mock_test = MagicMock()
        mock_test.test_name = "t-test"
        mock_test.p_value = 0.03
        mock_test.is_significant = True
        mock_test.to_prompt_text.return_value = "p=0.03"
        mock_test.sample_sizes = {"A": 50, "B": 50}
        mock_test.effect_size = 0.6
        mock_test.effect_size_interpretation = "medium"
        mock_test.group_means = {"A": 10.0, "B": 12.0}
        mock_test.additional_info = {}

        agent.stats_analyzer.analyze_hypothesis_data.return_value = {
            "descriptive_stats": [mock_desc],
            "statistical_tests": [mock_test],
            "trace": [],
        }

        state = _make_state(
            collected_data={"query_1": {"question": "test", "data": [{"a": 1}]}},
            hypothesis="A increases B",
        )

        result = agent._modeling(state)

        assert "statistical_findings" in result
        assert "key_metrics" in result
        assert result["current_phase"] == "evaluation"
