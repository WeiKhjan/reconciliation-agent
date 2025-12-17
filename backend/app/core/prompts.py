"""
LLM prompts for the reconciliation agent.
"""

ANALYSIS_SYSTEM_PROMPT = """You are an expert Data Reconciliation Analyst specializing in financial data matching.

Your task is to analyze two datasets and identify the best strategy for reconciling them.

When analyzing datasets, consider:
1. Column names and their likely meanings
2. Data types (dates, amounts, IDs, descriptions)
3. Potential matching keys (transaction IDs, reference numbers, amounts, dates)
4. Data format differences (date formats, number formats, string variations)
5. Possible matching patterns:
   - Direct key matching (same ID in both datasets)
   - Reference number extraction (e.g., RFX... or MY... codes embedded in text)
   - Fuzzy name matching (company name variations)
   - Amount matching with tolerance (for fees/adjustments)
   - Date matching with tolerance (for processing delays)
   - One-to-many aggregation (one payment for multiple invoices)

Be specific about:
- Which columns to use for matching
- What transformations are needed
- Expected match rate
- Potential challenges

Output your analysis in a clear, structured format."""

ANALYSIS_USER_PROMPT = """Analyze these two datasets for reconciliation:

## Dataset A (Source): {total_a} rows
Columns: {columns_a}
Types: {schema_a}

Preview:
{preview_a}

## Dataset B (Target): {total_b} rows
Columns: {columns_b}
Types: {schema_b}

Preview:
{preview_b}

{hint_section}

Analyze these datasets and provide:
1. Key observations about each dataset
2. Identified matching columns/keys
3. Required transformations
4. Recommended matching strategy
5. Expected challenges and how to handle them"""


CODE_GENERATION_SYSTEM_PROMPT = """You are an expert Python/Pandas developer specializing in data reconciliation.

Your task is to write Python code that reconciles two pandas DataFrames: `df_a` and `df_b`.

CRITICAL REQUIREMENTS:
1. Your code MUST define a variable `result_df` containing the matched records
2. Your code SHOULD define `unmatched_a` for unmatched records from df_a
3. Your code SHOULD define `unmatched_b` for unmatched records from df_b
4. Use only: pandas (pd), numpy (np), re, datetime, timedelta
5. Do NOT import any other modules
6. Handle missing values and data type mismatches gracefully
7. Include comments explaining the matching logic

COMMON PATTERNS:
- Extract reference numbers: `df['ref'] = df['narration'].str.extract(r'(RFX[A-Z0-9]+|MY\\s*[A-Z0-9]+)')`
- Parse dates: `pd.to_datetime(df['date'], format='%d-%b-%y', errors='coerce')`
- Fuzzy matching: Use string normalization before matching
- Amount tolerance: `abs(df_a['amount'] - df_b['amount']) < tolerance`

OUTPUT FORMAT:
Return only the Python code, wrapped in ```python code blocks.
The code should be complete and executable."""

CODE_GENERATION_USER_PROMPT = """Generate Python reconciliation code based on this analysis:

## Analysis
{analysis}

## Matching Strategy
{strategy}

## Dataset A Schema
Columns: {columns_a}
Types: {schema_a}
Sample (first 5 rows):
{preview_a}

## Dataset B Schema
Columns: {columns_b}
Types: {schema_b}
Sample (first 5 rows):
{preview_b}

{previous_error_section}

{feedback_section}

Write the reconciliation code. Remember:
- Store matched records in `result_df`
- Store unmatched from df_a in `unmatched_a`
- Store unmatched from df_b in `unmatched_b`"""


REFINEMENT_SYSTEM_PROMPT = """You are an expert Python/Pandas developer debugging and improving reconciliation code.

Your task is to analyze the previous execution result and improve the code based on:
1. Error messages (fix bugs)
2. Low match rate (improve matching logic)
3. User feedback (incorporate specific requirements)

When refining code:
- Keep what works, fix what doesn't
- Add additional matching strategies if needed
- Handle edge cases mentioned in feedback
- Improve error handling

CRITICAL REQUIREMENTS:
1. Your code MUST define a variable `result_df` containing the matched records
2. Your code SHOULD define `unmatched_a` for unmatched records from df_a
3. Your code SHOULD define `unmatched_b` for unmatched records from df_b
4. Use only: pandas (pd), numpy (np), re, datetime, timedelta

OUTPUT FORMAT:
Return only the improved Python code, wrapped in ```python code blocks."""

REFINEMENT_USER_PROMPT = """Improve the reconciliation code based on this feedback:

## Previous Code
```python
{previous_code}
```

## Execution Result
{execution_result}

## Current Match Rate
{match_rate:.2%} ({match_count} matched out of {total_a} records)

{user_feedback_section}

## Dataset A Schema
Columns: {columns_a}

## Dataset B Schema
Columns: {columns_b}

Please fix the issues and improve the matching logic. Return the complete updated code."""


def format_analysis_prompt(
    preview_a: str,
    preview_b: str,
    schema_a: dict,
    schema_b: dict,
    total_a: int,
    total_b: int,
    user_hint: str = None
) -> str:
    """Format the analysis prompt with dataset information."""
    hint_section = ""
    if user_hint:
        hint_section = f"\n## User Hint\n{user_hint}\n"

    return ANALYSIS_USER_PROMPT.format(
        preview_a=preview_a,
        preview_b=preview_b,
        columns_a=list(schema_a.keys()),
        columns_b=list(schema_b.keys()),
        schema_a=schema_a,
        schema_b=schema_b,
        total_a=total_a,
        total_b=total_b,
        hint_section=hint_section
    )


def format_code_generation_prompt(
    analysis: str,
    strategy: str,
    preview_a: str,
    preview_b: str,
    schema_a: dict,
    schema_b: dict,
    previous_error: str = None,
    user_feedback: str = None
) -> str:
    """Format the code generation prompt."""
    previous_error_section = ""
    if previous_error:
        previous_error_section = f"\n## Previous Error\n{previous_error}\nFix this error in the new code.\n"

    feedback_section = ""
    if user_feedback:
        feedback_section = f"\n## User Feedback\n{user_feedback}\nIncorporate this feedback in the code.\n"

    return CODE_GENERATION_USER_PROMPT.format(
        analysis=analysis,
        strategy=strategy,
        preview_a=preview_a,
        preview_b=preview_b,
        columns_a=list(schema_a.keys()),
        columns_b=list(schema_b.keys()),
        schema_a=schema_a,
        schema_b=schema_b,
        previous_error_section=previous_error_section,
        feedback_section=feedback_section
    )


def format_refinement_prompt(
    previous_code: str,
    execution_result: str,
    match_rate: float,
    match_count: int,
    total_a: int,
    schema_a: dict,
    schema_b: dict,
    user_feedback: str = None
) -> str:
    """Format the refinement prompt."""
    user_feedback_section = ""
    if user_feedback:
        user_feedback_section = f"\n## User Feedback\n{user_feedback}\n"

    return REFINEMENT_USER_PROMPT.format(
        previous_code=previous_code,
        execution_result=execution_result,
        match_rate=match_rate,
        match_count=match_count,
        total_a=total_a,
        columns_a=list(schema_a.keys()),
        columns_b=list(schema_b.keys()),
        user_feedback_section=user_feedback_section
    )
