"""Optimized Japanese vocabulary enricher with cost reduction.

Cost reduction strategy (same as Mandarin):
1. Use minimal LLM response model (only explanation, examples, pos)
2. Examples are Japanese-only (no romaji or translations in LLM response)
3. Use Azure Translation API for English translations (2M free chars/month)
4. Use Python libraries for:
   - Romaji romanization (pykakasi)
   - Furigana generation (if needed)
5. Assemble final LearningItem from all sources

Expected cost savings: ~60-70% token reduction per item
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field
from pykakasi import kakasi

from src.havachat.enrichers.base import BaseEnricher
from src.havachat.utils.azure_translation import AzureTranslationHelper
from src.havachat.utils.llm_client import LLMClient
from src.havachat.utils.romanization import get_japanese_romaji
from src.havachat.validators.schema import Category, Example, LearningItem, LevelSystem

logger = logging.getLogger(__name__)


class JapaneseEnrichedVocab(BaseModel):
    """French vocab enrichment."""
    
    definition: str = Field(
        ...,
        description="Clear English definition suitable for learners, to be used in flashcards"
    )
    examples: List[str] = Field(
        ...,
        min_length=2,
        max_length=3,
        description="Example sentences in Japanese ONLY (no romaji, no English translation). Example: '学校に行きます。'"
    )
    pos: Optional[str] = Field(
        None, 
        description="Part of speech: noun, verb, adjective, etc."
    )


# Optimized system prompt - no romaji or translation instructions
OPTIMIZED_SYSTEM_PROMPT = """You are an expert Japanese teacher specializing in vocabulary pedagogy.
Your task is to enrich vocabulary entries with accurate, learner-friendly information.

CRITICAL INSTRUCTIONS:
1. **NO ROMAJI**: Do NOT include romaji/romanization in your response. It will be added automatically.
2. **JAPANESE ONLY EXAMPLES**: Provide examples in Japanese characters ONLY. Do NOT add romaji or English translations.
3. **Clarity**: Explanations must be clear and suitable for learners at the specified level.
4. **Examples**: Provide 2-3 contextual example sentences using ONLY Japanese characters (hiragana, katakana, kanji).
5. **Part of Speech**: Identify the part of speech (noun, verb, adjective, etc.).

**Example Response Format:**
{
  "definition": "school",
  "examples": [
    "学校に行きます。",
    "私の学校は大きいです。",
    "学校で友達と会います。"
  ],
  "pos": "noun"
}

Remember: Japanese characters ONLY in examples. No romaji. No English translations.
"""


class JapaneseVocabEnricher(BaseEnricher):
    """Optimized enricher for Japanese vocabulary with cost reduction.

    Expected input format: JSON with word, furigana, romaji, level fields
    
    Optimizations:
    - Minimal LLM response (explanation, examples, pos only)
    - Japanese-only examples (no romaji/translations in LLM response)
    - Azure Translation for English translations
    - Python libraries for romaji generation
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        max_retries: int = 3,
        manual_review_dir: Optional[Union[str, Path]] = None,
        skip_llm: bool = False,
        skip_translation: bool = False,
    ):
        """Initialize Japanese enricher with Azure Translation.
        
        Args:
            llm_client: Optional LLM client for enrichment
            max_retries: Maximum retry attempts (default: 3)
            manual_review_dir: Directory for manual review queue
            skip_llm: Skip LLM enrichment (default: False)
            skip_translation: Skip translation service (default: False)
        """
        super().__init__(llm_client, max_retries, manual_review_dir, skip_llm, skip_translation)
        
        # Initialize Azure Translation helper unless skip_translation is True
        if not skip_translation:
            try:
                self.azure_translator = AzureTranslationHelper()
                logger.info("Azure Translation initialized successfully")
            except ValueError as e:
                logger.warning(f"Azure Translation not available: {e}")
                self.azure_translator = None
        else:
            logger.info("Translation service skipped (--skip-translation)")
            self.azure_translator = None

    @property
    def system_prompt(self) -> str:
        """Get optimized Japanese-specific system prompt."""
        return OPTIMIZED_SYSTEM_PROMPT

    def parse_source(self, source_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """Parse JSON file with Japanese vocabulary.

        Args:
            source_path: Path to JSON file

        Returns:
            List of dictionaries with vocabulary data

        Raises:
            FileNotFoundError: If source file doesn't exist
            json.JSONDecodeError: If JSON format is invalid
        """
        return parse_japanese_vocab_json(source_path)

    def detect_missing_fields(self, item: Dict[str, Any]) -> List[str]:
        """Detect which fields need enrichment.

        For optimized Japanese enricher:
        - Always need: definition, examples (LLM)
        - Optionally need: pos (if not provided)
        - Auto-generated: romanization, translations

        Args:
            item: Item dictionary

        Returns:
            List of field names needing enrichment
        """
        missing = []

        # Always need these from LLM
        if not item.get("definition"):
            missing.append("definition")

        if not item.get("examples") or len(item.get("examples", [])) < 3:
            missing.append("examples")

        # POS is optional but helpful
        if not item.get("pos"):
            missing.append("pos")

        return missing

    def enrich_item(self, item: Dict[str, Any]) -> Optional[LearningItem]:
        """Enrich a single Japanese vocabulary item using optimized strategy.
        
        Process:
        1. Get minimal LLM response (explanation, Japanese-only examples, pos)
        2. Use pykakasi to generate romanization if needed
        3. Use Azure Translation to translate examples to English
        4. Assemble complete LearningItem
        
        Args:
            item: Source item dictionary
            
        Returns:
            LearningItem with all fields populated, or None if enrichment fails
        """
        target_item = item.get("target_item", "")
        
        # If skip_llm is True, generate minimal structure with UUID only
        if self.skip_llm:
            logger.info(f"Skipping LLM enrichment for '{target_item}' (--skip-llm mode)")
            
            # Generate romaji if not present
            romanization = item.get("romanization") or get_japanese_romaji(target_item)
            
            # Create minimal item with UUID
            minimal_item = LearningItem(
                id=str(uuid4()),
                language="ja",
                category=Category.VOCAB,
                target_item=target_item,
                definition=item.get("definition", ""),  # Empty or from source
                examples=[],  # Empty examples
                sense_gloss=None,
                romanization=romanization,
                pos=item.get("pos"),
                lemma=None,
                aliases=[],
                level_system=LevelSystem.JLPT,
                level_min=item.get("level_min", "N5"),
                level_max=item.get("level_max", "N5"),
                created_at=datetime.now(UTC),
                version="1.0.0",
                source_file=item.get("source_file"),
            )
            
            return minimal_item
        
        if not self.llm_client:
            logger.warning("LLM client not available, skipping enrichment")
            return None

        try:
            # Step 1: Get minimal LLM response (Japanese-only examples)
            missing_fields = self.detect_missing_fields(item)
            prompt = self.build_prompt(item, missing_fields)
            
            llm_response: JapaneseEnrichedVocab = self.llm_client.generate(
                prompt=prompt,
                response_model=JapaneseEnrichedVocab,
                use_cache=True
            )
            
            logger.debug(f"LLM response for '{target_item}': {len(llm_response.examples)} examples")
            
            # Step 2: Generate romaji if not present
            romanization = item.get("romanization") or get_japanese_romaji(target_item)
            
            # Step 3: Translate examples to English using Azure Translation
            example_translations = []
            if self.azure_translator:
                try:
                    example_translations = self.azure_translator.translate_batch(
                        texts=llm_response.examples,
                        from_language="ja",
                        to_language="en"
                    )
                    logger.debug(f"Translated {len(example_translations)} examples")
                except Exception as e:
                    logger.error(f"Azure Translation failed: {e}")
                    # Fall back to empty translations
                    example_translations = ["" for _ in llm_response.examples]
            else:
                logger.warning("Azure Translation not available, examples will have no translations")
                example_translations = ["" for _ in llm_response.examples]
            
            # Step 4: Format examples with romaji and translations
            formatted_examples = self._format_examples(
                llm_response.examples,
                example_translations
            )
            
            # Step 5: Assemble complete LearningItem
            enriched_item = LearningItem(
                id=str(uuid4()),
                language="ja",
                category=Category.VOCAB,
                target_item=target_item,
                definition=llm_response.definition,
                examples=formatted_examples,
                sense_gloss=None,  # Japanese enricher doesn't use sense_gloss
                romanization=romanization,
                pos=llm_response.pos,
                lemma=None,
                aliases=[],  # Could add kanji variants if needed
                level_system=LevelSystem.JLPT,
                level_min=item.get("level_min", "N5"),
                level_max=item.get("level_max", "N5"),
                created_at=datetime.now(UTC),
                version="1.0.0",
                source_file=item.get("source_file"),
            )
            
            logger.info(
                f"Successfully enriched '{target_item}'",
                extra={
                    "target_item": target_item,
                    "romanization": romanization,
                    "example_count": len(formatted_examples),
                }
            )
            
            return enriched_item
            
        except Exception as e:
            logger.error(
                f"Failed to enrich '{target_item}': {e}",
                exc_info=True,
                extra={"target_item": target_item}
            )
            return None

    def build_prompt(self, item: Dict[str, Any], missing_fields: List[str]) -> str:
        """Build enrichment prompt for minimal LLM response.
        
        Args:
            item: Item dictionary
            missing_fields: Fields to request from LLM
            
        Returns:
            Formatted prompt string
        """
        target_item = item.get("target_item", "")
        meaning = item.get("meaning", "")
        level_min = item.get("level_min", "N5")
        level_max = item.get("level_max", level_min)
        
        prompt = f"""Enrich the following Japanese vocabulary item:

**Word**: {target_item}
**Brief meaning**: {meaning if meaning else "Not provided"}
**Proficiency Level**: {level_min} to {level_max}

**Instructions**:
1. Write a clear, learner-friendly explanation in English (ignore the brief meaning above, generate a full explanation)
2. Identify the part of speech
3. Create 2-3 original example sentences in JAPANESE ONLY (no romaji, no English)

**CRITICAL**: Examples must be Japanese characters ONLY. Example:
- CORRECT: "学校に行きます。"
- INCORRECT: "学校に行きます。(Gakkou ni ikimasu.) - I go to school."

Remember: We will add romaji and English translations automatically later.
"""
        
        return prompt

    def _format_examples(
        self, 
        japanese_examples: List[str], 
        translations: List[str]
    ) -> List[Example]:
        """Format examples with romaji and English translations.
        
        Args:
            japanese_examples: List of Japanese-only example sentences
            translations: List of English translations (same order)
            
        Returns:
            List of Example objects with text, translation, and empty media_urls
        """
        formatted = []
        
        for japanese, translation in zip(japanese_examples, translations):            
            example = Example(
                text=japanese,
                translation=translation if translation else "",
                media_urls=[]
            )
            formatted.append(example)
        
        return formatted

    def validate_output(self, item: Dict[str, Any], enriched_data: LearningItem) -> bool:
        """Validate enriched Japanese vocabulary item.
        
        Args:
            item: Original item dictionary
            enriched_data: Enriched LearningItem
            
        Returns:
            True if validation passes
        """
        # Check romanization
        if not enriched_data.romanization:
            logger.warning(f"Missing romanization for '{enriched_data.target_item}'")
            return False

        # Check examples
        if not (3 <= len(enriched_data.examples) <= 5):
            logger.warning(
                f"Expected 2-3 examples, got {len(enriched_data.examples)} "
                f"for '{enriched_data.target_item}'"
            )
            return False

        # Check that examples contain Japanese characters
        for example in enriched_data.examples:
            has_japanese = any(
                # Hiragana, Katakana, or Kanji
                ("\u3040" <= char <= "\u309F")  # Hiragana
                or ("\u30A0" <= char <= "\u30FF")  # Katakana
                or ("\u4E00" <= char <= "\u9FFF")  # Kanji
                for char in example
            )

            if not has_japanese:
                logger.warning(
                    f"Example doesn't contain Japanese: '{example}' "
                    f"for '{enriched_data.target_item}'"
                )
                return False

        # Check language
        if enriched_data.language != "ja":
            logger.warning(f"Expected language='ja', got '{enriched_data.language}'")
            return False

        return True

    def get_translation_usage(self) -> Optional[dict]:
        """Get Azure Translation usage statistics.
        
        Returns:
            Dictionary with usage stats, or None if Azure Translation not available
        """
        if self.azure_translator:
            return self.azure_translator.get_usage_summary()
        return None

    @staticmethod
    def _normalize_jlpt_level(level: str | None) -> str:
        """Normalize JLPT level to standard format.

        Args:
            level: Input level (N5, n5, 5, JLPT5, etc.)

        Returns:
            Normalized level (N5, N4, N3, N2, N1)
        """
        if not level:
            return "N5"  # Default to beginner

        level = str(level).upper().strip()

        # Extract number
        if "5" in level:
            return "N5"
        elif "4" in level:
            return "N4"
        elif "3" in level:
            return "N3"
        elif "2" in level:
            return "N2"
        elif "1" in level:
            return "N1"
        else:
            return "N5"  # Default
