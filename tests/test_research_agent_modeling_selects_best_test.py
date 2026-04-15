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

from dataclasses import dataclass, field
from unittest.mock import Mock

from askrita.research.ResearchAgent import ResearchAgent, ResearchWorkflowState


@dataclass
class _FakeTest:
    test_name: str
    test_statistic: float
    p_value: float
    is_significant: bool
    sample_sizes: dict = field(default_factory=dict)
    group_means: dict = field(default_factory=dict)
    group_stds: dict = field(default_factory=dict)
    effect_size: float | None = None
    effect_size_interpretation: str = ""

    def to_prompt_text(self) -> str:
        return f"TEST: {self.test_name}"


def test_modeling_uses_best_test_not_last():
    """
    Regression: previously key_metrics were overwritten in a loop (last test wins),
    which can cause INCONCLUSIVE if the last test is a sample-size sentinel.
    """
    agent = ResearchAgent.__new__(ResearchAgent)
    agent.stats_analyzer = Mock()

    good = _FakeTest(
        test_name="Welch's t-test",
        test_statistic=2.0,
        p_value=0.01,
        is_significant=True,
        sample_sizes={"A": 50, "B": 50},
        group_means={"A": 10.0, "B": 8.0},
        effect_size=0.6,
        effect_size_interpretation="medium",
    )
    good.additional_info = {"value_column": "ltr", "group_column": "member_type"}
    bad_last = _FakeTest(
        test_name="Sample Size Check Failed",
        test_statistic=0.0,
        p_value=1.0,
        is_significant=False,
        sample_sizes={"A": 1, "B": 1},
        group_means={"A": 10.0, "B": 8.0},
    )
    bad_last.additional_info = {"value_column": "value", "group_column": "group"}

    agent.stats_analyzer.analyze_hypothesis_data.return_value = {
        "descriptive_stats": [],
        "statistical_tests": [good, bad_last],  # last is sentinel
        "summary_text": [],
    }

    state = ResearchWorkflowState(
        hypothesis="Medicare vs Commercial using ltr by member_type",
        collected_data={"query_1": {"data": [{"x": 1}]}}
    )
    update = agent._modeling(state)

    assert update["key_metrics"]["test_name"] == "Welch's t-test"
    assert update["key_metrics"]["p_value"] == 0.01


