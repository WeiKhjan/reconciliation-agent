"""
API routes for the Reconciliation Agent.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Path
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional
import uuid
import pandas as pd
from datetime import datetime
from io import BytesIO
import json
import logging

from app.models.schemas import (
    CreateSessionResponse,
    UploadResponse,
    ReconcileRequest,
    ReconcileStatusResponse,
    ReconcileResultResponse,
    FeedbackRequest,
    FeedbackResponse,
    N8nExportOptions,
    N8nWorkflowResponse,
    SessionStatus,
    FileMetadata,
    DataPreview,
    ErrorResponse
)
from app.services.file_parser import file_parser
from app.services.n8n_exporter import n8n_exporter
from app.config import settings

# Lazy import agent to avoid startup crashes
reconciliation_agent = None

def get_agent():
    global reconciliation_agent
    if reconciliation_agent is None:
        from app.core.agent import ReconciliationAgent
        reconciliation_agent = ReconciliationAgent()
    return reconciliation_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["reconciliation"])

# In-memory session storage (replace with Redis for production)
sessions = {}


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session():
    """Create a new reconciliation session."""
    session_id = str(uuid.uuid4())

    sessions[session_id] = {
        "id": session_id,
        "status": SessionStatus.CREATED,
        "created_at": datetime.utcnow(),
        "dataset_a": None,
        "dataset_b": None,
        "df_a": None,
        "df_b": None,
        "metadata_a": None,
        "metadata_b": None,
        "hint": None,
        "results": None
    }

    logger.info(f"Created session {session_id}")

    return CreateSessionResponse(
        session_id=session_id,
        status=SessionStatus.CREATED,
        created_at=sessions[session_id]["created_at"]
    )


@router.post("/sessions/{session_id}/upload", response_model=UploadResponse)
async def upload_files(
    session_id: str,
    file_a: UploadFile = File(..., description="Dataset A (source)"),
    file_b: UploadFile = File(..., description="Dataset B (target)")
):
    """Upload the two datasets for reconciliation."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    session["status"] = SessionStatus.UPLOADING

    try:
        # Read file contents
        content_a = await file_a.read()
        content_b = await file_b.read()

        # Parse files
        df_a, metadata_a = file_parser.parse(content_a, file_a.filename)
        df_b, metadata_b = file_parser.parse(content_b, file_b.filename)

        # Get previews
        preview_a = file_parser.get_preview(df_a)
        preview_b = file_parser.get_preview(df_b)

        # Store in session
        session["df_a"] = df_a
        session["df_b"] = df_b
        session["metadata_a"] = metadata_a
        session["metadata_b"] = metadata_b
        session["status"] = SessionStatus.UPLOADED

        logger.info(f"Session {session_id}: Uploaded {file_a.filename} ({len(df_a)} rows) and {file_b.filename} ({len(df_b)} rows)")

        return UploadResponse(
            session_id=session_id,
            status=SessionStatus.UPLOADED,
            dataset_a=FileMetadata(**metadata_a),
            dataset_b=FileMetadata(**metadata_b),
            preview_a=DataPreview(**preview_a),
            preview_b=DataPreview(**preview_b)
        )

    except Exception as e:
        session["status"] = SessionStatus.ERROR
        logger.error(f"Session {session_id}: Upload failed - {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/reconcile")
async def start_reconciliation(
    session_id: str,
    request: ReconcileRequest
):
    """Start the reconciliation process."""
    import asyncio

    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]

    if session["df_a"] is None or session["df_b"] is None:
        raise HTTPException(status_code=400, detail="Please upload datasets first")

    session["status"] = SessionStatus.ANALYZING
    session["hint"] = request.hint

    # Run reconciliation in background using asyncio.create_task
    async def run_reconciliation():
        try:
            logger.info(f"Session {session_id}: Starting reconciliation...")
            result = await get_agent().start_reconciliation(
                session_id=session_id,
                df_a=session["df_a"],
                df_b=session["df_b"],
                user_hint=request.hint
            )
            session["results"] = result
            session["status"] = SessionStatus(result.get("status", "complete"))
            logger.info(f"Session {session_id}: Reconciliation completed with status {session['status']}")
        except Exception as e:
            session["status"] = SessionStatus.ERROR
            session["error"] = str(e)
            logger.error(f"Session {session_id}: Reconciliation failed - {e}")
            import traceback
            traceback.print_exc()

    # Use asyncio.create_task for proper async execution
    asyncio.create_task(run_reconciliation())

    return {
        "session_id": session_id,
        "status": "started",
        "message": "Reconciliation started. Poll /status for progress."
    }


@router.get("/sessions/{session_id}/status", response_model=ReconcileStatusResponse)
async def get_status(session_id: str):
    """Get the current status of a reconciliation session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    results = session.get("results") or {}

    return ReconcileStatusResponse(
        session_id=session_id,
        status=session["status"],
        iteration=results.get("iterations", 0),
        max_iterations=settings.MAX_ITERATIONS,
        match_rate=results.get("match_rate", 0.0),
        message=results.get("execution_result"),
        error=results.get("execution_error") or session.get("error")
    )


@router.get("/sessions/{session_id}/results", response_model=ReconcileResultResponse)
async def get_results(session_id: str):
    """Get the full results of a completed reconciliation."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    results = session.get("results")

    if not results:
        raise HTTPException(status_code=400, detail="Reconciliation not complete")

    return ReconcileResultResponse(
        session_id=session_id,
        status=session["status"],
        match_rate=results.get("match_rate", 0.0),
        matched_count=results.get("match_count", 0),
        unmatched_a_count=len(results.get("unmatched_a", [])),
        unmatched_b_count=len(results.get("unmatched_b", [])),
        total_a_count=results.get("total_a", 0),
        total_b_count=results.get("total_b", 0),
        generated_code=results.get("python_code", ""),
        reasoning_trace=results.get("reasoning_trace", []),
        matched_records=results.get("matched_records", []),
        unmatched_a=results.get("unmatched_a", []),
        unmatched_b=results.get("unmatched_b", [])
    )


@router.post("/sessions/{session_id}/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    session_id: str,
    request: FeedbackRequest
):
    """Submit feedback to refine the reconciliation."""
    import asyncio

    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    session["status"] = SessionStatus.REFINING

    async def process_feedback_task():
        try:
            result = await get_agent().submit_feedback(
                session_id=session_id,
                feedback=request.feedback
            )
            session["results"] = result
            session["status"] = SessionStatus(result.get("status", "complete"))
            logger.info(f"Session {session_id}: Feedback processed, new status {session['status']}")
        except Exception as e:
            session["status"] = SessionStatus.ERROR
            session["error"] = str(e)
            logger.error(f"Session {session_id}: Feedback processing failed - {e}")
            import traceback
            traceback.print_exc()

    asyncio.create_task(process_feedback_task())

    return FeedbackResponse(
        session_id=session_id,
        status=SessionStatus.REFINING,
        message="Feedback received. Processing refinement..."
    )


@router.get("/sessions/{session_id}/export/data")
async def export_data(
    session_id: str,
    format: str = Query("csv", pattern="^(csv|xlsx)$")
):
    """Export reconciled data as CSV or Excel."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    results = session.get("results")

    if not results:
        raise HTTPException(status_code=400, detail="No results to export")

    matched = results.get("matched_records", [])
    df = pd.DataFrame(matched)

    output = BytesIO()

    if format == "csv":
        df.to_csv(output, index=False)
        media_type = "text/csv"
        filename = f"reconciled_data_{session_id[:8]}.csv"
    else:
        df.to_excel(output, index=False, engine='openpyxl')
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"reconciled_data_{session_id[:8]}.xlsx"

    output.seek(0)

    return StreamingResponse(
        output,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/sessions/{session_id}/export/code")
async def export_code(session_id: str):
    """Export the generated Python code."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    results = session.get("results")

    if not results:
        raise HTTPException(status_code=400, detail="No code to export")

    code = results.get("python_code", "# No code generated")

    return StreamingResponse(
        BytesIO(code.encode()),
        media_type="text/x-python",
        headers={"Content-Disposition": f"attachment; filename=reconciliation_code_{session_id[:8]}.py"}
    )


@router.get("/sessions/{session_id}/export/n8n", response_model=N8nWorkflowResponse)
async def export_n8n_workflow(session_id: str):
    """Export n8n workflow JSON with JavaScript nodes."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    results = session.get("results")

    if not results:
        raise HTTPException(status_code=400, detail="No results to export")

    code = results.get("python_code", "")

    workflow = n8n_exporter.generate_workflow(
        python_code=code,
        workflow_name=f"Reconciliation Workflow - {session_id[:8]}"
    )

    return N8nWorkflowResponse(
        workflow=workflow,
        filename=f"reconciliation_workflow_{session_id[:8]}.json"
    )


@router.get("/sessions/{session_id}/export/n8n/download")
async def download_n8n_workflow(session_id: str):
    """Download n8n workflow as JSON file with JavaScript nodes."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    results = session.get("results")

    if not results:
        raise HTTPException(status_code=400, detail="No results to export")

    code = results.get("python_code", "")

    workflow = n8n_exporter.generate_workflow(
        python_code=code,
        workflow_name=f"Reconciliation Workflow - {session_id[:8]}"
    )

    json_content = json.dumps(workflow, indent=2)
    filename = f"reconciliation_workflow_{session_id[:8]}.json"

    return StreamingResponse(
        BytesIO(json_content.encode()),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/sessions/{session_id}/preview/{dataset}")
async def get_preview(
    session_id: str,
    dataset: str = Path(..., pattern="^(a|b)$")
):
    """Get preview of a dataset."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]

    df = session.get(f"df_{dataset}")
    if df is None:
        raise HTTPException(status_code=400, detail=f"Dataset {dataset} not uploaded")

    preview = file_parser.get_preview(df)
    return preview


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and its data."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    del sessions[session_id]
    logger.info(f"Deleted session {session_id}")

    return {"message": "Session deleted", "session_id": session_id}
