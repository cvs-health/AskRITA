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
# LLM Provider Configuration

Configure Ask RITA to use OpenAI, Azure OpenAI, Google Vertex AI, or AWS Bedrock as your LLM provider.

## OpenAI Configuration

**Requirements:**
- ✅ **Mandatory**: `OPENAI_API_KEY` environment variable
- ✅ **Mandatory**: `provider: "openai"`
- ✅ **Mandatory**: `model` specification
- ❌ **Not supported**: API key in config file (security enhancement)

```yaml
llm:
  provider: "openai"
  model: "gpt-4o"                    # REQUIRED: gpt-4o, gpt-4o-mini, gpt-4.1
  temperature: 0.1                   # Optional: 0.0-2.0 (default: 0.1)
  max_tokens: 4000                   # Optional: Max response tokens (default: 4000)
  top_p: 1.0                         # Optional: Nucleus sampling (default: 1.0)
  frequency_penalty: 0.0             # Optional: -2.0 to 2.0 (default: 0.0)
  presence_penalty: 0.0              # Optional: -2.0 to 2.0 (default: 0.0)
  timeout: 60                        # Optional: Request timeout in seconds (default: 60)
  
  # Optional: Custom CA bundle for corporate environments (e.g., Zscaler)
  ca_bundle_path: "/path/to/custom-ca-bundle.pem"
  
  # Optional: Custom base URL (for OpenAI-compatible APIs)
  base_url: "https://api.openai.com/v1"
  
  # Optional: Organization ID (for OpenAI organization accounts)
  organization: "org-your-organization-id"
```

**Environment Variables:**
```bash
# REQUIRED
export OPENAI_API_KEY="sk-your-actual-api-key-here"

# Optional (for corporate environments)
export HTTPS_PROXY="http://proxy.company.com:8080"
export HTTP_PROXY="http://proxy.company.com:8080"
```

## Azure OpenAI Configuration

**Requirements:**
- ✅ **Mandatory**: Certificate-based authentication (all 3 fields required)
- ✅ **Mandatory**: `azure_endpoint` and `azure_deployment`
- ❌ **Not supported**: API key authentication (removed for security)

```yaml
llm:
  provider: "azure_openai"
  model: "gpt-4o"                              # REQUIRED: Model name (deployment-specific)
  
  # REQUIRED: Azure OpenAI endpoint and deployment
  azure_endpoint: "https://your-resource.openai.azure.com/"
  azure_deployment: "your-deployment-name"    # Your model deployment name
  api_version: "2025-04-01-preview"           # Optional: API version (default: latest)
  
  # REQUIRED: Certificate-based authentication (all three required)
  azure_tenant_id: "your-tenant-id"
  azure_client_id: "your-client-id"
  azure_certificate_path: "/path/to/certificate.pem"
  
  # Optional: Certificate password (if certificate is encrypted)
  azure_certificate_password: "cert-password"
  
  # Optional: Model parameters
  temperature: 0.1                             # Optional: 0.0-2.0 (default: 0.1)
  max_tokens: 4000                             # Optional: Max response tokens
  timeout: 60                                  # Optional: Request timeout in seconds
```

**Certificate Setup:**
```bash
# Create Azure service principal with certificate
az ad sp create-for-rbac --name "askrita-sp" --cert @/path/to/certificate.pem

# Grant necessary permissions
az role assignment create --assignee <client-id> --role "Cognitive Services User" --scope /subscriptions/<subscription-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>
```

## Google Vertex AI Configuration

**Requirements:**
- ✅ **Mandatory**: `project_id`
- ✅ **Choose one**: Service account credentials OR gcloud CLI auth
- ✅ **Mandatory**: `location` (GCP region)

**Option 1: Service Account Authentication**
```yaml
llm:
  provider: "vertex_ai"
  model: "gemini-1.5-pro"                    # REQUIRED: gemini-1.5-pro, gemini-pro, etc.
  project_id: "your-gcp-project-id"         # REQUIRED: GCP project ID
  location: "us-central1"                    # REQUIRED: GCP region
  
  # REQUIRED: Service account credentials
  credentials_path: "/path/to/service-account.json"
  
  # Optional: Model parameters
  temperature: 0.1                           # Optional: 0.0-1.0 (default: 0.1)
  max_tokens: 4000                           # Optional: Max response tokens
  top_p: 1.0                                 # Optional: Nucleus sampling
  timeout: 60                                # Optional: Request timeout in seconds
```

**Option 2: gcloud CLI Authentication (Recommended for Development)**
```yaml
llm:
  provider: "vertex_ai"
  model: "gemini-1.5-pro"                    # REQUIRED: Model name
  project_id: "your-gcp-project-id"         # REQUIRED: GCP project ID
  location: "us-central1"                    # REQUIRED: GCP region
  
  # REQUIRED: Use gcloud CLI authentication
  gcloud_cli_auth: true
  
  # Optional: Model parameters
  temperature: 0.1
  max_tokens: 4000
```

**Environment Variables:**
```bash
# Option 1: Service Account
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# Option 2: gcloud CLI (run this first)
gcloud auth login
gcloud config set project your-gcp-project-id
```

## AWS Bedrock Configuration

**Requirements:**
- ✅ **Mandatory**: `region_name`
- ✅ **Mandatory**: AWS credentials (IAM roles, environment variables, or AWS CLI)
- ✅ **Mandatory**: Model access enabled in AWS Bedrock console

```yaml
llm:
  provider: "bedrock"
  model: "anthropic.claude-4-6-sonnet-20250514-v1:0"  # REQUIRED: Full Bedrock model ID
  region_name: "us-east-1"                   # REQUIRED: AWS region
  
  # Optional: Model parameters
  temperature: 0.1                           # Optional: 0.0-1.0 (default: 0.1)
  max_tokens: 4000                           # Optional: Max response tokens
  top_p: 1.0                                 # Optional: Nucleus sampling
  timeout: 60                                # Optional: Request timeout in seconds
```

**Supported Models:**
```yaml
# Claude 4.6 Sonnet (Recommended)
model: "anthropic.claude-4-6-sonnet-20250514-v1:0"

# Claude 4.6 Haiku (Cost-effective)
model: "anthropic.claude-4-6-haiku-20250514-v1:0"

# Amazon Titan
model: "amazon.titan-text-express-v1"

# Meta Llama
model: "meta.llama3-70b-instruct-v1:0"
```

**Environment Variables:**
```bash
# Option 1: Environment variables
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"

# Option 2: AWS CLI (run this first)
aws configure

# Option 3: IAM roles (for EC2/ECS/Lambda)
# No environment variables needed - uses instance/container role
```

