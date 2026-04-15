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
# Installation

## From PyPI

<!-- termynal -->

```
$ pip install askrita
---> 100%
Successfully installed askrita-0.13.9
```

## With Optional Dependencies

<!-- termynal -->

```
$ pip install askrita[exports]
---> 100%
Successfully installed askrita-0.13.9 python-pptx-1.0.2 reportlab-4.4.10 matplotlib-3.10.8 xlsxwriter-3.2.9
```

## From a Private Registry

If your organization hosts Ask RITA on a private package registry, use `--extra-index-url`:

```bash
pip install --extra-index-url https://${REGISTRY_USER}:${REGISTRY_TOKEN}@your-registry.example.com/simple/ askrita
```

**Persistent Configuration (for multiple projects):**
```bash
pip config set global.extra-index-url https://${REGISTRY_USER}:${REGISTRY_TOKEN}@your-registry.example.com/simple/
pip install askrita
```

**Secure Authentication Options:**
```bash
# Option 1: .netrc file (most secure for local development)
echo "machine your-registry.example.com login $REGISTRY_USER password $REGISTRY_TOKEN" > ~/.netrc
chmod 600 ~/.netrc
pip install --extra-index-url https://your-registry.example.com/simple/ askrita

# Option 2: Poetry with credential storage
poetry config repositories.private https://your-registry.example.com/simple/
poetry config http-basic.private $REGISTRY_USER $REGISTRY_TOKEN
poetry add askrita
```

**Security Best Practices for Private Registries:**

- Use API tokens instead of passwords when possible
- Store credentials in environment variables or secure credential stores
- Use `.netrc` with proper permissions (`chmod 600 ~/.netrc`)
- Enable Poetry keyring for secure credential storage
- Never commit credentials to version control

## From Source

```bash
# Direct install from Git
pip install git+https://<TOKEN>@github.com/cvs-health/askRITA.git@main

# Or install a specific tag
pip install git+https://<TOKEN>@github.com/cvs-health/askRITA.git@v0.13.13
```

## For Development

<!-- termynal -->

```
$ git clone https://github.com/cvs-health/askRITA.git
$ cd askRITA
$ pip install poetry
$ poetry install
---> 100%
Installing dependencies from lock file
Package operations: 42 installs, 0 updates, 0 removals
```

Editable install from Git:

```bash
pip install -e git+https://github.com/cvs-health/askRITA.git@main#egg=askrita
```

## Quick Start

Once installed, create a config file and run your first query:

```python
from askrita import ConfigManager, SQLAgentWorkflow

config = ConfigManager("config.yaml")
workflow = SQLAgentWorkflow(config)

result = workflow.query("Show the top 10 customers by revenue")
print(result["answer"])
```
