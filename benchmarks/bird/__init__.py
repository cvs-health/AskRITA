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

"""BIRD benchmark evaluation for askRITA text-to-SQL framework.

BIRD (BIg Bench for LaRge-scale Database Grounded Text-to-SQL) is a cross-domain
benchmark that evaluates text-to-SQL systems against real-world databases with
dirty values, external knowledge, and efficiency requirements.

This module provides:
- Dataset download and setup (BIRD Mini-Dev, 500 instances)
- Benchmark runner that feeds BIRD questions through askRITA
- BIRD-compatible evaluation metrics (EX, Soft F1, R-VES)
- Results reporting with difficulty-level breakdown

Reference: https://bird-bench.github.io/
"""

from .evaluate import BIRDEvaluator
from .runner import BIRDBenchmarkRunner
from .setup_data import BIRDDatasetManager

__all__ = [
    "BIRDBenchmarkRunner",
    "BIRDEvaluator",
    "BIRDDatasetManager",
]
