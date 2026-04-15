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

"""BIRD Mini-Interact benchmark evaluation for askRITA.

BIRD Mini-Interact is a multi-turn interactive text-to-SQL benchmark
(300 tasks, SQLite, no Docker) where each task starts with an ambiguous
user query that must be clarified through dialogue before SQL generation.

This module provides:
- Dataset download and setup from HuggingFace
- Multi-turn conversation runner (askRITA + user simulator)
- Test-case based evaluation with reward scoring
- Results reporting with per-database breakdown

Reference: https://bird-interact.github.io/
"""

from .evaluate import MiniInteractEvaluator
from .runner import MiniInteractRunner
from .setup_data import MiniInteractDataManager, MiniInteractTask
from .user_simulator import UserSimulator

__all__ = [
    "MiniInteractDataManager",
    "MiniInteractEvaluator",
    "MiniInteractRunner",
    "MiniInteractTask",
    "UserSimulator",
]
