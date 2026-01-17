# ============================================
# FILE: app/models.py
# ============================================
"""
Pydantic models for request/response validation.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, validator


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="User's legal query",
        example="What is Section 302 of IPC?"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session ID for conversation history"
    )
    
    @validator("query")
    def validate_query(cls, v: str) -> str:
        """Ensure query is not just whitespace."""
        if not v.strip():
            raise ValueError("Query cannot be empty or whitespace")
        return v.strip()


class RetrievedDocument(BaseModel):
    """Model for a retrieved document."""
    
    section: str = Field(..., description="IPC section number")
    title: str = Field(..., description="Section title")
    text: str = Field(..., description="Section content")
    score: float = Field(..., description="Relevance score", ge=0.0, le=1.0)


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    
    answer: str = Field(..., description="Generated answer from LLM")
    sources: List[RetrievedDocument] = Field(
        default=[],
        description="Source documents used to generate answer"
    )
    session_id: str = Field(..., description="Session ID for this conversation")
    query: str = Field(..., description="Original user query")


class HealthResponse(BaseModel):
    """Response model for health check."""
    
    status: str = Field(default="healthy", description="Service health status")
    environment: str = Field(..., description="Runtime environment")
    version: str = Field(default="1.0.0", description="API version")
    services: dict = Field(
        default={},
        description="Status of dependent services"
    )


class ErrorResponse(BaseModel):
    """Standard error response."""
    
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict] = Field(default=None, description="Additional error details")

