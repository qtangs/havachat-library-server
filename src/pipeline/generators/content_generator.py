"""Content generator with chain-of-thought reasoning.

This module generates conversations and/or stories using ALL learning item categories
together in a single LLM call. The chain-of-thought process includes:

1. Generate: Create conversations and/or stories using all items
2. Critique: Evaluate coverage, level-appropriateness, natural flow
3. Revise: Improve based on critique, list items used explicitly
4. Assign Scenarios: Give 3-8 word scenario names to each piece

All steps are structured within a single prompt, not sequential API calls.
Uses the instructor library for structured output with Pydantic validation.

Content types can be generated separately:
- Conversations only (--type conversation)
- Stories only (--type story)
- Both together (--type both)
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from pipeline.parsers.source_parsers import load_source_file
from pipeline.prompts.content_generator_prompts import build_content_generation_system_prompt
from pipeline.utils.azure_translation import AzureTranslationHelper
from pipeline.utils.llm_client import LLMClient
from pipeline.validators.schema import (
    Category,
    ContentType,
    ContentUnit,
    LearningItem,
    LevelSystem,
    Segment,
    SegmentType,
    Speaker,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Topic and Scenario Storage Models
# ============================================================================


class Topic(BaseModel):
    """Topic with UUID for content categorization."""
    
    id: str = Field(..., description="Topic UUID")
    name: str = Field(..., description="Topic name in English")


class Scenario(BaseModel):
    """Scenario with UUID for content situations."""
    
    id: str = Field(..., description="Scenario UUID")
    name: str = Field(..., description="Scenario name in English")


# ============================================================================
# Chain-of-Thought Pydantic Models
# ============================================================================


class SpeakerInfo(BaseModel):
    """Speaker information in overview."""
    
    name: str = Field(..., description="Speaker name in English")
    role: str = Field(..., description="Speaker role in English")
    gender: Optional[str] = Field(None, description="Speaker gender (male/female/any) in English, only when relevant")


class ContentOverview(BaseModel):
    """Overview of a content piece with metadata."""
    
    type: ContentType
    title: str = Field(..., description="Content title in English")
    speakers: Optional[List[SpeakerInfo]] = Field(
        None, description="List of speakers (for conversations only)"
    )


class SimplifiedLearningItem(BaseModel):
    """Simplified learning item for token-efficient prompts.
    
    Contains minimal fields based on category:
    - Vocab: word + part_of_speech
    - Grammar: rule
    - Other categories: target_item
    
    This reduces token usage significantly (~300-400 tokens for 200 items).
    """
    
    id: str = Field(..., description="Learning item UUID")
    category: Category
    target_item: str = Field(..., description="The word, phrase, or pattern")
    
    # Category-specific fields (only populated for relevant categories)
    part_of_speech: Optional[str] = Field(None, description="POS for vocab items")
    rule: Optional[str] = Field(None, description="Grammar rule for grammar items")


class SegmentDraft(BaseModel):
    """Draft segment with learning items (no translation in initial draft)."""
    
    speaker: Optional[int] = Field(
        None, description="Speaker index (0-based, references speakers in overview)"
    )
    text: str = Field(..., description="Text in target language")
    learning_item_ids: List[str] = Field(
        ..., description="Short UUIDs (8 chars) of learning items in this segment"
    )


class RevisedSegmentDraft(BaseModel):
    """Revised segment with learning items and translation (from LLM or Azure)."""
    
    speaker: Optional[int] = Field(
        None, description="Speaker index (0-based, references speakers in overview)"
    )
    text: str = Field(..., description="Text in target language")
    translation: str = Field(..., description="English translation of the text")
    learning_item_ids: List[str] = Field(
        ..., description="Short UUIDs (8 chars) of learning items in this segment"
    )


class ContentDraft(BaseModel):
    """Initial draft of a conversation or story (references overview for type/title/speakers)."""
    
    segments: List[SegmentDraft] = Field(..., min_length=1)


class Critique(BaseModel):
    """Critique of the initial draft."""
    
    coverage_score: int = Field(
        ..., ge=0, le=10, description="How well learning items are incorporated (0-10)"
    )
    level_appropriateness_score: int = Field(
        ..., ge=0, le=10, description="Matches target level difficulty (0-10)"
    )
    natural_flow_score: int = Field(
        ..., ge=0, le=10, description="Conversational naturalness (0-10)"
    )
    issues_found: List[str] = Field(
        ..., description="Specific problems to address"
    )
    strengths: List[str] = Field(
        ..., description="What works well in the draft"
    )


class RevisedContent(BaseModel):
    """Revised content after critique (includes translations)."""
    
    segments: List[RevisedSegmentDraft]
    improvements_made: List[str] = Field(
        ..., description="Changes made based on critique"
    )


class ScenarioAssignment(BaseModel):
    """3-8 word scenario name for a content piece."""
    
    scenario_name: str = Field(
        ..., description="3-8 word scenario name (e.g., 'Ordering food at a restaurant')"
    )


class ChainOfThoughtContent(BaseModel):
    """Complete chain-of-thought for content generation."""
    
    overview: List[ContentOverview] = Field(
        ..., description="Overview of each content piece (type, title, speakers)"
    )
    initial_drafts: List[ContentDraft] = Field(
        ..., description="Initial generated conversations and stories (same order as overview)"
    )
    critiques: List[Critique] = Field(
        ..., description="Critique for each draft (same order as overview)"
    )
    revised_contents: List[RevisedContent] = Field(
        ..., description="Revised versions after critique (same order as overview)"
    )
    scenario_assignments: List[ScenarioAssignment] = Field(
        ..., description="Scenario names for each piece (same order as overview)"
    )


class ContentBatch(BaseModel):
    """Batch of generated content with metadata."""
    
    conversations: List[ContentUnit] = Field(default_factory=list)
    stories: List[ContentUnit] = Field(default_factory=list)
    chain_of_thought_metadata: Dict = Field(
        default_factory=dict,
        description="Summary of chain-of-thought quality metrics"
    )
    chain_of_thought_raw: Optional[ChainOfThoughtContent] = Field(
        default=None,
        description="Full chain-of-thought response for review"
    )


# ============================================================================
# Content Generator
# ============================================================================


class ContentGenerator:
    """Generate conversations and stories with chain-of-thought reasoning.

    This generator:
    1. Loads ALL learning items (vocab, grammar, pronunciation, idioms, etc.)
       in simplified format (target_item only) to minimize tokens
    2. Generates content batch (N conversations + N stories) in single LLM call
       using chain-of-thought: generate → critique → revise → assign scenarios
    3. Validates all learning_item_ids exist and appear in text
    4. Creates ContentUnit objects with proper structure
    """

    def __init__(
        self,
        language: str,
        level_system: LevelSystem,
        level: str,
        llm_client: Optional[LLMClient] = None,
        use_azure_translation: bool = False,
    ):
        """Initialize content generator.

        Args:
            language: ISO 639-1 code (zh, ja, fr, en, es)
            level_system: Level system (cefr, hsk, jlpt)
            level: Target level (A1, HSK1, N5, etc.)
            llm_client: Optional LLM client (creates default if None)
            use_azure_translation: Use Azure Translation instead of LLM (default: False)
        """
        self.language = language
        self.level_system = level_system
        self.level = level
        self.llm_client = llm_client or LLMClient()
        self.use_azure_translation = use_azure_translation

        # Storage for loaded learning items
        self.all_learning_items: Dict[str, LearningItem] = {}
        self.simplified_items: List[SimplifiedLearningItem] = []
        
        # UUID mapping: short (8 chars) -> full UUID
        self.short_to_full_uuid: Dict[str, str] = {}
        
        # Storage for topics and scenarios
        self.topics: Dict[str, Topic] = {}  # name -> Topic
        self.scenarios: Dict[str, Scenario] = {}  # name -> Scenario
        self.topics_file: Optional[Path] = None
        self.scenarios_file: Optional[Path] = None
        
        # Initialize Azure Translation helper only if requested
        if use_azure_translation:
            try:
                self.azure_translator = AzureTranslationHelper()
                logger.info("Azure Translation initialized for content generation")
            except ValueError as e:
                logger.warning(f"Azure Translation not available: {e}")
                self.azure_translator = None
        else:
            logger.info("Using LLM for translations (default)")
            self.azure_translator = None

    def load_topics_and_scenarios(self, output_dir: Path) -> None:
        """Load topics and scenarios from JSON files.
        
        Args:
            output_dir: Directory containing topics.json and scenarios.json
        """
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)
        
        self.topics_file = output_dir / "topics.json"
        self.scenarios_file = output_dir / "scenarios.json"
        
        # Load topics
        if self.topics_file.exists():
            with open(self.topics_file, "r", encoding="utf-8") as f:
                topics_data = json.load(f)
                for topic_data in topics_data:
                    topic = Topic(**topic_data)
                    self.topics[topic.name] = topic
            logger.info(f"Loaded {len(self.topics)} topics from {self.topics_file}")
        else:
            logger.info(f"No existing topics file found at {self.topics_file}")
        
        # Load scenarios
        if self.scenarios_file.exists():
            with open(self.scenarios_file, "r", encoding="utf-8") as f:
                scenarios_data = json.load(f)
                for scenario_data in scenarios_data:
                    scenario = Scenario(**scenario_data)
                    self.scenarios[scenario.name] = scenario
            logger.info(f"Loaded {len(self.scenarios)} scenarios from {self.scenarios_file}")
        else:
            logger.info(f"No existing scenarios file found at {self.scenarios_file}")
    
    def _save_topics_and_scenarios(self) -> None:
        """Save topics and scenarios to JSON files."""
        if not self.topics_file or not self.scenarios_file:
            logger.warning("Topics/scenarios file paths not set. Call load_topics_and_scenarios() first.")
            return
        
        # Ensure parent directories exist
        self.topics_file.parent.mkdir(parents=True, exist_ok=True)
        self.scenarios_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Save topics
        if self.topics:
            with open(self.topics_file, "w", encoding="utf-8") as f:
                topics_list = [topic.model_dump() for topic in self.topics.values()]
                json.dump(topics_list, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(self.topics)} topics to {self.topics_file}")
        
        # Save scenarios
        if self.scenarios:
            with open(self.scenarios_file, "w", encoding="utf-8") as f:
                scenarios_list = [scenario.model_dump() for scenario in self.scenarios.values()]
                json.dump(scenarios_list, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(self.scenarios)} scenarios to {self.scenarios_file}")
    
    def _get_or_create_topic(self, topic_name: str) -> str:
        """Get or create a topic UUID.
        
        Args:
            topic_name: Topic name in English
        
        Returns:
            Topic UUID
        """
        if topic_name not in self.topics:
            topic = Topic(
                id=str(uuid4()),
                name=topic_name,
            )
            self.topics[topic_name] = topic
            logger.info(f"Created new topic: {topic_name} (ID: {topic.id})")
        return self.topics[topic_name].id
    
    def _get_or_create_scenario(self, scenario_name: str) -> str:
        """Get or create a scenario UUID.
        
        Args:
            scenario_name: Scenario name in English
        
        Returns:
            Scenario UUID
        """
        if scenario_name not in self.scenarios:
            scenario = Scenario(
                id=str(uuid4()),
                name=scenario_name,
            )
            self.scenarios[scenario_name] = scenario
            logger.info(f"Created new scenario: {scenario_name} (ID: {scenario.id})")
        return self.scenarios[scenario_name].id

    def load_learning_items(self, learning_items_dir: Path) -> int:
        """Load ALL learning items using generated_content_info.json.

        This reads generated_content_info.json to discover learning item files
        and their types (original TSV/CSV vs enriched JSON), then loads them
        appropriately.

        Items are stored in two formats:
        1. Full LearningItem objects (for validation)
        2. Simplified format with minimal fields (for prompts)

        Args:
            learning_items_dir: Directory containing generated_content_info.json

        Returns:
            Number of items loaded
        """
        info_file = learning_items_dir / "generated_content_info.json"
        
        if not info_file.exists():
            raise FileNotFoundError(
                f"generated_content_info.json not found in {learning_items_dir}. "
                "This file is required to locate and parse learning item files."
            )
        
        # Load content info
        with open(info_file, "r", encoding="utf-8") as f:
            content_info = json.load(f)
        
        logger.info(f"Loading learning items from {len(content_info)} sources")
        
        # Load items from each source
        for category_key, source_info in content_info.items():
            source_path = learning_items_dir / source_info["path"]
            source_type = source_info["type"]
            
            logger.info(f"Loading {category_key} from {source_info['path']} (type: {source_type})")
            
            try:
                if source_type == "original":
                    # Parse original source file (TSV/CSV)
                    self._load_original_source(source_path, category_key)
                elif source_type == "enriched":
                    # Load enriched JSON file(s)
                    self._load_enriched_source(source_path, category_key)
                else:
                    logger.warning(f"Unknown source type '{source_type}' for {category_key}")
            except Exception as e:
                logger.error(f"Failed to load {category_key} from {source_path}: {e}")
                continue
        
        logger.info(f"Loaded {len(self.all_learning_items)} learning items")
        logger.info(f"Categories: {self._count_by_category()}")
        return len(self.all_learning_items)

    def generate_content_batch(
        self,
        topic: str,
        num_conversations: int = 5,
        num_stories: int = 5,
        content_type: str = "both",
    ) -> ContentBatch:
        """Generate a batch of content using chain-of-thought reasoning.

        Single LLM call generates content with structure:
        1. Generate: Initial drafts using all learning items
        2. Critique: Evaluate coverage, level, flow
        3. Revise: Improve based on critique
        4. Assign Scenarios: Give 3-8 word names

        Args:
            topic: Topic name (e.g., "Food", "Travel")
            num_conversations: Number of conversations to generate (default: 5, ignored if content_type="story")
            num_stories: Number of stories to generate (default: 5, ignored if content_type="conversation")
            content_type: Type of content to generate: "conversation", "story", or "both" (default: "both")

        Returns:
            ContentBatch with conversations, stories, and metadata

        Raises:
            ValueError: If no learning items loaded or invalid content_type
        """
        if not self.all_learning_items:
            raise ValueError("No learning items loaded. Call load_learning_items() first.")
        
        if content_type not in ["conversation", "story", "both"]:
            raise ValueError(f"Invalid content_type: {content_type}. Must be 'conversation', 'story', or 'both'.")
        
        # Adjust counts based on content_type
        actual_conversations = num_conversations if content_type in ["conversation", "both"] else 0
        actual_stories = num_stories if content_type in ["story", "both"] else 0

        logger.info(
            f"Generating content batch: topic={topic}, type={content_type}, "
            f"conversations={actual_conversations}, stories={actual_stories}"
        )

        # Build chain-of-thought prompt
        system_prompt = self._build_system_prompt(content_type)
        user_prompt = self._build_generation_prompt(topic, actual_conversations, actual_stories, content_type)

        # Generate with structured output
        try:
            cot_response = self.llm_client.generate(
                prompt=user_prompt,
                response_model=ChainOfThoughtContent,
                system_prompt=system_prompt,
                temperature=0.8,
                max_tokens=4096,
            )

            # Convert to ContentBatch
            batch = self._convert_to_content_batch(cot_response, topic)

            # Validate all learning_item_ids
            self._validate_content_batch(batch)

            # Calculate chain-of-thought quality metrics
            batch.chain_of_thought_metadata = self._calculate_cot_metrics(cot_response)

            logger.info(f"Generated {len(batch.conversations)} conversations, {len(batch.stories)} stories")
            
            # Store chain-of-thought response for review
            batch.chain_of_thought_raw = cot_response
            
            # Save topics and scenarios to JSON files
            self._save_topics_and_scenarios()
            
            return batch

        except Exception as e:
            logger.error(f"Failed to generate content batch: {e}", exc_info=True)
            raise

    def validate_presence(self, content_unit: ContentUnit) -> bool:
        """Validate all learning_item_ids exist and appear in text.

        Args:
            content_unit: Content to validate

        Returns:
            True if all IDs valid and present
        """
        # Check all IDs exist
        for item_id in content_unit.learning_item_ids:
            if item_id not in self.all_learning_items:
                logger.error(f"Learning item not found: {item_id}")
                return False

        # Check all IDs appear in text
        text_lower = content_unit.text.lower()
        for item_id in content_unit.learning_item_ids:
            item = self.all_learning_items[item_id]
            target_lower = item.target_item.lower()
            
            if target_lower not in text_lower:
                logger.warning(
                    f"Learning item not found in text: {item.target_item} (ID: {item_id})"
                )
                # Allow some flexibility for morphological variations
                # but log warning for manual review

        return True

    # ========================================================================
    # Private methods
    # ========================================================================

    def _load_original_source(self, source_path: Path, category_key: str) -> None:
        """Load items from original source file (TSV/CSV).
        
        Args:
            source_path: Path to source file
            category_key: Category key from generated_content_info.json (e.g., "vocab", "grammar")
        """
        # Determine content type for parser
        content_type = "vocab" if "vocab" in category_key.lower() else "grammar"
        
        # Parse source file
        parsed_items = load_source_file(source_path, self.language, content_type)
        
        # Convert to LearningItem and SimplifiedLearningItem
        for item_data in parsed_items:
            # Create full LearningItem with required fields
            item = LearningItem(
                id=str(uuid4()),
                language=self.language,
                category=Category.VOCAB if content_type == "vocab" else Category.GRAMMAR,
                target_item=item_data.get("target_item", ""),
                definition=item_data.get("meaning", ""),  # Use meaning as definition
                examples=[],  # Original sources don't have examples yet
                meaning=item_data.get("meaning", ""),
                part_of_speech=item_data.get("part_of_speech"),
                rule=item_data.get("rule"),
                romanization=item_data.get("romanization"),
                level_system=self.level_system,
                level_min=item_data.get("level_min", self.level),
                level_max=item_data.get("level_max", self.level),
            )
            
            # Store full item
            self.all_learning_items[item.id] = item
            
            # Map short UUID (first 8 chars) to full UUID
            short_id = item.id[:8]
            self.short_to_full_uuid[short_id] = item.id
            
            # Create simplified version with minimal fields and short ID
            if content_type == "vocab":
                # Vocab: word + part_of_speech
                simplified = SimplifiedLearningItem(
                    id=short_id,
                    category=item.category,
                    target_item=item.target_item,
                    part_of_speech=item.part_of_speech,
                )
            else:
                # Grammar: rule
                simplified = SimplifiedLearningItem(
                    id=short_id,
                    category=item.category,
                    target_item=item.target_item,
                    rule=item.rule,
                )
            
            self.simplified_items.append(simplified)
    
    def _load_enriched_source(self, source_path: Path, category_key: str) -> None:
        """Load items from enriched JSON file(s).
        
        Args:
            source_path: Path to JSON file or directory
            category_key: Category key from generated_content_info.json
        """
        # Check if path is file or directory
        if source_path.is_file():
            json_files = [source_path]
        elif source_path.is_dir():
            json_files = list(source_path.rglob("*.json"))
        else:
            logger.warning(f"Source path does not exist: {source_path}")
            return
        
        # Load each JSON file
        for json_file in json_files:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                    # Handle both single item and array of items
                    items_data = data if isinstance(data, list) else [data]
                    
                    for item_data in items_data:
                        item = LearningItem(**item_data)
                        
                        # Store full item
                        self.all_learning_items[item.id] = item
                        
                        # Map short UUID (first 8 chars) to full UUID
                        short_id = item.id[:8]
                        self.short_to_full_uuid[short_id] = item.id
                        
                        # Create simplified version - all enriched items just use target_item
                        simplified = SimplifiedLearningItem(
                            id=short_id,
                            category=item.category,
                            target_item=item.target_item,
                        )
                        self.simplified_items.append(simplified)
            except Exception as e:
                logger.warning(f"Failed to load {json_file}: {e}")
                continue

    def _count_by_category(self) -> Dict[str, int]:
        """Count learning items by category."""
        counts = {}
        for item in self.all_learning_items.values():
            category = item.category.value
            counts[category] = counts.get(category, 0) + 1
        return counts

    def _build_system_prompt(self, content_type: str = "both") -> str:
        """Build system prompt for content generation.
        
        Args:
            content_type: Type of content ("conversation", "story", or "both")
        """
        return build_content_generation_system_prompt(self.language, self.level, content_type)

    def _build_generation_prompt(
        self, topic: str, num_conversations: int, num_stories: int, content_type: str = "both"
    ) -> str:
        """Build user prompt for content generation.
        
        Args:
            topic: Topic name
            num_conversations: Number of conversations (0 if not generating)
            num_stories: Number of stories (0 if not generating)
            content_type: Type of content to generate
        """
        # Format simplified items for prompt with minimal fields
        items_by_category = {}
        for item in self.simplified_items:
            category = item.category.value
            if category not in items_by_category:
                items_by_category[category] = []
            
            # Format based on category
            if item.category == Category.VOCAB and item.part_of_speech:
                # Vocab: word (POS) - using short ID (8 chars)
                formatted = f"  - {item.target_item} ({item.part_of_speech}) [ID: {item.id}]"
            elif item.category == Category.GRAMMAR and item.rule:
                # Grammar: rule - using short ID (8 chars)
                formatted = f"  - {item.rule} [ID: {item.id}]"
            else:
                # Other categories: just target_item - using short ID (8 chars)
                formatted = f"  - {item.target_item} [ID: {item.id}]"
            
            items_by_category[category].append(formatted)

        items_formatted = "\n\n".join([
            f"{category.upper()}:\n" + "\n".join(items[:20])  # Limit to 20 per category
            for category, items in items_by_category.items()
        ])
        
        # Build generate section based on content_type
        generate_section = []
        if num_conversations > 0:
            generate_section.append(f"- {num_conversations} conversations (6-10 dialogue turns each)")
        if num_stories > 0:
            generate_section.append(f"- {num_stories} stories (8-12 sentences each)")
        generate_text = "\n".join(generate_section)

        return f"""Topic: {topic}
Language: {self.language}
Level: {self.level}

Generate:
{generate_text}

Learning Items to Incorporate:
{items_formatted}

Follow the four-step chain-of-thought process:
1. Create overview with type, title, and speakers (for conversations)
2. Generate initial drafts (reference speakers by index: 0, 1, 2...)
3. Critique each draft
4. Revise based on critique
5. Assign scenario names

Remember:
- Use items from MULTIPLE categories in each piece
- Match {self.level} difficulty
- Make content natural and engaging
- Use speaker indices (0, 1, 2...) that reference the overview
- Use short IDs (8 chars) for learning items
- Explicitly list all learning item IDs in revised versions"""

    def _convert_to_content_batch(
        self, cot_response: ChainOfThoughtContent, topic_name: str
    ) -> ContentBatch:
        """Convert chain-of-thought response to ContentBatch.
        
        Args:
            cot_response: Chain-of-thought response from LLM
            topic_name: Topic name for this batch
        
        Returns:
            ContentBatch with UUIDs for topics and scenarios
        """
        batch = ContentBatch()
        
        # Get or create topic UUID
        topic_id = self._get_or_create_topic(topic_name)

        for idx, revised in enumerate(cot_response.revised_contents):
            # Get overview metadata
            overview = cot_response.overview[idx]
            scenario_name = cot_response.scenario_assignments[idx].scenario_name
            
            # Get or create scenario UUID
            scenario_id = self._get_or_create_scenario(scenario_name)
            
            content_id = str(uuid4())

            # Convert speakers from overview to A/B/C IDs
            speakers_list = []
            speaker_ids = ["A", "B", "C", "D", "E", "F", "G", "H"]
            
            if overview.speakers:
                for i, speaker_info in enumerate(overview.speakers):
                    speaker = Speaker(
                        id=speaker_ids[i],
                        name=speaker_info.name,
                        role=speaker_info.role,
                        gender=speaker_info.gender,
                    )
                    speakers_list.append(speaker)

            # Create ContentUnit segments with A/B/C speaker IDs
            segments = []
            
            # If using Azure Translation, override LLM translations
            if self.use_azure_translation and self.azure_translator:
                segment_texts = [seg_draft.text for seg_draft in revised.segments]
                
                try:
                    segment_translations = self.azure_translator.translate_batch(
                        texts=segment_texts,
                        from_language=self.language,
                        to_language="en"
                    )
                    logger.debug(f"Azure Translation: translated {len(segment_translations)} segments for content {idx}")
                except Exception as e:
                    logger.error(f"Azure Translation failed for content {idx}: {e}, using LLM translations")
                    # Fall back to LLM translations from seg_draft.translation
                    segment_translations = [seg_draft.translation for seg_draft in revised.segments]
            else:
                # Use LLM translations (default)
                segment_translations = [seg_draft.translation for seg_draft in revised.segments]
            
            # Create segments with translations
            for i, seg_draft in enumerate(revised.segments):
                # Convert speaker index to A/B/C ID
                speaker_id = None
                if seg_draft.speaker is not None and speakers_list:
                    speaker_id = speaker_ids[seg_draft.speaker]
                
                # Convert short UUIDs to full UUIDs
                full_item_ids = [
                    self.short_to_full_uuid.get(short_id, short_id)
                    for short_id in seg_draft.learning_item_ids
                ]
                
                segment = Segment(
                    speaker=speaker_id,
                    text=seg_draft.text,
                    translation=segment_translations[i] if i < len(segment_translations) else "",
                    learning_item_ids=full_item_ids,
                )
                segments.append(segment)

            # Concatenate text
            full_text = "\n".join([seg.text for seg in segments])

            # Deduplicate learning_item_ids (convert short to full UUIDs)
            all_ids = []
            for seg in segments:
                all_ids.extend(seg.learning_item_ids)
            unique_ids = list(dict.fromkeys(all_ids))  # Preserve order

            content_unit = ContentUnit(
                id=content_id,
                language=self.language,
                type=overview.type,
                title=overview.title,
                description=f"{self.level} level {overview.type.value} about {scenario_name}",
                text=full_text,
                segments=segments,
                speakers=speakers_list if speakers_list else None,
                learning_item_ids=unique_ids,
                topic_ids=[topic_id],
                scenario_ids=[scenario_id],
                level_system=self.level_system,
                level_min=self.level,
                level_max=self.level,
                has_audio=False,
                has_questions=False,
                publishable=False,
            )

            if overview.type == ContentType.CONVERSATION:
                batch.conversations.append(content_unit)
            else:
                batch.stories.append(content_unit)

        return batch

    def _validate_content_batch(self, batch: ContentBatch) -> None:
        """Validate all content in batch."""
        all_content = batch.conversations + batch.stories
        
        for content in all_content:
            if not self.validate_presence(content):
                logger.warning(f"Presence validation failed for content: {content.id}")

    def _calculate_cot_metrics(
        self, cot_response: ChainOfThoughtContent
    ) -> Dict:
        """Calculate chain-of-thought quality metrics."""
        metrics = {
            "num_drafts": len(cot_response.initial_drafts),
            "num_critiques": len(cot_response.critiques),
            "num_revised": len(cot_response.revised_contents),
            "avg_coverage_score": 0.0,
            "avg_level_score": 0.0,
            "avg_flow_score": 0.0,
            "total_improvements": 0,
        }

        if cot_response.critiques:
            metrics["avg_coverage_score"] = sum(
                c.coverage_score for c in cot_response.critiques
            ) / len(cot_response.critiques)
            metrics["avg_level_score"] = sum(
                c.level_appropriateness_score for c in cot_response.critiques
            ) / len(cot_response.critiques)
            metrics["avg_flow_score"] = sum(
                c.natural_flow_score for c in cot_response.critiques
            ) / len(cot_response.critiques)

        if cot_response.revised_contents:
            metrics["total_improvements"] = sum(
                len(r.improvements_made) for r in cot_response.revised_contents
            )

        # Check if revised versions improved coverage
        improved_count = 0
        for i, critique in enumerate(cot_response.critiques):
            if i < len(cot_response.initial_drafts) and i < len(cot_response.revised_contents):
                initial = cot_response.initial_drafts[i]
                revised = cot_response.revised_contents[i]

                initial_learning_items_used = set()
                for seg in initial.segments:
                    initial_learning_items_used.update(seg.learning_item_ids)

                revised_learning_items_used = set()
                for seg in revised.segments:
                    revised_learning_items_used.update(seg.learning_item_ids)
                
                if len(revised_learning_items_used) > len(initial_learning_items_used):
                    improved_count += 1

        if cot_response.critiques:
            metrics["improvement_rate"] = improved_count / len(cot_response.critiques)

        return metrics
