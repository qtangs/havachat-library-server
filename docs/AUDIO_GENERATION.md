# Audio Generation System - Phase 7

## Overview

The audio generation system creates TTS audio files for learning items and content units using ElevenLabs API, with local-first storage and optional Cloudflare R2 sync.

## Prerequisites

1. **ElevenLabs API Key**: Set `ELEVENLABS_API_KEY` environment variable
2. **Cloudflare R2 Credentials** (for sync only):
   - `R2_ACCOUNT_ID`
   - `R2_ACCESS_KEY_ID`
   - `R2_SECRET_ACCESS_KEY`
   - `R2_BUCKET_NAME`

3. **Dependencies**: Install with `uv sync`
   - `elevenlabs>=1.0.0`
   - `boto3>=1.35.0` (for R2 sync)

## Voice Configuration

Voice mappings are defined in language-specific files at the repository root: `voice_config_{lang}.json` (e.g., `voice_config_zh.json`, `voice_config_ja.json`, `voice_config_fr.json`)

### Voice Config Structure

```json
{
  "voices": [
    {
      "voice_id": "elevenlabs/ThT5KcBeYPX3keUQqHPh",
      "name": "Dorothy",
      "type": "single",
      "gender": "female",
      "description": "Female voice, pleasant and friendly",
      "supported_languages": ["zh", "ja", "fr", "en"],
      "comment": "General purpose female voice for learning items"
    },
    {
      "voice_id": "elevenlabs/XrExE9yKIg1WjnnlVkGX",
      "name": "Matilda",
      "type": "conversation",
      "gender": "female",
      "description": "Female voice, warm and approachable",
      "supported_languages": ["zh", "ja", "fr", "en"],
      "comment": "Conversation voice, female"
    },
    {
      "voice_id": "elevenlabs/flq6f7yk4E4fJM5XTYuZ",
      "name": "Michael",
      "type": "conversation",
      "gender": "male",
      "description": "Male voice, clear and articulate",
      "supported_languages": ["zh", "ja", "fr", "en"],
      "comment": "Conversation voice, male"
    }
  ]
}
```

**Voice Types**:
- `single`: General purpose voice for learning items
- `conversation`: Voice for conversations (system automatically matches to speaker genders)

**Gender Field**: `male` or `female` - Used for automatic voice assignment based on conversation speaker genders

**Voice ID Format**: `provider/id` (e.g., `elevenlabs/abc123`) to support multiple TTS providers in the future

## Workflow

### 1. Generate Audio

Generate audio for learning items or content units using language names or ISO codes:

```bash
# Generate audio for vocabulary items (using language name)
uv run python -m src.pipeline.cli.generate_audio \
  --language Mandarin \
  --level HSK1 \
  --item-type learning_item \
  --category vocab \
  --versions 2 \
  --format opus

# Generate audio using language code
uv run python -m src.pipeline.cli.generate_audio \
  --language zh \
  --level HSK1 \
  --item-type learning_item \
  --category vocab \
  --versions 2 \
  --format opus

# Generate audio for conversations (automatic voice assignment by gender)
uv run python -m src.pipeline.cli.generate_audio \
  --language zh \
  --level HSK1 \
  --item-type content_unit \
  --content-type conversation \
  --versions 1 \
  --format opus
```

**Options**:
- `--language`: Language name or ISO 639-1 code (Mandarin/zh, French/fr, Japanese/ja)
- `--level`: Proficiency level (HSK1, A1, N5)
- `--item-type`: `learning_item` or `content_unit`
- `--category`: Filter by category (vocab, grammar, idiom, etc.)
- `--content-type`: Filter content units (conversation, story)
- `--voice-id`: Specific voice ID for learning items (e.g., `elevenlabs/abc123`)
- `--versions`: Number of versions to generate (1-3)
- `--format`: Audio format (opus or mp3)
- `--batch-size`: Limit number of items to process
- `--resume`: Resume from checkpoint
- `--config-dir`: Directory containing voice_config_{lang}.json files (defaults to repo root)

**Output**:
- Audio files: `{Language}/{Level}/02_Generated/audio/{category}/{uuid}_v{N}.{format}`
- Metadata: `{Language}/{Level}/02_Generated/audio/learning_items_media.json` or `content_units_media.json`
- Progress: `{Language}/{Level}/02_Generated/audio/audio_generation_progress.json`

### 2. Select Best Version (Optional)

If you generated multiple versions, manually select the best one:

```bash
# For learning items
uv run python -m src.pipeline.cli.select_audio \
  --language zh \
  --level HSK1 \
  --item-type learning_item \
  --item-id 550e8400-e29b-41d4-a716-446655440000 \
  --version 2

# For content unit segments
uv run python -m src.pipeline.cli.select_audio \
  --language zh \
  --level HSK1 \
  --item-type content_unit \
  --item-id 650e8400-e29b-41d4-a716-446655440000 \
  --segment-index 0 \
  --version 2
```

### 3. Sync to Cloudflare R2

Upload audio files to R2 storage and update metadata with public URLs:

```bash
# Dry run (preview without uploading)
uv run python -m src.pipeline.cli.sync_audio \
  --language zh \
  --level HSK1 \
  --item-type all \
  --selected-only \
  --dry-run

# Actual sync (selected versions only)
uv run python -m src.pipeline.cli.sync_audio \
  --language zh \
  --level HSK1 \
  --item-type all \
  --selected-only

# Sync and cleanup local files
uv run python -m src.pipeline.cli.sync_audio \
  --language zh \
  --level HSK1 \
  --item-type all \
  --selected-only \
  --cleanup-local
```

**Options**:
- `--item-type`: `learning_item`, `content_unit`, or `all`
- `--category`: Filter by category
- `--selected-only`: Only sync selected versions
- `--dry-run`: Preview without uploading
- `--cleanup-local`: Delete local files after successful upload

**R2 Path Structure**: `{lang_code}/{category}/{uuid}_v{N}.{format}`
- Example: `zh/vocab/550e8400-e29b-41d4-a716-446655440000_v1.opus`

**Public URLs**: `https://pub-{ACCOUNT_ID}.r2.dev/{r2_path}`

## File Structure

```
havachat-knowledge/generated content/
└── Mandarin/
    └── HSK1/
        └── 02_Generated/
            ├── vocab_enriched.json
            ├── grammar_enriched.json
            ├── conversation/
            │   ├── conversation_0e668d26.json
            │   └── ...
            └── audio/
                ├── vocab/
                │   ├── 550e8400_v1.opus
                │   ├── 550e8400_v2.opus
                │   └── ...
                ├── conversation/
                │   ├── 650e8400_seg0_v1.opus
                │   └── ...
                ├── learning_items_media.json
                ├── content_units_media.json
                └── audio_generation_progress.json
```

## Metadata Structure

### learning_items_media.json

```json
[
  {
    "learning_item_id": "550e8400-e29b-41d4-a716-446655440000",
    "target_item": "银行",
    "category": "vocab",
    "versions": [
      {
        "version": 1,
        "audio_local_path": "audio/vocab/550e8400_v1.opus",
        "audio_url": "https://pub-xxx.r2.dev/zh/vocab/550e8400_v1.opus",
        "format": "opus",
        "sample_rate": 48000,
        "bitrate": 32,
        "file_size_bytes": 12345,
        "duration_ms": 1500,
        "voice_id": "pNInz6obpgDQGcFmaJgB",
        "character_count": 2,
        "selected": true,
        "generated_at": "2026-01-30T12:00:00Z"
      }
    ]
  }
]
```

### content_units_media.json

```json
[
  {
    "content_unit_id": "650e8400-e29b-41d4-a716-446655440000",
    "title": "Shopping at the Supermarket",
    "type": "conversation",
    "segments": [
      {
        "segment_index": 0,
        "speaker_id": "A",
        "text": "你好，我要买包子。",
        "versions": [
          {
            "version": 1,
            "audio_local_path": "audio/conversation/650e8400_seg0_v1.opus",
            "audio_url": "https://pub-xxx.r2.dev/zh/conversation/650e8400_seg0_v1.opus",
            "format": "opus",
            "sample_rate": 48000,
            "bitrate": 32,
            "voice_id": "XrExE9yKIg1WjnnlVkGX",
            "selected": true,
            "generated_at": "2026-01-30T12:00:00Z"
          }
        ]
      }
    ]
  }
]
```

## Cost Tracking

The system tracks ElevenLabs API usage:

```
COST TRACKING
================================================================================
Total characters: 15,420
Estimated cost: $4.63
ElevenLabs requests: 285
Failed requests: 3
```

**Pricing**: Approximately $0.30 per 1000 characters (ElevenLabs standard pricing)

## Checkpoint & Resume

Audio generation supports checkpoint-based resumption:

1. Progress is saved every 10 items (configurable with `--checkpoint-interval`)
2. If generation is interrupted, use `--resume` to continue:

```bash
uv run python -m src.pipeline.cli.generate_audio \
  --language Mandarin \
  --level HSK1 \
  --item-type learning_item \
  --resume
```

3. Checkpoint files are automatically cleaned up after successful completion

## Error Handling

- **Retry Logic**: 3 attempts with exponential backoff for both ElevenLabs API and R2 uploads
- **Failed Items**: Logged to progress file with error messages
- **Validation**: Voice configurations validated before batch starts (fail fast)

## Audio Formats

### Opus (Default)
- **Format**: Opus codec
- **Sample Rate**: 48kHz
- **Bitrate**: 32kbps
- **Extension**: `.opus`
- **Use Case**: Production (best quality/size ratio)

### MP3 (Comparison)
- **Format**: MP3
- **Sample Rate**: 44.1kHz
- **Bitrate**: 64kbps
- **Extension**: `.mp3`
- **Use Case**: Comparison or compatibility testing

## Troubleshooting

### "Voice ID not found"
- Check `voice_config.json` has the voice ID
- Verify voice supports the target language

### "No checkpoint found"
- First run doesn't have a checkpoint - this is normal
- Only appears if you use `--resume` flag

### "R2 upload failed"
- Verify R2 credentials are set correctly
- Check bucket exists and has proper permissions
- Use `--dry-run` first to test configuration

### "Audio file not found"
- Ensure audio generation completed successfully
- Check `learning_items_media.json` or `content_units_media.json` for file paths

## Advanced Usage

### Generate Multiple Languages

```bash
# Process all languages
for lang in zh ja fr; do
  for level in HSK1 N5 A1; do
    uv run python -m src.pipeline.cli.generate_audio \
      --language $lang \
      --level $level \
      --item-type learning_item \
      --versions 1
  done
done
```

### Batch Processing with Limits

```bash
# Process 100 items at a time
uv run python -m src.pipeline.cli.generate_audio \
  --language zh \
  --level HSK1 \
  --item-type learning_item \
  --batch-size 100
```

### Version Comparison Workflow

```bash
# 1. Generate 3 versions
uv run python -m src.pipeline.cli.generate_audio \
  --language zh \
  --level HSK1 \
  --item-type learning_item \
  --category vocab \
  --versions 3

# 2. Manually review audio files and select best version
# 3. Use select_audio.py to mark selection
# 4. Sync only selected versions
uv run python -m src.pipeline.cli.sync_audio \
  --language zh \
  --level HSK1 \
  --item-type learning_item \
  --selected-only
```

## Conversation Voice Assignment

The system automatically assigns voices to conversation speakers based on gender:

1. **Conversation file** specifies speaker genders in the `speakers` array (see example below)
2. **Voice validator** randomly selects conversation voices matching each speaker's gender from `voice_config_{lang}.json`
3. **Audio generator** creates audio for each segment using the appropriate voice

### Example Conversation File

```json
{
  "id": "0e668d26-14f6-41a7-844e-fea0031514d9",
  "type": "conversation",
  "title": "Shopping at the Supermarket",
  "segments": [
    {
      "speaker": "A",
      "text": "你好，我要买包子。"
    },
    {
      "speaker": "B",
      "text": "你好，包子在那边。"
    }
  ],
  "speakers": [
    {
      "id": "A",
      "name": "Xiao Li",
      "gender": "female"
    },
    {
      "id": "B",
      "name": "Shop Assistant",
      "gender": "male"
    }
  ]
}
```

The system will:
- Assign a random female conversation voice to speaker A
- Assign a random male conversation voice to speaker B
- Use these voices consistently throughout the conversation

## Next Steps

After syncing to R2:
1. Update frontend to use `audio_url` from metadata
2. Implement audio playback in learning app
3. Monitor ElevenLabs usage and costs
4. Consider implementing audio caching strategy
