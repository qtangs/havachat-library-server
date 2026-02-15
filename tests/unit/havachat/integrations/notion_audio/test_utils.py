"""
Unit Tests for Notion Audio Content Processor Utilities

Tests filename sanitization, path construction, and content hash utilities.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from src.havachat.integrations.notion_audio.utils import (
    sanitize_filename,
    get_audio_storage_path,
    compute_content_hash,
    save_content_hash,
    load_content_hash,
    should_regenerate_audio
)


class TestFilenameSanitization:
    """Test filename sanitization for filesystem compatibility."""
    
    def test_sanitize_basic(self):
        """Test basic filename sanitization."""
        assert sanitize_filename("hello.mp3") == "hello.mp3"
        assert sanitize_filename("Test File 123") == "Test File 123"
    
    def test_sanitize_invalid_chars(self):
        """Test removal of invalid filesystem characters."""
        assert sanitize_filename("hello/world") == "hello-world"
        assert sanitize_filename("test:example") == "test-example"
        assert sanitize_filename("file\\ name") == "file- name"
        assert sanitize_filename("test<>:\"| ?*") == "test----- --"  # Space is valid
    
    def test_sanitize_unicode(self):
        """Test Unicode normalization."""
        # Combining diacritics normalized to composed form
        assert sanitize_filename("café") == "café"
        assert sanitize_filename("日本語") == "日本語"
        assert sanitize_filename("中文测试") == "中文测试"
    
    def test_sanitize_dots_and_spaces(self):
        """Test stripping of leading/trailing dots and spaces."""
        assert sanitize_filename("  .hidden.txt  ") == "hidden.txt"
        assert sanitize_filename("...test...") == "test"  # Trailing dots stripped
        assert sanitize_filename("   spaces   ") == "spaces"
    
    def test_sanitize_control_chars(self):
        """Test removal of control characters."""
        # ASCII control characters should be removed
        assert sanitize_filename("test\x00file") == "testfile"
        assert sanitize_filename("hello\x1fworld") == "helloworld"
    
    def test_sanitize_max_length(self):
        """Test truncation to max length."""
        long_name = "a" * 300
        result = sanitize_filename(long_name, max_length=255)
        assert len(result.encode('utf-8')) <= 255
    
    def test_sanitize_empty_fallback(self):
        """Test fallback for empty filenames."""
        assert sanitize_filename("") == "untitled"
        assert sanitize_filename("   ") == "untitled"
        assert sanitize_filename("...") == "untitled"


class TestAudioStoragePath:
    """Test audio file path construction."""
    
    def setup_method(self):
        """Create temporary directory for testing."""
        self.temp_dir = Path(tempfile.mkdtemp())
    
    def teardown_method(self):
        """Clean up temporary directory."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_basic_path_construction(self):
        """Test basic path construction."""
        path = get_audio_storage_path(
            self.temp_dir,
            "Education",
            "Grammar",
            "abc123",
            "Present Tense"
        )
        
        assert path == self.temp_dir / "Education" / "Grammar" / "abc123-Present Tense.mp3"
        assert path.parent.exists()  # Directory should be created
    
    def test_path_with_special_chars(self):
        """Test path construction with special characters."""
        path = get_audio_storage_path(
            self.temp_dir,
            "Topic: A",
            "Sub/Type",
            "def456",
            "Test: File?"
        )
        
        # Special chars should be sanitized
        assert "Topic- A" in str(path)
        assert "Sub-Type" in str(path)
        assert "Test- File-" in str(path)
    
    def test_custom_extension(self):
        """Test custom file extension."""
        path = get_audio_storage_path(
            self.temp_dir,
            "Audio",
            "Test",
            "xyz789",
            "file",
            extension="wav"
        )
        
        assert path.suffix == ".wav"


class TestContentHash:
    """Test content hash utilities for duplicate detection."""
    
    def test_compute_hash_deterministic(self):
        """Test that hash is deterministic."""
        content = "Hello, world!"
        hash1 = compute_content_hash(content)
        hash2 = compute_content_hash(content)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length
    
    def test_compute_hash_different_content(self):
        """Test that different content produces different hashes."""
        hash1 = compute_content_hash("Content A")
        hash2 = compute_content_hash("Content B")
        
        assert hash1 != hash2
    
    def test_save_and_load_hash(self):
        """Test saving and loading hash from sidecar file."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            audio_path = Path(f.name)
        
        try:
            test_hash = "abc123def456"
            save_content_hash(audio_path, test_hash)
            
            loaded_hash = load_content_hash(audio_path)
            assert loaded_hash == test_hash
            
            # Check that hash file exists
            hash_path = Path(str(audio_path) + ".hash")
            assert hash_path.exists()
        finally:
            audio_path.unlink(missing_ok=True)
            Path(str(audio_path) + ".hash").unlink(missing_ok=True)
    
    def test_load_hash_missing_file(self):
        """Test loading hash when file doesn't exist."""
        audio_path = Path("/nonexistent/audio.mp3")
        assert load_content_hash(audio_path) is None


class TestShouldRegenerateAudio:
    """Test duplicate detection logic."""
    
    def test_regenerate_missing_audio(self):
        """Test regeneration when audio file is missing."""
        audio_path = Path("/nonexistent/audio.mp3")
        assert should_regenerate_audio(audio_path, "Some content") is True
    
    def test_regenerate_missing_hash(self):
        """Test regeneration when hash file is missing."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            audio_path = Path(f.name)
        
        try:
            # Audio exists but hash doesn't
            assert should_regenerate_audio(audio_path, "Content") is True
        finally:
            audio_path.unlink(missing_ok=True)
    
    def test_skip_unchanged_content(self):
        """Test skipping when content hasn't changed."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            audio_path = Path(f.name)
        
        try:
            content = "Test content"
            content_hash = compute_content_hash(content)
            save_content_hash(audio_path, content_hash)
            
            # Same content → should skip
            assert should_regenerate_audio(audio_path, content) is False
        finally:
            audio_path.unlink(missing_ok=True)
            Path(str(audio_path) + ".hash").unlink(missing_ok=True)
    
    def test_regenerate_changed_content(self):
        """Test regeneration when content has changed."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            audio_path = Path(f.name)
        
        try:
            old_content = "Old content"
            old_hash = compute_content_hash(old_content)
            save_content_hash(audio_path, old_hash)
            
            # Different content → should regenerate
            new_content = "New content"
            assert should_regenerate_audio(audio_path, new_content) is True
        finally:
            audio_path.unlink(missing_ok=True)
            Path(str(audio_path) + ".hash").unlink(missing_ok=True)
