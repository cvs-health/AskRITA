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

"""Dataset download and management for BIRD Mini-Interact benchmark.

Mini-Interact is a lightweight interactive text-to-SQL benchmark (300 tasks,
SQLite, no Docker) from the BIRD-Interact project.  Each task contains an
*ambiguous* user query that must be clarified through multi-turn dialogue
before SQL generation.

Dataset: https://huggingface.co/datasets/birdsql/mini-interact
"""

import json
import logging
import os
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MINI_INTERACT_HF_REPO = "birdsql/mini-interact"
MINI_INTERACT_GOOGLE_DRIVE_BACKUP = (
    "https://drive.google.com/file/d/1HAXSy0rEiPRBvSZTPoOzmZrYq9wv549q/view"
)


@dataclass
class MiniInteractTask:
    """A single BIRD Mini-Interact task."""

    instance_id: str
    selected_database: str
    amb_user_query: str
    user_query_ambiguity: List[Dict[str, Any]] = field(default_factory=list)
    non_critical_ambiguity: List[Dict[str, Any]] = field(default_factory=list)
    knowledge_ambiguity: List[Dict[str, Any]] = field(default_factory=list)
    external_knowledge: Any = field(default_factory=list)

    # Ground-truth fields (require emailing bird.bench25@gmail.com)
    sol_sql: Optional[str] = None
    preprocess_sql: Optional[List[str]] = None
    clean_up_sql: Optional[List[str]] = None
    test_cases: Optional[List[Dict[str, Any]]] = None

    @property
    def has_ground_truth(self) -> bool:
        """True when sol_sql is available (with or without test cases)."""
        return bool(isinstance(self.sol_sql, str) and self.sol_sql.strip())

    @property
    def max_turn(self) -> int:
        """Max clarification turns = number of ambiguity points + patience."""
        return len(self.user_query_ambiguity) + len(self.knowledge_ambiguity)

    @property
    def ambiguity_count(self) -> int:
        return len(self.user_query_ambiguity) + len(self.knowledge_ambiguity)


@dataclass
class MiniInteractDataManager:
    """Manages BIRD Mini-Interact dataset download, storage, and access.

    Supports downloading the dataset from HuggingFace (``git clone``) and
    optionally merging ground-truth fields from a separately obtained file.

    Args:
        data_dir: Root directory for Mini-Interact data storage.
    """

    data_dir: str = "./benchmarks/bird_interact/data"
    _tasks: List[MiniInteractTask] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self.data_dir = str(Path(self.data_dir).resolve())
        self.repo_dir = os.path.join(self.data_dir, "mini-interact")
        self.tasks_file = os.path.join(self.repo_dir, "mini_interact.jsonl")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def setup(self) -> bool:
        """Download and prepare the Mini-Interact dataset.

        Returns:
            True if setup completed successfully.
        """
        os.makedirs(self.data_dir, exist_ok=True)

        if self._is_ready():
            logger.info(
                "Mini-Interact dataset already available at %s", self.repo_dir
            )
            return True

        return self._download_from_huggingface()

    def load_tasks(
        self,
        limit: Optional[int] = None,
        db_filter: Optional[str] = None,
    ) -> List[MiniInteractTask]:
        """Load Mini-Interact tasks from the dataset.

        Args:
            limit: Maximum number of tasks to load.
            db_filter: Only load tasks for this database.

        Returns:
            List of MiniInteractTask instances.
        """
        if self._tasks and not limit and not db_filter:
            return self._tasks

        self._resolve_tasks_file()

        tasks = self._read_tasks_from_file(limit, db_filter)

        if not limit and not db_filter:
            self._tasks = tasks

        logger.info("Loaded %d Mini-Interact tasks", len(tasks))
        return tasks

    def _resolve_tasks_file(self) -> None:
        """Ensure tasks_file points to an existing JSONL file."""
        if os.path.exists(self.tasks_file):
            return
        alt = os.path.join(self.repo_dir, "mini_interact_test.jsonl")
        if os.path.exists(alt):
            self.tasks_file = alt
        else:
            raise FileNotFoundError(
                f"Tasks file not found: {self.tasks_file}\n"
                "Run setup() first to download the dataset."
            )

    def _read_tasks_from_file(
        self, limit: Optional[int], db_filter: Optional[str]
    ) -> List[MiniInteractTask]:
        """Read and filter tasks from the JSONL file."""
        tasks: List[MiniInteractTask] = []
        with open(self.tasks_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)
                if db_filter and raw.get("selected_database") != db_filter:
                    continue
                tasks.append(self._parse_task(raw))
                if limit and len(tasks) >= limit:
                    break
        return tasks

    def merge_ground_truth(self, gt_path: str) -> None:
        """Merge ground-truth fields into the public tasks file.

        After emailing ``bird.bench25@gmail.com`` with subject
        ``[mini-interact GT&Test Cases]``, you receive a JSONL file with
        ``sol_sql``, ``test_cases``, ``preprocess_sql``, and ``clean_up_sql``.
        This method merges those fields into the public data.

        Args:
            gt_path: Path to the GT JSONL file received via email.
        """
        if not os.path.exists(gt_path):
            raise FileNotFoundError(f"Ground truth file not found: {gt_path}")

        gt_map = self._load_gt_map(gt_path)
        if not gt_map:
            logger.warning("GT file contains no entries: %s", gt_path)
            return

        merged_lines = self._merge_gt_into_tasks(gt_map)

        with open(self.tasks_file, "w") as f:
            f.write("\n".join(merged_lines) + "\n")

        self._tasks = []
        logger.info(
            "Merged %d GT entries into %s", len(gt_map), self.tasks_file
        )

    def _load_gt_map(self, gt_path: str) -> Dict[str, Dict[str, Any]]:
        """Load ground-truth entries keyed by instance_id."""
        gt_map: Dict[str, Dict[str, Any]] = {}
        with open(gt_path, "r") as f:
            for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                entry = json.loads(raw_line)
                iid = entry.get("instance_id", "")
                if iid:
                    gt_map[iid] = entry
        return gt_map

    _GT_MERGE_KEYS = ("sol_sql", "test_cases", "preprocess_sql",
                      "clean_up_sql", "clean_up_sqls", "external_knowledge")

    def _merge_gt_into_tasks(
        self, gt_map: Dict[str, Dict[str, Any]]
    ) -> List[str]:
        """Merge GT fields into public task lines and return merged JSONL strings."""
        merged_lines: List[str] = []
        with open(self.tasks_file, "r") as f:
            for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                public = json.loads(raw_line)
                iid = public.get("instance_id", "")
                if iid in gt_map:
                    gt = gt_map[iid]
                    for key in self._GT_MERGE_KEYS:
                        if key in gt:
                            public[key] = gt[key]
                merged_lines.append(json.dumps(public, ensure_ascii=False))
        return merged_lines

    @property
    def has_ground_truth(self) -> bool:
        """Check whether any loaded task has GT fields."""
        if not self._tasks:
            tasks = self.load_tasks(limit=1)
        else:
            tasks = self._tasks
        return any(t.has_ground_truth for t in tasks)

    def get_db_path(self, db_name: str) -> str:
        """Get the SQLite database file path for a given database name."""
        candidates = [
            os.path.join(self.repo_dir, db_name, f"{db_name}.sqlite"),
            os.path.join(self.repo_dir, "DBs", db_name, f"{db_name}.sqlite"),
            os.path.join(self.repo_dir, db_name, f"{db_name}.db"),
            os.path.join(self.repo_dir, "DBs", db_name, f"{db_name}.db"),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        # Glob fallback
        for root, _dirs, files in os.walk(
            os.path.join(self.repo_dir)
        ):
            for fname in files:
                if fname.endswith((".sqlite", ".db")) and db_name in root:
                    return os.path.join(root, fname)
        raise FileNotFoundError(
            f"Database file for '{db_name}' not found under {self.repo_dir}"
        )

    def get_connection_string(self, db_name: str) -> str:
        return f"sqlite:///{self.get_db_path(db_name)}"

    def get_schema(self, db_name: str) -> str:
        """Read the schema text file for a database."""
        candidates = [
            os.path.join(self.repo_dir, db_name, f"{db_name}_schema.txt"),
            os.path.join(self.repo_dir, "DBs", db_name, f"{db_name}_schema.txt"),
        ]
        for p in candidates:
            if os.path.exists(p):
                with open(p, "r") as f:
                    return f.read()

        # Fall back to reading schema from the SQLite database directly
        return self._read_schema_from_db(db_name)

    def get_knowledge_base(self, db_name: str) -> List[Dict[str, Any]]:
        """Read the knowledge base JSONL file for a database."""
        candidates = [
            os.path.join(self.repo_dir, db_name, f"{db_name}_kb.jsonl"),
            os.path.join(self.repo_dir, "DBs", db_name, f"{db_name}_kb.jsonl"),
        ]
        for p in candidates:
            if os.path.exists(p):
                entries: List[Dict[str, Any]] = []
                with open(p, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            entries.append(json.loads(line))
                return entries
        return []

    def list_databases(self) -> List[str]:
        """List all available database names."""
        tasks = self.load_tasks()
        return sorted({t.selected_database for t in tasks})

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _is_ready(self) -> bool:
        if not os.path.isdir(self.repo_dir):
            return False
        if os.path.exists(self.tasks_file):
            return True
        alt = os.path.join(self.repo_dir, "mini_interact_test.jsonl")
        return os.path.exists(alt)

    def _download_from_huggingface(self) -> bool:
        """Clone the mini-interact dataset from HuggingFace."""
        logger.info("Downloading Mini-Interact from HuggingFace...")
        try:
            env = os.environ.copy()
            env["GIT_LFS_SKIP_SMUDGE"] = "0"
            subprocess.run(
                [
                    "git", "clone",
                    f"https://huggingface.co/datasets/{MINI_INTERACT_HF_REPO}",
                    self.repo_dir,
                ],
                check=True,
                env=env,
                capture_output=True,
                text=True,
            )
            logger.info("Dataset cloned to %s", self.repo_dir)
        except subprocess.CalledProcessError as e:
            logger.error("git clone failed: %s\n%s", e.stdout, e.stderr)
            return False
        except FileNotFoundError:
            logger.error(
                "git not found. Please install git and git-lfs, then retry.\n"
                "Alternatively, manually clone:\n"
                "  git clone https://huggingface.co/datasets/%s %s",
                MINI_INTERACT_HF_REPO,
                self.repo_dir,
            )
            return False

        if not self._is_ready():
            logger.warning(
                "Clone succeeded but tasks file not found at %s.\n"
                "The dataset may also be downloaded from Google Drive:\n  %s",
                self.tasks_file,
                MINI_INTERACT_GOOGLE_DRIVE_BACKUP,
            )
            return False

        return True

    def _parse_task(self, raw: Dict[str, Any]) -> MiniInteractTask:
        """Parse a raw JSON dict into a MiniInteractTask."""
        # sol_sql may be a string, a single-element list, or an empty list
        raw_sol = raw.get("sol_sql")
        if isinstance(raw_sol, str) and raw_sol.strip():
            sol_sql = raw_sol
        elif isinstance(raw_sol, list) and raw_sol:
            sol_sql = str(raw_sol[0]) if raw_sol[0] else None
        else:
            sol_sql = None

        # Dataset uses "clean_up_sqls" (with trailing s)
        clean_up = raw.get("clean_up_sqls") or raw.get("clean_up_sql")

        # test_cases: treat empty list as None
        raw_tc = raw.get("test_cases")
        test_cases = raw_tc if isinstance(raw_tc, list) and raw_tc else None

        return MiniInteractTask(
            instance_id=str(raw.get("instance_id", "")),
            selected_database=raw.get("selected_database", ""),
            amb_user_query=raw.get("amb_user_query", ""),
            user_query_ambiguity=raw.get("user_query_ambiguity", []),
            non_critical_ambiguity=raw.get("non_critical_ambiguity", []),
            knowledge_ambiguity=raw.get("knowledge_ambiguity", []),
            external_knowledge=raw.get("external_knowledge", []),
            sol_sql=sol_sql,
            preprocess_sql=raw.get("preprocess_sql"),
            clean_up_sql=clean_up,
            test_cases=test_cases,
        )

    def _read_schema_from_db(self, db_name: str) -> str:
        """Fall back to reading schema directly from SQLite."""
        db_path = self.get_db_path(db_name)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        )
        tables = [row[0] for row in cursor.fetchall()]
        parts = [f"Database: {db_name}", f"Tables: {len(tables)}", ""]
        for table in tables:
            cursor.execute(f"PRAGMA table_info('{table}');")
            columns = cursor.fetchall()
            col_strs = [f"  {col[1]} ({col[2]})" for col in columns]
            parts.append(f"{table}:")
            parts.extend(col_strs)
            parts.append("")
        conn.close()
        return "\n".join(parts)
