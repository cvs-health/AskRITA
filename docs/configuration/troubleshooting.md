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
# Troubleshooting & Migration

Common configuration issues, fixes, and migration guides between versions.

## Issue 1: "Configuration validation failed"

```bash
# Check for missing required sections
askrita test --config my-config.yaml

# Common causes:
# - Missing prompts section
# - Missing database or llm section
# - Environment variables not set
```

## Issue 2: "OpenAI API key not found"

```bash
# Set environment variable
export OPENAI_API_KEY="your-key-here"

# Verify it's set
echo $OPENAI_API_KEY

# Add to shell profile for persistence (use ~/.zshrc on macOS)
echo 'export OPENAI_API_KEY="your-key-here"' >> ~/.zshrc
```

## Issue 3: "Database connection failed"

```bash
# Test connection string manually
psql "postgresql://$DB_USER:$DB_PASSWORD@host:5432/db"

# Check environment variables
echo $DB_PASSWORD

# Test configuration (validates both database and LLM connectivity)
askrita test --config my-config.yaml
```

## Issue 4: "LLM authentication failed"

```bash
# Check provider-specific requirements
# OpenAI: OPENAI_API_KEY environment variable
# Azure: Certificate files and tenant/client IDs
# Vertex AI: gcloud auth login or service account
# Bedrock: aws configure or IAM roles

# Test configuration (validates LLM connectivity along with database)
askrita test --config my-config.yaml --verbose
```

## 📚 Example Configuration Files

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

## Migration Guide

### From v0.10.0 to v0.10.1

**New Features (Optional - Zero Breaking Changes):**
1. **PII/PHI Detection**: Add comprehensive privacy protection for sensitive data
2. **Regulatory Compliance**: Configure for HIPAA, GDPR, and SOX compliance requirements
3. **Audit Logging**: Enable complete audit trails for enterprise governance
4. **Sample Data Validation**: Proactive scanning of existing database content

```yaml
# Add to existing configuration (all optional)
workflow:
  steps:
    pii_detection: true  # Add as first step (default: false)

# Add new section for privacy protection
pii_detection:
  enabled: true
  block_on_detection: true
  entities: ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "US_SSN"]
  confidence_threshold: 0.5
  validate_sample_data: true
  audit_log_path: "/var/log/askrita/pii_audit.log"
```

## From v0.2.0 to v0.2.1

**New Features (Optional):**
1. **Hybrid Schema Descriptions**: Add automatic metadata extraction and manual enhancements for better SQL generation
2. **Cross-Project Access**: Add BigQuery cross-project configuration if needed
3. **Enhanced Security**: Consider adding new workflow security settings
4. **Extended Validation**: Configure input validation and SQL safety rules
5. **Parse Overrides**: Add shortcuts for common query patterns

```yaml
# Add to your existing configuration
database:
  # ... existing settings ...
  schema_descriptions:          # New in v0.2.1 - Hybrid schema descriptions
    project_context: "Your data domain description"
    automatic_extraction:
      enabled: true             # Enable automatic metadata extraction
      fallback_to_column_name: true
      include_data_types: true
      extract_comments: true
    columns:
      customer_id:
        description: "Unique customer identifier"
        mode: "supplement"
        business_context: "Primary key for analytics"
    business_terms:
      churn: "Customer attrition definition"
  cross_project_access:         # New in v0.2.1
    enabled: false              # Enable if you need cross-project access
    datasets: []
    exclude_tables: ["temp_*"]

workflow:
  # ... existing settings ...
  input_validation:             # New in v0.2.1
    max_question_length: 10000
    blocked_substrings: ["<script", "javascript:"]
  sql_safety:                   # New in v0.2.1
    allowed_query_types: ["SELECT", "WITH"]
    forbidden_patterns: ["DROP", "DELETE", "TRUNCATE"]
  conversation_context:         # New in v0.2.1
    max_history_messages: 6
```

## From Previous Versions

1. **API Keys**: Move from config files to environment variables
2. **Azure Authentication**: Switch from API keys to certificate-based auth
3. **Database Credentials**: Use environment variables for passwords
4. **Prompts**: Ensure all required prompts are present in config
5. **Schema Caching**: Enable for better performance (added in v0.2.0)

## Configuration Upgrade Checklist

**For all versions:**
- [ ] Set `OPENAI_API_KEY` environment variable
- [ ] Remove `api_key` from YAML files
- [ ] Update Azure OpenAI to use certificates
- [ ] Move database passwords to environment variables
- [ ] Test configuration with `askrita test`
- [ ] Update CI/CD pipelines with new environment variables

**For v0.2.1 (Optional enhancements):**
- [ ] Enable schema caching if not already done (`cache_schema: true`)
- [ ] Configure hybrid schema descriptions for better SQL generation
- [ ] Configure cross-project access for BigQuery if needed
- [ ] Add input validation rules for enhanced security
- [ ] Configure SQL safety settings for production environments
- [ ] Set up parse overrides for common query patterns
- [ ] Configure conversation context settings for chat workflows

