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

"""Multi-turn conversation runner for BIRD Mini-Interact benchmark.

Orchestrates the interactive dialogue loop between askRITA (system) and
the user simulator for each Mini-Interact task.  The flow per task is:

  1. Build initial prompt from ambiguous query + schema + knowledge.
  2. Send to askRITA's SQLAgentWorkflow.query() → system response.
  3. If system emits SQL → done.  If clarifying question → continue.
  4. Pass clarification to user simulator → get user response.
  5. Append user response to conversation and go to step 2.
  6. Loop until SQL is emitted or max_turn is reached.
  7. Optional debug round: if SQL fails test cases, system gets one retry.
"""

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

from .setup_data import MiniInteractDataManager, MiniInteractTask
from .user_simulator import UserSimulator, UserSimulatorConfig

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """A single turn in the multi-turn conversation."""

    turn_number: int
    role: str  # "system" or "user"
    content: str
    contains_sql: bool = False
    extracted_sql: Optional[str] = None


@dataclass
class ConversationResult:
    """Result of running the multi-turn conversation for a single task."""

    instance_id: str
    selected_database: str
    amb_user_query: str
    predicted_sql: str
    conversation_turns: List[ConversationTurn] = field(default_factory=list)
    num_turns: int = 0
    reward_score: float = 0.0
    debug_used: bool = False
    latency_seconds: float = 0.0
    success: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "selected_database": self.selected_database,
            "amb_user_query": self.amb_user_query,
            "predicted_sql": self.predicted_sql,
            "num_turns": self.num_turns,
            "reward_score": self.reward_score,
            "debug_used": self.debug_used,
            "latency_seconds": round(self.latency_seconds, 3),
            "success": self.success,
            "error": self.error,
            "conversation": [
                {
                    "turn": t.turn_number,
                    "role": t.role,
                    "content": t.content,
                    "contains_sql": t.contains_sql,
                    "extracted_sql": t.extracted_sql,
                }
                for t in self.conversation_turns
            ],
        }


@dataclass
class MiniInteractRunner:
    """Runs askRITA through the BIRD Mini-Interact multi-turn benchmark.

    Args:
        dataset_manager: MiniInteractDataManager with loaded dataset.
        user_simulator: UserSimulator instance for generating user responses.
        llm_provider: LLM provider for askRITA system workflow.
        llm_model: LLM model for askRITA system workflow.
        llm_config_overrides: Additional LLM config fields.
        output_dir: Directory for result files.
        patience: Extra turns beyond the ambiguity count.
        max_retries: Max SQL generation retries in askRITA workflow.
        timeout_per_task: Timeout in seconds per task.
    """

    dataset_manager: MiniInteractDataManager
    user_simulator: UserSimulator
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_config_overrides: Dict[str, Any] = field(default_factory=dict)
    output_dir: str = "./benchmarks/bird_interact/output"
    patience: int = 3
    max_retries: int = 2
    timeout_per_task: int = 300
    progress_callback: Optional[Callable[[int, int, ConversationResult], None]] = None

    _results: List[ConversationResult] = field(default_factory=list, repr=False)
    _workflow_cache: Dict[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self.output_dir = str(Path(self.output_dir).resolve())
        os.makedirs(self.output_dir, exist_ok=True)

    def run(
        self,
        tasks: Optional[List[MiniInteractTask]] = None,
        limit: Optional[int] = None,
        db_filter: Optional[str] = None,
        resume_from: Optional[str] = None,
    ) -> List[ConversationResult]:
        """Run the benchmark on Mini-Interact tasks.

        Args:
            tasks: Specific tasks to run.  If None, loads from dataset_manager.
            limit: Maximum number of tasks to process.
            db_filter: Only run tasks for this database.
            resume_from: Path to partial results JSONL to resume from.

        Returns:
            List of ConversationResult for each task processed.
        """
        if tasks is None:
            tasks = self.dataset_manager.load_tasks(limit=limit, db_filter=db_filter)

        completed_ids = set()
        if resume_from and os.path.exists(resume_from):
            completed_ids = self._load_completed_ids(resume_from)
            logger.info("Resuming: skipping %d completed tasks", len(completed_ids))

        self._results = []
        total = len(tasks)

        logger.info(
            "Starting Mini-Interact benchmark: %d tasks, provider=%s, model=%s, patience=%d",
            total,
            self.llm_provider,
            self.llm_model,
            self.patience,
        )

        for idx, task in enumerate(tasks):
            if task.instance_id in completed_ids:
                continue

            logger.info(
                "[%d/%d] Processing task %s (db=%s, ambiguities=%d)",
                idx + 1,
                total,
                task.instance_id,
                task.selected_database,
                task.ambiguity_count,
            )

            result = self._run_single_task(task)
            self._results.append(result)

            if self.progress_callback:
                self.progress_callback(idx + 1, total, result)

            if result.success:
                logger.info(
                    "  -> SQL generated in %.1fs (%d turns, debug=%s)",
                    result.latency_seconds,
                    result.num_turns,
                    result.debug_used,
                )
            else:
                logger.warning(
                    "  -> FAILED: %s (%.1fs)",
                    result.error,
                    result.latency_seconds,
                )

            if (idx + 1) % 10 == 0:
                self._save_checkpoint()

        self._save_results()
        self._save_predictions()

        success_count = sum(1 for r in self._results if r.success)
        logger.info(
            "Benchmark complete: %d/%d tasks produced SQL (%.1f%%)",
            success_count,
            len(self._results),
            100.0 * success_count / max(len(self._results), 1),
        )

        return self._results

    def _run_single_task(self, task: MiniInteractTask) -> ConversationResult:
        """Run the multi-turn conversation loop for a single task."""
        start_time = time.time()
        turns: List[ConversationTurn] = []
        max_turn = task.max_turn + self.patience
        predicted_sql = ""

        try:
            workflow = self._get_or_create_workflow(task.selected_database)
            schema = self.dataset_manager.get_schema(task.selected_database)

            knowledge_text = ""
            if task.external_knowledge:
                knowledge_text = json.dumps(
                    task.external_knowledge, indent=2, ensure_ascii=False
                )

            initial_prompt = self._build_initial_prompt(task, knowledge_text)

            conversation_history = initial_prompt

            for turn_num in range(1, max_turn + 1):
                state = workflow.query(conversation_history)
                system_response = self._extract_response_text(state)

                sql = self._extract_sql_from_response(system_response)
                has_sql = sql is not None

                turns.append(
                    ConversationTurn(
                        turn_number=turn_num,
                        role="system",
                        content=system_response,
                        contains_sql=has_sql,
                        extracted_sql=sql,
                    )
                )

                if has_sql:
                    predicted_sql = sql
                    break

                clarification = self._extract_clarification(system_response)
                if not clarification:
                    # System didn't ask a question and didn't provide SQL.
                    # Force SQL extraction from raw state.
                    raw_sql = self._extract_sql_from_state(state)
                    if raw_sql:
                        predicted_sql = raw_sql
                        turns[-1].contains_sql = True
                        turns[-1].extracted_sql = raw_sql
                    break

                sim_context = self._build_simulator_context(task, schema)
                sim_response = self.user_simulator.simulate(
                    clarification_question=clarification,
                    task_context=sim_context,
                )

                turns.append(
                    ConversationTurn(
                        turn_number=turn_num,
                        role="user",
                        content=sim_response.user_message,
                    )
                )

                conversation_history = (
                    f"{conversation_history}\n\n"
                    f"User response: {sim_response.user_message}\n\n"
                    f"### Turn {turn_num + 1} ({max_turn - turn_num} turns left):\n"
                    f"Continue the conversation. "
                    f"Ask another clarifying question or generate the final SQL."
                )

            if not predicted_sql:
                predicted_sql = "SELECT 1"

            latency = time.time() - start_time
            return ConversationResult(
                instance_id=task.instance_id,
                selected_database=task.selected_database,
                amb_user_query=task.amb_user_query,
                predicted_sql=predicted_sql,
                conversation_turns=turns,
                num_turns=len([t for t in turns if t.role == "system"]),
                latency_seconds=latency,
                success=predicted_sql != "SELECT 1",
            )

        except Exception as e:
            latency = time.time() - start_time
            logger.error("Error processing task %s: %s", task.instance_id, e)
            return ConversationResult(
                instance_id=task.instance_id,
                selected_database=task.selected_database,
                amb_user_query=task.amb_user_query,
                predicted_sql="SELECT 1",
                conversation_turns=turns,
                num_turns=len([t for t in turns if t.role == "system"]),
                latency_seconds=latency,
                success=False,
                error=str(e),
            )

    def _build_initial_prompt(
        self,
        task: MiniInteractTask,
        knowledge_text: str,
    ) -> str:
        """Build the initial question prompt from the BIRD-Interact protocol.

        The DB schema is NOT embedded in the question text because askRITA's
        prompt-injection guard will reject ``CREATE TABLE`` keywords.  The
        schema is already available to the workflow via the SQLite connection.
        """
        parts = [
            task.amb_user_query,
        ]

        if knowledge_text:
            parts.extend(
                [
                    "",
                    "Additional context:",
                    knowledge_text,
                ]
            )

        return "\n".join(parts)

    def _build_simulator_context(
        self, task: MiniInteractTask, schema: str
    ) -> Dict[str, Any]:
        """Build the context dict for the user simulator."""
        amb_points = task.user_query_ambiguity + task.knowledge_ambiguity
        return {
            "amb_json": amb_points,
            "sol_sql": task.sol_sql,
            "clear_query": task.amb_user_query,
            "db_schema": schema,
            "knowledge_ambiguity": task.knowledge_ambiguity,
        }

    def _extract_sql_from_response(self, response: str) -> Optional[str]:
        """Extract SQL from a system response containing ```sqlite ... ``` blocks."""
        pattern = r"```sqlite\s*(.*?)```"
        match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
        if match:
            sql = match.group(1).strip()
            if sql:
                return sql

        pattern2 = r"```sql\s*(.*?)```"
        match2 = re.search(pattern2, response, re.DOTALL | re.IGNORECASE)
        if match2:
            sql = match2.group(1).strip()
            if sql:
                return sql

        return None

    def _extract_clarification(self, response: str) -> Optional[str]:
        """Extract a clarification question from the system response."""
        match = re.search(r"<question>(.*?)</question>", response, re.DOTALL)
        if match:
            return match.group(1).strip()

        if "?" in response:
            sentences = re.split(r"(?<=[.!?])\s+", response)
            questions = [s for s in sentences if "?" in s]
            if questions:
                return " ".join(questions)

        return None

    def _extract_response_text(self, state: Any) -> str:
        """Extract the response text from the workflow state."""
        if hasattr(state, "formatted_response"):
            return state.formatted_response or ""
        if hasattr(state, "sql_query"):
            sql = state.sql_query or ""
            if sql:
                return f"```sqlite\n{sql}\n```"
        if isinstance(state, dict):
            return state.get("formatted_response", state.get("sql_query", ""))
        return str(state)

    def _extract_sql_from_state(self, state: Any) -> Optional[str]:
        """Extract SQL directly from the workflow state object."""
        if hasattr(state, "sql_query"):
            sql = state.sql_query or ""
            if sql.strip():
                return sql.strip()
        if isinstance(state, dict):
            sql = state.get("sql_query", "")
            if sql and sql.strip():
                return sql.strip()
        return None

    def _get_or_create_workflow(self, db_name: str) -> Any:
        """Get a cached workflow or create a new one for the given database."""
        if db_name in self._workflow_cache:
            return self._workflow_cache[db_name]

        from askrita import ConfigManager, SQLAgentWorkflow

        config_path = self._create_config_for_db(db_name)
        config = ConfigManager(config_path)
        workflow = SQLAgentWorkflow(config)
        self._workflow_cache[db_name] = workflow

        logger.info("Created workflow for database: %s", db_name)
        return workflow

    def _create_config_for_db(self, db_name: str) -> str:
        """Create a temporary YAML config for a specific Mini-Interact database."""
        connection_string = self.dataset_manager.get_connection_string(db_name)

        steps = {
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

        llm_config: Dict[str, Any] = {
            "provider": self.llm_provider,
            "model": self.llm_model,
            "temperature": 0.0,
        }
        llm_config.update(self.llm_config_overrides)

        sqlite_system_prompt = (
            "You are an expert SQLite SQL query generator engaged in a "
            "multi-turn conversation. You MUST generate valid SQLite-dialect "
            "SQL only.\n"
            "CRITICAL SQLite rules:\n"
            "- Use CAST(x AS REAL) for float division\n"
            "- Use CASE WHEN for conditional counting\n"
            "- Use SUBSTR(), LENGTH(), || for strings\n"
            "- Use strftime() for dates\n"
            "- Use GROUP_CONCAT(), IFNULL() or COALESCE()\n"
            "- Generate SELECT queries only\n"
            "- If the conversation provides clarifications, incorporate them."
        )

        sqlite_human_prompt = (
            "Database: SQLite\n"
            "Schema:\n{schema}\n\n"
            "Question: {question}\n\n"
            "Generate a valid SQLite SELECT query. Return ONLY the SQL query."
        )

        config_data = {
            "database": {
                "connection_string": connection_string,
                "cache_schema": True,
                "schema_refresh_interval": 86400,
                "sql_syntax": {"cast_to_string": "TEXT"},
            },
            "llm": llm_config,
            "workflow": {
                "steps": steps,
                "max_retries": self.max_retries,
                "timeout_per_step": self.timeout_per_task,
                "sql_safety": {
                    "forbidden_patterns": [],
                    "max_sql_length": 10000,
                },
                "input_validation": {"blocked_substrings": []},
            },
            "prompts": {
                "parse_question": {
                    "system": "You are a data analyst. Parse user questions for a SQLite database.",
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
            "chain_of_thoughts": {"enabled": False},
            "framework": {"debug": False},
        }

        config_dir = os.path.join(self.output_dir, "configs")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, f"interact_{db_name}.yaml")

        with open(config_path, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False)

        return config_path

    def _load_completed_ids(self, results_path: str) -> set:
        """Load completed instance IDs from a partial results JSONL."""
        completed = set()
        try:
            with open(results_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entry = json.loads(line)
                        completed.add(entry.get("instance_id", ""))
        except Exception as e:
            logger.warning("Could not load resume file %s: %s", results_path, e)
        return completed

    def _save_checkpoint(self) -> None:
        """Save intermediate results as a checkpoint."""
        checkpoint_path = os.path.join(self.output_dir, "results_checkpoint.jsonl")
        with open(checkpoint_path, "w") as f:
            for result in self._results:
                f.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")
        logger.info("Checkpoint saved: %d results", len(self._results))

    def _save_results(self) -> None:
        """Save detailed results as JSONL."""
        results_path = os.path.join(self.output_dir, "detailed_results.jsonl")
        with open(results_path, "w") as f:
            for result in self._results:
                f.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")
        logger.info("Detailed results saved to %s", results_path)

    def _save_predictions(self) -> None:
        """Save predictions in a simple JSON format."""
        predictions: Dict[str, str] = {}
        for result in self._results:
            predictions[result.instance_id] = result.predicted_sql
        predictions_path = os.path.join(self.output_dir, "predictions.json")
        with open(predictions_path, "w") as f:
            json.dump(predictions, f, indent=2, ensure_ascii=False)
        logger.info("Predictions saved to %s", predictions_path)

    def get_results_summary(self) -> Dict[str, Any]:
        """Get a summary of benchmark results."""
        if not self._results:
            return {"total": 0, "message": "No results yet."}

        total = len(self._results)
        success = sum(1 for r in self._results if r.success)
        latencies = [r.latency_seconds for r in self._results if r.success]
        avg_turns = sum(r.num_turns for r in self._results) / total if total else 0

        by_db: Dict[str, Dict[str, int]] = {}
        for r in self._results:
            if r.selected_database not in by_db:
                by_db[r.selected_database] = {"total": 0, "success": 0}
            by_db[r.selected_database]["total"] += 1
            if r.success:
                by_db[r.selected_database]["success"] += 1

        return {
            "total": total,
            "success": success,
            "failed": total - success,
            "sql_generation_rate": round(100.0 * success / max(total, 1), 2),
            "avg_latency_seconds": round(sum(latencies) / max(len(latencies), 1), 3),
            "avg_turns": round(avg_turns, 2),
            "by_database": by_db,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "patience": self.patience,
        }
