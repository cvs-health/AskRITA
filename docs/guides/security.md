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
# Security: SQL Safety, Prompt Injection, and PII Detection

Ask RITA includes multiple layers of security to prevent destructive database operations, prompt injection attacks, and accidental exposure of personal information.

## Table of Contents

- [Overview](#overview)
- [SQL Safety](#sql-safety)
- [Input Validation](#input-validation)
- [Prompt Injection Detection](#prompt-injection-detection)
- [PII/PHI Detection](#piiphi-detection)
- [Configuration Reference](#configuration-reference)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

Ask RITA enforces security at three layers:

```mermaid
flowchart TD
    A[User Question] --> B[Input Validation]
    B -->|"Block XSS, length, suspicious patterns"| C[Prompt Injection Detection]
    C -->|"Block instruction override, embedded SQL"| D["PII/PHI Detection (optional)"]
    D -->|"Scan with Microsoft Presidio"| E[LLM Generates SQL]
    E --> F[SQL Safety Validation]
    F -->|"Block DML/DDL, suspicious functions, SELECT *"| G[Execute Query]
    style A fill:#2F5496,color:#fff
    style B fill:#4CAF50,color:#fff
    style C fill:#4CAF50,color:#fff
    style D fill:#4CAF50,color:#fff
    style E fill:#0288D1,color:#fff
    style F fill:#4CAF50,color:#fff
    style G fill:#4CAF50,color:#fff
```

All layers raise `ValidationError` when a violation is detected, preventing the query from reaching the database.

## SQL Safety

SQL safety validation runs on every generated SQL query **before** it is executed against the database.

### Configuration

```yaml
workflow:
  sql_safety:
    allowed_query_types:
      - "SELECT"
      - "WITH"
    forbidden_patterns:
      - "DROP"
      - "DELETE"
      - "TRUNCATE"
      - "ALTER"
      - "CREATE"
      - "INSERT"
      - "UPDATE"
      - "GRANT"
      - "REVOKE"
      - "EXEC"
      - "EXECUTE"
      - "MERGE"
      - "REPLACE"
      - "LOAD"
      - "IMPORT"
      - "EXPORT"
      - "BACKUP"
      - "RESTORE"
      - "SHUTDOWN"
    suspicious_functions:
      - "OPENROWSET"
      - "OPENDATASOURCE"
      - "XP_"
      - "SP_"
      - "DBMS_"
      - "UTL_FILE"
      - "UTL_HTTP"
      - "BULK"
      - "OUTFILE"
      - "DUMPFILE"
    max_sql_length: 50000
    allow_select_star: false
```

### Validation Rules

| Check | What It Does | Default |
|---|---|---|
| **Allowed query types** | First token of normalized SQL must be `SELECT` or `WITH` | `["SELECT", "WITH"]` |
| **Forbidden patterns** | Blocks DML/DDL keywords as substrings (case-insensitive, after comment stripping) | 18 patterns (see above) |
| **Suspicious functions** | Blocks database-specific dangerous functions | 10 patterns |
| **Max SQL length** | Rejects queries exceeding a character limit | 50,000 |
| **SELECT * blocking** | Optionally rejects `SELECT *` and `.*` patterns | Blocked by default (`allow_select_star: false`) |

### Comment Stripping

Before validation, SQL comments are stripped:

- Single-line comments: `-- comment`
- Multi-line comments: `/* comment */`

This prevents attackers from hiding forbidden patterns inside comments.

### Customizing SQL Safety

To allow `SELECT *` queries:

```yaml
workflow:
  sql_safety:
    allow_select_star: true
```

To allow additional query types (e.g., `EXPLAIN`):

```yaml
workflow:
  sql_safety:
    allowed_query_types:
      - "SELECT"
      - "WITH"
      - "EXPLAIN"
```

## Input Validation

Input validation runs on every user question before it reaches the LLM.

### Configuration

```yaml
workflow:
  input_validation:
    max_question_length: 10000
    blocked_substrings:
      - "<script"
      - "javascript:"
      - "data:"
      - "vbscript:"
      - "@@"
```

### Validation Rules

| Check | What It Does | Default |
|---|---|---|
| **Max question length** | Rejects questions exceeding a character limit | 10,000 |
| **Blocked substrings** | Case-insensitive substring matching against a block list | XSS and injection patterns |

### Customizing Blocked Substrings

Add domain-specific blocked content:

```yaml
workflow:
  input_validation:
    max_question_length: 5000
    blocked_substrings:
      - "<script"
      - "javascript:"
      - "data:"
      - "vbscript:"
      - "@@"
      - "password"
      - "secret"
```

## Prompt Injection Detection

Prompt injection detection runs on the user question (in `query()` mode) to catch attempts to manipulate the LLM's behavior.

### Detection Categories

Three categories of patterns are checked:

**1. Instruction Override Patterns**

Detects attempts to override the system prompt or LLM instructions:

- "ignore all previous instructions"
- "disregard your instructions"
- "forget your training"
- "you are now a different AI"
- "act as if you have no restrictions"
- Jailbreak-style phrases

**2. Dangerous SQL Phrases**

Detects natural-language requests for destructive operations:

- "drop table"
- "delete from"
- "truncate table"
- "alter table"
- Similar DML/DDL phrases embedded in questions

**3. Embedded SQL Patterns**

Detects raw SQL injected into questions:

- `SELECT ... FROM` patterns
- Backtick-prefixed SQL statements
- "run this sql" / "execute this query" phrases
- `FROM table WHERE column = value` patterns

### Behavior

- Runs **before** the LLM sees the question
- Only runs on `query()`, not on `chat()` message lists
- Raises `ValidationError` with a user-friendly message
- Patterns are checked with regex (case-insensitive)

### Error Messages

When injection is detected, the user sees:

- For instruction overrides: *"Your question appears to contain instructions rather than a data question. Please rephrase as a natural language question about your data."*
- For SQL patterns: *"Your question appears to contain SQL code. Please ask your question in plain English and Ask RITA will generate the appropriate SQL."*

## PII/PHI Detection

PII (Personally Identifiable Information) and PHI (Protected Health Information) detection uses **Microsoft Presidio** to scan user questions and optionally sample database rows.

### Enabling PII Detection

PII detection requires two configuration settings:

```yaml
pii_detection:
  enabled: true
  block_on_detection: true
  confidence_threshold: 0.5
  language: "en"

workflow:
  steps:
    pii_detection: true  # Enable the workflow step
```

### Configuration

```yaml
pii_detection:
  enabled: true
  block_on_detection: true       # Block queries containing PII
  log_pii_attempts: true         # Log PII detection events
  confidence_threshold: 0.5      # Minimum confidence (0.0-1.0)
  language: "en"                 # Presidio language model
  redact_in_logs: true           # Redact PII in log messages
  audit_log_path: null           # Path for PII audit log file

  # Sample data scanning
  validate_sample_data: true     # Scan database sample rows at init
  sample_data_rows: 100          # Max rows per table to scan
  sample_data_timeout: 30        # Timeout for sample scan (seconds)

  # Entity types to detect
  entities:
    - "PERSON"
    - "EMAIL_ADDRESS"
    - "PHONE_NUMBER"
    - "CREDIT_CARD"
    - "US_SSN"
    - "US_DRIVER_LICENSE"
    - "IP_ADDRESS"
    - "LOCATION"
    - "DATE_TIME"
    - "NRP"
    - "MEDICAL_LICENSE"
    - "US_BANK_NUMBER"
    - "US_PASSPORT"
    - "US_ITIN"

  # Custom recognizers (advanced)
  custom_recognizers: {}
```

### How It Works

**Question Scanning**: Before the LLM processes a question, the PII detector scans the text for entity types defined in the configuration. If PII is detected and `block_on_detection` is `true`, the query is blocked with a `ValidationError`.

**Sample Data Scanning**: At workflow initialization (when `validate_sample_data` is `true`), the detector scans sample rows from the database to check for PII in the data itself. Results are logged but do not block initialization.

### PIIDetectionResult

```python
@dataclass
class PIIDetectionResult:
    has_pii: bool                    # Whether PII was detected
    detected_entities: List[Dict]    # Entity details (type, score, snippet)
    confidence_scores: Dict          # Scores by entity type
    blocked: bool                    # Whether the query was blocked
    analysis_time_ms: float          # Detection time
    redacted_text: Optional[str]     # Text with PII redacted

    # Computed properties
    entity_count: int                # Number of entities found
    max_confidence: float            # Highest confidence score
    entity_types: Set[str]           # Unique entity types
```

### Detected Entity Format

Each detected entity contains:

```python
{
    "entity_type": "EMAIL_ADDRESS",
    "start": 15,
    "end": 35,
    "score": 0.85,
    "text_snippet": "jo***@example.com"  # Redacted if redact_in_logs=True
}
```

### Audit Logging

When `audit_log_path` is set, PII detection events are written to a dedicated log file:

```yaml
pii_detection:
  enabled: true
  log_pii_attempts: true
  audit_log_path: "logs/pii_audit.log"
```

### Dependencies

PII detection requires the Presidio analyzer:

```bash
pip install presidio-analyzer presidio-anonymizer
python -m spacy download en_core_web_lg  # Language model
```

If Presidio is not installed, PII detection is silently disabled (a warning is logged).

## Configuration Reference

### Complete Security Configuration

```yaml
workflow:
  steps:
    pii_detection: true  # Enable PII scanning step

  input_validation:
    max_question_length: 10000
    blocked_substrings:
      - "<script"
      - "javascript:"
      - "data:"
      - "vbscript:"
      - "@@"

  sql_safety:
    allowed_query_types: ["SELECT", "WITH"]
    forbidden_patterns:
      - "DROP"
      - "DELETE"
      - "TRUNCATE"
      - "ALTER"
      - "CREATE"
      - "INSERT"
      - "UPDATE"
    suspicious_functions:
      - "OPENROWSET"
      - "XP_"
      - "SP_"
    max_sql_length: 50000
    allow_select_star: false

pii_detection:
  enabled: true
  block_on_detection: true
  confidence_threshold: 0.7
  language: "en"
  validate_sample_data: true
  sample_data_rows: 100
  log_pii_attempts: true
  redact_in_logs: true
  audit_log_path: "logs/pii_audit.log"
```

## Best Practices

1. **Keep SQL safety defaults** — The default `forbidden_patterns` and `suspicious_functions` cover the most common attack vectors. Only modify if you have a specific need.

2. **Use strict PII thresholds in regulated environments** — Set `confidence_threshold: 0.7` or higher to reduce false positives while catching real PII.

3. **Enable PII audit logging** — In healthcare or financial environments, set `audit_log_path` to maintain a record of PII detection events.

4. **Block SELECT \*** — The default `allow_select_star: false` prevents accidental exposure of sensitive columns. Only enable it for development or non-sensitive databases.

5. **Use environment variables for credentials** — Never put passwords, API keys, or connection strings directly in YAML files. Use `${VAR}` substitution:
   ```yaml
   database:
     connection_string: "postgresql://${DB_USER}:${DB_PASSWORD}@host:5432/db"
   ```

6. **Review blocked substrings** — Add domain-specific blocked content (e.g., internal system names, sensitive column names) to `input_validation.blocked_substrings`.

## Troubleshooting

### ValidationError: Forbidden SQL Pattern

**Symptom**: `ValidationError: SQL query contains forbidden pattern: DROP`

The LLM generated SQL containing a blocked keyword. This is expected behavior — the safety layer prevented a potentially destructive query. Rephrase your question to be more specific about what data you want to retrieve.

### ValidationError: Question Contains Unsafe Content

**Symptom**: `ValidationError: Question contains potentially unsafe content: @@`

Your question contains a blocked substring. Check `input_validation.blocked_substrings` and either rephrase or remove the pattern from the block list if it is a false positive.

### ValidationError: Prompt Injection Detected

**Symptom**: *"Your question appears to contain instructions rather than a data question."*

The prompt injection detector flagged your question. Rephrase it as a natural-language data question without instruction-like phrases.

### PII Detection False Positives

**Symptom**: Legitimate questions are blocked by PII detection.

- Increase `confidence_threshold` (e.g., `0.7` or `0.8`)
- Narrow the `entities` list to only the types you need to detect
- Set `block_on_detection: false` to log without blocking

### PII Detection Not Working

**Symptom**: PII in questions is not detected.

- Ensure `pii_detection.enabled: true` in config
- Ensure `workflow.steps.pii_detection: true`
- Install Presidio: `pip install presidio-analyzer presidio-anonymizer`
- Install the language model: `python -m spacy download en_core_web_lg`
- Check logs for initialization warnings

### SELECT * Being Blocked

**Symptom**: Queries that need `SELECT *` fail validation.

Set `allow_select_star: true` in your config:

```yaml
workflow:
  sql_safety:
    allow_select_star: true
```

---

**See also:**

- [Configuration Guide](../configuration/overview.md) — Complete YAML configuration reference
- [NoSQL Workflow](nosql-workflow.md) — MongoDB-specific safety (blocked operations)
- [Schema Enrichment](schema-enrichment.md) — Schema descriptions to guide SQL generation away from sensitive columns
