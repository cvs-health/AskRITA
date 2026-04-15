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
#   datasets (Apache-2.0)

"""Dataset download and management for BIRD Mini-Dev benchmark."""

import json
import logging
import math
import os
import random
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dataset field-name constants (used 3+ times)
# ---------------------------------------------------------------------------
_FIELD_DB_ID = "db_id"
_FIELD_DIFFICULTY = "difficulty"
_FIELD_QUESTION_ID = "question_id"
_FIELD_QUESTION = "question"
_FIELD_EVIDENCE = "evidence"
_SQLITE_EXT = ".sqlite"
_DIFFICULTY_SIMPLE = "simple"

BIRD_MINI_DEV_HF_DATASET = "birdsql/bird_mini_dev"

BIRD_DATABASES = [
    "debit_card_specializing",
    "student_club",
    "thrombosis_prediction",
    "european_football_2",
    "formula_1",
    "superhero",
    "codebase_community",
    "card_games",
    "toxicology",
    "california_schools",
    "financial",
]


@dataclass
class BIRDQuestion:
    """A single BIRD benchmark question."""

    question_id: int
    db_id: str
    question: str
    evidence: str
    gold_sql: str
    difficulty: str = _DIFFICULTY_SIMPLE


def _compute_stratified_quotas(counts_by_db: Dict[str, int], n: int) -> Dict[str, int]:
    """Integer quotas per database proportional to counts, capped by availability.

    Uses Hamilton / largest-remainder, then fills any deficit against DBs with spare rows.

    Args:
        counts_by_db: Number of questions available per ``db_id``.
        n: Target total sample size.

    Returns:
        Quotas per ``db_id`` summing to ``min(n, total_available)``.
    """
    total = sum(counts_by_db.values())
    if total == 0:
        return {}
    n = min(n, total)
    if n == total:
        return dict(counts_by_db)

    dbs = sorted(counts_by_db.keys())
    ideal = {d: n * counts_by_db[d] / total for d in dbs}
    quotas = {d: min(int(math.floor(ideal[d])), counts_by_db[d]) for d in dbs}
    deficit = n - sum(quotas.values())

    # Largest remainder among DBs that still have headroom
    while deficit > 0:
        candidates = [
            (ideal[d] - quotas[d], d)
            for d in dbs
            if quotas[d] < counts_by_db[d]
        ]
        if not candidates:
            break
        _, pick = max(candidates, key=lambda x: (x[0], x[1]))
        quotas[pick] += 1
        deficit -= 1

    return quotas


def stratified_sample_questions(
    questions: List[BIRDQuestion],
    n: int,
    seed: int = 42,
) -> Tuple[List[BIRDQuestion], Dict[str, int]]:
    """Sample ``n`` questions with proportional allocation per ``db_id``.

    Args:
        questions: Full pool (e.g. all Mini-Dev SQLite questions).
        n: Target sample size (capped at ``len(questions)``).
        seed: RNG seed for reproducible draws within each stratum.

    Returns:
        Tuple of (selected questions sorted by ``question_id``, allocation map db_id -> count).
    """
    if n <= 0:
        return [], {}

    by_db: Dict[str, List[BIRDQuestion]] = defaultdict(list)
    for q in questions:
        by_db[q.db_id].append(q)

    counts = {d: len(by_db[d]) for d in by_db}
    quotas = _compute_stratified_quotas(counts, n)

    rng = random.Random(seed)
    selected: List[BIRDQuestion] = []
    allocation: Dict[str, int] = {}

    for db_id, quota in sorted(quotas.items()):
        pool = list(by_db[db_id])
        rng.shuffle(pool)
        take = pool[:quota]
        selected.extend(take)
        if take:
            allocation[db_id] = len(take)

    selected.sort(key=lambda q: q.question_id)
    return selected, allocation


@dataclass
class BIRDDatasetManager:
    """Manages BIRD Mini-Dev dataset download, storage, and access.

    Supports two data sources:
    1. HuggingFace datasets library (preferred, automatic)
    2. Local directory with pre-downloaded data

    Args:
        data_dir: Root directory for BIRD data storage.
        use_huggingface: Whether to download from HuggingFace (requires `datasets` package).
    """

    data_dir: str = "./benchmarks/bird/data"
    use_huggingface: bool = True
    _questions: List[BIRDQuestion] = field(default_factory=list, repr=False)
    _gold_sqls: Dict[int, str] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self.data_dir = str(Path(self.data_dir).resolve())
        self.db_dir = os.path.join(self.data_dir, "dev_databases")
        self.questions_file = os.path.join(self.data_dir, "mini_dev_sqlite.json")
        self.gold_sql_file = os.path.join(self.data_dir, "mini_dev_sqlite_gold.sql")
        self.difficulty_file = os.path.join(self.data_dir, "mini_dev_sqlite.jsonl")

    def setup(self) -> bool:
        """Download and prepare the BIRD Mini-Dev dataset.

        Returns:
            True if setup completed successfully.

        Raises:
            RuntimeError: If dataset download or preparation fails.
        """
        os.makedirs(self.data_dir, exist_ok=True)

        if self._is_ready():
            logger.info("BIRD Mini-Dev dataset already available at %s", self.data_dir)
            return True

        if self.use_huggingface:
            return self._download_from_huggingface()
        else:
            return self._validate_local_data()

    def _is_ready(self) -> bool:
        """Check if dataset files and databases are already present."""
        if not os.path.exists(self.questions_file):
            return False
        if not os.path.exists(self.gold_sql_file):
            return False
        if not os.path.isdir(self.db_dir):
            return False

        db_count = sum(
            1
            for d in os.listdir(self.db_dir)
            if os.path.isdir(os.path.join(self.db_dir, d))
            and os.path.exists(
                os.path.join(self.db_dir, d, f"{d}.sqlite")
            )
        )
        return db_count >= len(BIRD_DATABASES)

    def _download_from_huggingface(self) -> bool:
        """Download BIRD Mini-Dev from HuggingFace datasets."""
        try:
            from datasets import load_dataset
        except ImportError:
            raise RuntimeError(
                "The 'datasets' package is required for HuggingFace download. "
                "Install it with: pip install datasets\n"
                "Alternatively, download the dataset manually from:\n"
                "https://drive.google.com/file/d/13VLWIwpw5E3d5DUkMvzw7hvHE67a4XkG/view\n"
                "and extract to: " + self.data_dir
            )

        logger.info("Downloading BIRD Mini-Dev from HuggingFace...")

        # Corporate proxies (e.g., Zscaler) require a custom CA bundle.
        # Set SSL_CERT_FILE / REQUESTS_CA_BUNDLE *before* running the
        # benchmark (or pass --ca-bundle to run_benchmark.py) instead of
        # disabling certificate verification globally.
        dataset = load_dataset(BIRD_MINI_DEV_HF_DATASET)

        sqlite_split = dataset["mini_dev_sqlite"]

        questions = []
        gold_lines = []
        jsonl_lines = []

        for idx, item in enumerate(sqlite_split):
            question_entry = {
                _FIELD_QUESTION_ID: idx,
                _FIELD_DB_ID: item[_FIELD_DB_ID],
                _FIELD_QUESTION: item[_FIELD_QUESTION],
                _FIELD_EVIDENCE: item.get(_FIELD_EVIDENCE, ""),
                "SQL": item["SQL"],
                _FIELD_DIFFICULTY: item.get(_FIELD_DIFFICULTY, _DIFFICULTY_SIMPLE),
            }
            questions.append(question_entry)
            gold_lines.append(f"{item['SQL']}\t{item['db_id']}")
            jsonl_lines.append(json.dumps({
                _FIELD_QUESTION_ID: idx,
                _FIELD_DB_ID: item[_FIELD_DB_ID],
                _FIELD_DIFFICULTY: item.get(_FIELD_DIFFICULTY, _DIFFICULTY_SIMPLE),
            }))

        with open(self.questions_file, "w") as f:
            json.dump(questions, f, indent=2)

        with open(self.gold_sql_file, "w") as f:
            f.write("\n".join(gold_lines) + "\n")

        with open(self.difficulty_file, "w") as f:
            f.write("\n".join(jsonl_lines) + "\n")

        logger.info(
            "Saved %d questions to %s", len(questions), self.questions_file
        )

        if not os.path.isdir(self.db_dir) or not self._databases_present():
            logger.warning(
                "HuggingFace dataset does not include SQLite database files.\n"
                "Please download the complete package from:\n"
                "  https://drive.google.com/file/d/13VLWIwpw5E3d5DUkMvzw7hvHE67a4XkG/view\n"
                "Extract the dev_databases/ folder to: %s",
                self.db_dir,
            )
            return False

        return True

    def _databases_present(self) -> bool:
        """Check if all required SQLite databases are present."""
        if not os.path.isdir(self.db_dir):
            return False
        for db_name in BIRD_DATABASES:
            db_path = os.path.join(self.db_dir, db_name, f"{db_name}.sqlite")
            if not os.path.exists(db_path):
                return False
        return True

    def _validate_local_data(self) -> bool:
        """Validate that local data directory has all required files."""
        missing = []
        if not os.path.exists(self.questions_file):
            missing.append(self.questions_file)
        if not os.path.exists(self.gold_sql_file):
            missing.append(self.gold_sql_file)
        if not self._databases_present():
            missing.append(f"{self.db_dir}/<db_name>/<db_name>.sqlite")

        if missing:
            raise RuntimeError(
                "Missing required BIRD data files:\n"
                + "\n".join(f"  - {m}" for m in missing)
                + "\n\nDownload the complete package from:\n"
                "  https://drive.google.com/file/d/13VLWIwpw5E3d5DUkMvzw7hvHE67a4XkG/view\n"
                f"Extract to: {self.data_dir}"
            )
        return True

    def _load_difficulty_map(self) -> Dict[int, str]:
        """Load question difficulty labels from the difficulty JSONL file."""
        difficulty_map: Dict[int, str] = {}
        if not os.path.exists(self.difficulty_file):
            return difficulty_map
        with open(self.difficulty_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    entry = json.loads(line)
                    difficulty_map[entry[_FIELD_QUESTION_ID]] = entry.get(_FIELD_DIFFICULTY, _DIFFICULTY_SIMPLE)
        return difficulty_map

    def load_questions(self, db_filter: Optional[str] = None, limit: Optional[int] = None) -> List[BIRDQuestion]:
        """Load BIRD questions from the dataset.

        Args:
            db_filter: Only load questions for this database (e.g., "financial").
            limit: Maximum number of questions to load.

        Returns:
            List of BIRDQuestion instances.
        """
        if self._questions and not db_filter and not limit:
            return self._questions

        with open(self.questions_file, "r") as f:
            raw_questions = json.load(f)

        difficulty_map = self._load_difficulty_map()

        questions = []
        for idx, q in enumerate(raw_questions):
            if db_filter and q[_FIELD_DB_ID] != db_filter:
                continue

            difficulty = difficulty_map.get(idx, q.get(_FIELD_DIFFICULTY, _DIFFICULTY_SIMPLE))

            questions.append(BIRDQuestion(
                question_id=idx,
                db_id=q[_FIELD_DB_ID],
                question=q[_FIELD_QUESTION],
                evidence=q.get(_FIELD_EVIDENCE, ""),
                gold_sql=q["SQL"],
                difficulty=difficulty,
            ))

            if limit and len(questions) >= limit:
                break

        if not db_filter and not limit:
            self._questions = questions

        logger.info("Loaded %d BIRD questions", len(questions))
        return questions

    def load_questions_stratified(
        self,
        total: int,
        seed: int = 42,
    ) -> Tuple[List[BIRDQuestion], Dict[str, int]]:
        """Load a stratified sample across all databases (proportional per ``db_id``).

        Use this for cost-controlled runs that still cover every Mini-Dev database
        (e.g. 100 questions spread across the 11 SQLite schemas).

        Args:
            total: Target number of questions (capped at full dataset size).
            seed: RNG seed for reproducible sampling.

        Returns:
            Tuple of (questions, allocation map ``db_id`` -> count in sample).
        """
        all_questions = self.load_questions(db_filter=None, limit=None)
        sampled, allocation = stratified_sample_questions(all_questions, total, seed=seed)
        logger.info(
            "Stratified sample: %d questions across %d databases (seed=%s)",
            len(sampled),
            len(allocation),
            seed,
        )
        return sampled, allocation

    def get_db_path(self, db_id: str) -> str:
        """Get the SQLite database file path for a given database ID.

        Args:
            db_id: BIRD database identifier (e.g., "financial").

        Returns:
            Absolute path to the SQLite database file.

        Raises:
            FileNotFoundError: If the database file doesn't exist.
        """
        db_path = os.path.join(self.db_dir, db_id, f"{db_id}.sqlite")
        if not os.path.exists(db_path):
            raise FileNotFoundError(
                f"BIRD database not found: {db_path}\n"
                "Run setup() first or download the databases manually."
            )
        return db_path

    def get_connection_string(self, db_id: str) -> str:
        """Get SQLAlchemy connection string for a BIRD database.

        Args:
            db_id: BIRD database identifier.

        Returns:
            SQLAlchemy-compatible connection string.
        """
        db_path = self.get_db_path(db_id)
        return f"sqlite:///{db_path}"

    def get_schema_info(self, db_id: str) -> str:
        """Get schema information for a BIRD database (for debugging).

        Args:
            db_id: BIRD database identifier.

        Returns:
            Human-readable schema description.
        """
        db_path = self.get_db_path(db_id)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = [row[0] for row in cursor.fetchall()]

        schema_parts = [f"Database: {db_id}", f"Tables: {len(tables)}", ""]
        _SAFE_IDENTIFIER = re.compile(r"^[\w]+$")
        for table in tables:
            if not _SAFE_IDENTIFIER.match(table):
                continue
            cursor.execute(f'PRAGMA table_info("{table}");')
            columns = cursor.fetchall()
            col_strs = [f"  {col[1]} ({col[2]})" for col in columns]
            schema_parts.append(f"{table}:")
            schema_parts.extend(col_strs)
            schema_parts.append("")

        conn.close()
        return "\n".join(schema_parts)

    def get_gold_sqls(self) -> Dict[int, str]:
        """Load gold standard SQL queries.

        Returns:
            Dictionary mapping question index to gold SQL string.
        """
        if self._gold_sqls:
            return self._gold_sqls

        with open(self.gold_sql_file, "r") as f:
            for idx, line in enumerate(f):
                line = line.strip()
                if line:
                    parts = line.split("\t")
                    self._gold_sqls[idx] = parts[0]

        return self._gold_sqls
