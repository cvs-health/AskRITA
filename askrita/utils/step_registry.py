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
Step Registry System for Chain of Thoughts tracking.

This module provides a centralized registry for managing workflow steps,
their types, and reasoning templates in a more maintainable way.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class StepInfo:
    """Information about a workflow step."""

    name: str
    step_type: str  # 'analysis', 'generation', 'validation', 'execution', 'formatting'
    reasoning_template: Dict[str, str] = field(default_factory=dict)
    description: str = ""
    enabled: bool = True


class StepRegistry:
    """
    Centralized registry for workflow steps and their metadata.

    This class manages step definitions, types, and reasoning templates
    in a more maintainable and extensible way.
    """

    def __init__(self):
        self._steps: Dict[str, StepInfo] = {}
        self._default_type = "unknown"
        self._initialize_default_steps()

    def _initialize_default_steps(self):
        """Initialize the registry with default workflow steps."""
        default_steps = [
            StepInfo(
                name="parse_question",
                step_type="analysis",
                description="Analyze natural language question to identify relevant database elements",
                reasoning_template={
                    "start": "Analyzing the natural language question to identify relevant database tables and columns",
                    "success": "Successfully identified {table_count} relevant tables and extracted key information",
                    "failure": "Failed to parse the question due to: {error}",
                },
            ),
            StepInfo(
                name="get_unique_nouns",
                step_type="analysis",
                description="Extract unique values from relevant columns to improve query accuracy",
                reasoning_template={
                    "start": "Extracting unique values from relevant columns to improve query accuracy",
                    "success": "Found {noun_count} unique values that will help generate precise SQL",
                    "failure": "Could not extract unique nouns: {error}",
                },
            ),
            StepInfo(
                name="generate_sql",
                step_type="generation",
                description="Generate SQL query based on question analysis and database schema",
                reasoning_template={
                    "start": "Generating SQL query based on question analysis and database schema",
                    "success": "Generated SQL query with {complexity} complexity targeting {tables}",
                    "failure": "SQL generation failed: {error}",
                },
            ),
            StepInfo(
                name="validate_and_fix_sql",
                step_type="validation",
                description="Validate generated SQL for syntax, safety, and optimization opportunities",
                reasoning_template={
                    "start": "Validating generated SQL for syntax, safety, and optimization opportunities",
                    "success": "SQL validated successfully{fixes}",
                    "failure": "SQL validation failed: {error}",
                },
            ),
            StepInfo(
                name="execute_sql",
                step_type="execution",
                description="Execute validated SQL query against the database",
                reasoning_template={
                    "start": "Executing validated SQL query against the database",
                    "success": "Query executed successfully, returned {row_count} rows in {duration}ms",
                    "failure": "Query execution failed: {error}",
                },
            ),
            StepInfo(
                name="format_results",
                step_type="formatting",
                description="Format query results into a comprehensive natural language response",
                reasoning_template={
                    "start": "Formatting query results into a comprehensive natural language response",
                    "success": "Formatted results into {format_type} with {insight_count} key insights",
                    "failure": "Result formatting failed: {error}",
                },
            ),
            StepInfo(
                name="choose_visualization",
                step_type="analysis",
                description="Analyze data characteristics to recommend optimal visualization",
                reasoning_template={
                    "start": "Analyzing data characteristics to recommend optimal visualization",
                    "success": "Recommended {chart_type} visualization based on {criteria}",
                    "failure": "Visualization selection failed: {error}",
                },
            ),
            StepInfo(
                name="format_data_for_visualization",
                step_type="formatting",
                description="Transform query results into chart-ready data format",
                reasoning_template={
                    "start": "Transforming query results into chart-ready data format",
                    "success": "Formatted {data_points} data points for {chart_type} chart",
                    "failure": "Data formatting for visualization failed: {error}",
                },
            ),
            StepInfo(
                name="generate_followup_questions",
                step_type="generation",
                description="Generate strategic follow-up questions based on results and context",
                reasoning_template={
                    "start": "Generating strategic follow-up questions based on results and context",
                    "success": "Generated {question_count} relevant follow-up questions",
                    "failure": "Follow-up question generation failed: {error}",
                },
            ),
        ]

        for step in default_steps:
            self.register_step(step)

    def register_step(self, step_info: StepInfo) -> None:
        """
        Register a workflow step with its metadata.

        Args:
            step_info: StepInfo object containing step metadata
        """
        self._steps[step_info.name] = step_info
        logger.debug(f"Registered step: {step_info.name} ({step_info.step_type})")

    def register_step_simple(
        self,
        name: str,
        step_type: str,
        reasoning_template: Optional[Dict[str, str]] = None,
        description: str = "",
        enabled: bool = True,
    ) -> None:
        """
        Register a step with simplified parameters.

        Args:
            name: Step name
            step_type: Type of step ('analysis', 'generation', etc.)
            reasoning_template: Optional reasoning templates
            description: Step description
            enabled: Whether the step is enabled
        """
        step_info = StepInfo(
            name=name,
            step_type=step_type,
            reasoning_template=reasoning_template or {},
            description=description,
            enabled=enabled,
        )
        self.register_step(step_info)

    def get_step_info(self, name: str) -> Optional[StepInfo]:
        """
        Get step information by name.

        Args:
            name: Step name

        Returns:
            StepInfo object or None if not found
        """
        return self._steps.get(name)

    def get_step_type(self, name: str) -> str:
        """
        Get step type by name.

        Args:
            name: Step name

        Returns:
            Step type or default type if not found
        """
        step_info = self.get_step_info(name)
        return step_info.step_type if step_info else self._default_type

    def get_reasoning_template(self, name: str) -> Dict[str, str]:
        """
        Get reasoning template for a step.

        Args:
            name: Step name

        Returns:
            Reasoning template dictionary
        """
        step_info = self.get_step_info(name)
        return step_info.reasoning_template if step_info else {}

    def get_all_steps(self) -> Dict[str, StepInfo]:
        """Get all registered steps."""
        return self._steps.copy()

    def get_steps_by_type(self, step_type: str) -> List[StepInfo]:
        """
        Get all steps of a specific type.

        Args:
            step_type: Type to filter by

        Returns:
            List of StepInfo objects
        """
        return [step for step in self._steps.values() if step.step_type == step_type]

    def is_step_enabled(self, name: str) -> bool:
        """
        Check if a step is enabled.

        Args:
            name: Step name

        Returns:
            True if step is enabled, False otherwise
        """
        step_info = self.get_step_info(name)
        return step_info.enabled if step_info else True

    def enable_step(self, name: str) -> bool:
        """
        Enable a step.

        Args:
            name: Step name

        Returns:
            True if step was found and enabled, False otherwise
        """
        step_info = self.get_step_info(name)
        if step_info:
            step_info.enabled = True
            return True
        return False

    def disable_step(self, name: str) -> bool:
        """
        Disable a step.

        Args:
            name: Step name

        Returns:
            True if step was found and disabled, False otherwise
        """
        step_info = self.get_step_info(name)
        if step_info:
            step_info.enabled = False
            return True
        return False

    def unregister_step(self, name: str) -> bool:
        """
        Unregister a step.

        Args:
            name: Step name

        Returns:
            True if step was found and removed, False otherwise
        """
        if name in self._steps:
            del self._steps[name]
            logger.debug(f"Unregistered step: {name}")
            return True
        return False

    def get_step_statistics(self) -> Dict[str, Any]:
        """Get statistics about registered steps."""
        total_steps = len(self._steps)
        enabled_steps = len([s for s in self._steps.values() if s.enabled])

        type_counts = {}
        for step in self._steps.values():
            type_counts[step.step_type] = type_counts.get(step.step_type, 0) + 1

        return {
            "total_steps": total_steps,
            "enabled_steps": enabled_steps,
            "disabled_steps": total_steps - enabled_steps,
            "type_distribution": type_counts,
        }


# Global registry instance
_global_registry = StepRegistry()


def get_step_registry() -> StepRegistry:
    """Get the global step registry instance."""
    return _global_registry


def register_step(
    name: str,
    step_type: str,
    reasoning_template: Optional[Dict[str, str]] = None,
    description: str = "",
    enabled: bool = True,
) -> None:
    """
    Register a step in the global registry.

    Args:
        name: Step name
        step_type: Type of step
        reasoning_template: Optional reasoning templates
        description: Step description
        enabled: Whether the step is enabled
    """
    _global_registry.register_step_simple(
        name, step_type, reasoning_template, description, enabled
    )


def get_step_type(name: str) -> str:
    """
    Get step type from global registry.

    Args:
        name: Step name

    Returns:
        Step type
    """
    return _global_registry.get_step_type(name)


def get_reasoning_template(name: str) -> Dict[str, str]:
    """
    Get reasoning template from global registry.

    Args:
        name: Step name

    Returns:
        Reasoning template dictionary
    """
    return _global_registry.get_reasoning_template(name)
