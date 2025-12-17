"""
API client for communicating with the backend.
"""
import httpx
import os
from typing import Dict, Any, Optional, Tuple
import streamlit as st

# Backend URL from environment or default
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080")


class APIClient:
    """Client for the Reconciliation Agent API."""

    def __init__(self, base_url: str = None):
        # Remove trailing slash to prevent double slashes in URLs
        self.base_url = (base_url or BACKEND_URL).rstrip("/")
        self.timeout = httpx.Timeout(300.0)  # 5 minute timeout for long operations

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Handle API response and errors."""
        if response.status_code >= 400:
            try:
                error_data = response.json()
                error_msg = error_data.get("detail", str(error_data))
            except:
                error_msg = response.text
            raise Exception(f"API Error ({response.status_code}): {error_msg}")
        return response.json()

    def create_session(self) -> Dict[str, Any]:
        """Create a new reconciliation session."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.base_url}/api/sessions")
            return self._handle_response(response)

    def upload_files(
        self,
        session_id: str,
        file_a: Tuple[str, bytes, str],
        file_b: Tuple[str, bytes, str]
    ) -> Dict[str, Any]:
        """
        Upload two files for reconciliation.

        Args:
            session_id: Session ID
            file_a: Tuple of (filename, content, content_type)
            file_b: Tuple of (filename, content, content_type)
        """
        with httpx.Client(timeout=self.timeout) as client:
            files = {
                "file_a": file_a,
                "file_b": file_b
            }
            response = client.post(
                f"{self.base_url}/api/sessions/{session_id}/upload",
                files=files
            )
            return self._handle_response(response)

    def start_reconciliation(
        self,
        session_id: str,
        hint: Optional[str] = None
    ) -> Dict[str, Any]:
        """Start the reconciliation process."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/api/sessions/{session_id}/reconcile",
                json={"hint": hint}
            )
            return self._handle_response(response)

    def get_status(self, session_id: str) -> Dict[str, Any]:
        """Get reconciliation status."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.base_url}/api/sessions/{session_id}/status"
            )
            return self._handle_response(response)

    def get_results(self, session_id: str) -> Dict[str, Any]:
        """Get reconciliation results."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.base_url}/api/sessions/{session_id}/results"
            )
            return self._handle_response(response)

    def submit_feedback(
        self,
        session_id: str,
        feedback: str
    ) -> Dict[str, Any]:
        """Submit feedback for refinement."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/api/sessions/{session_id}/feedback",
                json={"feedback": feedback}
            )
            return self._handle_response(response)

    def get_preview(
        self,
        session_id: str,
        dataset: str
    ) -> Dict[str, Any]:
        """Get preview of a dataset."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.base_url}/api/sessions/{session_id}/preview/{dataset}"
            )
            return self._handle_response(response)

    def export_data(
        self,
        session_id: str,
        format: str = "csv"
    ) -> bytes:
        """Export reconciled data."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.base_url}/api/sessions/{session_id}/export/data",
                params={"format": format}
            )
            if response.status_code >= 400:
                raise Exception(f"Export failed: {response.text}")
            return response.content

    def export_code(self, session_id: str) -> str:
        """Export generated Python code."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.base_url}/api/sessions/{session_id}/export/code"
            )
            if response.status_code >= 400:
                raise Exception(f"Export failed: {response.text}")
            return response.content.decode()

    def export_n8n(self, session_id: str) -> Dict[str, Any]:
        """Export n8n workflow JSON with JavaScript nodes."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.base_url}/api/sessions/{session_id}/export/n8n"
            )
            return self._handle_response(response)

    def download_n8n(self, session_id: str) -> bytes:
        """Download n8n workflow as JSON file with JavaScript nodes."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.base_url}/api/sessions/{session_id}/export/n8n/download"
            )
            if response.status_code >= 400:
                raise Exception(f"Download failed: {response.text}")
            return response.content

    def health_check(self) -> Dict[str, Any]:
        """Check if backend is healthy."""
        try:
            with httpx.Client(timeout=httpx.Timeout(5.0)) as client:
                response = client.get(f"{self.base_url}/health")
                return self._handle_response(response)
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# Global client instance
api_client = APIClient()
