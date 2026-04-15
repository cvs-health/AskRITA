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
# Versioning & Releases

How AskRITA versions are managed, where version numbers live, and how to cut a release.

## Semantic Versioning

AskRITA follows [Semantic Versioning 2.0.0](https://semver.org/):

```
MAJOR.MINOR.PATCH   (e.g. 0.13.7)
```

| Increment | When | Example |
|-----------|------|---------|
| **Patch** | Bug fixes, docs, dependency updates (backwards-compatible) | `0.13.7 → 0.13.8` |
| **Minor** | New features, config options, new DB/LLM support (backwards-compatible) | `0.13.7 → 0.14.0` |
| **Major** | Breaking API changes, removed features, config format changes | `0.13.7 → 1.0.0` |

## Where the Version Lives

The version string **must** stay in sync across three files:

| File | Line | Format |
|------|------|--------|
| `pyproject.toml` | `version = "X.Y.Z"` | Poetry source of truth |
| `setup.py` | `version="X.Y.Z"` | CI/CD compatibility shim |
| `askrita/__init__.py` | `__version__ = "X.Y.Z"` | Runtime `askrita.__version__` |

The version management script (`scripts/manage_version.py`) updates all three automatically.

## Bumping the Version

### Quick Commands (Poetry scripts)

```bash
# Show current version
poetry run version-show

# Bump patch  (0.13.7 → 0.13.8)
poetry run version-bump patch

# Bump minor  (0.13.7 → 0.14.0)
poetry run version-bump minor

# Bump major  (0.13.7 → 1.0.0)
poetry run version-bump major

# Set an exact version
poetry run version-bump set 1.0.0
```

### Using the Script Directly

```bash
python scripts/manage_version.py show
python scripts/manage_version.py patch
python scripts/manage_version.py minor
python scripts/manage_version.py major
python scripts/manage_version.py set 2.0.0
```

### Using bump2version (Alternative)

[bump2version](https://github.com/c4urself/bump2version/) is configured via `.bumpversion.cfg` and automatically creates a git commit and tag:

```bash
poetry run version-bump patch --tool bump2version
```

`.bumpversion.cfg` defines which files are updated and the commit/tag format:

```ini
[bumpversion]
current_version = 0.13.7
commit = True
tag = True
tag_name = v{new_version}
message = Bump version: {current_version} → {new_version}
```

!!! note
    `bump2version` commits and tags automatically. The default Poetry flow does not — you commit manually (see release checklist below).

## Release Checklist

After bumping the version:

### 1. Update Documentation

- [ ] **`CHANGELOG.md`** — Move items from `[Unreleased]` to a new `[X.Y.Z] - YYYY-MM-DD` section
- [ ] **`README.md`** — Update the "What's New" section if it's a minor/major release
- [ ] **`docs/`** — Update any guides affected by the changes

### 2. Run Quality Checks

```bash
# Full test suite
poetry run pytest tests/ -v

# Coverage (must stay above 80%)
poetry run pytest tests/ --cov=askrita --cov-fail-under=80

# Formatting and lint
poetry run black --check askrita/ tests/
poetry run isort --check-only askrita/ tests/
poetry run flake8 askrita/ tests/

# Secret scanning
gitleaks detect --source . --config .gitleaks.toml -v
```

### 3. Commit and Tag

```bash
git add .
git commit -m "Release vX.Y.Z: brief description"
git tag -a vX.Y.Z -m "Release version X.Y.Z"
```

### 4. Push

```bash
git push origin main
git push origin vX.Y.Z
```

### 5. Build and Publish

```bash
poetry build --clean
# poetry publish  # when PyPI publishing is configured
```

## Verifying Version Consistency

To confirm all files agree on the current version:

```bash
poetry run version-show
grep 'version' pyproject.toml | head -1
grep '__version__' askrita/__init__.py
grep 'version=' setup.py
```

All four should report the same value.
