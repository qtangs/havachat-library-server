"""
Unit tests for NotionClient.
"""

import json
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch, mock_open

import pytest

from src.models.llm_judge_evaluation import DimensionScore, LLMJudgeEvaluation
from src.pipeline.utils.notion_client import NotionClient, NotionSchemaError


class TestNotionClient:
    """Test suite for NotionClient."""
    
    @pytest.fixture
    def mock_notion_client(self):
        """Create mock Notion client."""
        with patch("src.pipeline.utils.notion_client.Client") as mock_client:
            yield mock_client
            
    @pytest.fixture
    def notion_client(self, mock_notion_client):
        """Create NotionClient instance with mocked dependencies."""
        return NotionClient(
            api_token="test-token",
            database_id="test-db-id",
            queue_file="test_queue.jsonl"
        )
        
    @pytest.fixture
    def sample_llm_evaluation(self):
        """Create sample LLM evaluation."""
        return LLMJudgeEvaluation(
            content_id="test-content-123",
            content_type="conversation",
            naturalness=DimensionScore(score=8, explanation="Natural dialogue flow observed"),
            level_appropriateness=DimensionScore(score=9, explanation="Perfect for HSK3 level"),
            grammatical_correctness=DimensionScore(score=10, explanation="No grammar errors detected"),
            vocabulary_diversity=DimensionScore(score=7, explanation="Good variety of words used"),
            cultural_accuracy=DimensionScore(score=8, explanation="Culturally appropriate context"),
            engagement=DimensionScore(score=7, explanation="Moderately engaging content"),
            overall_recommendation="proceed",
            recommendation_justification="High quality content suitable for publication",
            evaluated_at=datetime(2026, 1, 31, 12, 0, 0),
            evaluator_model="gpt-4",
            has_inconsistency=False,
            inconsistency_note=None
        )
        
    @pytest.fixture
    def sample_segments(self):
        """Create sample conversation segments."""
        return [
            {
                "speaker": "Speaker-1",
                "text": "你好！",
                "translation": "Hello!"
            },
            {
                "speaker": "Speaker-2",
                "text": "你好！最近怎么样？",
                "translation": "Hello! How have you been recently?"
            }
        ]
        
    def test_initialization(self, notion_client):
        """Test NotionClient initialization."""
        assert notion_client.database_id == "test-db-id"
        assert notion_client.queue_file == "test_queue.jsonl"
        assert notion_client.MAX_RETRIES == 3
        
    def test_validate_schema_success(self, notion_client, mock_notion_client):
        """Test successful schema validation."""
        # Mock database response with correct schema
        mock_notion_client.return_value.databases.retrieve.return_value = {
            "properties": {
                "Type": {"type": "select"},
                "Title": {"type": "title"},
                "Description": {"type": "rich_text"},
                "Topic": {"type": "rich_text"},
                "Scenario": {"type": "rich_text"},
                "Script": {"type": "rich_text"},
                "Translation": {"type": "rich_text"},
                "Audio": {"type": "url"},
                "LLM Comment": {"type": "rich_text"},
                "Human Comment": {"type": "rich_text"},
                "Status": {
                    "type": "select",
                    "select": {
                        "options": [
                            {"name": "Not started"},
                            {"name": "Ready for Review"},
                            {"name": "Reviewing"},
                            {"name": "Ready for Audio"},
                            {"name": "Rejected"},
                            {"name": "OK"}
                        ]
                    }
                }
            }
        }
        
        # Should not raise
        notion_client.validate_database_schema()
        
    def test_validate_schema_missing_column(self, notion_client, mock_notion_client):
        """Test schema validation with missing column."""
        # Mock database response missing "Audio" column
        mock_notion_client.return_value.databases.retrieve.return_value = {
            "properties": {
                "Type": {"type": "select"},
                "Title": {"type": "title"},
                "Description": {"type": "rich_text"},
                "Topic": {"type": "rich_text"},
                "Scenario": {"type": "rich_text"},
                "Script": {"type": "rich_text"},
                "Translation": {"type": "rich_text"},
                # "Audio" missing
                "LLM Comment": {"type": "rich_text"},
                "Human Comment": {"type": "rich_text"},
                "Status": {"type": "select"}
            }
        }
        
        with pytest.raises(NotionSchemaError, match="Missing columns: Audio"):
            notion_client.validate_database_schema()
            
    def test_validate_schema_type_mismatch(self, notion_client, mock_notion_client):
        """Test schema validation with type mismatch."""
        # Mock database response with wrong type for "Status"
        mock_notion_client.return_value.databases.retrieve.return_value = {
            "properties": {
                "Type": {"type": "select"},
                "Title": {"type": "title"},
                "Description": {"type": "rich_text"},
                "Topic": {"type": "rich_text"},
                "Scenario": {"type": "rich_text"},
                "Script": {"type": "rich_text"},
                "Translation": {"type": "rich_text"},
                "Audio": {"type": "url"},
                "LLM Comment": {"type": "rich_text"},
                "Human Comment": {"type": "rich_text"},
                "Status": {"type": "rich_text"}  # Should be "select"
            }
        }
        
        with pytest.raises(NotionSchemaError, match="Type mismatches: Status"):
            notion_client.validate_database_schema()
            
    def test_format_script(self, notion_client, sample_segments):
        """Test script formatting."""
        result = notion_client.format_script(sample_segments)
        expected = "Speaker-1: 你好！\nSpeaker-2: 你好！最近怎么样？"
        assert result == expected
        
    def test_format_translation(self, notion_client, sample_segments):
        """Test translation formatting."""
        result = notion_client.format_translation(sample_segments)
        expected = "Speaker-1: Hello!\nSpeaker-2: Hello! How have you been recently?"
        assert result == expected
        
    def test_push_conversation_success(
        self,
        notion_client,
        mock_notion_client,
        sample_llm_evaluation,
        sample_segments
    ):
        """Test successful conversation push."""
        # Mock successful API response
        mock_notion_client.return_value.pages.create.return_value = {
            "id": "notion-page-123"
        }
        
        result = notion_client.push_conversation(
            content_id="test-content-123",
            content_type="conversation",
            title="Test Conversation",
            description="A test conversation",
            topic="greetings",
            scenario="casual meeting",
            segments=sample_segments,
            llm_evaluation=sample_llm_evaluation,
            language="zh",
            level="HSK3"
        )
        
        assert result == "notion-page-123"
        
        # Verify API call
        mock_notion_client.return_value.pages.create.assert_called_once()
        call_args = mock_notion_client.return_value.pages.create.call_args
        assert call_args[1]["parent"]["database_id"] == "test-db-id"
        assert call_args[1]["properties"]["Title"]["title"][0]["text"]["content"] == "Test Conversation"
        
    def test_push_conversation_retry_success(
        self,
        notion_client,
        mock_notion_client,
        sample_llm_evaluation,
        sample_segments
    ):
        """Test push with retry success."""
        # Mock first attempt fails, second succeeds
        mock_notion_client.return_value.pages.create.side_effect = [
            Exception("API error"),
            {"id": "notion-page-123"}
        ]
        
        with patch("time.sleep"):  # Skip actual sleep
            result = notion_client.push_conversation(
                content_id="test-content-123",
                content_type="conversation",
                title="Test Conversation",
                description="A test conversation",
                topic="greetings",
                scenario="casual meeting",
                segments=sample_segments,
                llm_evaluation=sample_llm_evaluation,
                language="zh",
                level="HSK3"
            )
            
        assert result == "notion-page-123"
        assert mock_notion_client.return_value.pages.create.call_count == 2
        
    def test_push_conversation_all_retries_fail(
        self,
        notion_client,
        mock_notion_client,
        sample_llm_evaluation,
        sample_segments
    ):
        """Test push failure after all retries."""
        # Mock all attempts fail
        mock_notion_client.return_value.pages.create.side_effect = Exception("API error")
        
        with patch("time.sleep"), \
             patch("builtins.open", mock_open()) as mock_file:
            with pytest.raises(Exception, match="Failed to push content after 3 attempts"):
                notion_client.push_conversation(
                    content_id="test-content-123",
                    content_type="conversation",
                    title="Test Conversation",
                    description="A test conversation",
                    topic="greetings",
                    scenario="casual meeting",
                    segments=sample_segments,
                    llm_evaluation=sample_llm_evaluation,
                    language="zh",
                    level="HSK3"
                )
                
        # Verify queue file was written
        mock_file.assert_called_with("test_queue.jsonl", "a")
        
    def test_fetch_status_changes(self, notion_client, mock_notion_client):
        """Test fetching status changes from Notion."""
        # Mock database query response
        mock_notion_client.return_value.databases.query.return_value = {
            "results": [
                {
                    "id": "page-1",
                    "properties": {
                        "Status": {"select": {"name": "Ready for Audio"}},
                        "Title": {"title": [{"text": {"content": "Test 1"}}]},
                        "Type": {"select": {"name": "conversation"}},
                        "Audio": {"url": None}
                    }
                },
                {
                    "id": "page-2",
                    "properties": {
                        "Status": {"select": {"name": "Rejected"}},
                        "Title": {"title": [{"text": {"content": "Test 2"}}]},
                        "Type": {"select": {"name": "story"}},
                        "Audio": {"url": "https://r2.example.com/audio.mp3"}
                    }
                }
            ]
        }
        
        results = notion_client.fetch_status_changes()
        
        assert len(results) == 2
        assert results[0]["notion_page_id"] == "page-1"
        assert results[0]["status"] == "Ready for Audio"
        assert results[0]["title"] == "Test 1"
        assert results[1]["notion_page_id"] == "page-2"
        assert results[1]["status"] == "Rejected"
        
    def test_fetch_status_changes_with_since_filter(
        self,
        notion_client,
        mock_notion_client
    ):
        """Test fetching status changes with timestamp filter."""
        since = datetime(2026, 1, 31, 10, 0, 0)
        
        mock_notion_client.return_value.databases.query.return_value = {
            "results": []
        }
        
        notion_client.fetch_status_changes(since=since)
        
        # Verify filter was applied
        call_args = mock_notion_client.return_value.databases.query.call_args
        assert "filter" in call_args[1]
        assert call_args[1]["filter"]["last_edited_time"]["after"] == since.isoformat()
        
    def test_update_audio_field(self, notion_client, mock_notion_client):
        """Test updating audio field."""
        notion_client.update_audio_field(
            notion_page_id="page-1",
            audio_url="https://r2.example.com/audio.mp3"
        )
        
        mock_notion_client.return_value.pages.update.assert_called_once_with(
            page_id="page-1",
            properties={"Audio": {"url": "https://r2.example.com/audio.mp3"}}
        )
        
    def test_update_status(self, notion_client, mock_notion_client):
        """Test updating status field."""
        notion_client.update_status(
            notion_page_id="page-1",
            status="OK"
        )
        
        mock_notion_client.return_value.pages.update.assert_called_once_with(
            page_id="page-1",
            properties={"Status": {"select": {"name": "OK"}}}
        )
        
    def test_update_status_invalid_value(self, notion_client):
        """Test updating status with invalid value."""
        with pytest.raises(ValueError, match="Invalid status"):
            notion_client.update_status(
                notion_page_id="page-1",
                status="Invalid Status"
            )
