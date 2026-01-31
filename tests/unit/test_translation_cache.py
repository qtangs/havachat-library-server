"""Unit tests for translation cache functionality."""

import json
import tempfile
import time
from pathlib import Path

import pytest

from havachat.utils.translation_cache import TranslationCache


@pytest.fixture
def temp_cache_dir():
    """Create temporary cache directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def cache(temp_cache_dir):
    """Create cache instance for testing."""
    return TranslationCache(cache_dir=temp_cache_dir, ttl_days=1, enabled=True)


def test_cache_initialization(temp_cache_dir):
    """Test cache initialization creates directory."""
    cache = TranslationCache(cache_dir=temp_cache_dir, enabled=True)
    
    assert cache.cache_dir.exists()
    assert cache.enabled is True
    assert cache.ttl_days == TranslationCache.DEFAULT_TTL_DAYS


def test_cache_disabled():
    """Test cache operations when disabled."""
    cache = TranslationCache(enabled=False)
    
    # Set should do nothing
    cache.set("test", "translation", "zh", "en", "azure")
    
    # Get should return None
    result = cache.get("test", "zh", "en", "azure")
    assert result is None
    
    # Batch get should return all None
    results, missing = cache.get_batch(["test1", "test2"], "zh", "en", "azure")
    assert all(r is None for r in results)
    assert missing == [0, 1]


def test_cache_set_and_get(cache):
    """Test basic cache set and get operations."""
    text = "你好"
    translation = "Hello"
    
    cache.set(text, translation, "zh", "en", "azure")
    result = cache.get(text, "zh", "en", "azure")
    
    assert result == translation


def test_cache_key_uniqueness(cache):
    """Test cache keys are unique for different parameters."""
    text = "你好"
    translation_en = "Hello"
    translation_fr = "Bonjour"
    
    # Same text, different target language
    cache.set(text, translation_en, "zh", "en", "azure")
    cache.set(text, translation_fr, "zh", "fr", "azure")
    
    result_en = cache.get(text, "zh", "en", "azure")
    result_fr = cache.get(text, "zh", "fr", "azure")
    
    assert result_en == translation_en
    assert result_fr == translation_fr


def test_cache_service_isolation(cache):
    """Test different services have separate cache entries."""
    text = "你好"
    azure_translation = "Hello (Azure)"
    google_translation = "Hello (Google)"
    
    cache.set(text, azure_translation, "zh", "en", "azure")
    cache.set(text, google_translation, "zh", "en", "google")
    
    azure_result = cache.get(text, "zh", "en", "azure")
    google_result = cache.get(text, "zh", "en", "google")
    
    assert azure_result == azure_translation
    assert google_result == google_translation


def test_cache_batch_operations(cache):
    """Test batch cache operations."""
    texts = ["你好", "谢谢", "再见"]
    translations = ["Hello", "Thank you", "Goodbye"]
    
    # Set batch
    cache.set_batch(texts, translations, "zh", "en", "azure")
    
    # Get batch - all should be cached
    results, missing = cache.get_batch(texts, "zh", "en", "azure")
    
    assert results == translations
    assert missing == []


def test_cache_partial_batch_hit(cache):
    """Test batch operations with partial cache hits."""
    texts = ["你好", "谢谢", "再见"]
    
    # Cache only first two
    cache.set("你好", "Hello", "zh", "en", "azure")
    cache.set("谢谢", "Thank you", "zh", "en", "azure")
    
    # Get batch - third should miss
    results, missing = cache.get_batch(texts, "zh", "en", "azure")
    
    assert results[0] == "Hello"
    assert results[1] == "Thank you"
    assert results[2] is None
    assert missing == [2]


def test_cache_expiration(temp_cache_dir):
    """Test cache entries expire after TTL."""
    # Create cache with 1 second TTL
    cache = TranslationCache(cache_dir=temp_cache_dir, ttl_days=1/(24*60*60), enabled=True)
    
    text = "你好"
    translation = "Hello"
    
    cache.set(text, translation, "zh", "en", "azure")
    
    # Should be available immediately
    result = cache.get(text, "zh", "en", "azure")
    assert result == translation
    
    # Wait for expiration
    time.sleep(1.1)
    
    # Should be expired
    result = cache.get(text, "zh", "en", "azure")
    assert result is None


def test_cache_persistence(temp_cache_dir):
    """Test cache persists across instances."""
    text = "你好"
    translation = "Hello"
    
    # Create cache and store value
    cache1 = TranslationCache(cache_dir=temp_cache_dir, enabled=True)
    cache1.set(text, translation, "zh", "en", "azure")
    cache1._save_cache_for_language_pair("zh", "en")
    
    # Create new cache instance
    cache2 = TranslationCache(cache_dir=temp_cache_dir, enabled=True)
    
    # Should load from disk
    result = cache2.get(text, "zh", "en", "azure")
    assert result == translation


def test_cache_clean_expired_on_load(temp_cache_dir):
    """Test expired entries are cleaned when loading cache."""
    # Create cache with short TTL
    cache1 = TranslationCache(cache_dir=temp_cache_dir, ttl_days=1/(24*60*60), enabled=True)
    
    cache1.set("你好", "Hello", "zh", "en", "azure")
    cache1._save_cache_for_language_pair("zh", "en")
    
    # Wait for expiration
    time.sleep(1.1)
    
    # Create new cache - should clean expired entries during load
    cache2 = TranslationCache(cache_dir=temp_cache_dir, enabled=True)
    
    # Try to get - should trigger load and skip expired entries
    result = cache2.get("你好", "zh", "en", "azure")
    assert result is None


def test_cache_stats(cache):
    """Test cache statistics."""
    texts = ["你好", "谢谢", "再见"]
    translations = ["Hello", "Thank you", "Goodbye"]
    
    cache.set_batch(texts, translations, "zh", "en", "azure")
    
    stats = cache.get_stats()
    
    assert stats["total_entries"] == 3
    assert stats["ttl_days"] == 1
    assert stats["enabled"] is True
    assert "cache_dir" in stats
    assert "language_pairs" in stats
    assert "zh_en" in stats["language_pairs"]
    assert "cache_size_mb" in stats


def test_cache_clear(cache):
    """Test clearing cache."""
    cache.set("你好", "Hello", "zh", "en", "azure")
    cache.set("谢谢", "Thank you", "zh", "en", "azure")
    cache._save_cache_for_language_pair("zh", "en")
    
    assert len(cache.cache) == 2
    
    # Check CSV file exists
    csv_file = cache.cache_dir / "translation_cache_zh_en.csv"
    assert csv_file.exists()
    
    cache.clear()
    
    assert len(cache.cache) == 0
    assert not csv_file.exists()


def test_cache_handles_empty_batch(cache):
    """Test cache handles empty batch operations."""
    results, missing = cache.get_batch([], "zh", "en", "azure")
    
    assert results == []
    assert missing == []
    
    cache.set_batch([], [], "zh", "en", "azure")
    assert len(cache.cache) == 0


def test_cache_handles_mismatched_batch_lengths(cache):
    """Test cache handles mismatched text/translation lengths gracefully."""
    texts = ["你好", "谢谢"]
    translations = ["Hello"]  # Only one translation
    
    # Should log error but not crash
    cache.set_batch(texts, translations, "zh", "en", "azure")
    
    # Nothing should be cached due to mismatch
    results, missing = cache.get_batch(texts, "zh", "en", "azure")
    assert all(r is None for r in results)
