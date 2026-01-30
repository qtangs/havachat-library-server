"""Optimized Mandarin Chinese vocabulary enricher with cost reduction.

Cost reduction strategy:
1. Use minimal LLM response model (only explanation, examples, sense_gloss, pos)
2. Examples are Chinese-only (no pinyin or translations in LLM response)
3. Use Azure Translation API for English translations (2M free chars/month)
4. Use Python libraries for:
   - Pinyin romanization (pypinyin)
   - Traditional Chinese (opencc)
   - Numeric pinyin (pypinyin with TONE3 style)
5. Assemble final LearningItem from all sources

Expected cost savings: ~60-70% token reduction per item
"""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

import opencc
from pydantic import BaseModel, Field
from pypinyin import Style, pinyin

from src.pipeline.enrichers.base import BaseEnricher
from src.pipeline.parsers.source_parsers import parse_mandarin_vocab_tsv
from src.pipeline.utils.azure_translation import AzureTranslationHelper
from src.pipeline.utils.llm_client import LLMClient
from src.pipeline.utils.romanization import get_mandarin_pinyin
from src.pipeline.validators.schema import Category, Example, LearningItem, LevelSystem

logger = logging.getLogger(__name__)


class ChineseEnrichedVocab(BaseModel):
    """Chinese vocab enrichment."""
    
    definition: str = Field(
        ...,
        description="Clear English definition suitable for learners, to be used in flashcards"
    )
    examples: List[str] = Field(
        ...,
        min_length=2,
        max_length=3,
        description="Example sentences in Chinese ONLY (no pinyin, no English translation). Example: '我去银行。'"
    )
    sense_gloss: Optional[str] = Field(
        None,
        description="Sense gloss for polysemous words, for example: “and/with” for 和1 (hé) (conjunction/preposition). Other sense glosses for “和” are “harmony” (noun) or “sum” (noun) in math."
    )
    pos: Optional[str] = Field(
        None, 
        description="Part of speech: noun, verb, adjective, etc."
    )


# Optimized system prompt - no pinyin or translation instructions
class ChineseEnrichedVocab(BaseModel):
    """Chinese vocab enrichment."""
    
    definition: str = Field(
        ...,
        description="Clear English definition suitable for learners, to be used in flashcards"
    )
    examples: List[str] = Field(
        ...,
        min_length=2,
        max_length=3,
        description="Example sentences in Chinese ONLY (no pinyin, no English translation). Example: '我去银行。'"
    )
    sense_gloss: Optional[str] = Field(
        None,
        description='Sense gloss for polysemous words, for example: "and/with" for 和1 (hé) (conjunction/preposition). Other sense glosses for "和" are "harmony" (noun) or "sum" (noun) in math.'
    )
    pos: Optional[str] = Field(
        None, 
        description="Part of speech: noun, verb, adjective, etc."
    )


class MandarinVocabEnricher(BaseEnricher):
    """Optimized enricher for Mandarin vocabulary with cost reduction.

    Expected input format: TSV with "Word\tPart of Speech" columns
    
    Optimizations:
    - Minimal LLM response (explanation, examples, sense_gloss, pos only)
    - Chinese-only examples (no pinyin/translations in LLM response)
    - Azure Translation for English translations
    - Python libraries for pinyin, traditional Chinese, numeric pinyin
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        max_retries: int = 3,
        manual_review_dir: Optional[Union[str, Path]] = None,
        skip_llm: bool = False,
        skip_translation: bool = False,
    ):
        """Initialize Mandarin enricher with Azure Translation.
        
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
        """Get optimized Mandarin-specific system prompt."""
        return MANDARIN_VOCAB_SYSTEM_PROMPT

    def parse_source(self, source_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """Parse TSV file with Word and Part of Speech columns.

        Args:
            source_path: Path to TSV file

        Returns:
            List of dictionaries with 'word' and 'pos' keys

        Raises:
            FileNotFoundError: If source file doesn't exist
            ValueError: If TSV format is invalid
        """
        return parse_mandarin_vocab_tsv(source_path)

    def detect_missing_fields(self, item: Dict[str, Any]) -> List[str]:
        """Detect which fields need enrichment.

        For optimized Mandarin enricher:
        - Always need: definition, examples (LLM)
        - Optionally need: sense_gloss (if polysemous), pos (if not provided)
        - Auto-generated: romanization, traditional, numeric_pinyin, translations

        Args:
            item: Item dictionary with 'target_item' and optional existing fields

        Returns:
            List of field names needing enrichment
        """
        missing = []

        # Always need these from LLM
        if not item.get("definition"):
            missing.append("definition")

        if not item.get("examples") or len(item.get("examples", [])) < 3:
            missing.append("examples")

        # Check if sense_gloss is needed (polysemous words)
        if item.get("sense_marker") or self._detect_polysemy(item.get("target_item", "")):
            if not item.get("sense_gloss"):
                missing.append("sense_gloss")

        # POS is optional but helpful
        if not item.get("pos"):
            missing.append("pos")

        return missing

    def enrich_item(self, item: Dict[str, Any]) -> Optional[LearningItem]:
        """Enrich a single Mandarin vocabulary item using optimized strategy.
        
        Process:
        1. Get minimal LLM response (explanation, Chinese-only examples, sense_gloss, pos)
        2. Use pypinyin to generate romanization (tone marks and numeric)
        3. Use opencc to get traditional Chinese
        4. Use Azure Translation to translate examples to English
        5. Assemble complete LearningItem
        
        Args:
            item: Source item dictionary
            
        Returns:
            LearningItem with all fields populated, or None if enrichment fails
        """
        target_item = item.get("target_item", "")
        
        # If skip_llm is True, generate minimal structure with UUID only
        if self.skip_llm:
            logger.info(f"Skipping LLM enrichment for '{target_item}' (--skip-llm mode)")
            
            # Generate pinyin
            romanization = get_mandarin_pinyin(target_item)
            numeric_pinyin = self._get_numeric_pinyin(target_item)
            traditional = self._get_traditional(target_item)
            
            # Build aliases array
            aliases = []
            if traditional and traditional != target_item:
                aliases.append(traditional)
            if numeric_pinyin and numeric_pinyin != romanization:
                aliases.append(numeric_pinyin)
            
            # Create minimal item with UUID
            minimal_item = LearningItem(
                id=str(uuid4()),
                language="zh",
                category=Category.VOCAB,
                target_item=target_item,
                definition=item.get("definition", ""),  # Empty or from source
                examples=[],  # Empty examples
                sense_gloss=item.get("sense_gloss"),
                romanization=romanization,
                pos=item.get("pos"),
                lemma=None,
                aliases=aliases,
                level_system=LevelSystem.HSK,
                level_min=item.get("level_min", "HSK1"),
                level_max=item.get("level_max", "HSK1"),
                created_at=datetime.now(UTC),
                version="1.0.0",
                source_file=item.get("source_file"),
            )
            
            return minimal_item
        
        if not self.llm_client:
            logger.warning("LLM client not available, skipping enrichment")
            return None

        try:
            # Step 1: Get minimal LLM response (Chinese-only examples)
            missing_fields = self.detect_missing_fields(item)
            prompt = self.build_prompt(item, missing_fields)
            
            llm_response: ChineseEnrichedVocab = self.llm_client.generate(
                prompt=prompt,
                response_model=ChineseEnrichedVocab,
                use_cache=True
            )
            
            logger.debug(f"LLM response for '{target_item}': {len(llm_response.examples)} examples")
            
            # Step 2: Generate pinyin with tone marks (default)
            romanization = get_mandarin_pinyin(target_item)
            
            # Step 3: Generate numeric pinyin (ai4, ba4 ba5)
            numeric_pinyin = self._get_numeric_pinyin(target_item)
            
            # Step 4: Get traditional Chinese
            traditional = self._get_traditional(target_item)
            
            # Step 5: Translate examples to English using Azure Translation
            example_translations = []
            if self.azure_translator:
                try:
                    example_translations = self.azure_translator.translate_batch(
                        texts=llm_response.examples,
                        from_language="zh",
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
            
            # Step 6: Format examples with translations
            formatted_examples = self._format_examples(
                llm_response.examples,
                example_translations
            )
            
            # Step 7: Build aliases array [traditional, numeric_pinyin]
            aliases = []
            if traditional and traditional != target_item:
                aliases.append(traditional)
            if numeric_pinyin and numeric_pinyin != romanization:
                aliases.append(numeric_pinyin)
            
            # Step 8: Assemble complete LearningItem
            enriched_item = LearningItem(
                id=str(uuid4()),
                language="zh",
                category=Category.VOCAB,
                target_item=target_item,
                definition=llm_response.definition,
                examples=formatted_examples,
                sense_gloss=llm_response.sense_gloss,
                romanization=romanization,
                pos=llm_response.pos or item.get("pos"),
                lemma=None,
                aliases=aliases,
                level_system=LevelSystem.HSK,
                level_min=item.get("level_min", "HSK1"),
                level_max=item.get("level_max", "HSK1"),
                created_at=datetime.now(UTC),
                version="1.0.0",
                source_file=item.get("source_file"),
            )
            
            logger.info(
                f"Successfully enriched '{target_item}'",
                extra={
                    "target_item": target_item,
                    "romanization": romanization,
                    "traditional": traditional,
                    "numeric_pinyin": numeric_pinyin,
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
        pos = item.get("pos", "unknown")
        level_min = item.get("level_min", "HSK1")
        level_max = item.get("level_max", level_min)
        
        prompt = f"""Enrich the following Mandarin Chinese vocabulary item:

**Word**: {target_item}
**Part of Speech**: {pos}
**Proficiency Level**: {level_min} to {level_max}

**Instructions**:
1. Write a clear, learner-friendly explanation in English
2. Confirm or correct the part of speech
3. Create 2-3 original example sentences in CHINESE ONLY (no pinyin, no English)
4. If the word has multiple meanings, specify which sense in sense_gloss

**CRITICAL**: Examples must be Chinese characters ONLY. Example:
- CORRECT: "我爱你。"
- INCORRECT: "我爱你。(Wǒ ài nǐ.) - I love you."

Remember: We will add pinyin and English translations automatically later.
"""
        
        return prompt

    def _get_numeric_pinyin(self, text: str) -> str:
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

    def _get_traditional(self, text: str) -> str:
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

    def _format_examples(
        self, 
        chinese_examples: List[str], 
        translations: List[str]
    ) -> List[Example]:
        """Format examples with pinyin and English translations.
        
        Args:
            chinese_examples: List of Chinese-only example sentences
            translations: List of English translations (same order)
            
        Returns:
            List of Example objects with text, translation, and empty media_urls
        """
        formatted = []
        
        for chinese, translation in zip(chinese_examples, translations):
            example = Example(
                text=chinese,
                translation=translation if translation else "",
                media_urls=[]
            )
            formatted.append(example)
        
        return formatted

    def _detect_polysemy(self, target_item: str) -> bool:
        """Detect if a word has multiple distinct meanings.
        
        Args:
            target_item: Chinese word
            
        Returns:
            True if polysemy likely, False otherwise
        """
        # Single characters often have multiple meanings
        if len(target_item) == 1:
            return True

        # Common polysemous words
        polysemous_words = {"打", "看", "上", "下", "得", "过", "行", "会", "和"}

        return target_item in polysemous_words

    def validate_output(self, item: Dict[str, Any], enriched_data: LearningItem) -> bool:
        """Validate enriched Mandarin vocabulary item.
        
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

        # Check that examples contain Chinese characters
        for example in enriched_data.examples:
            if not any("\u4e00" <= char <= "\u9fff" for char in example):
                logger.warning(
                    f"Example doesn't contain Chinese: '{example}' "
                    f"for '{enriched_data.target_item}'"
                )
                return False

        # Check language
        if enriched_data.language != "zh":
            logger.warning(f"Expected language='zh', got '{enriched_data.language}'")
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

