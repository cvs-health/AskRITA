#!/usr/bin/env python
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
#
# This file uses the following unmodified third-party packages,
# each retaining its original copyright and license:
#   setuptools (MIT)

"""
Minimal setup.py for CI/CD compatibility.

⚠️  IMPORTANT: This project uses Poetry for dependency management.
    This setup.py file exists ONLY for CI/CD systems that require it.

    For development and building:
    - Use Poetry: `poetry install`, `poetry build`
    - All project configuration is in pyproject.toml

    This file provides minimal metadata for legacy CI systems.
"""

from setuptools import find_packages, setup

# Read version and metadata from pyproject.toml via Poetry
setup(
    name="askrita",
    version="0.13.13",
    packages=find_packages(),
    python_requires=">=3.11,<3.15",
    install_requires=[
        # LangChain core
        "langchain-core>=1.0.0",
        "langchain-community>=0.4.1",
        "langchain-openai>=1.0.0",
        "langchain-google-vertexai>=3.0.0",
        "langchain-aws>=1.0.0",
        "langgraph>=1.0.0",
        # SQL database drivers
        "sqlalchemy>=2.0.0",
        "psycopg2-binary>=2.9.0",
        "pymysql>=1.1.0",
        "sqlalchemy-bigquery>=1.10.0",
        "snowflake-sqlalchemy>=1.7.7",
        "google-cloud-bigquery>=3.10.0",
        "snowflake-connector-python>=3.18.0",
        # NoSQL database drivers (MongoDB)
        "langchain-mongodb>=0.11.0",
        # Cloud providers
        "azure-identity>=1.15.0",
        # Data processing
        "pandas>=2.0.0",
        "db-dtypes>=1.0.0",
        "pyarrow>=21.0.0",
        # Core utilities
        "requests>=2.30.0",
        "pyyaml>=6.0.0",
        "pydantic>=2.0.0",
        "mcp>=1.0.0",
        "starlette>=0.49.1",
        # Privacy & security
        "presidio-analyzer>=2.2.360; python_version < '3.14'",
    ],
    author="AskRITA Contributors",
    description="AskRITA - Natural language query interface for SQL and NoSQL databases powered by LangChain and LLMs",
    long_description="AskRITA - AI-Powered Data Processing Framework with Natural Language Interfaces for SQL (PostgreSQL, BigQuery, Snowflake, MySQL, DB2) and NoSQL (MongoDB) databases",
    license="Apache-2.0",
    url="https://github.com/cvs-health/askRITA",
)
