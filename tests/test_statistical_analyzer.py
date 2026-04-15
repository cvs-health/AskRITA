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
#   numpy (BSD-3-Clause)
#   pandas (BSD-3-Clause)

"""Comprehensive tests for StatisticalAnalyzer."""

import numpy as np
import pandas as pd

from askrita.research.StatisticalAnalyzer import (
    StatisticalAnalyzer,
    StatisticalResult,
    DescriptiveStats,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_two_group_df(n=30):
    """Return a DataFrame with two groups and a continuous value column."""
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "group": ["A"] * n + ["B"] * n,
        "value": np.concatenate([rng.normal(10, 2, n), rng.normal(15, 2, n)]),
    })


def _make_three_group_df(n=20):
    """Return a DataFrame with three groups."""
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "group": ["A"] * n + ["B"] * n + ["C"] * n,
        "value": np.concatenate([
            rng.normal(10, 2, n),
            rng.normal(15, 2, n),
            rng.normal(20, 2, n),
        ]),
    })


# ---------------------------------------------------------------------------
# StatisticalResult – str / to_prompt_text
# ---------------------------------------------------------------------------

class TestStatisticalResult:
    def test_str_significant(self):
        r = StatisticalResult(
            test_name="t-test", test_statistic=3.5, p_value=0.01, is_significant=True
        )
        s = str(r)
        assert "SIGNIFICANT" in s
        assert "t-test" in s

    def test_str_not_significant(self):
        r = StatisticalResult(
            test_name="t-test", test_statistic=1.0, p_value=0.5, is_significant=False
        )
        assert "NOT SIGNIFICANT" in str(r)

    def test_to_prompt_text_basic(self):
        r = StatisticalResult(
            test_name="t-test", test_statistic=2.0, p_value=0.04, is_significant=True
        )
        text = r.to_prompt_text()
        assert "TEST: t-test" in text
        assert "P-value" in text

    def test_to_prompt_text_with_effect_size(self):
        r = StatisticalResult(
            test_name="t-test", test_statistic=2.0, p_value=0.04, is_significant=True,
            effect_size=0.5, effect_size_interpretation="medium"
        )
        text = r.to_prompt_text()
        assert "Effect Size" in text
        assert "medium" in text

    def test_to_prompt_text_with_confidence_interval(self):
        r = StatisticalResult(
            test_name="t-test", test_statistic=2.0, p_value=0.04, is_significant=True,
            confidence_interval=(1.0, 3.0)
        )
        text = r.to_prompt_text()
        assert "Confidence Interval" in text

    def test_to_prompt_text_with_group_means(self):
        r = StatisticalResult(
            test_name="t-test", test_statistic=2.0, p_value=0.04, is_significant=True,
            group_means={"A": 10.0, "B": 15.0},
            group_stds={"A": 2.0, "B": 2.5},
            sample_sizes={"A": 30, "B": 30},
        )
        text = r.to_prompt_text()
        assert "Group Means" in text
        assert "A" in text

    def test_to_prompt_text_large_n_note(self):
        r = StatisticalResult(
            test_name="t-test", test_statistic=2.0, p_value=0.04, is_significant=True,
            additional_info={"large_n_note": "LARGE-N WARNING"}
        )
        text = r.to_prompt_text()
        assert "LARGE-N WARNING" in text

    def test_to_prompt_text_was_sampled(self):
        r = StatisticalResult(
            test_name="t-test", test_statistic=2.0, p_value=0.04, is_significant=True,
            sample_sizes={"A": 500, "B": 500},
            additional_info={"was_sampled": True, "original_n": 200000}
        )
        text = r.to_prompt_text()
        assert "sample" in text.lower()

    def test_to_prompt_text_bonferroni(self):
        r = StatisticalResult(
            test_name="t-test", test_statistic=2.0, p_value=0.04, is_significant=True,
            additional_info={
                "bonferroni_p": 0.12,
                "bonferroni_significant": False,
                "n_tests_corrected_for": 3
            }
        )
        text = r.to_prompt_text()
        assert "Bonferroni" in text

    def test_to_prompt_text_tukey(self):
        r = StatisticalResult(
            test_name="ANOVA", test_statistic=5.0, p_value=0.001, is_significant=True,
            additional_info={
                "tukey_hsd_pairwise": [
                    {"group1": "A", "group2": "B", "p_value": 0.01, "significant": True},
                    {"group1": "A", "group2": "C", "p_value": 0.5, "significant": False},
                ]
            }
        )
        text = r.to_prompt_text()
        assert "Tukey HSD" in text


# ---------------------------------------------------------------------------
# DescriptiveStats – to_prompt_text
# ---------------------------------------------------------------------------

class TestDescriptiveStats:
    def test_to_prompt_text(self):
        ds = DescriptiveStats(
            variable="value", count=30, mean=10.0, std=2.0,
            min=5.0, max=15.0, median=10.0, q1=8.5, q3=11.5
        )
        text = ds.to_prompt_text()
        assert "value" in text
        assert "n=30" in text


# ---------------------------------------------------------------------------
# StatisticalAnalyzer.sql_results_to_dataframe
# ---------------------------------------------------------------------------

class TestSqlResultsToDataframe:
    def setup_method(self):
        self.analyzer = StatisticalAnalyzer()

    def test_empty_results(self):
        df = self.analyzer.sql_results_to_dataframe([])
        assert df.empty

    def test_dict_results(self):
        results = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        df = self.analyzer.sql_results_to_dataframe(results)
        assert list(df.columns) == ["a", "b"]
        assert len(df) == 2

    def test_list_results_with_columns(self):
        results = [[1, 2], [3, 4]]
        df = self.analyzer.sql_results_to_dataframe(results, columns=["x", "y"])
        assert list(df.columns) == ["x", "y"]

    def test_list_results_no_columns(self):
        results = [[1, 2, 3], [4, 5, 6]]
        df = self.analyzer.sql_results_to_dataframe(results)
        assert "col_0" in df.columns

    def test_single_column_results(self):
        results = [10, 20, 30]
        df = self.analyzer.sql_results_to_dataframe(results)
        assert "value" in df.columns
        assert len(df) == 3

    def test_tuple_results(self):
        results = [(1, "a"), (2, "b")]
        df = self.analyzer.sql_results_to_dataframe(results)
        assert len(df) == 2


# ---------------------------------------------------------------------------
# StatisticalAnalyzer.descriptive_stats
# ---------------------------------------------------------------------------

class TestDescriptiveStatsMethod:
    def setup_method(self):
        self.analyzer = StatisticalAnalyzer()

    def test_missing_column(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        assert self.analyzer.descriptive_stats(df, "b") is None

    def test_all_nan(self):
        df = pd.DataFrame({"a": [None, None, None]})
        assert self.analyzer.descriptive_stats(df, "a") is None

    def test_valid(self):
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 5.0]})
        result = self.analyzer.descriptive_stats(df, "a")
        assert result is not None
        assert result.count == 5
        assert abs(result.mean - 3.0) < 0.01

    def test_with_missing_values(self):
        df = pd.DataFrame({"a": [1.0, 2.0, None, 4.0, 5.0]})
        result = self.analyzer.descriptive_stats(df, "a")
        assert result.missing == 1
        assert result.count == 4


# ---------------------------------------------------------------------------
# StatisticalAnalyzer._check_sample_size
# ---------------------------------------------------------------------------

class TestCheckSampleSize:
    def setup_method(self):
        self.analyzer = StatisticalAnalyzer()

    def test_insufficient(self):
        msg = self.analyzer._check_sample_size({"A": 1, "B": 5})
        assert "INSUFFICIENT" in msg

    def test_small_warning(self):
        msg = self.analyzer._check_sample_size({"A": 5, "B": 5})
        assert "WARNING" in msg

    def test_note_total_small(self):
        msg = self.analyzer._check_sample_size({"A": 10, "B": 10})
        assert "NOTE" in msg

    def test_adequate(self):
        msg = self.analyzer._check_sample_size({"A": 50, "B": 50})
        assert msg is None

    def test_empty(self):
        msg = self.analyzer._check_sample_size({})
        assert "INSUFFICIENT" in msg


# ---------------------------------------------------------------------------
# StatisticalAnalyzer._large_n_note
# ---------------------------------------------------------------------------

class TestLargeNNote:
    def setup_method(self):
        self.analyzer = StatisticalAnalyzer()

    def test_small_n(self):
        assert self.analyzer._large_n_note(1000) is None

    def test_large_n(self):
        note = self.analyzer._large_n_note(50000)
        assert note is not None
        assert "LARGE-N" in note


# ---------------------------------------------------------------------------
# StatisticalAnalyzer._stratified_sample
# ---------------------------------------------------------------------------

class TestStratifiedSample:
    def setup_method(self):
        self.analyzer = StatisticalAnalyzer()

    def test_no_sample_when_below_threshold(self):
        df = _make_two_group_df(n=100)
        result_df, was_sampled, original_n = self.analyzer._stratified_sample(df, "group")
        assert not was_sampled
        assert original_n == len(df)

    def test_sample_when_above_threshold(self):
        rng = np.random.default_rng(42)
        n = self.analyzer.SAMPLE_THRESHOLD + 1000
        df = pd.DataFrame({
            "group": (["A"] * (n // 2)) + (["B"] * (n - n // 2)),
            "value": rng.normal(0, 1, n),
        })
        result_df, was_sampled, original_n = self.analyzer._stratified_sample(df, "group")
        assert was_sampled
        assert original_n == n
        assert len(result_df) <= self.analyzer.TARGET_SAMPLE + 10


# ---------------------------------------------------------------------------
# StatisticalAnalyzer._interpret_effect_size
# ---------------------------------------------------------------------------

class TestInterpretEffectSize:
    def setup_method(self):
        self.analyzer = StatisticalAnalyzer()

    def test_cohens_d_negligible(self):
        assert self.analyzer._interpret_effect_size(0.1) == "negligible"

    def test_cohens_d_small(self):
        assert self.analyzer._interpret_effect_size(0.3) == "small"

    def test_cohens_d_medium(self):
        assert self.analyzer._interpret_effect_size(0.6) == "medium"

    def test_cohens_d_large(self):
        assert self.analyzer._interpret_effect_size(1.0) == "large"

    def test_eta_squared_negligible(self):
        assert self.analyzer._interpret_effect_size(0.005, is_eta_squared=True) == "negligible"

    def test_eta_squared_small(self):
        assert self.analyzer._interpret_effect_size(0.03, is_eta_squared=True) == "small"

    def test_eta_squared_medium(self):
        assert self.analyzer._interpret_effect_size(0.1, is_eta_squared=True) == "medium"

    def test_eta_squared_large(self):
        assert self.analyzer._interpret_effect_size(0.2, is_eta_squared=True) == "large"


# ---------------------------------------------------------------------------
# StatisticalAnalyzer.compare_groups
# ---------------------------------------------------------------------------

class TestCompareGroups:
    def setup_method(self):
        self.analyzer = StatisticalAnalyzer()

    def test_missing_columns(self):
        df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
        result = self.analyzer.compare_groups(df, "missing", "b")
        assert result is None

    def test_only_one_group(self):
        df = pd.DataFrame({"value": [1.0, 2.0, 3.0], "group": ["A", "A", "A"]})
        result = self.analyzer.compare_groups(df, "value", "group")
        assert result is None

    def test_insufficient_sample_sizes(self):
        df = pd.DataFrame({"value": [1.0, 2.0], "group": ["A", "B"]})
        result = self.analyzer.compare_groups(df, "value", "group")
        assert result is not None
        assert result.test_name == "Sample Size Check Failed"

    def test_two_group_comparison(self):
        df = _make_two_group_df(n=50)
        result = self.analyzer.compare_groups(df, "value", "group")
        assert result is not None
        assert result.test_name in ("Welch's t-test", "Mann-Whitney U test")
        assert result.p_value <= 1.0

    def test_multi_group_comparison(self):
        df = _make_three_group_df(n=20)
        result = self.analyzer.compare_groups(df, "value", "group")
        assert result is not None
        assert result.test_name in ("One-way ANOVA", "Kruskal-Wallis H test")


# ---------------------------------------------------------------------------
# StatisticalAnalyzer.correlation
# ---------------------------------------------------------------------------

class TestCorrelation:
    def setup_method(self):
        self.analyzer = StatisticalAnalyzer()

    def test_missing_columns(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        assert self.analyzer.correlation(df, "a", "missing") is None

    def test_too_few_rows(self):
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        assert self.analyzer.correlation(df, "a", "b") is None

    def test_valid_correlation(self):
        rng = np.random.default_rng(42)
        x = rng.normal(0, 1, 50)
        df = pd.DataFrame({"x": x, "y": x + rng.normal(0, 0.1, 50)})
        result = self.analyzer.correlation(df, "x", "y")
        assert result is not None
        assert abs(result.test_statistic) > 0.9

    def test_no_scipy(self):
        self.analyzer.scipy_available = False
        df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
        assert self.analyzer.correlation(df, "x", "y") is None
        self.analyzer.scipy_available = True


# ---------------------------------------------------------------------------
# StatisticalAnalyzer.tukey_hsd
# ---------------------------------------------------------------------------

class TestTukeyHsd:
    def setup_method(self):
        self.analyzer = StatisticalAnalyzer()

    def test_too_few_groups(self):
        df = _make_two_group_df(n=20)
        assert self.analyzer.tukey_hsd(df, "value", "group") is None

    def test_missing_columns(self):
        df = _make_three_group_df()
        assert self.analyzer.tukey_hsd(df, "missing", "group") is None

    def test_three_groups(self):
        df = _make_three_group_df(n=30)
        result = self.analyzer.tukey_hsd(df, "value", "group")
        # May return None if scipy version doesn't support tukey_hsd
        if result is not None:
            assert len(result) == 3  # 3 pairwise comparisons: AB, AC, BC
            for pair in result:
                assert "group1" in pair
                assert "group2" in pair
                assert "p_value" in pair

    def test_no_scipy(self):
        self.analyzer.scipy_available = False
        df = _make_three_group_df()
        assert self.analyzer.tukey_hsd(df, "value", "group") is None
        self.analyzer.scipy_available = True


# ---------------------------------------------------------------------------
# StatisticalAnalyzer.apply_bonferroni_correction
# ---------------------------------------------------------------------------

class TestBonferroniCorrection:
    def test_single_test_no_change(self):
        r = StatisticalResult(
            test_name="t-test", test_statistic=2.0, p_value=0.04, is_significant=True
        )
        StatisticalAnalyzer.apply_bonferroni_correction([r])
        assert "bonferroni_p" not in r.additional_info

    def test_multiple_tests(self):
        results = [
            StatisticalResult(test_name="t1", test_statistic=1.0, p_value=0.01, is_significant=True),
            StatisticalResult(test_name="t2", test_statistic=1.0, p_value=0.02, is_significant=True),
            StatisticalResult(test_name="t3", test_statistic=1.0, p_value=0.03, is_significant=True),
        ]
        StatisticalAnalyzer.apply_bonferroni_correction(results)
        for r in results:
            assert "bonferroni_p" in r.additional_info
            assert r.additional_info["n_tests_corrected_for"] == 3

    def test_bonferroni_caps_at_1(self):
        results = [
            StatisticalResult(test_name="t1", test_statistic=1.0, p_value=0.9, is_significant=False),
            StatisticalResult(test_name="t2", test_statistic=1.0, p_value=0.9, is_significant=False),
        ]
        StatisticalAnalyzer.apply_bonferroni_correction(results)
        assert results[0].additional_info["bonferroni_p"] <= 1.0


# ---------------------------------------------------------------------------
# StatisticalAnalyzer.chi_square
# ---------------------------------------------------------------------------

class TestChiSquare:
    def setup_method(self):
        self.analyzer = StatisticalAnalyzer()

    def test_missing_columns(self):
        df = pd.DataFrame({"a": ["x", "y"], "b": ["p", "q"]})
        assert self.analyzer.chi_square(df, "a", "missing") is None

    def test_valid_chi_square(self):
        # A clear association
        data = {"color": ["red"] * 50 + ["blue"] * 50, "buy": ["yes"] * 40 + ["no"] * 10 + ["no"] * 40 + ["yes"] * 10}
        df = pd.DataFrame(data)
        result = self.analyzer.chi_square(df, "color", "buy")
        assert result is not None
        assert result.test_name == "Chi-square Test of Independence"

    def test_no_scipy(self):
        self.analyzer.scipy_available = False
        df = pd.DataFrame({"a": ["x", "y"], "b": ["p", "q"]})
        assert self.analyzer.chi_square(df, "a", "b") is None
        self.analyzer.scipy_available = True

    def test_too_small_contingency(self):
        # Only one combination → contingency < 2x2
        df = pd.DataFrame({"a": ["x", "x", "x"], "b": ["p", "p", "p"]})
        result = self.analyzer.chi_square(df, "a", "b")
        assert result is None


# ---------------------------------------------------------------------------
# StatisticalAnalyzer._fallback_comparison
# ---------------------------------------------------------------------------

class TestFallbackComparison:
    def setup_method(self):
        self.analyzer = StatisticalAnalyzer()

    def test_missing_columns(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        assert self.analyzer._fallback_comparison(df, "a", "missing") is None

    def test_valid_fallback(self):
        df = _make_two_group_df()
        result = self.analyzer._fallback_comparison(df, "value", "group")
        assert result is not None
        assert "scipy not available" in result.test_name


# ---------------------------------------------------------------------------
# StatisticalAnalyzer._infer_column_meanings
# ---------------------------------------------------------------------------

class TestInferColumnMeanings:
    def setup_method(self):
        self.analyzer = StatisticalAnalyzer()

    def test_renames_col0_categorical_col1_numeric(self):
        df = pd.DataFrame({"col_0": ["A", "B", "C"], "col_1": [1.0, 2.0, 3.0]})
        result = self.analyzer._infer_column_meanings(df)
        assert "group" in result.columns
        assert "value" in result.columns

    def test_renames_col0_numeric_col1_categorical(self):
        df = pd.DataFrame({"col_0": [1.0, 2.0, 3.0], "col_1": ["A", "B", "C"]})
        result = self.analyzer._infer_column_meanings(df)
        assert "group" in result.columns
        assert "value" in result.columns

    def test_three_columns_no_rename(self):
        df = pd.DataFrame({"a": ["x", "y"], "b": [1, 2], "c": [3, 4]})
        result = self.analyzer._infer_column_meanings(df)
        # Should not rename since columns count != 2
        assert list(result.columns) == ["a", "b", "c"]

    def test_both_numeric_no_rename(self):
        df = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
        result = self.analyzer._infer_column_meanings(df)
        assert list(result.columns) == ["a", "b"]


# ---------------------------------------------------------------------------
# StatisticalAnalyzer.analyze_hypothesis_data – integration
# ---------------------------------------------------------------------------

class TestAnalyzeHypothesisData:
    def setup_method(self):
        self.analyzer = StatisticalAnalyzer()

    def test_empty_collected_data(self):
        result = self.analyzer.analyze_hypothesis_data({}, "some hypothesis")
        assert result["statistical_tests"] == []
        assert result["descriptive_stats"] == []

    def test_skips_error_entries(self):
        collected_data = {
            "q1": {"error": "DB error", "data": []}
        }
        result = self.analyzer.analyze_hypothesis_data(collected_data, "hypothesis")
        assert result["statistical_tests"] == []

    def test_group_comparison_from_dict_data(self):
        rng = np.random.default_rng(42)
        data = [
            {"group": "A", "value": float(v)} for v in rng.normal(10, 2, 30)
        ] + [
            {"group": "B", "value": float(v)} for v in rng.normal(15, 2, 30)
        ]
        collected_data = {
            "q1": {"data": data, "question": "Does value differ by group?"}
        }
        result = self.analyzer.analyze_hypothesis_data(collected_data, "value group")
        assert len(result["statistical_tests"]) > 0

    def test_correlation_from_two_numeric_columns(self):
        rng = np.random.default_rng(42)
        x = rng.normal(0, 1, 50)
        data = [{"x": float(xi), "y": float(xi + rng.normal(0, 0.1))} for xi in x]
        collected_data = {"q1": {"data": data, "question": "Correlation between x and y"}}
        result = self.analyzer.analyze_hypothesis_data(collected_data, "x y")
        assert len(result["statistical_tests"]) > 0

    def test_chi_square_from_two_categorical_columns(self):
        data = [
            {"color": "red", "size": "large"}, {"color": "red", "size": "small"},
            {"color": "blue", "size": "large"}, {"color": "blue", "size": "small"},
            {"color": "red", "size": "large"}, {"color": "red", "size": "small"},
            {"color": "blue", "size": "large"}, {"color": "blue", "size": "small"},
            {"color": "red", "size": "large"}, {"color": "blue", "size": "small"},
        ]
        collected_data = {"q1": {"data": data, "question": "Is color related to size?"}}
        result = self.analyzer.analyze_hypothesis_data(collected_data, "color size")
        assert "statistical_tests" in result  # may or may not find test; verify no exception raised

    def test_aggregated_data_detected_and_skipped(self):
        # Each group has exactly one row – aggregated data
        data = [
            {"group": "A", "value": 10.0},
            {"group": "B", "value": 15.0},
        ]
        collected_data = {"q1": {"data": data, "question": "avg value by group"}}
        result = self.analyzer.analyze_hypothesis_data(collected_data, "group value")
        # Should not produce a real statistical test
        for t in result["statistical_tests"]:
            assert t.test_name != "Welch's t-test"

    def test_large_dataset_advisory(self):
        rng = np.random.default_rng(42)
        n = self.analyzer.LARGE_N_THRESHOLD + 100
        data = [{"x": float(v), "y": float(v + 0.1)} for v in rng.normal(0, 1, n)]
        collected_data = {"q1": {"data": data, "question": "x vs y"}}
        result = self.analyzer.analyze_hypothesis_data(collected_data, "x y")
        assert any("LARGE DATASET" in t for t in result["summary_text"])

    def test_list_of_lists_data(self):
        data = [["A", 10.0], ["A", 12.0], ["B", 20.0], ["B", 22.0],
                ["A", 11.0], ["B", 21.0], ["A", 13.0], ["B", 19.0],
                ["A", 10.5], ["B", 20.5]]
        collected_data = {"q1": {"data": data, "question": "group comparison"}}
        result = self.analyzer.analyze_hypothesis_data(collected_data, "hypothesis")
        # Should not crash
        assert isinstance(result, dict)

    def test_trace_populated(self):
        rng = np.random.default_rng(42)
        data = [{"group": g, "value": float(v)}
                for g in ["A"] * 20 + ["B"] * 20
                for v in rng.normal(0, 1, 1)]
        collected_data = {"q1": {"data": data[:40], "question": "hypothesis"}}
        result = self.analyzer.analyze_hypothesis_data(collected_data, "hypothesis")
        assert len(result["trace"]) >= 1
