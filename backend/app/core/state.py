"""
LangGraph state definition for the reconciliation agent.
"""
from typing import TypedDict, Annotated, List, Optional, Dict, Any
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage


class ReconciliationState(TypedDict):
    """
    State maintained throughout the reconciliation process.

    This state is passed between nodes in the LangGraph and contains
    all information needed for the reconciliation workflow.
    """

    # Session identification
    session_id: str

    # Input data (stored as list of dicts for serialization)
    dataset_a: List[Dict[str, Any]]
    dataset_b: List[Dict[str, Any]]

    # Data previews for LLM context (first N rows as markdown)
    dataset_a_preview: str
    dataset_b_preview: str

    # Schema information
    dataset_a_schema: Dict[str, str]  # Column names -> dtypes
    dataset_b_schema: Dict[str, str]
    dataset_a_columns: List[str]
    dataset_b_columns: List[str]

    # Row counts
    total_a: int
    total_b: int

    # User inputs
    user_hint: Optional[str]
    user_feedback: Optional[str]

    # LLM conversation messages
    messages: Annotated[List[BaseMessage], add_messages]

    # Analysis results
    analysis: Optional[str]
    matching_strategy: Optional[str]

    # Generated code
    python_code: str
    code_history: List[str]

    # Execution results
    execution_result: str
    execution_error: Optional[str]

    # Output data
    matched_records: List[Dict[str, Any]]
    unmatched_a: List[Dict[str, Any]]
    unmatched_b: List[Dict[str, Any]]
    match_rate: float
    match_count: int

    # Control flow
    iterations: int
    max_iterations: int
    status: str  # analyzing, generating, executing, evaluating, awaiting_feedback, complete, error

    # Reasoning trace for transparency
    reasoning_trace: List[str]


def create_initial_state(
    session_id: str,
    dataset_a: List[Dict[str, Any]],
    dataset_b: List[Dict[str, Any]],
    dataset_a_preview: str,
    dataset_b_preview: str,
    dataset_a_schema: Dict[str, str],
    dataset_b_schema: Dict[str, str],
    user_hint: Optional[str] = None,
    max_iterations: int = 5
) -> ReconciliationState:
    """
    Create the initial state for a new reconciliation session.

    Args:
        session_id: Unique session identifier
        dataset_a: First dataset as list of dicts
        dataset_b: Second dataset as list of dicts
        dataset_a_preview: Markdown preview of dataset A
        dataset_b_preview: Markdown preview of dataset B
        dataset_a_schema: Column types for dataset A
        dataset_b_schema: Column types for dataset B
        user_hint: Optional user hint about reconciliation
        max_iterations: Maximum refinement iterations

    Returns:
        Initialized ReconciliationState
    """
    return ReconciliationState(
        session_id=session_id,
        dataset_a=dataset_a,
        dataset_b=dataset_b,
        dataset_a_preview=dataset_a_preview,
        dataset_b_preview=dataset_b_preview,
        dataset_a_schema=dataset_a_schema,
        dataset_b_schema=dataset_b_schema,
        dataset_a_columns=list(dataset_a_schema.keys()),
        dataset_b_columns=list(dataset_b_schema.keys()),
        total_a=len(dataset_a),
        total_b=len(dataset_b),
        user_hint=user_hint,
        user_feedback=None,
        messages=[],
        analysis=None,
        matching_strategy=None,
        python_code="",
        code_history=[],
        execution_result="",
        execution_error=None,
        matched_records=[],
        unmatched_a=[],
        unmatched_b=[],
        match_rate=0.0,
        match_count=0,
        iterations=0,
        max_iterations=max_iterations,
        status="analyzing",
        reasoning_trace=[]
    )
