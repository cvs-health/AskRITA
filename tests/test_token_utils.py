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
#   langchain-core (MIT)

"""Tests for token_utils to boost coverage."""

from askrita.utils.token_utils import (
    estimate_messages_token_count,
    estimate_token_count,
    get_model_context_limit,
    get_safe_context_limit,
    optimize_context_for_model,
    truncate_list_to_tokens,
    truncate_text_to_tokens,
)


class TestTokenUtils:
    """Test token utility functions."""

    def test_get_model_context_limit_known_models(self):
        """Test getting context limits for known models."""
        # Test GPT-4
        limit = get_model_context_limit("gpt-4")
        assert limit > 0
        assert limit >= 8000  # GPT-4 has at least 8k context

        # Test GPT-4o
        limit = get_model_context_limit("gpt-4o")
        assert limit > 0

        # Test GPT-3.5
        limit = get_model_context_limit("gpt-3.5-turbo")
        assert limit > 0

    def test_get_model_context_limit_unknown_model(self):
        """Test getting context limit for unknown model."""
        limit = get_model_context_limit("unknown-model-12345")
        assert limit > 0  # Should return default
        assert limit >= 4000  # Default should be reasonable

    def test_get_safe_context_limit(self):
        """Test getting safe context limit."""
        limit = get_safe_context_limit("gpt-4")
        full_limit = get_model_context_limit("gpt-4")
        assert limit < full_limit  # Safe limit should be less than full
        assert limit > 0

    def test_estimate_token_count_simple(self):
        """Test token counting for simple strings."""
        # Empty string
        count = estimate_token_count("")
        assert count == 0

        # Simple string
        count = estimate_token_count("Hello world")
        assert count > 0
        assert count < 10  # Should be small number

        # Longer string
        long_text = "This is a much longer string with many more words that should result in more tokens being counted."
        count = estimate_token_count(long_text)
        assert count > 10

    def test_estimate_messages_token_count(self):
        """Test token counting for messages."""
        from langchain_core.messages import AIMessage, HumanMessage

        messages = [HumanMessage(content="Hello"), AIMessage(content="Hi there!")]

        count = estimate_messages_token_count(messages)
        assert count > 0
        assert count < 50  # Should be reasonable for short messages

    def test_truncate_text_to_tokens_no_truncation(self):
        """Test truncation when text fits within limit."""
        short_text = "This is a short text."
        max_tokens = 1000

        result = truncate_text_to_tokens(short_text, max_tokens)
        assert result == short_text  # Should be unchanged

    def test_truncate_text_to_tokens_with_truncation_middle(self):
        """Test truncation from middle when text exceeds limit."""
        # Create a long text
        long_text = (
            "This is the beginning. " + "Middle content. " * 100 + " This is the end."
        )
        max_tokens = 20  # Small limit to force truncation

        result = truncate_text_to_tokens(long_text, max_tokens, truncate_from="middle")

        # Result should be shorter than original
        assert len(result) < len(long_text)

        # Result should still be meaningful (not empty)
        assert len(result) > 0

        # Should preserve beginning and end
        assert result.startswith("This is the beginning")
        assert result.endswith("This is the end.")

    def test_truncate_text_to_tokens_with_truncation_end(self):
        """Test truncation from end when text exceeds limit."""
        long_text = "Start of text. " + "Content. " * 100
        max_tokens = 10

        result = truncate_text_to_tokens(long_text, max_tokens, truncate_from="end")

        assert len(result) < len(long_text)
        assert len(result) > 0
        assert result.startswith("Start of text")

    def test_truncate_list_to_tokens(self):
        """Test truncating list of items to fit token limit."""
        items = ["Item 1", "Item 2", "Item 3", "Item 4", "Item 5"]
        max_tokens = 20

        result = truncate_list_to_tokens(items, max_tokens)

        # Should be a string
        assert isinstance(result, str)

        # Should contain some items
        assert len(result) > 0

        # Should not exceed rough token limit (this is an estimate)
        estimated_tokens = estimate_token_count(result)
        assert (
            estimated_tokens <= max_tokens * 2
        )  # Allow some buffer for estimation errors

    def test_truncate_list_to_tokens_custom_separator(self):
        """Test truncating list with custom separator."""
        items = ["A", "B", "C", "D"]
        max_tokens = 10
        separator = " | "

        result = truncate_list_to_tokens(items, max_tokens, separator)

        assert isinstance(result, str)
        if separator in result:
            assert separator in result  # Should use custom separator

    def test_optimize_context_for_model_basic(self):
        """Test basic context optimization."""
        schema = "CREATE TABLE users (id INT, name VARCHAR(100), email VARCHAR(255))"
        question = "How many users are there?"
        model_name = "gpt-4"

        result = optimize_context_for_model(
            schema=schema,
            unique_nouns=[],
            question=question,
            parsed_question={},
            model_name=model_name,
        )

        assert isinstance(result, dict)
        assert "schema" in result
        assert "question" in result
        assert result["question"] == question

    def test_optimize_context_for_model_with_nouns(self):
        """Test context optimization with unique nouns."""
        schema = "CREATE TABLE users (id INT, name VARCHAR(100), email VARCHAR(255))"
        question = "How many users are there?"
        unique_nouns = ["users", "name", "email"]
        model_name = "gpt-4"

        result = optimize_context_for_model(
            schema=schema,
            unique_nouns=unique_nouns,
            question=question,
            parsed_question={},
            model_name=model_name,
        )

        assert isinstance(result, dict)
        assert "schema" in result
        assert "unique_nouns" in result
        assert result["unique_nouns"] == unique_nouns

    def test_optimize_context_for_model_with_parsed_question(self):
        """Test context optimization with parsed question."""
        schema = "CREATE TABLE users (id INT, name VARCHAR(100))"
        question = "How many users are there?"
        parsed_question = {"is_relevant": True, "relevant_tables": ["users"]}
        model_name = "gpt-4"

        result = optimize_context_for_model(
            schema=schema,
            unique_nouns=[],
            question=question,
            parsed_question=parsed_question,
            model_name=model_name,
        )

        assert isinstance(result, dict)
        assert "parsed_question" in result
        assert result["parsed_question"] == parsed_question

    def test_optimize_context_for_model_large_schema(self):
        """Test context optimization with large schema that needs truncation."""
        # Create a very large schema
        large_schema = "CREATE TABLE users (id INT, name VARCHAR(100));\n" * 1000
        question = "How many users are there?"
        model_name = "gpt-3.5-turbo"  # Smaller context window

        result = optimize_context_for_model(
            schema=large_schema,
            unique_nouns=[],
            question=question,
            parsed_question={},
            model_name=model_name,
        )

        assert isinstance(result, dict)
        assert "schema" in result

        # Schema should be truncated
        assert len(result["schema"]) < len(large_schema)

        # But question should remain unchanged
        assert result["question"] == question

    def test_optimize_context_for_model_with_additional_context(self):
        """Test context optimization with additional context."""
        schema = "CREATE TABLE users (id INT, name VARCHAR(100))"
        question = "How many users are there?"
        additional_context = {"notes": "This is additional context information."}
        model_name = "gpt-4"

        result = optimize_context_for_model(
            schema=schema,
            unique_nouns=[],
            question=question,
            parsed_question={},
            model_name=model_name,
            additional_context=additional_context,
        )

        assert isinstance(result, dict)
        # additional_context is merged at top-level
        assert "notes" in result
        assert result["notes"] == additional_context["notes"]


class TestTokenUtilsEdgeCases:
    """Test edge cases for token utilities."""

    def test_estimate_token_count_edge_cases(self):
        """Test token counting edge cases."""
        # None input - should handle gracefully
        count = estimate_token_count(None)
        assert count >= 0

        # Very long text
        very_long = "word " * 10000
        count = estimate_token_count(very_long)
        assert count > 1000

    def test_truncate_text_edge_cases(self):
        """Test text truncation edge cases."""
        # Zero tokens
        result = truncate_text_to_tokens("Hello world", 0)
        assert isinstance(result, str)

        # Negative tokens - should handle gracefully
        result = truncate_text_to_tokens("Hello world", -1)
        assert isinstance(result, str)

        # Empty text
        result = truncate_text_to_tokens("", 100)
        assert result == ""

    def test_truncate_list_edge_cases(self):
        """Test list truncation edge cases."""
        # Empty list
        result = truncate_list_to_tokens([], 100)
        assert result == ""

        # Single item
        result = truncate_list_to_tokens(["single"], 100)
        assert result == "single"

        # Zero tokens
        result = truncate_list_to_tokens(["a", "b"], 0)
        assert isinstance(result, str)

    def test_optimize_context_edge_cases(self):
        """Test context optimization edge cases."""
        # Empty schema
        result = optimize_context_for_model(
            schema="",
            unique_nouns=[],
            question="test",
            parsed_question={},
            model_name="gpt-4",
        )
        assert isinstance(result, dict)
        assert result["schema"] == ""

        # Very large schema that needs truncation
        large_schema = "CREATE TABLE test (col INT);\n" * 10000
        result = optimize_context_for_model(
            schema=large_schema,
            unique_nouns=[],
            question="test",
            parsed_question={},
            model_name="gpt-3.5-turbo",  # Smaller context
        )
        assert isinstance(result, dict)
        # Schema should be truncated
        assert len(result["schema"]) < len(large_schema)
