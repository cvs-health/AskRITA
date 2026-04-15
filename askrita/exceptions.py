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

"""Exception hierarchy for AskRITA framework."""


class AskRITAError(Exception):
    """Base exception for all AskRITA errors."""

    pass


class ConfigurationError(AskRITAError):
    """Configuration validation or loading errors."""

    pass


class DatabaseError(AskRITAError):
    """Database connection or query errors."""

    pass


class LLMError(AskRITAError):
    """LLM provider errors (API failures, invalid responses, etc.)."""

    pass


class ValidationError(AskRITAError):
    """Input validation errors (malformed questions, unsafe queries, etc.)."""

    pass


class QueryError(AskRITAError):
    """SQL query generation, validation, or execution errors."""

    pass


class TimeoutError(AskRITAError):
    """Operation timeout errors."""

    pass


class ExportError(AskRITAError):
    """Export operation errors (PPTX, PDF generation failures)."""

    pass


class ResearchError(AskRITAError):
    """Research operation errors (hypothesis testing, analysis failures, etc.)."""

    pass
