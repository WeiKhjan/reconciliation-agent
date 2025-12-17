"""
LangGraph nodes for the reconciliation agent.
"""
import pandas as pd
from typing import Dict, Any
import logging

from langchain_core.messages import HumanMessage, AIMessage

from app.core.state import ReconciliationState
from app.core.prompts import (
    ANALYSIS_SYSTEM_PROMPT,
    CODE_GENERATION_SYSTEM_PROMPT,
    REFINEMENT_SYSTEM_PROMPT,
    format_analysis_prompt,
    format_code_generation_prompt,
    format_refinement_prompt
)
from app.services.llm_client import get_llm
from app.services.code_executor import code_executor

logger = logging.getLogger(__name__)


async def analyze_schemas(state: ReconciliationState) -> Dict[str, Any]:
    """
    Analyze both datasets to identify matching strategy.

    This node:
    1. Examines column names and data types
    2. Identifies potential matching keys
    3. Suggests transformations needed
    4. Proposes a matching strategy
    """
    logger.info(f"[{state['session_id']}] Analyzing schemas...")

    llm = get_llm()

    # Format the analysis prompt
    user_prompt = format_analysis_prompt(
        preview_a=state['dataset_a_preview'],
        preview_b=state['dataset_b_preview'],
        schema_a=state['dataset_a_schema'],
        schema_b=state['dataset_b_schema'],
        total_a=state['total_a'],
        total_b=state['total_b'],
        user_hint=state.get('user_hint')
    )

    messages = [
        {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    response = await llm.ainvoke(messages)
    analysis = response.content

    # Update reasoning trace
    reasoning_trace = state.get('reasoning_trace', []).copy()
    reasoning_trace.append(f"Schema Analysis:\n{analysis}")

    logger.info(f"[{state['session_id']}] Schema analysis complete")

    return {
        "analysis": analysis,
        "status": "generating",
        "reasoning_trace": reasoning_trace,
        "messages": [
            HumanMessage(content=user_prompt),
            AIMessage(content=analysis)
        ]
    }


async def generate_strategy(state: ReconciliationState) -> Dict[str, Any]:
    """
    Generate a specific matching strategy based on analysis.

    This node refines the analysis into actionable matching rules.
    """
    logger.info(f"[{state['session_id']}] Generating matching strategy...")

    llm = get_llm()

    strategy_prompt = f"""Based on this analysis of the two datasets:

{state['analysis']}

Provide a specific, step-by-step matching strategy that includes:
1. Primary matching key(s) and how to extract/transform them
2. Secondary matching criteria if primary fails
3. How to handle unmatched records
4. Any data cleaning steps needed

Be specific about column names and transformations."""

    messages = [
        {"role": "system", "content": "You are a data reconciliation strategist. Provide clear, actionable matching strategies."},
        {"role": "user", "content": strategy_prompt}
    ]

    response = await llm.ainvoke(messages)
    strategy = response.content

    # Update reasoning trace
    reasoning_trace = state.get('reasoning_trace', []).copy()
    reasoning_trace.append(f"Matching Strategy:\n{strategy}")

    logger.info(f"[{state['session_id']}] Strategy generation complete")

    return {
        "matching_strategy": strategy,
        "reasoning_trace": reasoning_trace,
        "messages": [
            HumanMessage(content=strategy_prompt),
            AIMessage(content=strategy)
        ]
    }


async def generate_code(state: ReconciliationState) -> Dict[str, Any]:
    """
    Generate Python/Pandas reconciliation code.

    This node creates executable code based on the analysis and strategy.
    """
    logger.info(f"[{state['session_id']}] Generating reconciliation code (iteration {state['iterations'] + 1})...")

    llm = get_llm()

    # Determine if this is a refinement (has previous code and error)
    previous_error = None
    if state.get('execution_error') and state.get('python_code'):
        previous_error = state['execution_error']

    # Format the code generation prompt
    user_prompt = format_code_generation_prompt(
        analysis=state.get('analysis', 'No analysis available'),
        strategy=state.get('matching_strategy', 'No strategy available'),
        preview_a=state['dataset_a_preview'],
        preview_b=state['dataset_b_preview'],
        schema_a=state['dataset_a_schema'],
        schema_b=state['dataset_b_schema'],
        previous_error=previous_error,
        user_feedback=state.get('user_feedback')
    )

    messages = [
        {"role": "system", "content": CODE_GENERATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    response = await llm.ainvoke(messages)
    code = response.content

    # Update code history
    code_history = state.get('code_history', []).copy()
    if state.get('python_code'):
        code_history.append(state['python_code'])

    # Update reasoning trace
    reasoning_trace = state.get('reasoning_trace', []).copy()
    reasoning_trace.append(f"Generated Code (iteration {state['iterations'] + 1}):\n```python\n{code}\n```")

    logger.info(f"[{state['session_id']}] Code generation complete")

    return {
        "python_code": code,
        "code_history": code_history,
        "status": "executing",
        "iterations": state['iterations'] + 1,
        "execution_error": None,  # Clear previous error
        "reasoning_trace": reasoning_trace,
        "messages": [
            HumanMessage(content=user_prompt),
            AIMessage(content=code)
        ]
    }


def execute_code(state: ReconciliationState) -> Dict[str, Any]:
    """
    Execute the generated code in a sandbox.

    This node runs the code against the actual datasets and captures results.
    """
    logger.info(f"[{state['session_id']}] Executing code...")

    # Convert data back to DataFrames
    df_a = pd.DataFrame(state['dataset_a'])
    df_b = pd.DataFrame(state['dataset_b'])

    # Execute the code
    result = code_executor.execute(
        code=state['python_code'],
        df_a=df_a,
        df_b=df_b
    )

    # Update reasoning trace
    reasoning_trace = state.get('reasoning_trace', []).copy()

    if result['success']:
        reasoning_trace.append(
            f"Execution Result: SUCCESS\n"
            f"Match Rate: {result['match_rate']:.2%}\n"
            f"Matched: {result['match_count']} / {result['total_a']} records"
        )
        logger.info(f"[{state['session_id']}] Code execution successful. Match rate: {result['match_rate']:.2%}")

        return {
            "execution_result": f"Success. Matched {result['match_count']} out of {result['total_a']} records.",
            "execution_error": None,
            "matched_records": result['matched'],
            "unmatched_a": result['unmatched_a'],
            "unmatched_b": result['unmatched_b'],
            "match_rate": result['match_rate'],
            "match_count": result['match_count'],
            "status": "evaluating",
            "reasoning_trace": reasoning_trace
        }
    else:
        reasoning_trace.append(f"Execution Error: {result['error']}")
        logger.warning(f"[{state['session_id']}] Code execution failed: {result['error']}")

        return {
            "execution_result": f"Error: {result['error']}",
            "execution_error": result['error'],
            "match_rate": 0.0,
            "match_count": 0,
            "status": "evaluating",
            "reasoning_trace": reasoning_trace
        }


async def evaluate_results(state: ReconciliationState) -> Dict[str, Any]:
    """
    Evaluate the reconciliation results and determine next steps.

    This node analyzes the match rate and decides whether to:
    - Complete (high match rate)
    - Retry (has error or low match rate, iterations remaining)
    - Await feedback (max iterations reached)
    """
    logger.info(f"[{state['session_id']}] Evaluating results...")

    match_rate = state.get('match_rate', 0.0)
    has_error = state.get('execution_error') is not None
    iterations = state.get('iterations', 0)
    max_iterations = state.get('max_iterations', 5)

    # Update reasoning trace
    reasoning_trace = state.get('reasoning_trace', []).copy()

    # Determine status
    if not has_error and match_rate >= 0.95:
        status = "complete"
        reasoning_trace.append(f"Evaluation: Complete! Match rate {match_rate:.2%} exceeds 95% threshold.")
        logger.info(f"[{state['session_id']}] Reconciliation complete with {match_rate:.2%} match rate")
    elif iterations >= max_iterations:
        status = "awaiting_feedback"
        reasoning_trace.append(
            f"Evaluation: Reached max iterations ({max_iterations}). "
            f"Current match rate: {match_rate:.2%}. Awaiting user feedback."
        )
        logger.info(f"[{state['session_id']}] Max iterations reached. Awaiting feedback.")
    else:
        status = "generating"  # Will trigger retry
        if has_error:
            reasoning_trace.append(f"Evaluation: Error detected. Will retry code generation.")
        else:
            reasoning_trace.append(
                f"Evaluation: Match rate {match_rate:.2%} below 95% threshold. "
                f"Iteration {iterations}/{max_iterations}. Retrying..."
            )
        logger.info(f"[{state['session_id']}] Retrying. Match rate: {match_rate:.2%}")

    return {
        "status": status,
        "reasoning_trace": reasoning_trace
    }


async def process_feedback(state: ReconciliationState) -> Dict[str, Any]:
    """
    Process user feedback and prepare for refinement.

    This node incorporates user feedback into the context for the next iteration.
    """
    logger.info(f"[{state['session_id']}] Processing user feedback...")

    feedback = state.get('user_feedback', '')

    # Update reasoning trace
    reasoning_trace = state.get('reasoning_trace', []).copy()
    reasoning_trace.append(f"User Feedback Received:\n{feedback}")

    # Reset iterations to allow more attempts after feedback
    # (or keep current count if you want to limit total attempts)

    logger.info(f"[{state['session_id']}] Feedback processed. Preparing for refinement.")

    return {
        "status": "generating",
        "reasoning_trace": reasoning_trace
    }
