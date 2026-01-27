"""
Pre-generation Pipeline for Learning Content

This package contains the batch processing pipeline for generating and enriching
learning content (vocabulary, grammar, conversations, questions) from source materials.

**Version**: 0.1.0
**Python**: >=3.14
**Key Dependencies**: langgraph, instructor, pydantic, docling
"""

__version__ = "0.1.0"
__author__ = "Havachat"

# Pipeline metadata
SUPPORTED_LANGUAGES = ["zh", "ja", "fr", "en", "es"]
LEVEL_SYSTEMS = {
    "zh": "hsk",  # HSK 1-6
    "ja": "jlpt",  # JLPT N5-N1
    "fr": "cefr",  # CEFR A1-C2
    "en": "cefr",
    "es": "cefr",
}

__all__ = [
    "__version__",
    "__author__",
    "SUPPORTED_LANGUAGES",
    "LEVEL_SYSTEMS",
]
