"""Vocabulary enrichers for different languages."""

from .chinese import ChineseVocabEnricher
from .japanese import JapaneseVocabEnricher
from .french import FrenchVocabEnricher

__all__ = [
    "ChineseVocabEnricher",
    "JapaneseVocabEnricher",
    "FrenchVocabEnricher",
]
