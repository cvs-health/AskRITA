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
#   httpx (BSD-3-Clause)
#   openai (MIT)
#   sqlglot (MIT)

"""User simulator for BIRD Mini-Interact benchmark.

Implements the 2-step BIRD-Interact user simulator protocol:
  Step 1 (Encoder/Parser):  Classify the system's clarifying question against
      labelled ambiguity points, parse SQL segments via sqlglot, and choose an
      action (labeled / unlabeled / unanswerable).
  Step 2 (Decoder/Generator):  Given the chosen action and hidden task context,
      generate a natural-language user response.

Prompt templates are adapted from the official BIRD-Interact codebase:
  https://github.com/bird-bench/BIRD-Interact/blob/main/mini_interact/
      knowledge_based/mini_interact_conv/prompts.py
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


_CLAUSE_TYPE_LABELS: Dict[str, str] = {}  # populated lazily


def _get_clause_type_labels() -> Dict[str, str]:
    """Return a mapping from sqlglot expression class name to SQL clause label."""
    if _CLAUSE_TYPE_LABELS:
        return _CLAUSE_TYPE_LABELS
    _CLAUSE_TYPE_LABELS.update(
        {
            "Select": "SELECT",
            "From": "FROM",
            "Where": "WHERE",
            "Group": "GROUP BY",
            "Order": "ORDER BY",
            "Join": "JOIN",
            "Having": "HAVING",
        }
    )
    return _CLAUSE_TYPE_LABELS


def _parse_sql_segments(sql: str) -> str:
    """Parse a SQL query into structural segments using sqlglot.

    Returns a JSON-formatted string of segment descriptions suitable
    for the user simulator prompt.  Falls back to a raw SQL dump if
    sqlglot is unavailable or parsing fails.
    """
    try:
        import sqlglot
        from sqlglot import exp

        labels = _get_clause_type_labels()
        parsed = sqlglot.parse(sql, dialect="sqlite")
        segments: List[str] = []
        for statement in parsed:
            if statement is None:
                continue
            for node in statement.walk():
                label = labels.get(type(node).__name__)
                if label == "SELECT" and isinstance(node, exp.Select):
                    cols = [col.sql(dialect="sqlite") for col in node.expressions]
                    segments.append(f"SELECT: {', '.join(cols)}")
                elif label:
                    segments.append(f"{label}: {node.sql(dialect='sqlite')}")
        if segments:
            return json.dumps(segments, indent=2)
    except Exception as exc:
        logger.debug("sqlglot parse failed, using raw SQL: %s", exc)

    return json.dumps([sql], indent=2)


# ---------------------------------------------------------------------------
# Prompt templates (adapted from official BIRD-Interact prompts.py)
# ---------------------------------------------------------------------------

_ENCODER_PROMPT = """\
You are role-playing as a human USER interacting with an AI collaborator to \
complete a Text-to-SQL task. The AI collaborator may ask one question about \
this task. Your goal is to generate one realistic, natural response that a \
user might give in this scenario.

## Input Information:
- Labeled Ambiguity Points: All labeled ambiguity points about the user's \
question for the Text-to-SQL task.
- Ground-truth SQL Segments: All ground-truth SQL segments.
- Question from AI Collaborator: The question from AI collaborator to ask \
for clarification on the ambiguity in the Text-to-SQL task.

Inputs:
<|The Start of Task Description|>
The question from AI collaborator maybe related to existing Labeled \
Ambiguity Points or related to unlabeled ambiguity or even irrelevant.

Action Choices:
1. **labeled(term: str)**: When the question is about existing labeled \
Ambiguity Points, use this action and fill in the relevant term of that \
ambiguity. Format: **labeled("Amb")**.
2. **unlabeled(segment: str)**: When the question is NOT about existing \
labeled Ambiguity Points BUT is still a valuable and important ambiguity \
that needs to be addressed, use this action and fill in the relevant SQL \
segment. Format: **unlabeled("ALTER")**.
3. **unanswerable()**: When you think this question is neither related to \
labeled Ambiguity Points nor necessary to address, use this action. \
Format: **unanswerable()**.
<|The End of Task Description|>

<|The Start of All Labeled Ambiguity Points|>
```json
{amb_json}
```
<|The End of All Labeled Ambiguity Points|>

<|The Start of Ground-truth SQL Segments|>
{sql_segments}
<|The End of Ground-truth SQL Segments|>

<|The Start of Question from AI Collaborator|>
{clarification_question}
<|The End of Question from AI Collaborator|>

## Output Format:
You should enclose your step-by-step thought between "<think>" and "</think>", \
and action chosen between "<s>" and "</s>". Format example:
```
- Thought:
<think>[Step-by-Step Thought]</think>

- Action:
<s>[Your Action]</s>
```

## Your Response:
"""

_DECODER_PROMPT = """\
You are role-playing as a human USER interacting with an AI collaborator to \
complete a Text-to-SQL task. The AI collaborator may ask one question about \
this task. Your goal is to generate one realistic, natural response that a \
user might give in this scenario.

## Input Information:
- DB Schema Information
- Labeled Ambiguity Points
- Original Text-to-SQL Question
- Ground-truth SQL and SQL Segments
- Question from AI Collaborator
- Action Used (from previous step)

Inputs:
<|The Start of DB Schema Information|>
{db_schema}
<|The End of DB Schema Information|>

<|The Start of All Labeled Ambiguity Points|>
```json
{amb_json}
```
<|The End of All Labeled Ambiguity Points|>

<|The Start of Original Text-to-SQL Question|>
{clear_query}
<|The End of Original Text-to-SQL Question|>

<|The Start of Ground-truth SQL|>
```sqlite
{gt_sql}
```
<|The End of Ground-truth SQL|>

<|The Start of Ground-truth SQL Segments|>
{sql_segments}
<|The End of Ground-truth SQL Segments|>

<|The Start of Question from AI Collaborator|>
{clarification_question}
<|The End of Question from AI Collaborator|>

<|The Start of Action Chosen|>
{action}
<|The End of Action Chosen|>

## Guidelines:
1. Generate a response to the AI Collaborator's question based on the action \
and original question above. Do NOT reveal the original clear question \
directly, but use it to inform your answer.
2. Do NOT give any ground-truth SQL segments or solution steps.
3. Do NOT ask any question. Keep the response concise.

## Output Format:
Your response must follow the format: [Your-Response]

## Your Response:
"""


@dataclass
class UserSimulatorConfig:
    """Configuration for the user simulator LLM."""

    model: str = "gpt-4o"
    provider: str = "openai"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 1024
    ca_bundle_path: Optional[str] = None


@dataclass
class UserSimulatorResponse:
    """Result of a single user simulator invocation."""

    user_message: str
    action: str
    encoder_raw: str = ""
    decoder_raw: str = ""


@dataclass
class UserSimulator:
    """BIRD-Interact user simulator using a 2-step LLM process.

    Requires ground-truth information (ambiguity points, GT SQL) to generate
    realistic user responses.  When GT is unavailable, falls back to a simple
    template response.

    Args:
        config: LLM configuration for the user simulator.
    """

    config: UserSimulatorConfig = field(default_factory=UserSimulatorConfig)
    _client: Any = field(default=None, repr=False)

    def simulate(
        self,
        clarification_question: str,
        task_context: Dict[str, Any],
    ) -> UserSimulatorResponse:
        """Generate a user response to the system's clarifying question.

        Args:
            clarification_question: The system's question to the user.
            task_context: Dict with keys:
                - amb_json: list of ambiguity point dicts
                - sol_sql: ground-truth SQL string (optional)
                - clear_query: the unambiguous version of the query (optional)
                - db_schema: schema text for the database
                - knowledge_ambiguity: list of knowledge ambiguity dicts

        Returns:
            UserSimulatorResponse with the generated user message.
        """
        sol_sql = task_context.get("sol_sql")
        if not sol_sql:
            return self._fallback_response(clarification_question)

        amb_points = task_context.get("amb_json", [])
        knowledge_amb = task_context.get("knowledge_ambiguity", [])
        all_amb = amb_points + knowledge_amb

        sql_segments = _parse_sql_segments(sol_sql)

        # Step 1: Encoder — classify the question and choose an action
        encoder_prompt = _ENCODER_PROMPT.format(
            amb_json=json.dumps(all_amb, indent=2, ensure_ascii=False),
            sql_segments=sql_segments,
            clarification_question=clarification_question,
        )
        encoder_response = self._call_llm(encoder_prompt)
        action = self._extract_action(encoder_response)

        # Step 2: Decoder — generate the user response
        clear_query = task_context.get("clear_query", "")
        db_schema = task_context.get("db_schema", "")

        decoder_prompt = _DECODER_PROMPT.format(
            db_schema=db_schema,
            amb_json=json.dumps(all_amb, indent=2, ensure_ascii=False),
            clear_query=clear_query,
            gt_sql=sol_sql,
            sql_segments=sql_segments,
            clarification_question=clarification_question,
            action=action,
        )
        decoder_response = self._call_llm(decoder_prompt)
        user_message = self._extract_response(decoder_response)

        return UserSimulatorResponse(
            user_message=user_message,
            action=action,
            encoder_raw=encoder_response,
            decoder_raw=decoder_response,
        )

    def _fallback_response(self, _question: str) -> UserSimulatorResponse:
        """Generate a generic response when GT is unavailable."""
        return UserSimulatorResponse(
            user_message=(
                "I'm not entirely sure about the specifics. "
                "Please use your best judgment based on the available data."
            ),
            action="unanswerable()",
        )

    def _call_llm(self, prompt: str) -> str:
        """Call the user simulator LLM."""
        client = self._get_client()
        try:
            response = client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("User simulator LLM call failed: %s", e)
            return ""

    def _get_client(self) -> Any:
        """Lazily initialise the OpenAI client."""
        if self._client is not None:
            return self._client

        import openai

        kwargs: Dict[str, Any] = {}
        if self.config.api_key:
            kwargs["api_key"] = self.config.api_key
        if self.config.api_base:
            kwargs["base_url"] = self.config.api_base

        if self.config.ca_bundle_path:
            import httpx

            http_client = httpx.Client(verify=self.config.ca_bundle_path)
            kwargs["http_client"] = http_client

        self._client = openai.OpenAI(**kwargs)
        return self._client

    def _extract_action(self, encoder_output: str) -> str:
        """Extract the action string from the encoder's output."""
        match = re.search(r"<s>(.*?)</s>", encoder_output, re.DOTALL)
        if match:
            return match.group(1).strip()

        for pattern in [
            r"\*\*(labeled|unlabeled|unanswerable)\(.*?\)\*\*",
            r"(?:labeled|unlabeled|unanswerable)\(.*?\)",
        ]:
            m = re.search(pattern, encoder_output, re.DOTALL)
            if m:
                return m.group(0).strip("*").strip()

        return "unanswerable()"

    def _extract_response(self, decoder_output: str) -> str:
        """Extract the user response text from the decoder's output."""
        cleaned = decoder_output.strip()
        cleaned = cleaned.strip("\"'")
        cleaned = cleaned.strip()
        if not cleaned:
            return "I'm not sure about that. Please proceed with your best judgment."
        return cleaned
