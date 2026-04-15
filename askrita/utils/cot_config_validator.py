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
Configuration Validator for Chain of Thoughts.

This module provides validation for chain of thoughts configuration
to ensure proper setup and prevent runtime errors.
"""

import logging
from typing import Any, Dict, List

from ..config_manager import ChainOfThoughtsConfig

logger = logging.getLogger(__name__)


class CoTConfigValidationError(Exception):
    """Exception raised when chain of thoughts configuration is invalid."""

    pass


class CoTConfigValidator:
    """
    Validator for chain of thoughts configuration.

    This class provides comprehensive validation for CoT configuration
    to ensure proper setup and prevent runtime issues.
    """

    def __init__(self):
        self.validation_rules = {
            "max_reasoning_length": self._validate_max_reasoning_length,
            "display_preferences": self._validate_display_preferences,
            "enabled": self._validate_enabled,
            "include_timing": self._validate_include_timing,
            "include_confidence": self._validate_include_confidence,
            "include_step_details": self._validate_include_step_details,
            "track_retries": self._validate_track_retries,
        }

    def validate_config(self, config: ChainOfThoughtsConfig) -> List[str]:
        """
        Validate chain of thoughts configuration.

        Args:
            config: ChainOfThoughtsConfig instance to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Validate each configuration field
        for field_name, validator in self.validation_rules.items():
            try:
                field_value = getattr(config, field_name, None)
                field_errors = validator(field_value, field_name)
                errors.extend(field_errors)
            except Exception as e:
                errors.append(f"Error validating {field_name}: {str(e)}")

        # Cross-field validation
        cross_errors = self._validate_cross_fields(config)
        errors.extend(cross_errors)

        return errors

    def _validate_max_reasoning_length(self, value: Any, field_name: str) -> List[str]:
        """Validate max_reasoning_length field."""
        errors = []

        if not isinstance(value, int):
            errors.append(f"{field_name} must be an integer")
            return errors

        if value < 50:
            errors.append(f"{field_name} must be at least 50 characters")

        if value > 10000:
            errors.append(
                f"{field_name} should not exceed 10000 characters (performance impact)"
            )

        if value < 100:
            logger.warning(
                f"{field_name} is very small ({value}), may limit reasoning detail"
            )

        return errors

    def _validate_display_preferences(self, value: Any, field_name: str) -> List[str]:
        """Validate display_preferences field."""
        errors = []

        if not isinstance(value, dict):
            errors.append(f"{field_name} must be a dictionary")
            return errors

        # Required display preference keys
        required_keys = {
            "show_successful_steps",
            "show_failed_steps",
            "show_skipped_steps",
            "collapse_successful_steps",
            "highlight_failed_steps",
            "show_step_timing",
            "show_confidence_scores",
        }

        # Check for required keys
        missing_keys = required_keys - set(value.keys())
        if missing_keys:
            errors.append(f"{field_name} missing required keys: {missing_keys}")

        # Validate each preference value
        for key, pref_value in value.items():
            if not isinstance(pref_value, bool):
                errors.append(f"{field_name}.{key} must be a boolean value")

        # Validate logical combinations
        if value.get("show_step_timing", False) and not value.get(
            "include_timing", True
        ):
            errors.append("show_step_timing requires include_timing to be enabled")

        if value.get("show_confidence_scores", False) and not value.get(
            "include_confidence", True
        ):
            errors.append(
                "show_confidence_scores requires include_confidence to be enabled"
            )

        return errors

    def _validate_enabled(self, value: Any, field_name: str) -> List[str]:
        """Validate enabled field."""
        errors = []

        if not isinstance(value, bool):
            errors.append(f"{field_name} must be a boolean value")

        return errors

    def _validate_include_timing(self, value: Any, field_name: str) -> List[str]:
        """Validate include_timing field."""
        errors = []

        if not isinstance(value, bool):
            errors.append(f"{field_name} must be a boolean value")

        return errors

    def _validate_include_confidence(self, value: Any, field_name: str) -> List[str]:
        """Validate include_confidence field."""
        errors = []

        if not isinstance(value, bool):
            errors.append(f"{field_name} must be a boolean value")

        return errors

    def _validate_include_step_details(self, value: Any, field_name: str) -> List[str]:
        """Validate include_step_details field."""
        errors = []

        if not isinstance(value, bool):
            errors.append(f"{field_name} must be a boolean value")

        return errors

    def _validate_track_retries(self, value: Any, field_name: str) -> List[str]:
        """Validate track_retries field."""
        errors = []

        if not isinstance(value, bool):
            errors.append(f"{field_name} must be a boolean value")

        return errors

    def _check_display_preferences_consistency(
        self, config: ChainOfThoughtsConfig, errors: List[str]
    ) -> None:
        """Validate display preference consistency when CoT is enabled."""
        display_prefs = config.display_preferences
        if display_prefs.get("show_step_timing", False) and not config.include_timing:
            errors.append("Cannot show step timing when include_timing is disabled")
        if (
            display_prefs.get("show_confidence_scores", False)
            and not config.include_confidence
        ):
            errors.append(
                "Cannot show confidence scores when include_confidence is disabled"
            )
        if (
            display_prefs.get("show_step_details", False)
            and not config.include_step_details
        ):
            logger.warning("Showing step details but include_step_details is disabled")

    def _validate_cross_fields(self, config: ChainOfThoughtsConfig) -> List[str]:
        """Validate cross-field dependencies and logical consistency."""
        errors = []

        if not config.enabled:
            if (
                config.include_timing
                or config.include_confidence
                or config.include_step_details
            ):
                logger.warning(
                    "Chain of thoughts is disabled but timing/confidence/details are enabled"
                )

        if (
            config.enabled
            and config.include_step_details
            and config.max_reasoning_length > 2000
        ):
            logger.warning(
                "Large max_reasoning_length with detailed step tracking may impact performance"
            )

        if config.enabled:
            self._check_display_preferences_consistency(config, errors)

        return errors

    def validate_and_fix_config(
        self, config: ChainOfThoughtsConfig
    ) -> ChainOfThoughtsConfig:
        """
        Validate configuration and attempt to fix common issues.

        Args:
            config: ChainOfThoughtsConfig instance to validate and fix

        Returns:
            Fixed ChainOfThoughtsConfig instance

        Raises:
            CoTConfigValidationError: If configuration cannot be fixed
        """
        errors = self.validate_config(config)

        if not errors:
            return config

        # Attempt to fix common issues
        fixed_config = self._create_fixed_config(config)

        # Validate the fixed configuration
        fixed_errors = self.validate_config(fixed_config)

        if fixed_errors:
            raise CoTConfigValidationError(
                f"Configuration validation failed and could not be auto-fixed. "
                f"Errors: {fixed_errors}"
            )

        logger.info("Chain of thoughts configuration was automatically fixed")
        return fixed_config

    def _create_fixed_config(
        self, config: ChainOfThoughtsConfig
    ) -> ChainOfThoughtsConfig:
        """Create a fixed version of the configuration."""
        from dataclasses import replace

        # Fix max_reasoning_length
        max_reasoning_length = self._fix_max_reasoning_length(
            config.max_reasoning_length
        )

        # Fix display_preferences
        display_preferences = self._fix_display_preferences(config.display_preferences)

        # Fix boolean fields
        boolean_fields = self._fix_boolean_fields(config)

        return replace(
            config,
            enabled=boolean_fields["enabled"],
            include_timing=boolean_fields["include_timing"],
            include_confidence=boolean_fields["include_confidence"],
            include_step_details=boolean_fields["include_step_details"],
            track_retries=boolean_fields["track_retries"],
            max_reasoning_length=max_reasoning_length,
            display_preferences=display_preferences,
        )

    def _fix_max_reasoning_length(self, value: Any) -> int:
        """Fix max_reasoning_length field."""
        if not isinstance(value, int):
            return 500
        elif value < 50:
            return 50
        elif value > 10000:
            return 10000
        return value

    def _fix_display_preferences(self, preferences: Dict[str, Any]) -> Dict[str, bool]:
        """Fix display_preferences field."""
        fixed_preferences = preferences.copy() if preferences else {}

        # Ensure all required keys exist with default values
        default_preferences = {
            "show_successful_steps": True,
            "show_failed_steps": True,
            "show_skipped_steps": True,
            "collapse_successful_steps": False,
            "highlight_failed_steps": True,
            "show_step_timing": True,
            "show_confidence_scores": True,
        }

        for key, default_value in default_preferences.items():
            if key not in fixed_preferences or not isinstance(
                fixed_preferences[key], bool
            ):
                fixed_preferences[key] = default_value

        return fixed_preferences

    def _fix_boolean_fields(self, config: ChainOfThoughtsConfig) -> Dict[str, bool]:
        """Fix boolean configuration fields."""
        return {
            "enabled": self._fix_boolean_value(config.enabled, True),
            "include_timing": self._fix_boolean_value(config.include_timing, True),
            "include_confidence": self._fix_boolean_value(
                config.include_confidence, True
            ),
            "include_step_details": self._fix_boolean_value(
                config.include_step_details, False
            ),
            "track_retries": self._fix_boolean_value(config.track_retries, True),
        }

    def _fix_boolean_value(self, value: Any, default: bool) -> bool:
        """Fix a single boolean value."""
        if isinstance(value, bool):
            return value
        elif isinstance(value, (int, str)):
            return bool(value)
        return default

    def get_configuration_recommendations(
        self, config: ChainOfThoughtsConfig
    ) -> List[str]:
        """
        Get recommendations for optimizing the configuration.

        Args:
            config: ChainOfThoughtsConfig instance

        Returns:
            List of optimization recommendations
        """
        recommendations = []

        # Performance recommendations
        if (
            config.enabled
            and config.include_step_details
            and config.max_reasoning_length > 2000
        ):
            recommendations.append(
                "Consider reducing max_reasoning_length for better performance with detailed tracking"
            )

        if (
            config.enabled
            and config.include_timing
            and config.include_confidence
            and config.include_step_details
        ):
            recommendations.append(
                "All tracking features are enabled - consider disabling some for better performance"
            )

        # Usability recommendations
        if config.enabled and not config.display_preferences.get(
            "show_step_timing", False
        ):
            recommendations.append(
                "Consider enabling show_step_timing to see step performance"
            )

        if config.enabled and not config.display_preferences.get(
            "highlight_failed_steps", False
        ):
            recommendations.append(
                "Consider enabling highlight_failed_steps for better error visibility"
            )

        # Development recommendations
        if not config.enabled:
            recommendations.append(
                "Chain of thoughts is disabled - enable for debugging and transparency"
            )

        return recommendations


def validate_cot_config(config: ChainOfThoughtsConfig) -> List[str]:
    """
    Convenience function to validate chain of thoughts configuration.

    Args:
        config: ChainOfThoughtsConfig instance to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    validator = CoTConfigValidator()
    return validator.validate_config(config)


def validate_and_fix_cot_config(config: ChainOfThoughtsConfig) -> ChainOfThoughtsConfig:
    """
    Convenience function to validate and fix chain of thoughts configuration.

    Args:
        config: ChainOfThoughtsConfig instance to validate and fix

    Returns:
        Fixed ChainOfThoughtsConfig instance

    Raises:
        CoTConfigValidationError: If configuration cannot be fixed
    """
    validator = CoTConfigValidator()
    return validator.validate_and_fix_config(config)
