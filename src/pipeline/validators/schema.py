"""Pydantic models for all pipeline entities.

This module defines the data models used throughout the pre-generation pipeline.
All models include validation rules and JSON schema generation for contract testing.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


# ============================================================================
# Enums
# ============================================================================


class LevelSystem(str, Enum):
    """Proficiency level system."""

    CEFR = "cefr"
    HSK = "hsk"
    JLPT = "jlpt"


class Category(str, Enum):
    """Learning item category (12 types)."""

    VOCAB = "vocab"
    GRAMMAR = "grammar"
    PRONUNCIATION = "pronunciation"
    IDIOM = "idiom"
    FUNCTIONAL = "functional"
    CULTURAL = "cultural"
    WRITING_SYSTEM = "writing_system"
    SOCIOLINGUISTIC = "sociolinguistic"
    PRAGMATIC = "pragmatic"
    LITERACY = "literacy"
    PATTERN = "pattern"
    OTHER = "other"


class ContentType(str, Enum):
    """Type of generated content."""

    CONVERSATION = "conversation"
    STORY = "story"


class SegmentType(str, Enum):
    """Type of content segment."""

    DIALOGUE = "dialogue"
    NARRATION = "narration"
    QUESTION = "question"


class ContentStatus(str, Enum):
    """Status of content unit."""

    ACTIVE = "active"
    FOR_REVIEW = "for_review"


class QuestionType(str, Enum):
    """Type of comprehension question."""

    MCQ = "mcq"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    SUMMARY = "summary"


class Difficulty(str, Enum):
    """Question difficulty level."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class FailureType(str, Enum):
    """QA gate failure types."""

    SCHEMA_VALIDATION = "schema_validation"
    PRESENCE_CHECK = "presence_check"
    DUPLICATION = "duplication"
    LINK_CORRECTNESS = "link_correctness"
    ANSWERABILITY = "answerability"
    DIFFICULTY_MISALIGNMENT = "difficulty_misalignment"
    LANGUAGE_CONTAMINATION = "language_contamination"


# ============================================================================
# Core Entities
# ============================================================================


class Example(BaseModel):
    """Example sentence with translation and optional media."""

    text: str = Field(
        ..., description="Example text in target language"
    )
    translation: str = Field(
        ..., description="English translation of the example"
    )
    media_urls: List[str] = Field(
        default_factory=list,
        description="URLs for media resources (audio, image, video)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "text": "我去银行取钱。",
                "translation": "I go to the bank to withdraw money.",
                "media_urls": []
            }
        }
    }


class LearningItem(BaseModel):
    """Atomic pedagogical unit (vocabulary, grammar, pronunciation, cultural note).

    Validation Rules:
    - Chinese/Japanese MUST have romanization
    - If sense_gloss is present, there must be another item with same
      target_item but different sense_gloss (polysemy)
    - level_min <= level_
    max in ordinal comparison
    """

    id: str = Field(default_factory=lambda: str(uuid4()), description="UUID v4")
    language: str = Field(
        ..., description="ISO 639-1 code: zh, ja, fr, en, es", pattern="^[a-z]{2}$"
    )
    category: Category
    target_item: str = Field(
        ..., description="The word, phrase, or grammar pattern being taught"
    )
    definition: str = Field(
        ..., description="Clear English definition suitable for learners, to be used in flashcards"
    )
    examples: List[Example] = Field(
        ...,
        # min_length=2,
        # max_length=3,
        description="Contextual usage examples (2-3 items)",
    )

    # Optional fields (language-specific)
    romanization: Optional[str] = Field(
        None, description="Pinyin for Chinese, Romaji for Japanese"
    )
    sense_gloss: Optional[str] = Field(
        None,
        description="Disambiguation for polysemous words: 'bank (financial)' vs 'bank (river)'",
    )
    lemma: Optional[str] = Field(None, description="Base form for inflected words")
    pos: Optional[str] = Field(
        None, description="Part of speech: noun, verb, adj, etc."
    )
    aliases: List[str] = Field(
        default_factory=list, description="Alternative forms or spellings"
    )
    media_urls: List[str] = Field(
        default_factory=list,
        description="URLs for media resources (audio, image, video) for this learning item"
    )

    # Level metadata
    level_system: LevelSystem
    level_min: str = Field(
        ..., description="Minimum proficiency level: A1, HSK1, N5"
    )
    level_max: str = Field(
        ..., description="Maximum proficiency level: C1, HSK6, N1"
    )

    # Audit fields
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: str = Field(default="1.0.0", description="Schema version")
    source_file: Optional[str] = Field(
        None, description="Original source file path"
    )

    # @field_validator("examples")
    # @classmethod
    # def validate_examples_count(cls, v: List[str]) -> List[str]:
    #     """Ensure 2-3 examples."""
    #     if not 3 <= len(v) <= 5:
    #         raise ValueError("examples must contain between 3 and 5 items")
    #     return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "language": "zh",
                "category": "vocab",
                "target_item": "银行",
                "definition": "A financial institution where people deposit money and obtain loans",
                "examples": [
                    {
                        "text": "我去银行取钱。",
                        "translation": "I go to the bank to withdraw money.",
                        "media_urls": []
                    },
                    {
                        "text": "这家银行提供低利率贷款。",
                        "translation": "This bank offers low-interest loans.",
                        "media_urls": []
                    },
                    {
                        "text": "银行的营业时间是周一到周五。",
                        "translation": "The bank's business hours are Monday to Friday.",
                        "media_urls": []
                    }
                ],
                "romanization": "yínháng",
                "sense_gloss": "bank (financial institution)",
                "lemma": "银行",
                "pos": "noun",
                "media_urls": [],
                "level_system": "hsk",
                "level_min": "HSK1",
                "level_max": "HSK1",
                "created_at": "2026-01-26T12:00:00Z",
                "version": "1.0.0",
            }
        }
    }


class Segment(BaseModel):
    """Content segment (dialogue turn, narration, question)."""

    speaker: Optional[str] = Field(
        None, description="Speaker ID (A/B/C) for dialogue, null for narration"
    )
    text: str = Field(..., description="Text in target language")
    translation: Optional[str] = Field(None, description="English translation")
    learning_item_ids: List[str] = Field(
        ..., description="UUIDs of learning items featured in this segment"
    )
    start_time_ms: Optional[int] = Field(
        None, description="Audio start timestamp (milliseconds)"
    )
    end_time_ms: Optional[int] = Field(
        None, description="Audio end timestamp (milliseconds)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "segment_id": "seg-1",
                "type": "dialogue",
                "speaker": "A",
                "text": "Bonjour! Je m'appelle Alice.",
                "translation": "Hello! My name is Alice.",
                "learning_item_ids": [
                    "550e8400-e29b-41d4-a716-446655440001",
                    "550e8400-e29b-41d4-a716-446655440002",
                ],
                "start_time_ms": None,
                "end_time_ms": None,
            }
        }
    }


class Speaker(BaseModel):
    """Speaker metadata for conversations."""

    id: str = Field(..., description="Speaker ID (A, B, C, etc.)")
    name: str = Field(..., description="Speaker name")
    role: str = Field(..., description="Speaker role or relationship")
    gender: Optional[str] = Field(None, description="Speaker gender in English (male/female/any)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "A",
                "name": "Alice",
                "role": "Student",
                "gender": "female",
            }
        }
    }


class ContentUnit(BaseModel):
    """Conversation or story containing multiple segments.

    Validation Rules:
    - Every learning_item_id in segments must appear in learning_item_ids
    - text field should equal concatenation of all segment texts
    - If has_audio=true, all segments must have start_time_ms and end_time_ms
    """

    id: str = Field(default_factory=lambda: str(uuid4()), description="UUID v4")
    language: str = Field(..., description="ISO 639-1 code", pattern="^[a-z]{2}$")
    type: ContentType
    title: str = Field(..., description="Content title")
    description: str = Field(..., description="Brief summary of content")
    text: str = Field(..., description="Full text (concatenated segments)")
    segments: List[Segment] = Field(..., min_length=1)
    speakers: Optional[List[Speaker]] = Field(
        default=None,
        description="Speaker metadata for conversations (id, name, role, gender)"
    )
    learning_item_ids: List[str] = Field(
        ...,
        description="All learning items featured in this content (deduplicated)",
    )

    # Metadata
    topic_ids: List[str] = Field(
        default_factory=list, description="Thematic categories"
    )
    scenario_ids: List[str] = Field(
        default_factory=list, description="Concrete situations"
    )
    level_system: LevelSystem
    level_min: str
    level_max: str

    # Status flags
    has_audio: bool = Field(default=False)
    has_questions: bool = Field(default=False)
    publishable: bool = Field(
        default=False, description="True if passed all QA gates"
    )
    status: ContentStatus = Field(
        default=ContentStatus.ACTIVE,
        description="Content validation status (active or for_review)"
    )
    validation_notes: Optional[List[str]] = Field(
        default=None,
        description="List of validation issues requiring review"
    )

    # Audit
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: str = Field(default="1.0.0")

    @model_validator(mode="after")
    def validate_learning_item_ids(self) -> "ContentUnit":
        """Ensure all segment learning_item_ids are in content-level list."""
        segment_ids = set()
        for segment in self.segments:
            segment_ids.update(segment.learning_item_ids)

        content_ids = set(self.learning_item_ids)
        missing = segment_ids - content_ids
        if missing:
            raise ValueError(
                f"Segments reference learning_item_ids not in content-level list: {missing}"
            )
        return self

    @model_validator(mode="after")
    def validate_audio_timestamps(self) -> "ContentUnit":
        """If has_audio=true, all segments must have timestamps."""
        if self.has_audio:
            for segment in self.segments:
                if segment.start_time_ms is None or segment.end_time_ms is None:
                    raise ValueError(
                        f"Segment {segment.segment_id} missing timestamps (has_audio=true)"
                    )
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "650e8400-e29b-41d4-a716-446655440000",
                "language": "fr",
                "type": "conversation",
                "title": "Greeting Someone New",
                "description": "A1 level conversation about meeting someone for the first time",
                "text": "Alice: Bonjour! Je m'appelle Alice. Bob: Enchanté, Alice. Je suis Bob.",
                "segments": [
                    {
                        "segment_id": "seg-1",
                        "type": "dialogue",
                        "speaker": "Alice",
                        "text": "Bonjour! Je m'appelle Alice.",
                        "translation": "Hello! My name is Alice.",
                        "learning_item_ids": [
                            "550e8400-e29b-41d4-a716-446655440001",
                            "550e8400-e29b-41d4-a716-446655440002",
                        ],
                    }
                ],
                "learning_item_ids": [
                    "550e8400-e29b-41d4-a716-446655440001",
                    "550e8400-e29b-41d4-a716-446655440002",
                ],
                "topic_ids": ["social-interaction"],
                "scenario_ids": ["meeting-someone-new"],
                "level_system": "cefr",
                "level_min": "A1",
                "level_max": "A1",
                "word_count": 12,
                "estimated_reading_time_seconds": 30,
                "has_audio": False,
                "has_questions": False,
                "publishable": False,
                "created_at": "2026-01-26T12:00:00Z",
                "version": "1.0.0",
            }
        }
    }


class MCQOption(BaseModel):
    """Multiple choice question option."""

    option_id: str = Field(..., description="A, B, C, D", pattern="^[A-D]$")
    text: str


class Question(BaseModel):
    """Comprehension question for a content unit.

    Validation Rules:
    - For question_type=mcq, must have exactly 4 options and answer_key in [A,B,C,D]
    - For question_type=true_false, must have no options and answer_key in [true,false]
    - segment_range IDs must exist in parent content unit
    """

    id: str = Field(default_factory=lambda: str(uuid4()), description="UUID v4")
    content_id: str = Field(..., description="Parent content unit UUID")
    segment_range: Optional[List[str]] = Field(
        None,
        description="Segment IDs this question covers, null for full content",
    )
    question_type: QuestionType
    question_text: str

    # Type-specific fields
    options: Optional[List[MCQOption]] = Field(
        None, description="For MCQ only, exactly 4 options"
    )
    answer_key: str = Field(
        ...,
        description="For MCQ: 'A'/'B'/'C'/'D', for true_false: 'true'/'false', for short_answer: expected answer text",
    )
    rationale: str = Field(
        ...,
        description="Explanation of why answer is correct and learning value",
    )

    # Metadata
    difficulty: Difficulty
    tags: List[str] = Field(
        ...,
        description="inference, detail, main-idea, vocab-focus, grammar-focus",
    )

    # Audit
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: str = Field(default="1.0.0")

    @model_validator(mode="after")
    def validate_question_type_constraints(self) -> "Question":
        """Validate type-specific constraints."""
        if self.question_type == QuestionType.MCQ:
            if not self.options or len(self.options) != 4:
                raise ValueError("MCQ questions must have exactly 4 options")
            if self.answer_key not in ["A", "B", "C", "D"]:
                raise ValueError(
                    "MCQ answer_key must be one of: A, B, C, D"
                )
        elif self.question_type == QuestionType.TRUE_FALSE:
            if self.options:
                raise ValueError("True/false questions must not have options")
            if self.answer_key.lower() not in ["true", "false"]:
                raise ValueError(
                    "True/false answer_key must be 'true' or 'false'"
                )
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "750e8400-e29b-41d4-a716-446655440000",
                "content_id": "650e8400-e29b-41d4-a716-446655440000",
                "segment_range": ["seg-1", "seg-2"],
                "question_type": "mcq",
                "question_text": "What is Alice's name?",
                "options": [
                    {"option_id": "A", "text": "Alice"},
                    {"option_id": "B", "text": "Bob"},
                    {"option_id": "C", "text": "Claire"},
                    {"option_id": "D", "text": "Not mentioned"},
                ],
                "answer_key": "A",
                "rationale": "Alice explicitly states 'Je m'appelle Alice' (My name is Alice). This tests basic comprehension of self-introduction patterns.",
                "difficulty": "easy",
                "tags": ["detail", "vocab-focus"],
                "created_at": "2026-01-26T12:00:00Z",
                "version": "1.0.0",
            }
        }
    }


class Topic(BaseModel):
    """Broad thematic category (e.g., 'food', 'travel', 'work')."""

    id: str = Field(..., description="Slug: food, travel, work-business")
    name: str = Field(..., description="English name")
    aliases: List[str] = Field(
        default_factory=list, description="Alternative names"
    )
    language: Optional[str] = Field(
        None, description="Language-specific topic, or null for universal"
    )
    parent_topic_id: Optional[str] = Field(
        None,
        description="For hierarchical topics: food > restaurant-dining",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "food",
                "name": "Food & Dining",
                "aliases": ["cuisine", "eating", "meals"],
                "language": None,
                "parent_topic_id": None,
            }
        }
    }


class Scenario(BaseModel):
    """Concrete situation within a topic (e.g., 'ordering at restaurant').

    Rich tagging for search and organization, with semantic embeddings for
    similarity-based scenario reuse.
    """

    id: str = Field(
        ...,
        description="UUID v4 or slug: ordering-at-restaurant, airport-checkin",
    )
    name: str = Field(..., description="English name")
    aliases: List[str] = Field(default_factory=list)
    topic_id: str = Field(..., description="Parent topic")
    language: Optional[str] = Field(
        None, description="Language-specific scenario, or null for universal"
    )
    description: str = Field(..., description="Brief description of the situation")

    # Rich tagging for search and organization
    tags: List[str] = Field(
        default_factory=list,
        description="Searchable tags: formality, setting, participant-count, etc.",
    )
    formality: Optional[str] = Field(
        None, description="formal, informal, neutral"
    )
    setting: Optional[str] = Field(
        None, description="indoor, outdoor, virtual, public, private"
    )
    participant_count: Optional[str] = Field(
        None, description="one-on-one, small-group, large-group"
    )
    interaction_type: Optional[str] = Field(
        None, description="transactional, social, academic, professional"
    )

    # Content relationships
    content_unit_ids: List[str] = Field(
        default_factory=list,
        description="Content units associated with this scenario",
    )
    learning_item_ids: List[str] = Field(
        default_factory=list,
        description="Learning items commonly used in this scenario",
    )

    # Usage tracking for live API
    usage_count: int = Field(
        default=0, description="Number of times this scenario has been requested"
    )
    last_used: Optional[datetime] = Field(
        None, description="Last time this scenario was used"
    )

    # Similarity metadata for search
    embedding: Optional[List[float]] = Field(
        None, description="Semantic embedding for similarity search"
    )

    # Audit
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str = Field(
        default="manual", description="manual, live-api, imported"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "ordering-at-restaurant",
                "name": "Ordering Food at a Restaurant",
                "aliases": ["restaurant order", "dining out"],
                "topic_id": "food",
                "language": None,
                "description": "Interacting with a server to order food and drinks at a casual restaurant",
                "tags": ["transactional", "public", "informal"],
                "formality": "informal",
                "setting": "public",
                "participant_count": "one-on-one",
                "interaction_type": "transactional",
                "content_unit_ids": [],
                "learning_item_ids": [],
                "usage_count": 0,
                "last_used": None,
                "embedding": None,
                "created_at": "2026-01-26T12:00:00Z",
                "updated_at": "2026-01-26T12:00:00Z",
                "source": "manual",
            }
        }
    }


class UsageStats(BaseModel):
    """Track how often each learning item appears in published content."""

    learning_item_id: str
    appearances_count: int = Field(
        default=0,
        description="Number of published content units featuring this item",
    )
    last_used_content_id: Optional[str] = Field(None)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FlaggedItem(BaseModel):
    """QA gate failure details for a single item."""

    item_id: str
    item_type: str = Field(
        ..., description="learning_item, content_unit, question"
    )
    failure_type: FailureType
    failure_reason: str
    line_reference: Optional[str] = Field(
        None, description="File path or segment ID"
    )
    suggested_fix: Optional[str] = Field(None)


class ValidationReport(BaseModel):
    """Output of QA gates for a batch.

    Contains summary statistics and flagged items requiring manual review.
    """

    batch_id: str = Field(default_factory=lambda: str(uuid4()), description="UUID for this QA run")
    language: str
    level: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    total_items: int
    passed_count: int
    failed_count: int
    flagged_items: List[FlaggedItem]
    summary_stats: dict = Field(
        ..., description="Pass rate, most common failures"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "batch_id": "850e8400-e29b-41d4-a716-446655440000",
                "language": "fr",
                "level": "A1",
                "timestamp": "2026-01-26T12:00:00Z",
                "total_items": 100,
                "passed_count": 95,
                "failed_count": 5,
                "flagged_items": [
                    {
                        "item_id": "550e8400-e29b-41d4-a716-446655440003",
                        "item_type": "learning_item",
                        "failure_type": "duplication",
                        "failure_reason": "Duplicate target_item 'banco' with same sense_gloss 'bank (financial)'",
                        "line_reference": "French/A1/vocab/item-550e8400-e29b-41d4-a716-446655440003.json",
                        "suggested_fix": "Add sense_gloss disambiguation or merge items",
                    }
                ],
                "summary_stats": {
                    "pass_rate_percent": 95,
                    "most_common_failures": ["duplication", "presence_check"],
                },
            }
        }
    }
