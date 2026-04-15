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
#   scipy (BSD-3-Clause)

"""
Statistical Analyzer - Real statistical computation for Research Agent.

Provides actual statistical tests, not LLM-generated interpretations.
Uses scipy and pandas for computations.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Optional imports - graceful degradation if not available
try:
    from scipy import stats

    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.warning("scipy not available - statistical tests will be limited")


@dataclass
class StatisticalResult:
    """Result of a statistical test."""

    test_name: str
    test_statistic: float
    p_value: float
    is_significant: bool  # p < 0.05
    effect_size: Optional[float] = None
    effect_size_interpretation: str = ""  # "small", "medium", "large"
    confidence_interval: Optional[Tuple[float, float]] = None
    sample_sizes: Dict[str, int] = field(default_factory=dict)
    group_means: Dict[str, float] = field(default_factory=dict)
    group_stds: Dict[str, float] = field(default_factory=dict)
    additional_info: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        sig = "SIGNIFICANT" if self.is_significant else "NOT SIGNIFICANT"
        return f"{self.test_name}: stat={self.test_statistic:.4f}, p={self.p_value:.4f} ({sig})"

    def _prompt_lines_group_means(self) -> list:
        """Generate group means lines for prompt text."""
        if not self.group_means:
            return []
        lines = ["Group Means:"]
        for group, mean in self.group_means.items():
            std = self.group_stds.get(group, 0)
            n = self.sample_sizes.get(group, 0)
            lines.append(f"  - {group}: M={mean:.4f}, SD={std:.4f}, n={n}")
        return lines

    def _prompt_lines_additional_info(self, info: dict) -> list:
        """Generate additional info lines for prompt text."""
        lines = []
        if info.get("large_n_note"):
            lines.append(f"\n{info['large_n_note']}")
        if info.get("was_sampled") and info.get("original_n"):
            analyzed_n = sum(self.sample_sizes.values()) if self.sample_sizes else "?"
            lines.append(
                f"Note: Stratified sample used ({info['original_n']:,} original rows -> "
                f"{analyzed_n} analyzed rows)"
            )
        if info.get("bonferroni_p") is not None:
            bon_sig = (
                "significant"
                if info.get("bonferroni_significant")
                else "not significant"
            )
            n_cor = info.get("n_tests_corrected_for", "?")
            lines.append(
                f"Bonferroni-corrected p: {info['bonferroni_p']:.6f} ({bon_sig}, corrected for {n_cor} tests)"
            )
        if info.get("tukey_hsd_pairwise"):
            lines.extend(self._prompt_lines_tukey(info["tukey_hsd_pairwise"]))
        return lines

    def _prompt_lines_tukey(self, tukey_pairs: list) -> list:
        """Generate Tukey HSD pairwise comparison lines for prompt text."""
        lines = ["\nTukey HSD Post-hoc Pairwise Comparisons:"]
        for pair in tukey_pairs:
            sig_mark = " *" if pair["significant"] else ""
            lines.append(
                f"  {pair['group1']} vs {pair['group2']}: "
                f"p={pair['p_value']:.4f}{sig_mark}"
            )
        return lines

    def to_prompt_text(self) -> str:
        """Generate text suitable for LLM interpretation."""
        lines = [
            f"TEST: {self.test_name}",
            f"Test Statistic: {self.test_statistic:.4f}",
            f"P-value: {self.p_value:.6f}",
            f"Statistically Significant: {'Yes (p < 0.05)' if self.is_significant else 'No (p >= 0.05)'}",
        ]

        if self.effect_size is not None:
            lines.append(
                f"Effect Size: {self.effect_size:.4f} ({self.effect_size_interpretation})"
            )

        if self.confidence_interval:
            lines.append(
                f"95% Confidence Interval: [{self.confidence_interval[0]:.4f}, {self.confidence_interval[1]:.4f}]"
            )

        lines.extend(self._prompt_lines_group_means())
        lines.extend(self._prompt_lines_additional_info(self.additional_info or {}))

        return "\n".join(lines)


@dataclass
class DescriptiveStats:
    """Descriptive statistics for a variable."""

    variable: str
    count: int
    mean: float
    std: float
    min: float
    max: float
    median: float
    q1: float  # 25th percentile
    q3: float  # 75th percentile
    missing: int = 0

    def to_prompt_text(self) -> str:
        return (
            f"{self.variable}: n={self.count}, M={self.mean:.2f}, SD={self.std:.2f}, "
            f"Mdn={self.median:.2f}, Range=[{self.min:.2f}, {self.max:.2f}]"
        )


class StatisticalAnalyzer:
    """
    Real statistical computation engine.

    Performs actual statistical tests using scipy/pandas.
    Results are passed to LLM for interpretation, not generation.
    """

    # Large-N thresholds
    LARGE_N_THRESHOLD: int = 10_000  # warn about p-value inflation above this
    SAMPLE_THRESHOLD: int = 100_000  # trigger stratified sampling above this
    TARGET_SAMPLE: int = 50_000  # post-sampling target size

    def __init__(self):
        self.scipy_available = SCIPY_AVAILABLE

    def sql_results_to_dataframe(
        self, results: List[Any], columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Convert SQL query results to pandas DataFrame."""
        if not results:
            return pd.DataFrame()

        # Handle different result formats
        if isinstance(results[0], dict):
            return pd.DataFrame(results)
        elif isinstance(results[0], (list, tuple)):
            if columns:
                return pd.DataFrame(results, columns=columns)
            else:
                # Auto-generate column names
                return pd.DataFrame(
                    results, columns=[f"col_{i}" for i in range(len(results[0]))]
                )
        else:
            # Single column
            return pd.DataFrame({"value": results})

    def descriptive_stats(
        self, df: pd.DataFrame, column: str
    ) -> Optional[DescriptiveStats]:
        """Compute descriptive statistics for a numeric column."""
        if column not in df.columns:
            return None

        series = pd.to_numeric(df[column], errors="coerce")
        valid = series.dropna()

        if len(valid) == 0:
            return None

        return DescriptiveStats(
            variable=column,
            count=len(valid),
            mean=float(valid.mean()),
            std=float(valid.std()),
            min=float(valid.min()),
            max=float(valid.max()),
            median=float(valid.median()),
            q1=float(valid.quantile(0.25)),
            q3=float(valid.quantile(0.75)),
            missing=len(series) - len(valid),
        )

    def compare_groups(
        self, df: pd.DataFrame, value_column: str, group_column: str
    ) -> Optional[StatisticalResult]:
        """
        Compare means across groups using appropriate test.

        - 2 groups: Independent samples t-test (or Mann-Whitney U if non-normal)
        - 3+ groups: One-way ANOVA (or Kruskal-Wallis if non-normal)
        """
        if not self.scipy_available:
            return self._fallback_comparison(df, value_column, group_column)

        if value_column not in df.columns or group_column not in df.columns:
            logger.warning(f"Columns not found: {value_column}, {group_column}")
            return None

        # Prepare data
        df_clean = df[[value_column, group_column]].dropna()
        df_clean[value_column] = pd.to_numeric(df_clean[value_column], errors="coerce")
        df_clean = df_clean.dropna()

        # Large-N handling: stratified sample if needed, warn if still large
        df_clean, was_sampled, original_n = self._stratified_sample(
            df_clean, group_column
        )
        large_n_note = self._large_n_note(original_n)

        groups = df_clean.groupby(group_column)[value_column]
        group_data = {name: group.values for name, group in groups}

        if len(group_data) < 2:
            logger.warning("Need at least 2 groups for comparison")
            return None

        # Calculate group statistics
        group_means = {str(k): float(v.mean()) for k, v in group_data.items()}
        group_stds = {str(k): float(v.std()) for k, v in group_data.items()}
        sample_sizes = {str(k): len(v) for k, v in group_data.items()}

        # Check sample sizes
        sample_warning = self._check_sample_size(sample_sizes)
        if sample_warning and "INSUFFICIENT" in sample_warning:
            logger.warning(sample_warning)
            return StatisticalResult(
                test_name="Sample Size Check Failed",
                test_statistic=0.0,
                p_value=1.0,
                is_significant=False,
                sample_sizes=sample_sizes,
                group_means=group_means,
                group_stds=group_stds,
                additional_info={
                    "warning": sample_warning,
                    "value_column": value_column,
                    "group_column": group_column,
                    "large_n_note": large_n_note,
                    "was_sampled": was_sampled,
                    "original_n": original_n,
                },
            )

        # Choose test based on number of groups
        if len(group_data) == 2:
            result = self._two_group_test(
                group_data, group_means, group_stds, sample_sizes
            )
        else:
            result = self._multi_group_test(
                group_data, group_means, group_stds, sample_sizes
            )

        # Add sample warning if applicable
        if sample_warning:
            result.additional_info["sample_warning"] = sample_warning

        # Always record which columns we actually tested (critical for traceability and "context preservation")
        result.additional_info.setdefault("value_column", value_column)
        result.additional_info.setdefault("group_column", group_column)

        # Large-N metadata
        if large_n_note:
            result.additional_info["large_n_note"] = large_n_note
        result.additional_info["was_sampled"] = was_sampled
        result.additional_info["original_n"] = original_n

        return result

    def _check_sample_size(self, sample_sizes: Dict[str, int]) -> Optional[str]:
        """Check if sample sizes are adequate for statistical testing."""
        min_size = min(sample_sizes.values()) if sample_sizes else 0
        total = sum(sample_sizes.values()) if sample_sizes else 0

        if min_size < 2:
            return "INSUFFICIENT: At least 2 observations per group required for statistical testing"
        if min_size < 10:
            return f"WARNING: Small sample sizes (min n={min_size}). Results may not be reliable."
        if total < 30:
            return f"NOTE: Total sample size ({total}) is small. Consider collecting more data."
        return None

    def _large_n_note(self, n: int) -> Optional[str]:
        """Return a warning when N is large enough to make p-values trivially small."""
        if n > self.LARGE_N_THRESHOLD:
            return (
                f"LARGE-N WARNING (N={n:,}): With very large samples even trivial "
                f"differences become statistically significant. Prioritise effect size "
                f"and practical significance over p-value alone."
            )
        return None

    def _stratified_sample(
        self,
        df: pd.DataFrame,
        group_col: str,
    ) -> Tuple[pd.DataFrame, bool, int]:
        """
        Proportional stratified random sample when df exceeds SAMPLE_THRESHOLD.

        Returns (sampled_df, was_sampled, original_n).
        """
        original_n = len(df)
        if original_n <= self.SAMPLE_THRESHOLD:
            return df, False, original_n

        group_counts = df[group_col].value_counts()
        sampled_parts = []
        for group_val, count in group_counts.items():
            proportion = count / original_n
            n_take = max(1, round(proportion * self.TARGET_SAMPLE))
            group_df = df[df[group_col] == group_val]
            n_take = min(n_take, len(group_df))
            sampled_parts.append(group_df.sample(n=n_take, random_state=42))

        sampled_df = pd.concat(sampled_parts).reset_index(drop=True)
        logger.info(
            f"Stratified sample: {original_n:,} -> {len(sampled_df):,} rows "
            f"(target {self.TARGET_SAMPLE:,}, stratified on '{group_col}')"
        )
        return sampled_df, True, original_n

    @staticmethod
    def _check_correlation_normality(valid: "pd.DataFrame") -> bool:
        """Return True if both x and y columns pass Shapiro-Wilk (default True on error)."""
        try:
            n_check = min(len(valid), 5000)
            normal_x = stats.shapiro(valid["x"].iloc[:n_check])[1] > 0.05
            normal_y = stats.shapiro(valid["y"].iloc[:n_check])[1] > 0.05
            return normal_x and normal_y
        except Exception:
            return True

    @staticmethod
    def _interpret_correlation_strength(abs_r: float) -> str:
        """Return a verbal label for a correlation coefficient magnitude."""
        if abs_r < 0.1:
            return "negligible"
        if abs_r < 0.3:
            return "weak"
        if abs_r < 0.5:
            return "moderate"
        if abs_r < 0.7:
            return "strong"
        return "very strong"

    @staticmethod
    def _check_two_group_normality(groups: list) -> bool:
        """Return True if both groups pass Shapiro-Wilk normality (default True on error)."""
        try:
            normal1 = (
                stats.shapiro(groups[0][:5000])[1] > 0.05
                if len(groups[0]) >= 3
                else True
            )
            normal2 = (
                stats.shapiro(groups[1][:5000])[1] > 0.05
                if len(groups[1]) >= 3
                else True
            )
            return normal1 and normal2
        except Exception:
            return True

    @staticmethod
    def _parametric_two_group(groups: list):
        """Run Welch's t-test and return (stat, p_value, test_name, effect_size)."""
        stat, p_value = stats.ttest_ind(groups[0], groups[1], equal_var=False)
        pooled_std = np.sqrt((groups[0].var() + groups[1].var()) / 2)
        effect_size = (
            abs(groups[0].mean() - groups[1].mean()) / pooled_std
            if pooled_std > 0
            else 0
        )
        return stat, p_value, "Welch's t-test", effect_size

    @staticmethod
    def _nonparametric_two_group(groups: list):
        """Run Mann-Whitney U test and return (stat, p_value, test_name, effect_size)."""
        stat, p_value = stats.mannwhitneyu(
            groups[0], groups[1], alternative="two-sided"
        )
        n1, n2 = len(groups[0]), len(groups[1])
        effect_size = 1 - (2 * stat) / (n1 * n2)
        return stat, p_value, "Mann-Whitney U test", effect_size

    def _two_group_test(
        self,
        group_data: Dict[str, np.ndarray],
        group_means: Dict[str, float],
        group_stds: Dict[str, float],
        sample_sizes: Dict[str, int],
    ) -> StatisticalResult:
        """Perform two-group comparison (t-test or Mann-Whitney)."""
        groups = list(group_data.values())

        use_parametric = self._check_two_group_normality(groups)

        if use_parametric:
            stat, p_value, test_name, effect_size = self._parametric_two_group(groups)
        else:
            stat, p_value, test_name, effect_size = self._nonparametric_two_group(
                groups
            )

        # Effect size interpretation
        effect_interp = self._interpret_effect_size(abs(effect_size))

        # Confidence interval for mean difference
        mean_diff = groups[0].mean() - groups[1].mean()
        se_diff = np.sqrt(
            groups[0].var() / len(groups[0]) + groups[1].var() / len(groups[1])
        )
        ci = (mean_diff - 1.96 * se_diff, mean_diff + 1.96 * se_diff)

        return StatisticalResult(
            test_name=test_name,
            test_statistic=float(stat),
            p_value=float(p_value),
            is_significant=p_value < 0.05,
            effect_size=float(effect_size),
            effect_size_interpretation=effect_interp,
            confidence_interval=ci,
            sample_sizes=sample_sizes,
            group_means=group_means,
            group_stds=group_stds,
            additional_info={"mean_difference": float(mean_diff)},
        )

    def _multi_group_test(
        self,
        group_data: Dict[str, np.ndarray],
        group_means: Dict[str, float],
        group_stds: Dict[str, float],
        sample_sizes: Dict[str, int],
    ) -> StatisticalResult:
        """Perform multi-group comparison (ANOVA or Kruskal-Wallis)."""
        groups = list(group_data.values())

        # Check normality
        try:
            all_normal = all(
                stats.shapiro(g[:5000])[1] > 0.05 if len(g) >= 3 else True
                for g in groups
            )
        except Exception:
            all_normal = True

        if all_normal:
            # One-way ANOVA
            stat, p_value = stats.f_oneway(*groups)
            test_name = "One-way ANOVA"

            # Eta-squared effect size
            all_data = np.concatenate(groups)
            grand_mean = all_data.mean()
            ss_between = sum(len(g) * (g.mean() - grand_mean) ** 2 for g in groups)
            ss_total = sum((all_data - grand_mean) ** 2)
            effect_size = ss_between / ss_total if ss_total > 0 else 0
        else:
            # Kruskal-Wallis H test
            stat, p_value = stats.kruskal(*groups)
            test_name = "Kruskal-Wallis H test"

            # Epsilon-squared effect size
            n = sum(len(g) for g in groups)
            effect_size = (
                (stat - len(groups) + 1) / (n - len(groups)) if n > len(groups) else 0
            )

        effect_interp = self._interpret_effect_size(
            abs(effect_size), is_eta_squared=True
        )

        return StatisticalResult(
            test_name=test_name,
            test_statistic=float(stat),
            p_value=float(p_value),
            is_significant=p_value < 0.05,
            effect_size=float(effect_size),
            effect_size_interpretation=effect_interp,
            sample_sizes=sample_sizes,
            group_means=group_means,
            group_stds=group_stds,
            additional_info={"num_groups": len(groups)},
        )

    def correlation(
        self, df: pd.DataFrame, var1: str, var2: str
    ) -> Optional[StatisticalResult]:
        """
        Compute correlation between two numeric variables.

        Automatically selects Pearson (both normal) or Spearman (non-normal)
        based on Shapiro-Wilk normality test on up to 5,000 samples.
        """
        if not self.scipy_available:
            return None

        if var1 not in df.columns or var2 not in df.columns:
            return None

        df_clean = df[[var1, var2]].dropna()
        x = pd.to_numeric(df_clean[var1], errors="coerce")
        y = pd.to_numeric(df_clean[var2], errors="coerce")

        valid = pd.DataFrame({"x": x, "y": y}).dropna()
        if len(valid) < 3:
            return None

        large_n_note = self._large_n_note(len(valid))

        # Auto-select Pearson vs Spearman based on normality
        use_pearson = self._check_correlation_normality(valid)
        if use_pearson:
            r, p_value = stats.pearsonr(valid["x"], valid["y"])
            test_name = "Pearson Correlation"
        else:
            r, p_value = stats.spearmanr(valid["x"], valid["y"])
            test_name = "Spearman Rank Correlation"

        interp = self._interpret_correlation_strength(abs(r))

        return StatisticalResult(
            test_name=test_name,
            test_statistic=float(r),
            p_value=float(p_value),
            is_significant=p_value < 0.05,
            effect_size=float(r),
            effect_size_interpretation=interp,
            sample_sizes={"n": len(valid)},
            additional_info={
                "r_squared": float(r**2),
                "large_n_note": large_n_note,
                "value_column": var1,
                "group_column": var2,
            },
        )

    def tukey_hsd(
        self, df: pd.DataFrame, value_column: str, group_column: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Tukey HSD post-hoc pairwise comparisons after significant ANOVA.

        Returns list of dicts with group1, group2, p_value, statistic, significant.
        Returns None if fewer than 3 groups or scipy unavailable.
        """
        if not self.scipy_available:
            return None

        if value_column not in df.columns or group_column not in df.columns:
            return None

        df_clean = df[[value_column, group_column]].dropna().copy()
        df_clean[value_column] = pd.to_numeric(df_clean[value_column], errors="coerce")
        df_clean = df_clean.dropna()

        groups_dict = {
            name: grp[value_column].values
            for name, grp in df_clean.groupby(group_column)
        }
        group_names = list(groups_dict.keys())
        groups = list(groups_dict.values())

        if len(groups) < 3:
            return None

        try:
            result = stats.tukey_hsd(*groups)
            pairwise = []
            for i in range(len(group_names)):
                for j in range(i + 1, len(group_names)):
                    pairwise.append(
                        {
                            "group1": str(group_names[i]),
                            "group2": str(group_names[j]),
                            "p_value": float(result.pvalue[i][j]),
                            "statistic": float(result.statistic[i][j]),
                            "significant": bool(result.pvalue[i][j] < 0.05),
                        }
                    )
            return pairwise
        except Exception as e:
            logger.warning(f"Tukey HSD failed: {e}")
            return None

    @staticmethod
    def apply_bonferroni_correction(test_results: List["StatisticalResult"]) -> None:
        """
        Apply Bonferroni correction in-place across a list of StatisticalResult objects.

        Adjusts p-values by multiplying by the number of tests (capped at 1.0).
        Stores bonferroni_p, bonferroni_significant, and n_tests_corrected_for
        in each result's additional_info.
        """
        n = len(test_results)
        if n <= 1:
            return
        for tr in test_results:
            adj_p = min(float(tr.p_value) * n, 1.0)
            tr.additional_info["bonferroni_p"] = adj_p
            tr.additional_info["bonferroni_significant"] = adj_p < 0.05
            tr.additional_info["n_tests_corrected_for"] = n

    def chi_square(
        self, df: pd.DataFrame, var1: str, var2: str
    ) -> Optional[StatisticalResult]:
        """Chi-square test of independence for categorical variables."""
        if not self.scipy_available:
            return None

        if var1 not in df.columns or var2 not in df.columns:
            return None

        # Large-N handling: stratified sample before building contingency table
        original_n_chi = len(df)
        large_n_note = self._large_n_note(original_n_chi)
        if original_n_chi > self.SAMPLE_THRESHOLD:
            df, _, _ = self._stratified_sample(df, var1)

        # Create contingency table
        contingency = pd.crosstab(df[var1], df[var2])

        if contingency.size < 4:  # Need at least 2x2
            return None

        chi2, p_value, dof, expected = stats.chi2_contingency(contingency)

        # Cramér's V effect size
        n = contingency.sum().sum()
        min_dim = min(contingency.shape) - 1
        cramers_v = np.sqrt(chi2 / (n * min_dim)) if min_dim > 0 and n > 0 else 0

        if cramers_v < 0.1:
            interp = "negligible"
        elif cramers_v < 0.3:
            interp = "small"
        elif cramers_v < 0.5:
            interp = "medium"
        else:
            interp = "large"

        return StatisticalResult(
            test_name="Chi-square Test of Independence",
            test_statistic=float(chi2),
            p_value=float(p_value),
            is_significant=p_value < 0.05,
            effect_size=float(cramers_v),
            effect_size_interpretation=interp,
            additional_info={
                "degrees_of_freedom": int(dof),
                "contingency_shape": contingency.shape,
                "large_n_note": large_n_note,
                "original_n": original_n_chi,
            },
        )

    def _interpret_effect_size(
        self, effect: float, is_eta_squared: bool = False
    ) -> str:
        """Interpret effect size magnitude."""
        if is_eta_squared:
            # Eta-squared interpretation
            if effect < 0.01:
                return "negligible"
            elif effect < 0.06:
                return "small"
            elif effect < 0.14:
                return "medium"
            else:
                return "large"
        else:
            # Cohen's d interpretation
            if effect < 0.2:
                return "negligible"
            elif effect < 0.5:
                return "small"
            elif effect < 0.8:
                return "medium"
            else:
                return "large"

    def _fallback_comparison(
        self, df: pd.DataFrame, value_column: str, group_column: str
    ) -> Optional[StatisticalResult]:
        """Fallback when scipy is not available - basic comparison only."""
        if value_column not in df.columns or group_column not in df.columns:
            return None

        df_clean = df[[value_column, group_column]].dropna()
        df_clean[value_column] = pd.to_numeric(df_clean[value_column], errors="coerce")
        df_clean = df_clean.dropna()

        groups = df_clean.groupby(group_column)[value_column]

        group_means = {str(k): float(v.mean()) for k, v in groups}
        group_stds = {str(k): float(v.std()) for k, v in groups}
        sample_sizes = {str(k): len(v) for k, v in groups}

        return StatisticalResult(
            test_name="Descriptive Comparison (scipy not available)",
            test_statistic=0.0,
            p_value=1.0,
            is_significant=False,
            sample_sizes=sample_sizes,
            group_means=group_means,
            group_stds=group_stds,
            additional_info={"warning": "Install scipy for proper statistical tests"},
        )

    def _query_data_to_dataframe(self, data: list) -> Optional[pd.DataFrame]:
        """Convert raw query data list to a DataFrame, or return None if unsupported."""
        if not data:
            return None
        if isinstance(data[0], (dict, list, tuple)):
            df = pd.DataFrame(data)
            return df if not df.empty else None
        return None

    def _emit_large_n_advisory(
        self, results: Dict[str, Any], query_key: str, total_rows: int
    ) -> None:
        """Append a large-N advisory to summary_text when row count exceeds threshold."""
        large_n_summary = (
            f"LARGE DATASET ({total_rows:,} rows) for {query_key}: "
            f"Statistical significance is easily achieved at this scale; "
            f"prioritise effect sizes over p-values."
        )
        results["summary_text"].append(large_n_summary)
        logger.info(large_n_summary)

    def _build_column_orders(
        self, df: pd.DataFrame, hypothesis_tokens: set
    ) -> Tuple[list, list]:
        """Return (numeric_order, categorical_order) prioritising hypothesis-mentioned columns."""
        numeric_cols = list(df.select_dtypes(include=[np.number]).columns)
        preferred_numeric = [c for c in numeric_cols if str(c) in hypothesis_tokens]
        numeric_order = preferred_numeric + [
            c for c in numeric_cols if c not in preferred_numeric
        ]

        categorical_cols = list(
            df.select_dtypes(include=["object", "category"]).columns
        )
        preferred_categorical = [
            c for c in categorical_cols if str(c) in hypothesis_tokens
        ]
        categorical_order = preferred_categorical + [
            c for c in categorical_cols if c not in preferred_categorical
        ]
        return numeric_order, categorical_order

    def _collect_descriptive_stats(
        self, df: pd.DataFrame, numeric_order: list, results: Dict[str, Any]
    ) -> None:
        """Compute and accumulate descriptive stats for up to 5 numeric columns."""
        for col in numeric_order[:5]:
            desc = self.descriptive_stats(df, col)
            if desc:
                results["descriptive_stats"].append(desc)
                results["summary_text"].append(desc.to_prompt_text())

    def _check_aggregated_data(
        self,
        df: pd.DataFrame,
        query_key: str,
        first_group_col: str,
        first_value_col: str,
        results: Dict[str, Any],
        trace_entry: Dict[str, Any],
    ) -> bool:
        """
        Detect aggregated data (≤1 row per group) and record an advisory.
        Returns True if data is aggregated and the query should be skipped.
        """
        if first_group_col not in df.columns or first_value_col not in df.columns:
            return False
        max_group_size = int(
            df[first_group_col].value_counts().max()
            if not df[first_group_col].empty
            else 0
        )
        if max_group_size > 1:
            return False

        agg_vals = (
            df[[first_group_col, first_value_col]]
            .dropna()
            .set_index(first_group_col)[first_value_col]
            .to_dict()
        )
        agg_summary = (
            f"AGGREGATED DATA ({query_key}) — statistical tests require "
            f"raw individual rows, not grouped summaries.\n"
            f"Group values returned: "
            + ", ".join(
                f"{g}={v:.4f}" if isinstance(v, (int, float)) else f"{g}={v}"
                for g, v in agg_vals.items()
            )
        )
        results["summary_text"].append(agg_summary)
        logger.warning(
            f"{query_key}: data appears aggregated (max 1 row/group) — "
            "skipping statistical test"
        )
        trace_entry["test_outcome"] = {
            "test_name": "Aggregated Data — No Statistical Test",
            "warning": agg_summary,
        }
        return True

    def _run_group_comparison(
        self,
        df: pd.DataFrame,
        candidate_pairs: List[Tuple[str, str]],
        query_key: str,
        source_question: str,
        results: Dict[str, Any],
        trace_entry: Dict[str, Any],
    ) -> None:
        """Run group comparison (categorical vs numeric) and update results."""
        best_test: Optional[StatisticalResult] = None
        for value_col, group_col in candidate_pairs:
            test_result = self.compare_groups(df, value_col, group_col)
            if not test_result:
                continue
            if test_result.test_name != "Sample Size Check Failed":
                best_test = test_result
                break
            best_test = best_test or test_result

        if not best_test:
            return

        best_test.additional_info.setdefault("source_query", query_key)
        best_test.additional_info.setdefault("source_question", source_question)
        self._maybe_add_tukey_hsd(df, best_test)

        results["statistical_tests"].append(best_test)
        results["summary_text"].append(best_test.to_prompt_text())
        trace_entry["test_outcome"] = {
            "test_name": best_test.test_name,
            "p_value": best_test.p_value,
            "is_significant": best_test.is_significant,
            "sample_sizes": best_test.sample_sizes,
            "value_column": best_test.additional_info.get("value_column"),
            "group_column": best_test.additional_info.get("group_column"),
            "warning": best_test.additional_info.get("warning")
            or best_test.additional_info.get("sample_warning"),
        }

    def _maybe_add_tukey_hsd(
        self, df: pd.DataFrame, best_test: "StatisticalResult"
    ) -> None:
        """Add Tukey HSD post-hoc pairs to a significant ANOVA result."""
        if not (best_test.is_significant and best_test.test_name == "One-way ANOVA"):
            return
        v_col = best_test.additional_info.get("value_column")
        g_col = best_test.additional_info.get("group_column")
        if v_col and g_col:
            tukey_pairs = self.tukey_hsd(df, v_col, g_col)
            if tukey_pairs:
                best_test.additional_info["tukey_hsd_pairwise"] = tukey_pairs

    def _run_correlation_tests(
        self,
        df: pd.DataFrame,
        numeric_order: list,
        query_key: str,
        source_question: str,
        results: Dict[str, Any],
        trace_entry: Dict[str, Any],
    ) -> None:
        """Run Pearson/Spearman correlation for numeric-only data."""
        for i, var1 in enumerate(numeric_order[:3]):
            for var2 in numeric_order[i + 1 : 4]:
                corr = self.correlation(df, str(var1), str(var2))
                if not corr:
                    continue
                corr.additional_info.setdefault("source_query", query_key)
                corr.additional_info.setdefault("source_question", source_question)
                results["statistical_tests"].append(corr)
                results["summary_text"].append(corr.to_prompt_text())
                if trace_entry["test_outcome"] is None:
                    trace_entry["test_outcome"] = {
                        "test_name": corr.test_name,
                        "p_value": corr.p_value,
                        "is_significant": corr.is_significant,
                        "value_column": str(var1),
                        "group_column": str(var2),
                    }

    def _run_chi_square_tests(
        self,
        df: pd.DataFrame,
        categorical_order: list,
        query_key: str,
        source_question: str,
        results: Dict[str, Any],
        trace_entry: Dict[str, Any],
    ) -> None:
        """Run chi-square tests for categorical-only data."""
        for i, var1 in enumerate(categorical_order[:2]):
            for var2 in categorical_order[i + 1 : 3]:
                chi = self.chi_square(df, str(var1), str(var2))
                if not chi:
                    continue
                chi.additional_info.setdefault("source_query", query_key)
                chi.additional_info.setdefault("source_question", source_question)
                results["statistical_tests"].append(chi)
                results["summary_text"].append(chi.to_prompt_text())
                if trace_entry["test_outcome"] is None:
                    trace_entry["test_outcome"] = {
                        "test_name": chi.test_name,
                        "p_value": chi.p_value,
                        "is_significant": chi.is_significant,
                        "value_column": str(var1),
                        "group_column": str(var2),
                    }

    def _analyze_single_query(
        self,
        query_key: str,
        query_data: Dict[str, Any],
        hypothesis_tokens: set,
        results: Dict[str, Any],
    ) -> None:
        """Analyze a single query's data and append findings to results."""
        data = query_data.get("data", [])
        df = self._query_data_to_dataframe(data)
        if df is None:
            return

        total_rows = len(df)
        if total_rows > self.LARGE_N_THRESHOLD:
            self._emit_large_n_advisory(results, query_key, total_rows)

        df = self._infer_column_meanings(df)

        trace_entry: Dict[str, Any] = {
            "query_key": query_key,
            "question": query_data.get("question", ""),
            "df_columns": [str(c) for c in df.columns.tolist()],
            "df_dtypes": {str(c): str(df[c].dtype) for c in df.columns.tolist()[:20]},
            "hypothesis_tokens": sorted(list(hypothesis_tokens))[:50],
            "selected": {},
            "test_outcome": None,
        }

        numeric_order, categorical_order = self._build_column_orders(
            df, hypothesis_tokens
        )
        trace_entry["selected"]["numeric_order"] = [str(c) for c in numeric_order[:10]]
        trace_entry["selected"]["categorical_order"] = [
            str(c) for c in categorical_order[:10]
        ]

        self._collect_descriptive_stats(df, numeric_order, results)

        source_question = query_data.get("question", "")

        if categorical_order and numeric_order:
            candidate_pairs: List[Tuple[str, str]] = [
                (str(v), str(g))
                for g in categorical_order[:3]
                for v in numeric_order[:3]
            ]
            trace_entry["selected"]["candidate_pairs"] = candidate_pairs

            first_group_col = str(categorical_order[0])
            first_value_col = str(numeric_order[0])
            is_aggregated = self._check_aggregated_data(
                df, query_key, first_group_col, first_value_col, results, trace_entry
            )
            if is_aggregated:
                results["trace"].append(trace_entry)
                return

            self._run_group_comparison(
                df, candidate_pairs, query_key, source_question, results, trace_entry
            )

        elif len(numeric_order) >= 2 and not categorical_order:
            self._run_correlation_tests(
                df, numeric_order, query_key, source_question, results, trace_entry
            )

        elif len(categorical_order) >= 2 and not numeric_order:
            self._run_chi_square_tests(
                df, categorical_order, query_key, source_question, results, trace_entry
            )

        results["trace"].append(trace_entry)

    def analyze_hypothesis_data(
        self, collected_data: Dict[str, Any], hypothesis: str
    ) -> Dict[str, Any]:
        """
        Analyze all collected data and produce statistical results.

        Returns structured results for LLM interpretation.
        """
        results: Dict[str, Any] = {
            "descriptive_stats": [],
            "statistical_tests": [],
            "summary_text": [],
            "trace": [],
        }

        # Extract explicit column hints from the hypothesis (e.g., "ltr", "member_type")
        # This prevents "first numeric/first categorical" from picking irrelevant columns.
        hypothesis_tokens = set(re.findall(r"[A-Za-z_]\w*", hypothesis or ""))

        for query_key, query_data in collected_data.items():
            if "error" in query_data or not query_data.get("data"):
                continue
            self._analyze_single_query(
                query_key, query_data, hypothesis_tokens, results
            )

        # Bonferroni correction across ALL tests collected this run
        self.apply_bonferroni_correction(results["statistical_tests"])

        return results

    def _infer_column_meanings(self, df: pd.DataFrame) -> pd.DataFrame:
        """Infer column meanings from generic names like col_0, col_1."""
        # Common SQL aggregation patterns: (group, value) or (group, count)
        if len(df.columns) == 2:
            col0, col1 = df.columns[0], df.columns[1]

            def _is_string_like(dtype) -> bool:
                return pd.api.types.is_string_dtype(
                    dtype
                ) or pd.api.types.is_object_dtype(dtype)

            if _is_string_like(df[col0]) and pd.api.types.is_numeric_dtype(df[col1]):
                df = df.rename(columns={col0: "group", col1: "value"})
            elif _is_string_like(df[col1]) and pd.api.types.is_numeric_dtype(df[col0]):
                df = df.rename(columns={col1: "group", col0: "value"})

        return df
