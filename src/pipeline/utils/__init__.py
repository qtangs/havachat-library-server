"""
Shared utilities for the pre-generation pipeline.

This package contains reusable components used across all pipeline stages:
- llm_client.py: Instructor-wrapped OpenAI/Anthropic client with retry logic
- file_io.py: JSON/TSV/CSV/Markdown parsing and file operations
- logging_config.py: Structured JSON logging for pipeline observability
- similarity.py: Semantic similarity for scenario deduplication
"""

__all__ = [
    "llm_client",
    "file_io",
    "logging_config",
    "similarity",
]
