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

"""
Workflow management module for AskRITA SQLAgent.

This module contains workflow orchestration components for both SQL and NoSQL agent operations.

Classes:
    SQLAgentWorkflow: Main workflow orchestration class for SQL agent operations
    NoSQLAgentWorkflow: Workflow orchestration for NoSQL (MongoDB) agent operations
"""

from .NoSQLAgentWorkflow import NoSQLAgentWorkflow
from .SQLAgentWorkflow import SQLAgentWorkflow

__all__ = [
    "SQLAgentWorkflow",
    "NoSQLAgentWorkflow",
]
