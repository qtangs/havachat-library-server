# Quickstart: Notion Audio Content Processor

**Feature**: `001-notion-audio-processor`  
**Date**: 2026-02-12  
**Audience**: Developers and content managers using the batch audio generation system

---

## Overview

The Notion Audio Content Processor is a batch processing script that:
1. Reads text content from a Notion Audio Database
2. Converts text to audio using ElevenLabs TTS with timestamps
3. Stores audio files in organized folder structure (`<Topic>/<Sub-Type>/`)
4. Generates descriptions and hashtags using AI
5. Updates Notion records with generated metadata

**Use Case**: Convert written language learning content to audio files automatically.

---

## Prerequisites

### Required Software
- Python 3.13 (via `uv` package manager)
- `uv` package manager ([installation guide](https://github.com/astral-sh/uv))

### Required Accounts & API Keys
1. **Notion Integration** ([setup guide](https://developers.notion.com/docs/create-a-notion-integration))
   - Create integration at https://www.notion.so/my-integrations
   - Grant access to Audio Database and Voice Database
   - Copy API token (starts with `secret_`)

2. **ElevenLabs Account** ([signup](https://elevenlabs.io))
   - Free tier available (10,000 characters/month)
   - Copy API key from [profile settings](https://elevenlabs.io/speech-synthesis)
   - Note default voice ID (or create custom voice)

3. **LLM Provider** (choose one)
   - OpenAI API key ([get key](https://platform.openai.com/api-keys))
   - OR Anthropic API key ([get key](https://console.anthropic.com/))

### Notion Database Setup

#### 1. Create Audio Content Database

Required columns:
| Column | Type | Options |
|--------|------|---------|
| Name | Title | - |
| Content | Text | Long text field |
| Topic | Select | Add options: Education, Conversation, etc. |
| Sub-Type | Select | Add options: Grammar, Vocabulary, etc. |
| Status | Select | Options: Not started, Ready for Audio, Processing, Completed, Failed |
| Voices | Relation | Relates to Voice Database |
| Description | Text | (auto-filled by script) |
| Tags | Text | (auto-filled by script) |
| ID | Text | Unique identifier |

**Get database ID**:
- Open database in Notion
- Copy URL: `https://notion.so/workspace/DATABASE_ID?v=...`
- Extract 32-character hex string (DATABASE_ID)

#### 2. Create Voice Database

Required columns:
| Column | Type | Description |
|--------|------|-------------|
| Name | Title | Human-readable voice name |
| Voice Id | Text | ElevenLabs voice ID |

**Example voices**:
| Name | Voice Id |
|------|----------|
| Rachel (US English) | 21m00Tcm4TlvDq8ikWAM |
| Adam (US English) | pNInz6obpgDQGcFmaJgB |
| Matilda (UK English) | XrExE9yKIg1WjnnlVkGX |

Find voice IDs at [ElevenLabs Voice Library](https://elevenlabs.io/voice-library).

---

## Installation

### 1. Clone Repository

```bash
cd /path/to/havachat-library-server
```

### 2. Install Dependencies

```bash
uv sync
```

This installs all dependencies from `pyproject.toml`.

### 3. Set Up Environment Variables

Create `.env` file in project root:

```bash
# Notion Configuration
NOTION_API_KEY=secret_abc123xyz...
NOTION_AUDIO_DATABASE_ID=302dd30aa93a8087be8dda41b3b4de9b
NOTION_VOICE_DATABASE_ID=your_voice_database_id_here

# Storage Path
HAVACHAT_KNOWLEDGE_PATH=/Users/yourname/havachat-knowledge

# ElevenLabs Configuration
ELEVENLABS_API_KEY=your_elevenlabs_api_key
DEFAULT_VOICE_ID=21m00Tcm4TlvDq8ikWAM

# LLM Configuration (choose one)
OPENAI_API_KEY=sk-...
# OR
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=gpt-4o-mini  # Optional, defaults to gpt-4o-mini

# Optional: Override defaults
TTS_MODEL=eleven_multilingual_v2
AUDIO_FORMAT=mp3_44100_192
LOG_LEVEL=INFO
```

**Security**: Add `.env` to `.gitignore` (should already be ignored).

### 4. Create Storage Directory

```bash
mkdir -p "$HAVACHAT_KNOWLEDGE_PATH"
```

Verify writable:
```bash
touch "$HAVACHAT_KNOWLEDGE_PATH/test.txt" && rm "$HAVACHAT_KNOWLEDGE_PATH/test.txt"
```

---

## Usage

### Basic Usage

```bash
PYTHONPATH=src uv run python -m havachat.cli.notion_audio_processor
```

Or with full path:

```bash
uv run python -m src.havachat.cli.notion_audio_processor
```

### Common Options

**Dry run (preview without processing):**
```bash
uv run python -m src.havachat.cli.notion_audio_processor --dry-run
```

**Verbose logging:**
```bash
uv run python -m src.havachat.cli.notion_audio_processor --verbose
```

**Process limited records (testing):**
```bash
uv run python -m src.havachat.cli.notion_audio_processor --limit 5
```

**Process specific record:**
```bash
uv run python -m src.havachat.cli.notion_audio_processor --record-id abc123xyz
```

**Quiet mode (errors only):**
```bash
uv run python -m src.havachat.cli.notion_audio_processor --quiet
```

---

## Step-by-Step Walkthrough

### Step 1: Prepare Content in Notion

1. Open your Audio Content Database in Notion
2. Create a new row (or select existing content)
3. Fill in fields:
   - **Name**: "Present Tense Grammar"
   - **Content**: "The present tense is used to describe current actions. For example: I eat breakfast every day."
   - **Topic**: Select "Education"
   - **Sub-Type**: Select "Grammar"
   - **Status**: Select "Ready for Audio"
   - **Voices**: (Optional) Link to voice from Voice Database
   - **ID**: "edu-grammar-001"

4. Save the record

### Step 2: Run Processor (Dry Run First)

Test without making changes:

```bash
uv run python -m src.havachat.cli.notion_audio_processor --dry-run --verbose
```

Expected output:
```
[INFO] Notion Audio Processor starting (DRY RUN)...
[INFO] Configuration validated
[INFO] Found 1 record with Status = "Ready for Audio"
[INFO] Would process:
[INFO]   - edu-grammar-001: "Present Tense Grammar" (Education/Grammar)
[INFO]     Voice: Rachel (US English) - 21m00Tcm4TlvDq8ikWAM
[INFO]     Output: /Users/you/havachat-knowledge/Education/Grammar/edu-grammar-001-Present_Tense_Grammar.mp3
[INFO]     Content length: 95 characters (~3s audio)
[INFO] DRY RUN complete: 1 record would be processed
```

### Step 3: Run Processor (Real)

Process the content:

```bash
uv run python -m src.havachat.cli.notion_audio_processor --verbose
```

Expected output:
```
[INFO] Notion Audio Processor starting...
[INFO] Configuration validated
[INFO] Processing record 1/1: "Present Tense Grammar" (edu-grammar-001)
[INFO]   ✓ Voice resolved: 21m00Tcm4TlvDq8ikWAM (Rachel)
[INFO]   ✓ Audio generated: 3.2s (Education/Grammar/edu-grammar-001-Present_Tense_Grammar.mp3)
[INFO]   ✓ Metadata generated:
[INFO]     Description: "Learn how to use present tense to describe current actions with examples"
[INFO]     Tags: #grammar #english #beginner #presenttense #verbs
[INFO]   ✓ Notion record updated
[INFO] Batch processing complete
[INFO]   Total: 1 record
[INFO]   Success: 1 (100.0%)
[INFO]   Failed: 0 (0.0%)
[INFO]   Total time: 8.5s
```

### Step 4: Verify Results

**Check filesystem:**
```bash
ls -lh "$HAVACHAT_KNOWLEDGE_PATH/Education/Grammar/"
```

Expected files:
- `edu-grammar-001-Present_Tense_Grammar.mp3` (audio file, ~50KB for 95 chars)
- `edu-grammar-001-Present_Tense_Grammar.mp3.hash` (content hash for duplicate detection)

**Check Notion:**
1. Reload the record in Notion
2. Verify:
   - **Status**: Changed to "Completed"
   - **Description**: Filled with AI-generated summary
   - **Tags**: Filled with hashtags (e.g., "#grammar #english #beginner #presenttense #verbs")

**Listen to audio:**
```bash
open "$HAVACHAT_KNOWLEDGE_PATH/Education/Grammar/edu-grammar-001-Present_Tense_Grammar.mp3"
```

Audio should:
- Be clear and natural-sounding
- Match the content text exactly
- Have appropriate voice (if custom voice selected)

---

## Batch Processing Multiple Records

### Scenario: Process 50 Grammar Lessons

1. In Notion, create 50 records with:
   - Content filled in
   - Topic = "Education"
   - Sub-Type = "Grammar"
   - Status = "Ready for Audio"

2. Run processor:
```bash
uv run python -m src.havachat.cli.notion_audio_processor
```

3. Monitor progress:
```
Processing records: [▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░] 50% (25/50) - ETA: 5m 30s
```

4. Review summary:
```
[INFO] Batch processing complete
[INFO]   Total: 50 records
[INFO]   Success: 48 (96.0%)
[INFO]   Skipped: 0 (0.0%)
[INFO]   Failed: 2 (4.0%)
[INFO]   Total time: 10m 15s
```

5. Check failed records in logs:
```
[ERROR] Failed records:
[ERROR]   - edu-grammar-025: "Complex Conditionals" - ElevenLabsAPIError: Rate limit exceeded
[ERROR]   - edu-grammar-047: "Advanced Particles" - LLMError: Timeout after 30s
```

6. Re-run for failed records:
   - Set failed records back to "Ready for Audio" in Notion
   - Run again (will only process those 2 records)

---

## Troubleshooting

### Issue: "Missing required environment variables"

**Symptom:**
```
ERROR: Missing required environment variables: NOTION_API_KEY, ELEVENLABS_API_KEY
```

**Solution:**
1. Verify `.env` file exists in project root
2. Check variable names match exactly (case-sensitive)
3. Ensure no extra spaces around `=` signs
4. Verify API keys are copied correctly (no truncation)

### Issue: "Notion database not found"

**Symptom:**
```
ERROR: Failed to query Notion database: 404 Not Found
```

**Solution:**
1. Verify database ID is correct (32-char hex)
2. Ensure Notion integration has access to database:
   - Open database in Notion
   - Click "..." → "Connect to" → Select your integration
3. Check API token has not expired

### Issue: "ElevenLabs rate limit exceeded"

**Symptom:**
```
ERROR: ElevenLabsAPIError: Rate limit exceeded (429)
```

**Solution:**
1. **Free tier**: 10,000 chars/month, ~100 requests/hour
   - Wait 1 hour and retry
   - Upgrade to paid plan for higher limits
2. **Paid tier**: Contact ElevenLabs support to increase limits
3. **Workaround**: Process in smaller batches with `--limit 10` flag

### Issue: "Audio file not created"

**Symptom:**
```
ERROR: FileNotFoundError: Permission denied: /path/to/storage
```

**Solution:**
1. Check storage path exists: `mkdir -p "$HAVACHAT_KNOWLEDGE_PATH"`
2. Verify write permissions: `touch "$HAVACHAT_KNOWLEDGE_PATH/test.txt"`
3. Check disk space: `df -h "$HAVACHAT_KNOWLEDGE_PATH"`
4. Ensure path doesn't have special characters or spaces (use absolute path)

### Issue: "LLM metadata generation failed"

**Symptom:**
```
WARN: Metadata generation failed, using fallback
```

**Solution:**
1. Check LLM API key is valid and has credits
2. Verify network connectivity to OpenAI/Anthropic
3. Check if content is too long (>50k chars) → truncate content
4. **Note**: Audio is still generated; metadata just uses fallback

### Issue: "Voice ID not found"

**Symptom:**
```
WARN: Voice ID 'invalid_voice' not found, using default
```

**Solution:**
1. Verify voice ID in Voice Database is correct
2. Check voice exists in your ElevenLabs account
3. Ensure `DEFAULT_VOICE_ID` env var is set to valid voice
4. **Note**: Processing continues with default voice

---

## Advanced Usage

### Custom Voice Selection

1. Add voices to Voice Database in Notion:
   | Name | Voice Id |
   |------|----------|
   | Female Teacher | 21m00Tcm4TlvDq8ikWAM |
   | Male Teacher | pNInz6obpgDQGcFmaJgB |
   | Child Voice | XrExE9yKIg1WjnnlVkGX |

2. In Audio Content records, link Voices column to desired voice

3. Run processor normally (voice will be resolved automatically)

### Skipping Duplicates

By default, the processor skips audio generation if:
- File already exists
- Content hash matches (content unchanged)

**To force regeneration**:
```bash
uv run python -m src.havachat.cli.notion_audio_processor --skip-duplicates
```

This always regenerates audio, even if content unchanged.

### Processing Subsets

**Filter by topic** (manual approach):
1. Change Notion filter to show only desired records
2. Set only those records to "Ready for Audio"
3. Run processor

**Process specific record**:
```bash
uv run python -m src.havachat.cli.notion_audio_processor --record-id YOUR_NOTION_PAGE_ID
```

### Scheduling Batch Runs

**Using cron (Linux/macOS):**
```bash
# Edit crontab
crontab -e

# Add line (runs daily at 2 AM)
0 2 * * * cd /path/to/havachat-library-server && PYTHONPATH=src uv run python -m havachat.cli.notion_audio_processor >> logs/cron.log 2>&1
```

**Using launchd (macOS):**
Create `~/Library/LaunchAgents/com.havachat.audio-processor.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.havachat.audio-processor</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/uv</string>
        <string>run</string>
        <string>python</string>
        <string>-m</string>
        <string>src.havachat.cli.notion_audio_processor</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/havachat-library-server</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>src</string>
    </dict>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/path/to/logs/audio-processor.log</string>
    <key>StandardErrorPath</key>
    <string>/path/to/logs/audio-processor.error.log</string>
</dict>
</plist>
```

Load with:
```bash
launchctl load ~/Library/LaunchAgents/com.havachat.audio-processor.plist
```

---

## Performance Optimization

### Cost Optimization

**ElevenLabs costs** (approximate):
- Free tier: 10,000 characters/month (enough for ~20 short lessons)
- Starter ($5/month): 30,000 characters
- Creator ($22/month): 100,000 characters
- Pro ($99/month): 500,000 characters

**Typical content sizes:**
- Short lesson (100 words): ~500 characters → $0.003
- Medium lesson (500 words): ~2,500 characters → $0.015
- Long lesson (1000 words): ~5,000 characters → $0.030

**LLM costs** (metadata generation):
- OpenAI gpt-4o-mini: ~$0.0001 per request (negligible)
- Anthropic claude-3-haiku: ~$0.0001 per request (negligible)

**Total cost example**: 100 medium lessons = $1.50 (ElevenLabs) + $0.01 (LLM) = **$1.51**

### Speed Optimization

**Current performance**: ~30 seconds per 1000 characters

**Bottlenecks**:
1. ElevenLabs API latency: ~2-5 seconds per request
2. LLM metadata generation: ~1-2 seconds per request
3. Notion API updates: ~0.5-1 second per record

**Future optimization** (Phase 2):
- Parallel processing with `--workers 4` flag (4x faster)
- Batch API requests where possible
- Local caching of voice configurations

---

## Next Steps

### After First Successful Run

1. ✅ Verify audio quality meets requirements
2. ✅ Check metadata (descriptions and tags) are relevant
3. ✅ Confirm file organization makes sense for your use case
4. ✅ Test duplicate detection (re-run without changing content)

### Scaling to Production

1. **Organize content** in Notion:
   - Use consistent Topic/Sub-Type values
   - Add ID field to all records (for stable filenames)
   - Create standard voice assignments

2. **Set up monitoring**:
   - Schedule regular batch runs (daily or weekly)
   - Monitor success rates (should be ≥95%)
   - Alert on failures (integrate with Slack/email)

3. **Backup strategy**:
   - Back up `HAVACHAT_KNOWLEDGE_PATH` directory regularly
   - Consider versioning audio files if content changes
   - Keep Notion as source of truth for content

4. **Quality assurance**:
   - Randomly sample generated audio for quality checks
   - Review AI-generated metadata for accuracy
   - Adjust prompts if metadata quality is poor

### Customization

See [research.md](./research.md) for:
- Custom LLM prompt templates for metadata
- Alternative audio formats (opus, wav)
- Custom voice configurations
- Error handling strategies

---

## Support

**Documentation:**
- [Feature Spec](./spec.md) - Full requirements
- [Data Model](./data-model.md) - Entity definitions
- [CLI Contract](./contracts/cli-contract.md) - Technical interface
- [Research](./research.md) - Design decisions

**Common Issues:**
- Check logs in `logs/` directory
- Review error messages (include record ID and error type)
- Verify environment variables are set correctly
- Ensure API keys are valid and have sufficient credits

**Getting Help:**
- Open an issue in the repository
- Check existing issues for similar problems
- Include logs and error messages when reporting bugs

---

## Summary

You've now:
- ✅ Installed dependencies
- ✅ Configured environment variables
- ✅ Set up Notion databases
- ✅ Processed your first content record
- ✅ Verified audio and metadata generation
- ✅ Learned troubleshooting strategies

**Next**: Start processing your language learning content at scale! 🚀
