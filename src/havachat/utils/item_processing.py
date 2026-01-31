"""Common post-processing utilities for learning items.

This module provides reusable functions for:
- Romanization generation (pinyin, romaji)
- Example translation (using Azure Translation)
- Traditional Chinese conversion
- Example formatting

Used by both enrichers and learning item generators.
"""

import logging
from typing import List, Optional

import opencc
from pypinyin import Style, pinyin

from havachat.utils.azure_translation import AzureTranslationHelper
from havachat.utils.romanization import get_japanese_romaji, get_chinese_pinyin
from havachat.validators.schema import Example

logger = logging.getLogger(__name__)


# ============================================================================
# MANDARIN POST-PROCESSING
# ============================================================================


def get_numeric_pinyin(text: str) -> str:
    """Get pinyin with numeric tones (ai4, ba4 ba5).
    
    Args:
        text: Chinese text
        
    Returns:
        Pinyin with numeric tones (e.g., "ai4", "ba4 ba5")
    """
    try:
        result = pinyin(text, style=Style.TONE3, heteronym=False)
        return " ".join([item[0] for item in result])
    except Exception as e:
        logger.error(f"Failed to generate numeric pinyin for '{text}': {e}")
        return ""


def get_traditional_chinese(text: str) -> str:
    """Convert simplified Chinese to traditional Chinese using OpenCC.
    
    Uses s2t.json configuration (Simplified to Traditional Chinese).
    
    Args:
        text: Simplified Chinese text
        
    Returns:
        Traditional Chinese text
    """
    try:
        converter = opencc.OpenCC('s2t.json')
        traditional = converter.convert(text)
        return traditional
    except Exception as e:
        logger.error(f"Failed to convert to traditional for '{text}': {e}")
        return ""


def process_chinese_item(
    item_dict: dict,
    azure_translator: Optional[AzureTranslationHelper] = None,
    translate_examples: bool = True
) -> dict:
    """Apply Chinese-specific post-processing to an item.
    
    Generates:
    - romanization (pinyin with tone marks)
    - numeric_pinyin (pinyin with numbers)
    - traditional (traditional Chinese characters)
    - example translations (if Azure Translation available)
    
    Args:
        item_dict: Item dictionary with target_item and examples
        azure_translator: Optional Azure Translation helper
        translate_examples: Whether to translate example sentences
        
    Returns:
        Updated item dictionary with romanization and translations
    """
    target_item = item_dict.get("target_item", "")
    
    # Generate romanization
    if not item_dict.get("romanization"):
        item_dict["romanization"] = get_chinese_pinyin(target_item)
    
    # Generate numeric pinyin
    numeric_pinyin = get_numeric_pinyin(target_item)
    
    # Get traditional Chinese
    traditional = get_traditional_chinese(target_item)
    
    # Build aliases
    aliases = []
    if traditional and traditional != target_item:
        aliases.append(traditional)
    if numeric_pinyin and numeric_pinyin != item_dict.get("romanization"):
        aliases.append(numeric_pinyin)
    item_dict["aliases"] = aliases
    
    # Translate examples
    if translate_examples and "examples" in item_dict:
        examples = item_dict["examples"]
        if isinstance(examples, list) and len(examples) > 0:
            # Extract text from Example objects, dicts, or strings
            if isinstance(examples[0], Example):
                example_texts = [ex.text for ex in examples]
            elif isinstance(examples[0], dict):
                example_texts = [ex.get("text", ex) if isinstance(ex, dict) else ex for ex in examples]
            else:
                example_texts = examples
            
            # Translate
            translations = translate_examples_batch(
                example_texts, "zh", "en", azure_translator
            )
            
            # Update examples with translations
            formatted_examples = []
            for text, translation in zip(example_texts, translations):
                formatted_examples.append(
                    Example(
                        text=text,
                        translation=translation,
                        media_urls=[]
                    )
                )
            item_dict["examples"] = formatted_examples
    
    return item_dict


# ============================================================================
# JAPANESE POST-PROCESSING
# ============================================================================


def process_japanese_item(
    item_dict: dict,
    azure_translator: Optional[AzureTranslationHelper] = None,
    translate_examples: bool = True
) -> dict:
    """Apply Japanese-specific post-processing to an item.
    
    Generates:
    - romanization (romaji)
    - example translations (if Azure Translation available)
    
    Args:
        item_dict: Item dictionary with target_item and examples
        azure_translator: Optional Azure Translation helper
        translate_examples: Whether to translate example sentences
        
    Returns:
        Updated item dictionary with romanization and translations
    """
    target_item = item_dict.get("target_item", "")
    
    # Generate romanization if not present
    if not item_dict.get("romanization"):
        item_dict["romanization"] = get_japanese_romaji(target_item)
    
    # Translate examples
    if translate_examples and "examples" in item_dict:
        examples = item_dict["examples"]
        if isinstance(examples, list) and len(examples) > 0:
            # Extract text from Example objects, dicts, or strings
            if isinstance(examples[0], Example):
                example_texts = [ex.text for ex in examples]
            elif isinstance(examples[0], dict):
                example_texts = [ex.get("text", ex) if isinstance(ex, dict) else ex for ex in examples]
            else:
                example_texts = examples
            
            # Translate
            translations = translate_examples_batch(
                example_texts, "ja", "en", azure_translator
            )
            
            # Update examples with translations
            formatted_examples = []
            for text, translation in zip(example_texts, translations):
                formatted_examples.append(
                    Example(
                        text=text,
                        translation=translation,
                        media_urls=[]
                    )
                )
            item_dict["examples"] = formatted_examples
    
    return item_dict


# ============================================================================
# FRENCH POST-PROCESSING
# ============================================================================


def process_french_item(
    item_dict: dict,
    azure_translator: Optional[AzureTranslationHelper] = None,
    translate_examples: bool = True
) -> dict:
    """Apply French-specific post-processing to an item.
    
    Generates:
    - example translations (if Azure Translation available)
    
    Note: French doesn't need romanization (uses Latin alphabet)
    
    Args:
        item_dict: Item dictionary with examples
        azure_translator: Optional Azure Translation helper
        translate_examples: Whether to translate example sentences
        
    Returns:
        Updated item dictionary with translations
    """
    # French doesn't need romanization
    item_dict["romanization"] = None
    
    # Translate examples
    if translate_examples and "examples" in item_dict:
        examples = item_dict["examples"]
        if isinstance(examples, list) and len(examples) > 0:
            # Extract text from Example objects, dicts, or strings
            if isinstance(examples[0], Example):
                example_texts = [ex.text for ex in examples]
            elif isinstance(examples[0], dict):
                example_texts = [ex.get("text", ex) if isinstance(ex, dict) else ex for ex in examples]
            else:
                example_texts = examples
            
            # Translate
            translations = translate_examples_batch(
                example_texts, "fr", "en", azure_translator
            )
            
            # Update examples with translations
            formatted_examples = []
            for text, translation in zip(example_texts, translations):
                formatted_examples.append(
                    Example(
                        text=text,
                        translation=translation,
                        media_urls=[]
                    )
                )
            item_dict["examples"] = formatted_examples
    
    return item_dict


# ============================================================================
# TRANSLATION UTILITIES
# ============================================================================


def translate_examples_batch(
    texts: List[str],
    from_language: str,
    to_language: str,
    azure_translator: Optional[AzureTranslationHelper] = None
) -> List[str]:
    """Translate a batch of example sentences using Azure Translation.
    
    Args:
        texts: List of texts to translate
        from_language: Source language code (zh, ja, fr, etc.)
        to_language: Target language code (usually "en")
        azure_translator: Optional Azure Translation helper
        
    Returns:
        List of translated texts (empty strings if translation fails)
    """
    if not texts:
        return []
    
    if azure_translator:
        try:
            translations = azure_translator.translate_batch(
                texts=texts,
                from_language=from_language,
                to_language=to_language
            )
            logger.debug(f"Translated {len(translations)} examples from {from_language} to {to_language}")
            return translations
        except Exception as e:
            logger.error(f"Azure Translation failed: {e}")
            return ["" for _ in texts]
    else:
        logger.warning(f"Azure Translation not available, examples will have no translations")
        return ["" for _ in texts]


# ============================================================================
# GENERIC POST-PROCESSOR
# ============================================================================


def post_process_learning_item(
    item_dict: dict,
    language: str,
    azure_translator: Optional[AzureTranslationHelper] = None,
    translate_examples: bool = True
) -> dict:
    """Apply language-specific post-processing to a learning item.
    
    This is a convenience function that routes to the appropriate
    language-specific processor. Supports both dictionary and LearningItem inputs.
    
    Args:
        item_dict: Item dictionary or LearningItem object
        language: Language code (zh, ja, fr, etc.)
        azure_translator: Optional Azure Translation helper
        translate_examples: Whether to translate example sentences
        
    Returns:
        Updated item dictionary with post-processing applied (same type as input)
    """
    from havachat.validators.schema import LearningItem
    
    # Convert LearningItem to dict for processing
    is_learning_item = isinstance(item_dict, LearningItem)
    if is_learning_item:
        item_data = item_dict.model_dump()
    else:
        item_data = item_dict
    
    language = language.lower()
    
    if language == "zh":
        result = process_chinese_item(item_data, azure_translator, translate_examples)
    elif language == "ja":
        result = process_japanese_item(item_data, azure_translator, translate_examples)
    elif language == "fr":
        result = process_french_item(item_data, azure_translator, translate_examples)
    else:
        # For other languages, just translate examples if needed
        if translate_examples and azure_translator and "examples" in item_data:
            examples = item_data["examples"]
            if isinstance(examples, list) and len(examples) > 0:
                # Extract text from Example objects, dicts, or strings
                if isinstance(examples[0], Example):
                    example_texts = [ex.text for ex in examples]
                elif isinstance(examples[0], dict):
                    example_texts = [ex.get("text", ex) if isinstance(ex, dict) else ex for ex in examples]
                else:
                    example_texts = examples
                
                translations = translate_examples_batch(
                    example_texts, language, "en", azure_translator
                )
                
                formatted_examples = []
                for text, translation in zip(example_texts, translations):
                    formatted_examples.append(
                        Example(
                            text=text,
                            translation=translation,
                            media_urls=[]
                        )
                    )
                item_data["examples"] = formatted_examples
        
        result = item_data
    
    # Convert back to LearningItem if input was LearningItem
    if is_learning_item:
        return LearningItem(**result)
    else:
        return result
