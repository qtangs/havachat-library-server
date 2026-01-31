"""Integration test for character validation in content generation."""

import pytest
from uuid import uuid4

from havachat.validators.schema import (
    LevelSystem,
    Category,
    LearningItem,
    ContentStatus,
)
from datetime import datetime, UTC


@pytest.fixture
def mandarin_vocab_items():
    """Create sample Chinese vocabulary items."""
    return [
        LearningItem(
            id=str(uuid4()),
            language="zh",
            category=Category.VOCAB,
            target_item="我",
            definition="I, me",
            examples=[],
            level_system=LevelSystem.HSK,
            level_min="HSK1",
            level_max="HSK1",
            created_at=datetime.now(UTC),
        ),
        LearningItem(
            id=str(uuid4()),
            language="zh",
            category=Category.VOCAB,
            target_item="爱",
            definition="to love",
            examples=[],
            level_system=LevelSystem.HSK,
            level_min="HSK1",
            level_max="HSK1",
            created_at=datetime.now(UTC),
        ),
        LearningItem(
            id=str(uuid4()),
            language="zh",
            category=Category.VOCAB,
            target_item="学习",
            definition="to study",
            examples=[],
            level_system=LevelSystem.HSK,
            level_min="HSK1",
            level_max="HSK1",
            created_at=datetime.now(UTC),
        ),
    ]


def test_character_validation_all_present(mandarin_vocab_items):
    """Test that content with all characters in vocab is marked active."""
    from havachat.validators.character_validator import validate_content_characters
    
    # Content uses only characters from vocab
    content = "我爱学习"
    vocab_target_items = [item.target_item for item in mandarin_vocab_items]
    
    is_valid, missing = validate_content_characters(content, vocab_target_items, "zh")
    
    assert is_valid is True
    assert missing == []


def test_character_validation_missing_chars(mandarin_vocab_items):
    """Test that content with missing characters is marked for review."""
    from havachat.validators.character_validator import validate_content_characters
    
    # Content uses characters not in vocab: 你, 好
    content = "我爱学习，你好"
    vocab_target_items = [item.target_item for item in mandarin_vocab_items]
    
    is_valid, missing = validate_content_characters(content, vocab_target_items, "zh")
    
    assert is_valid is False
    assert '你' in missing
    assert '好' in missing


def test_character_validation_french_placeholder():
    """Test that French content validation is placeholder."""
    from havachat.validators.character_validator import validate_content_characters
    
    content = "Bonjour tout le monde"
    vocab = ["Bonjour", "tout", "le", "monde"]
    
    is_valid, missing = validate_content_characters(content, vocab, "fr")
    
    # Should pass (placeholder implementation)
    assert is_valid is True
    assert missing == []


def test_character_validation_japanese_placeholder():
    """Test that Japanese content validation is placeholder."""
    from havachat.validators.character_validator import validate_content_characters
    
    content = "こんにちは世界"
    vocab = ["こんにちは", "世界"]
    
    is_valid, missing = validate_content_characters(content, vocab, "ja")
    
    # Should pass (placeholder implementation)
    assert is_valid is True
    assert missing == []
