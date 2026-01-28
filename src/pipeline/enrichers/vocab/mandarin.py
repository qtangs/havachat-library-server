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

import csv
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

import opencc
from pydantic import BaseModel, Field
from pypinyin import Style, pinyin

from src.pipeline.enrichers.base import BaseEnricher
from src.pipeline.utils.azure_translation import AzureTranslationHelper
from src.pipeline.utils.llm_client import LLMClient
from src.pipeline.utils.romanization import (
    clean_sense_marker,
    extract_sense_marker,
    get_mandarin_pinyin,
    translate_chinese_pos,
)
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
        min_length=3,
        max_length=5,
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
OPTIMIZED_SYSTEM_PROMPT = """You are an expert Mandarin Chinese teacher specializing in vocabulary pedagogy.
Your task is to enrich vocabulary entries with accurate, learner-friendly information.

CRITICAL INSTRUCTIONS:
1. **NO PINYIN**: Do NOT include pinyin/romanization in your response. It will be added automatically.
2. **CHINESE ONLY EXAMPLES**: Provide examples in Chinese characters ONLY. Do NOT add pinyin or English translations.
3. **Clarity**: Explanations must be clear and suitable for learners at the specified level.
4. **Examples**: Provide 3-5 contextual example sentences using ONLY Chinese characters.
5. **Polysemy**: If a word has multiple meanings, specify the sense gloss in sense_gloss.
6. **Part of Speech**: Identify the part of speech (noun, verb, adjective, etc.).

**Understanding Chinese POS (词性) Labels:**
- 名 = noun, 动 = verb, 形 = adjective, 副 = adverb, 代 = pronoun
- 数 = numeral, 量 = measure word, 介 = preposition, 助 = particle
- 叹 = interjection, 连 = conjunction

**Understanding Sense Markers:**
Words with trailing numbers (e.g., 本1, 会1) indicate disambiguation.
Remove the number, but note the specific sense gloss in sense_gloss.

**Example Response Format:**
{
  "definition": "and; together with; with",
  "examples": [
    "我和你。",
    "我和吃苹果。",
    "他和看书。"
  ],
  "sense_gloss": "and/with",
  "pos": "verb"
}

Remember: Chinese characters ONLY in examples. No pinyin. No English translations.
"""


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
    ):
        """Initialize Mandarin enricher with Azure Translation.
        
        Args:
            llm_client: Optional LLM client for enrichment
            max_retries: Maximum retry attempts (default: 3)
            manual_review_dir: Directory for manual review queue
        """
        super().__init__(llm_client, max_retries, manual_review_dir)
        
        # Initialize Azure Translation helper
        try:
            self.azure_translator = AzureTranslationHelper()
            logger.info("Azure Translation initialized successfully")
        except ValueError as e:
            logger.warning(f"Azure Translation not available: {e}")
            self.azure_translator = None

    @property
    def system_prompt(self) -> str:
        """Get optimized Mandarin-specific system prompt."""
        return OPTIMIZED_SYSTEM_PROMPT

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
        source_path = Path(source_path)

        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        items = []

        with open(source_path, "r", encoding="utf-8") as f:
            # Skip BOM if present
            first_line = f.readline()
            if first_line.startswith("\ufeff"):
                first_line = first_line[1:]

            # Parse as TSV
            f.seek(0)
            reader = csv.DictReader(f, delimiter="\t")

            for i, row in enumerate(reader, start=1):
                # Handle various column name formats
                word = (
                    row.get("Word")
                    or row.get("word")
                    or row.get("WORD")
                    or row.get("汉字")
                )
                pos = (
                    row.get("Part of Speech")
                    or row.get("POS")
                    or row.get("pos")
                    or row.get("词性")
                )

                if not word:
                    logger.warning(f"Row {i} missing 'Word' column, skipping: {row}")
                    continue

                # Clean sense marker from word (e.g., "本1" → "本")
                clean_word = clean_sense_marker(word.strip())
                sense_marker = extract_sense_marker(word.strip())

                # Translate Chinese POS to English if needed
                english_pos = translate_chinese_pos(pos.strip()) if pos else None

                items.append(
                    {
                        "target_item": clean_word,
                        "pos": english_pos,
                        "original_pos": pos.strip() if pos else None,
                        "sense_marker": sense_marker,
                        "source_row": i,
                    }
                )

        logger.info(
            f"Parsed {len(items)} items from {source_path}",
            extra={"source": str(source_path), "item_count": len(items)},
        )

        return items

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
        if not self.llm_client:
            logger.warning("LLM client not available, skipping enrichment")
            return None

        target_item = item.get("target_item", "")
        
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
            
            # Step 6: Format examples with pinyin and translations
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
3. Create 3-5 original example sentences in CHINESE ONLY (no pinyin, no English)
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
                f"Expected 3-5 examples, got {len(enriched_data.examples)} "
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

