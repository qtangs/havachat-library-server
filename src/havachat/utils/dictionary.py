"""Generic dictionary lookup interface for translation reference.

Provides a base class for language-specific dictionaries (e.g., CC-CEDICT for Chinese,
EDICT for Japanese) that can be used as reference material for LLM translation.

Uses spaCy for tokenization and POS tagging.
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

try:
    import spacy
    from spacy.tokens import Doc
    HAS_SPACY = True
except ImportError:
    HAS_SPACY = False
    spacy = None
    Doc = None

try:
    import ctypes
    from macdict.foundation import (
        CFStringCreateWithBytes, CFStringEncodingUTF8, CFRange,
        DCSCopyTextDefinition, objc, sel_name
    )
    HAS_MACDICT = True
except ImportError:
    HAS_MACDICT = False
    ctypes = None

logger = logging.getLogger(__name__)


def macdict_lookup_word(word: str) -> Optional[str]:
    """Look up word in macOS Dictionary.app.
    
    Fixed version that properly handles multibyte UTF-8 characters like Chinese.
    """
    if not HAS_MACDICT:
        return None
    
    try:
        word_bytes = word.encode('utf-8')
        word_cfstring = CFStringCreateWithBytes(
            None, word_bytes, len(word_bytes), CFStringEncodingUTF8, False)
        
        # Use character length, not byte length for CFRange
        definition_nsstring = DCSCopyTextDefinition(
            None, word_cfstring, CFRange(0, len(word)))
        
        if not definition_nsstring:
            return None
        
        definition = ctypes.c_char_p(objc.objc_msgSend(
            definition_nsstring, sel_name('UTF8String')))
        
        if definition.value:
            return definition.value.decode('utf-8')
    except Exception as e:
        logger.debug(f"macdict lookup failed for '{word}': {e}")
    
    return None


class Dictionary(ABC):
    """Abstract base class for language dictionaries.
    
    Subclasses should implement language-specific lookup logic.
    Uses spaCy for tokenization and POS tagging.
    """
    
    def __init__(self, language: str, spacy_model: str):
        """Initialize dictionary for a specific language.
        
        Args:
            language: ISO 639-1 language code (e.g., "zh", "ja", "fr")
            spacy_model: spaCy model name (e.g., "zh_core_web_sm")
        """
        self.language = language
        self.lookup_dict: Dict[str, str] = {}
        self.spacy_model_name = spacy_model
        self.nlp = None
        
        # Load spaCy model
        if HAS_SPACY:
            try:
                self.nlp = spacy.load(spacy_model)
                logger.info(f"Loaded spaCy model: {spacy_model}")
            except OSError:
                error_msg = (
                    f"spaCy model '{spacy_model}' not found. "
                    f"Install with: PYTHONPATH=src uv run python -m spacy download {spacy_model}"
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg)
        else:
            error_msg = (
                "spaCy not installed. Dictionary tokenization will not work. "
                "Install with: uv add spacy"
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    @abstractmethod
    def load_dictionary(self) -> None:
        """Load dictionary data into lookup_dict.
        
        Subclasses must implement this to load their specific dictionary format.
        """
        pass
    
    def tokenize_and_lookup(self, text: str) -> List[Tuple[str, str, Optional[str]]]:
        """Tokenize text using spaCy and look up each word in dictionary.
        
        Args:
            text: Text to tokenize and look up
        
        Returns:
            List of (word, pos, definition) tuples. Definition is None if not found.
        """
        if not self.nlp:
            logger.warning(f"spaCy model not loaded for {self.language}")
            return []
        
        # Parse text with spaCy
        doc: Doc = self.nlp(text)
        results = []
        
        for token in doc:
            # Skip whitespace and punctuation
            if token.is_space or token.is_punct:
                continue
            
            # Use lemma for dictionary lookup (base form)
            lemma = token.lemma_
            pos = token.pos_
            
            # Look up in dictionary
            definition = self.lookup_dict.get(lemma) or self.lookup_dict.get(token.text)
            
            results.append((token.text, pos, definition))
        
        return results
    
    def lookup_batch_with_context(self, texts: List[str]) -> List[List[Tuple[str, str, Optional[str]]]]:
        """Look up dictionary definitions for words in a batch of texts.
        
        Args:
            texts: List of texts to process
        
        Returns:
            List of word lists, where each word is (word, pos, definition)
        """
        return [self.tokenize_and_lookup(text) for text in texts]
    
    def lookup(self, text: str) -> Optional[str]:
        """Look up dictionary translation for a text (legacy method).
        
        Note: This method is kept for backward compatibility but tokenize_and_lookup
        is preferred for more accurate results.
        
        Args:
            text: Text to look up in the source language
        
        Returns:
            Dictionary translation if found, None otherwise
        """
        # Try exact match first
        if text in self.lookup_dict:
            return self.lookup_dict[text]
        
        # Try tokenization and lookup
        words_with_defs = self.tokenize_and_lookup(text)
        definitions = [d for _, _, d in words_with_defs if d]
        
        if definitions:
            return "; ".join(definitions)
        
        return None
    
    def lookup_batch(self, texts: List[str]) -> List[Optional[str]]:
        """Look up dictionary translations for a batch of texts (legacy method).
        
        Args:
            texts: List of texts to look up
        
        Returns:
            List of dictionary translations (None for texts without entries)
        """
        return [self.lookup(text) for text in texts]
    
    def size(self) -> int:
        """Get the number of entries in the dictionary.
        
        Returns:
            Number of entries
        """
        return len(self.lookup_dict)


class CCCEDICTDictionary(Dictionary):
    """CC-CEDICT dictionary for Chinese.
    
    Loads dictionary entries from macOS Dictionary.app (via macdict) if available,
    otherwise falls back to CC-CEDICT parser.
    Uses spaCy zh_core_web_sm model for tokenization.
    """
    
    def __init__(self):
        """Initialize CC-CEDICT dictionary for Chinese."""
        super().__init__(language="zh", spacy_model="zh_core_web_sm")
        self.use_macdict = False
        self.load_dictionary()
    
    def load_dictionary(self) -> None:
        """Load dictionary entries from macOS Dictionary or CC-CEDICT.
        
        Priority:
        1. macOS Dictionary.app (via macdict) - better contextual definitions
        2. CC-CEDICT - fallback for non-macOS or if macdict unavailable
        """
        # Try macOS Dictionary first
        if HAS_MACDICT:
            try:
                # Test if macdict works with Chinese (use a common word)
                test_result = macdict_lookup_word("好")
                if test_result:
                    self.use_macdict = True
                    logger.info("Using macOS Dictionary.app for Chinese lookups")
                    return
                else:
                    logger.info("macOS Dictionary returned no results for Chinese, falling back to CC-CEDICT")
            except Exception as e:
                logger.info(f"macOS Dictionary error ({e}), falling back to CC-CEDICT")
        
        # Fall back to CC-CEDICT
        try:
            from havachat.enrichers.vocab.chinese.cc_cedict_parser import cc_cedict
            
            if not cc_cedict:
                logger.warning("CC-CEDICT dictionary not loaded")
                return
            
            # Build lookup dictionary: Chinese -> English
            for entry in cc_cedict:
                simplified = entry.get("simplified")
                traditional = entry.get("traditional")
                english = entry.get("english")
                
                if simplified and english:
                    self.lookup_dict[simplified] = english
                if traditional and english and traditional != simplified:
                    self.lookup_dict[traditional] = english
            
            logger.info(f"Loaded {len(self.lookup_dict)} CC-CEDICT entries")
        
        except ImportError as e:
            logger.warning(f"Failed to import CC-CEDICT parser: {e}")
        except Exception as e:
            logger.warning(f"Failed to load CC-CEDICT dictionary: {e}")
    
    def tokenize_and_lookup(self, text: str) -> List[Tuple[str, str, Optional[str]]]:
        """Tokenize text using spaCy and look up each word.
        
        If macdict is available, uses macOS Dictionary for lookups.
        Otherwise uses CC-CEDICT lookup dictionary.
        
        Args:
            text: Text to tokenize and look up
        
        Returns:
            List of (word, pos, definition) tuples
        """
        if not self.nlp:
            logger.warning(f"spaCy model not loaded for {self.language}")
            return []
        
        # Parse text with spaCy
        doc: Doc = self.nlp(text)
        results = []
        
        for token in doc:
            # Skip whitespace and punctuation
            if token.is_space or token.is_punct:
                continue
            
            # Use lemma for dictionary lookup (base form)
            pos = token.pos_
            
            # Look up definition
            if self.use_macdict and HAS_MACDICT:
                # Use macOS Dictionary
                try:
                    definition = macdict_lookup_word(token.text)
                    # Clean up the definition (remove HTML tags, limit length)
                    if definition:
                        # Extract just the first definition if multiple exist
                        import re
                        # Remove HTML tags
                        definition = re.sub(r'<[^>]+>', '', definition)
                        # Take first line/definition
                        definition = definition.split('\n')[0].strip()
                        # Limit length
                        if len(definition) > 200:
                            definition = definition[:197] + "..."
                except Exception as e:
                    logger.debug(f"macdict lookup failed for '{token.text}': {e}")
                    definition = None
            else:
                # Use CC-CEDICT dictionary
                lemma = token.lemma_
                definition = self.lookup_dict.get(lemma) or self.lookup_dict.get(token.text)
            
            results.append((token.text, pos, definition))
        
        return results
    
    def size(self) -> int:
        """Get the number of entries in the dictionary.
        
        Returns:
            Number of entries (0 if using macdict)
        """
        if self.use_macdict:
            return 0  # macdict is dynamic, no fixed size
        return len(self.lookup_dict)


class DictionaryFactory:
    """Factory for creating language-specific dictionaries."""
    
    _dictionaries: Dict[str, Dictionary] = {}
    
    @classmethod
    def get_dictionary(cls, language: str) -> Optional[Dictionary]:
        """Get or create a dictionary for the specified language.
        
        Checks USE_DICTIONARY_LOOKUP environment variable. If false or not set,
        returns None to disable dictionary lookups.
        
        Args:
            language: ISO 639-1 language code (e.g., "zh", "ja", "fr")
        
        Returns:
            Dictionary instance for the language, or None if not available or disabled
        """
        # Check if dictionary lookup is enabled
        use_dictionary = os.getenv("USE_DICTIONARY_LOOKUP", "true").lower() == "true"
        if not use_dictionary:
            logger.info("Dictionary lookup disabled via USE_DICTIONARY_LOOKUP environment variable")
            return None
        
        # Return cached dictionary if available
        if language in cls._dictionaries:
            return cls._dictionaries[language]
        
        # Create new dictionary based on language
        dictionary = None
        
        if language == "zh":
            try:
                dictionary = CCCEDICTDictionary()
                source = "macOS Dictionary.app" if dictionary.use_macdict else f"CC-CEDICT ({dictionary.size()} entries)"
                logger.info(f"Created Chinese dictionary using {source}")
            except Exception as e:
                logger.warning(f"Failed to create Chinese dictionary: {e}")
        
        # Add more language dictionaries here in the future:
        # elif language == "ja":
        #     dictionary = EDICTDictionary()
        # elif language == "fr":
        #     dictionary = FreeDictDictionary()
        
        else:
            logger.info(f"No dictionary available for language: {language}")
        
        # Cache and return
        if dictionary:
            cls._dictionaries[language] = dictionary
        
        return dictionary
    
    @classmethod
    def clear_cache(cls) -> None:
        """Clear the dictionary cache (useful for testing)."""
        cls._dictionaries.clear()
