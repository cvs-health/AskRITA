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
Research Agent module for AskRITA.

CRISP-DM research workflow using SQL Agent as the data foundation.
"""

from .ResearchAgent import AssumptionAnalysis  # Backwards compatibility alias
from .ResearchAgent import (
    BusinessUnderstandingOutput,
    DataUnderstandingOutput,
    DeploymentOutput,
    EvaluationOutput,
    ModelingOutput,
    ResearchAgent,
    ResearchWorkflowState,
)
from .SchemaAnalyzer import (
    ColumnAnalysis,
    SchemaAnalysisReport,
    SchemaAnalyzer,
    TableAnalysis,
)
from .StatisticalAnalyzer import (
    DescriptiveStats,
    StatisticalAnalyzer,
    StatisticalResult,
)

__all__ = [
    # Main agent
    "ResearchAgent",
    # Workflow models
    "ResearchWorkflowState",
    "BusinessUnderstandingOutput",
    "DataUnderstandingOutput",
    "ModelingOutput",
    "EvaluationOutput",
    "DeploymentOutput",
    "AssumptionAnalysis",
    # Schema analysis
    "SchemaAnalyzer",
    "SchemaAnalysisReport",
    "TableAnalysis",
    "ColumnAnalysis",
    # Statistical analysis (REAL computation)
    "StatisticalAnalyzer",
    "StatisticalResult",
    "DescriptiveStats",
]
