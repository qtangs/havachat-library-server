"""Unit tests for romanization utilities."""

import pytest

from src.pipeline.utils.romanization import (
    clean_sense_marker,
    extract_sense_marker,
    get_japanese_romaji,
    get_mandarin_pinyin,
    translate_chinese_pos,
)


class TestMandarinPinyin:
    """Tests for Mandarin pinyin generation."""

    def test_basic_words(self):
        """Test pinyin generation for common words."""
        assert get_mandarin_pinyin("银行") == "yínháng"
        assert get_mandarin_pinyin("学校") == "xuéxiào"
        assert get_mandarin_pinyin("学习") == "xuéxí"

    def test_single_characters(self):
        """Test pinyin generation for single characters."""
        assert get_mandarin_pinyin("爱") == "ài"
        assert get_mandarin_pinyin("点") == "diǎn"
        assert get_mandarin_pinyin("本") == "běn"
        assert get_mandarin_pinyin("会") == "huì"
        assert get_mandarin_pinyin("和") == "hé"

    def test_tone_marks(self):
        """Test that tone marks are correctly included."""
        result = get_mandarin_pinyin("中国")
        assert "ō" in result or "ó" in result or "ǒ" in result or "ò" in result


class TestSenseMarkers:
    """Tests for sense marker handling."""

    def test_clean_sense_marker(self):
        """Test removal of sense markers."""
        assert clean_sense_marker("本1") == "本"
        assert clean_sense_marker("点1") == "点"
        assert clean_sense_marker("会1") == "会"
        assert clean_sense_marker("和1") == "和"
        assert clean_sense_marker("两2") == "两"
        
    def test_clean_no_marker(self):
        """Test cleaning words without markers."""
        assert clean_sense_marker("学校") == "学校"
        assert clean_sense_marker("银行") == "银行"

    def test_extract_sense_marker(self):
        """Test extraction of sense marker numbers."""
        assert extract_sense_marker("本1") == 1
        assert extract_sense_marker("点1") == 1
        assert extract_sense_marker("会1") == 1
        assert extract_sense_marker("两2") == 2
        
    def test_extract_no_marker(self):
        """Test extraction when no marker present."""
        assert extract_sense_marker("学校") is None
        assert extract_sense_marker("银行") is None


class TestChinesePosTranslation:
    """Tests for Chinese POS label translation."""

    def test_basic_pos(self):
        """Test translation of basic POS labels."""
        assert translate_chinese_pos("名") == "noun"
        assert translate_chinese_pos("动") == "verb"
        assert translate_chinese_pos("形") == "adjective"
        assert translate_chinese_pos("副") == "adverb"
        assert translate_chinese_pos("量") == "classifier"
        assert translate_chinese_pos("介") == "preposition"
        assert translate_chinese_pos("助") == "particle"
        assert translate_chinese_pos("叹") == "interjection"
        assert translate_chinese_pos("连") == "conjunction"
        assert translate_chinese_pos("代") == "pronoun"
        assert translate_chinese_pos("数") == "numeral"

    def test_compound_pos(self):
        """Test translation of compound POS labels."""
        # Should take the first/primary one
        assert translate_chinese_pos("名、动") == "noun"
        assert translate_chinese_pos("量、（名）") == "classifier"

    def test_pos_with_parentheses(self):
        """Test POS labels with parentheses."""
        assert translate_chinese_pos("（名）") == "noun"
        assert translate_chinese_pos("(动)") == "verb"

    def test_unknown_pos(self):
        """Test unknown POS labels return unchanged."""
        assert translate_chinese_pos("未知") == "未知"


class TestJapaneseRomaji:
    """Tests for Japanese romaji generation."""

    def test_kanji_words(self):
        """Test romaji generation for kanji words."""
        assert get_japanese_romaji("学校") == "gakkou"
        assert get_japanese_romaji("先生") == "sensei"
        assert get_japanese_romaji("今日") == "kyou"

    def test_hiragana_words(self):
        """Test romaji generation for hiragana words."""
        assert get_japanese_romaji("こんにちは") == "konnichiha"
        assert get_japanese_romaji("ありがとう") == "arigatou"

    def test_katakana_words(self):
        """Test romaji generation for katakana words."""
        # コーヒー (coffee)
        assert get_japanese_romaji("コーヒー") == "koohii"

    def test_capitalize_option(self):
        """Test capitalization option."""
        result = get_japanese_romaji("学校", capitalize=True)
        assert result[0].isupper()
        assert result == "Gakkou"
