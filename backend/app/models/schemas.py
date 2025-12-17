"""
Pydantic schemas for the Reconciliation Agent API.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime


class SessionStatus(str, Enum):
    """Status of a reconciliation session."""
    CREATED = "created"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    EXECUTING = "executing"
    EVALUATING = "evaluating"
    AWAITING_FEEDBACK = "awaiting_feedback"
    REFINING = "refining"
    COMPLETE = "complete"
    ERROR = "error"


class FileMetadata(BaseModel):
    """Metadata about an uploaded file."""
    filename: str
    file_type: str
    rows: int
    columns: List[str]
    size_bytes: int
    encoding: Optional[str] = None
    sheets: Optional[List[str]] = None
    parser_used: Optional[str] = None


class DataPreview(BaseModel):
    """Preview of a dataset."""
    columns: List[str]
    dtypes: Dict[str, str]
    sample_rows: List[Dict[str, Any]]
    total_rows: int


class CreateSessionResponse(BaseModel):
    """Response when creating a new session."""
    session_id: str
    status: SessionStatus
    created_at: datetime


class UploadResponse(BaseModel):
    """Response after uploading files."""
    session_id: str
    status: SessionStatus
    dataset_a: FileMetadata
    dataset_b: FileMetadata
    preview_a: DataPreview
    preview_b: DataPreview


class ReconcileRequest(BaseModel):
    """Request to start reconciliation."""
    hint: Optional[str] = Field(
        None,
        description="Optional hint about how to reconcile the datasets"
    )


class ReconcileStatusResponse(BaseModel):
    """Status of an ongoing reconciliation."""
    session_id: str
    status: SessionStatus
    iteration: int
    max_iterations: int
    match_rate: float
    message: Optional[str] = None
    error: Optional[str] = None


class ReconcileResultResponse(BaseModel):
    """Result of a completed reconciliation."""
    session_id: str
    status: SessionStatus
    match_rate: float
    matched_count: int
    unmatched_a_count: int
    unmatched_b_count: int
    total_a_count: int
    total_b_count: int
    generated_code: str
    reasoning_trace: List[str]
    matched_records: List[Dict[str, Any]]
    unmatched_a: List[Dict[str, Any]]
    unmatched_b: List[Dict[str, Any]]


class FeedbackRequest(BaseModel):
    """Request to submit feedback for refinement."""
    feedback: str = Field(
        ...,
        min_length=1,
        description="User feedback to improve reconciliation"
    )


class FeedbackResponse(BaseModel):
    """Response after submitting feedback."""
    session_id: str
    status: SessionStatus
    message: str


class ExportFormat(str, Enum):
    """Available export formats."""
    CSV = "csv"
    XLSX = "xlsx"


class N8nExportOptions(BaseModel):
    """Options for n8n workflow export."""
    workflow_name: str = Field(
        "Reconciliation Workflow",
        description="Name for the exported workflow"
    )


class N8nWorkflowResponse(BaseModel):
    """Response containing n8n workflow JSON."""
    workflow: Dict[str, Any]
    filename: str


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    session_id: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: datetime
