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
# Custom CA Bundle Setup for Ask RITA

Setup guide for corporate networks with custom certificate authorities (like Zscaler) that intercept TLS traffic.

## Quick Start

```bash
# 1. Copy working configuration
cp example-configs/example-zscaler-config.yaml your-config.yaml

# 2. Edit your-config.yaml with your credentials and set ca_bundle_path

# 3. Test setup
python3 -m askrita.cli test --config your-config.yaml
```

## Configuration

Set `ca_bundle_path` in your YAML config to point to your custom CA bundle:

```yaml
llm:
  provider: "openai"
  model: "gpt-4o"
  ca_bundle_path: "credentials/your-ca-bundle.pem"
```

## Usage

```python
from askrita import SQLAgentWorkflow, ConfigManager

config = ConfigManager("your-config.yaml")
workflow = SQLAgentWorkflow(config)

result = workflow.query("What are the top customer issues?")
print(result.answer)
```

## Creating a CA Bundle

### Automatic (macOS with Zscaler)

```bash
# Extract Zscaler root certificate from system keychain
security find-certificate -a -c "Zscaler" -p /Library/Keychains/System.keychain > zscaler-root.pem

# Combine with server certificates
openssl s_client -connect api.openai.com:443 -showcerts 2>/dev/null \
  | sed -n '/BEGIN CERTIFICATE/,/END CERTIFICATE/p' > server-certs.pem

cat server-certs.pem zscaler-root.pem > credentials/ca-bundle.pem
```

### Manual

```bash
# Extract certificates from TLS connection
openssl s_client -connect api.openai.com:443 -showcerts > server-certs.txt

# Extract corporate root CA from system keychain (macOS)
security find-certificate -a -c "Zscaler" -p /Library/Keychains/System.keychain > zscaler-root.pem

# Combine into a single bundle
cat server-certs.txt zscaler-root.pem > credentials/manual-ca-bundle.pem
```

## Troubleshooting

**SSL Certificate Error?**

- Verify your CA bundle file exists at the configured path
- Ensure it contains both the corporate root CA and server certificates
- Try regenerating the bundle using the steps above

**Configuration Error?**

```bash
# Start from the working example
cp example-configs/example-zscaler-config.yaml your-config.yaml
```