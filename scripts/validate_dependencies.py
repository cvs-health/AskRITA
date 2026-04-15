#!/usr/bin/env python3
# Copyright 2026 CVS Health and/or one of its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Dependency validation script for AskRITA.
Checks that all required dependencies are properly installed and compatible.
"""

import importlib
import subprocess
import sys
from typing import Dict, List, Tuple

_STATUS_AVAILABLE = "\u2705 Available"


def check_core_dependencies() -> List[Tuple[str, bool, str]]:
    """Check core dependencies that are always required."""
    core_deps = [
        ("langchain_core", "LangChain Core"),
        ("langchain_community", "LangChain Community"),
        ("langchain_openai", "LangChain OpenAI"),
        ("langgraph", "LangGraph"),
        ("sqlalchemy", "SQLAlchemy"),
        ("psycopg2", "PostgreSQL adapter"),
        ("pymysql", "MySQL adapter"),
        ("requests", "HTTP requests"),
        ("yaml", "YAML parser"),
    ]

    results = []
    for module, description in core_deps:
        try:
            importlib.import_module(module)
            results.append((description, True, _STATUS_AVAILABLE))
        except ImportError as e:
            results.append((description, False, f"❌ Missing: {e}"))

    return results


def check_cloud_dependencies() -> Dict[str, List[Tuple[str, bool, str]]]:
    """Check cloud provider specific dependencies."""
    cloud_deps = {
        "Azure OpenAI": [
            ("langchain_openai", "Azure OpenAI (uses same package as OpenAI)"),
        ],
        "GCP Vertex AI": [
            ("langchain_google_vertexai", "Google Vertex AI"),
        ],
        "AWS Bedrock": [
            ("langchain_aws", "AWS LangChain"),
            ("boto3", "AWS SDK"),
        ],
    }

    results = {}
    for provider, deps in cloud_deps.items():
        provider_results = []
        for module, description in deps:
            try:
                importlib.import_module(module)
                provider_results.append((description, True, _STATUS_AVAILABLE))
            except ImportError:
                provider_results.append((description, False, "❌ Not installed"))
        results[provider] = provider_results

    return results


def check_dev_dependencies() -> List[Tuple[str, bool, str]]:
    """Check development dependencies."""
    dev_deps = [
        ("pytest", "Testing framework"),
        ("black", "Code formatter"),
        ("flake8", "Code linter"),
        ("mypy", "Type checker"),
    ]

    results = []
    for module, description in dev_deps:
        try:
            importlib.import_module(module)
            results.append((description, True, _STATUS_AVAILABLE))
        except ImportError:
            results.append((description, False, "❌ Not installed (dev only)"))

    return results


def get_package_version(package_name: str) -> str:
    """Get installed package version."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", package_name],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in result.stdout.split("\n"):
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip()
    except:
        pass
    return "Unknown"


def main():
    """Main validation function."""
    print("🔍 AskRITA Dependency Validation")
    print("=" * 50)
    print()

    # Check core dependencies
    print("📦 Core Dependencies:")
    core_results = check_core_dependencies()
    all_core_ok = True

    for description, available, status in core_results:
        print(f"  {status} {description}")
        if not available:
            all_core_ok = False

    print()

    # Check cloud provider dependencies
    print("☁️  Cloud Provider Dependencies:")
    cloud_results = check_cloud_dependencies()

    for provider, provider_results in cloud_results.items():
        print(f"\n  {provider}:")
        for description, available, status in provider_results:
            print(f"    {status} {description}")

    print()

    # Check development dependencies
    print("🛠️  Development Dependencies:")
    dev_results = check_dev_dependencies()

    for description, available, status in dev_results:
        print(f"  {status} {description}")

    print()

    # Summary and recommendations
    print("📋 Summary:")
    if all_core_ok:
        print("  ✅ All core dependencies are available")
        print("  ✅ AskRITA should work with all cloud providers:")
        print("     • OpenAI, Azure OpenAI, Google Cloud Vertex AI, AWS Bedrock")
    else:
        print("  ❌ Missing core dependencies - AskRITA will not work")
        print("  💡 Run: pip install -e .")

    print()
    print("💡 Installation Command:")
    print("  pip install askrita")


if __name__ == "__main__":
    main()
