"""Optimized French vocabulary enricher with cost reduction.

Cost reduction strategy (same as Mandarin/Japanese):
1. Use minimal LLM response model (only explanation, examples)
2. Examples are French-only (no English translations in LLM response)
3. Use Azure Translation API for English translations (2M free chars/month)
4. No romanization needed (French uses Latin alphabet)
5. Assemble final LearningItem from all sources

Expected cost savings: ~60-70% token reduction per item
"""

import csv
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field

from src.pipeline.enrichers.base import BaseEnricher
from src.pipeline.utils.azure_translation import AzureTranslationHelper
from src.pipeline.utils.llm_client import LLMClient
from src.pipeline.validators.schema import Category, Example, LearningItem, LevelSystem

logger = logging.getLogger(__name__)


class FrenchEnrichedVocab(BaseModel):
    """French vocab enrichment."""
    
    definition: str = Field(
        ...,
        description="Clear English definition suitable for learners, to be used in flashcards"
    )
    examples: List[str] = Field(
        ...,
        min_length=3,
        max_length=5,
        description="Example sentences in French ONLY (no English translation). Example: 'Bonjour, comment allez-vous ?'"
    )
    pos: Optional[str] = Field(
        None, 
        description="Part of speech: noun, verb, adjective, expression, etc."
    )
    lemma: Optional[str] = Field(
        None,
        description="Lemma/base form if this is an inflected form"
    )


# Optimized system prompt - no translation instructions
OPTIMIZED_SYSTEM_PROMPT = """You are an expert French teacher specializing in vocabulary pedagogy.
Your task is to enrich vocabulary entries with accurate, learner-friendly information.

CRITICAL INSTRUCTIONS:
1. **FRENCH ONLY EXAMPLES**: Provide examples in French ONLY. Do NOT add English translations.
2. **Clarity**: Explanations must be clear and suitable for learners at the specified level.
3. **Examples**: Provide 3-5 contextual example sentences using ONLY French.
4. **Functional Context**: Consider the functional category (e.g., "Saluer" = greeting, "Prendre congé" = saying goodbye).
5. **Part of Speech**: Identify the part of speech when applicable.

**Example Response Format:**
{
  "definition": "hello; good morning; good afternoon; good-day",
  "examples": [
    "Bonjour, comment allez-vous ?",
    "Bonjour madame, puis-je vous aider ?",
    "Bonjour tout le monde !"
  ],
  "pos": "expression"
}

Remember: French ONLY in examples. No English translations.
"""


class FrenchVocabEnricher(BaseEnricher):
    """Optimized enricher for French vocabulary with cost reduction.

    Expected input format: TSV with "Mot\tCatégorie" columns
    
    Optimizations:
    - Minimal LLM response (explanation, examples only)
    - French-only examples (no translations in LLM response)
    - Azure Translation for English translations
    - No romanization needed (Latin alphabet)
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        max_retries: int = 3,
        manual_review_dir: Optional[Union[str, Path]] = None,
    ):
        """Initialize French enricher with Azure Translation.
        
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
        """Get optimized French-specific system prompt."""
        return OPTIMIZED_SYSTEM_PROMPT

    def parse_source(self, source_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """Parse TSV file with Mot (word/phrase) and Catégorie (functional category).

        Args:
            source_path: Path to TSV file

        Returns:
            List of dictionaries with French vocabulary data

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
            content = f.read()
            if content.startswith("\ufeff"):
                content = content[1:]
            
            # Parse TSV
            lines = content.strip().split("\n")
            if len(lines) < 2:
                raise ValueError(f"TSV file must have at least header and one data row")
            
            # Parse header
            header = lines[0].split("\t")
            if len(header) < 2:
                raise ValueError(f"Expected at least 2 columns (Mot, Catégorie), got {len(header)}")

            for i, line in enumerate(lines[1:], start=1):
                parts = line.split("\t")
                if len(parts) < 2:
                    logger.warning(f"Row {i} has insufficient columns, skipping: {line}")
                    continue
                
                word = parts[0].strip()
                category = parts[1].strip()

                if not word:
                    logger.warning(f"Row {i} missing 'Mot' value, skipping")
                    continue

                item = {
                    "target_item": word,
                    "context_category": category if category else None,
                    "source_row": i,
                }

                items.append(item)

        logger.info(
            f"Parsed {len(items)} items from {source_path}",
            extra={"source": str(source_path), "item_count": len(items)},
        )

        return items

    def detect_missing_fields(self, item: Dict[str, Any]) -> List[str]:
        """Detect which fields need enrichment.

        For optimized French enricher:
        - Always need: definition, examples (LLM)
        - Optionally need: pos (if not provided)
        - No romanization needed (Latin alphabet)

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

        # POS is optional
        if not item.get("pos"):
            missing.append("pos")

        return missing

    def enrich_item(self, item: Dict[str, Any]) -> Optional[LearningItem]:
        """Enrich a single French vocabulary item using optimized strategy.
        
        Process:
        1. Get minimal LLM response (explanation, French-only examples)
        2. Use Azure Translation to translate examples to English
        3. Assemble complete LearningItem
        
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
            # Step 1: Get minimal LLM response (French-only examples)
            missing_fields = self.detect_missing_fields(item)
            prompt = self.build_prompt(item, missing_fields)
            
            llm_response: FrenchEnrichedVocab = self.llm_client.generate(
                prompt=prompt,
                response_model=FrenchEnrichedVocab,
                use_cache=True
            )
            
            logger.debug(f"LLM response for '{target_item}': {len(llm_response.examples)} examples")
            
            # Step 2: Translate examples to English using Azure Translation
            example_translations = []
            if self.azure_translator:
                try:
                    example_translations = self.azure_translator.translate_batch(
                        texts=llm_response.examples,
                        from_language="fr",
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
            
            # Step 3: Format examples with translations
            formatted_examples = self._format_examples(
                llm_response.examples,
                example_translations
            )
            
            # Step 4: Assemble complete LearningItem
            enriched_item = LearningItem(
                id=str(uuid4()),
                language="fr",
                category=Category.VOCAB,
                target_item=target_item,
                definition=llm_response.definition,
                examples=formatted_examples,
                sense_gloss=None,  # Not commonly used for French
                romanization=None,  # French doesn't need romanization
                pos=llm_response.pos,
                lemma=llm_response.lemma,
                aliases=[],
                level_system=LevelSystem.CEFR,
                level_min=item.get("level_min", "A1"),
                level_max=item.get("level_max", "A1"),
                created_at=datetime.now(UTC),
                version="1.0.0",
                source_file=item.get("source_file"),
            )
            
            logger.info(
                f"Successfully enriched '{target_item}'",
                extra={
                    "target_item": target_item,
                    "context_category": item.get("context_category"),
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
        context_category = item.get("context_category", "")
        level_min = item.get("level_min", "A1")
        level_max = item.get("level_max", level_min)
        
        context_info = f"\n**Functional Context**: {context_category}" if context_category else ""
        
        prompt = f"""Enrich the following French vocabulary item:

**Word/Phrase**: {target_item}{context_info}
**Proficiency Level**: {level_min} to {level_max}

**Instructions**:
1. Write a clear, learner-friendly explanation in English
2. Identify the part of speech (noun, verb, expression, etc.)
3. Create 3-5 original example sentences in FRENCH ONLY (no English)

**CRITICAL**: Examples must be French ONLY. Example:
- CORRECT: "Bonjour, comment allez-vous ?"
- INCORRECT: "Bonjour, comment allez-vous ? - Hello, how are you?"

Remember: We will add English translations automatically later.
"""
        
        return prompt

    def _format_examples(
        self, 
        french_examples: List[str], 
        translations: List[str]
    ) -> List[Example]:
        """Format examples with English translations.
        
        Args:
            french_examples: List of French-only example sentences
            translations: List of English translations (same order)
            
        Returns:
            List of Example objects with text, translation, and empty media_urls
        """
        formatted = []
        
        for french, translation in zip(french_examples, translations):
            example = Example(
                text=french,
                translation=translation if translation else "",
                media_urls=[]
            )
            formatted.append(example)
        
        return formatted

    def validate_output(self, item: Dict[str, Any], enriched_data: LearningItem) -> bool:
        """Validate enriched French vocabulary item.
        
        Args:
            item: Original item dictionary
            enriched_data: Enriched LearningItem
            
        Returns:
            True if validation passes
        """
        # Check examples
        if not (3 <= len(enriched_data.examples) <= 5):
            logger.warning(
                f"Expected 3-5 examples, got {len(enriched_data.examples)} "
                f"for '{enriched_data.target_item}'"
            )
            return False

        # Check that examples contain French text
        for example in enriched_data.examples:
            if len(example.strip()) < 5:
                logger.warning(
                    f"Example too short: '{example}' "
                    f"for '{enriched_data.target_item}'"
                )
                return False

            if not any(char.isalpha() for char in example):
                logger.warning(
                    f"Example doesn't contain text: '{example}' "
                    f"for '{enriched_data.target_item}'"
                )
                return False

        # Check language
        if enriched_data.language != "fr":
            logger.warning(f"Expected language='fr', got '{enriched_data.language}'")
            return False

        # French should NOT have romanization
        if enriched_data.romanization:
            logger.warning(
                f"French item should not have romanization: '{enriched_data.target_item}'"
            )
            # Not a failure, just a warning

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
    def _normalize_cefr_level(level: str | None) -> str:
        """Normalize CEFR level to standard format.

        Args:
            level: Input level (A1, a1, A-1, etc.)

        Returns:
            Normalized level (A1, A2, B1, B2, C1, C2)
        """
        if not level:
            return "A1"  # Default to beginner

        level = str(level).upper().strip().replace("-", "").replace("_", "")

        # Standard CEFR levels
        valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]

        if level in valid_levels:
            return level

        # Try to extract
        for valid in valid_levels:
            if valid in level:
                return valid

        return "A1"  # Default
