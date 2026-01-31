"""Centralized system prompts for the pre-generation havachat.

This package contains all LLM system prompts used throughout the pipeline:
- content_generator_prompts.py: Chain-of-thought content generation
- learning_item_prompts.py: Learning item generation (pronunciation, idioms, etc.)
- mandarin/grammar_prompts.py: Mandarin grammar and vocabulary enrichment

Organizing prompts centrally makes them easier to:
- Find and update
- Version control
- Share across modules
- Test and validate
"""
