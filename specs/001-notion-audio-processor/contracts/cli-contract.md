# CLI Contract: Notion Audio Processor

**Feature**: `001-notion-audio-processor`  
**Date**: 2026-02-12  
**Type**: Command-line interface (batch processing script)

---

## Command Signature

```bash
uv run python -m src.havachat.cli.notion_audio_processor [OPTIONS]
```

or with PYTHONPATH:

```bash
PYTHONPATH=src uv run python -m havachat.cli.notion_audio_processor [OPTIONS]
```

---

## Exit Codes

| Code | Meaning | Description |
|------|---------|-------------|
| `0` | Success | Batch completed with ≥95% success rate (SC-001) |
| `1` | Configuration Error | Missing or invalid environment variables |
| `2` | Notion API Error | Failed to connect to Notion or query database |
| `3` | Fatal Processing Error | Filesystem error (disk full, permission denied) |
| `4` | Success Rate Failed | Batch completed but <95% success rate |

---

## Command-line Options

### Optional Flags

```
--dry-run              Preview records without processing
--limit N              Process only first N records (for testing)
--record-id ID         Process only specific record by Notion page ID
--skip-duplicates      Skip duplicate detection (always regenerate)
--verbose, -v          Enable detailed logging
--quiet, -q            Suppress all output except errors
--help, -h             Show help message
```

### Examples

**Process all ready records:**
```bash
uv run python -m src.havachat.cli.notion_audio_processor
```

**Dry run to preview:**
```bash
uv run python -m src.havachat.cli.notion_audio_processor --dry-run
```

**Process specific record:**
```bash
uv run python -m src.havachat.cli.notion_audio_processor --record-id abc123xyz
```

**Test with limited records:**
```bash
uv run python -m src.havachat.cli.notion_audio_processor --limit 5 --verbose
```

---

## Environment Variables Contract

### Required Variables

| Variable | Type | Validation | Example |
|----------|------|------------|---------|
| `NOTION_API_KEY` | str | Non-empty, starts with `secret_` | `secret_abc123...` |
| `NOTION_VOICE_DATABASE_ID` | str | 32-char hex | `302dd30aa93a8087be8dda41b3b4de9b` |
| `HAVACHAT_KNOWLEDGE_PATH` | path | Exists and writable | `/Users/user/havachat-knowledge` |
| `ELEVENLABS_API_KEY` | str | Non-empty | (from ElevenLabs dashboard) |
| `DEFAULT_VOICE_ID` | str | Valid ElevenLabs voice ID | `21m00Tcm4TlvDq8ikWAM` |
| `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` | str | Non-empty | `sk-...` or `sk-ant-...` |

### Optional Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `NOTION_AUDIO_DATABASE_ID` | str | `302dd30aa93a8087be8dda41b3b4de9b` | Audio Content database |
| `TTS_MODEL` | str | `eleven_multilingual_v2` | ElevenLabs model |
| `AUDIO_FORMAT` | str | `mp3_44100_192` | Output audio format |
| `LLM_MODEL` | str | `gpt-4o-mini` | LLM for metadata |
| `LOG_LEVEL` | str | `INFO` | Logging verbosity |

### Validation on Startup

The script **MUST** validate all required environment variables and exit with code `1` if any are missing or invalid:

```python
def validate_environment() -> None:
    """Validate all required environment variables."""
    required = [
        "NOTION_API_KEY",
        "NOTION_VOICE_DATABASE_ID",
        "HAVACHAT_KNOWLEDGE_PATH",
        "ELEVENLABS_API_KEY",
        "DEFAULT_VOICE_ID",
    ]
    
    missing = [var for var in required if not os.getenv(var)]
    if missing:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)
    
    # Check LLM API key (at least one)
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")):
        print("ERROR: Either OPENAI_API_KEY or ANTHROPIC_API_KEY must be set")
        sys.exit(1)
    
    # Validate storage path
    storage_path = Path(os.getenv("HAVACHAT_KNOWLEDGE_PATH"))
    if not storage_path.exists():
        print(f"ERROR: HAVACHAT_KNOWLEDGE_PATH does not exist: {storage_path}")
        sys.exit(1)
```

**FR-015**: All validation must complete before any processing begins.

---

## Standard Output Contract

### Successful Run

```
[INFO] Notion Audio Processor starting...
[INFO] Configuration loaded: 6 required records found
[INFO] Processing record 1/6: "Present Tense Grammar" (abc123)
[INFO]   ✓ Voice resolved: 21m00Tcm4TlvDq8ikWAM
[INFO]   ✓ Audio generated: 2.3s (Education/Grammar/abc123-present-tense.mp3)
[INFO]   ✓ Metadata generated: "Learn present tense verb conjugation"
[INFO]   ✓ Notion updated
[INFO] Processing record 2/6: "Colors Vocabulary" (def456)
[INFO]   ⏭️  Skipped: content unchanged
...
[INFO] Batch processing complete
[INFO]   Total: 6 records
[INFO]   Success: 5 (83.3%)
[INFO]   Skipped: 1 (16.7%)
[INFO]   Failed: 0 (0.0%)
[INFO]   Total time: 12.4s
```

### Failed Run (with errors)

```
[INFO] Notion Audio Processor starting...
[INFO] Configuration loaded: 3 required records found
[INFO] Processing record 1/3: "Test Content" (ghi789)
[ERROR]  ✗ Failed to process ghi789: ElevenLabsAPIError: Rate limit exceeded
[ERROR]    Record: "Test Content" (ghi789)
[ERROR]    Error: ElevenLabsAPIError: Rate limit exceeded (429)
[INFO] Processing record 2/3: "Another Test" (jkl012)
[INFO]   ✓ Success
...
[WARN] Batch processing complete with failures
[WARN]   Total: 3 records
[WARN]   Success: 2 (66.7%)
[WARN]   Failed: 1 (33.3%)
[WARN]   Success rate below threshold (95%)
[ERROR] Failed records:
[ERROR]   - ghi789: "Test Content" - ElevenLabsAPIError: Rate limit exceeded
```

**Exit code: 4** (success rate below 95%)

---

## Logging Contract

### Log Format

All logs follow structured JSON format for machine readability:

```json
{
  "timestamp": "2026-02-12T10:30:45.123Z",
  "level": "INFO",
  "msg": "Processing record",
  "record_id": "abc123",
  "record_name": "Present Tense Grammar",
  "topic": "Education",
  "sub_type": "Grammar"
}
```

### Log Levels

- **DEBUG**: Detailed function calls, cache hits, API requests
- **INFO**: Processing milestones, success messages
- **WARN**: Fallback behaviors, retries, skipped records
- **ERROR**: Processing failures, API errors

### Log Output Targets

- **Console**: Human-readable format (`--verbose` or `--quiet` flags)
- **File**: `logs/notion_audio_processor_YYYYMMDD_HHMMSS.log` (JSON format)

**FR-010**: All processing activities must be logged with sufficient detail for troubleshooting.

---

## Error Message Format

All error messages **MUST** follow this format for consistency:

```
[ERROR] Failed to process {record_id}: {ErrorType}: {error_message}
[ERROR]   Record: "{record_name}" ({record_id})
[ERROR]   Step: {step_name}
[ERROR]   Error: {error_details}
[ERROR]   Suggestion: {troubleshooting_hint}
```

Example:

```
[ERROR] Failed to process abc123: ElevenLabsAPIError: Invalid voice ID
[ERROR]   Record: "Test Content" (abc123)
[ERROR]   Step: Audio Generation
[ERROR]   Error: Voice ID 'invalid_voice' not found in ElevenLabs account
[ERROR]   Suggestion: Check DEFAULT_VOICE_ID environment variable or Voice Database configuration
```

**FR-009**: Error messages must be actionable and include troubleshooting guidance where possible.

---

## Progress Reporting

For long-running batches (>10 records), the script **SHOULD** display progress:

```
Processing records: [▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░] 50% (5/10) - ETA: 2m 15s
```

Progress includes:
- Visual progress bar
- Percentage complete
- Records processed / total
- Estimated time remaining (based on average processing time)

**Note**: Progress bar is suppressed in `--quiet` mode or when output is not a TTY.

---

## Return Value (Programmatic Usage)

If imported and used programmatically (not via CLI):

```python
from havachat.cli.notion_audio_processor import process_audio_batch

# Returns BatchProcessingSummary
summary = process_audio_batch(
    config=config,
    dry_run=False,
    limit=None,
    record_id=None
)

print(f"Success rate: {summary.success_rate}%")
print(f"Failed records: {len([r for r in summary.results if not r.success])}")
```

**Return Type**: `BatchProcessingSummary` (see data-model.md)

---

## File System Side Effects

### Files Created

For each successfully processed record:

1. **Audio file**: `<HAVACHAT_KNOWLEDGE_PATH>/<Topic>/<Sub-Type>/<ID>-<Name>.mp3`
2. **Hash file**: `<HAVACHAT_KNOWLEDGE_PATH>/<Topic>/<Sub-Type>/<ID>-<Name>.mp3.hash`

### Directories Created

Intermediate directories are created automatically:
- `<HAVACHAT_KNOWLEDGE_PATH>/<Topic>/`
- `<HAVACHAT_KNOWLEDGE_PATH>/<Topic>/<Sub-Type>/`

### Files Modified

None (script is read-only except for new file creation).

### Files Deleted

None (script never deletes files; duplicate detection skips regeneration).

---

## Notion Side Effects

### Records Read

Query filter: `Status == "Ready for Audio"`

Fields read: `ID`, `Name`, `Content`, `Topic`, `Sub-Type`, `Voices` (relation)

### Records Written

For each successfully processed record:

**Updated fields:**
- `Description` ← Generated description (50-200 chars)
- `Tags` ← Generated tags (space-separated, e.g., "#grammar #english")
- `Status` ← `"Completed"`

**On failure (optional):**
- `Status` ← `"Failed"`

### Rate Limiting

Script respects Notion API rate limits (~3 requests/second):
- Sequential processing (no parallel requests)
- Exponential backoff on 429 errors (up to 3 retries)
- Voice Database queries are cached to minimize API calls

---

## Performance Guarantees

| Metric | Target | Measured By |
|--------|--------|-------------|
| Processing time | ≤30s per 1000 chars | `ProcessingResult.processing_time` |
| Success rate | ≥95% | `BatchProcessingSummary.success_rate` |
| Fatal failure rate | <5% | Exit code 3 occurrences |

**SC-002**: Processing time is logged for each record and reported in batch summary.

---

## Testing Contract

### Unit Test Coverage

All public functions must have unit tests:
- `resolve_voice()` → voice resolution with cache and fallback
- `sanitize_filename()` → filename sanitization edge cases
- `generate_metadata()` → LLM metadata generation with fallback
- `should_regenerate_audio()` → duplicate detection logic

### Integration Test

End-to-end test with mock Notion database and ElevenLabs API:
1. Mock Notion query returning 3 test records
2. Mock voice database with 2 voices
3. Mock ElevenLabs TTS returning fake audio + timestamps
4. Mock LLM returning valid metadata
5. Assert: 3 audio files created, 3 Notion records updated, success rate 100%

### CLI Test

Test CLI interface with `--dry-run`:
```bash
uv run python -m src.havachat.cli.notion_audio_processor --dry-run | grep "would process"
```

Expected output:
```
[INFO] DRY RUN: Would process 6 records
[INFO]   - abc123: "Present Tense Grammar" (Education/Grammar)
...
```

---

## Security Considerations

### API Key Handling

- **MUST NOT** log API keys (Notion, ElevenLabs, OpenAI/Anthropic)
- **MUST NOT** include API keys in error messages
- **MUST** validate API key format before use (basic sanity check)

### File System Access

- **MUST** validate storage path is within `HAVACHAT_KNOWLEDGE_PATH` (no `..` escapes)
- **MUST** sanitize filenames to prevent path traversal attacks
- **SHOULD** check available disk space before processing large batches

### Notion Data

- **SHOULD NOT** log full `Content` field (may contain sensitive data)
- **MAY** log truncated content (first 100 chars) with `--verbose` flag
- **MUST** log record ID and name for troubleshooting

---

## Future Extensibility

This contract is designed to support future enhancements:

1. **Parallel processing**: `--workers N` flag for concurrent processing
2. **Resume on failure**: Save checkpoint state, resume with `--resume` flag
3. **Webhook notifications**: `--webhook URL` for completion notifications
4. **Custom prompts**: `--metadata-prompt FILE` for custom LLM prompt templates
5. **Output formats**: `--format opus` to support additional audio formats

Changes to this contract **MUST** maintain backward compatibility or increment a major version.

---

## Summary

This CLI contract defines:
- ✅ Command signature and options
- ✅ Exit codes (0-4)
- ✅ Environment variables (required + optional)
- ✅ Output format (logs, progress, errors)
- ✅ Side effects (filesystem, Notion updates)
- ✅ Performance guarantees
- ✅ Security considerations
- ✅ Testing requirements

All functional requirements (FR-001 through FR-015) and success criteria (SC-001 through SC-010) are satisfied by this contract.
