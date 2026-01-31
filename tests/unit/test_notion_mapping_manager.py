"""
Unit tests for NotionMappingManager.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from src.models.notion_mapping import NotionMapping
from src.pipeline.utils.notion_mapping_manager import NotionMappingManager


class TestNotionMappingManager:
    """Test suite for NotionMappingManager."""
    
    @pytest.fixture
    def temp_mapping_file(self):
        """Create temporary mapping file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name
        yield temp_path
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)
        
    @pytest.fixture
    def mapping_manager(self, temp_mapping_file):
        """Create NotionMappingManager with temp file."""
        return NotionMappingManager(mapping_file=temp_mapping_file)
        
    @pytest.fixture
    def sample_mappings(self):
        """Create sample mapping data."""
        return [
            {
                "content_id": "content-1",
                "notion_page_id": "page-1",
                "language": "zh",
                "level": "HSK3",
                "type": "conversation",
                "title": "Ordering Food",
                "last_pushed_at": "2026-01-31T10:00:00",
                "last_synced_at": "2026-01-31T10:30:00",
                "status_in_notion": "Ready for Audio",
                "status_in_local": "generated"
            },
            {
                "content_id": "content-2",
                "notion_page_id": "page-2",
                "language": "ja",
                "level": "N5",
                "type": "story",
                "title": "Going to School",
                "last_pushed_at": "2026-01-31T11:00:00",
                "last_synced_at": "2026-01-31T11:30:00",
                "status_in_notion": "Rejected",
                "status_in_local": "rejected"
            }
        ]
        
    def test_initialization_empty_file(self, mapping_manager):
        """Test initialization with no existing file."""
        assert len(mapping_manager._mappings) == 0
        
    def test_load_mapping_success(self, temp_mapping_file, sample_mappings):
        """Test loading existing mappings."""
        # Write sample data to file
        with open(temp_mapping_file, "w") as f:
            json.dump(sample_mappings, f)
            
        # Load mappings
        manager = NotionMappingManager(mapping_file=temp_mapping_file)
        
        assert len(manager._mappings) == 2
        assert "content-1" in manager._mappings
        assert manager._mappings["content-1"].notion_page_id == "page-1"
        
    def test_load_mapping_invalid_json(self, temp_mapping_file):
        """Test handling of invalid JSON."""
        # Write invalid JSON
        with open(temp_mapping_file, "w") as f:
            f.write("{invalid json")
            
        # Should not crash, just start with empty mappings
        manager = NotionMappingManager(mapping_file=temp_mapping_file)
        assert len(manager._mappings) == 0
        
    def test_save_mapping(self, mapping_manager, temp_mapping_file):
        """Test saving mappings to file."""
        # Add a mapping
        mapping_manager.add_mapping(
            content_id="test-content",
            notion_page_id="test-page",
            language="zh",
            level="HSK3",
            content_type="conversation",
            title="Test Title"
        )
        
        # Read file and verify
        with open(temp_mapping_file, "r") as f:
            data = json.load(f)
            
        assert len(data) == 1
        assert data[0]["content_id"] == "test-content"
        assert data[0]["notion_page_id"] == "test-page"
        
    def test_add_mapping(self, mapping_manager):
        """Test adding new mapping."""
        result = mapping_manager.add_mapping(
            content_id="content-123",
            notion_page_id="page-456",
            language="fr",
            level="A2",
            content_type="story",
            title="A French Story"
        )
        
        assert isinstance(result, NotionMapping)
        assert result.content_id == "content-123"
        assert result.notion_page_id == "page-456"
        assert result.language == "fr"
        assert result.title == "A French Story"
        
        # Verify it's in the mappings
        assert "content-123" in mapping_manager._mappings
        
    def test_get_notion_page_id_success(self, mapping_manager):
        """Test getting Notion page ID."""
        mapping_manager.add_mapping(
            content_id="content-123",
            notion_page_id="page-456",
            language="zh",
            level="HSK3",
            content_type="conversation",
            title="Test"
        )
        
        result = mapping_manager.get_notion_page_id("content-123")
        assert result == "page-456"
        
    def test_get_notion_page_id_not_found(self, mapping_manager):
        """Test getting Notion page ID for non-existent content."""
        result = mapping_manager.get_notion_page_id("non-existent")
        assert result is None
        
    def test_get_content_id(self, mapping_manager):
        """Test reverse lookup: Notion page ID → content ID."""
        mapping_manager.add_mapping(
            content_id="content-123",
            notion_page_id="page-456",
            language="zh",
            level="HSK3",
            content_type="conversation",
            title="Test"
        )
        
        result = mapping_manager.get_content_id("page-456")
        assert result == "content-123"
        
    def test_get_content_id_not_found(self, mapping_manager):
        """Test reverse lookup for non-existent page."""
        result = mapping_manager.get_content_id("non-existent")
        assert result is None
        
    def test_get_mapping(self, mapping_manager):
        """Test getting full mapping object."""
        mapping_manager.add_mapping(
            content_id="content-123",
            notion_page_id="page-456",
            language="zh",
            level="HSK3",
            content_type="conversation",
            title="Test"
        )
        
        result = mapping_manager.get_mapping("content-123")
        assert isinstance(result, NotionMapping)
        assert result.content_id == "content-123"
        
    def test_update_sync_status(self, mapping_manager):
        """Test updating sync status."""
        mapping_manager.add_mapping(
            content_id="content-123",
            notion_page_id="page-456",
            language="zh",
            level="HSK3",
            content_type="conversation",
            title="Test"
        )
        
        # Update status
        mapping_manager.update_sync_status(
            content_id="content-123",
            status_in_notion="OK",
            status_in_local="published"
        )
        
        # Verify updates
        mapping = mapping_manager.get_mapping("content-123")
        assert mapping.status_in_notion == "OK"
        assert mapping.status_in_local == "published"
        
    def test_update_sync_status_partial(self, mapping_manager):
        """Test updating only one status field."""
        mapping_manager.add_mapping(
            content_id="content-123",
            notion_page_id="page-456",
            language="zh",
            level="HSK3",
            content_type="conversation",
            title="Test"
        )
        
        original_mapping = mapping_manager.get_mapping("content-123")
        original_local_status = original_mapping.status_in_local
        
        # Update only Notion status
        mapping_manager.update_sync_status(
            content_id="content-123",
            status_in_notion="Reviewing"
        )
        
        # Verify only Notion status changed
        mapping = mapping_manager.get_mapping("content-123")
        assert mapping.status_in_notion == "Reviewing"
        assert mapping.status_in_local == original_local_status
        
    def test_find_by_title_exact(self, mapping_manager):
        """Test finding mappings by exact title."""
        mapping_manager.add_mapping(
            content_id="content-1",
            notion_page_id="page-1",
            language="zh",
            level="HSK3",
            content_type="conversation",
            title="Ordering Food"
        )
        mapping_manager.add_mapping(
            content_id="content-2",
            notion_page_id="page-2",
            language="zh",
            level="HSK3",
            content_type="conversation",
            title="Shopping"
        )
        
        results = mapping_manager.find_by_title("Ordering Food")
        assert len(results) == 1
        assert results[0].content_id == "content-1"
        
    def test_find_by_title_partial(self, mapping_manager):
        """Test finding mappings by partial title."""
        mapping_manager.add_mapping(
            content_id="content-1",
            notion_page_id="page-1",
            language="zh",
            level="HSK3",
            content_type="conversation",
            title="Ordering Food at Restaurant"
        )
        
        results = mapping_manager.find_by_title("ordering")
        assert len(results) == 1
        
    def test_find_by_title_with_filters(self, mapping_manager):
        """Test finding with language/level filters."""
        mapping_manager.add_mapping(
            content_id="content-1",
            notion_page_id="page-1",
            language="zh",
            level="HSK3",
            content_type="conversation",
            title="Food"
        )
        mapping_manager.add_mapping(
            content_id="content-2",
            notion_page_id="page-2",
            language="ja",
            level="N5",
            content_type="conversation",
            title="Food"
        )
        
        results = mapping_manager.find_by_title("Food", language="zh")
        assert len(results) == 1
        assert results[0].language == "zh"
        
    def test_get_all_mappings(self, mapping_manager):
        """Test getting all mappings."""
        mapping_manager.add_mapping(
            content_id="content-1",
            notion_page_id="page-1",
            language="zh",
            level="HSK3",
            content_type="conversation",
            title="Test 1"
        )
        mapping_manager.add_mapping(
            content_id="content-2",
            notion_page_id="page-2",
            language="ja",
            level="N5",
            content_type="story",
            title="Test 2"
        )
        
        results = mapping_manager.get_all_mappings()
        assert len(results) == 2
        
    def test_delete_mapping(self, mapping_manager):
        """Test deleting a mapping."""
        mapping_manager.add_mapping(
            content_id="content-123",
            notion_page_id="page-456",
            language="zh",
            level="HSK3",
            content_type="conversation",
            title="Test"
        )
        
        # Delete
        result = mapping_manager.delete_mapping("content-123")
        assert result is True
        assert "content-123" not in mapping_manager._mappings
        
    def test_delete_mapping_not_found(self, mapping_manager):
        """Test deleting non-existent mapping."""
        result = mapping_manager.delete_mapping("non-existent")
        assert result is False
        
    def test_get_stats(self, mapping_manager):
        """Test getting statistics."""
        mapping_manager.add_mapping(
            content_id="content-1",
            notion_page_id="page-1",
            language="zh",
            level="HSK3",
            content_type="conversation",
            title="Test 1",
            status_in_notion="Ready for Audio",
            status_in_local="generated"
        )
        mapping_manager.add_mapping(
            content_id="content-2",
            notion_page_id="page-2",
            language="ja",
            level="N5",
            content_type="story",
            title="Test 2",
            status_in_notion="OK",
            status_in_local="published"
        )
        
        stats = mapping_manager.get_stats()
        
        assert stats["total"] == 2
        assert stats["by_notion_status"]["Ready for Audio"] == 1
        assert stats["by_notion_status"]["OK"] == 1
        assert stats["by_local_status"]["generated"] == 1
        assert stats["by_local_status"]["published"] == 1
        assert stats["by_language"]["zh"] == 1
        assert stats["by_language"]["ja"] == 1
        assert stats["by_type"]["conversation"] == 1
        assert stats["by_type"]["story"] == 1
