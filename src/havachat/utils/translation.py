"""Translation utilities for LLM, Azure Translation, and Google Translate.

Provides a common interface for translating text using:
1. LLM with structured output (default)
2. Azure Translation API (optional, via flag)
3. Google Translate API (optional, via flag)

Uses spaCy for word-level dictionary tokenization and POS tagging.
"""

import logging
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

from havachat.utils.azure_translation import AzureTranslationHelper
from havachat.utils.google_translate import GoogleTranslateHelper
from havachat.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


class TextTranslation(BaseModel):
    """Translation for a single text."""
    
    index: int = Field(..., description="Text index (0-based)")
    translation: str = Field(..., description="English translation")


class BatchTranslationResult(BaseModel):
    """Batch translation result."""
    
    translations: List[TextTranslation] = Field(
        ..., description="Translations for each text in order"
    )


def translate_texts(
    texts: List[str],
    from_language: str,
    llm_client: Optional[LLMClient] = None,
    azure_translator: Optional[AzureTranslationHelper] = None,
    google_translator: Optional[GoogleTranslateHelper] = None,
    use_azure: bool = False,
    use_google: bool = False,
    dictionary = None,
) -> List[str]:
    """Translate texts using LLM, Azure Translation, or Google Translate.
    
    Args:
        texts: List of texts to translate
        from_language: Source language ISO 639-1 code (e.g., "zh", "ja")
        llm_client: Optional LLM client for LLM translation
        azure_translator: Optional Azure Translation helper
        google_translator: Optional Google Translate helper
        use_azure: If True, use Azure Translation (default: False)
        use_google: If True, use Google Translate (default: False)
        dictionary: Optional Dictionary object for word-level lookups with spaCy
    
    Returns:
        List of English translations (same order as input)
    
    Note:
        Priority order: Google > Azure > LLM (if multiple flags are True)
        Dictionary is used for word-level reference with POS tagging for LLM translation.
    """
    if not texts:
        return []
    
    # Use Google Translate if requested and available (highest priority)
    if use_google and google_translator:
        try:
            translations = google_translator.translate_batch(
                texts=texts,
                from_language=from_language,
                to_language="en"
            )
            logger.debug(f"Google Translate: translated {len(translations)} texts")
            return translations
        except Exception as e:
            logger.error(f"Google Translate failed: {e}, falling back to Azure or LLM")
            # Fall through to next option
    
    # Use Azure Translation if requested and available
    if use_azure and azure_translator:
        try:
            translations = azure_translator.translate_batch(
                texts=texts,
                from_language=from_language,
                to_language="en"
            )
            logger.debug(f"Azure Translation: translated {len(translations)} texts")
            return translations
        except Exception as e:
            logger.error(f"Azure Translation failed: {e}, falling back to LLM")
            # Fall through to LLM translation
    
    # Use LLM translation (default or fallback)
    if not llm_client:
        logger.warning("No LLM client available, returning empty translations")
        return ["" for _ in texts]
    
    return _translate_with_llm(texts, from_language, llm_client, dictionary)


def _translate_with_llm(
    texts: List[str],
    from_language: str,
    llm_client: LLMClient,
    dictionary = None,
) -> List[str]:
    """Translate texts using LLM with structured output.
    
    Args:
        texts: List of texts to translate
        from_language: Source language ISO 639-1 code
        llm_client: LLM client
        dictionary: Optional Dictionary object for word-level lookups
    
    Returns:
        List of English translations (same order)
    """
    # Build prompt with numbered texts and word-level dictionary references
    texts_formatted_lines = []
    has_dictionary_refs = False
    
    for i, text in enumerate(texts):
        line = f"{i}. {text}"
        
        # Get word-level dictionary lookups if available
        if dictionary and hasattr(dictionary, 'tokenize_and_lookup'):
            word_defs = dictionary.tokenize_and_lookup(text)
            if word_defs:
                # Format: each entry on its own line, split multiple definitions
                dict_lines = []
                for word, pos, definition in word_defs:
                    if definition:
                        has_dictionary_refs = True
                        # Split definitions by semicolon and create separate lines
                        defs = [d.strip() for d in definition.split(';')]
                        for def_part in defs:
                            if def_part:  # Skip empty parts
                                dict_lines.append(f"     {word} ({pos}): {def_part}")
                
                if dict_lines:
                    line += "\n   Dictionary:\n" + "\n".join(dict_lines)
        
        texts_formatted_lines.append(line)
    
    texts_formatted = "\n\n".join(texts_formatted_lines)
    
    # Build prompt with context about dictionary references
    dictionary_context = ""
    if has_dictionary_refs:
        dictionary_context = """\n\nNote: Some words have dictionary definitions provided with their part of speech (POS). 
Use these as reference for word meanings, but translate the entire text naturally based on context. 
Dictionary definitions may be literal or have multiple meanings - choose the sense that fits the context best."""
    
    prompt = f"""Translate the following {from_language} texts to English.
Provide accurate, natural translations that preserve meaning and tone.{dictionary_context}

Texts:
{texts_formatted}

Provide translations in the same order with their index numbers."""

    logger.info(f"LLM Translation Prompt:\n{prompt}")
    
    try:
        result: BatchTranslationResult = llm_client.generate(
            prompt=prompt,
            response_model=BatchTranslationResult,
            system_prompt=f"You are a professional translator for {from_language} to English.",
            temperature=0.3,
        )
        
        # Sort by index and extract translations
        sorted_translations = sorted(result.translations, key=lambda x: x.index)
        translations = [t.translation for t in sorted_translations]
        
        # Ensure we have the right number of translations
        if len(translations) != len(texts):
            logger.warning(
                f"Translation count mismatch: expected {len(texts)}, "
                f"got {len(translations)}"
            )
            # Pad with empty strings if needed
            translations.extend(["" for _ in range(len(texts) - len(translations))])
        
        return translations[:len(texts)]
        
    except Exception as e:
        logger.error(f"LLM translation failed: {e}")
        return ["" for _ in texts]
