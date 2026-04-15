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

"""Benchmark runner that feeds BIRD questions through the askRITA pipeline."""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

from .setup_data import BIRDDatasetManager, BIRDQuestion

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stats-dict key constants (used 3+ times)
# ---------------------------------------------------------------------------
_KEY_TOTAL = "total"
_KEY_SUCCESS = "success"
_KEY_RETRY_COUNT = "retry_count"

BIRD_PREDICTION_SEPARATOR = "\t----- bird -----\t"


@dataclass
class BenchmarkResult:
    """Result of running askRITA on a single BIRD question."""

    question_id: int
    db_id: str
    question: str
    evidence: str
    gold_sql: str
    predicted_sql: str
    difficulty: str
    success: bool
    error: Optional[str] = None
    latency_seconds: float = 0.0
    retry_count: int = 0


@dataclass
class BIRDBenchmarkRunner:
    """Runs askRITA against BIRD benchmark questions and produces prediction files.

    This runner creates a temporary askRITA config per database, instantiates
    SQLAgentWorkflow, and extracts the generated SQL from the workflow state.

    Args:
        dataset_manager: BIRDDatasetManager with loaded dataset.
        llm_provider: LLM provider name (e.g., "openai", "azure_openai").
        llm_model: LLM model name (e.g., "gpt-4o").
        llm_config_overrides: Additional LLM config fields (api_key, endpoint, etc.).
        output_dir: Directory for prediction files and logs.
        include_evidence: Whether to include BIRD's "evidence" (external knowledge)
            in the question prompt. This simulates the "with oracle knowledge" setting.
        max_retries: Max SQL generation retries in the askRITA workflow.
        timeout_per_question: Timeout in seconds per question.
        workflow_steps_override: Override which workflow steps to enable.
            By default, disables visualization and follow-up steps for speed.
    """

    dataset_manager: BIRDDatasetManager
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_config_overrides: Dict[str, Any] = field(default_factory=dict)
    output_dir: str = "./benchmarks/bird/output"
    include_evidence: bool = True
    max_retries: int = 2
    timeout_per_question: int = 120
    workflow_steps_override: Optional[Dict[str, bool]] = None
    progress_callback: Optional[Callable[[int, int, BenchmarkResult], None]] = None

    _results: List[BenchmarkResult] = field(default_factory=list, repr=False)
    _workflow_cache: Dict[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self.output_dir = str(Path(self.output_dir).resolve())
        os.makedirs(self.output_dir, exist_ok=True)

    def run(
        self,
        questions: Optional[List[BIRDQuestion]] = None,
        db_filter: Optional[str] = None,
        limit: Optional[int] = None,
        resume_from: Optional[str] = None,
    ) -> List[BenchmarkResult]:
        """Run the benchmark on BIRD questions.

        Args:
            questions: Specific questions to run. If None, loads from dataset_manager.
            db_filter: Only run questions for this database.
            limit: Maximum number of questions to process.
            resume_from: Path to a partial predictions file to resume from.

        Returns:
            List of BenchmarkResult for each question processed.
        """
        if questions is None:
            questions = self.dataset_manager.load_questions(
                db_filter=db_filter, limit=limit
            )

        completed_ids = set()
        if resume_from and os.path.exists(resume_from):
            completed_ids = self._load_completed_ids(resume_from)
            logger.info(
                "Resuming: skipping %d already-completed questions", len(completed_ids)
            )

        self._results = []
        total = len(questions)

        logger.info(
            "Starting BIRD benchmark: %d questions, provider=%s, model=%s, evidence=%s",
            total,
            self.llm_provider,
            self.llm_model,
            self.include_evidence,
        )

        for idx, question in enumerate(questions):
            if question.question_id in completed_ids:
                continue

            logger.info(
                "[%d/%d] Processing question %d (db=%s, difficulty=%s)",
                idx + 1,
                total,
                question.question_id,
                question.db_id,
                question.difficulty,
            )

            result = self._run_single_question(question)
            self._results.append(result)

            if self.progress_callback:
                self.progress_callback(idx + 1, total, result)

            if result.success:
                logger.info(
                    "  -> SQL generated in %.1fs (retries=%d)",
                    result.latency_seconds,
                    result.retry_count,
                )
            else:
                logger.warning(
                    "  -> FAILED: %s (%.1fs)",
                    result.error,
                    result.latency_seconds,
                )

            # Checkpoint every 25 questions
            if (idx + 1) % 25 == 0:
                self._save_checkpoint()

        self._save_predictions()
        self._save_detailed_results()

        success_count = sum(1 for r in self._results if r.success)
        logger.info(
            "Benchmark complete: %d/%d questions produced SQL (%.1f%%)",
            success_count,
            len(self._results),
            100.0 * success_count / max(len(self._results), 1),
        )

        return self._results

    def _run_single_question(self, question: BIRDQuestion) -> BenchmarkResult:
        """Run askRITA on a single BIRD question."""
        start_time = time.time()

        try:
            workflow = self._get_or_create_workflow(question.db_id)
            prompt = self._build_prompt(question)
            state = workflow.query(prompt)

            predicted_sql = self._extract_sql(state)
            latency = time.time() - start_time

            if not predicted_sql or predicted_sql.strip() == "":
                return BenchmarkResult(
                    question_id=question.question_id,
                    db_id=question.db_id,
                    question=question.question,
                    evidence=question.evidence,
                    gold_sql=question.gold_sql,
                    predicted_sql="SELECT 1",
                    difficulty=question.difficulty,
                    success=False,
                    error="Empty SQL generated",
                    latency_seconds=latency,
                    retry_count=getattr(state, _KEY_RETRY_COUNT, 0),
                )

            return BenchmarkResult(
                question_id=question.question_id,
                db_id=question.db_id,
                question=question.question,
                evidence=question.evidence,
                gold_sql=question.gold_sql,
                predicted_sql=predicted_sql,
                difficulty=question.difficulty,
                success=True,
                latency_seconds=latency,
                retry_count=getattr(state, _KEY_RETRY_COUNT, 0),
            )

        except Exception as e:
            latency = time.time() - start_time
            logger.error("Error processing question %d: %s", question.question_id, e)
            return BenchmarkResult(
                question_id=question.question_id,
                db_id=question.db_id,
                question=question.question,
                evidence=question.evidence,
                gold_sql=question.gold_sql,
                predicted_sql="SELECT 1",
                difficulty=question.difficulty,
                success=False,
                error=str(e),
                latency_seconds=latency,
            )

    def _get_or_create_workflow(self, db_id: str):
        """Get a cached workflow or create a new one for the given database.

        Workflows are cached per db_id to avoid re-initializing the LLM
        and database connections for every question in the same database.
        """
        if db_id in self._workflow_cache:
            return self._workflow_cache[db_id]

        from askrita import ConfigManager, SQLAgentWorkflow

        config_path = self._create_config_for_db(db_id)
        config = ConfigManager(config_path)
        workflow = SQLAgentWorkflow(config)
        self._workflow_cache[db_id] = workflow

        logger.info("Created workflow for database: %s", db_id)
        return workflow

    def _create_config_for_db(self, db_id: str) -> str:
        """Create a temporary YAML config file for a specific BIRD database.

        The config is optimized for benchmarking:
        - Only SQL generation steps are enabled (no viz, no follow-ups)
        - Schema caching is enabled for speed
        - SQL safety checks are relaxed for benchmark queries
        """
        connection_string = self.dataset_manager.get_connection_string(db_id)

        steps = self.workflow_steps_override or {
            "parse_question": True,
            "get_unique_nouns": True,
            "generate_sql": True,
            "validate_and_fix_sql": False,
            "execute_sql": False,
            "format_results": False,
            "choose_visualization": False,
            "format_data_for_visualization": False,
            "choose_and_format_visualization": False,
            "generate_followup_questions": False,
            "pii_detection": False,
        }

        llm_config = {
            "provider": self.llm_provider,
            "model": self.llm_model,
            "temperature": 0.0,
        }
        llm_config.update(self.llm_config_overrides)

        sqlite_system_prompt = (
            "You are an expert SQLite SQL query generator. "
            "You MUST generate valid SQLite-dialect SQL only. "
            "CRITICAL SQLite rules you MUST follow:\n"
            "- Use CAST(x AS REAL) or *1.0 for float division, NEVER use ::float or ::numeric\n"
            "- Use CASE WHEN ... THEN 1 ELSE 0 END for conditional counting, NEVER use FILTER(WHERE ...)\n"
            "- Use SUBSTR() not SUBSTRING(), LENGTH() not LEN()\n"
            "- Use || for string concatenation, NEVER use CONCAT()\n"
            "- Use strftime() for dates, NEVER use DATE_PART(), EXTRACT(), or TO_DATE()\n"
            "- Use GROUP_CONCAT() not STRING_AGG() or ARRAY_AGG()\n"
            "- Use IFNULL() or COALESCE(), NEVER use ISNULL() or NVL()\n"
            "- Use IIF(condition, true_val, false_val) for inline conditionals\n"
            "- SQLite is case-insensitive for keywords but case-sensitive for string comparisons by default\n"
            "- Use LIKE for case-insensitive string matching when needed\n"
            "- Generate SELECT queries only. Never generate DROP, DELETE, INSERT, UPDATE, ALTER, or DDL.\n"
            "- If the user question includes 'Additional context' or 'evidence', use it as domain knowledge to write accurate SQL."
        )

        sqlite_human_prompt = (
            "Database: SQLite\n"
            "Schema:\n{schema}\n\n"
            "Question: {question}\n\n"
            "Generate a valid SQLite SELECT query to answer this question. "
            "Return ONLY the SQL query."
        )

        config_data = {
            "database": {
                "connection_string": connection_string,
                "cache_schema": True,
                "schema_refresh_interval": 86400,
                "sql_syntax": {
                    "cast_to_string": "TEXT",
                },
            },
            "llm": llm_config,
            "workflow": {
                "steps": steps,
                "max_retries": self.max_retries,
                "timeout_per_step": self.timeout_per_question,
                "sql_safety": {
                    "forbidden_patterns": [],
                    "max_sql_length": 10000,
                },
                "input_validation": {
                    "blocked_substrings": [],
                },
            },
            "prompts": {
                "parse_question": {
                    "system": "You are a data analyst. Parse user questions and identify relevant tables in a SQLite database.",
                    "human": "Database schema: {schema}\nUser question: {question}\n\nIdentify relevant tables.",
                },
                "generate_sql": {
                    "system": sqlite_system_prompt,
                    "human": sqlite_human_prompt,
                },
                "validate_sql": {
                    "system": "Validate SQLite SQL queries and fix syntax issues.",
                    "human": "Schema: {schema}\nQuery: {query}\nValidate this SQLite query.",
                },
                "format_results": {
                    "system": "Format query results for display.",
                    "human": "Results: {results}\nFormat for display.",
                },
            },
            "chain_of_thoughts": {
                "enabled": False,
            },
            "framework": {
                "debug": False,
            },
        }

        config_dir = os.path.join(self.output_dir, "configs")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, f"bird_{db_id}.yaml")

        with open(config_path, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False)

        return config_path

    def _build_prompt(self, question: BIRDQuestion) -> str:
        """Build the prompt for askRITA from a BIRD question.

        When include_evidence is True, the external knowledge evidence is
        prepended to the question, matching BIRD's "with oracle knowledge" setting.
        """
        if self.include_evidence and question.evidence and question.evidence.strip():
            return f"{question.question}\n\n" f"Additional context: {question.evidence}"
        return question.question

    def _extract_sql(self, state) -> str:
        """Extract the generated SQL from the workflow state.

        Handles both WorkflowState objects and dict-like returns.
        """
        if hasattr(state, "sql_query"):
            return state.sql_query or ""
        if isinstance(state, dict):
            return state.get("sql_query", "")
        return ""

    def _load_completed_ids(self, predictions_path: str) -> set:
        """Load question IDs from a partial predictions file for resume support."""
        completed = set()
        try:
            with open(predictions_path, "r") as f:
                predictions = json.load(f)
            for key in predictions:
                completed.add(int(key))
        except Exception as e:
            logger.warning("Could not load resume file %s: %s", predictions_path, e)
        return completed

    def _save_checkpoint(self):
        """Save intermediate predictions as a checkpoint."""
        checkpoint_path = os.path.join(self.output_dir, "predictions_checkpoint.json")
        predictions = {}
        for result in self._results:
            predictions[str(result.question_id)] = (
                f"{result.predicted_sql}{BIRD_PREDICTION_SEPARATOR}{result.db_id}"
            )
        with open(checkpoint_path, "w") as f:
            json.dump(predictions, f, indent=2)
        logger.info("Checkpoint saved: %d predictions", len(predictions))

    def _save_predictions(self):
        """Save predictions in BIRD-compatible format.

        Format: {"0": "SELECT ... \\t----- bird -----\\t db_name", ...}
        """
        predictions = {}
        for result in self._results:
            sql = result.predicted_sql.strip().replace("\n", " ")
            predictions[str(result.question_id)] = (
                f"{sql}{BIRD_PREDICTION_SEPARATOR}{result.db_id}"
            )

        predictions_path = os.path.join(self.output_dir, "predictions.json")
        with open(predictions_path, "w") as f:
            json.dump(predictions, f, indent=2)

        logger.info("Predictions saved to %s", predictions_path)

    def _save_detailed_results(self):
        """Save detailed results with latency, errors, and metadata."""
        detailed = []
        for r in self._results:
            detailed.append(
                {
                    "question_id": r.question_id,
                    "db_id": r.db_id,
                    "question": r.question,
                    "evidence": r.evidence,
                    "gold_sql": r.gold_sql,
                    "predicted_sql": r.predicted_sql,
                    "difficulty": r.difficulty,
                    _KEY_SUCCESS: r.success,
                    "error": r.error,
                    "latency_seconds": round(r.latency_seconds, 3),
                    _KEY_RETRY_COUNT: r.retry_count,
                }
            )

        results_path = os.path.join(self.output_dir, "detailed_results.json")
        with open(results_path, "w") as f:
            json.dump(detailed, f, indent=2)

        logger.info("Detailed results saved to %s", results_path)

    def get_results_summary(self) -> Dict[str, Any]:
        """Get a summary of benchmark results.

        Returns:
            Dictionary with counts, success rates, and latency stats.
        """
        if not self._results:
            return {
                _KEY_TOTAL: 0,
                "message": "No results yet. Run the benchmark first.",
            }

        total = len(self._results)
        success = sum(1 for r in self._results if r.success)
        latencies = [r.latency_seconds for r in self._results if r.success]

        by_difficulty = {}
        for difficulty in ["simple", "moderate", "challenging"]:
            subset = [r for r in self._results if r.difficulty == difficulty]
            if subset:
                by_difficulty[difficulty] = {
                    _KEY_TOTAL: len(subset),
                    _KEY_SUCCESS: sum(1 for r in subset if r.success),
                    "success_rate": round(
                        100.0 * sum(1 for r in subset if r.success) / len(subset), 2
                    ),
                }

        by_db = {}
        for r in self._results:
            if r.db_id not in by_db:
                by_db[r.db_id] = {_KEY_TOTAL: 0, _KEY_SUCCESS: 0}
            by_db[r.db_id][_KEY_TOTAL] += 1
            if r.success:
                by_db[r.db_id][_KEY_SUCCESS] += 1

        return {
            _KEY_TOTAL: total,
            _KEY_SUCCESS: success,
            "failed": total - success,
            "sql_generation_rate": round(100.0 * success / max(total, 1), 2),
            "avg_latency_seconds": round(sum(latencies) / max(len(latencies), 1), 3),
            "median_latency_seconds": round(
                sorted(latencies)[len(latencies) // 2] if latencies else 0, 3
            ),
            "by_difficulty": by_difficulty,
            "by_database": by_db,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "include_evidence": self.include_evidence,
        }
