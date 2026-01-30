"""Mandarin Chinese grammar enricher.

This enricher processes official Chinese grammar lists from CSV files with the format:
类别,类别名称,细目,语法内容

Example:
词类,动词,能愿动词,会、能

The enricher:
1. Parses CSV to extract grammar patterns
2. Splits multi-item patterns (e.g., "会、能") into individual items to avoid "mega-items"
3. Uses LLM to generate definitions and examples
4. Validates granularity to ensure narrow-scope learning items
"""

import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field

from pipeline.enrichers.base import BaseEnricher
from pipeline.parsers.source_parsers import parse_mandarin_grammar_csv
from pipeline.prompts.mandarin.grammar_prompts import MANDARIN_GRAMMAR_SYSTEM_PROMPT
from pipeline.utils.azure_translation import AzureTranslationHelper
from pipeline.utils.llm_client import LLMClient
from pipeline.utils.romanization import get_mandarin_pinyin
from pipeline.validators.schema import Category, Example, LearningItem, LevelSystem

logger = logging.getLogger(__name__)


class ChineseGrammarEnriched(BaseModel):
    """Grammar enrichment response from LLM."""
    
    definition: str = Field(
        ...,
        description="Clear English definition explaining the grammar pattern, suitable for learners"
    )
    examples: List[str] = Field(
        ...,
        min_length=2,
        max_length=3,
        description="Example sentences in Chinese ONLY (no pinyin, no English translation)"
    )


class ChineseGrammarEnriched(BaseModel):
    """Grammar enrichment response from LLM."""
    
    definition: str = Field(
        ...,
        description="Clear English definition explaining the grammar pattern, suitable for learners"
    )
    examples: List[str] = Field(
        ...,
        min_length=2,
        max_length=3,
        description="Example sentences in Chinese ONLY (no pinyin, no English translation)"
    )


class MandarinGrammarEnricher(BaseEnricher):
    """Enricher for Mandarin grammar patterns from official CSV lists.
    
    Expected input format: CSV with columns "类别,类别名称,细目,语法内容"
    
    Key features:
    - Automatic pattern splitting to avoid mega-items (e.g., "会、能" → ["会", "能"])
    - Grammar-specific validation (narrow scope, clear target_item)
    - Azure Translation for English translations of examples
    - Auto-generated pinyin using pypinyin
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        max_retries: int = 3,
        manual_review_dir: Optional[Union[str, Path]] = None,
        skip_llm: bool = False,
        skip_translation: bool = False,
    ):
        """Initialize Mandarin grammar enricher.
        
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
        """Get grammar-specific system prompt."""
        return MANDARIN_GRAMMAR_SYSTEM_PROMPT

    def parse_source(self, source_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """Parse CSV file with grammar patterns.
        
        Expected format: 类别,类别名称,细目,语法内容
        
        Example rows:
        - 词类,动词,能愿动词,会、能
        - 词类,代词,人称代词,我、你、您、他、她
        
        Multi-item patterns (separated by 、) are split into individual items.
        
        Args:
            source_path: Path to CSV file
            
        Returns:
            List of dictionaries with 'type', 'subtype', 'detail', 'pattern' keys
            
        Raises:
            FileNotFoundError: If source file doesn't exist
            ValueError: If CSV format is invalid
        """
        return parse_mandarin_grammar_csv(source_path)

    def detect_missing_fields(self, item: Dict[str, Any]) -> List[str]:
        """Detect fields that need enrichment.
        
        For grammar items, we always need to enrich:
        - definition: Grammar explanation
        - examples: Usage examples
        
        Args:
            item: Grammar pattern item from parse_source()
            
        Returns:
            List of field names requiring enrichment
        """
        missing = []
        
        # Always need definition and examples for grammar
        if "definition" not in item or not item.get("definition"):
            missing.append("definition")
        if "examples" not in item or not item.get("examples"):
            missing.append("examples")
        
        return missing

    def build_prompt(
        self,
        item: Dict[str, Any],
        missing_fields: List[str],
        language: str,
        level: str,
    ) -> str:
        """Build enrichment prompt for grammar pattern.
        
        Args:
            item: Grammar pattern item
            missing_fields: Fields requiring enrichment
            language: ISO 639-1 language code (e.g., "zh")
            level: Proficiency level (e.g., "HSK1")
            
        Returns:
            User prompt string for LLM
        """
        pattern = item["pattern"]
        grammar_type = item["type"]
        category_name = item["category_name"]
        detail = item["detail"]
        original_content = item.get("original_content", pattern)
        
        prompt = f"""Enrich the following Mandarin grammar pattern:

**Grammar Pattern**: {pattern}
**Type**: {grammar_type} > {category_name}"""
        
        if detail:
            prompt += f"\n**Detail**: {detail}"
        
        prompt += f"\n**Original Group**: {original_content}"
        prompt += f"\n**Target Level**: {level}"
        
        prompt += """

**CRITICAL**: This is a SINGLE, SPECIFIC grammar pattern. Do NOT create a "mega-item" that covers multiple patterns or overly broad explanations.

**Required**:
1. **Definition**: Explain the grammatical function and usage of THIS SPECIFIC pattern
2. **Examples**: Provide 2-3 example sentences in Chinese characters ONLY (no pinyin, no English)

**Granularity Check**:
- If the pattern seems to cover multiple distinct uses, focus on the PRIMARY use
- Keep the scope NARROW and SPECIFIC to this pattern
- Examples should clearly demonstrate THIS pattern, not related patterns

Provide your response in the format:
{
  "definition": "...",
  "examples": ["...", "...", "..."]
}
"""
        
        return prompt

    def validate_output(
        self, enriched: LearningItem, source_item: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """Validate enriched grammar item.
        
        Validation checks:
        1. Category must be "grammar"
        2. Target_item must match the pattern
        3. Granularity check: Definition should be focused and specific
        4. Examples must exist and be in Chinese
        
        Args:
            enriched: Enriched LearningItem
            source_item: Original source item
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Category check
        if enriched.category != Category.GRAMMAR:
            return False, f"Category must be 'grammar', got '{enriched.category}'"
        
        # Target item check
        pattern = source_item["pattern"]
        if enriched.target_item != pattern:
            return False, f"target_item '{enriched.target_item}' doesn't match pattern '{pattern}'"
        
        # Granularity check: Definition shouldn't be overly long (suggests mega-item)
        if len(enriched.definition) > 500:
            logger.warning(
                f"Definition for '{pattern}' is long ({len(enriched.definition)} chars). "
                "Possible mega-item. Consider manual review."
            )
        
        # Examples check
        if not enriched.examples or len(enriched.examples) < 3:
            return False, "Must have at least 3 examples"
        
        # Check examples are in Chinese (contain Chinese characters)
        chinese_pattern = re.compile(r"[\u4e00-\u9fff]+")
        for i, example in enumerate(enriched.examples):
            if not chinese_pattern.search(example.text):
                return False, f"Example {i+1} doesn't contain Chinese characters"
        
        return True, None

    def enrich_item(self, item: Dict[str, Any]) -> Optional[LearningItem]:
        """Enrich a single grammar pattern.
        
        Args:
            item: Grammar pattern item from parse_source() with metadata
            
        Returns:
            Enriched LearningItem or None if enrichment fails
        """
        pattern = item["pattern"]
        language = item.get("language", "zh")
        level = item.get("level", "HSK1")
        level_system = item.get("level_system", LevelSystem.HSK)
        
        # If skip_llm is True, generate minimal structure with UUID only
        if self.skip_llm:
            logger.info(f"Skipping LLM enrichment for grammar pattern '{pattern}' (--skip-llm mode)")
            
            # Get pinyin for the pattern
            pattern_pinyin = get_mandarin_pinyin(pattern)
            
            # Create minimal item with UUID
            minimal_item = LearningItem(
                id=str(uuid4()),
                language=language,
                category=Category.GRAMMAR,
                target_item=pattern,
                definition=item.get("definition", ""),  # Empty or from source
                examples=[],  # Empty examples
                romanization=pattern_pinyin,
                sense_gloss=None,
                lemma=pattern,
                pos=None,
                aliases=[],
                media_urls=[],
                level_system=level_system,
                level_min=level,
                level_max=level,
                created_at=datetime.now(UTC),
                version="1.0.0",
                source_file=str(item.get("source_file", "")),
            )
            
            return minimal_item
        
        # Detect missing fields
        missing_fields = self.detect_missing_fields(item)
        
        if not missing_fields:
            logger.info(f"Grammar pattern '{pattern}' already enriched, skipping")
            return None
        
        # Check if dry-run
        if self.llm_client is None:
            logger.info(f"[DRY RUN] Would enrich grammar pattern: {pattern}")
            return None
        
        # Build prompt
        prompt = self.build_prompt(item, missing_fields, language, level)
        
        # Get LLM enrichment with retries
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"Enriching grammar pattern '{pattern}' (attempt {attempt}/{self.max_retries})"
                )
                
                # Get structured response from LLM
                enriched_data = self.llm_client.generate(
                    prompt=prompt,
                    response_model=ChineseGrammarEnriched,
                    use_cache=True,
                )
                
                # Process examples: Add pinyin and translations
                processed_examples = []
                for example_text in enriched_data.examples:
                    # Get pinyin
                    pinyin_text = get_mandarin_pinyin(example_text)
                    
                    # Get English translation
                    if self.azure_translator:
                        try:
                            translation = self.azure_translator.translate_single(
                                text=example_text,
                                from_language="zh",
                                to_language="en"
                            )
                        except Exception as e:
                            logger.warning(f"Translation failed for '{example_text}': {e}")
                            translation = "[Translation unavailable]"
                    else:
                        translation = "[Translation unavailable]"
                    
                    processed_examples.append(
                        Example(
                            text=example_text,
                            translation=translation,
                            media_urls=[],
                        )
                    )
                
                # Get pinyin for the pattern
                pattern_pinyin = get_mandarin_pinyin(pattern)
                
                # Build LearningItem
                learning_item = LearningItem(
                    id=str(uuid4()),
                    language=language,
                    category=Category.GRAMMAR,
                    target_item=pattern,
                    definition=enriched_data.definition,
                    examples=processed_examples,
                    romanization=pattern_pinyin,
                    sense_gloss=None,
                    lemma=pattern,
                    pos=None,
                    aliases=[],
                    media_urls=[],
                    level_system=level_system,
                    level_min=level,
                    level_max=level,
                    created_at=datetime.now(UTC),
                    version="1.0.0",
                    source_file=str(item.get("source_file", "")),
                )
                
                # Validate output
                is_valid, error_msg = self.validate_output(learning_item, item)
                if not is_valid:
                    logger.error(f"Validation failed for '{pattern}': {error_msg}")
                    if attempt == self.max_retries:
                        # Write to manual review queue
                        if self.manual_review_dir:
                            self._write_to_manual_review(item, error_msg)
                        return None
                    continue
                
                logger.info(f"Successfully enriched grammar pattern: {pattern}")
                return learning_item
                
            except Exception as e:
                logger.error(f"Enrichment failed for '{pattern}' (attempt {attempt}): {e}")
                if attempt == self.max_retries:
                    # Write to manual review queue
                    if self.manual_review_dir:
                        self._write_to_manual_review(item, str(e))
                    return None
        
        return None

    def _write_to_manual_review(self, item: Dict[str, Any], error: str) -> None:
        """Write failed item to manual review queue.
        
        Args:
            item: Grammar pattern item
            error: Error message
        """
        if not self.manual_review_dir:
            return
        
        pattern = item["pattern"]
        review_file = self.manual_review_dir / f"grammar_{pattern}_{uuid4().hex[:8]}.json"
        
        review_data = {
            "item": item,
            "error": error,
            "timestamp": datetime.now(UTC).isoformat(),
            "enricher": self.__class__.__name__,
        }
        
        try:
            import json
            with open(review_file, "w", encoding="utf-8") as f:
                json.dump(review_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Written to manual review: {review_file}")
        except Exception as e:
            logger.error(f"Failed to write manual review file: {e}")
