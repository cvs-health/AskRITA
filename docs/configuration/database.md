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
# Database Configuration

Configure Ask RITA to connect to PostgreSQL, MySQL, SQLite, BigQuery, Snowflake, or MongoDB.

**⚡ New in v0.2.0**: All database configurations now support intelligent schema caching with `cache_schema: true` and `schema_refresh_interval` for up to 3x faster query performance.

**🧠 New in v0.2.1**: BigQuery configurations now support hybrid schema descriptions with `schema_descriptions` for automatic metadata extraction combined with manual enhancements, dramatically improving SQL generation quality.

## PostgreSQL Configuration

**Requirements:**
- ✅ **Mandatory**: Connection string with all credentials
- ✅ **Recommended**: Use environment variables for passwords

```yaml
database:
  # Connection string with environment variables (recommended)
  connection_string: "postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:5432/${DB_NAME}"
  
  # Optional: Performance settings
  query_timeout: 30                          # Query timeout in seconds
  max_results: 1000                          # Maximum rows to return
  
  # Schema Caching (New in v0.2.0) - Improves performance by 3x
  cache_schema: true                         # Enable schema caching (default: false)
  schema_refresh_interval: 3600              # Cache expiry in seconds (1 hour recommended for production)
```

**Connection string variants:**

```bash
# Basic
postgresql://${DB_USER}:${DB_PASSWORD}@host:5432/database

# With SSL and timeout
postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:5432/db?sslmode=require&connect_timeout=10
```

**Environment Variables:**
```bash
export DB_PASSWORD="your-secure-password"
export DB_HOST="your-database-host"
export DB_USER="your-username"
export DB_NAME="your-database-name"

# Use in config:
# connection_string: "postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:5432/${DB_NAME}"
```

## MySQL Configuration

```yaml
database:
  connection_string: "mysql+pymysql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:3306/${DB_NAME}"
  
  # Optional: Performance settings
  query_timeout: 30
  max_results: 1000
  
  # Schema Caching (New in v0.2.0) - Improves performance by 3x
  cache_schema: true                         # Enable schema caching (default: false)
  schema_refresh_interval: 3600              # Cache expiry in seconds (1 hour recommended for production)
```

**Connection string variants:**

```bash
# Basic
mysql+pymysql://${DB_USER}:${DB_PASSWORD}@host:3306/database

# With SSL and charset
mysql+pymysql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:3306/db?charset=utf8mb4&ssl_disabled=false

# MariaDB (same syntax)
mysql+pymysql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:3306/database
```

## SQLite Configuration

```yaml
database:
  # File-based SQLite
  connection_string: "sqlite:///./path/to/database.db"
  
  # Absolute path
  connection_string: "sqlite:////absolute/path/to/database.db"
  
  # In-memory database (for testing)
  connection_string: "sqlite:///:memory:"
  
  # Optional: Performance settings
  query_timeout: 30                          # Less relevant for SQLite
  max_results: 1000
  
  # Schema Caching (New in v0.2.0) - Still beneficial for SQLite
  cache_schema: true                         # Enable schema caching (default: false)
  schema_refresh_interval: 1800              # 30 minutes recommended for development
```

## BigQuery Configuration

**Requirements:**
- ✅ **Mandatory**: Project and dataset in connection string
- ✅ **Choose one**: Service account credentials OR gcloud CLI auth

**Option 1: Service Account Authentication**
```yaml
database:
  connection_string: "bigquery://your-project-id/your-dataset-id"
  
  # REQUIRED: Service account credentials
  bigquery_credentials_path: "/path/to/service-account.json"
  bigquery_project_id: "your-project-id"    # Optional: Override project ID
  
  # Optional: Performance settings
  query_timeout: 60                          # BigQuery queries can be slow
  max_results: 10000                         # BigQuery can handle larger results
  
  # Schema Caching (v0.2.0) - Highly recommended for BigQuery
  cache_schema: true                         # Enable schema caching (default: false)
  schema_refresh_interval: 7200              # 2 hours recommended for enterprise data warehouses
  
  # Cross-Project Dataset Access (New in v0.2.1)
  cross_project_access:
    enabled: true                            # Enable cross-project functionality
    datasets:
      - "project-a.dataset-name"             # Primary cross-project dataset
      - "project-b.analytics"                # Additional datasets
    include_tables: []                       # Empty = include all tables
    exclude_tables: ["temp_*", "staging_*"] # Patterns to exclude
    cache_metadata: true                     # Cache cross-project metadata
    metadata_refresh_interval: 7200         # Cache expiry in seconds (2 hours)
  
  # Schema Descriptions Configuration (New in v0.2.1)
  # Hybrid system: automatic extraction + manual enhancements
  schema_descriptions:
    project_context: "Enterprise data warehouse for analytics and reporting"
    automatic_extraction:
      enabled: true                          # Extract descriptions from BigQuery INFORMATION_SCHEMA
      fallback_to_column_name: true         # Generate descriptions from column names if no metadata
      include_data_types: true              # Include data types in descriptions
      extract_comments: true                # Extract existing column/table comments
    columns:
      customer_id:
        description: "Unique customer identifier"
        mode: "supplement"                   # supplement | override | fallback | auto_only
        business_context: "Primary key for customer analytics"
    tables:
      customers:
        description: "Master customer data with demographics"
        business_purpose: "Customer segmentation and personalization"
    business_terms:
      churn: "Customer who hasn't purchased in 90+ days"
      ltv: "Customer Lifetime Value calculation"
```

**Option 2: gcloud CLI Authentication (Recommended for Development)**
```yaml
database:
  connection_string: "bigquery://your-project-id/your-dataset-id"
  
  # REQUIRED: Use gcloud CLI authentication
  bigquery_gcloud_cli_auth: true
  
  # Optional: Performance settings
  query_timeout: 60
  max_results: 10000
  
  # Schema Caching (v0.2.0) - Highly recommended for BigQuery
  cache_schema: true                         # Enable schema caching (default: false)
  schema_refresh_interval: 1800              # 30 minutes recommended for development
  
  # Cross-Project Dataset Access (New in v0.2.1)
  cross_project_access:
    enabled: false                           # Usually disabled for development
    datasets: []                             # Cross-project datasets to access
    include_tables: []                       # Table patterns to include
    exclude_tables: ["temp_*"]               # Table patterns to exclude
    cache_metadata: true                     # Cache metadata for performance
    metadata_refresh_interval: 3600         # Cache expiry: 1 hour for dev
  
  # Schema Descriptions Configuration (New in v0.2.1)
  schema_descriptions:
    project_context: "Development environment for testing and analytics"
    automatic_extraction:
      enabled: true                          # Enable automatic extraction
      fallback_to_column_name: true         # Generate from column names
      include_data_types: true              # Include data types
      extract_comments: true                # Extract existing comments
    columns:
      customer_id:
        description: "Unique customer identifier"
        mode: "supplement"
        business_context: "Primary key for analytics"
    business_terms:
      churn: "Customer attrition rate"
      retention: "Customer retention metrics"
```

**Environment Variables:**
```bash
# Option 1: Service Account
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# Option 2: gcloud CLI (run this first)
gcloud auth login
gcloud config set project your-project-id
```

## Snowflake Configuration

**Requirements:**
- ✅ **Mandatory**: Account, warehouse, schema, and role in connection string
- ✅ **Mandatory**: Username and password

```yaml
database:
  # Basic Snowflake connection
  connection_string: "snowflake://${SNOWFLAKE_USER}:${SNOWFLAKE_PASSWORD}@account/database?warehouse=warehouse&schema=schema&role=role"
  
  # With additional parameters
  connection_string: "snowflake://${SNOWFLAKE_USER}:${SNOWFLAKE_PASSWORD}@${SNOWFLAKE_ACCOUNT}/db?warehouse=WH&schema=PUBLIC&role=ROLE&authenticator=snowflake"
  
  # With environment variables
  connection_string: "snowflake://${SF_USER}:${SF_PASSWORD}@${SF_ACCOUNT}/${SF_DATABASE}?warehouse=${SF_WAREHOUSE}&schema=${SF_SCHEMA}&role=${SF_ROLE}"
  
  # Optional: Performance settings
  query_timeout: 120                         # Snowflake queries can be slow
  max_results: 10000                         # Snowflake can handle large results
  
  # Schema Caching (New in v0.2.0) - Highly recommended for Snowflake
  cache_schema: true                         # Enable schema caching (default: false)
  schema_refresh_interval: 3600              # 1 hour recommended for production data warehouses
```

**Environment Variables:**
```bash
export SF_USER="your-snowflake-username"
export SF_PASSWORD="your-snowflake-password"
export SF_ACCOUNT="your-account-identifier"
export SF_DATABASE="your-database"
export SF_WAREHOUSE="your-warehouse"
export SF_SCHEMA="your-schema"
export SF_ROLE="your-role"
```

## MongoDB Configuration (New in v0.12.0)

**Requirements:**
- ✅ **Mandatory**: Connection string with database name
- ✅ **Mandatory**: Use `NoSQLAgentWorkflow` instead of `SQLAgentWorkflow`

> **📖 Full Guide**: See [NoSQL Workflow Guide](../guides/nosql-workflow.md) for comprehensive MongoDB documentation.

```yaml
database:
  # Local MongoDB
  connection_string: "mongodb://${MONGO_USER}:${MONGO_PASSWORD}@host:27017/database"

  # MongoDB Atlas (cloud)
  connection_string: "mongodb+srv://${MONGO_USER}:${MONGO_PASSWORD}@cluster.mongodb.net/database"

  # With environment variables (recommended)
  connection_string: "mongodb://${MONGO_USER}:${MONGO_PASSWORD}@${MONGO_HOST}:27017/${MONGO_DB}"

  # Performance settings
  query_timeout: 30
  max_results: 1000

  # Schema Caching - Recommended for production
  cache_schema: true
  schema_refresh_interval: 3600              # 1 hour
```

**Environment Variables:**
```bash
export MONGO_USER="your-username"
export MONGO_PASSWORD="your-password"
export MONGO_HOST="your-host"
export MONGO_DB="your-database"
```

**Usage:**
```python
from askrita import NoSQLAgentWorkflow, ConfigManager

config = ConfigManager("example-configs/query-mongodb.yaml")
workflow = NoSQLAgentWorkflow(config)
result = workflow.query("How many orders per month?")
print(result.answer)
```

**Key Differences from SQL Workflow:**
- Uses `NoSQLAgentWorkflow` instead of `SQLAgentWorkflow`
- LLM generates MongoDB aggregation pipelines (`db.collection.aggregate([...])`) instead of SQL
- Schema is inferred from document sampling via `langchain-mongodb`
- Safety validation blocks MongoDB write operations (`$out`, `$merge`, `deleteMany`, etc.)
- Workflow step names remain the same for configuration compatibility (`generate_sql` maps to MongoDB query generation)

