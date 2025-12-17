"""
LangGraph agent for reconciliation logic discovery.
"""
from typing import Dict, Any, Optional
import logging
import pandas as pd

# LangGraph imports with fallback for different versions
try:
    from langgraph.graph import StateGraph, END
except ImportError:
    from langgraph.graph import StateGraph
    END = "__end__"

try:
    from langgraph.checkpoint.memory import MemorySaver
except ImportError:
    # Fallback for older versions
    MemorySaver = None

from app.core.state import ReconciliationState, create_initial_state
from app.core.nodes import (
    analyze_schemas,
    generate_strategy,
    generate_code,
    execute_code,
    evaluate_results,
    process_feedback
)
from app.services.file_parser import file_parser
from app.config import settings

logger = logging.getLogger(__name__)


def should_continue(state: ReconciliationState) -> str:
    """
    Determine the next step based on current state.

    Routes to:
    - "complete": Reconciliation successful
    - "retry": Need to regenerate code
    - "await_feedback": Max iterations reached, need user input
    """
    status = state.get("status", "")

    if status == "complete":
        return "complete"
    elif status == "awaiting_feedback":
        return "await_feedback"
    elif status in ["generating", "executing", "evaluating"]:
        # Check if we should retry or continue
        if state.get("execution_error") or state.get("match_rate", 0) < 0.95:
            if state.get("iterations", 0) < state.get("max_iterations", 5):
                return "retry"
            else:
                return "await_feedback"
        return "complete"
    else:
        return "retry"


def create_reconciliation_graph() -> StateGraph:
    """
    Create the LangGraph for reconciliation.

    Graph structure:
    analyze -> strategize -> generate -> execute -> evaluate
                                ^                      |
                                |                      v
                         [retry if needed] <----- [check result]
                                                       |
                                                       v
                                                  [complete or await_feedback]
    """
    workflow = StateGraph(ReconciliationState)

    # Add nodes
    workflow.add_node("analyze", analyze_schemas)
    workflow.add_node("strategize", generate_strategy)
    workflow.add_node("generate", generate_code)
    workflow.add_node("execute", execute_code)
    workflow.add_node("evaluate", evaluate_results)
    workflow.add_node("process_feedback", process_feedback)

    # Set entry point
    workflow.set_entry_point("analyze")

    # Define edges
    workflow.add_edge("analyze", "strategize")
    workflow.add_edge("strategize", "generate")
    workflow.add_edge("generate", "execute")
    workflow.add_edge("execute", "evaluate")

    # Conditional edges from evaluate
    workflow.add_conditional_edges(
        "evaluate",
        should_continue,
        {
            "complete": END,
            "retry": "generate",
            "await_feedback": END
        }
    )

    # Feedback re-entry point
    workflow.add_edge("process_feedback", "generate")

    return workflow


def compile_agent(checkpointer=None):
    """
    Compile the reconciliation agent with optional checkpointing.

    Args:
        checkpointer: Optional memory saver for state persistence

    Returns:
        Compiled LangGraph application
    """
    graph = create_reconciliation_graph()

    if checkpointer is None and MemorySaver is not None:
        checkpointer = MemorySaver()

    if checkpointer:
        return graph.compile(checkpointer=checkpointer)
    else:
        return graph.compile()


class ReconciliationAgent:
    """
    High-level interface for the reconciliation agent.

    Manages state, provides easy methods for running reconciliation
    and handling user feedback.
    """

    def __init__(self):
        self.checkpointer = MemorySaver() if MemorySaver else None
        self.agent = compile_agent(self.checkpointer)
        self.sessions: Dict[str, ReconciliationState] = {}

    async def start_reconciliation(
        self,
        session_id: str,
        df_a: pd.DataFrame,
        df_b: pd.DataFrame,
        user_hint: Optional[str] = None
    ) -> ReconciliationState:
        """
        Start a new reconciliation session.

        Args:
            session_id: Unique session identifier
            df_a: First dataset
            df_b: Second dataset
            user_hint: Optional user hint about reconciliation

        Returns:
            Final state after running the agent
        """
        logger.info(f"Starting reconciliation session {session_id}")

        # Create initial state
        initial_state = create_initial_state(
            session_id=session_id,
            dataset_a=df_a.fillna("").to_dict('records'),
            dataset_b=df_b.fillna("").to_dict('records'),
            dataset_a_preview=file_parser.to_markdown_preview(df_a, rows=10),
            dataset_b_preview=file_parser.to_markdown_preview(df_b, rows=10),
            dataset_a_schema=file_parser.get_schema(df_a),
            dataset_b_schema=file_parser.get_schema(df_b),
            user_hint=user_hint,
            max_iterations=settings.MAX_ITERATIONS
        )

        # Run the agent
        config = {"configurable": {"thread_id": session_id}}

        try:
            final_state = await self.agent.ainvoke(initial_state, config)
            self.sessions[session_id] = final_state
            logger.info(f"Session {session_id} completed with status: {final_state.get('status')}")
            return final_state
        except Exception as e:
            logger.error(f"Session {session_id} failed: {e}")
            initial_state["status"] = "error"
            initial_state["execution_error"] = str(e)
            self.sessions[session_id] = initial_state
            return initial_state

    async def submit_feedback(
        self,
        session_id: str,
        feedback: str
    ) -> ReconciliationState:
        """
        Submit user feedback and continue reconciliation.

        Args:
            session_id: Session to continue
            feedback: User feedback text

        Returns:
            Updated state after processing feedback
        """
        logger.info(f"Processing feedback for session {session_id}")

        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        config = {"configurable": {"thread_id": session_id}}

        # Get current state and update with feedback
        current_state = self.sessions[session_id]
        current_state["user_feedback"] = feedback
        current_state["status"] = "refining"

        # Update state in checkpointer
        self.agent.update_state(config, {
            "user_feedback": feedback,
            "status": "refining"
        })

        # Run from process_feedback node
        # First process the feedback
        feedback_result = await process_feedback(current_state)
        current_state.update(feedback_result)

        # Then continue with code generation
        try:
            final_state = await self.agent.ainvoke(None, config)
            self.sessions[session_id] = final_state
            logger.info(f"Feedback processed for {session_id}. New status: {final_state.get('status')}")
            return final_state
        except Exception as e:
            logger.error(f"Feedback processing failed for {session_id}: {e}")
            current_state["status"] = "error"
            current_state["execution_error"] = str(e)
            return current_state

    def get_session_state(self, session_id: str) -> Optional[ReconciliationState]:
        """Get the current state of a session."""
        return self.sessions.get(session_id)

    def get_results(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the results of a completed session.

        Returns:
            Dict with matched records, unmatched records, code, and metrics
        """
        state = self.sessions.get(session_id)
        if not state:
            return None

        return {
            "status": state.get("status"),
            "match_rate": state.get("match_rate", 0.0),
            "match_count": state.get("match_count", 0),
            "total_a": state.get("total_a", 0),
            "total_b": state.get("total_b", 0),
            "matched_records": state.get("matched_records", []),
            "unmatched_a": state.get("unmatched_a", []),
            "unmatched_b": state.get("unmatched_b", []),
            "generated_code": state.get("python_code", ""),
            "reasoning_trace": state.get("reasoning_trace", []),
            "iterations": state.get("iterations", 0)
        }


# Global agent instance
reconciliation_agent = ReconciliationAgent()
