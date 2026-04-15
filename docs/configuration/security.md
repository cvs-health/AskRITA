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
# Security Best Practices

Environment variables, read-only database accounts, connection string security, certificate management, and query safety tiers.

!!! danger "Read-Only Database Access Required"

    Ask RITA generates and executes SQL/NoSQL queries against your database. **LLM-generated queries are inherently unpredictable.** To prevent inadvertent writes, deletes, or schema changes:

    1. **Always connect with a read-only database user.** Grant only `SELECT` (SQL) or `find`/`aggregate` (MongoDB) permissions. Never use credentials with `INSERT`, `UPDATE`, `DELETE`, `DROP`, or DDL privileges.
    2. **Do not rely on application-level safeguards alone.** Ask RITA includes prompt-injection detection and blocks known destructive patterns, but these are defence-in-depth measures — not substitutes for proper database permissions.
    3. **Store credentials in environment variables** (`${DB_USER}`, `${DB_PASSWORD}`), never in config files. See [Configuration Overview](overview.md).

    **The database user's granted permissions are the only reliable boundary between Ask RITA and your data.**

```mermaid
flowchart TD
    A[Generated SQL Query] --> B[Tier 1: Database Access Control]
    B -->|read-only user| C[Tier 2: Static Query Analysis]
    C -->|sql_safety rules| D{safe?}
    D -->|blocked pattern| E[Query Rejected]
    D -->|pass| F[Tier 3: LLM Prompt Instructions]
    F --> G[Execute Query]

    style B fill:#4CAF50,color:#fff
    style C fill:#FF9800,color:#fff
    style F fill:#2196F3,color:#fff
    style E fill:#E53935,color:#fff
```

## 1. Environment Variables (Recommended)

```bash
# Create .env file for local development
cat > .env << EOF
OPENAI_API_KEY=sk-your-key-here
DB_PASSWORD=your-secure-password
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
EOF

# Load environment variables
source .env

# Or use direnv for automatic loading
echo "source .env" > .envrc
direnv allow
```

## 2. Read-Only Database Accounts (Recommended)

Use a database account with **read-only privileges** when connecting Ask RITA to any database. This is the strongest safeguard against accidental or malicious write operations because enforcement happens at the database layer, outside of application control.

```sql
-- PostgreSQL: create a read-only role
CREATE ROLE askrita_reader WITH LOGIN PASSWORD 'secure-password';
GRANT CONNECT ON DATABASE analytics TO askrita_reader;
GRANT USAGE ON SCHEMA public TO askrita_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO askrita_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO askrita_reader;

-- MySQL: create a read-only user
CREATE USER 'askrita_reader'@'%' IDENTIFIED BY 'secure-password';
GRANT SELECT ON analytics.* TO 'askrita_reader'@'%';

-- BigQuery: assign the BigQuery Data Viewer role
-- (roles/bigquery.dataViewer grants read-only table access)

-- Snowflake: grant read-only warehouse and database access
CREATE ROLE askrita_reader;
GRANT USAGE ON WAREHOUSE analytics_wh TO ROLE askrita_reader;
GRANT USAGE ON DATABASE analytics TO ROLE askrita_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics.public TO ROLE askrita_reader;

-- MongoDB: create a read-only user
db.createUser({
  user: "askrita_reader",
  pwd: "secure-password",
  roles: [{ role: "read", db: "analytics" }]
});
```

Then reference the read-only account in your config:

```yaml
database:
  connection_string: "postgresql://askrita_reader:${DB_PASSWORD}@host:5432/analytics"
```

> **Note**: Ask RITA does not enforce read-only connections at the application level. Database-level read-only accounts are the recommended first line of defense.

## 3. Connection String Security

```yaml
# BAD: Hardcoded credentials
database:
  connection_string: "postgresql://user:plaintext_password@host:5432/db"

# GOOD: Environment variables
database:
  connection_string: "postgresql://askrita_reader:${DB_PASSWORD}@host:5432/db"
```

## 4. Certificate Management

```bash
# Store certificates securely
chmod 600 /path/to/certificate.pem
chown $USER:$USER /path/to/certificate.pem

# Use environment variables for paths
export AZURE_CERT_PATH="/secure/path/to/certificate.pem"
```

## 5. Query Security (Three-Tier Safeguards)

Ask RITA uses a layered approach to prevent write operations:

**Tier 1 -- Database-level access control** (see section 2 above)
Use read-only database accounts so that even if a write query reaches the database, it is rejected.

**Tier 2 -- Static query analysis**
Ask RITA performs static analysis on every generated query before execution. This is configured via `workflow.sql_safety`:

```yaml
workflow:
  sql_safety:
    enabled: true
    allowed_query_types: ["SELECT", "WITH"]
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
      - "MERGE"
    suspicious_functions:
      - "OPENROWSET"
      - "XP_"
      - "DBMS_"
      - "UTL_FILE"
    max_sql_length: 50000
```

For MongoDB, the NoSQL workflow blocks write operations (`$out`, `$merge`, `deleteMany`, `insertOne`, `updateOne`, `drop`, etc.) using the same static analysis approach.

**Tier 3 -- LLM prompt instructions**
Configure your `generate_sql` prompt to explicitly instruct the LLM to produce only read queries:

```yaml
prompts:
  generate_sql:
    system: |
      You are a read-only SQL analyst. Generate ONLY SELECT statements.
      NEVER generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, or any
      other data-modifying statements. If the user asks for a write
      operation, respond with NOT_ENOUGH_INFO.
```

For MongoDB, the default prompt includes: "NEVER use write operations ($out, $merge, deleteMany, insertOne, etc.)"

```yaml
business_rules:
  # Limit resource usage
  result_limits:
    max_rows: 1000
    max_query_time: 30
  
  # Restrict table access
  allowed_tables:
    - "customers"
    - "orders"
    - "products"
    - "analytics_*"  # Pattern matching
```

