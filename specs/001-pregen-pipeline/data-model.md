# Data Model & Schemas

**Feature**: Pre-generation Pipeline for Learning Content  
**Phase**: 1 (Design & Contracts)  
**Date**: 2026-01-26

## Overview

All entities are defined as Pydantic models in `src/pipeline/validators/schema.py` for use with Instructor. JSON schemas are derived from these models for contract validation and API documentation.

## Core Entities

### 1. Learning Item

**Purpose**: Atomic pedagogical unit (vocabulary, grammar, pronunciation, cultural note)

**Pydantic Model**:
```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class LevelSystem(str, Enum):
    CEFR = "cefr"
    HSK = "hsk"
    JLPT = "jlpt"

class Category(str, Enum):
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

class Example(BaseModel):
    text: str = Field(..., description="Example text in target language")
    translation: str = Field(..., description="English translation of the example")
    media_urls: List[str] = Field(default_factory=list, description="URLs for media resources (audio, image, video)")

class LearningItem(BaseModel):
    id: str = Field(..., description="UUID v4")
    language: str = Field(..., description="ISO 639-1 code: zh, ja, fr, en, es")
    category: Category
    target_item: str = Field(..., description="The word, phrase, or grammar pattern being taught")
    definition: str = Field(..., description="Clear English definition suitable for learners, to be used in flashcards")
    examples: List[Example] = Field(..., min_items=3, max_items=5, description="Contextual usage examples with translations and optional media")
    
    # Optional fields (language-specific)
    romanization: Optional[str] = Field(None, description="Pinyin for Chinese, Romaji for Japanese")
    sense_gloss: Optional[str] = Field(None, description="Disambiguation for polysemous words: 'bank (financial)' vs 'bank (river)'")
    lemma: Optional[str] = Field(None, description="Base form for inflected words")
    pos: Optional[str] = Field(None, description="Part of speech: noun, verb, adj, etc.")
    aliases: List[str] = Field(default_factory=list, description="Alternative forms or spellings")
    media_urls: List[str] = Field(default_factory=list, description="URLs for media resources (audio, image, video) for this learning item")
    
    # Level metadata
    level_system: LevelSystem
    level_min: str = Field(..., description="Minimum proficiency level: A1, HSK1, N5")
    level_max: str = Field(..., description="Maximum proficiency level: C1, HSK6, N1")
    
    # Audit fields
    created_at: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(default="1.0.0", description="Schema version")
    source_file: Optional[str] = Field(None, description="Original source file path")
    
    class Config:
        json_schema_extra = {
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
                "version": "1.0.0"
            }
        }
```

**JSON Schema** (stored in `contracts/learning_item.schema.json`):
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["id", "language", "category", "target_item", "definition", "examples", "level_system", "level_min", "level_max"],
  "properties": {
    "id": {"type": "string", "format": "uuid"},
    "language": {"type": "string", "enum": ["zh", "ja", "fr", "en", "es"]},
    "category": {"type": "string", "enum": ["vocab", "grammar", "pronunciation", "idiom", "functional", "cultural", "writing_system", "sociolinguistic", "pragmatic", "literacy", "pattern", "other"]},
    "target_item": {"type": "string"},
    "definition": {"type": "string"},
    "examples": {
      "type": "array", 
      "items": {
        "type": "object",
        "required": ["text", "translation"],
        "properties": {
          "text": {"type": "string"},
          "translation": {"type": "string"},
          "media_urls": {"type": "array", "items": {"type": "string"}}
        }
      },
      "minItems": 3, 
      "maxItems": 5
    },
    "romanization": {"type": "string"},
    "sense_gloss": {"type": "string"},
    "lemma": {"type": "string"},
    "pos": {"type": "string"},
    "aliases": {"type": "array", "items": {"type": "string"}},
    "level_system": {"type": "string", "enum": ["cefr", "hsk", "jlpt"]},
    "level_min": {"type": "string"},
    "level_max": {"type": "string"},
    "created_at": {"type": "string", "format": "date-time"},
    "version": {"type": "string"},
    "source_file": {"type": "string"}
  }
}
```

**File Storage**: `havachat-knowledge/generated content/{language}/{level}/{category}/item-{uuid}.json`

**Validation Rules**:
- Chinese/Japanese MUST have `romanization` (enforced by language-specific enrichers)
- If `sense_gloss` is present, there must be another item with same `target_item` but different `sense_gloss` (polysemy)
- `level_min` <= `level_max` in ordinal comparison (A1 < A2 < B1... or HSK1 < HSK2...)

---

### 2. Content Unit

**Purpose**: Conversation or story containing multiple segments, each linked to learning items

**Pydantic Model**:
```python
class ContentType(str, Enum):
    CONVERSATION = "conversation"
    STORY = "story"

class SegmentType(str, Enum):
    DIALOGUE = "dialogue"
    NARRATION = "narration"
    QUESTION = "question"

class Segment(BaseModel):
    segment_id: str = Field(..., description="Unique ID within content unit")
    type: SegmentType
    speaker: Optional[str] = Field(None, description="Speaker name for dialogue, null for narration")
    text: str = Field(..., description="Text in target language")
    translation: Optional[str] = Field(None, description="English translation")
    learning_item_ids: List[str] = Field(..., description="UUIDs of learning items featured in this segment")
    start_time_ms: Optional[int] = Field(None, description="Audio start timestamp (milliseconds)")
    end_time_ms: Optional[int] = Field(None, description="Audio end timestamp (milliseconds)")

class ContentUnit(BaseModel):
    id: str = Field(..., description="UUID v4")
    language: str = Field(..., description="ISO 639-1 code")
    type: ContentType
    title: str = Field(..., description="Content title")
    description: str = Field(..., description="Brief summary of content")
    text: str = Field(..., description="Full text (concatenated segments)")
    segments: List[Segment] = Field(..., min_items=1)
    learning_item_ids: List[str] = Field(..., description="All learning items featured in this content (deduplicated)")
    
    # Metadata
    topic_ids: List[str] = Field(default_factory=list, description="Thematic categories")
    scenario_ids: List[str] = Field(default_factory=list, description="Concrete situations")
    level_system: LevelSystem
    level_min: str
    level_max: str
    word_count: int = Field(..., description="Total word count (language-aware tokenization)")
    estimated_reading_time_seconds: int = Field(..., description="Based on average reading speed for target language")
    
    # Status flags
    has_audio: bool = Field(default=False)
    has_questions: bool = Field(default=False)
    publishable: bool = Field(default=False, description="True if passed all QA gates")
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(default="1.0.0")
    
    class Config:
        json_schema_extra = {
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
                        "learning_item_ids": ["550e8400-e29b-41d4-a716-446655440001", "550e8400-e29b-41d4-a716-446655440002"]
                    }
                ],
                "learning_item_ids": ["550e8400-e29b-41d4-a716-446655440001", "550e8400-e29b-41d4-a716-446655440002"],
                "topic_ids": ["social-interaction"],
                "scenario_ids": ["meeting-someone-new"],
                "level_system": "cefr",
                "level_min": "A1",
                "level_max": "A1",
                "word_count": 12,
                "estimated_reading_time_seconds": 30,
                "has_audio": false,
                "has_questions": false,
                "publishable": false,
                "created_at": "2026-01-26T12:00:00Z",
                "version": "1.0.0"
            }
        }
```

**File Storage**: `havachat-knowledge/generated content/{language}/{level}/{type}s/content-{uuid}.json`

**Validation Rules**:
- Every `learning_item_id` in segments must exist in `{language}/{level}/vocab/` or `grammar/`
- Every `learning_item_id` in segments must appear in `learning_item_ids` (deduplicated list)
- `text` field should equal concatenation of all segment texts (validation check)
- If `has_audio=true`, all segments must have `start_time_ms` and `end_time_ms`

---

### 3. Question Set

**Purpose**: Comprehension questions for a content unit

**Pydantic Model**:
```python
class QuestionType(str, Enum):
    MCQ = "mcq"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    SUMMARY = "summary"

class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class MCQOption(BaseModel):
    option_id: str = Field(..., description="A, B, C, D")
    text: str

class Question(BaseModel):
    id: str = Field(..., description="UUID v4")
    content_id: str = Field(..., description="Parent content unit UUID")
    segment_range: Optional[List[str]] = Field(None, description="Segment IDs this question covers, null for full content")
    question_type: QuestionType
    question_text: str
    
    # Type-specific fields
    options: Optional[List[MCQOption]] = Field(None, description="For MCQ only, exactly 4 options")
    answer_key: str = Field(..., description="For MCQ: 'A'/'B'/'C'/'D', for true_false: 'true'/'false', for short_answer: expected answer text")
    rationale: str = Field(..., description="Explanation of why answer is correct and learning value")
    
    # Metadata
    difficulty: Difficulty
    tags: List[str] = Field(..., description="inference, detail, main-idea, vocab-focus, grammar-focus")
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(default="1.0.0")
    
    class Config:
        json_schema_extra = {
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
                    {"option_id": "D", "text": "Not mentioned"}
                ],
                "answer_key": "A",
                "rationale": "Alice explicitly states 'Je m'appelle Alice' (My name is Alice). This tests basic comprehension of self-introduction patterns.",
                "difficulty": "easy",
                "tags": ["detail", "vocab-focus"],
                "created_at": "2026-01-26T12:00:00Z",
                "version": "1.0.0"
            }
        }
```

**File Storage**: `havachat-knowledge/generated content/{language}/{level}/questions/questions-{content_id}.json`

**Validation Rules**:
- `content_id` must reference an existing content unit
- For `question_type=mcq`, must have exactly 4 options and `answer_key` in ['A', 'B', 'C', 'D']
- For `question_type=true_false`, must have no options and `answer_key` in ['true', 'false']
- `segment_range` IDs must exist in parent content unit

---

### 4. Topic

**Purpose**: Broad thematic category (e.g., "food", "travel", "work")

**Pydantic Model**:
```python
class Topic(BaseModel):
    id: str = Field(..., description="Slug: food, travel, work-business")
    name: str = Field(..., description="English name")
    aliases: List[str] = Field(default_factory=list, description="Alternative names")
    language: Optional[str] = Field(None, description="Language-specific topic, or null for universal")
    parent_topic_id: Optional[str] = Field(None, description="For hierarchical topics: food > restaurant-dining")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "food",
                "name": "Food & Dining",
                "aliases": ["cuisine", "eating", "meals"],
                "language": None,
                "parent_topic_id": None
            }
        }
```

**File Storage**: `havachat-knowledge/generated content/topics.json` (single file, array of topics)

---

### 5. Scenario

**Purpose**: Concrete situation within a topic (e.g., "ordering at restaurant", "airport check-in")

**Pydantic Model**:
```python
class Scenario(BaseModel):
    id: str = Field(..., description="UUID v4 or slug: ordering-at-restaurant, airport-checkin")
    name: str = Field(..., description="English name")
    aliases: List[str] = Field(default_factory=list)
    topic_id: str = Field(..., description="Parent topic")
    language: Optional[str] = Field(None, description="Language-specific scenario, or null for universal")
    description: str = Field(..., description="Brief description of the situation")
    
    # Rich tagging for search and organization
    tags: List[str] = Field(default_factory=list, description="Searchable tags: formality, setting, participant-count, etc.")
    formality: Optional[str] = Field(None, description="formal, informal, neutral")
    setting: Optional[str] = Field(None, description="indoor, outdoor, virtual, public, private")
    participant_count: Optional[str] = Field(None, description="one-on-one, small-group, large-group")
    interaction_type: Optional[str] = Field(None, description="transactional, social, academic, professional")
    
    # Content relationships
    content_unit_ids: List[str] = Field(default_factory=list, description="Content units associated with this scenario")
    learning_item_ids: List[str] = Field(default_factory=list, description="Learning items commonly used in this scenario")
    
    # Usage tracking for live API
    usage_count: int = Field(default=0, description="Number of times this scenario has been requested")
    last_used: Optional[datetime] = Field(None, description="Last time this scenario was used")
    
    # Similarity metadata for search
    embedding: Optional[List[float]] = Field(None, description="Semantic embedding for similarity search")
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(default="manual", description="manual, live-api, imported")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "ordering-at-restaurant",
                "name": "Ordering Food at a Restaurant",
                "aliases": ["restaurant order", "dining out"],
                "topic_id": "food",
                "language": None,
                "description": "Interacting with a server to order food and drinks at a casual restaurant"
            }
        }
```

**File Storage**: 
- Initial: `havachat-knowledge/generated content/scenarios.json` (single file, array of scenarios)
- Live API: `havachat-knowledge/generated content/{language}/scenarios/{scenario-id}.json` (per-scenario files for growing library)

**Database Partitioning**:
- All scenario data MUST be partitioned by language at the database level
- No cross-language joins required (each language is independent)
- Enables horizontal scaling and optimized queries per language
- Meilisearch: One index per language (`scenarios_zh`, `scenarios_ja`, `scenarios_fr`)
- Postgres: Partition tables by language or use separate schemas (`zh_scenarios`, `ja_scenarios`, `fr_scenarios`)

---

### 6. Usage Metadata

**Purpose**: Track how often each learning item appears in published content (for future frequency balancing)

**Pydantic Model**:
```python
class UsageStats(BaseModel):
    learning_item_id: str
    appearances_count: int = Field(default=0, description="Number of published content units featuring this item")
    last_used_content_id: Optional[str] = Field(None)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
```

**File Storage**: `havachat-knowledge/generated content/{language}/{level}/usage_stats.json` (array of stats)

---

### 7. Validation Report

**Purpose**: Output of QA gates for a batch

**Pydantic Model**:
```python
class FailureType(str, Enum):
    SCHEMA_VALIDATION = "schema_validation"
    PRESENCE_CHECK = "presence_check"
    DUPLICATION = "duplication"
    LINK_CORRECTNESS = "link_correctness"
    ANSWERABILITY = "answerability"
    DIFFICULTY_MISALIGNMENT = "difficulty_misalignment"
    LANGUAGE_CONTAMINATION = "language_contamination"

class FlaggedItem(BaseModel):
    item_id: str
    item_type: str = Field(..., description="learning_item, content_unit, question")
    failure_type: FailureType
    failure_reason: str
    line_reference: Optional[str] = Field(None, description="File path or segment ID")
    suggested_fix: Optional[str] = Field(None)

class ValidationReport(BaseModel):
    batch_id: str = Field(..., description="UUID for this QA run")
    language: str
    level: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_items: int
    passed_count: int
    failed_count: int
    flagged_items: List[FlaggedItem]
    summary_stats: dict = Field(..., description="Pass rate, most common failures")
    
    class Config:
        json_schema_extra = {
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
                        "suggested_fix": "Add sense_gloss disambiguation or merge items"
                    }
                ],
                "summary_stats": {
                    "pass_rate_percent": 95,
                    "most_common_failures": ["duplication", "presence_check"]
                }
            }
        }
```

**File Storage**: `havachat-knowledge/generated content/{language}/{level}/qa_reports/report-{timestamp}.json` and `.md`

---

## Relationships

```
Topic (1) ─────< Scenario (many)
          ↓                ↓
     ContentUnit ────────> LearningItem (many-to-many via learning_item_ids)
          ↓
     QuestionSet ────────> ContentUnit (many-to-one via content_id)
          ↓
    ValidationReport ────> LearningItem/ContentUnit/Question (via flagged_items)
```

## Schema Evolution

- All entities include `version` field (semver)
- Breaking changes increment major version (e.g., 1.0.0 → 2.0.0)
- Pipeline must handle multiple schema versions during migration periods
- Pydantic V2 `model_validate()` used for runtime validation
