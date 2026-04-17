# Research: Notion Audio Content Processor

**Date**: 2026-02-12  
**Feature**: `001-notion-audio-processor`  
**Purpose**: Resolve technical unknowns and document best practices for implementation

---

## 1. Python Version Requirement (NEEDS CLARIFICATION)

### Decision
Use **Python 3.13** as specified in current `pyproject.toml`.

### Rationale
- Current project configuration: `requires-python = ">=3.13,<3.14"` in pyproject.toml
- Constitution specifies >=3.14 as aspirational goal, but project is not yet ready
- All existing code and dependencies work with Python 3.13
- No Python 3.14-specific features required for this feature
- Changing Python version project-wide is out of scope for this feature

### Alternatives Considered
- **Upgrade to Python 3.14**: Rejected because it would require testing entire codebase, updating CI/CD, and is beyond this feature's scope
- **Create separate environment**: Rejected because unnecessary complexity for a single feature

### Action
Document in plan.md that this feature uses Python 3.13 per current project standards. Python 3.14 upgrade should be a separate project-wide initiative.

---

## 2. ElevenLabs TTS Integration Best Practices

### Decision
Reuse existing `src/tools/audio/tts_with_elevenlabs.py` module with the `text_to_speech_with_timestamps()` function.

### Rationale
- Existing implementation already handles:
  - Character-level timing from ElevenLabs API
  - Conversion to word-level and sentence-level timestamps
  - Transcript schema compatibility
  - Error handling and retry logic
  - Cost tracking and logging
- Module uses recommended parameters: `mp3_44100_192` format, `eleven_multilingual_v2` model (can be upgraded to `eleven_v3` per spec)
- No need to reimplement TTS logic

### Implementation Details
```python
from tools.audio.tts_with_elevenlabs import text_to_speech_with_timestamps

# Call with spec-required parameters
result = text_to_speech_with_timestamps(
    text=content_text,
    voice_id=resolved_voice_id,
    output_path=audio_file_path,
    language=language_code,  # e.g., "en", "zh", "ja"
    model_id="eleven_multilingual_v2",  # or "eleven_turbo_v2_5" for speed
    output_format="mp3_44100_192"  # As per spec
)
```

### Alternatives Considered
- **Direct ElevenLabs API**: Rejected because existing wrapper provides better error handling and schema integration
- **Different TTS provider**: Rejected because spec explicitly requires ElevenLabs

---

## 3. Notion API Batch Processing Best Practices

### Decision
Use existing `NotionClient` from `src/havachat/utils/notion_client.py` with error handling per record.

### Rationale
- Existing client handles:
  - API v2025-09-03 (latest)
  - Retry logic with exponential backoff (3 attempts)
  - Schema validation
  - Rate limit handling (429 errors)
- Batch processing pattern: query all records, process sequentially, update individually

### Implementation Pattern
```python
from havachat.utils.notion_client import NotionClient

# Initialize client
client = NotionClient(
    api_token=os.getenv("NOTION_API_KEY"),
    database_id=os.getenv("NOTION_AUDIO_DATABASE_ID")
)

# Query records with filter
records = client.query_database(filters={
    "property": "Status",
    "select": {"equals": "Ready for Audio"}
})

# Process each record independently
for record in records:
    try:
        # Process audio generation
        # Update Notion record on success
        client.update_page(record["id"], properties={...})
    except Exception as e:
        # Log error, continue with next record
        logger.error(f"Failed to process {record['id']}: {e}")
        continue
```

### Alternatives Considered
- **Parallel batch processing**: Rejected because Notion API has rate limits; sequential processing is safer
- **Transactional updates**: Notion doesn't support transactions; individual updates with error logging is standard

### Additional Considerations
- **Rate Limiting**: Respect Notion API limits (~3 requests/second). Add small delay between operations if needed
- **Duplicate Detection**: Check existing audio files before generating (avoid re-processing unchanged content)

---

## 4. Voice Database Resolution Pattern

### Decision
Create new `VoiceResolver` module to handle Voice Database lookups and caching.

### Rationale
- Voice resolution is a distinct concern separate from audio generation
- Voices can be cached in memory during batch run (avoid repeated queries)
- Need to handle missing/invalid voice references gracefully

### Implementation Pattern
```python
class VoiceResolver:
    """Resolves voice IDs from Notion Voice Database."""
    
    def __init__(self, notion_client: NotionClient, voice_db_id: str):
        self.notion_client = notion_client
        self.voice_db_id = voice_db_id
        self._cache: Dict[str, str] = {}  # name -> voice_id
        
    def resolve_voice(self, voice_relation_id: Optional[str]) -> str:
        """
        Resolve voice ID from relation or return default.
        
        Returns:
            Voice ID for ElevenLabs (e.g., "abc123xyz")
        """
        if not voice_relation_id:
            return self._get_default_voice()
            
        if voice_relation_id in self._cache:
            return self._cache[voice_relation_id]
            
        # Query Voice Database for voice_id
        voice_page = self.notion_client.get_page(voice_relation_id)
        voice_id = voice_page.properties["Voice Id"]["rich_text"][0]["plain_text"]
        
        self._cache[voice_relation_id] = voice_id
        return voice_id
```

### Alternatives Considered
- **Direct database query per record**: Rejected due to unnecessary API calls
- **Pre-load all voices**: Acceptable alternative if voice database is small (<100 voices)

---

## 5. LLM-Based Metadata Generation

### Decision
Use existing `LLMClient` from `src/havachat/utils/llm_client.py` with structured Pydantic output.

### Rationale
- Existing client provides:
  - Instructor integration for structured responses
  - Retry logic (3 attempts with exponential backoff)
  - Token usage tracking
  - Multiple provider support (OpenAI, Anthropic, Gemini)
  - Langfuse tracing for observability
- Structured output ensures consistent format for Description and Tags

### Implementation Pattern
```python
from havachat.utils.llm_client import LLMClient
from pydantic import BaseModel, Field

class ContentMetadata(BaseModel):
    """Metadata generated for audio content."""
    description: str = Field(..., min_length=50, max_length=200)
    tags: List[str] = Field(..., min_items=3, max_items=7)

llm_client = LLMClient(model="gpt-4o-mini")  # Fast and cost-effective

metadata = llm_client.generate(
    prompt=f"""Analyze this content and generate metadata:

Content: {content_text}
Topic: {topic}
Sub-Type: {sub_type}

Generate:
1. A concise description (50-200 characters)
2. 3-7 relevant hashtags (no spaces, format: #tag)

Be specific and accurate.""",
    response_model=ContentMetadata
)

# metadata.description -> string
# metadata.tags -> ["#grammar", "#english", "#beginner"]
```

### Prompt Engineering Best Practices
- **Specificity**: Include content, topic, and sub-type as context
- **Format constraints**: Explicitly state character limits and hashtag format
- **Examples**: Consider few-shot examples for consistency
- **Language awareness**: If content is non-English, instruct LLM to generate tags in English for consistency

### Alternatives Considered
- **Rule-based metadata**: Rejected because LLM provides better quality and context understanding
- **Different LLM provider**: Existing client supports multiple providers; can be configured via env var

### Cost Considerations
- Use `gpt-4o-mini` or `claude-3-haiku` for cost efficiency (~$0.0001 per request)
- Metadata generation is cheap compared to audio generation cost

---

## 6. Filename Sanitization for Filesystem Storage

### Decision
Implement filename sanitization function to handle invalid characters and length limits.

### Rationale
- ID and Name fields from Notion may contain characters invalid for filenames:
  - Path separators: `/` `\`
  - Reserved characters: `:` `*` `?` `"` `<` `>` `|`
  - Control characters and Unicode edge cases
- Filesystem limits: 255 bytes for filename on most systems
- Need deterministic mapping (same input → same filename)

### Implementation Pattern
```python
import re
import unicodedata

def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize filename to be safe across filesystems.
    
    Args:
        filename: Raw filename from Notion
        max_length: Maximum filename length (bytes)
        
    Returns:
        Sanitized filename safe for all filesystems
    """
    # Normalize Unicode (NFC form)
    filename = unicodedata.normalize("NFC", filename)
    
    # Replace invalid characters with underscore
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename)
    
    # Replace multiple spaces/underscores with single underscore
    filename = re.sub(r'[\s_]+', "_", filename)
    
    # Remove leading/trailing dots and spaces (Windows compatibility)
    filename = filename.strip(". ")
    
    # Truncate to max_length (leave room for extension)
    if len(filename.encode('utf-8')) > max_length - 10:
        # Truncate at character boundary
        while len(filename.encode('utf-8')) > max_length - 10:
            filename = filename[:-1]
    
    # Ensure not empty
    if not filename:
        filename = "untitled"
    
    return filename

# Usage
audio_filename = f"{sanitize_filename(record_id)}-{sanitize_filename(name)}.mp3"
```

### Alternatives Considered
- **URL encoding**: Rejected because creates less readable filenames
- **Hash-based names**: Rejected because not human-readable; loses connection to content
- **No sanitization**: Rejected because will cause filesystem errors

### Edge Cases Handled
- Empty or whitespace-only names → "untitled"
- Unicode normalization → consistent representation
- Length limits → truncation at character boundary
- Reserved names on Windows → add suffix if needed (e.g., "CON" → "CON_")

---

## 7. Error Handling for Batch Processing

### Decision
Implement per-record error handling with detailed logging; continue processing on failures.

### Rationale
- Success criteria SC-006: "less than 5% fatal failures (entire batch stops)"
- Individual record failures should not halt batch
- Need detailed error logging for troubleshooting
- Support partial success (some records processed, some failed)

### Implementation Pattern
```python
from dataclasses import dataclass
from typing import List
from loguru import logger

@dataclass
class ProcessingResult:
    """Result of processing a single record."""
    record_id: str
    success: bool
    error: Optional[str] = None
    audio_path: Optional[str] = None
    processing_time: float = 0.0

def process_batch(records: List[dict]) -> List[ProcessingResult]:
    """
    Process batch of records with error isolation.
    
    Returns:
        List of processing results (success + failures)
    """
    results = []
    
    for record in records:
        start_time = time.time()
        result = ProcessingResult(
            record_id=record["id"],
            success=False
        )
        
        try:
            # Step 1: Resolve voice
            voice_id = resolve_voice(record)
            
            # Step 2: Generate audio
            audio_path = generate_audio(record, voice_id)
            
            # Step 3: Generate metadata
            metadata = generate_metadata(record)
            
            # Step 4: Update Notion
            update_notion_record(record["id"], metadata)
            
            result.success = True
            result.audio_path = audio_path
            
        except Exception as e:
            logger.error({
                "msg": "Failed to process record",
                "record_id": record["id"],
                "error": str(e),
                "error_type": type(e).__name__,
                "record_name": record.get("properties", {}).get("Name", "unknown")
            })
            result.error = str(e)
            
        finally:
            result.processing_time = time.time() - start_time
            results.append(result)
    
    # Summary logging
    success_count = sum(1 for r in results if r.success)
    logger.info({
        "msg": "Batch processing complete",
        "total": len(results),
        "success": success_count,
        "failed": len(results) - success_count,
        "success_rate": f"{success_count / len(results) * 100:.1f}%"
    })
    
    return results
```

### Error Categories
1. **Notion API errors**: Network issues, rate limits, schema errors → retry with backoff
2. **Voice resolution errors**: Missing voice → use default, log warning
3. **Audio generation errors**: ElevenLabs API errors → log error, skip record
4. **File system errors**: Permission denied, disk full → log error, halt batch (fatal)
5. **LLM errors**: Timeout, invalid format → retry, use fallback metadata on failure

### Alternatives Considered
- **Fail-fast approach**: Rejected because contradicts success criteria
- **Queue-based retry**: Could be added later for failed records, but not required for MVP

---

## 8. Directory Structure Organization

### Decision
Create hierarchical directory structure: `<HAVACHAT_KNOWLEDGE_PATH>/<Topic>/<Sub-Type>/`

### Rationale
- Spec requirement: organized by Topic and Sub-Type
- Human-readable structure for manual browsing
- Supports future features (e.g., bulk operations by topic)

### Implementation Pattern
```python
from pathlib import Path

def get_audio_storage_path(
    base_path: str,
    topic: str,
    sub_type: str,
    record_id: str,
    name: str
) -> Path:
    """
    Construct organized audio file path.
    
    Returns:
        Path object: <base>/<topic>/<sub_type>/<id>-<name>.mp3
    """
    # Sanitize directory components
    topic_safe = sanitize_filename(topic)
    sub_type_safe = sanitize_filename(sub_type)
    filename = f"{sanitize_filename(record_id)}-{sanitize_filename(name)}.mp3"
    
    # Construct path
    path = Path(base_path) / topic_safe / sub_type_safe / filename
    
    # Create parent directories if needed
    path.parent.mkdir(parents=True, exist_ok=True)
    
    return path
```

### Edge Cases Handled
- Missing Topic or Sub-Type → use "uncategorized" as fallback
- Empty after sanitization → use "default"
- Path too long (>260 chars on Windows) → truncate sanitized components

### Alternatives Considered
- **Flat structure with prefixes**: Rejected because less human-readable
- **Date-based organization**: Rejected because not in spec requirements
- **Hash-based sharding**: Rejected because unnecessary for expected scale

---

## 9. Duplicate Detection Strategy

### Decision
Check for existing audio file before generation; skip if file exists and content unchanged.

### Rationale
- Success criteria SC-004: "existing audio file is not regenerated unless content has changed"
- Saves API costs and processing time
- Requires tracking content version or checksum

### Implementation Pattern
```python
import hashlib

def should_regenerate_audio(
    audio_path: Path,
    content_text: str
) -> bool:
    """
    Determine if audio needs regeneration.
    
    Args:
        audio_path: Expected audio file path
        content_text: Current content text
        
    Returns:
        True if audio should be generated
    """
    # File doesn't exist → generate
    if not audio_path.exists():
        return True
    
    # Check content hash (stored in sidecar file)
    hash_file = audio_path.with_suffix(".mp3.hash")
    current_hash = hashlib.sha256(content_text.encode()).hexdigest()
    
    if hash_file.exists():
        stored_hash = hash_file.read_text().strip()
        if stored_hash == current_hash:
            logger.info(f"Audio unchanged, skipping: {audio_path.name}")
            return False
    
    # Need regeneration
    return True

def save_content_hash(audio_path: Path, content_text: str):
    """Save content hash for duplicate detection."""
    hash_file = audio_path.with_suffix(".mp3.hash")
    content_hash = hashlib.sha256(content_text.encode()).hexdigest()
    hash_file.write_text(content_hash)
```

### Alternatives Considered
- **Timestamp comparison**: Rejected because doesn't detect content changes
- **Store hash in Notion**: Rejected to avoid polluting database schema
- **No duplicate detection**: Simpler but wastes API costs; rejected

---

## 10. Summary of Technology Choices

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Python Version | 3.13 | Current project standard (pyproject.toml) |
| TTS Provider | ElevenLabs | Spec requirement, existing integration |
| TTS Model | `eleven_multilingual_v2` | Balance of quality and speed |
| Audio Format | mp3_44100_192 | Spec requirement |
| Notion Client | Existing `NotionClient` | Proven, handles v2025 API |
| LLM Provider | OpenAI/Anthropic via `LLMClient` | Existing abstraction, structured output |
| LLM Model | gpt-4o-mini / claude-3-haiku | Cost-effective for metadata |
| Metadata Structure | Pydantic models | Type safety, validation |
| Error Handling | Per-record with logging | Meets SC-006 requirement |
| File Organization | `<Topic>/<Sub-Type>/` | Spec requirement |
| Duplicate Detection | Content hash in sidecar file | Efficient, no DB pollution |

---

## 11. Environment Variables Required

| Variable | Purpose | Default | Required |
|----------|---------|---------|----------|
| `NOTION_AUDIO_DATABASE_ID` | Audio Content database | `302dd30aa93a8087be8dda41b3b4de9b` | Yes |
| `NOTION_VOICE_DATABASE_ID` | Voice configuration database | None | Yes |
| `NOTION_API_KEY` | Notion API authentication | None | Yes |
| `HAVACHAT_KNOWLEDGE_PATH` | Audio storage root directory | None | Yes |
| `ELEVENLABS_API_KEY` | ElevenLabs authentication | None | Yes |
| `LLM_MODEL` | LLM for metadata | `gpt-4o-mini` | No |
| `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` | LLM authentication | None | Yes (one) |
| `DEFAULT_VOICE_ID` | Fallback voice | None | Yes |

---

## Next Steps

With research complete, proceed to Phase 1:
1. Generate `data-model.md` (entity definitions)
2. Generate API contracts (if applicable - likely N/A for CLI script)
3. Generate `quickstart.md` (usage guide)
4. Update agent context

All NEEDS CLARIFICATION items have been resolved.
