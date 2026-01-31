"""Romanization utilities for Chinese and Japanese.

Provides automatic romanization using Python libraries instead of LLM:
- Chinese: pypinyin (pinyin with tone marks)
- Japanese: pykakasi (romaji - Hepburn style)
"""

import logging
from typing import Optional

# Import romanization libraries
try:
    from pypinyin import lazy_pinyin, Style
    PYPINYIN_AVAILABLE = True
except ImportError:
    PYPINYIN_AVAILABLE = False

try:
    from pykakasi import kakasi
    PYKAKASI_AVAILABLE = True
except ImportError:
    PYKAKASI_AVAILABLE = False

logger = logging.getLogger(__name__)


def get_chinese_pinyin(text: str, tone_marks: bool = True) -> str:
    """Get pinyin romanization for Chinese text.

    Uses pypinyin library to convert Chinese characters to pinyin with tone marks.

    Args:
        text: Chinese text (simplified or traditional)
        tone_marks: Include tone marks (default: True)

    Returns:
        Pinyin romanization with tone marks (e.g., "yínháng" for 银行)

    Example:
        >>> get_chinese_pinyin("银行")
        'yínháng'
        >>> get_chinese_pinyin("学校")
        'xuéxiào'
    """
    if not PYPINYIN_AVAILABLE:
        logger.warning("pypinyin not available, returning empty string")
        return ""

    # Get pinyin with tone marks
    style = Style.TONE if tone_marks else Style.NORMAL

    pinyin_list = lazy_pinyin(text, style=style, errors='ignore')

    # Join without spaces for single words, with spaces for phrases
    if len(text) <= 2:
        # Single word - join without spaces
        return ''.join(pinyin_list)
    else:
        # Phrase - join with spaces
        return ' '.join(pinyin_list)


def get_japanese_romaji(text: str, capitalize: bool = False) -> str:
    """Get romaji romanization for Japanese text.

    Uses pykakasi library to convert Japanese (hiragana/katakana/kanji) to romaji.

    Args:
        text: Japanese text (any mix of hiragana, katakana, kanji)
        capitalize: Capitalize first letter (default: False)

    Returns:
        Romaji romanization (Hepburn style)

    Example:
        >>> get_japanese_romaji("学校")
        'gakkou'
        >>> get_japanese_romaji("こんにちは")
        'konnichiha'
    """
    if not PYKAKASI_AVAILABLE:
        logger.warning("pykakasi not available, returning empty string")
        return ""

    # Initialize kakasi converter
    kks = kakasi()

    # Convert to romaji
    result = kks.convert(text)

    # Extract romaji from result
    romaji_parts = [item['hepburn'] for item in result]
    romaji = ''.join(romaji_parts)

    if capitalize and romaji:
        romaji = romaji[0].upper() + romaji[1:]

    return romaji


def clean_sense_marker(text: str) -> str:
    """Remove sense markers (trailing numbers) from Chinese vocabulary.

    Sense markers like 本1, 点1, 会1 are used in teaching materials to
    disambiguate homographs. The number is NOT part of the actual word.

    Args:
        text: Text that may contain sense marker (e.g., "本1", "和1")

    Returns:
        Text with sense marker removed (e.g., "本", "和")

    Example:
        >>> clean_sense_marker("本1")
        '本'
        >>> clean_sense_marker("会1")
        '会'
        >>> clean_sense_marker("学校")
        '学校'
    """
    # Remove trailing digits
    return text.rstrip('0123456789')


def extract_sense_marker(text: str) -> Optional[int]:
    """Extract sense marker number from Chinese vocabulary.

    Args:
        text: Text that may contain sense marker (e.g., "本1", "和1")

    Returns:
        Sense number if present, None otherwise

    Example:
        >>> extract_sense_marker("本1")
        1
        >>> extract_sense_marker("会2")
        2
        >>> extract_sense_marker("学校")
        None
    """
    # Find trailing digits
    i = len(text) - 1
    while i >= 0 and text[i].isdigit():
        i -= 1

    if i < len(text) - 1:
        return int(text[i + 1:])

    return None


# POS label translation map (Chinese → English)
CHINESE_POS_MAP = {
    "名": "noun",
    "动": "verb",
    "形": "adjective",
    "副": "adverb",
    "代": "pronoun",
    "数": "numeral",
    "量": "classifier",
    "介": "preposition",
    "助": "particle",
    "叹": "interjection",
    "连": "conjunction",
    "前缀": "prefix",
    "后缀": "suffix",
    "数量": "quantity_phrase",
}


def translate_chinese_pos(chinese_pos: str) -> str:
    """Translate Chinese POS label to English.

    Args:
        chinese_pos: Chinese POS label (e.g., "名", "动", "形")

    Returns:
        English POS equivalent (e.g., "noun", "verb", "adjective")

    Example:
        >>> translate_chinese_pos("名")
        'noun'
        >>> translate_chinese_pos("动")
        'verb'
        >>> translate_chinese_pos("量")
        'classifier'
    """
    # Handle compound POS like "名、动" or "量、（名）"
    # Take the first/primary one
    if "、" in chinese_pos:
        chinese_pos = chinese_pos.split("、")[0]

    # Remove parentheses
    chinese_pos = chinese_pos.strip("()（）")

    return CHINESE_POS_MAP.get(chinese_pos, chinese_pos)
