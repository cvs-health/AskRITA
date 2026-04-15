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
# Workflow Configuration

Step control, security settings, follow-up question generation, and performance optimizations.

```mermaid
flowchart LR
    A[Question] --> B[PII Detection]
    B --> C[Parse Question]
    C --> D[Get Unique Nouns]
    D --> E[Generate SQL]
    E --> F[Validate & Fix SQL]
    F --> G[Execute SQL]
    G --> H[Format Results]
    H --> I[Choose & Format Viz]
    I --> J[Follow-up Questions]
    J --> K[Response]
    style A fill:#2F5496,color:#fff
    style B fill:#4CAF50,color:#fff
    style C fill:#0288D1,color:#fff
    style D fill:#4CAF50,color:#fff
    style E fill:#0288D1,color:#fff
    style F fill:#0288D1,color:#fff
    style G fill:#4CAF50,color:#fff
    style H fill:#0288D1,color:#fff
    style I fill:#0288D1,color:#fff
    style J fill:#0288D1,color:#fff
    style K fill:#7B1FA2,color:#fff
```

Each step above can be individually enabled or disabled via the `steps` configuration:

```yaml
workflow:
  # Basic workflow settings
  max_retries: 3                            # SQL error retry attempts
  timeout_per_step: 120                     # Timeout per workflow step (seconds)
  output_format: "json"                     # Output format preference
  include_metadata: true                    # Include metadata in responses
  include_query_info: true                  # Include query information
  
  # Step control
  steps:
    parse_question: true
    get_unique_nouns: true
    generate_sql: true
    validate_and_fix_sql: true
    execute_sql: true
    format_results: true
    choose_visualization: true
    format_data_for_visualization: true
    generate_followup_questions: true     # Generate contextual follow-up questions
  
  # Input Validation (New in v0.2.1)
  input_validation:
    max_question_length: 10000              # Maximum question length
    blocked_substrings:                     # Block potentially harmful content
      - "<script"
      - "javascript:"
      - "data:"
      - "vbscript:"
      - "@@"
  
  # Parse Overrides (New in v0.2.1)
  parse_overrides:                          # Short-circuit parsing for special cases
    - enabled: true
      match_any_keywords:                   # Keywords to match
        - "survey"
        - "specific_dataset"
      parsed_response:                      # Pre-defined response
        is_relevant: true
        relevant_tables:
          - table_name: "project.dataset.table"
            relevance_reason: "Explicitly mentioned table"
            noun_columns: ["id", "name"]
            numeric_columns: ["count"]
        question_type: "analysis"
        analysis_type: "data_exploration"
  
  # SQL Safety (New in v0.2.1)
  sql_safety:
    allowed_query_types: ["SELECT", "WITH"] # Only allow safe query types
    forbidden_patterns:                     # Block dangerous SQL patterns
      - "DROP"
      - "DELETE"
      - "TRUNCATE"
      - "ALTER"
      - "CREATE"
      - "INSERT"
      - "UPDATE"
      - "GRANT"
      - "REVOKE"
      - "EXEC"
      - "EXECUTE"
    suspicious_functions:                   # Block suspicious SQL functions
      - "OPENROWSET"
      - "OPENDATASOURCE"
      - "XP_"
      - "SP_"
      - "DBMS_"
      - "UTL_FILE"
      - "UTL_HTTP"
      - "BULK"
      - "OUTFILE"
      - "DUMPFILE"
    max_sql_length: 50000                   # Maximum SQL query length
  
  # Conversation Context (New in v0.2.1)
  conversation_context:
    max_history_messages: 6                 # Maximum messages to keep in context
```

## Enhanced Security Features

**Input Validation:**
- Protects against injection attacks and malformed input
- Configurable content filtering and length limits
- Customizable blocked substring patterns

**SQL Safety:**
- Multi-layer SQL injection protection
- Configurable allowed query types and forbidden patterns
- Detection of suspicious functions and operations
- Query length limits to prevent resource exhaustion

**Parse Overrides:**
- Bypass standard parsing for specific use cases
- Pre-defined responses for known keywords or patterns
- Improved performance for common queries

**Conversation Context:**
- Intelligent conversation history management
- Configurable context window size
- Optimized for token efficiency in LLM prompts

## Follow-up Question Generation

The follow-up question generation feature provides AI-powered contextual questions to help users explore their data more deeply after receiving initial query results.

## Key Benefits

- **🧠 Contextual Intelligence**: Generates questions based on actual query results and context
- **🔄 Exploration Guidance**: Suggests natural next steps for data exploration  
- **⚡ Smart Fallbacks**: Uses rule-based generation when LLM is unavailable
- **🎯 Selective Generation**: Only generates meaningful questions, returns empty list when appropriate

## Configuration

```yaml
workflow:
  steps:
    generate_followup_questions: true         # Enable follow-up question generation
    
prompts:
  generate_followup_questions:
    system: |
      You are an AI assistant that generates relevant follow-up questions based on a user's database query and results.
      Your goal is to suggest 2-3 questions that would provide additional insights, help users explore the data further,
      or uncover related information they might find valuable.
      
      Guidelines:
      - Generate 2-3 concise, specific questions
      - Focus on actionable insights and deeper analysis
      - Consider drill-down opportunities (time periods, categories, segments)
      - Suggest comparative analysis when appropriate
      - Avoid generic questions - be specific to the data and context
      - Return questions as a simple numbered list
      
      Example good follow-up questions:
      - "What are the month-over-month trends for these top categories?"
      - "How do these numbers compare to the same period last year?"
      - "Which specific subcategories drive the highest volume in Customer Service?"
      
    human: |
      Original question: {question}
      Answer provided: {answer}
      SQL query executed: {sql_query}
      Data summary: {results_summary}
      Context: {context_info}
      Number of result rows: {row_count}
      
      Based on this information, generate 2-3 relevant follow-up questions that would provide additional insights:
```

## How It Works

1. **Execution Sequence**: Runs after `format_results` to ensure it has access to the formatted answer
2. **Context Analysis**: Analyzes the original question, generated answer, SQL query, and result data
3. **Intelligent Generation**: 
   - **Primary**: Uses LLM with contextual prompts for high-quality questions
   - **Fallback**: Uses rule-based logic when LLM is unavailable
   - **Smart Skip**: Returns empty list when no meaningful questions can be generated

## Rule-Based Fallback Logic

When LLM is unavailable, the system uses intelligent rule-based generation:

- **GROUP BY + COUNT queries**: Suggests trend analysis and comparative questions
- **Category-based queries**: Suggests subcategory drill-downs and effectiveness comparisons  
- **Date-based queries**: Suggests seasonal patterns and time-period comparisons
- **Aggregation queries**: Suggests distribution analysis and factor exploration

## Best Practices

**Prompt Configuration:**
```yaml
# Focus on specific, actionable questions
prompts:
  generate_followup_questions:
    system: |
      Generate specific, actionable follow-up questions.
      Avoid generic questions like "What else would you like to know?"
      Focus on business insights and deeper analysis opportunities.
```

**Integration with Chat Workflows:**
- Follow-up questions consider conversation history for chat mode
- Questions adapt based on whether it's a standalone query or part of ongoing conversation
- Conversation context helps avoid repetitive suggestions


## Performance Optimizations

### Combined Visualization Step (New in v0.6.2)

Ask RITA offers an optimized workflow step that combines visualization choice and data formatting, **saving ~250-400ms latency and ~14% cost per query**.

### How It Works

Instead of using two separate LLM calls:
1. `choose_visualization` - Choose the visualization type
2. `format_data_for_visualization` - Format the data

You can use a single optimized step:
- `choose_and_format_visualization` - Does BOTH in one LLM call!

### Configuration - Choose ONE Approach

```yaml
workflow:
  steps:
    # OPTION 1 (Recommended): Combined step - SINGLE LLM call
    choose_and_format_visualization: true       # DEFAULT: Uses optimized single call
    
    # OPTION 2 (Legacy): Separate steps - TWO LLM calls
    choose_visualization: false                 # Set combined to false to use these
    format_data_for_visualization: false        # Set combined to false to use these
```

**⚠️ IMPORTANT:** Only enable ONE approach at a time:
- ✅ **Either** `choose_and_format_visualization: true` (recommended)
- ✅ **Or** `choose_visualization: true` + `format_data_for_visualization: true` (legacy)
- ❌ **Do NOT** enable both combined AND separate steps

### Default Behavior

The new defaults in `ConfigManager` use the optimized approach:

```python
@dataclass
class WorkflowConfig:
    steps: Dict[str, bool] = field(default_factory=lambda: {
        # ... other steps ...
        "choose_and_format_visualization": True,  # DEFAULT: Optimized
        "choose_visualization": False,            # Legacy
        "format_data_for_visualization": False    # Legacy
    })
```

### Custom Prompt Configuration

The combined step uses the `choose_and_format_visualization` prompt. All example configs include this:

```yaml
prompts:
  # OPTION 1: Combined prompt (for single LLM call)
  choose_and_format_visualization:
    system: |
      You are an expert data visualization assistant that BOTH recommends 
      visualizations AND formats data for them - all in a SINGLE response.
      
      Your task has TWO parts that must be completed together:
      1. CHOOSE the most appropriate visualization type
      2. FORMAT the data for both legacy and universal chart formats
      
      **Available Chart Types:**
      - bar, horizontal_bar, line, pie, scatter, area, table, none
      
      **You MUST provide BOTH formats in your response:**
      1. legacy_format: Backward-compatible structure
      2. universal_format: Modern UniversalChartData structure
    
    human: |
      **Question:** {question}
      **SQL Query:** {sql_query}
      **Data:** {num_rows} rows x {num_cols} columns
      **Sample:** {query_results_sample}
      **Full:** {query_results_full}
      
      Generate complete response with ALL fields.
  
  # OPTION 2: Separate prompts (for legacy two-step approach)
  choose_visualization:
    system: "Recommend appropriate visualization..."
    human: "Question: {question}..."
  
  format_data_for_visualization:
    system: "Format data for the chosen visualization..."
    human: "Visualization: {visualization}..."
```

### Backward Compatibility

Old configurations automatically work:

| Configuration | Behavior |
|--------------|----------|
| ✅ `choose_and_format_visualization: true` (default) | **Optimized single LLM call** |
| ✅ `choose_visualization: true` + `format_data_for_visualization: true` | Legacy two LLM calls |
| ❌ Both disabled | No visualization |
| ⚠️ Both combined AND separate enabled | **ERROR - Choose ONE approach!** |

### Benefits

- **~250-400ms faster** per query (1 fewer LLM call)
- **~14% cheaper** (saved LLM call = ~$0.0015 per query for GPT-4o)
- **Type-safe** with Pydantic `CombinedVisualizationResponse` model
- **Explicit control** via workflow steps configuration
- **No hidden magic** - clear configuration options

### Migration Guide

If you have existing configs with the old separate steps:

```yaml
# OLD (still works, but slower)
workflow:
  steps:
    choose_visualization: true
    format_data_for_visualization: true

# NEW (recommended - faster and cheaper)
workflow:
  steps:
    choose_and_format_visualization: true
    choose_visualization: false
    format_data_for_visualization: false
```

### Example Configs

All example configs use the optimized approach by default:
- `example-configs/query-openai.yaml` ✅
- `example-configs/query-bigquery.yaml` ✅
- `example-configs/query-bigquery-advanced.yaml` ✅
- `example-configs/query-vertex-ai.yaml` ✅
- `example-configs/query-azure-openai.yaml` ✅
- `example-configs/query-bedrock.yaml` ✅
- `example-configs/query-vertex-ai-gcloud.yaml` ✅
- `example-configs/query-snowflake.yaml` ✅

