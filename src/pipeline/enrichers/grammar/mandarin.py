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

import csv
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field

from src.pipeline.enrichers.base import BaseEnricher
from src.pipeline.utils.azure_translation import AzureTranslationHelper
from src.pipeline.utils.llm_client import LLMClient
from src.pipeline.utils.romanization import get_mandarin_pinyin
from src.pipeline.validators.schema import Category, Example, LearningItem, LevelSystem

logger = logging.getLogger(__name__)


class ChineseGrammarEnriched(BaseModel):
    """Grammar enrichment response from LLM."""
    
    definition: str = Field(
        ...,
        description="Clear English definition explaining the grammar pattern, suitable for learners"
    )
    examples: List[str] = Field(
        ...,
        min_length=3,
        max_length=5,
        description="Example sentences in Chinese ONLY (no pinyin, no English translation)"
    )


GRAMMAR_SYSTEM_PROMPT = """You are an expert Mandarin Chinese grammar teacher specializing in teaching grammar patterns to learners.
Your task is to enrich grammar entries with accurate, learner-friendly explanations and examples.

CRITICAL INSTRUCTIONS:
1. **NO PINYIN**: Do NOT include pinyin/romanization in your response. It will be added automatically.
2. **CHINESE ONLY EXAMPLES**: Provide examples in Chinese characters ONLY. Do NOT add pinyin or English translations.
3. **NARROW SCOPE**: Focus on the SPECIFIC grammar pattern provided. Do not create "mega-items" covering multiple patterns.
4. **Clear Explanations**: Definitions must explain the grammatical function, usage, and any constraints.
5. **Natural Examples**: Provide 3-5 example sentences that demonstrate the pattern in natural contexts.
6. **Learner-Appropriate**: Match the proficiency level specified. Keep examples simple for lower levels.

**Grammar Pattern Types:**
- **Morphemes (语素)**: Prefixes (前缀) and suffixes (后缀) like 小-, 第-, -们, -边
- **Word Classes (词类)**: Nouns, verbs, pronouns, measure words, adverbs, prepositions, conjunctions, particles
- **Phrases (短语)**: Coordination, modification, verb-object, subject-predicate, complement structures
- **Sentences (句子)**: Statement, question, imperative, exclamation patterns
- **Sentence Components (句类)**: Subject, predicate, object, attribute, adverbial, complement
- **Complex Sentences (复句)**: Coordination, causation, condition, concession, etc.

**Special Considerations:**
- For particles (助词): Explain function, position, and tone/mood implications
- For modal verbs (能愿动词): Clarify differences in meaning and usage contexts
- For measure words (量词): Note which nouns they pair with
- For separable verbs (离合词): Explain insertion patterns with objects/aspects
- For patterns with numbers (e.g., 会1, 还1): Focus on the specific sense indicated by the number

**Example Response Format:**
{
  "definition": "A modal verb expressing ability or capability, similar to 'can' or 'be able to'",
  "examples": [
    "我会说中文。",
    "他会游泳。",
    "你会开车吗？"
  ]
}

Remember: Chinese characters ONLY in examples. No pinyin. No English translations.
"""


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
    ):
        """Initialize Mandarin grammar enricher.
        
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
        """Get grammar-specific system prompt."""
        return GRAMMAR_SYSTEM_PROMPT

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
        path = Path(source_path)
        if not path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        items = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            
            # Validate columns
            expected_cols = {"类别", "类别名称", "细目", "语法内容"}
            if not expected_cols.issubset(set(reader.fieldnames or [])):
                raise ValueError(
                    f"CSV must have columns: {expected_cols}. Found: {reader.fieldnames}"
                )
            
            for row in reader:
                grammar_type = row["类别"].strip()
                category_name = row["类别名称"].strip()
                detail = row["细目"].strip()
                content = row["语法内容"].strip()
                
                # Split multi-item patterns by 、 or comma
                patterns = re.split(r"[、,，]", content)
                patterns = [p.strip() for p in patterns if p.strip()]
                
                # Create individual items for each pattern to avoid mega-items
                for pattern in patterns:
                    # Remove any parenthetical numbers or notes for target_item
                    # e.g., "会 1" → "会", "（1）专用名量词：本" → "本"
                    clean_pattern = re.sub(r"\s*\d+\s*$", "", pattern)  # Remove trailing numbers
                    clean_pattern = re.sub(r"^（\d+）[^：]*：", "", clean_pattern)  # Remove prefix like "（1）专用名量词："
                    clean_pattern = clean_pattern.strip()
                    
                    if clean_pattern:
                        items.append({
                            "type": grammar_type,
                            "category_name": category_name,
                            "detail": detail,
                            "pattern": clean_pattern,
                            "original_content": content,  # Keep for context
                        })
        
        logger.info(f"Parsed {len(items)} grammar patterns from {source_path}")
        return items

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
2. **Examples**: Provide 3-5 example sentences in Chinese characters ONLY (no pinyin, no English)

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
