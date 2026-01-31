"""Unit tests for Google Translate helper."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.havachat.utils.google_translate import GoogleTranslateHelper


@pytest.fixture
def temp_cache_dir():
    """Create temporary cache directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_translate_client():
    """Mock Google Translate client."""
    with patch('src.havachat.utils.google_translate.translate.Client') as mock_client:
        yield mock_client


@pytest.fixture
def mock_env_credentials():
    """Mock GOOGLE_APPLICATION_CREDENTIALS environment variable."""
    with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": "/path/to/credentials.json"}):
        yield


def test_init_without_credentials():
    """Test initialization fails without credentials."""
    with pytest.raises(ValueError, match="Google Translate credentials not set"):
        GoogleTranslateHelper()


def test_init_with_credentials(mock_translate_client, mock_env_credentials, temp_cache_dir):
    """Test successful initialization with credentials."""
    helper = GoogleTranslateHelper()
    helper.cache.cache_dir = temp_cache_dir
    
    assert helper.client is not None
    assert helper.total_characters == 0
    assert helper.monthly_limit == 500_000
    assert helper.cache is not None


def test_translate_batch(mock_translate_client, mock_env_credentials, temp_cache_dir):
    """Test batch translation."""
    # Mock API response
    mock_client_instance = MagicMock()
    mock_client_instance.translate.return_value = [
        {'translatedText': 'Hello'},
        {'translatedText': 'Thank you'},
        {'translatedText': 'Goodbye'}
    ]
    mock_translate_client.return_value = mock_client_instance
    
    helper = GoogleTranslateHelper()
    helper.cache.cache_dir = temp_cache_dir
    
    texts = ["你好", "谢谢", "再见"]
    translations = helper.translate_batch(texts, "zh", "en")
    
    assert len(translations) == 3
    assert translations[0] == 'Hello'
    assert translations[1] == 'Thank you'
    assert translations[2] == 'Goodbye'
    assert helper.total_characters == 6  # 你好 + 谢谢 + 再见


def test_translate_single(mock_translate_client, mock_env_credentials, temp_cache_dir):
    """Test single text translation."""
    mock_client_instance = MagicMock()
    mock_client_instance.translate.return_value = [{'translatedText': 'Hello'}]
    mock_translate_client.return_value = mock_client_instance
    
    helper = GoogleTranslateHelper()
    helper.cache.cache_dir = temp_cache_dir
    
    translation = helper.translate_single("你好", "zh", "en")
    
    assert translation == 'Hello'
    assert helper.total_characters == 2


def test_monthly_limit_exceeded(mock_translate_client, mock_env_credentials, temp_cache_dir):
    """Test that exceeding monthly limit raises error."""
    mock_client_instance = MagicMock()
    mock_translate_client.return_value = mock_client_instance
    
    helper = GoogleTranslateHelper()
    helper.cache.cache_dir = temp_cache_dir
    helper.total_characters = 499_999
    
    # Try to translate text that would exceed limit
    texts = ["这是一个很长的文本" * 100]  # Will exceed remaining 1 char
    
    with pytest.raises(RuntimeError, match="Google Translate monthly limit exceeded"):
        helper.translate_batch(texts, "zh", "en")


def test_get_usage_summary(mock_translate_client, mock_env_credentials, temp_cache_dir):
    """Test usage summary."""
    mock_client_instance = MagicMock()
    mock_client_instance.translate.return_value = [{'translatedText': 'Hello'}]
    mock_translate_client.return_value = mock_client_instance
    
    helper = GoogleTranslateHelper()
    helper.cache.cache_dir = temp_cache_dir
    helper.translate_single("你好", "zh", "en")
    
    summary = helper.get_usage_summary()
    
    assert summary['total_characters'] == 2
    assert summary['monthly_limit'] == 500_000
    assert summary['remaining'] == 499_998
    assert 'usage_percent' in summary
    assert 'cache_stats' in summary


def test_reset_usage(mock_translate_client, mock_env_credentials, temp_cache_dir):
    """Test resetting usage counter."""
    mock_client_instance = MagicMock()
    mock_translate_client.return_value = mock_client_instance
    
    helper = GoogleTranslateHelper()
    helper.cache.cache_dir = temp_cache_dir
    helper.total_characters = 10000
    
    helper.reset_usage()
    
    assert helper.total_characters == 0


def test_cache_integration(mock_translate_client, mock_env_credentials, temp_cache_dir):
    """Test that cache is used for repeated translations."""
    mock_client_instance = MagicMock()
    mock_client_instance.translate.return_value = [{'translatedText': 'Hello'}]
    mock_translate_client.return_value = mock_client_instance
    
    helper = GoogleTranslateHelper(enable_cache=True)
    helper.cache.cache_dir = temp_cache_dir
    
    # First call should hit API
    result1 = helper.translate_single("你好world", "zh", "en")
    assert mock_client_instance.translate.call_count == 1
    
    # Second call should use cache
    result2 = helper.translate_single("你好world", "zh", "en")
    assert mock_client_instance.translate.call_count == 1  # Still 1, not 2
    
    assert result1 == result2 == 'Hello'


def test_empty_batch(mock_translate_client, mock_env_credentials, temp_cache_dir):
    """Test translating empty batch."""
    helper = GoogleTranslateHelper()
    helper.cache.cache_dir = temp_cache_dir
    
    translations = helper.translate_batch([], "zh", "en")
    
    assert translations == []
