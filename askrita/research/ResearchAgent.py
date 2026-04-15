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
#   langgraph (MIT)
#   pydantic (MIT)

"""
Research Agent - CRISP-DM LangGraph Workflow for Data Science Research.

Implements the Cross-Industry Standard Process for Data Mining:
1. Business Understanding - Define research questions and objectives
2. Data Understanding - Schema analysis, data quality assessment
3. Data Preparation - Collect evidence via SQL Agent
4. Modeling - Statistical analysis and hypothesis testing
5. Evaluation - Assess findings and confidence
6. Deployment - Generate actionable recommendations

Uses SQL Agent for data queries, LLM for analysis with structured output.
"""

import concurrent.futures
import logging
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from ..config_manager import ConfigManager
from ..sqlagent.workflows.SQLAgentWorkflow import SQLAgentWorkflow
from .SchemaAnalyzer import SchemaAnalysisReport, SchemaAnalyzer
from .StatisticalAnalyzer import StatisticalAnalyzer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Phase-state dict keys (used 3+ times — defined once to avoid duplication)
# ---------------------------------------------------------------------------
_CURRENT_PHASE = "current_phase"
_ERRORS = "errors"
_BONFERRONI_P = "bonferroni_p"
_BONFERRONI_SIGNIFICANT = "bonferroni_significant"
_KEY_METRICS = "key_metrics"
_STATISTICAL_FINDINGS = "statistical_findings"
_DATA_LIMITATIONS = "data_limitations"
_RELEVANT_COLUMNS = "relevant_columns"
_CONFIDENCE = "confidence"
_CONCLUSION = "conclusion"
_INSIGHTS = "insights"
_RECOMMENDATIONS = "recommendations"
_NEXT_STEPS = "next_steps"
_VALIDITY_ASSESSMENT = "validity_assessment"
_TIMESTAMP = "timestamp"
_STATS_TRACE = "stats_trace"
_P_VALUE = "p_value"
_EFFECT_SIZE = "effect_size"
_VALUE_COLUMN = "value_column"
_GROUP_COLUMN = "group_column"
_QUESTION = "question"
_ANSWER = "answer"
_HYPOTHESIS = "hypothesis"
_SUCCESS_CRITERIA = "success_criteria"

# CRISP-DM phase names
_PHASE_BUSINESS_UNDERSTANDING = "business_understanding"
_PHASE_DATA_UNDERSTANDING = "data_understanding"
_PHASE_DATA_PREPARATION = "data_preparation"
_PHASE_MODELING = "modeling"
_PHASE_EVALUATION = "evaluation"
_PHASE_DEPLOYMENT = "deployment"

# Not-computed sentinel
_NOT_COMPUTED = "Not computed"

# Column-name prefix used when DB returns positional columns
_COL_PREFIX = "col_"


# =============================================================================
# WORKFLOW STATE
# =============================================================================


class ResearchWorkflowState(BaseModel):
    """State for research workflow."""

    # Phase 1: Business Understanding
    research_question: str = ""
    hypothesis: str = ""
    success_criteria: str = ""

    # Phase 2: Data Understanding
    schema_summary: str = ""
    data_quality_assessment: str = ""
    relevant_columns: List[str] = Field(default_factory=list)
    data_limitations: List[str] = Field(default_factory=list)

    # Phase 3: Data Preparation
    evidence_queries: List[str] = Field(default_factory=list)
    current_query_index: int = 0
    collected_data: Dict[str, Any] = Field(default_factory=dict)
    sample_sizes: Dict[str, int] = Field(default_factory=dict)

    # Phase 4: Modeling/Analysis (COMPUTED, not LLM-generated)
    statistical_findings: List[str] = Field(default_factory=list)
    key_metrics: Dict[str, Any] = Field(default_factory=dict)
    computed_stats_text: str = ""  # Text representation of computed statistics
    stats_trace: List[Dict[str, Any]] = Field(default_factory=list)

    # Phase 5: Evaluation
    conclusion: str = ""
    confidence: int = 0
    validity_assessment: str = ""

    # Phase 6: Deployment
    insights: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)

    # Metadata
    current_phase: str = _PHASE_BUSINESS_UNDERSTANDING
    errors: List[str] = Field(default_factory=list)
    timestamp: str = ""

    model_config = ConfigDict(arbitrary_types_allowed=True)


# =============================================================================
# STRUCTURED OUTPUT MODELS
# =============================================================================


class BusinessUnderstandingOutput(BaseModel):
    """Output from business understanding phase."""

    refined_hypothesis: str = Field(description="Clear, testable hypothesis statement")
    success_criteria: str = Field(
        description="What would confirm or refute this hypothesis"
    )
    key_variables: List[str] = Field(description="Variables to analyze")


class DataUnderstandingOutput(BaseModel):
    """Output from data understanding phase."""

    relevant_columns: List[str] = Field(
        description="Columns relevant to the hypothesis"
    )
    data_quality_notes: str = Field(description="Assessment of data quality")
    limitations: List[str] = Field(description="Known limitations of the data")
    recommended_queries: List[str] = Field(
        description="Plain-English data questions to gather evidence (NOT SQL)"
    )


class ModelingOutput(BaseModel):
    """Output from modeling/analysis phase."""

    statistical_findings: List[str] = Field(
        description="Key statistical findings from the data"
    )
    key_metrics: Dict[str, Any] = Field(
        default_factory=dict, description="Important metrics extracted"
    )
    patterns_identified: List[str] = Field(
        default_factory=list, description="Patterns or trends in the data"
    )


class EvaluationOutput(BaseModel):
    """Output from evaluation phase."""

    conclusion: Literal["SUPPORTED", "REFUTED", "INCONCLUSIVE"] = Field(
        description="Whether hypothesis is supported by evidence"
    )
    confidence: int = Field(ge=0, le=100, description="Confidence level 0-100%")
    validity_assessment: str = Field(description="Assessment of conclusion validity")
    caveats: List[str] = Field(description="Important caveats or limitations")


class DeploymentOutput(BaseModel):
    """Output from deployment phase."""

    executive_summary: str = Field(description="2-3 sentence summary for executives")
    insights: List[str] = Field(description="Key business insights")
    recommendations: List[str] = Field(description="Actionable recommendations")
    next_steps: List[str] = Field(description="Suggested follow-up research")


# =============================================================================
# RESEARCH AGENT - CRISP-DM WORKFLOW
# =============================================================================


class ResearchAgent:
    """
    CRISP-DM Research Agent with LangGraph workflow.

    Implements complete data science research methodology:
    - Business Understanding → Data Understanding → Data Preparation
    - Modeling → Evaluation → Deployment

    Uses SQL Agent for data, LLM for analysis.
    """

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        research_max_results: int = 50_000,
        **kwargs,
    ):
        """Initialize Research Agent.

        Args:
            config_manager: Optional shared ConfigManager. Note: ``max_results``
                is overridden to ``research_max_results`` so evidence queries
                fetch enough rows for statistically valid tests.
            research_max_results: Maximum rows fetched per evidence SQL query.
                Defaults to 50,000. Lower this for faster iteration during
                development; raise it if your dataset demands more rows.
            **kwargs: Forwarded to SQLAgentWorkflow.
        """
        self.config = config_manager or ConfigManager()
        # Raise the DB result cap for research: statistics need enough raw rows.
        # Standard SQL Agent queries use max_results=1000 for token efficiency,
        # but statistical tests require full-population or large-sample data.
        self._research_max_results = research_max_results
        self.config.database.max_results = research_max_results
        logger.info(f"Research mode: database.max_results set to {research_max_results:,}")

        # Disable SQL Agent steps not needed for research.
        # execute_sql is disabled so the SQL Agent only generates and validates SQL;
        # the Research Agent executes the resulting SQL directly via db_manager so
        # evidence queries can run in parallel without sharing SQLAgentWorkflow state.
        self.config.workflow.steps["execute_sql"] = False
        self.config.workflow.steps["format_results"] = False
        self.config.workflow.steps["get_unique_nouns"] = False
        self.config.workflow.steps["generate_followup_questions"] = False
        self.config.workflow.steps["format_data_for_visualization"] = False
        self.config.workflow.steps["choose_visualization"] = False
        self.config.workflow.steps["choose_and_format_visualization"] = False

        # Initialize SQL workflow
        self.sql_agent = SQLAgentWorkflow(config_manager=self.config, **kwargs)

        # Schema analyzer
        self.schema_analyzer = SchemaAnalyzer(self.sql_agent)
        self._schema_analysis: Optional[SchemaAnalysisReport] = None

        # Statistical analyzer - for REAL computation
        self.stats_analyzer = StatisticalAnalyzer()

        # Build CRISP-DM workflow
        self.workflow = self._build_crispdm_workflow()

        logger.info("🔬 CRISP-DM Research Agent initialized")

    def _build_crispdm_workflow(self) -> StateGraph:
        """Build the CRISP-DM LangGraph workflow."""

        workflow = StateGraph(ResearchWorkflowState)

        # Add CRISP-DM phase nodes
        workflow.add_node(_PHASE_BUSINESS_UNDERSTANDING, self._business_understanding)
        workflow.add_node(_PHASE_DATA_UNDERSTANDING, self._data_understanding)
        workflow.add_node(_PHASE_DATA_PREPARATION, self._data_preparation)
        workflow.add_node(_PHASE_MODELING, self._modeling)
        workflow.add_node(_PHASE_EVALUATION, self._evaluation)
        workflow.add_node(_PHASE_DEPLOYMENT, self._deployment)

        # Set entry point
        workflow.set_entry_point(_PHASE_BUSINESS_UNDERSTANDING)

        # Linear flow through phases
        workflow.add_edge(_PHASE_BUSINESS_UNDERSTANDING, _PHASE_DATA_UNDERSTANDING)
        workflow.add_edge(_PHASE_DATA_UNDERSTANDING, _PHASE_DATA_PREPARATION)

        # Data preparation runs all queries in one parallel pass
        workflow.add_edge(_PHASE_DATA_PREPARATION, _PHASE_MODELING)

        workflow.add_edge(_PHASE_MODELING, _PHASE_EVALUATION)
        workflow.add_edge(_PHASE_EVALUATION, _PHASE_DEPLOYMENT)
        workflow.add_edge(_PHASE_DEPLOYMENT, END)

        return workflow.compile()

    # =========================================================================
    # PHASE 1: BUSINESS UNDERSTANDING
    # =========================================================================

    def _business_understanding(self, state: ResearchWorkflowState) -> Dict[str, Any]:
        """Phase 1: Understand business context and refine hypothesis."""

        logger.info("📋 Phase 1: Business Understanding")

        prompt = f"""You are a data scientist starting a research project.

RESEARCH QUESTION: {state.research_question}
INITIAL HYPOTHESIS: {state.hypothesis}

Refine this into a clear, testable hypothesis. Define:
1. A precise, testable hypothesis statement
2. Success criteria - what evidence would support or refute it
3. Key variables to analyze

IMPORTANT: If the hypothesis mentions specific database column names (e.g., "column of ltr", "database column X"),
you MUST preserve these exact column names in your refined hypothesis and key_variables.
These are critical hints about which actual database columns to use."""

        try:
            result = self.sql_agent.llm_manager.invoke_with_structured_output_direct(
                system_prompt="You are a data scientist specializing in hypothesis formulation.",
                human_prompt=prompt,
                response_model=BusinessUnderstandingOutput,
            )

            return {
                _HYPOTHESIS: result.refined_hypothesis,
                _SUCCESS_CRITERIA: result.success_criteria,
                _RELEVANT_COLUMNS: result.key_variables,
                _CURRENT_PHASE: _PHASE_DATA_UNDERSTANDING,
            }
        except Exception as e:
            logger.error(f"Business understanding failed: {e}")
            return {_ERRORS: state.errors + [str(e)]}

    # =========================================================================
    # PHASE 2: DATA UNDERSTANDING
    # =========================================================================

    def _data_understanding(self, state: ResearchWorkflowState) -> Dict[str, Any]:
        """Phase 2: Analyze available data and assess quality."""

        logger.info("🔍 Phase 2: Data Understanding")

        # Get structured schema summary
        schema_summary = self._get_structured_schema_summary()

        # Extract any column hints from state
        column_hints = state.relevant_columns if state.relevant_columns else []
        column_hint_text = (
            f"\nCOLUMN HINTS FROM HYPOTHESIS: {', '.join(column_hints)}"
            if column_hints
            else ""
        )

        row_limit = self._research_max_results

        prompt = f"""You are analyzing a database to test this hypothesis:

HYPOTHESIS: {state.hypothesis}
SUCCESS CRITERIA: {state.success_criteria}
{column_hint_text}

DATABASE STRUCTURE:
{schema_summary}

Analyze the data available and provide:
1. Which columns are relevant to test this hypothesis (list specific column names from the schema above)
2. Data quality notes
3. Data limitations
4. 3-5 specific DATA QUESTIONS to ask the database (plain English, NOT SQL)

IMPORTANT:
- If the hypothesis mentions specific column names (e.g., 'ltr', 'nps_score'), use those EXACT column names.
- The recommended_queries MUST be plain-English data questions (NOT SQL). Do not output SQL.
- Use ONLY column names that exist in the DATABASE STRUCTURE above. Never invent columns.

CRITICAL FOR STATISTICAL TESTING:
ALL questions MUST return RAW individual rows, NOT aggregated results.

RULES (mandatory):
- NEVER ask for averages, sums, counts, or any GROUP BY aggregation.
- NEVER use words like "average", "mean", "total", "count per", "by category".
- ALWAYS ask for individual row data with exactly 2 columns: one grouping column + one metric column.
- ALWAYS include a row limit of {row_limit:,}.

REQUIRED question format (fill in real column names from the schema):
  "Show up to {row_limit:,} rows of <group_column> and <metric_column>"

EXAMPLE questions (replace column names with real ones from this schema):
  "Show up to {row_limit:,} rows of member_type and ltr"
  "Show up to {row_limit:,} rows of business_segment and nps_score"
  "Show up to {row_limit:,} rows of region and satisfaction_score"

WHY: Statistical tests (t-test, ANOVA, Mann-Whitney) require individual observations.
Aggregated results (1 row per group) have insufficient variance and cannot be tested."""

        try:
            result = self.sql_agent.llm_manager.invoke_with_structured_output_direct(
                system_prompt="You are a data analyst. Generate specific, executable data questions.",
                human_prompt=prompt,
                response_model=DataUnderstandingOutput,
            )

            return {
                _RELEVANT_COLUMNS: result.relevant_columns,
                "data_quality_assessment": result.data_quality_notes,
                _DATA_LIMITATIONS: result.limitations,
                "evidence_queries": result.recommended_queries,
                "schema_summary": f"Analyzed schema with {len(result.relevant_columns)} relevant columns",
                _CURRENT_PHASE: _PHASE_DATA_PREPARATION,
            }
        except Exception as e:
            logger.error(f"Data understanding failed: {e}")
            return {
                _ERRORS: state.errors + [f"Data understanding failed: {str(e)}"],
                "evidence_queries": [],  # Empty - will skip to analysis with no data
            }

    # =========================================================================
    # PHASE 3: DATA PREPARATION
    # =========================================================================

    @staticmethod
    def _detect_column_remapping(raw_rows: list) -> tuple:
        """Return (needs_remapping, num_cols) by inspecting the first row."""
        if not raw_rows:
            return False, 0
        first_row = raw_rows[0]
        if isinstance(first_row, (list, tuple)):
            return True, len(first_row)
        if isinstance(first_row, dict):
            keys = list(first_row.keys())
            if keys and all(k.startswith(_COL_PREFIX) and k[4:].isdigit() for k in keys):
                return True, len(keys)
        return False, 0

    def _remap_raw_rows(self, raw_rows: list, column_names: Optional[List[str]]) -> list:
        """Remap raw DB rows using resolved column names."""
        data_rows = []
        for row in raw_rows:
            if isinstance(row, dict):
                row_keys = list(row.keys())
                if column_names and len(column_names) == len(row) and all(
                    k.startswith(_COL_PREFIX) for k in row_keys
                ):
                    sorted_keys = sorted(row_keys, key=lambda k: int(k.split("_")[1]))
                    data_rows.append({column_names[i]: row[k] for i, k in enumerate(sorted_keys)})
                else:
                    data_rows.append(row)
            elif isinstance(row, (list, tuple)):
                if column_names and len(column_names) == len(row):
                    data_rows.append(dict(zip(column_names, row)))
                else:
                    data_rows.append({f"{_COL_PREFIX}{i}": v for i, v in enumerate(row)})
            else:
                data_rows.append({"value": row})
        return data_rows

    def _execute_query(
        self,
        idx: int,
        queries: list,
        sql_map: Dict[int, str],
        collected: Dict[str, Any],
        sample_sizes: Dict[str, int],
    ) -> None:
        """Execute one query and populate collected/sample_sizes (thread-safe by key)."""
        key = f"query_{idx + 1}"
        query = queries[idx]
        sql = sql_map.get(idx, "")

        if not sql:
            collected[key] = {_QUESTION: query, "error": "SQL generation failed"}
            sample_sizes[key] = 0
            return

        try:
            raw_rows = self.sql_agent.db_manager.execute_query(sql)
            needs_remapping, num_cols = self._detect_column_remapping(raw_rows)
            column_names: Optional[List[str]] = None
            if needs_remapping and num_cols > 0:
                column_names = self._extract_column_names_from_sql(sql, num_cols)
            data_rows = self._remap_raw_rows(raw_rows, column_names)
            collected[key] = {
                _QUESTION: query,
                "sql": sql,
                "data": data_rows,
                "row_count": len(raw_rows),
            }
            sample_sizes[key] = len(raw_rows)
        except Exception as e:
            logger.error(f"  SQL execution failed for {key}: {e}")
            collected[key] = {_QUESTION: query, "sql": sql, "error": str(e)}
            sample_sizes[key] = 0

    def _data_preparation(self, state: ResearchWorkflowState) -> Dict[str, Any]:
        """Phase 3: Generate SQL sequentially, execute in parallel.

        SQL Agent generates and validates SQL (sequential — SQLAgentWorkflow shares
        internal tracker state and is not safe for concurrent invocations).
        DB execution runs in parallel via db_manager, which is thread-safe.
        """
        queries = state.evidence_queries
        if not queries:
            return {_CURRENT_PHASE: _PHASE_MODELING}

        logger.info(
            f"📊 Phase 3: Generating SQL for {len(queries)} queries, then executing in parallel"
        )

        # ------------------------------------------------------------------
        # Phase A: Generate + validate SQL for every query (sequential, LLM)
        # ------------------------------------------------------------------
        sql_map: Dict[int, str] = {}  # idx → sql string
        for idx, query in enumerate(queries):
            logger.info(f"  Generating SQL {idx + 1}/{len(queries)}: {query[:60]}...")
            try:
                gen_result = self.sql_agent.query(query)
                sql = getattr(gen_result, "sql_query", None) or ""
                if sql:
                    sql_map[idx] = sql
                else:
                    logger.warning(f"  SQL generation returned empty for query {idx + 1}")
                    sql_map[idx] = ""
            except Exception as e:
                logger.error(f"  SQL generation failed for query {idx + 1}: {e}")
                sql_map[idx] = ""

        # ------------------------------------------------------------------
        # Phase B: Execute SQL in parallel (DB calls — thread-safe)
        # ------------------------------------------------------------------
        collected: Dict[str, Any] = {}
        sample_sizes: Dict[str, int] = {}

        max_workers = min(len(queries), 5)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self._execute_query, i, queries, sql_map, collected, sample_sizes)
                for i in range(len(queries))
            ]
            concurrent.futures.wait(futures)

        logger.info(f"📊 Phase 3 complete: {len(collected)} queries executed")
        return {
            "collected_data": collected,
            "sample_sizes": sample_sizes,
            "current_query_index": len(queries),
            _CURRENT_PHASE: _PHASE_MODELING,
        }

    # =========================================================================
    # PHASE 4: MODELING / ANALYSIS
    # =========================================================================

    @staticmethod
    def _score_test(tr, hypothesis_tokens: set) -> float:
        """Score a test result for ranking; higher is better."""
        min_n = min(tr.sample_sizes.values()) if getattr(tr, "sample_sizes", None) else 0
        p = float(getattr(tr, _P_VALUE, 1.0) or 1.0)
        has_es = 1.0 if getattr(tr, _EFFECT_SIZE, None) is not None else 0.0
        sentinel_penalty = (
            -1000.0 if getattr(tr, "test_name", "") == "Sample Size Check Failed" else 0.0
        )
        info = getattr(tr, "additional_info", {}) or {}
        value_col = str(info.get(_VALUE_COLUMN, ""))
        group_col = str(info.get(_GROUP_COLUMN, ""))
        column_match_bonus = 0.0
        if value_col in hypothesis_tokens:
            column_match_bonus += 200.0
        if group_col in hypothesis_tokens:
            column_match_bonus += 200.0
        return sentinel_penalty + column_match_bonus + (min_n * 10.0) + ((1.0 - p) * 5.0) + has_es

    @staticmethod
    def _populate_best_test_metrics(best_test, computed_metrics: dict, n_tests: int) -> None:
        """Write key metrics from the best statistical test into computed_metrics."""
        computed_metrics["test_name"] = best_test.test_name
        computed_metrics["test_statistic"] = best_test.test_statistic
        computed_metrics[_P_VALUE] = best_test.p_value
        computed_metrics["is_significant"] = best_test.is_significant
        if best_test.effect_size is not None:
            computed_metrics[_EFFECT_SIZE] = best_test.effect_size
            computed_metrics["effect_interpretation"] = best_test.effect_size_interpretation
        for group, mean in best_test.group_means.items():
            computed_metrics[f"mean_{group}"] = mean
        info = getattr(best_test, "additional_info", {}) or {}
        computed_metrics["selected_test_context"] = {
            "source_query": info.get("source_query"),
            "source_question": info.get("source_question"),
            _VALUE_COLUMN: info.get(_VALUE_COLUMN),
            _GROUP_COLUMN: info.get(_GROUP_COLUMN),
            "warning": info.get("warning") or info.get("sample_warning"),
        }
        if _BONFERRONI_P in info:
            computed_metrics[_BONFERRONI_P] = info[_BONFERRONI_P]
            computed_metrics[_BONFERRONI_SIGNIFICANT] = info.get(_BONFERRONI_SIGNIFICANT)
            computed_metrics["n_tests_corrected"] = info.get("n_tests_corrected_for", n_tests)

    def _modeling(self, state: ResearchWorkflowState) -> Dict[str, Any]:
        """Phase 4: REAL statistical analysis using scipy/pandas."""

        logger.info("📈 Phase 4: Statistical Analysis (COMPUTED)")

        # Check if we have actual data
        if not state.collected_data:
            logger.warning("No data collected - cannot perform analysis")
            return {
                _STATISTICAL_FINDINGS: [
                    "No data was collected - analysis cannot be performed"
                ],
                _KEY_METRICS: {},
                "computed_stats_text": "NO DATA COLLECTED",
                _ERRORS: state.errors + ["No data collected for analysis"],
            }

        # REAL STATISTICAL COMPUTATION
        stats_results = self.stats_analyzer.analyze_hypothesis_data(
            state.collected_data, state.hypothesis
        )

        # Extract computed findings
        computed_findings = []
        computed_metrics = {}
        stats_text_parts = []
        stats_trace = stats_results.get("trace", [])

        # Process descriptive stats
        for desc_stat in stats_results.get("descriptive_stats", []):
            computed_findings.append(desc_stat.to_prompt_text())
            computed_metrics[f"{desc_stat.variable}_mean"] = desc_stat.mean
            computed_metrics[f"{desc_stat.variable}_std"] = desc_stat.std
            computed_metrics[f"{desc_stat.variable}_n"] = desc_stat.count

        # Process statistical tests (Bonferroni already applied by StatisticalAnalyzer)
        # Choose ONE "best" test for key_metrics; all findings go into computed_findings.
        test_results = list(stats_results.get("statistical_tests", []))
        for test_result in test_results:
            computed_findings.append(test_result.to_prompt_text())
            stats_text_parts.append(test_result.to_prompt_text())

        import re

        hypothesis_tokens = set(re.findall(r"[A-Za-z_]\w*", state.hypothesis or ""))

        best_test = max(test_results, key=lambda tr: self._score_test(tr, hypothesis_tokens)) if test_results else None

        # Store key metrics from the best test only (prevents "last query wins" -> always INCONCLUSIVE)
        if best_test:
            self._populate_best_test_metrics(best_test, computed_metrics, len(test_results))

        # Fallback if no statistical tests could be run
        if not computed_findings:
            # Summarize raw data
            for key, data in state.collected_data.items():
                if "error" not in data and data.get(_ANSWER):
                    computed_findings.append(
                        f"Query result: {data.get('answer', 'N/A')}"
                    )

        # Build computed stats text for LLM interpretation
        computed_stats_text = (
            "\n\n".join(stats_text_parts)
            if stats_text_parts
            else "No statistical tests could be performed on the data structure."
        )

        logger.info(
            f"📊 Computed {len(stats_results.get('statistical_tests', []))} statistical tests"
        )

        return {
            _STATISTICAL_FINDINGS: computed_findings,
            _KEY_METRICS: computed_metrics,
            "computed_stats_text": computed_stats_text,
            _STATS_TRACE: stats_trace,
            _CURRENT_PHASE: _PHASE_EVALUATION,
        }

    # =========================================================================
    # PHASE 5: EVALUATION
    # =========================================================================

    def _evaluation(self, state: ResearchWorkflowState) -> Dict[str, Any]:
        """Phase 5: Evaluate findings - LLM INTERPRETS computed statistics."""

        logger.info("⚖️ Phase 5: Evaluation (Interpreting computed results)")

        # Get computed statistics
        p_value = state.key_metrics.get(_P_VALUE)
        is_significant = state.key_metrics.get("is_significant")
        effect_size = state.key_metrics.get(_EFFECT_SIZE)
        effect_interp = state.key_metrics.get("effect_interpretation", "")
        bonferroni_p = state.key_metrics.get(_BONFERRONI_P)
        bonferroni_sig = state.key_metrics.get(_BONFERRONI_SIGNIFICANT)

        # Build statistics summary for LLM
        stats_summary = (
            state.computed_stats_text
            if state.computed_stats_text
            else "No statistical tests performed"
        )

        prompt = f"""INTERPRET the following COMPUTED statistical results.

HYPOTHESIS: {state.hypothesis}
SUCCESS CRITERIA: {state.success_criteria}

=== COMPUTED STATISTICAL RESULTS (from scipy) ===
{stats_summary}

=== KEY COMPUTED METRICS ===
P-value: {p_value if p_value is not None else _NOT_COMPUTED}
Statistically Significant: {is_significant if is_significant is not None else _NOT_COMPUTED}
Bonferroni-corrected P-value: {bonferroni_p if bonferroni_p is not None else 'N/A (single test)'}
Bonferroni Significant: {bonferroni_sig if bonferroni_sig is not None else 'N/A'}
Effect Size: {effect_size if effect_size is not None else _NOT_COMPUTED} ({effect_interp})

=== DATA LIMITATIONS ===
{chr(10).join(f"• {lim}" for lim in state.data_limitations)}

Based on these COMPUTED statistics (not your interpretation):
1. Is the hypothesis SUPPORTED (p < 0.05 AND meaningful effect), REFUTED (p < 0.05 showing opposite), or INCONCLUSIVE (p >= 0.05 or insufficient data)?
2. Derive confidence from p-value and effect size - don't invent numbers
3. Assess validity of the statistical approach
4. List important caveats

DO NOT invent statistics. Only interpret what was computed above."""

        try:
            result = self.sql_agent.llm_manager.invoke_with_structured_output_direct(
                system_prompt="You are a research evaluator. ONLY interpret the provided computed statistics - do not invent numbers.",
                human_prompt=prompt,
                response_model=EvaluationOutput,
            )

            # Override confidence based on computed statistics.
            # Prefer Bonferroni-corrected significance when multiple tests were run.
            confidence = self._compute_evaluation_confidence(
                p_value, is_significant, bonferroni_sig, bonferroni_p, effect_size,
                fallback=result.confidence,
            )

            return {
                _CONCLUSION: result.conclusion,
                _CONFIDENCE: confidence,
                _VALIDITY_ASSESSMENT: result.validity_assessment,
                _DATA_LIMITATIONS: state.data_limitations + result.caveats,
                _CURRENT_PHASE: _PHASE_DEPLOYMENT,
            }
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            # Provide defaults when LLM fails
            return {
                _CONCLUSION: "INCONCLUSIVE",
                _CONFIDENCE: 0,
                _VALIDITY_ASSESSMENT: f"Evaluation could not be completed: {str(e)}",
                _CURRENT_PHASE: _PHASE_DEPLOYMENT,
                _ERRORS: state.errors + [f"Evaluation failed: {str(e)}"],
            }

    def _compute_evaluation_confidence(
        self, p_value, is_significant, bonferroni_sig, bonferroni_p, effect_size, fallback: int
    ) -> int:
        """Compute confidence score from computed statistical metrics."""
        if p_value is None or is_significant is None:
            return fallback
        effective_sig = bonferroni_sig if bonferroni_sig is not None else is_significant
        effective_p = bonferroni_p if bonferroni_p is not None else p_value
        if effective_sig and effect_size and abs(effect_size) > 0.5:
            return 90
        if effective_sig:
            return 75
        if effective_p < 0.1:
            return 50
        return 30

    # =========================================================================
    # PHASE 6: DEPLOYMENT
    # =========================================================================

    def _deployment(self, state: ResearchWorkflowState) -> Dict[str, Any]:
        """Phase 6: Generate actionable insights and recommendations."""

        logger.info("🚀 Phase 6: Deployment")

        prompt = f"""Generate actionable business recommendations based on research findings.

RESEARCH QUESTION: {state.research_question}
HYPOTHESIS: {state.hypothesis}
CONCLUSION: {state.conclusion} (Confidence: {state.confidence}%)

STATISTICAL FINDINGS:
{chr(10).join(f"• {f}" for f in state.statistical_findings)}

LIMITATIONS:
{chr(10).join(f"• {lim}" for lim in state.data_limitations)}

Generate:
1. Executive summary (2-3 sentences)
2. Key business insights
3. Actionable recommendations
4. Suggested next steps for follow-up research"""

        try:
            result = self.sql_agent.llm_manager.invoke_with_structured_output_direct(
                system_prompt="You are a business consultant translating research into action.",
                human_prompt=prompt,
                response_model=DeploymentOutput,
            )

            return {
                _INSIGHTS: result.insights,
                _RECOMMENDATIONS: result.recommendations,
                _NEXT_STEPS: result.next_steps,
                _TIMESTAMP: datetime.now().isoformat(),
                _CURRENT_PHASE: "complete",
            }
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            # Provide defaults when LLM fails
            return {
                _INSIGHTS: [f"Research concluded with {state.conclusion} result"],
                _RECOMMENDATIONS: [
                    "Review data quality and sample sizes before further analysis"
                ],
                _NEXT_STEPS: ["Collect more data if sample sizes were insufficient"],
                _TIMESTAMP: datetime.now().isoformat(),
                _CURRENT_PHASE: "complete",
                _ERRORS: state.errors + [f"Deployment failed: {str(e)}"],
            }

    # =========================================================================
    # HELPERS
    # =========================================================================

    @staticmethod
    def _split_select_columns(select_clause: str) -> List[str]:
        """Split a SELECT clause on top-level commas (respecting parentheses)."""
        columns = []
        depth = 0
        current: list = []
        for char in select_clause:
            if char == "(":
                depth += 1
                current.append(char)
            elif char == ")":
                depth -= 1
                current.append(char)
            elif char == "," and depth == 0:
                columns.append("".join(current).strip())
                current = []
            else:
                current.append(char)
        if current:
            columns.append("".join(current).strip())
        return columns

    @staticmethod
    def _extract_column_alias(col: str, index: int) -> str:
        """Extract the column name or alias from a single SELECT column expression."""
        import re
        as_match = re.search(r'\s+AS\s+[`"\']?(\w+)[`"\']?\s*$', col, re.IGNORECASE)
        if as_match:
            return as_match.group(1)
        implicit_match = re.search(r'\)\s+[`"\']?(\w+)[`"\']?\s*$', col)
        if implicit_match:
            return implicit_match.group(1)
        simple_match = re.search(r'[`"\']?(\w+)[`"\']?\s*$', col)
        return simple_match.group(1) if simple_match else f"{_COL_PREFIX}{index}"

    def _extract_column_names_from_sql(
        self, sql: str, expected_count: int
    ) -> Optional[List[str]]:
        """
        Parse column names/aliases from a SQL SELECT clause.

        Returns column names if parsing succeeds and count matches, else None.
        """
        import re

        if not sql:
            return None

        sql_normalized = " ".join(sql.split())
        match = re.search(r"SELECT\s+(.+?)\s+FROM\s", sql_normalized, re.IGNORECASE)
        if not match:
            return None

        select_clause = match.group(1)
        if select_clause.strip() == "*":
            return None

        columns = self._split_select_columns(select_clause)
        names = [
            self._extract_column_alias(col.strip(), i)
            for i, col in enumerate(columns)
            if col.strip()
        ]

        return names if len(names) == expected_count else None

    def _get_structured_schema_summary(self) -> str:
        """Get a clean, structured summary with ALL columns and their descriptions."""
        try:
            analysis = self.analyze_schema()

            lines = []
            lines.append(f"Database: {analysis.database_type}")
            lines.append(
                f"Tables: {analysis.total_tables}, Columns: {analysis.total_columns}"
            )

            # ALL tables with ALL columns including descriptions
            for table_name, table in analysis.tables.items():
                lines.append(f"\nTABLE: {table.full_name}")
                if table.description:
                    lines.append(f"Description: {table.description}")

                lines.append("COLUMNS:")
                for col_name, col in table.columns.items():
                    # Include type, statistical category, and description
                    col_info = (
                        f"  - {col_name} ({col.data_type}, {col.statistical_type})"
                    )
                    if col.description:
                        col_info += f": {col.description}"
                    lines.append(col_info)

            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Schema analysis failed, using basic info: {e}")
            return "Database with schema. Use specific column names from your domain knowledge."

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def test_hypothesis(
        self, research_question: str, hypothesis: str
    ) -> Dict[str, Any]:
        """
        Run complete CRISP-DM research workflow.

        Args:
            research_question: The business question to answer
            hypothesis: The hypothesis to test

        Returns:
            Complete research results with all CRISP-DM phases
        """
        logger.info(f"🔬 Starting CRISP-DM research: {hypothesis[:50]}...")

        initial_state = ResearchWorkflowState(
            research_question=research_question, hypothesis=hypothesis
        )

        final_state = self.workflow.invoke(initial_state)

        return {
            # Phase outputs
            "research_question": final_state.get("research_question"),
            _HYPOTHESIS: final_state.get(_HYPOTHESIS),
            _SUCCESS_CRITERIA: final_state.get(_SUCCESS_CRITERIA),
            "data_quality": final_state.get("data_quality_assessment"),
            _RELEVANT_COLUMNS: final_state.get(_RELEVANT_COLUMNS),
            _DATA_LIMITATIONS: final_state.get(_DATA_LIMITATIONS),
            _STATISTICAL_FINDINGS: final_state.get(_STATISTICAL_FINDINGS),
            _KEY_METRICS: final_state.get(_KEY_METRICS),
            _BONFERRONI_P: (final_state.get(_KEY_METRICS) or {}).get(_BONFERRONI_P),
            _BONFERRONI_SIGNIFICANT: (final_state.get(_KEY_METRICS) or {}).get(
                _BONFERRONI_SIGNIFICANT
            ),
            _STATS_TRACE: final_state.get(_STATS_TRACE, []),
            _CONCLUSION: final_state.get(_CONCLUSION),
            _CONFIDENCE: final_state.get(_CONFIDENCE),
            _VALIDITY_ASSESSMENT: final_state.get(_VALIDITY_ASSESSMENT),
            _INSIGHTS: final_state.get(_INSIGHTS),
            _RECOMMENDATIONS: final_state.get(_RECOMMENDATIONS),
            _NEXT_STEPS: final_state.get(_NEXT_STEPS),
            # Metadata
            "queries_executed": len(final_state.get("collected_data", {})),
            _ERRORS: final_state.get(_ERRORS, []),
            _TIMESTAMP: final_state.get(_TIMESTAMP),
        }

    # Backwards compatibility
    def test_assumption(
        self, assumption: str, evidence_queries: List[str]
    ) -> Dict[str, Any]:
        """Legacy method - use test_hypothesis for CRISP-DM workflow."""
        return self.test_hypothesis(research_question=assumption, hypothesis=assumption)

    def query(self, question: str) -> Dict[str, Any]:
        """Execute a single question: SQL Agent generates SQL, db_manager executes it."""
        gen = self.sql_agent.query(question)
        sql = getattr(gen, "sql_query", None) or ""
        raw_rows = self.sql_agent.db_manager.execute_query(sql) if sql else []
        return {
            _QUESTION: question,
            "sql": sql,
            _ANSWER: gen.answer,
            "data": raw_rows,
        }

    @property
    def schema(self) -> str:
        """Get database schema."""
        return self.sql_agent.schema

    def analyze_schema(self) -> SchemaAnalysisReport:
        """Analyze database schema."""
        if self._schema_analysis is None:
            self._schema_analysis = self.schema_analyzer.analyze_schema(True)
        return self._schema_analysis


# Export models
AssumptionAnalysis = EvaluationOutput  # Backwards compatibility
