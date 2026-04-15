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
# Supported Platforms

Databases, LLM providers, and authentication options supported by Ask RITA.

## SQL Databases

- **PostgreSQL** (recommended)
- **MySQL/MariaDB**
- **SQLite**
- **SQL Server**
- **Google BigQuery**
- **Snowflake**
- **IBM DB2**
- Any SQLAlchemy-supported database

## NoSQL Databases

- **MongoDB** — `mongodb://` and `mongodb+srv://` (Atlas) connections

> See [NoSQL Workflow Guide](guides/nosql-workflow.md) for comprehensive MongoDB setup and usage.

## Connection String Examples

```yaml
# PostgreSQL
connection_string: "postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:5432/db"

# MySQL
connection_string: "mysql+pymysql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:3306/db"

# SQLite
connection_string: "sqlite:///./database.db"

# BigQuery (requires service account credentials)
connection_string: "bigquery://project-id/dataset-id"

# Snowflake
connection_string: "snowflake://${SNOWFLAKE_USER}:${SNOWFLAKE_PASSWORD}@${SNOWFLAKE_ACCOUNT}/database?warehouse=warehouse&schema=schema"
# Or with additional parameters
connection_string: "snowflake://${SNOWFLAKE_USER}:${SNOWFLAKE_PASSWORD}@account.region.cloud/database?warehouse=warehouse&schema=schema&role=role"

# Snowflake with authentication parameters
connection_string: "snowflake://${SNOWFLAKE_USER}:${SNOWFLAKE_PASSWORD}@account.snowflakecomputing.com/MYDB?warehouse=MYWH&schema=PUBLIC&role=MYROLE"

# Snowflake with additional connection parameters
connection_string: "snowflake://${SNOWFLAKE_USER}:${SNOWFLAKE_PASSWORD}@account/db?warehouse=WH&schema=SCHEMA&role=ROLE&authenticator=oauth&timeout=60"

# DB2 (requires ibm-db-sa driver)
connection_string: "ibm_db_sa://${DB2_USER}:${DB2_PASSWORD}@hostname:port/database"
# Or using db2:// prefix
connection_string: "db2://${DB2_USER}:${DB2_PASSWORD}@hostname:port/database"
# With SSL
connection_string: "ibm_db_sa://${DB2_USER}:${DB2_PASSWORD}@hostname:50000/SAMPLE?SECURITY=SSL"

# MongoDB (local)
connection_string: "mongodb://${MONGO_USER}:${MONGO_PASSWORD}@host:27017/database"
# MongoDB Atlas (cloud)
connection_string: "mongodb+srv://${MONGO_USER}:${MONGO_PASSWORD}@cluster.mongodb.net/database"
```

---

## Multi-Cloud LLM Support

All providers work out of the box with no extra installation.

| Provider | Models | Authentication |
|----------|--------|---------------|
| **OpenAI** | GPT-5.4, GPT-5.4 Mini, GPT-5.4 Nano, GPT-4o | `OPENAI_API_KEY` environment variable |
| **Azure OpenAI** | Enterprise deployments of any OpenAI model | `azure_endpoint` + `azure_deployment` + certificate auth |
| **Google Cloud Vertex AI** | Gemini 2.5 Pro, Gemini 2.5 Flash, Gemini 2.5 Flash-Lite | `project_id` + (`credentials_path` or `gcloud_cli_auth: true`) |
| **AWS Bedrock** | Claude 4.6 Sonnet and other Bedrock models | `region_name` + AWS credentials |

### Database Authentication

| Database | Required Fields |
|----------|----------------|
| `bigquery://` | `bigquery_credentials_path` OR `bigquery_gcloud_cli_auth: true` |
| `postgresql://` | Credentials via `${ENV_VAR}` in connection string |
| `sqlite://` | File path only |

### Provider Configuration Examples

```yaml
# OpenAI
llm:
  provider: "openai"
  model: "gpt-4o"
  # API key is read from OPENAI_API_KEY environment variable

# Vertex AI (gcloud CLI auth)
llm:
  provider: "vertex_ai"
  project_id: "my-gcp-project"
  gcloud_cli_auth: true

# BigQuery (gcloud CLI auth)
database:
  connection_string: "bigquery://my-project/my-dataset"
  bigquery_gcloud_cli_auth: true
```

### Configuration Templates

```bash
# Basic templates
example-configs/query-openai.yaml           # OpenAI + PostgreSQL  
example-configs/query-azure-openai.yaml     # Azure OpenAI
example-configs/query-snowflake.yaml        # Snowflake database
example-configs/query-mongodb.yaml          # MongoDB (NoSQL)

# Privacy & Security templates
example-configs/query-pii-detection.yaml    # PII detection enabled
example-configs/query-bigquery-pii.yaml     # Enterprise compliance ready

# Specialized templates
example-configs/example-zscaler-config.yaml # Corporate proxy
example-configs/data-classification-*.yaml  # Data processing
```

> See [Configuration Guide](configuration/overview.md) for the complete YAML reference.

