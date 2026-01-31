"""Vocabulary enrichers for different languages."""

from .mandarin import MandarinVocabEnricher
from .japanese import JapaneseVocabEnricher
from .french import FrenchVocabEnricher

__all__ = [
    "MandarinVocabEnricher",
    "JapaneseVocabEnricher",
    "FrenchVocabEnricher",
]
