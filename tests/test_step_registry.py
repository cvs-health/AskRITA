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

"""Tests for step_registry.py – targets missing coverage lines."""

from askrita.utils.step_registry import (
    StepInfo,
    StepRegistry,
    get_step_registry,
    register_step,
    get_step_type,
    get_reasoning_template,
)


# ---------------------------------------------------------------------------
# StepInfo
# ---------------------------------------------------------------------------

class TestStepInfo:
    def test_create_step_info(self):
        step = StepInfo(name="my_step", step_type="analysis", description="desc", enabled=True)
        assert step.name == "my_step"
        assert step.step_type == "analysis"
        assert step.enabled is True

    def test_default_enabled_true(self):
        step = StepInfo(name="step", step_type="generation")
        assert step.enabled is True


# ---------------------------------------------------------------------------
# StepRegistry
# ---------------------------------------------------------------------------

class TestStepRegistry:
    def _fresh_registry(self):
        return StepRegistry()

    def test_default_steps_registered(self):
        registry = self._fresh_registry()
        steps = registry.get_all_steps()
        assert "parse_question" in steps
        assert "generate_sql" in steps
        assert "execute_sql" in steps

    def test_register_step(self):
        registry = self._fresh_registry()
        step_info = StepInfo(name="custom_step", step_type="analysis")
        registry.register_step(step_info)
        assert registry.get_step_info("custom_step") is not None

    def test_register_step_simple(self):
        registry = self._fresh_registry()
        registry.register_step_simple(
            "simple_step", "validation",
            reasoning_template={"start": "starting"},
            description="A simple step",
            enabled=True,
        )
        info = registry.get_step_info("simple_step")
        assert info is not None
        assert info.step_type == "validation"
        assert info.description == "A simple step"

    def test_register_step_simple_no_template(self):
        registry = self._fresh_registry()
        registry.register_step_simple("step_no_template", "execution")
        info = registry.get_step_info("step_no_template")
        assert info.reasoning_template == {}

    def test_get_step_info_returns_none_for_unknown(self):
        registry = self._fresh_registry()
        assert registry.get_step_info("nonexistent") is None

    def test_get_step_type_known(self):
        registry = self._fresh_registry()
        assert registry.get_step_type("parse_question") == "analysis"
        assert registry.get_step_type("generate_sql") == "generation"
        assert registry.get_step_type("execute_sql") == "execution"

    def test_get_step_type_unknown_returns_default(self):
        registry = self._fresh_registry()
        result = registry.get_step_type("unknown_step")
        assert result == "unknown"

    def test_get_reasoning_template_known(self):
        registry = self._fresh_registry()
        template = registry.get_reasoning_template("parse_question")
        assert isinstance(template, dict)
        assert len(template) > 0

    def test_get_reasoning_template_unknown_returns_empty(self):
        registry = self._fresh_registry()
        template = registry.get_reasoning_template("nonexistent")
        assert template == {}

    def test_get_all_steps_returns_copy(self):
        registry = self._fresh_registry()
        steps1 = registry.get_all_steps()
        steps2 = registry.get_all_steps()
        assert steps1 == steps2
        # Modifying returned dict doesn't affect registry
        steps1["new_key"] = None
        assert "new_key" not in registry.get_all_steps()

    def test_get_steps_by_type(self):
        registry = self._fresh_registry()
        analysis_steps = registry.get_steps_by_type("analysis")
        assert len(analysis_steps) > 0
        for step in analysis_steps:
            assert step.step_type == "analysis"

    def test_get_steps_by_type_nonexistent(self):
        registry = self._fresh_registry()
        result = registry.get_steps_by_type("nonexistent_type")
        assert result == []

    def test_is_step_enabled_known(self):
        registry = self._fresh_registry()
        assert registry.is_step_enabled("parse_question") is True

    def test_is_step_enabled_unknown_returns_true(self):
        registry = self._fresh_registry()
        assert registry.is_step_enabled("nonexistent") is True

    def test_enable_step(self):
        registry = self._fresh_registry()
        registry.register_step_simple("disabled_step", "analysis", enabled=False)
        result = registry.enable_step("disabled_step")
        assert result is True
        assert registry.is_step_enabled("disabled_step") is True

    def test_enable_step_nonexistent_returns_false(self):
        registry = self._fresh_registry()
        result = registry.enable_step("nonexistent")
        assert result is False

    def test_disable_step(self):
        registry = self._fresh_registry()
        result = registry.disable_step("parse_question")
        assert result is True
        assert registry.is_step_enabled("parse_question") is False

    def test_disable_step_nonexistent_returns_false(self):
        registry = self._fresh_registry()
        result = registry.disable_step("nonexistent")
        assert result is False

    def test_unregister_step(self):
        registry = self._fresh_registry()
        registry.register_step_simple("temp_step", "analysis")
        result = registry.unregister_step("temp_step")
        assert result is True
        assert registry.get_step_info("temp_step") is None

    def test_unregister_step_nonexistent_returns_false(self):
        registry = self._fresh_registry()
        result = registry.unregister_step("nonexistent")
        assert result is False

    def test_get_step_statistics(self):
        registry = self._fresh_registry()
        stats = registry.get_step_statistics()
        assert "total_steps" in stats
        assert "enabled_steps" in stats
        assert "disabled_steps" in stats
        assert "type_distribution" in stats
        assert stats["total_steps"] > 0
        assert stats["enabled_steps"] + stats["disabled_steps"] == stats["total_steps"]

    def test_statistics_after_disable(self):
        registry = self._fresh_registry()
        initial_stats = registry.get_step_statistics()
        registry.disable_step("parse_question")
        new_stats = registry.get_step_statistics()
        assert new_stats["disabled_steps"] == initial_stats["disabled_steps"] + 1
        assert new_stats["enabled_steps"] == initial_stats["enabled_steps"] - 1


# ---------------------------------------------------------------------------
# Global registry functions
# ---------------------------------------------------------------------------

class TestGlobalRegistryFunctions:
    def test_get_step_registry_returns_instance(self):
        registry = get_step_registry()
        assert isinstance(registry, StepRegistry)

    def test_get_step_registry_is_singleton(self):
        r1 = get_step_registry()
        r2 = get_step_registry()
        assert r1 is r2

    def test_get_step_type_known(self):
        result = get_step_type("parse_question")
        assert result == "analysis"

    def test_get_step_type_unknown(self):
        result = get_step_type("totally_unknown_step")
        assert result == "unknown"

    def test_get_reasoning_template(self):
        template = get_reasoning_template("parse_question")
        assert isinstance(template, dict)
        assert len(template) > 0

    def test_get_reasoning_template_unknown(self):
        template = get_reasoning_template("nonexistent")
        assert template == {}

    def test_register_step_adds_to_global(self):
        register_step(
            "global_test_step",
            "analysis",
            reasoning_template={"start": "starting"},
            description="test",
        )
        registry = get_step_registry()
        info = registry.get_step_info("global_test_step")
        assert info is not None
        assert info.step_type == "analysis"
