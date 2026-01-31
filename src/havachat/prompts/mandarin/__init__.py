"""Prompts for Mandarin Chinese enrichment."""

from .vocab_prompts import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    build_vocab_enrichment_prompt,
)

__all__ = [
    "SYSTEM_PROMPT",
    "USER_PROMPT_TEMPLATE",
    "build_vocab_enrichment_prompt",
]
