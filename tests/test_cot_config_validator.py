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
#   pytest (MIT)

"""Comprehensive tests for CoTConfigValidator."""

import pytest

from askrita.config_manager import ChainOfThoughtsConfig
from askrita.utils.cot_config_validator import (
    CoTConfigValidationError,
    CoTConfigValidator,
    validate_and_fix_cot_config,
    validate_cot_config,
)


def _valid_config(**kwargs) -> ChainOfThoughtsConfig:
    """Return a valid ChainOfThoughtsConfig, optionally overriding fields."""
    defaults = dict(
        enabled=True,
        include_timing=True,
        include_confidence=True,
        include_step_details=False,
        track_retries=True,
        max_reasoning_length=500,
        display_preferences={
            "show_successful_steps": True,
            "show_failed_steps": True,
            "show_skipped_steps": True,
            "collapse_successful_steps": False,
            "highlight_failed_steps": True,
            "show_step_timing": True,
            "show_confidence_scores": True,
        },
    )
    defaults.update(kwargs)
    return ChainOfThoughtsConfig(**defaults)


class TestCoTConfigValidator:
    def setup_method(self):
        self.validator = CoTConfigValidator()

    # ------------------------------------------------------------------
    # validate_config – happy path
    # ------------------------------------------------------------------
    def test_valid_config_no_errors(self):
        config = _valid_config()
        errors = self.validator.validate_config(config)
        assert errors == []

    # ------------------------------------------------------------------
    # _validate_max_reasoning_length
    # ------------------------------------------------------------------
    def test_max_reasoning_length_not_int(self):
        errors = self.validator._validate_max_reasoning_length(
            "not_int", "max_reasoning_length"
        )
        assert any("integer" in e for e in errors)

    def test_max_reasoning_length_too_small(self):
        errors = self.validator._validate_max_reasoning_length(
            30, "max_reasoning_length"
        )
        assert any("at least 50" in e for e in errors)

    def test_max_reasoning_length_too_large(self):
        errors = self.validator._validate_max_reasoning_length(
            20000, "max_reasoning_length"
        )
        assert any("10000" in e for e in errors)

    def test_max_reasoning_length_small_warning(self):
        # Value between 50-99 triggers a warning but no error
        errors = self.validator._validate_max_reasoning_length(
            60, "max_reasoning_length"
        )
        assert errors == []

    def test_max_reasoning_length_valid(self):
        errors = self.validator._validate_max_reasoning_length(
            500, "max_reasoning_length"
        )
        assert errors == []

    # ------------------------------------------------------------------
    # _validate_display_preferences
    # ------------------------------------------------------------------
    def test_display_preferences_not_dict(self):
        errors = self.validator._validate_display_preferences(
            "bad", "display_preferences"
        )
        assert any("dictionary" in e for e in errors)

    def test_display_preferences_missing_keys(self):
        errors = self.validator._validate_display_preferences({}, "display_preferences")
        assert any("missing required keys" in e for e in errors)

    def test_display_preferences_non_bool_value(self):
        prefs = {
            "show_successful_steps": "yes",
            "show_failed_steps": True,
            "show_skipped_steps": True,
            "collapse_successful_steps": False,
            "highlight_failed_steps": True,
            "show_step_timing": True,
            "show_confidence_scores": True,
        }
        errors = self.validator._validate_display_preferences(
            prefs, "display_preferences"
        )
        assert any("boolean" in e for e in errors)

    def test_display_preferences_show_timing_without_include_timing(self):
        prefs = {
            "show_successful_steps": True,
            "show_failed_steps": True,
            "show_skipped_steps": True,
            "collapse_successful_steps": False,
            "highlight_failed_steps": True,
            "show_step_timing": True,
            "show_confidence_scores": True,
            "include_timing": False,  # triggers logical check
        }
        errors = self.validator._validate_display_preferences(
            prefs, "display_preferences"
        )
        # The check looks for show_step_timing=True AND include_timing=False
        assert any("include_timing" in e for e in errors)

    def test_display_preferences_show_confidence_without_include_confidence(self):
        prefs = {
            "show_successful_steps": True,
            "show_failed_steps": True,
            "show_skipped_steps": True,
            "collapse_successful_steps": False,
            "highlight_failed_steps": True,
            "show_step_timing": False,
            "show_confidence_scores": True,
            "include_confidence": False,
        }
        errors = self.validator._validate_display_preferences(
            prefs, "display_preferences"
        )
        assert any("include_confidence" in e for e in errors)

    def test_display_preferences_valid(self):
        prefs = {
            "show_successful_steps": True,
            "show_failed_steps": True,
            "show_skipped_steps": True,
            "collapse_successful_steps": False,
            "highlight_failed_steps": True,
            "show_step_timing": True,
            "show_confidence_scores": True,
        }
        errors = self.validator._validate_display_preferences(
            prefs, "display_preferences"
        )
        assert errors == []

    # ------------------------------------------------------------------
    # Boolean field validators
    # ------------------------------------------------------------------
    def test_validate_enabled_invalid(self):
        errors = self.validator._validate_enabled("yes", "enabled")
        assert any("boolean" in e for e in errors)

    def test_validate_enabled_valid(self):
        assert self.validator._validate_enabled(True, "enabled") == []

    def test_validate_include_timing_invalid(self):
        errors = self.validator._validate_include_timing(1, "include_timing")
        assert any("boolean" in e for e in errors)

    def test_validate_include_confidence_invalid(self):
        errors = self.validator._validate_include_confidence(None, "include_confidence")
        assert any("boolean" in e for e in errors)

    def test_validate_include_step_details_invalid(self):
        errors = self.validator._validate_include_step_details(
            "nope", "include_step_details"
        )
        assert any("boolean" in e for e in errors)

    def test_validate_track_retries_invalid(self):
        errors = self.validator._validate_track_retries(0, "track_retries")
        assert any("boolean" in e for e in errors)

    # ------------------------------------------------------------------
    # validate_config with bad field triggers except branch
    # ------------------------------------------------------------------
    def test_validate_config_exception_branch(self):
        """Validator should catch attribute errors gracefully."""
        config = _valid_config()
        # Patch a validator to raise
        original = self.validator.validation_rules["enabled"]
        self.validator.validation_rules["enabled"] = lambda v, n: (_ for _ in ()).throw(
            RuntimeError("boom")
        )
        try:
            errors = self.validator.validate_config(config)
            assert any("Error validating enabled" in e for e in errors)
        finally:
            self.validator.validation_rules["enabled"] = original

    # ------------------------------------------------------------------
    # _validate_cross_fields
    # ------------------------------------------------------------------
    def test_cross_fields_disabled_with_timing(self):
        """Disabled CoT with timing enabled triggers warning (no error)."""
        config = _valid_config(enabled=False, include_timing=True)
        errors = self.validator._validate_cross_fields(config)
        assert errors == []

    def test_cross_fields_show_step_timing_without_include_timing(self):
        prefs = {
            "show_successful_steps": True,
            "show_failed_steps": True,
            "show_skipped_steps": True,
            "collapse_successful_steps": False,
            "highlight_failed_steps": True,
            "show_step_timing": True,
            "show_confidence_scores": False,
        }
        config = _valid_config(
            enabled=True, include_timing=False, display_preferences=prefs
        )
        errors = self.validator._validate_cross_fields(config)
        assert any("step timing" in e.lower() for e in errors)

    def test_cross_fields_show_confidence_without_include_confidence(self):
        prefs = {
            "show_successful_steps": True,
            "show_failed_steps": True,
            "show_skipped_steps": True,
            "collapse_successful_steps": False,
            "highlight_failed_steps": True,
            "show_step_timing": False,
            "show_confidence_scores": True,
        }
        config = _valid_config(
            enabled=True, include_confidence=False, display_preferences=prefs
        )
        errors = self.validator._validate_cross_fields(config)
        assert any("confidence" in e.lower() for e in errors)

    def test_cross_fields_performance_warning(self):
        """Large max_reasoning_length with step_details triggers warning (no error)."""
        config = _valid_config(
            enabled=True, include_step_details=True, max_reasoning_length=5000
        )
        errors = self.validator._validate_cross_fields(config)
        assert errors == []  # just a warning, no error

    def test_cross_fields_show_step_details_warning(self):
        prefs = {
            "show_successful_steps": True,
            "show_failed_steps": True,
            "show_skipped_steps": True,
            "collapse_successful_steps": False,
            "highlight_failed_steps": True,
            "show_step_timing": False,
            "show_confidence_scores": False,
            "show_step_details": True,
        }
        config = _valid_config(
            enabled=True, include_step_details=False, display_preferences=prefs
        )
        errors = self.validator._validate_cross_fields(config)
        assert errors == []  # warning only

    # ------------------------------------------------------------------
    # validate_and_fix_config
    # ------------------------------------------------------------------
    def test_validate_and_fix_returns_same_when_valid(self):
        config = _valid_config()
        fixed = self.validator.validate_and_fix_config(config)
        assert fixed is config

    def test_validate_and_fix_repairs_max_reasoning_length(self):
        config = _valid_config(max_reasoning_length=10)
        fixed = self.validator.validate_and_fix_config(config)
        assert fixed.max_reasoning_length >= 50

    def test_validate_and_fix_repairs_max_reasoning_too_large(self):
        config = _valid_config(max_reasoning_length=99999)
        fixed = self.validator.validate_and_fix_config(config)
        assert fixed.max_reasoning_length <= 10000

    def test_validate_and_fix_raises_when_unfixable(self):
        """If auto-fix still produces errors, raise CoTConfigValidationError."""
        config = _valid_config()
        # Make validate_config always return errors even for the "fixed" config
        original_validate = self.validator.validate_config

        call_count = [0]

        def patched_validate(cfg):
            call_count[0] += 1
            # First call (original) returns errors; second call (fixed) also returns errors
            return ["unfixable error"]

        self.validator.validate_config = patched_validate
        try:
            with pytest.raises(CoTConfigValidationError):
                self.validator.validate_and_fix_config(config)
        finally:
            self.validator.validate_config = original_validate

    # ------------------------------------------------------------------
    # _fix_* helpers
    # ------------------------------------------------------------------
    def test_fix_max_reasoning_length_not_int(self):
        assert self.validator._fix_max_reasoning_length("bad") == 500

    def test_fix_max_reasoning_length_too_small(self):
        assert self.validator._fix_max_reasoning_length(10) == 50

    def test_fix_max_reasoning_length_too_large(self):
        assert self.validator._fix_max_reasoning_length(99999) == 10000

    def test_fix_max_reasoning_length_ok(self):
        assert self.validator._fix_max_reasoning_length(300) == 300

    def test_fix_display_preferences_none(self):
        result = self.validator._fix_display_preferences(None)
        assert "show_successful_steps" in result

    def test_fix_display_preferences_missing_key(self):
        prefs = {"show_successful_steps": True}
        result = self.validator._fix_display_preferences(prefs)
        assert "show_failed_steps" in result
        assert result["show_failed_steps"] is True

    def test_fix_display_preferences_non_bool_replaced(self):
        prefs = {"show_successful_steps": "yes"}
        result = self.validator._fix_display_preferences(prefs)
        assert isinstance(result["show_successful_steps"], bool)

    def test_fix_boolean_value_bool(self):
        assert self.validator._fix_boolean_value(True, False) is True
        assert self.validator._fix_boolean_value(False, True) is False

    def test_fix_boolean_value_int(self):
        assert self.validator._fix_boolean_value(1, False) is True
        assert self.validator._fix_boolean_value(0, True) is False

    def test_fix_boolean_value_str(self):
        assert self.validator._fix_boolean_value("yes", False) is True
        assert self.validator._fix_boolean_value("", True) is False

    def test_fix_boolean_value_fallback(self):
        assert self.validator._fix_boolean_value(None, True) is True
        assert self.validator._fix_boolean_value(None, False) is False

    # ------------------------------------------------------------------
    # get_configuration_recommendations
    # ------------------------------------------------------------------
    def test_recommendations_all_tracking_enabled(self):
        config = _valid_config(
            enabled=True,
            include_timing=True,
            include_confidence=True,
            include_step_details=True,
            max_reasoning_length=5000,
        )
        recs = self.validator.get_configuration_recommendations(config)
        assert any("performance" in r.lower() for r in recs)

    def test_recommendations_disabled(self):
        config = _valid_config(enabled=False)
        recs = self.validator.get_configuration_recommendations(config)
        assert any("disabled" in r.lower() for r in recs)

    def test_recommendations_no_step_timing_display(self):
        prefs = {
            "show_successful_steps": True,
            "show_failed_steps": True,
            "show_skipped_steps": True,
            "collapse_successful_steps": False,
            "highlight_failed_steps": True,
            "show_step_timing": False,
            "show_confidence_scores": True,
        }
        config = _valid_config(enabled=True, display_preferences=prefs)
        recs = self.validator.get_configuration_recommendations(config)
        assert any("step_timing" in r.lower() or "timing" in r.lower() for r in recs)

    def test_recommendations_no_highlight_failed(self):
        prefs = {
            "show_successful_steps": True,
            "show_failed_steps": True,
            "show_skipped_steps": True,
            "collapse_successful_steps": False,
            "highlight_failed_steps": False,
            "show_step_timing": True,
            "show_confidence_scores": True,
        }
        config = _valid_config(enabled=True, display_preferences=prefs)
        recs = self.validator.get_configuration_recommendations(config)
        assert any("highlight" in r.lower() for r in recs)

    def test_recommendations_clean_config(self):
        config = _valid_config(
            enabled=True,
            include_step_details=False,
            max_reasoning_length=500,
        )
        recs = self.validator.get_configuration_recommendations(config)
        # No "all tracking" recommendation since step_details is False
        assert not any("all tracking features" in r.lower() for r in recs)


# ------------------------------------------------------------------
# Module-level convenience functions
# ------------------------------------------------------------------
class TestConvenienceFunctions:
    def test_validate_cot_config_valid(self):
        config = _valid_config()
        errors = validate_cot_config(config)
        assert errors == []

    def test_validate_cot_config_invalid(self):
        config = _valid_config(max_reasoning_length=5)
        errors = validate_cot_config(config)
        assert len(errors) > 0

    def test_validate_and_fix_cot_config_valid(self):
        config = _valid_config()
        fixed = validate_and_fix_cot_config(config)
        assert fixed is config

    def test_validate_and_fix_cot_config_fixable(self):
        config = _valid_config(max_reasoning_length=5)
        fixed = validate_and_fix_cot_config(config)
        assert fixed.max_reasoning_length >= 50
