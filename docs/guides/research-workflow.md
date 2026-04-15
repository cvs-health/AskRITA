<!--
  © 2026 CVS Health and/or one of its affiliates. All rights reserved.

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.
-->
# Research Workflow (CRISP-DM)

Ask RITA includes a full research agent that follows the **CRISP-DM** methodology to test hypotheses against your database using real statistical analysis — not LLM fabrication.

> **New in v0.13.0** — Bonferroni correction, Tukey HSD post-hoc tests, and parallel evidence execution.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [API Reference](#api-reference)
- [How It Works](#how-it-works)
- [Statistical Tests](#statistical-tests)
- [Schema Analysis](#schema-analysis)
- [Troubleshooting](#troubleshooting)

## Overview

The `ResearchAgent` orchestrates a six-phase CRISP-DM workflow:

| Phase | Name | What Happens |
|---|---|---|
| 1 | **Business Understanding** | LLM refines the hypothesis, defines success criteria and key variables |
| 2 | **Data Understanding** | Schema analysis identifies relevant columns, data quality notes, and limitations |
| 3 | **Data Preparation** | SQL Agent generates evidence queries; database executes them in parallel |
| 4 | **Modeling** | `StatisticalAnalyzer` runs real scipy-based tests on collected data |
| 5 | **Evaluation** | LLM interprets statistical results → SUPPORTED / REFUTED / INCONCLUSIVE |
| 6 | **Deployment** | LLM produces executive summary, insights, recommendations, and next steps |

Key design principles:

- **Real statistics** — All p-values, effect sizes, and confidence intervals come from scipy, not the LLM
- **LLM for interpretation** — The LLM interprets computed results, never fabricates numbers
- **Shared infrastructure** — Uses the same `ConfigManager`, `DatabaseManager`, and `LLMManager` as the SQL workflow

## Quick Start

### 1. Install Dependencies

```bash
pip install askrita
# scipy is included automatically for statistical analysis
```

### 2. Create Configuration

The research workflow uses the same YAML configuration as the SQL workflow. Any valid SQL workflow config works:

```yaml
database:
  connection_string: "postgresql://${DB_USER}:${DB_PASSWORD}@localhost:5432/mydb"
  max_results: 50000  # Research queries may need more rows

llm:
  provider: "openai"
  model: "gpt-4o"
  temperature: 0.1
```

### 3. Test a Hypothesis

```python
from askrita import ConfigManager
from askrita.research import ResearchAgent

config = ConfigManager("config.yaml")
agent = ResearchAgent(config_manager=config)

result = agent.test_hypothesis(
    research_question="Do premium customers spend more than standard customers?",
    hypothesis="Premium customers have a significantly higher average order value"
)

print(f"Conclusion: {result['conclusion']}")
print(f"Confidence: {result['confidence']}%")
print(f"Key findings: {result['insights']}")
```

## Configuration

The research workflow shares the standard Ask RITA configuration. The only research-specific parameter is `research_max_results`, set at initialization:

```python
agent = ResearchAgent(
    config_manager=config,
    research_max_results=50_000,  # Max rows per evidence query (default: 50,000)
)
```

This overrides `database.max_results` internally so evidence queries can return larger datasets for statistical analysis.

### Recommended Database Settings

```yaml
database:
  connection_string: "..."
  max_results: 50000       # Higher than typical query use
  query_timeout: 120       # Evidence queries may be complex
  cache_schema: true       # Schema is analyzed at startup
```

## Usage Examples

### Hypothesis Testing

```python
from askrita import ConfigManager
from askrita.research import ResearchAgent

config = ConfigManager("config.yaml")
agent = ResearchAgent(config_manager=config)

result = agent.test_hypothesis(
    research_question="Is there a seasonal pattern in sales?",
    hypothesis="Q4 sales are significantly higher than other quarters"
)

# Result structure
print(f"Conclusion: {result['conclusion']}")        # SUPPORTED, REFUTED, or INCONCLUSIVE
print(f"Confidence: {result['confidence']}%")        # 0-100
print(f"Validity: {result['validity_assessment']}")

# Statistical evidence
for finding in result['statistical_findings']:
    print(f"  Test: {finding['test_name']}")
    print(f"  p-value: {finding['p_value']}")
    print(f"  Significant: {finding['is_significant']}")

# Actionable output
print(f"Insights: {result['insights']}")
print(f"Recommendations: {result['recommendations']}")
print(f"Next steps: {result['next_steps']}")

# Bonferroni correction (when multiple tests)
if result.get('bonferroni_p') is not None:
    print(f"Bonferroni-corrected p: {result['bonferroni_p']}")
    print(f"Still significant: {result['bonferroni_significant']}")
```

### Ad-Hoc Queries

Use `query()` for single questions that generate SQL and return raw data:

```python
result = agent.query("What is the average order value by customer tier?")

print(f"SQL: {result['sql']}")
print(f"Answer: {result['answer']}")
print(f"Data: {result['data']}")  # Raw rows from the database
```

### Schema Analysis

Analyze your database schema to understand research potential:

```python
from askrita.research import SchemaAnalyzer

report = agent.analyze_schema()

print(f"Tables: {report.total_tables}")
print(f"Columns: {report.total_columns}")
print(f"Data model: {report.data_model_type}")
print(f"Research readiness: {report.research_readiness}")

# High-value tables for analysis
for table_name in report.high_value_tables:
    table = next(t for t in report.tables if t.name == table_name)
    print(f"\n{table.name} (entity: {table.entity_type})")
    print(f"  Research value: {table.research_value}")
    print(f"  Suggestions: {table.analysis_suggestions}")

# Generate a detailed text report
detailed = agent.schema_analyzer.generate_detailed_report(report)
print(detailed)
```

### Legacy API

The `test_assumption()` method is maintained for backwards compatibility but delegates to `test_hypothesis()`:

```python
result = agent.test_assumption(
    assumption="Premium customers have higher lifetime value",
    evidence_queries=[]  # Ignored — queries are generated automatically
)
```

## API Reference

### ResearchAgent

```python
class ResearchAgent:
    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        research_max_results: int = 50_000,
        **kwargs,  # Forwarded to SQLAgentWorkflow
    ): ...

    def test_hypothesis(
        self,
        research_question: str,
        hypothesis: str,
    ) -> Dict[str, Any]: ...

    def test_assumption(
        self,
        assumption: str,
        evidence_queries: List[str],  # Ignored
    ) -> Dict[str, Any]: ...

    def query(self, question: str) -> Dict[str, Any]: ...

    def analyze_schema(self) -> SchemaAnalysisReport: ...

    @property
    def schema(self) -> str: ...
```

### test_hypothesis Return Value

| Key | Type | Description |
|---|---|---|
| `research_question` | `str` | Original research question |
| `hypothesis` | `str` | Hypothesis being tested |
| `success_criteria` | `str` | LLM-defined criteria for support |
| `data_quality` | `str` | Assessment of data quality |
| `relevant_columns` | `list` | Columns identified as relevant |
| `data_limitations` | `str` | Known limitations of the data |
| `statistical_findings` | `list` | List of `StatisticalResult` dicts |
| `key_metrics` | `str` | Summary of key metrics |
| `bonferroni_p` | `float` | Bonferroni-corrected p-value (if multiple tests) |
| `bonferroni_significant` | `bool` | Whether result holds after correction |
| `stats_trace` | `list` | Detailed trace of statistical decisions |
| `conclusion` | `str` | `"SUPPORTED"`, `"REFUTED"`, or `"INCONCLUSIVE"` |
| `confidence` | `int` | 0–100 confidence score |
| `validity_assessment` | `str` | Assessment of conclusion validity |
| `insights` | `list` | Key insights from the analysis |
| `recommendations` | `list` | Actionable recommendations |
| `next_steps` | `list` | Suggested follow-up research |
| `queries_executed` | `int` | Number of SQL queries run |
| `errors` | `list` | Any errors encountered |
| `timestamp` | `str` | ISO timestamp |

### SchemaAnalysisReport

```python
@dataclass
class SchemaAnalysisReport:
    database_type: str
    total_tables: int
    total_columns: int
    analysis_timestamp: str
    tables: List[TableAnalysis]
    naming_patterns: Dict
    data_type_distribution: Dict
    high_value_tables: List[str]
    potential_fact_tables: List[str]
    potential_dimension_tables: List[str]
    suggested_relationships: List[Dict]
    schema_complexity: str
    data_model_type: str
    research_readiness: str
    analysis_steps: List[str]
    recommended_analyses: List[str]
```

### TableAnalysis

```python
@dataclass
class TableAnalysis:
    name: str
    full_name: str
    columns: List[ColumnAnalysis]
    description: str
    row_count_estimate: Optional[int]
    primary_keys: List[str]
    foreign_keys: List[str]
    research_value: str
    entity_type: str
    relationships: List[str]
    analysis_suggestions: List[str]
```

### ColumnAnalysis

```python
@dataclass
class ColumnAnalysis:
    name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool
    is_foreign_key: bool
    description: str
    research_potential: str
    statistical_type: str
    sample_queries: List[str]
```

## How It Works

```mermaid
flowchart TD
    A[Research Question + Hypothesis] --> B[1. Business Understanding]
    B -->|"LLM refines hypothesis, defines success criteria and key variables"| C[2. Data Understanding]
    C -->|"SchemaAnalyzer examines tables, columns, types, relationships"| D[3. Data Preparation]
    D -->|"LLM generates evidence queries; SQL Agent produces SQL; DB executes in parallel"| E[4. Modeling]
    E -->|"StatisticalAnalyzer runs scipy tests: t-test, ANOVA, correlation, chi-square"| F[5. Evaluation]
    F -->|"LLM interprets stats → SUPPORTED / REFUTED / INCONCLUSIVE"| G[6. Deployment]
    G -->|"Executive summary, insights, recommendations, next steps"| H[Final Report]
    style A fill:#2F5496,color:#fff
    style B fill:#0288D1,color:#fff
    style C fill:#4CAF50,color:#fff
    style D fill:#00897B,color:#fff
    style E fill:#4CAF50,color:#fff
    style F fill:#0288D1,color:#fff
    style G fill:#0288D1,color:#fff
    style H fill:#7B1FA2,color:#fff
```

### Integration with SQL Agent

The `ResearchAgent` constructs an internal `SQLAgentWorkflow` with several steps disabled (execution, formatting, visualization, follow-ups) so that the SQL path only **generates and validates** SQL. The research agent then executes queries directly via `DatabaseManager.execute_query()` in a thread pool for parallel evidence collection.

## Statistical Tests

The `StatisticalAnalyzer` automatically selects the appropriate test based on data characteristics:

### Test Selection Logic

| Data Shape | Normality | Test Applied |
|---|---|---|
| 2 groups, numeric | Normal (Shapiro-Wilk) | **Welch's t-test** (unequal variance) |
| 2 groups, numeric | Non-normal | **Mann-Whitney U** |
| 3+ groups, numeric | All normal | **One-way ANOVA** + **Tukey HSD** post-hoc |
| 3+ groups, numeric | Any non-normal | **Kruskal-Wallis** |
| 2 numeric columns | Normal | **Pearson correlation** |
| 2 numeric columns | Non-normal | **Spearman correlation** |
| 2+ categorical | — | **Chi-square test of independence** |

### Effect Sizes

Each test reports an effect size with interpretation:

| Test | Effect Size Metric | Interpretation Scale |
|---|---|---|
| t-test / Mann-Whitney | Cohen's d | Small (0.2), Medium (0.5), Large (0.8) |
| ANOVA | Eta-squared | Small (0.01), Medium (0.06), Large (0.14) |
| Kruskal-Wallis | Epsilon-squared | Small (0.01), Medium (0.06), Large (0.14) |
| Chi-square | Cramer's V | Small (0.1), Medium (0.3), Large (0.5) |
| Correlation | r / rho | Small (0.1), Medium (0.3), Large (0.5) |

### Multiple Testing Correction

When multiple statistical tests are run in a single hypothesis evaluation, **Bonferroni correction** is automatically applied. This adjusts p-values to control the family-wise error rate:

- `bonferroni_p = original_p * n_tests`
- `bonferroni_significant = bonferroni_p < 0.05`

### Large Dataset Handling

- Datasets over 100,000 rows are **stratified-sampled** to 50,000 rows
- Normality testing (Shapiro-Wilk) uses up to 5,000 values per group
- Large-N notes are appended to results when sample sizes exceed 10,000

### StatisticalResult

```python
@dataclass
class StatisticalResult:
    test_name: str
    test_statistic: float
    p_value: float
    is_significant: bool          # p < 0.05
    effect_size: Optional[float]
    effect_size_interpretation: Optional[str]
    confidence_interval: Optional[tuple]
    sample_sizes: Optional[Dict]
    group_means: Optional[Dict]
    group_stds: Optional[Dict]
    additional_info: Optional[Dict]

    def to_prompt_text(self) -> str:
        """Format for LLM interpretation."""
```

### DescriptiveStats

```python
@dataclass
class DescriptiveStats:
    variable: str
    count: int
    mean: float
    std: float
    min: float
    max: float
    median: float
    q1: float
    q3: float
    missing: int

    def to_prompt_text(self) -> str:
        """Format for LLM interpretation."""
```

## Schema Analysis

The `SchemaAnalyzer` provides a structured view of your database for research planning:

```python
report = agent.analyze_schema()

# Classification
print(report.data_model_type)       # e.g., "Star Schema", "Normalized"
print(report.schema_complexity)      # e.g., "Moderate"
print(report.research_readiness)     # e.g., "High"

# Table roles
print(report.potential_fact_tables)       # Transaction/event tables
print(report.potential_dimension_tables)  # Lookup/reference tables
print(report.suggested_relationships)     # FK-based joins

# Per-table detail
for table in report.tables:
    print(f"{table.name}: {table.entity_type} (value: {table.research_value})")
    for col in table.columns:
        print(f"  {col.name}: {col.statistical_type} — {col.research_potential}")
```

When `include_sample_data=True` (the default) and the schema has 20 or fewer tables, the analyzer runs sample queries on up to 5 high-value tables to estimate row counts.

## Troubleshooting

### No Statistical Tests Run

**Symptom**: `statistical_findings` is empty.

- Ensure evidence queries return enough rows (at least 2 per group for comparisons)
- Check that the data contains numeric or categorical columns appropriate for testing
- Aggregated data (1 row per group) cannot be tested — the trace will show "Aggregated Data — No Statistical Test"

### scipy Not Available

**Symptom**: Results show `test_name: "Descriptive Comparison (scipy not available)"` with `p_value: 1.0`.

- Install scipy: `pip install scipy`
- scipy is included in the default askrita installation

### Evidence Queries Failing

**Symptom**: `errors` list is non-empty, `queries_executed` is lower than expected.

- Check database permissions for the tables involved
- Increase `database.query_timeout` for complex queries
- Increase `research_max_results` if queries hit the row limit

### Inconclusive Results

The conclusion is `INCONCLUSIVE` when:

- Sample sizes are too small for meaningful statistical testing
- Effect sizes are negligible despite statistical significance
- Data quality issues prevent reliable analysis
- The hypothesis cannot be tested with the available data

---

**See also:**

- [Configuration Guide](../configuration/overview.md) — Complete YAML configuration reference
- [Usage Examples](../usage-examples.md) — SQL and NoSQL workflow examples
- [Supported Platforms](../supported-platforms.md) — Database and LLM provider support
