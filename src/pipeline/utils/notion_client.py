"""
Notion API client for content review workflow.

This module provides a client for interacting with the Notion database
used for human review of generated content. It handles:
- Schema validation
- Pushing new conversations/stories for review
- Fetching status changes from reviewers
- Updating audio URLs and status fields
- Retry logic with exponential backoff
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
from pydantic import ValidationError

from src.models.llm_judge_evaluation import LLMJudgeEvaluation
from src.models.notion_mapping import NotionPushQueue

logger = logging.getLogger(__name__)


class NotionSchemaError(Exception):
    """Raised when Notion database schema doesn't match expected structure."""
    pass


class NotionClient:
    """Client for Notion database operations."""
    
    # Expected database schema
    REQUIRED_COLUMNS = {
        "Type": "select",
        "Title": "title",
        "Description": "rich_text",
        "Topic": "rich_text",
        "Scenario": "rich_text",
        "Script": "rich_text",
        "Translation": "rich_text",
        "Audio": "files",  # Changed from "url" to match actual Notion type
        "LLM Comment": "rich_text",
        "Human Comment": "rich_text",
        "Status": "status",  # Changed from "select" to match actual Notion type
    }
    
    # Status values
    STATUS_VALUES = [
        "Not started",
        "Ready for Review",
        "Reviewing",
        "Ready for Audio",
        "Rejected",
        "OK"
    ]
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0  # seconds
    RETRY_MULTIPLIER = 2.0
    
    # Notion API configuration
    NOTION_API_VERSION = "2025-09-03"
    NOTION_API_BASE = "https://api.notion.com/v1"
    
    def __init__(
        self,
        api_token: str,
        database_id: str,
        queue_file: str = "notion_push_queue.jsonl"
    ):
        """
        Initialize Notion client.
        
        Args:
            api_token: Notion integration API token
            database_id: Notion database ID
            queue_file: Path to failed push queue file
        """
        self.api_token = api_token
        self.database_id = database_id
        self.queue_file = queue_file
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Notion-Version": self.NOTION_API_VERSION,
            "Content-Type": "application/json"
        }
        self.data_source_id = None  # Will be fetched on first use
        
    def _get_data_source_id(self) -> str:
        """
        Fetch data source ID from database (API v2025-09-03).
        Uses the first data source if multiple exist.
        
        Returns:
            Data source ID
        """
        if self.data_source_id:
            return self.data_source_id
            
        # Retrieve database to get data sources
        url = f"{self.NOTION_API_BASE}/databases/{self.database_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        database = response.json()
        
        data_sources = database.get("data_sources", [])
        if not data_sources:
            raise NotionSchemaError("No data sources found in database")
            
        # Use first data source (most common case)
        self.data_source_id = data_sources[0]["id"]
        logger.info(f"Using data source: {data_sources[0].get('name', self.data_source_id)}")
        
        return self.data_source_id
        
    def validate_database_schema(self) -> None:
        """
        Validate that Notion database has expected schema.
        
        Raises:
            NotionSchemaError: If schema doesn't match expected structure
        """
        try:
            # Get data source ID first (API v2025-09-03)
            data_source_id = self._get_data_source_id()
            
            # Retrieve data source to get properties (schema)
            url = f"{self.NOTION_API_BASE}/data_sources/{data_source_id}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data_source = response.json()
            properties = data_source.get("properties", {})
            
            # Check each required column
            missing_columns = []
            type_mismatches = []
            
            for col_name, expected_type in self.REQUIRED_COLUMNS.items():
                if col_name not in properties:
                    missing_columns.append(col_name)
                    continue
                    
                actual_type = properties[col_name].get("type")
                if actual_type != expected_type:
                    type_mismatches.append(
                        f"{col_name} (expected {expected_type}, found {actual_type})"
                    )
            
            # Report errors
            if missing_columns or type_mismatches:
                error_parts = []
                if missing_columns:
                    error_parts.append(
                        f"Missing columns: {', '.join(missing_columns)}"
                    )
                if type_mismatches:
                    error_parts.append(
                        f"Type mismatches: {', '.join(type_mismatches)}"
                    )
                raise NotionSchemaError("; ".join(error_parts))
                
            # Validate Status options (status type, not select)
            status_property = properties.get("Status", {})
            status_options = status_property.get("status", {}).get("options", [])
            available_statuses = {opt["name"] for opt in status_options}
            
            missing_statuses = set(self.STATUS_VALUES) - available_statuses
            if missing_statuses:
                logger.warning(
                    f"Status field missing expected values: {', '.join(missing_statuses)}"
                )
                
        except Exception as e:
            if isinstance(e, NotionSchemaError):
                raise
            raise NotionSchemaError(f"Failed to retrieve database schema: {str(e)}")
            
    def format_script(self, segments: List[Dict[str, Any]]) -> str:
        """
        Format conversation segments with speaker labels.
        
        Args:
            segments: List of segment dicts with 'speaker' and 'text' fields
            
        Returns:
            Formatted script string (e.g., "Speaker-1: Hello\nSpeaker-2: Hi")
        """
        lines = []
        for segment in segments:
            speaker = segment.get("speaker", "Unknown")
            text = segment.get("text", "")
            lines.append(f"{speaker}: {text}")
        return "\n".join(lines)
        
    def format_translation(self, segments: List[Dict[str, Any]]) -> str:
        """
        Format translation segments matching script format.
        
        Args:
            segments: List of segment dicts with 'speaker' and 'translation' fields
            
        Returns:
            Formatted translation string
        """
        lines = []
        for segment in segments:
            speaker = segment.get("speaker", "Unknown")
            translation = segment.get("translation", "")
            lines.append(f"{speaker}: {translation}")
        return "\n".join(lines)
        
    def push_conversation(
        self,
        content_id: Optional[str] = None,
        content_type: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        topic: Optional[str] = None,
        scenario: Optional[str] = None,
        segments: Optional[List[Dict[str, Any]]] = None,
        llm_evaluation: Optional[LLMJudgeEvaluation] = None,
        language: Optional[str] = None,
        level: Optional[str] = None,
        content_unit: Optional[Any] = None,  # ContentUnit object
    ) -> str:
        """
        Push conversation/story to Notion database.
        
        Can be called with either individual parameters OR a ContentUnit object.
        
        Args:
            content_id: Local content UUID
            content_type: "conversation" or "story"
            title: Content title
            description: Content description
            topic: Topic name (or comma-separated IDs if from ContentUnit)
            scenario: Scenario name (or comma-separated IDs if from ContentUnit)
            segments: List of segments with text/translation
            llm_evaluation: LLM judge evaluation result
            language: Language code
            level: Level code
            content_unit: ContentUnit object (alternative to individual params)
            
        Returns:
            Notion page ID
            
        Raises:
            Exception: If push fails after retries
        """
        # Support legacy positional call: push_conversation(content_unit)
        if content_unit is None and content_id is not None and not isinstance(content_id, str):
            content_unit = content_id
            content_id = None

        # If content_unit provided, extract all parameters from it
        if content_unit is not None:
            content_id = content_unit.id
            content_type = content_unit.type.value
            title = content_unit.title
            description = content_unit.description
            # Join topic_ids/scenario_ids as comma-separated strings
            topic = ", ".join(content_unit.topic_ids) if content_unit.topic_ids else ""
            scenario = ", ".join(content_unit.scenario_ids) if content_unit.scenario_ids else ""
            segments = [seg.model_dump() for seg in content_unit.segments]
            llm_evaluation = content_unit.llm_judge_evaluation
            language = content_unit.language
            level = content_unit.level_min  # Use min level as the primary level
        
        # Validate required parameters
        if not all([content_id, content_type, title, segments, language, level]):
            raise ValueError("Missing required parameters for push_conversation")
        
        # Format script and translation
        script = self.format_script(segments)
        translation = self.format_translation(segments)
        
        # Serialize LLM evaluation
        llm_comment = llm_evaluation.to_json_string() if llm_evaluation else ""
        
        # Build payload
        payload = {
            "Type": {"select": {"name": content_type}},
            "Title": {"title": [{"text": {"content": title}}]},
            "Description": {"rich_text": [{"text": {"content": description or ""}}]},
            "Topic": {"rich_text": [{"text": {"content": topic or ""}}]},
            "Scenario": {"rich_text": [{"text": {"content": scenario or ""}}]},
            "Script": {"rich_text": [{"text": {"content": script}}]},
            "Translation": {"rich_text": [{"text": {"content": translation}}]},
            "Audio": {"files": []},  # Empty until generated (files type, not url)
            "LLM Comment": {"rich_text": [{"text": {"content": llm_comment}}]},
            "Human Comment": {"rich_text": []},
            "Status": {"status": {"name": "Not started"}},  # status type, not select
        }
        
        # Retry with exponential backoff
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                # Get data source ID (API v2025-09-03 requires data_source_id parent)
                data_source_id = self._get_data_source_id()
                
                # Create page using REST API
                url = f"{self.NOTION_API_BASE}/pages"
                body = {
                    "parent": {
                        "type": "data_source_id",
                        "data_source_id": data_source_id
                    },
                    "properties": payload
                }
                response = requests.post(url, headers=self.headers, json=body)
                response.raise_for_status()
                result = response.json()
                notion_page_id = result["id"]
                logger.info(
                    f"Pushed content to Notion: {content_id} → {notion_page_id}"
                )
                return notion_page_id
                
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Push attempt {attempt + 1}/{self.MAX_RETRIES} failed: {last_error}"
                )
                
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_BASE_DELAY * (self.RETRY_MULTIPLIER ** attempt)
                    time.sleep(delay)
        
        # All retries failed, queue for later
        self._queue_failed_push(
            content_id=content_id,
            content_type=content_type,
            title=title,
            language=language,
            level=level,
            error=last_error,
            payload=payload
        )
        
        raise Exception(f"Failed to push content after {self.MAX_RETRIES} attempts: {last_error}")
        
    def _queue_failed_push(
        self,
        content_id: str,
        content_type: str,
        title: str,
        language: str,
        level: str,
        error: str,
        payload: Dict[str, Any]
    ) -> None:
        """
        Queue failed push for later retry.
        
        Args:
            content_id: Local content UUID
            content_type: "conversation" or "story"
            title: Content title
            language: Language code
            level: Level code
            error: Error message
            payload: Full Notion payload
        """
        queue_entry = NotionPushQueue(
            content_id=content_id,
            type=content_type,
            title=title,
            language=language,
            level=level,
            attempt_count=self.MAX_RETRIES,
            last_error=error,
            failed_at=datetime.now(),
            payload=payload
        )
        
        # Append to queue file (newline-delimited JSON)
        with open(self.queue_file, "a") as f:
            f.write(queue_entry.model_dump_json() + "\n")
            
        logger.error(f"Queued failed push: {content_id} ({title})")
        
    def fetch_status_changes(
        self,
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch pages with status changes from Notion.
        
        Args:
            since: Only fetch pages modified after this timestamp
            
        Returns:
            List of page data dicts with fields: notion_page_id, status,
            title, type, audio_url
        """
        try:
            # Build query body
            body: Dict[str, Any] = {}
            
            if since:
                body["filter"] = {
                    "timestamp": "last_edited_time",
                    "last_edited_time": {
                        "after": since.isoformat()
                    }
                }
            
            # Query data source using REST API (API v2025-09-03)
            data_source_id = self._get_data_source_id()
            url = f"{self.NOTION_API_BASE}/data_sources/{data_source_id}/query"
            response = requests.post(url, headers=self.headers, json=body)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            
            # Extract relevant fields
            pages = []
            for page in results:
                page_id = page["id"]
                props = page.get("properties", {})
                
                # Extract status (status type, not select)
                status_prop = props.get("Status", {}).get("status")
                status = status_prop.get("name") if status_prop else None
                
                title_prop = props.get("Title", {}).get("title", [])
                title = title_prop[0].get("text", {}).get("content", "") if title_prop else ""
                
                type_prop = props.get("Type", {}).get("select")
                content_type = type_prop.get("name") if type_prop else None
                
                # Audio is files type, extract first file URL if exists
                audio_files = props.get("Audio", {}).get("files", [])
                audio_url = audio_files[0].get("file", {}).get("url") if audio_files else None
                
                pages.append({
                    "notion_page_id": page_id,
                    "status": status,
                    "title": title,
                    "type": content_type,
                    "audio_url": audio_url,
                })
                
            logger.info(f"Fetched {len(pages)} pages from Notion")
            return pages
            
        except Exception as e:
            logger.error(f"Failed to fetch status changes: {str(e)}")
            raise
            
    def update_audio_field(
        self,
        notion_page_id: str,
        audio_url: str
    ) -> None:
        """
        Update Audio field in Notion page.
        
        Args:
            notion_page_id: Notion page ID
            audio_url: R2 audio URL
        """
        try:
            # Audio is files type, need to provide external file object
            url = f"{self.NOTION_API_BASE}/pages/{notion_page_id}"
            body = {
                "properties": {
                    "Audio": {
                        "files": [
                            {
                                "name": "audio.mp3",
                                "type": "external",
                                "external": {"url": audio_url}
                            }
                        ]
                    }
                }
            }
            response = requests.patch(url, headers=self.headers, json=body)
            response.raise_for_status()
            logger.info(f"Updated audio URL for {notion_page_id}")
            
        except Exception as e:
            logger.error(
                f"Failed to update audio field for {notion_page_id}: {str(e)}"
            )
            raise
            
    def update_status(
        self,
        notion_page_id: str,
        status: str
    ) -> None:
        """
        Update Status field in Notion page.
        
        Args:
            notion_page_id: Notion page ID
            status: New status value (must be in STATUS_VALUES)
        """
        if status not in self.STATUS_VALUES:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: {', '.join(self.STATUS_VALUES)}"
            )
            
        try:
            # Update status using REST API
            url = f"{self.NOTION_API_BASE}/pages/{notion_page_id}"
            body = {
                "properties": {
                    "Status": {"status": {"name": status}}  # status type, not select
                }
            }
            response = requests.patch(url, headers=self.headers, json=body)
            response.raise_for_status()
            logger.info(f"Updated status for {notion_page_id} to '{status}'")
            
        except Exception as e:
            logger.error(
                f"Failed to update status for {notion_page_id}: {str(e)}"
            )
            raise
