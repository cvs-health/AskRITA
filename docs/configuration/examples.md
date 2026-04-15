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
# Configuration Examples

Complete YAML configuration examples for every provider and database combination, plus reference tables.

## OpenAI + PostgreSQL (Production Setup)

```yaml
# REQUIRED: Environment variable
# export OPENAI_API_KEY="sk-your-key-here"
# export DB_PASSWORD="your-db-password"

database:
  connection_string: "postgresql://askrita_user:${DB_PASSWORD}@prod-db.company.com:5432/analytics"
  query_timeout: 30
  max_results: 1000
  cache_schema: true
  schema_refresh_interval: 3600

llm:
  provider: "openai"
  model: "gpt-4o"
  temperature: 0.1
  max_tokens: 4000
  timeout: 60

workflow:
  max_retries: 3
  steps:
    pii_detection: true
    parse_question: true
    get_unique_nouns: true
    generate_sql: true
    validate_and_fix_sql: true
    execute_sql: true
    format_results: true
    choose_and_format_visualization: true
    generate_followup_questions: true

# PII Detection for Production Security
pii_detection:
  enabled: true
  block_on_detection: true
  entities:
    - "PERSON"
    - "EMAIL_ADDRESS"
    - "PHONE_NUMBER"
    - "CREDIT_CARD"
    - "US_SSN"
  confidence_threshold: 0.4
  validate_sample_data: true
  audit_log_path: "/var/log/askrita/pii_audit.log"

prompts:
  generate_sql:
    system: |
      You are an expert SQL analyst. Generate valid, efficient SQL queries based on user questions.
      Always use proper joins and WHERE clauses to filter data appropriately.
    human: |
      Database schema: {schema}
      User question: {question}
      Generate SQL query:

  validate_sql:
    system: |
      You are a SQL validator. Check for syntax errors and optimize queries.
    human: |
      Validate and fix this SQL query: {sql_query}
      Error (if any): {error}

business_rules:
  result_limits:
    max_rows: 1000
    max_query_time: 30

logging:
  level: "INFO"
```

## Azure OpenAI + BigQuery (Enterprise Setup)

```yaml
# REQUIRED: gcloud auth login or service account
# REQUIRED: Azure certificate authentication

database:
  connection_string: "bigquery://my-enterprise-project/analytics_dataset"
  bigquery_gcloud_cli_auth: true
  query_timeout: 60
  max_results: 10000
  cache_schema: true
  schema_refresh_interval: 7200

llm:
  provider: "azure_openai"
  model: "gpt-4o"
  azure_endpoint: "https://my-company-openai.openai.azure.com/"
  azure_deployment: "gpt-4o-deployment"
  api_version: "2025-04-01-preview"
  azure_tenant_id: "your-tenant-id"
  azure_client_id: "your-client-id"
  azure_certificate_path: "/path/to/company-cert.pem"
  temperature: 0.1
  max_tokens: 4000

workflow:
  max_retries: 3
  steps:
    parse_question: true
    get_unique_nouns: true
    generate_sql: true
    validate_and_fix_sql: true
    execute_sql: true
    format_results: true
    choose_and_format_visualization: true
    generate_followup_questions: true

prompts:
  generate_sql:
    system: "You are an expert SQL analyst."
    human: |
      Database schema: {schema}
      User question: {question}
      Generate SQL query:
  validate_sql:
    system: "You are a SQL validator."
    human: "Validate and fix this SQL query: {sql_query}"
  format_results:
    system: "You are a data analyst."
    human: "Question: {question}\nSQL: {sql_query}\nResults: {query_results}\nProvide a clear answer."
  choose_and_format_visualization:
    system: "You are a data visualization expert."
    human: "Question: {question}\nResults: {query_results}\nChoose a chart type and format the data."
```

## Vertex AI + Snowflake (Google Cloud Setup)

```yaml
# REQUIRED: gcloud auth login
# REQUIRED: Snowflake credentials

database:
  connection_string: "snowflake://${SF_USER}:${SF_PASSWORD}@${SF_ACCOUNT}/${SF_DATABASE}?warehouse=${SF_WAREHOUSE}&schema=${SF_SCHEMA}&role=${SF_ROLE}"
  query_timeout: 120
  max_results: 10000
  cache_schema: true
  schema_refresh_interval: 3600

llm:
  provider: "vertex_ai"
  model: "gemini-1.5-pro"
  project_id: "my-gcp-project"
  location: "us-central1"
  gcloud_cli_auth: true
  temperature: 0.1
  max_tokens: 4000

workflow:
  max_retries: 3
  steps:
    parse_question: true
    get_unique_nouns: true
    generate_sql: true
    validate_and_fix_sql: true
    execute_sql: true
    format_results: true
    choose_and_format_visualization: true
    generate_followup_questions: true

prompts:
  generate_sql:
    system: "You are an expert SQL analyst."
    human: "Schema: {schema}\nQuestion: {question}\nGenerate SQL:"
  validate_sql:
    system: "You are a SQL validator."
    human: "Validate: {sql_query}"
  format_results:
    system: "You are a data analyst."
    human: "Question: {question}\nResults: {query_results}\nProvide a clear answer."
  choose_and_format_visualization:
    system: "You are a data visualization expert."
    human: "Question: {question}\nResults: {query_results}\nChoose a chart type and format the data."
```

## AWS Bedrock + SQLite (Development Setup)

```yaml
# REQUIRED: aws configure or IAM roles

database:
  connection_string: "sqlite:///./dev_database.db"
  query_timeout: 30
  max_results: 1000

llm:
  provider: "bedrock"
  model: "anthropic.claude-4-6-sonnet-20250514-v1:0"
  region_name: "us-east-1"
  temperature: 0.1
  max_tokens: 4000

workflow:
  max_retries: 3
  steps:
    parse_question: true
    get_unique_nouns: true
    generate_sql: true
    validate_and_fix_sql: true
    execute_sql: true
    format_results: true
    choose_and_format_visualization: true
    generate_followup_questions: true

prompts:
  generate_sql:
    system: "You are an expert SQL analyst."
    human: "Schema: {schema}\nQuestion: {question}\nGenerate SQL:"
  validate_sql:
    system: "You are a SQL validator."
    human: "Validate: {sql_query}"
  format_results:
    system: "You are a data analyst."
    human: "Question: {question}\nResults: {query_results}\nProvide a clear answer."
  choose_and_format_visualization:
    system: "You are a data visualization expert."
    human: "Question: {question}\nResults: {query_results}\nChoose a chart type and format the data."
```

## Configuration Priority

| Setting Type | Location | Priority | Description |
|--------------|----------|----------|-------------|
| **Environment Variables** | OS Environment | 🥇 **Highest** | Overrides all config file settings |
| **YAML Configuration** | Config file | 🥈 **Medium** | Explicit configuration settings |
| **Built-in Defaults** | Code | 🥉 **Lowest** | Framework defaults when not specified |

## Mandatory vs Optional Settings

### LLM Configuration

| Provider | Mandatory Settings | Optional Settings | Environment Variables |
|----------|-------------------|-------------------|----------------------|
| **OpenAI** | `provider`, `model` | `temperature`, `max_tokens`, `timeout`, `base_url`, `organization`, `ca_bundle_path` | `OPENAI_API_KEY` (required) |
| **Azure OpenAI** | `provider`, `model`, `azure_endpoint`, `azure_deployment`, `azure_tenant_id`, `azure_client_id`, `azure_certificate_path` | `api_version`, `azure_certificate_password`, `temperature`, `max_tokens`, `timeout` | None |
| **Vertex AI** | `provider`, `model`, `project_id`, `location`, (`credentials_path` OR `gcloud_cli_auth`) | `temperature`, `max_tokens`, `top_p`, `timeout` | `GOOGLE_APPLICATION_CREDENTIALS` (if not using gcloud CLI) |
| **Bedrock** | `provider`, `model`, `region_name` | `temperature`, `max_tokens`, `top_p`, `timeout` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` (if not using IAM) |

### Database Configuration

| Database | Mandatory Settings | Optional Settings | Environment Variables |
|----------|-------------------|-------------------|----------------------|
| **PostgreSQL** | `connection_string` | `query_timeout`, `max_results`, `cache_schema`, `schema_refresh_interval` | `DB_PASSWORD`, `DB_HOST`, `DB_USER`, `DB_NAME` |
| **MySQL** | `connection_string` | `query_timeout`, `max_results`, `cache_schema`, `schema_refresh_interval` | `DB_PASSWORD`, `DB_HOST`, `DB_USER`, `DB_NAME` |
| **SQLite** | `connection_string` | `query_timeout`, `max_results`, `cache_schema`, `schema_refresh_interval` | None |
| **BigQuery** | `connection_string`, (`bigquery_credentials_path` OR `bigquery_gcloud_cli_auth`) | `query_timeout`, `max_results`, `cache_schema`, `schema_refresh_interval`, `cross_project_access`, `schema_descriptions` | `GOOGLE_APPLICATION_CREDENTIALS` (if not using gcloud CLI) |
| **Snowflake** | `connection_string` (with all parameters) | `query_timeout`, `max_results`, `cache_schema`, `schema_refresh_interval` | `SF_USER`, `SF_PASSWORD`, `SF_ACCOUNT`, `SF_DATABASE`, `SF_WAREHOUSE`, `SF_SCHEMA`, `SF_ROLE` |
| **MongoDB** | `connection_string` (with database name) | `query_timeout`, `max_results`, `cache_schema`, `schema_refresh_interval` | `MONGO_USER`, `MONGO_PASSWORD`, `MONGO_HOST`, `MONGO_DB` |

### Framework Configuration

| Section | Mandatory Settings | Optional Settings |
|---------|-------------------|-------------------|
| **Prompts** | `parse_question`, `generate_sql`, `validate_sql`, `format_results`, `choose_and_format_visualization` | `generate_followup_questions`, additional custom prompts |
| **Workflow** | None | `max_retries`, `steps`, `input_validation`, `parse_overrides`, `sql_safety`, `conversation_context` |
| **Business Rules** | None | `result_limits`, `allowed_tables` |
| **PII Detection** | None | `enabled`, `block_on_detection`, `entities`, `confidence_threshold`, `validate_sample_data`, `audit_log_path` |
| **Logging** | None | `level`, `format` |


## Testing Configurations

### Configuration Validation

```bash
# Test complete configuration (validates LLM and database connectivity)
askrita test --config my-config.yaml

# Verbose output for debugging
askrita test --config my-config.yaml --verbose
```

### Development Testing

```bash
# Use minimal config for quick testing
cat > test-config.yaml << EOF
database:
  connection_string: "sqlite:///./test.db"
llm:
  provider: "openai"
  model: "gpt-4o-mini"
prompts:
  generate_sql:
    system: "Generate SQL"
    human: "{question}"
  validate_sql:
    system: "Validate SQL"
    human: "{sql_query}"
  format_results:
    system: "Format results"
    human: "Question: {question}\nResults: {query_results}"
  choose_and_format_visualization:
    system: "Choose visualization"
    human: "Question: {question}\nResults: {query_results}"
EOF

# Test with minimal config
OPENAI_API_KEY=your-key askrita test --config test-config.yaml
```


## Example Configuration Files

See the complete example configurations in the `example-configs/` directory:

## SQL Agent Configurations
- `query-minimal.yaml` - Minimal required settings
- `query-openai.yaml` - OpenAI + PostgreSQL production setup
- `query-azure-openai.yaml` - Azure OpenAI enterprise setup
- `query-vertex-ai.yaml` - Google Vertex AI configuration
- `query-vertex-ai-gcloud.yaml` - Vertex AI with gcloud CLI authentication
- `query-bedrock.yaml` - AWS Bedrock configuration
- `query-bigquery.yaml` - BigQuery cloud analytics setup (updated with v0.2.1 features)
- `query-bigquery-advanced.yaml` - Comprehensive BigQuery example with hybrid schema descriptions and cross-project access (New in v0.2.1)
- `query-snowflake.yaml` - Snowflake data warehouse setup
- `schema-descriptions-simple.yaml` - Simple example showing hybrid schema descriptions feature (New in v0.2.1)
- `example-zscaler-config.yaml` - Complete example with cross-project access, security settings, and corporate proxy support

## Privacy & Security Configurations (New in v0.10.1)
- `query-pii-detection.yaml` - Basic PII detection enabled for development
- `query-bigquery-pii.yaml` - Enterprise-grade PII protection with HIPAA/GDPR compliance settings

## Data Classification Configurations
- `data-classification-openai.yaml` - OpenAI for classification
- `data-classification-azure.yaml` - Azure OpenAI for classification
- `data-classification-vertex-ai.yaml` - Vertex AI for classification
- `data-classification-general.yaml` - General classification template
- `data-classification-csv-examples.yaml` - CSV processing examples

## Additional Examples
- `mcp-server-config.yaml` - MCP server configuration for AI assistants

