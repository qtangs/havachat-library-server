"""
Unit Tests for VoiceResolver

Tests voice resolution from Notion Voice Database with caching.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from src.havachat.integrations.notion_audio.voice_resolver import VoiceResolver


class TestVoiceResolver:
    """Test VoiceResolver voice lookup and caching."""
    
    def setup_method(self):
        """Create mock NotionClient and VoiceResolver."""
        self.mock_notion_client = Mock()
        self.mock_notion_client.NOTION_API_BASE = "https://api.notion.com/v1"
        self.mock_notion_client.headers = {"Authorization": "Bearer test"}
        
        self.voice_db_id = "303dd30aa93a8085b3a3dd5b10867276"
        self.default_voice_id = "default_voice_123"
        
        self.resolver = VoiceResolver(
            notion_client=self.mock_notion_client,
            voice_db_id=self.voice_db_id,
            default_voice_id=self.default_voice_id
        )
    
    def test_resolve_voice_with_cache(self):
        """Test voice resolution with cached result."""
        # Pre-populate cache
        voice_relation_id = "abc123"
        cached_voice_id = "cached_voice_456"
        self.resolver._cache[voice_relation_id] = cached_voice_id
        
        # Resolve should return cached value without API call
        result = self.resolver.resolve_voice(voice_relation_id)
        
        assert result == cached_voice_id
        # No API calls should be made
        assert len(self.mock_notion_client.method_calls) == 0
    
    def test_resolve_voice_with_api_call(self):
        """Test voice resolution with API call and caching."""
        voice_relation_id = "relation_abc"
        voice_id = "voice_xyz"
        
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "properties": {
                "Voice ID": {
                    "type": "rich_text",
                    "rich_text": [
                        {"plain_text": voice_id}
                    ]
                }
            }
        }
        
        with patch("requests.get", return_value=mock_response):
            result = self.resolver.resolve_voice(voice_relation_id)
        
        # Should return the voice ID
        assert result == voice_id
        
        # Should cache the result
        assert self.resolver._cache[voice_relation_id] == voice_id
    
    def test_fallback_to_default_empty_relation(self):
        """Test fallback to default when relation is empty."""
        result = self.resolver.resolve_voice(None)
        assert result == self.default_voice_id
        
        result = self.resolver.resolve_voice("")
        assert result == self.default_voice_id
    
    def test_fallback_to_default_api_error(self):
        """Test fallback to default when API call fails."""
        voice_relation_id = "failing_relation"
        
        # Mock failed API response
        with patch("requests.get", side_effect=Exception("API Error")):
            result = self.resolver.resolve_voice(voice_relation_id)
        
        # Should fallback to default
        assert result == self.default_voice_id
        
        # Should cache the fallback to avoid repeated failures
        assert self.resolver._cache[voice_relation_id] == self.default_voice_id
    
    def test_fallback_to_default_missing_property(self):
        """Test fallback when Voice ID property is missing."""
        voice_relation_id = "relation_missing_property"
        
        # Mock response without Voice ID property
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": "Some Voice"}]
                }
                # Missing "Voice ID" property
            }
        }
        
        with patch("requests.get", return_value=mock_response):
            result = self.resolver.resolve_voice(voice_relation_id)
        
        # Should fallback to default
        assert result == self.default_voice_id
    
    def test_clear_cache(self):
        """Test cache clearing."""
        # Populate cache
        self.resolver._cache["key1"] = "value1"
        self.resolver._cache["key2"] = "value2"
        
        assert len(self.resolver._cache) == 2
        
        # Clear cache
        self.resolver.clear_cache()
        
        assert len(self.resolver._cache) == 0
    
    def test_get_cache_stats(self):
        """Test cache statistics."""
        # Populate cache
        self.resolver._cache["relation1"] = "voice1"
        self.resolver._cache["relation2"] = "voice2"
        
        stats = self.resolver.get_cache_stats()
        
        assert stats["cache_size"] == 2
        assert "relation1" in stats["cached_voices"]
        assert "relation2" in stats["cached_voices"]
    
    def test_default_voice_getter(self):
        """Test _get_default_voice() method."""
        result = self.resolver._get_default_voice()
        assert result == self.default_voice_id
