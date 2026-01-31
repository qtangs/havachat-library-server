"""Unit tests for character validation utilities."""

import pytest

from src.pipeline.validators.character_validator import (
    extract_chinese_characters,
    validate_chinese_characters,
    validate_content_characters,
)


class TestChineseCharacterExtraction:
    """Tests for Chinese character extraction."""

    def test_extract_basic_chinese(self):
        """Test extraction of basic Chinese characters."""
        text = "我爱学习中文"
        chars = extract_chinese_characters(text)
        assert chars == {'我', '爱', '学', '习', '中', '文'}

    def test_extract_with_punctuation(self):
        """Test extraction ignores punctuation."""
        text = "你好！world 123"
        chars = extract_chinese_characters(text)
        assert chars == {'你', '好'}

    def test_extract_mixed_content(self):
        """Test extraction from mixed Chinese/English content."""
        text = "I love 中国 and 日本"
        chars = extract_chinese_characters(text)
        assert chars == {'中', '国', '日', '本'}

    def test_extract_empty_text(self):
        """Test extraction from text with no Chinese characters."""
        text = "Hello world 123!"
        chars = extract_chinese_characters(text)
        assert chars == set()

    def test_extract_repeated_characters(self):
        """Test extraction removes duplicates."""
        text = "好好学习，天天向上"
        chars = extract_chinese_characters(text)
        # Should have unique characters only
        assert '好' in chars
        assert '天' in chars
        assert '学' in chars


class TestChineseCharacterValidation:
    """Tests for Chinese character validation."""

    def test_validate_all_present(self):
        """Test validation passes when all characters are in vocab."""
        content = "我爱学习"
        vocab = ["我", "爱", "学习", "中文"]
        is_valid, missing = validate_chinese_characters(content, vocab)
        assert is_valid is True
        assert missing == []

    def test_validate_missing_characters(self):
        """Test validation fails when characters are missing."""
        content = "我爱学习中文"
        vocab = ["我", "爱"]
        is_valid, missing = validate_chinese_characters(content, vocab)
        assert is_valid is False
        assert set(missing) == {'学', '习', '中', '文'}

    def test_validate_partial_match(self):
        """Test validation with partial vocabulary match."""
        content = "我在学校学习"
        vocab = ["我", "在", "学校"]
        is_valid, missing = validate_chinese_characters(content, vocab)
        assert is_valid is False
        # "学校" contains "学" and "校", so only "习" should be missing
        assert missing == ['习']

    def test_validate_multi_character_words(self):
        """Test validation with multi-character vocabulary words."""
        content = "我在学校"
        vocab = ["我在", "学校"]
        is_valid, missing = validate_chinese_characters(content, vocab)
        assert is_valid is True
        assert missing == []

    def test_validate_no_chinese_content(self):
        """Test validation passes when content has no Chinese."""
        content = "Hello world"
        vocab = ["你好", "世界"]
        is_valid, missing = validate_chinese_characters(content, vocab)
        assert is_valid is True
        assert missing == []

    def test_validate_empty_vocab(self):
        """Test validation fails with empty vocabulary."""
        content = "我爱学习"
        vocab = []
        is_valid, missing = validate_chinese_characters(content, vocab)
        assert is_valid is False
        assert len(missing) == 4

    def test_validate_with_punctuation(self):
        """Test validation ignores punctuation in content."""
        content = "我爱学习！你好吗？"
        vocab = ["我", "爱", "学习", "你好", "吗"]
        is_valid, missing = validate_chinese_characters(content, vocab)
        assert is_valid is True
        assert missing == []


class TestContentCharacterValidation:
    """Tests for language-agnostic content validation."""

    def test_validate_chinese_content(self):
        """Test validation routing for Chinese content."""
        content = "我爱学习"
        vocab = ["我", "爱"]
        is_valid, missing = validate_content_characters(content, vocab, "zh")
        assert is_valid is False
        assert len(missing) == 2

    def test_validate_japanese_placeholder(self):
        """Test Japanese validation placeholder."""
        content = "こんにちは"
        vocab = ["こんにちは"]
        is_valid, missing = validate_content_characters(content, vocab, "ja")
        assert is_valid is True
        assert missing == []

    def test_validate_french_placeholder(self):
        """Test French validation placeholder."""
        content = "Bonjour le monde"
        vocab = ["Bonjour", "le", "monde"]
        is_valid, missing = validate_content_characters(content, vocab, "fr")
        assert is_valid is True
        assert missing == []

    def test_validate_unsupported_language(self):
        """Test validation for unsupported language."""
        content = "Hello world"
        vocab = ["Hello", "world"]
        is_valid, missing = validate_content_characters(content, vocab, "en")
        assert is_valid is True
        assert missing == []
