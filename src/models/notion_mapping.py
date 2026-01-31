"""Notion Mapping Models

This module defines models for tracking relationships between local content and Notion database rows.
Enables bidirectional sync and prevents duplicate row creation.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class NotionMapping(BaseModel):
    """Mapping between local content unit and Notion database row.
    
    Tracks the relationship to enable:
    - Updates to existing Notion rows (vs creating duplicates)
    - Status synchronization between Notion and local files
    - Audit trail of push/sync operations
    """
    
    content_id: str = Field(..., description="Local content UUID")
    notion_page_id: str = Field(..., description="Notion database row/page ID")
    
    language: str = Field(..., description="Content language (zh, ja, fr, etc.)")
    level: str = Field(..., description="Proficiency level (hsk1, jlpt-n5, a1, etc.)")
    type: Literal["conversation", "story"] = Field(..., description="Content type")
    title: str = Field(..., description="Content title for reference")
    
    # Sync tracking
    last_pushed_at: datetime = Field(..., description="Timestamp of last push to Notion")
    last_synced_at: datetime | None = Field(
        default=None,
        description="Timestamp of last sync from Notion (checking status changes)"
    )
    
    # Status tracking
    status_in_notion: Literal[
        "Not started", 
        "Ready for Review", 
        "Reviewing", 
        "Ready for Audio", 
        "Rejected", 
        "OK"
    ] = Field(..., description="Current Status field value in Notion")
    
    status_in_local: str = Field(
        default="pending_review",
        description="Status in local JSON file (pending_review, approved, rejected, published)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "content_id": "abc123-def456-ghi789",
                "notion_page_id": "notion-page-xyz789",
                "language": "zh",
                "level": "hsk1",
                "type": "conversation",
                "title": "Shopping at the Supermarket",
                "last_pushed_at": "2026-01-31T10:30:00Z",
                "last_synced_at": "2026-01-31T15:45:00Z",
                "status_in_notion": "Ready for Audio",
                "status_in_local": "approved"
            }
        }


class NotionPushQueue(BaseModel):
    """Failed Notion push operation awaiting retry.
    
    Stores complete payload for failed push attempts to enable manual retry
    without regenerating evaluation or formatting conversation data.
    """
    
    content_id: str = Field(..., description="Local content UUID")
    type: Literal["conversation", "story"] = Field(..., description="Content type")
    title: str = Field(..., description="Content title")
    language: str = Field(..., description="Content language")
    level: str = Field(..., description="Proficiency level")
    
    # Retry tracking
    attempt_count: int = Field(default=1, ge=1, description="Number of push attempts")
    last_error: str = Field(..., description="Error message from last failed attempt")
    failed_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of last failure")
    
    # Full payload for retry
    payload: dict = Field(..., description="Complete Notion row data (Type, Title, Script, etc.)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "content_id": "abc123-def456-ghi789",
                "type": "conversation",
                "title": "Shopping at the Supermarket",
                "language": "zh",
                "level": "hsk1",
                "attempt_count": 2,
                "last_error": "Notion API rate limit exceeded (429)",
                "failed_at": "2026-01-31T10:30:00Z",
                "payload": {
                    "Type": "conversation",
                    "Title": "Shopping at the Supermarket",
                    "Description": "HSK1 level conversation about...",
                    "Script": "Speaker 1: 你好...",
                    "LLM Comment": "{...}"
                }
            }
        }
