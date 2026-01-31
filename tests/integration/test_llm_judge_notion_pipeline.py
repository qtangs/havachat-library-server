"""
Integration tests for LLM Judge and Notion pipeline.

Tests the complete workflow:
1. Generate conversation → LLM judge evaluation → push to Notion
2. Check Notion status changes → generate audio for approved items
3. Process rejected items → update local status → decrement usage stats
4. Audio regeneration by title → handle duplicates
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.models.llm_judge_evaluation import DimensionScore, LLMJudgeEvaluation
from src.pipeline.validators.llm_judge import LLMJudge
from src.pipeline.utils.notion_client import NotionClient
from src.pipeline.utils.notion_mapping_manager import NotionMappingManager
from havachat.cli.notion_sync import NotionSyncCLI


class TestLLMJudgeNotionPipeline:
    """Test suite for LLM judge and Notion integration pipeline."""
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            # Create language/level directory
            zh_hsk3 = data_dir / "zh" / "HSK3"
            zh_hsk3.mkdir(parents=True)
            
            # Create sample content file
            conversations = [
                {
                    "id": "conv-1",
                    "type": "conversation",
                    "title": "Ordering Food",
                    "description": "A conversation about ordering food",
                    "topic_name": "Food",
                    "scenario_name": "Restaurant Ordering",
                    "learning_item_ids": ["item-1", "item-2"],
                    "segments": [
                        {
                            "speaker": "Speaker-1",
                            "text": "你好！",
                            "translation": "Hello!"
                        }
                    ],
                    "status": "generated",
                    "created_at": "2026-01-31T10:00:00"
                }
            ]
            
            with open(zh_hsk3 / "conversations.json", "w") as f:
                json.dump(conversations, f)
                
            # Create usage stats file
            usage_stats = [
                {
                    "learning_item_id": "item-1",
                    "appearances_count": 5,
                    "last_used_content_id": "conv-1"
                },
                {
                    "learning_item_id": "item-2",
                    "appearances_count": 3,
                    "last_used_content_id": "conv-1"
                }
            ]
            
            with open(zh_hsk3 / "usage_stats.json", "w") as f:
                json.dump(usage_stats, f)
                
            yield data_dir
            
    @pytest.fixture
    def temp_mapping_file(self):
        """Create temporary mapping file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name
        yield temp_path
        Path(temp_path).unlink(missing_ok=True)
        
    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client."""
        client = Mock()
        client.generate.return_value = LLMJudgeEvaluation(
            content_id="conv-1",
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
            evaluator_model="gpt-4"
        )
        return client
        
    @pytest.fixture
    def mock_notion_client(self):
        """Create mock Notion client."""
        with patch("src.pipeline.utils.notion_client.Client") as mock:
            yield mock
            
    def test_end_to_end_generation_to_notion(
        self,
        mock_llm_client,
        mock_notion_client,
        temp_mapping_file
    ):
        """Test: generate conversation → LLM judge → push to Notion."""
        # Create LLM judge
        llm_judge = LLMJudge(llm_client=mock_llm_client)
        
        # Evaluate content
        evaluation = llm_judge.evaluate_conversation(
            content_id="conv-1",
            text="Speaker-1: 你好！\nSpeaker-2: 你好！最近怎么样？",
            language="zh",
            level="HSK3",
            content_type="conversation"
        )
        
        assert evaluation.content_id == "conv-1"
        assert evaluation.average_score() >= 7.0
        assert evaluation.overall_recommendation == "proceed"
        
        # Push to Notion
        mock_notion_client.return_value.pages.create.return_value = {
            "id": "notion-page-1"
        }
        
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
                "Status": {"type": "select"}
            }
        }
        
        notion_client = NotionClient(
            api_token="test-token",
            database_id="test-db"
        )
        
        notion_page_id = notion_client.push_conversation(
            content_id="conv-1",
            content_type="conversation",
            title="Ordering Food",
            description="A conversation about ordering food",
            topic="Food",
            scenario="Restaurant Ordering",
            segments=[
                {
                    "speaker": "Speaker-1",
                    "text": "你好！",
                    "translation": "Hello!"
                }
            ],
            llm_evaluation=evaluation,
            language="zh",
            level="HSK3"
        )
        
        assert notion_page_id == "notion-page-1"
        
        # Add mapping
        mapping_manager = NotionMappingManager(mapping_file=temp_mapping_file)
        mapping_manager.add_mapping(
            content_id="conv-1",
            notion_page_id=notion_page_id,
            language="zh",
            level="HSK3",
            content_type="conversation",
            title="Ordering Food"
        )
        
        # Verify mapping
        assert mapping_manager.get_notion_page_id("conv-1") == "notion-page-1"
        
    def test_notion_sync_ready_for_audio(
        self,
        mock_notion_client,
        temp_data_dir,
        temp_mapping_file
    ):
        """Test: Notion status → generate audio → update Notion."""
        # Setup mock Notion response
        mock_notion_client.return_value.databases.query.return_value = {
            "results": [
                {
                    "id": "notion-page-1",
                    "properties": {
                        "Status": {"select": {"name": "Ready for Audio"}},
                        "Title": {"title": [{"text": {"content": "Ordering Food"}}]},
                        "Type": {"select": {"name": "conversation"}},
                        "Audio": {"url": None}
                    }
                }
            ]
        }
        
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
        
        # Create mapping first
        mapping_manager = NotionMappingManager(mapping_file=temp_mapping_file)
        mapping_manager.add_mapping(
            content_id="conv-1",
            notion_page_id="notion-page-1",
            language="zh",
            level="HSK3",
            content_type="conversation",
            title="Ordering Food"
        )
        
        # Create sync CLI with mapping manager override
        sync_cli = NotionSyncCLI(
            notion_token="test-token",
            database_id="test-db",
            data_root=str(temp_data_dir)
        )
        sync_cli.mapping_manager = mapping_manager  # Override with our test mapping
        
        # Mock audio generation
        sync_cli._generate_audio = Mock(return_value="https://r2.example.com/audio.mp3")
        
        # Check Notion
        sync_cli.check_notion()
        
        # Verify audio generation was called
        sync_cli._generate_audio.assert_called_once()
        
    def test_notion_sync_rejected_item(
        self,
        mock_notion_client,
        temp_data_dir,
        temp_mapping_file
    ):
        """Test: rejected item → update local status → decrement usage stats."""
        # Setup mock Notion response
        mock_notion_client.return_value.databases.query.return_value = {
            "results": [
                {
                    "id": "notion-page-1",
                    "properties": {
                        "Status": {"select": {"name": "Rejected"}},
                        "Title": {"title": [{"text": {"content": "Ordering Food"}}]},
                        "Type": {"select": {"name": "conversation"}},
                        "Audio": {"url": None}
                    }
                }
            ]
        }
        
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
        
        # Create mapping
        mapping_manager = NotionMappingManager(mapping_file=temp_mapping_file)
        mapping_manager.add_mapping(
            content_id="conv-1",
            notion_page_id="notion-page-1",
            language="zh",
            level="HSK3",
            content_type="conversation",
            title="Ordering Food"
        )
        
        # Create sync CLI with mapping manager override
        sync_cli = NotionSyncCLI(
            notion_token="test-token",
            database_id="test-db",
            data_root=str(temp_data_dir)
        )
        sync_cli.mapping_manager = mapping_manager  # Override with our test mapping
        
        # Check Notion
        sync_cli.check_notion()
        
        # Verify local status updated
        conversations_file = temp_data_dir / "zh" / "HSK3" / "conversations.json"
        with open(conversations_file, "r") as f:
            conversations = json.load(f)
        assert conversations[0]["status"] == "rejected"
        
        # Verify usage stats decremented
        usage_stats_file = temp_data_dir / "zh" / "HSK3" / "usage_stats.json"
        with open(usage_stats_file, "r") as f:
            usage_stats = json.load(f)
        assert usage_stats[0]["appearances_count"] == 4  # Was 5, now 4
        assert usage_stats[1]["appearances_count"] == 2  # Was 3, now 2
        
    def test_audio_regeneration_by_title(
        self,
        mock_notion_client,
        temp_data_dir,
        temp_mapping_file
    ):
        """Test: regenerate audio by title → handle duplicates."""
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
        
        # Create mapping
        mapping_manager = NotionMappingManager(mapping_file=temp_mapping_file)
        mapping_manager.add_mapping(
            content_id="conv-1",
            notion_page_id="notion-page-1",
            language="zh",
            level="HSK3",
            content_type="conversation",
            title="Ordering Food"
        )
        
        # Create sync CLI with mapping manager override
        sync_cli = NotionSyncCLI(
            notion_token="test-token",
            database_id="test-db",
            data_root=str(temp_data_dir)
        )
        sync_cli.mapping_manager = mapping_manager  # Override with our test mapping
        
        # Mock audio generation
        sync_cli._generate_audio = Mock(return_value="https://r2.example.com/audio-new.mp3")
        
        # Regenerate audio
        sync_cli.regenerate_audio(title="Ordering Food", language="zh", level="HSK3")
        
        # Verify audio generation was called
        sync_cli._generate_audio.assert_called_once()
        
    def test_notion_schema_validation(self, mock_notion_client):
        """Test: detect missing/mismatched columns."""
        # Mock database with missing column
        mock_notion_client.return_value.databases.retrieve.return_value = {
            "properties": {
                "Type": {"type": "select"},
                "Title": {"type": "title"},
                # Missing "Audio" column
                "Description": {"type": "rich_text"},
                "Topic": {"type": "rich_text"},
                "Scenario": {"type": "rich_text"},
                "Script": {"type": "rich_text"},
                "Translation": {"type": "rich_text"},
                "LLM Comment": {"type": "rich_text"},
                "Human Comment": {"type": "rich_text"},
                "Status": {"type": "select"}
            }
        }
        
        from src.pipeline.utils.notion_client import NotionSchemaError
        
        with pytest.raises(NotionSchemaError, match="Missing columns: Audio"):
            notion_client = NotionClient(
                api_token="test-token",
                database_id="test-db"
            )
            notion_client.validate_database_schema()
            
    def test_notion_type_mismatch(self, mock_notion_client):
        """Test: detect column type mismatch."""
        # Mock database with wrong type for Status
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
        
        from src.pipeline.utils.notion_client import NotionSchemaError
        
        with pytest.raises(NotionSchemaError, match="Type mismatches: Status"):
            notion_client = NotionClient(
                api_token="test-token",
                database_id="test-db"
            )
            notion_client.validate_database_schema()
