# Data Model: Notion Audio Content Processor

**Feature**: `001-notion-audio-processor`  
**Date**: 2026-02-12  
**Purpose**: Define entities, relationships, validation rules, and state transitions

---

## Entity Relationship Diagram

```
┌─────────────────────────┐
│  Audio Content Record   │
│  (Notion Database)      │
│─────────────────────────│
│ • id: str               │
│ • name: str             │
│ • content: str          │
│ • topic: str            │
│ • sub_type: str         │
│ • status: Status        │
│ • voices: [Relation]    │◄────┐
│ • description: str?     │     │ References
│ • tags: str?            │     │
└─────────────────────────┘     │
           │                    │
           │ Generates          │
           ▼                    │
┌─────────────────────────┐     │
│  Generated Audio File   │     │
│  (Filesystem)           │     │
│─────────────────────────│     │
│ • path: Path            │     │
│ • format: str           │     │
│ • duration: float       │     │
│ • timestamps: Transcript│     │
│ • content_hash: str     │     │
└─────────────────────────┘     │
                                │
┌─────────────────────────┐     │
│  Voice Configuration    │     │
│  (Notion Database)      │─────┘
│─────────────────────────│
│ • id: str               │
│ • name: str             │
│ • voice_id: str         │
└─────────────────────────┘
           │ Uses
           ▼
┌─────────────────────────┐
│  Processing Metadata    │
│  (LLM Generated)        │
│─────────────────────────│
│ • description: str      │
│ • tags: List[str]       │
└─────────────────────────┘
```

---

## 1. Audio Content Record

**Source**: Notion Audio Database (via `NOTION_AUDIO_DATABASE_ID`)

**Purpose**: Represents content items that need audio generation

### Fields

| Field | Type | Required | Validation | Source |
|-------|------|----------|------------|--------|
| `id` | str | Yes | UUID format | Notion page ID |
| `name` | str | Yes | 1-255 chars, sanitized for filename | Notion "Name" property (title) |
| `content` | str | Yes | Non-empty, max ~50k chars | Notion "Content" property (text) |
| `topic` | str | Yes | Non-empty, sanitized for directory | Notion "Topic" property (select) |
| `sub_type` | str | Yes | Non-empty, sanitized for directory | Notion "Sub-Type" property (select) |
| `status` | Status | Yes | One of enum values | Notion "Status" property (select) |
| `voices` | Optional[str] | No | Valid Notion relation | Notion "Voices" property (relation) |
| `description` | Optional[str] | No | 50-200 chars after generation | Notion "Description" property (text) - **Updated by processor** |
| `tags` | Optional[str] | No | 3-7 hashtags, no spaces | Notion "Tags" property (text) - **Updated by processor** |

### Status Enum

```python
from enum import Enum

class AudioContentStatus(str, Enum):
    """Status values for Audio Content Record."""
    NOT_STARTED = "Not started"
    READY_FOR_AUDIO = "Ready for Audio"  # ← Filter target
    PROCESSING = "Processing"  # ← Set during generation
    COMPLETED = "Completed"  # ← Set after success
    FAILED = "Failed"  # ← Set on error
```

### Validation Rules

**FR-002**: All required fields must be present and non-empty
- `content` must not be only whitespace (edge case)
- `topic` and `sub_type` must be valid select values (not empty after sanitization)
- `name` and `id` must sanitize to non-empty strings

**FR-011**: Filename sanitization
- Remove/replace invalid filesystem characters: `< > : " / \ | ? *`
- Normalize Unicode (NFC form)
- Truncate to 255 bytes max
- Strip leading/trailing dots and spaces

### State Transitions

```
Not started ──────────────────────────────────────┐
                                                   │
Ready for Audio ──► Processing ──► Completed      │
     ▲                   │              │         │
     │                   └──► Failed ───┘         │
     │                           │                │
     └───────────────────────────┘────────────────┘
                              (Manual reset)
```

**Transition Rules**:
1. Processor queries records where `status == "Ready for Audio"`
2. On processing start: status → `"Processing"` (optional, for concurrent runs)
3. On success: status → `"Completed"` + update `description` and `tags`
4. On error: status → `"Failed"` + log error (do not update description/tags)
5. Manual reset: `"Failed"` or `"Completed"` → `"Ready for Audio"` (human intervention)

---

## 2. Voice Configuration

**Source**: Notion Voice Database (via `NOTION_VOICE_DATABASE_ID`)

**Purpose**: Maps human-readable voice names to ElevenLabs voice IDs

### Fields

| Field | Type | Required | Validation | Source |
|-------|------|----------|------------|--------|
| `id` | str | Yes | UUID format | Notion page ID (relation target) |
| `name` | str | Yes | Non-empty | Notion "Name" property (title) |
| `voice_id` | str | Yes | Valid ElevenLabs voice ID format | Notion "Voice Id" property (text) |

### Validation Rules

**FR-003**: Voice resolution
- `voice_id` must match ElevenLabs voice ID format (alphanumeric, 20-30 chars)
- If `voice_id` is invalid or missing, use default voice from `DEFAULT_VOICE_ID` env var
- If Audio Content Record has no `voices` relation, use default voice

### Caching Strategy

Voice configurations are **cached in memory** during batch run to minimize Notion API calls.

```python
voice_cache: Dict[str, str] = {}  # relation_id -> voice_id
```

**Cache invalidation**: Not needed for single batch run; cache cleared on next run.

---

## 3. Generated Audio File

**Source**: Filesystem at `<HAVACHAT_KNOWLEDGE_PATH>/<Topic>/<Sub-Type>/<ID>-<Name>.mp3`

**Purpose**: Stores generated TTS audio with timing information

### Fields

| Field | Type | Required | Validation | Source |
|-------|------|----------|------------|--------|
| `path` | Path | Yes | Valid filesystem path | Constructed from Topic/Sub-Type/ID-Name |
| `format` | str | Yes | `"mp3_44100_192"` | ElevenLabs output format (spec requirement) |
| `duration` | float | Yes | Positive seconds | From TTS API response |
| `timestamps` | Transcript | Yes | Valid Transcript schema | From `tts_with_elevenlabs.py` |
| `content_hash` | str | Yes | SHA-256 hex digest | Computed from `content` text |

### Transcript Schema

Defined in `src/datatypes/transcript.py`:

```python
from pydantic import BaseModel
from typing import List, Optional

class TranscriptWord(BaseModel):
    """Word-level timing information."""
    start: float  # Start time in seconds
    end: float    # End time in seconds
    word: str     # Word text
    score: Optional[float] = None  # Confidence score

class TranscriptSegment(BaseModel):
    """Sentence-level segment."""
    start: float
    end: float
    text: str
    words: List[TranscriptWord]

class Transcript(BaseModel):
    """Complete transcript with timing."""
    text: str  # Full text
    segments: List[TranscriptSegment]
    language: str
    duration: float
    transcriber: str = "elevenlabs_tts"
```

### Validation Rules

**FR-004**: Audio generation with timestamps
- Timestamps must be present at character, word, and sentence levels
- Timestamps must be monotonically increasing
- Total duration must match sum of segment durations (within tolerance)

**FR-005**: File organization
- Directory structure must be created if not exists (`mkdir -p` equivalent)
- File must be writable to target location
- Parent directories must be sanitized (same rules as filename)

**FR-014**: Duplicate detection
- Store content hash in sidecar file: `<audio>.mp3.hash`
- Compare hash before regeneration (skip if unchanged)

### File Structure Example

```
/Users/user/havachat-knowledge/
├── Education/
│   ├── Grammar/
│   │   ├── abc123-present-tense.mp3
│   │   ├── abc123-present-tense.mp3.hash
│   │   ├── abc124-past-tense.mp3
│   │   └── abc124-past-tense.mp3.hash
│   └── Vocabulary/
│       ├── def456-colors.mp3
│       └── def456-colors.mp3.hash
└── Conversation/
    └── Daily/
        ├── ghi789-greetings.mp3
        └── ghi789-greetings.mp3.hash
```

---

## 4. Processing Metadata

**Source**: LLM-generated via `havachat.utils.llm_client.LLMClient`

**Purpose**: Automatically generated content summary and categorization tags

### Fields

| Field | Type | Required | Validation | Written To |
|-------|------|----------|------------|------------|
| `description` | str | Yes | 50-200 chars | Notion "Description" field |
| `tags` | List[str] | Yes | 3-7 items, format `#tag` | Notion "Tags" field (joined) |

### Validation Rules

**FR-006**: Description generation
- Length: 50-200 characters (enforced by Pydantic `Field`)
- Content: Concise summary of what the content teaches/covers
- Language: English (regardless of content language)
- No special characters that break Notion rich text format

**FR-007**: Tags generation
- Count: 3-7 tags (enforced by Pydantic `Field`)
- Format: Each tag starts with `#`, no spaces within tag (e.g., `#presenttense` not `#present tense`)
- Content: Relevant to topic, sub-type, and content themes
- Example: `["#grammar", "#english", "#beginner", "#verbs"]`

### Pydantic Model

```python
from pydantic import BaseModel, Field, field_validator
from typing import List
import re

class ContentMetadata(BaseModel):
    """Metadata generated by LLM for audio content."""
    
    description: str = Field(
        ...,
        min_length=50,
        max_length=200,
        description="Concise content summary"
    )
    
    tags: List[str] = Field(
        ...,
        min_items=3,
        max_items=7,
        description="Hashtags for categorization"
    )
    
    @field_validator("tags")
    @classmethod
    def validate_tag_format(cls, tags: List[str]) -> List[str]:
        """Ensure tags follow #tag format with no spaces."""
        for tag in tags:
            if not re.match(r'^#[a-zA-Z0-9_]+$', tag):
                raise ValueError(
                    f"Tag '{tag}' must start with # and contain no spaces"
                )
        return tags
    
    def tags_as_string(self) -> str:
        """Format tags for Notion (space-separated)."""
        return " ".join(self.tags)
```

### Generation Prompt Template

```python
METADATA_PROMPT = """Analyze the following content and generate metadata:

Content: {content}
Topic: {topic}
Sub-Type: {sub_type}

Generate:
1. **Description** (50-200 characters): A concise summary of what this content teaches or covers. Be specific and informative.

2. **Tags** (3-7 hashtags): Relevant categorization tags with no spaces. Format each tag as #tagname. Consider:
   - Content type (e.g., #grammar, #vocabulary, #conversation)
   - Language (e.g., #english, #chinese, #japanese)
   - Proficiency level (e.g., #beginner, #intermediate, #advanced)
   - Specific topics (e.g., #verbs, #numbers, #greetings)

Examples:
- Description: "Learn present tense verb conjugation with common daily activities"
- Tags: ["#grammar", "#english", "#beginner", "#verbs", "#presenttense"]
"""
```

### Error Handling

**FR-009**: Graceful metadata generation failures
- If LLM returns invalid format → retry with stricter prompt (up to 3 attempts)
- If all retries fail → use fallback metadata:
  - Description: `"Audio content about {topic} - {sub_type}"`
  - Tags: `["#{topic.lower()}", "#{sub_type.lower()}", "#audio"]`
- Log error but continue processing (audio file is still valid)

---

## 5. Processing Result

**Purpose**: Track processing outcome for each record in batch

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `record_id` | str | Yes | Notion page ID |
| `record_name` | str | Yes | Human-readable name for logging |
| `success` | bool | Yes | Whether processing succeeded |
| `error` | Optional[str] | No | Error message if failed |
| `audio_path` | Optional[Path] | No | Generated audio file path if successful |
| `processing_time` | float | Yes | Time taken in seconds |
| `skipped` | bool | No | True if skipped due to duplicate detection |

### Pydantic Model

```python
from pydantic import BaseModel
from pathlib import Path
from typing import Optional

class ProcessingResult(BaseModel):
    """Result of processing a single Audio Content Record."""
    
    record_id: str
    record_name: str
    success: bool
    error: Optional[str] = None
    audio_path: Optional[Path] = None
    processing_time: float
    skipped: bool = False
    
    def __str__(self) -> str:
        """Human-readable summary."""
        if self.skipped:
            return f"⏭️  SKIPPED: {self.record_name} (unchanged)"
        if self.success:
            return f"✅ SUCCESS: {self.record_name} ({self.processing_time:.1f}s)"
        return f"❌ FAILED: {self.record_name} - {self.error}"
```

### Batch Summary

```python
class BatchProcessingSummary(BaseModel):
    """Summary of entire batch processing run."""
    
    total_records: int
    successful: int
    failed: int
    skipped: int
    total_time: float
    results: List[ProcessingResult]
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate (excluding skipped)."""
        processed = self.total_records - self.skipped
        if processed == 0:
            return 100.0
        return (self.successful / processed) * 100.0
    
    def meets_success_criteria(self) -> bool:
        """Check if meets SC-001: 95% success rate."""
        return self.success_rate >= 95.0
```

---

## 6. Configuration Model

**Purpose**: Encapsulate all environment variables and configuration

### Pydantic Model

```python
from pydantic import BaseModel, Field, field_validator
from pathlib import Path
import os

class AudioProcessorConfig(BaseModel):
    """Configuration for Notion Audio Processor."""
    
    # Notion configuration
    NOTION_API_KEY: str = Field(..., description="Notion API token")
    notion_audio_db_id: str = Field(
        default="302dd30aa93a8087be8dda41b3b4de9b",
        description="Audio Content database ID"
    )
    notion_voice_db_id: str = Field(..., description="Voice configuration database ID")
    
    # Storage configuration
    storage_path: Path = Field(..., description="Root path for audio storage")
    
    # ElevenLabs configuration
    elevenlabs_api_key: str = Field(..., description="ElevenLabs API key")
    default_voice_id: str = Field(..., description="Default voice for fallback")
    tts_model: str = Field(default="eleven_multilingual_v2", description="TTS model")
    audio_format: str = Field(default="mp3_44100_192", description="Audio format")
    
    # LLM configuration
    llm_model: str = Field(default="gpt-4o-mini", description="LLM for metadata")
    llm_api_key: str = Field(..., description="OpenAI/Anthropic API key")
    
    @field_validator("storage_path")
    @classmethod
    def validate_storage_path(cls, path: Path) -> Path:
        """Ensure storage path exists and is writable."""
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        if not path.is_dir():
            raise ValueError(f"Storage path is not a directory: {path}")
        return path
    
    @classmethod
    def from_env(cls) -> "AudioProcessorConfig":
        """Load configuration from environment variables."""
        return cls(
            NOTION_API_KEY=os.getenv("NOTION_API_KEY"),
            notion_audio_db_id=os.getenv(
                "NOTION_AUDIO_DATABASE_ID",
                "302dd30aa93a8087be8dda41b3b4de9b"
            ),
            notion_voice_db_id=os.getenv("NOTION_VOICE_DATABASE_ID"),
            storage_path=Path(os.getenv("HAVACHAT_KNOWLEDGE_PATH")),
            elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY"),
            default_voice_id=os.getenv("DEFAULT_VOICE_ID"),
            tts_model=os.getenv("TTS_MODEL", "eleven_multilingual_v2"),
            audio_format=os.getenv("AUDIO_FORMAT", "mp3_44100_192"),
            llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            llm_api_key=os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"),
        )
```

---

## 7. Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Notion Audio Processor                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. Query Notion Audio Database                                  │
│     Filter: Status = "Ready for Audio"                           │
│     Returns: List[AudioContentRecord]                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. For each record (sequential processing):                     │
│     ┌──────────────────────────────────────────────────┐        │
│     │ 2a. Resolve Voice ID                              │        │
│     │     - Query Voice Database (with caching)         │        │
│     │     - Fallback to default if missing              │        │
│     └──────────────────────────────────────────────────┘        │
│                              │                                   │
│                              ▼                                   │
│     ┌──────────────────────────────────────────────────┐        │
│     │ 2b. Check for duplicate                           │        │
│     │     - Construct file path                         │        │
│     │     - Check content hash                          │        │
│     │     - Skip if unchanged                           │        │
│     └──────────────────────────────────────────────────┘        │
│                              │                                   │
│                              ▼                                   │
│     ┌──────────────────────────────────────────────────┐        │
│     │ 2c. Generate Audio                                │        │
│     │     - Call ElevenLabs TTS API                     │        │
│     │     - Save audio to filesystem                    │        │
│     │     - Save timestamps (Transcript)                │        │
│     │     - Save content hash                           │        │
│     └──────────────────────────────────────────────────┘        │
│                              │                                   │
│                              ▼                                   │
│     ┌──────────────────────────────────────────────────┐        │
│     │ 2d. Generate Metadata                             │        │
│     │     - Call LLM with content/topic/sub-type        │        │
│     │     - Validate format (50-200 chars, 3-7 tags)    │        │
│     │     - Fallback on error                           │        │
│     └──────────────────────────────────────────────────┘        │
│                              │                                   │
│                              ▼                                   │
│     ┌──────────────────────────────────────────────────┐        │
│     │ 2e. Update Notion Record                          │        │
│     │     - Set Description field                       │        │
│     │     - Set Tags field                              │        │
│     │     - Set Status = "Completed"                    │        │
│     └──────────────────────────────────────────────────┘        │
│                              │                                   │
│                              ▼                                   │
│     ┌──────────────────────────────────────────────────┐        │
│     │ 2f. Handle Errors                                 │        │
│     │     - Log error with record ID                    │        │
│     │     - Set Status = "Failed" (optional)            │        │
│     │     - Continue to next record                     │        │
│     └──────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. Generate Batch Summary                                       │
│     - Total/success/failed/skipped counts                        │
│     - Success rate (check SC-001: ≥95%)                          │
│     - Total processing time                                      │
│     - List of failed records for review                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. Success Criteria Mapping

| Success Criterion | Data Model Element | Validation |
|-------------------|-------------------|------------|
| SC-001: 95% success rate | `BatchProcessingSummary.success_rate` | Must be ≥95% |
| SC-002: 30s per 1000 chars | `ProcessingResult.processing_time` | Measure and log |
| SC-003: 100% accurate organization | File path construction with sanitization | Test file existence |
| SC-004: Description 50-200 chars | `ContentMetadata.description` field | Pydantic validation |
| SC-005: Tags 3-7 items, no spaces | `ContentMetadata.tags` field | Pydantic validator |
| SC-006: <5% fatal failures | Error handling per record | Continue on errors |
| SC-007: 100% troubleshootable logs | `ProcessingResult.error` field | Detailed error messages |
| SC-008: 95% voice resolution | `VoiceResolver` with fallback | Default voice on failure |
| SC-009: 100% conflict handling | Duplicate detection with content hash | Skip or overwrite |
| SC-010: 100% env validation | `AudioProcessorConfig.from_env()` | Pydantic validation |

---

## Next Steps

With data model complete, proceed to:
1. Generate contracts (likely minimal for CLI script)
2. Generate quickstart.md
3. Update agent context
4. Re-evaluate Constitution Check
