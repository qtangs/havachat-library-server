"""Character validation utilities for content generation.

This module provides language-specific character validation to ensure
generated content only uses characters present in the vocabulary.
"""

import logging
import re
from typing import List, Set, Dict, Tuple

logger = logging.getLogger(__name__)


def extract_chinese_characters(text: str) -> Set[str]:
    """Extract all Chinese characters from text.
    
    Chinese characters are in the CJK Unified Ideographs Unicode block:
    U+4E00 to U+9FFF (most common Chinese characters)
    
    Args:
        text: Text to extract characters from
        
    Returns:
        Set of unique Chinese characters
        
    Example:
        >>> extract_chinese_characters("我爱学习中文！123 abc")
        {'我', '爱', '学', '习', '中', '文'}
    """
    # CJK Unified Ideographs range (most common Chinese characters)
    chinese_chars = set(char for char in text if '\u4e00' <= char <= '\u9fff')
    return chinese_chars


def extract_japanese_characters(text: str) -> Set[str]:
    """Extract all Japanese characters (Hiragana, Katakana, Kanji) from text.
    
    Japanese character ranges:
    - Hiragana: U+3040 to U+309F
    - Katakana: U+30A0 to U+30FF
    - Kanji: U+4E00 to U+9FFF (CJK Unified Ideographs)
    
    Args:
        text: Text to extract characters from
        
    Returns:
        Set of unique Japanese characters
        
    Example:
        >>> extract_japanese_characters("こんにちは世界")
        {'こ', 'ん', 'に', 'ち', 'は', '世', '界'}
    """
    # Placeholder for now - will be implemented later
    return set()


def extract_french_characters(text: str) -> Set[str]:
    """Extract all French special characters from text.
    
    French special characters include:
    - Accented vowels: à, â, é, è, ê, ë, î, ï, ô, ù, û, ü, ÿ
    - Cedilla: ç
    - Ligatures: æ, œ
    
    Args:
        text: Text to extract characters from
        
    Returns:
        Set of unique French special characters
        
    Example:
        >>> extract_french_characters("café crème")
        {'é', 'è'}
    """
    # Placeholder for now - will be implemented later
    return set()


def validate_chinese_characters(
    content_text: str,
    vocab_items: List[str]
) -> Tuple[bool, List[str]]:
    """Validate that all Chinese characters in content are present in vocabulary.
    
    Args:
        content_text: The content text to validate
        vocab_items: List of vocabulary items (target_item field)
        
    Returns:
        Tuple of (is_valid, missing_characters)
        - is_valid: True if all characters are in vocab, False otherwise
        - missing_characters: List of characters not found in vocab
        
    Example:
        >>> validate_chinese_characters("我爱你", ["我", "爱"])
        (False, ['你'])
    """
    # Extract all Chinese characters from content
    content_chars = extract_chinese_characters(content_text)
    
    if not content_chars:
        # No Chinese characters found, validation passes
        return True, []
    
    # Extract all Chinese characters from vocabulary
    vocab_chars = set()
    for item in vocab_items:
        vocab_chars.update(extract_chinese_characters(item))
    
    # Find characters in content but not in vocab
    missing_chars = content_chars - vocab_chars
    
    if missing_chars:
        logger.warning(
            f"Found {len(missing_chars)} Chinese characters not in vocabulary: "
            f"{sorted(missing_chars)}"
        )
        return False, sorted(missing_chars)
    
    return True, []


def validate_japanese_characters(
    content_text: str,
    vocab_items: List[str]
) -> Tuple[bool, List[str]]:
    """Validate that all Japanese characters in content are present in vocabulary.
    
    Placeholder implementation for future use.
    
    Args:
        content_text: The content text to validate
        vocab_items: List of vocabulary items (target_item field)
        
    Returns:
        Tuple of (is_valid, missing_characters)
        - Currently always returns (True, [])
    """
    # TODO: Implement Japanese character validation
    logger.info("Japanese character validation not yet implemented - skipping")
    return True, []


def validate_french_characters(
    content_text: str,
    vocab_items: List[str]
) -> Tuple[bool, List[str]]:
    """Validate that all French special characters in content are present in vocabulary.
    
    Placeholder implementation for future use.
    
    Args:
        content_text: The content text to validate
        vocab_items: List of vocabulary items (target_item field)
        
    Returns:
        Tuple of (is_valid, missing_characters)
        - Currently always returns (True, [])
    """
    # TODO: Implement French character validation
    logger.info("French character validation not yet implemented - skipping")
    return True, []


def validate_content_characters(
    content_text: str,
    vocab_items: List[str],
    language: str
) -> Tuple[bool, List[str]]:
    """Validate characters in content based on language.
    
    Args:
        content_text: The content text to validate
        vocab_items: List of vocabulary items (target_item field)
        language: ISO 639-1 language code (zh, ja, fr, etc.)
        
    Returns:
        Tuple of (is_valid, missing_characters)
        - is_valid: True if all characters are in vocab or validation not needed
        - missing_characters: List of characters/items not found in vocab
    """
    if language == "zh":
        return validate_chinese_characters(content_text, vocab_items)
    elif language == "ja":
        return validate_japanese_characters(content_text, vocab_items)
    elif language == "fr":
        return validate_french_characters(content_text, vocab_items)
    else:
        # For other languages, no character validation needed
        logger.debug(f"No character validation implemented for language: {language}")
        return True, []
