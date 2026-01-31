"""Learning item generators for all categories.

This module generates learning items beyond official vocab/grammar lists:
- Pronunciation items (tone pairs, initials, finals)
- Idioms and expressions
- Functional language (greetings, apologies, requests)
- Cultural notes (customs, etiquette, context)
- Writing system (radicals, stroke order, character components)
- Miscellaneous (sociolinguistic, pragmatic, literacy, pattern)

Optimization: Uses lean response models to reduce token usage by ~60-70%.
"""

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
from uuid import uuid4

from pydantic import BaseModel, Field

from havachat.prompts import learning_item_prompts
from havachat.utils.llm_client import LLMClient
from havachat.validators.schema import Category, Example, LearningItem, LevelSystem

logger = logging.getLogger(__name__)


# ============================================================================
# Lean response models for token optimization
# ============================================================================


class LeanLearningItem(BaseModel):
    """Minimal learning item for LLM generation - only essential fields.
    
    This model reduces token usage by ~60-70% compared to full LearningItem.
    Known fields (language, category, level, etc.) are added after generation.
    """
    
    target_item: str = Field(
        description="The target word, phrase, or pattern to learn"
    )
    definition: str = Field(
        description="Clear, learner-friendly definition in English"
    )
    examples: List[str] = Field(
        min_length=2,
        max_length=3,
        description="Example sentences in TARGET LANGUAGE ONLY (no romanization, no English)"
    )


class LeanLearningItemBatch(BaseModel):
    """Batch of lean learning items from LLM."""
    
    items: List[LeanLearningItem] = Field(
        description="List of generated learning items with minimal fields"
    )


class BaseLearningItemGenerator:
    """Base class for generating learning items from source content.

    This generator creates learning items for categories beyond official lists:
    - pronunciation: Generated from vocab items (tone pairs, initials, finals)
    - idiom: Extracted from vocab phrases and common expressions
    - functional: Derived from grammar patterns (greetings, requests, etc.)
    - cultural: Generated from topic/scenario context
    - writing_system: For zh/ja languages (radicals, components, stroke order)
    - misc categories: sociolinguistic, pragmatic, literacy, pattern

    Each category has specific generation logic and prompts.
    Items are generated one-by-one with individual LLM calls (retry up to 3 times).
    """

    def __init__(
        self,
        language: str,
        level_system: LevelSystem,
        level: str,
        llm_client: Optional[LLMClient] = None,
    ):
        """Initialize learning item generator.

        Args:
            language: ISO 639-1 code (zh, ja, fr, en, es)
            level_system: Level system (cefr, hsk, jlpt)
            level: Target level (A1, HSK1, N5, etc.)
            llm_client: Optional LLM client (creates default if None)
        """
        self.language = language
        self.level_system = level_system
        self.level = level
        self.llm_client = llm_client or LLMClient()

        # Track generated items to avoid duplicates
        self.generated_items: Dict[Category, Set[str]] = {
            Category.PRONUNCIATION: set(),
            Category.IDIOM: set(),
            Category.FUNCTIONAL: set(),
            Category.CULTURAL: set(),
            Category.WRITING_SYSTEM: set(),
            Category.SOCIOLINGUISTIC: set(),
            Category.PRAGMATIC: set(),
            Category.LITERACY: set(),
            Category.PATTERN: set(),
            Category.OTHER: set(),
        }

    def generate_pronunciation_items(
        self, vocab_items: List[LearningItem]
    ) -> List[LearningItem]:
        """Generate pronunciation items from vocabulary.

        For Chinese:
        - Tone pairs: 我们 (wǒmen) demonstrates tone 3 + tone 0
        - Initials: 你好 (nǐhǎo) demonstrates 'n' and 'h' sounds
        - Finals: 天气 (tiānqì) demonstrates 'ian' and 'i' finals

        For Japanese:
        - Pitch accent patterns: はし (橋 - bridge) vs はし (箸 - chopsticks)
        - Long vowels: おねえさん (older sister) demonstrates extended 'e'
        - Special sounds: きゃ、きゅ、きょ (kya, kyu, kyo)

        For other languages: Returns empty list (no pronunciation category)

        Args:
            vocab_items: Source vocabulary items to analyze

        Returns:
            List of generated pronunciation learning items
        """
        if self.language not in ["zh", "ja"]:
            logger.info(f"No pronunciation items for language={self.language}")
            return []

        logger.info(f"Generating pronunciation items from {len(vocab_items)} vocab items in single LLM call")
        
        # Generate all pronunciation items in one batch
        items = self._generate_pronunciation_items_batch(vocab_items)
        
        # Deduplicate and track
        unique_items = []
        for item in items:
            if item.target_item not in self.generated_items[Category.PRONUNCIATION]:
                unique_items.append(item)
                self.generated_items[Category.PRONUNCIATION].add(item.target_item)

        logger.info(f"Generated {len(unique_items)} unique pronunciation items")
        return unique_items

    def generate_idiom_items(
        self, vocab_items: List[LearningItem], grammar_items: List[LearningItem]
    ) -> List[LearningItem]:
        """Generate idiom/expression items from vocab phrases and patterns.

        Identifies and extracts:
        - Fixed expressions: "How are you?", "See you later"
        - Idioms: "Break the ice", "Piece of cake"
        - Collocations: "Make a decision", "Take a shower"
        - Proverbs: "Practice makes perfect"

        Args:
            vocab_items: Source vocabulary items
            grammar_items: Source grammar items

        Returns:
            List of generated idiom learning items
        """
        # Filter to multi-word phrases
        phrase_items = [
            item for item in vocab_items 
            if len(item.target_item.split()) >= 2 or len(item.target_item) >= 3
        ]
        
        if not phrase_items:
            logger.info("No multi-word phrases found for idiom generation")
            return []

        logger.info(f"Generating idiom items from {len(phrase_items)} phrases in single LLM call")
        
        # Generate all idiom items in one batch
        items = self._generate_idiom_items_batch(phrase_items)
        
        # Deduplicate and track
        unique_items = []
        for item in items:
            if item.target_item not in self.generated_items[Category.IDIOM]:
                unique_items.append(item)
                self.generated_items[Category.IDIOM].add(item.target_item)

        logger.info(f"Generated {len(unique_items)} unique idiom items")
        return unique_items

    def generate_functional_items(
        self, grammar_items: List[LearningItem]
    ) -> List[LearningItem]:
        """Generate functional language items from grammar patterns.

        Functional language includes:
        - Greetings: "Hello", "Good morning"
        - Apologies: "Sorry", "Excuse me"
        - Requests: "Could you...?", "Would you mind...?"
        - Offers: "Can I help you?", "Would you like...?"
        - Agreement/Disagreement: "I agree", "I don't think so"

        Args:
            grammar_items: Source grammar patterns

        Returns:
            List of generated functional language items
        """
        # Identify functional patterns in grammar items
        functional_keywords = [
            "greet", "apolog", "request", "offer", "suggest",
            "agree", "disagree", "thank", "invite", "refuse",
            "ask for", "polite", "formal", "informal"
        ]
        
        functional_candidates = [
            item for item in grammar_items
            if any(keyword in item.definition.lower() for keyword in functional_keywords)
        ]
        
        if not functional_candidates:
            logger.info("No functional patterns found in grammar items")
            return []

        logger.info(f"Generating functional items from {len(functional_candidates)} grammar patterns in single LLM call")
        
        # Generate all functional items in one batch
        items = self._generate_functional_items_batch(functional_candidates)
        
        # Deduplicate and track
        unique_items = []
        for item in items:
            if item.target_item not in self.generated_items[Category.FUNCTIONAL]:
                unique_items.append(item)
                self.generated_items[Category.FUNCTIONAL].add(item.target_item)

        logger.info(f"Generated {len(unique_items)} unique functional items")
        return unique_items

    def generate_cultural_items(
        self, topic: str, scenario: str
    ) -> List[LearningItem]:
        """Generate cultural note items from topic/scenario context.

        Cultural items include:
        - Customs: Bowing in Japan, tipping in US
        - Etiquette: Gift-giving, dining manners
        - Taboos: Topics to avoid, inappropriate gestures
        - Context: Historical/social background

        Args:
            topic: Topic name (e.g., "Food", "Travel")
            scenario: Scenario description (e.g., "Ordering at a restaurant")

        Returns:
            List of generated cultural note items
        """
        logger.info(f"Generating cultural items for topic={topic}, scenario={scenario} in single LLM call")
        
        # Generate 2-3 cultural items in one batch
        items = self._generate_cultural_items_batch(topic, scenario, count=3)
        
        # Deduplicate and track
        unique_items = []
        for item in items:
            if item.target_item not in self.generated_items[Category.CULTURAL]:
                unique_items.append(item)
                self.generated_items[Category.CULTURAL].add(item.target_item)

        logger.info(f"Generated {len(unique_items)} unique cultural items for topic={topic}")
        return unique_items

    def generate_writing_system_items(
        self, vocab_items: List[LearningItem]
    ) -> List[LearningItem]:
        """Generate writing system items for zh/ja languages.

        For Chinese:
        - Radicals: 亻(person radical) in 你, 他, 们
        - Components: 木 (wood) in 林 (forest), 森 (woods)
        - Stroke order: 永 (eternal) - classic 8 basic strokes

        For Japanese:
        - Kanji components: 日 (sun) in 明 (bright)
        - Hiragana vs Katakana usage rules
        - Okurigana patterns

        Args:
            vocab_items: Source vocabulary items

        Returns:
            List of generated writing system items
        """
        if self.language not in ["zh", "ja"]:
            logger.info(f"No writing system items for language={self.language}")
            return []

        if not vocab_items:
            logger.info("No vocabulary items for writing system generation")
            return []

        logger.info(f"Generating writing system items from {len(vocab_items)} vocab items in single LLM call")
        
        # Generate all writing system items in one batch
        items = self._generate_writing_system_items_batch(vocab_items)
        
        # Deduplicate and track
        unique_items = []
        for item in items:
            if item.target_item not in self.generated_items[Category.WRITING_SYSTEM]:
                unique_items.append(item)
                self.generated_items[Category.WRITING_SYSTEM].add(item.target_item)

        logger.info(f"Generated {len(unique_items)} unique writing system items")
        return unique_items

    def generate_miscellaneous_items(
        self, 
        vocab_items: List[LearningItem],
        grammar_items: List[LearningItem],
        category: Category
    ) -> List[LearningItem]:
        """Generate miscellaneous category items.

        Categories:
        - sociolinguistic: Register, formality levels, dialectal variations
        - pragmatic: Implicature, inference, conversational strategies
        - literacy: Reading strategies, text types, discourse markers
        - pattern: Sentence patterns, collocational patterns

        Args:
            vocab_items: Source vocabulary items
            grammar_items: Source grammar items
            category: Specific miscellaneous category to generate

        Returns:
            List of generated items for the specified category
        """
        if category not in [
            Category.SOCIOLINGUISTIC,
            Category.PRAGMATIC,
            Category.LITERACY,
            Category.PATTERN,
            Category.OTHER,
        ]:
            raise ValueError(f"Invalid miscellaneous category: {category}")

        # Combine vocab and grammar for analysis
        source_items = (vocab_items + grammar_items)[:10]  # Limit to 10 to avoid excessive generation
        
        if not source_items:
            logger.info(f"No source items for {category.value} generation")
            return []

        logger.info(f"Generating {category.value} items from {len(source_items)} source items in single LLM call")
        
        # Generate all miscellaneous items in one batch
        items = self._generate_miscellaneous_items_batch(source_items, category)
        
        # Deduplicate and track
        unique_items = []
        for item in items:
            if item.target_item not in self.generated_items[category]:
                unique_items.append(item)
                self.generated_items[category].add(item.target_item)

        logger.info(f"Generated {len(unique_items)} unique {category.value} items")
        return unique_items

    # ========================================================================
    # Private batch LLM generation methods (multiple items in one call)
    # ========================================================================

    def _assemble_learning_items(
        self, lean_items: List[LeanLearningItem], category: Category
    ) -> List[LearningItem]:
        """Assemble full LearningItem objects from lean LLM responses.
        
        Adds all known metadata fields that don't need LLM generation:
        - language, category, level_system, level_min, level_max
        - id, created_at, version
        - Format examples as Example objects (text only, translations added later)
        
        Args:
            lean_items: List of lean items from LLM
            category: Category to assign
            
        Returns:
            List of full LearningItem objects
        """
        full_items = []
        
        for lean in lean_items:
            # Convert example strings to Example objects (text only)
            examples = [
                Example(text=example_text, translation="", media_urls=[])
                for example_text in lean.examples
            ]
            
            # Build full LearningItem with metadata
            full_item = LearningItem(
                id=str(uuid4()),
                language=self.language,
                category=category,
                target_item=lean.target_item,
                definition=lean.definition,
                examples=examples,
                romanization="",  # To be filled by language-specific logic if needed
                sense_gloss=None,
                lemma=None,
                pos=None,
                aliases=[],
                media_urls=[],
                level_system=self.level_system,
                level_min=self.level,
                level_max=self.level,
                created_at=datetime.now(UTC),
                version="1.0.0",
                source_file=None,
            )
            
            full_items.append(full_item)
        
        return full_items

    def _generate_pronunciation_items_batch(
        self, vocab_items: List[LearningItem]
    ) -> List[LearningItem]:
        """Generate multiple pronunciation items from vocab items in a single LLM call.

        Uses lean response model for token optimization (~60-70% reduction).
        """
        system_prompt = learning_item_prompts.get_pronunciation_system_prompt()
        
        # Build concise list of vocab items for the prompt
        vocab_list = "\n".join([
            f"- {item.target_item} ({item.romanization}): {item.definition}"
            for item in vocab_items
        ])
        
        user_prompt = f"""Generate 5-10 pronunciation learning items from these vocabulary words:

{vocab_list}

Language: {self.language}
Level: {self.level}

Focus on:
- Chinese: Tone patterns, initial/final combinations, tone sandhi, similar sounds
- Japanese: Pitch accent, long vowels, special sound combinations, similar mora

Extract pronunciation features that appear across multiple words (e.g., "tone 3 + tone 3 = tone 2 + tone 3").
Each learning item should teach a pronunciation pattern or feature, not individual words.
Provide clear definitions for learners and 2-3 examples per item.

**CRITICAL**: Examples must be in TARGET LANGUAGE ONLY (no romanization, no English)."""

        try:
            response = self.llm_client.generate(
                prompt=user_prompt,
                response_model=LeanLearningItemBatch,
                system_prompt=system_prompt,
                temperature=0.7,
            )
            
            # Convert lean items to full LearningItem objects
            return self._assemble_learning_items(response.items, Category.PRONUNCIATION)
            
        except Exception as e:
            logger.error(f"Failed to generate pronunciation items batch: {e}")
            return []

    def _generate_idiom_items_batch(
        self, phrase_items: List[LearningItem]
    ) -> List[LearningItem]:
        """Generate multiple idiom items from phrase items in a single LLM call."""
        system_prompt = learning_item_prompts.get_idiom_system_prompt()
        
        phrase_list = "\n".join([
            f"- {item.target_item}: {item.definition}"
            for item in phrase_items
        ])
        
        user_prompt = f"""Identify idioms, expressions, and collocations from these phrases:

{phrase_list}

Language: {self.language}
Level: {self.level}

For each idiom/expression found, create a learning item explaining:
- Literal vs figurative meaning
- Usage context
- Common collocations

Provide 2-3 examples showing natural usage for each item.
Generate 5-10 learning items."""

        try:
            response = self.llm_client.generate(
                prompt=user_prompt,
                response_model=LeanLearningItemBatch,
                system_prompt=system_prompt,
                temperature=0.7,
            )
            
            # Convert lean items to full LearningItem objects
            return self._assemble_learning_items(response.items, Category.IDIOM)
            
        except Exception as e:
            logger.error(f"Failed to generate idiom items batch: {e}")
            return []

    def _generate_functional_items_batch(
        self, grammar_items: List[LearningItem]
    ) -> List[LearningItem]:
        """Generate multiple functional language items from grammar patterns in a single LLM call."""
        system_prompt = learning_item_prompts.get_functional_system_prompt()
        
        grammar_list = "\n".join([
            f"- {item.target_item}: {item.definition}"
            for item in grammar_items
        ])
        
        user_prompt = f"""Create functional language items from these grammar patterns:

{grammar_list}

Language: {self.language}
Level: {self.level}

Focus on:
- Communicative functions (greeting, request, apology, offer, etc.)
- Formality levels (formal, informal, polite)
- Appropriate contexts (business, casual, written, spoken)

Provide 2-3 examples showing functional use in different situations for each item.
Generate 5-10 learning items."""

        try:
            response = self.llm_client.generate(
                prompt=user_prompt,
                response_model=LeanLearningItemBatch,
                system_prompt=system_prompt,
                temperature=0.7,
            )
            
            # Convert lean items to full LearningItem objects
            return self._assemble_learning_items(response.items, Category.FUNCTIONAL)
            
        except Exception as e:
            logger.error(f"Failed to generate functional items batch: {e}")
            return []

    def _generate_cultural_items_batch(
        self, topic: str, scenario: str, count: int = 3
    ) -> List[LearningItem]:
        """Generate multiple cultural note items in a single LLM call."""
        system_prompt = learning_item_prompts.get_cultural_system_prompt()
        
        user_prompt = f"""Create {count} cultural notes for learners:

Topic: {topic}
Scenario: {scenario}
Language/Culture: {self.language}
Level: {self.level}

Focus on:
- Customs, etiquette, or social norms relevant to this scenario
- Practical advice for learners
- Cultural context that helps understanding
- Do's and don'ts

Provide 2-3 examples demonstrating each cultural point.
Generate exactly {count} distinct learning items covering different aspects."""

        try:
            response = self.llm_client.generate(
                prompt=user_prompt,
                response_model=LeanLearningItemBatch,
                system_prompt=system_prompt,
                temperature=0.7,
            )
            
            # Convert lean items to full LearningItem objects
            return self._assemble_learning_items(response.items, Category.CULTURAL)
            
        except Exception as e:
            logger.error(f"Failed to generate cultural items batch: {e}")
            return []

    def _generate_writing_system_items_batch(
        self, vocab_items: List[LearningItem]
    ) -> List[LearningItem]:
        """Generate multiple writing system items in a single LLM call."""
        system_prompt = learning_item_prompts.get_writing_system_system_prompt()
        
        vocab_list = "\n".join([
            f"- {item.target_item}: {item.definition}"
            for item in vocab_items
        ])
        
        user_prompt = f"""Create writing system items for learners:

Characters/Words:
{vocab_list}

Language: {self.language}
Level: {self.level}

For Chinese, focus on:
- Radicals and their meanings (e.g., 亻person radical in 你/他/们)
- Character components (e.g., 木 wood in 林 forest)
- Stroke order patterns

For Japanese, focus on:
- Kanji components (e.g., 日 sun in 明 bright)
- Hiragana/Katakana usage rules
- Okurigana patterns

Extract patterns that appear across multiple characters.
Provide 2-3 examples showing each writing system feature.
Generate 5-10 learning items."""

        try:
            response = self.llm_client.generate(
                prompt=user_prompt,
                response_model=LeanLearningItemBatch,
                system_prompt=system_prompt,
                temperature=0.7,
            )
            
            # Convert lean items to full LearningItem objects
            return self._assemble_learning_items(response.items, Category.WRITING_SYSTEM)
            
        except Exception as e:
            logger.error(f"Failed to generate writing system items batch: {e}")
            return []

    def _generate_miscellaneous_items_batch(
        self, source_items: List[LearningItem], category: Category
    ) -> List[LearningItem]:
        """Generate multiple miscellaneous category items in a single LLM call."""
        system_prompt = learning_item_prompts.get_miscellaneous_system_prompt(category)
        
        source_list = "\n".join([
            f"- {item.target_item}: {item.definition}"
            for item in source_items
        ])
        
        user_prompt = f"""Create {category.value} learning items:

Source items:
{source_list}

Language: {self.language}
Level: {self.level}

Category focus:
- sociolinguistic: Register, formality, dialectal variations
- pragmatic: Implicature, inference, conversational strategies
- literacy: Reading strategies, text types, discourse markers
- pattern: Sentence patterns, collocational patterns

Provide 2-3 examples demonstrating each linguistic feature.
Generate 3-7 learning items."""

        try:
            response = self.llm_client.generate(
                prompt=user_prompt,
                response_model=LeanLearningItemBatch,
                system_prompt=system_prompt,
                temperature=0.7,
            )
            
            # Convert lean items to full LearningItem objects
            return self._assemble_learning_items(response.items, category)
            
        except Exception as e:
            logger.error(f"Failed to generate {category.value} items batch: {e}")
            return []

    # ========================================================================
    # System prompts moved to src/pipeline/prompts/learning_item_prompts.py
    # ========================================================================

