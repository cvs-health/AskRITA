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
# Contributing to AskRITA

Welcome and thank you for considering contributing to AskRITA!

It takes a lot of time and effort to use software much less build upon it, so we deeply appreciate your desire to help make this project thrive.

## Table of Contents

- [Table of Contents](#table-of-contents)
- [How to Contribute](#how-to-contribute)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Enhancements](#suggesting-enhancements)
  - [Pull Requests](#pull-requests)
- [Development Setup](#development-setup)
  - [Development tasks](#development-tasks)
- [Style Guides](#style-guides)
  - [Code Style](#code-style)
- [License](#license)

## How to Contribute

### Reporting Bugs

If you find a bug, please report it by opening an issue on GitHub. Include as much detail as possible:
- Steps to reproduce the bug.
- Expected and actual behavior.
- Screenshots if applicable.
- Any other information that might help us understand the problem.

### Suggesting Enhancements

We welcome suggestions for new features or improvements. To suggest an enhancement, please open an issue on GitHub and include:
- A clear description of the suggested enhancement.
- Why you believe this enhancement would be useful.
- Any relevant examples or mockups.

### Pull Requests

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/your-feature-name`).
3. Make your changes.
4. Commit your changes (`git commit -m 'Add some feature'`).
5. Push to the branch (`git push origin feature/your-feature-name`).
6. Open a pull request.

Please ensure your pull request adheres to the following guidelines:
- Follow the project's code style.
- Include tests for any new features or bug fixes.
- Consider the security impacts of your changes.

## Development Setup

1. Clone the repository: `git clone https://github.com/cvs-health/askRITA.git`
2. Navigate to the project directory: `cd askRITA`
3. Create and activate a virtual environment (using `venv` or `conda`)
4. Install dependencies: `poetry install`
5. Install our pre-commit hooks to ensure code style compliance: `pre-commit install`
6. Run tests to ensure everything is working: `pytest tests/ -v`

You're ready to develop!

### Development tasks

| Task | Command |
|------|---------|
| Run tests with coverage | `poetry run pytest tests/ --cov=askrita --cov-report=term-missing` |
| Bandit security checks | `poetry run bandit -r askrita` |
| flake8 linting | `poetry run flake8 askrita tests` |
| Type checking | `poetry run mypy askrita` |
| Format code | `poetry run black askrita tests` |
| Sort imports | `poetry run isort askrita tests` |
| Run all checks via tox | `tox` |

**For documentation contributions**
Our documentation lives in the `docs/` directory.

Key documentation files:
* `docs/configuration.md` - Configuration reference
* `docs/nosql-workflow.md` - NoSQL workflow guide
* `example-configs/` - Example YAML configurations
* `CHANGELOG.md` - Version history

## Style Guides

### Code Style

- We use [Black](https://github.com/psf/black) for code formatting and [isort](https://pycqa.github.io/isort/) for import sorting.
- We use [flake8](https://flake8.pycqa.org/) for linting and [mypy](https://mypy-lang.org/) for type checking.
- Our pre-commit hook will run these checks when you commit.
- All functions must include type hints and docstrings.

Please ensure your code is properly formatted and linted before committing.

## License

Before contributing to this CVS Health sponsored project, you will need to sign the associated [Contributor License Agreement (CLA)](https://forms.office.com/r/zx8HY2GUDf)

---

Thanks again for using and supporting AskRITA!
