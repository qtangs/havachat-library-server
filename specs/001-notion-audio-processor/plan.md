# Implementation Plan: Notion Audio Content Processor

**Branch**: `001-notion-audio-processor` | **Date**: 2026-02-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-notion-audio-processor/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Create a batch processing script that reads content records from a Notion Audio Database (distinct from the existing Chinese Content database), converts text to audio using ElevenLabs TTS with detailed timestamps, stores audio files in an organized folder structure by topic/sub-type, and uses an LLM to automatically generate descriptions and hashtags that are written back to Notion.

## Technical Context

**Language/Version**: Python 3.13 (per pyproject.toml: requires-python = ">=3.13,<3.14")  
**Primary Dependencies**: elevenlabs>=1.0.0, requests>=2.31.0, python-dotenv>=1.2.1, pydantic (via existing models), instructor>=1.0.0, openai>=1.0.0 or anthropic>=0.40.0 (via havachat.utils.llm_client)  
**Storage**: Filesystem (audio files at `<HAVACHAT_KNOWLEDGE_PATH>/<Topic>/<Sub-Type>/<ID>-<Name>.mp3`, Notion as metadata database)  
**Testing**: pytest>=8.0.0 (already configured in pyproject.toml)  
**Target Platform**: macOS/Linux (local batch processing script, can be scheduled via cron)
**Project Type**: Single project (batch processing CLI script, separate from existing API server)  
**Performance Goals**: Process content within 30 seconds per 1000 characters of text (per success criteria SC-002)  
**Constraints**: 95% success rate (SC-001), graceful error handling without batch termination (SC-006), 100% accurate folder organization (SC-003)  
**Scale/Scope**: Batch processing multiple Notion records per run (tens to hundreds), organized hierarchical file storage

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Code Quality & Maintainability
- [x] Batch generation logic separated from online serving (no mixed concerns) — **PASS**: This is pure batch processing script, no API exposure
- [⚠️] Using `uv` package manager, Python >=3.14 — **NEEDS CLARIFICATION**: pyproject.toml specifies Python 3.13, not 3.14; constitution requires >=3.14
- [x] Type hints on all public functions/methods — **PLANNED**: Will add type hints to all new code
- [x] Modular, reusable components with clear documentation — **PLANNED**: Will structure as reusable modules in src/havachat/cli/ and src/havachat/integrations/

### II. Testing Standards & Quality Gates
- [x] QA gates identified (schema validation, duplication checks, link correctness, question answerability, audio-text alignment) — **ADAPTED**: Relevant gates are: file existence validation, audio format validation (mp3_44100_192), metadata format validation (hashtags with no spaces), timestamp presence in audio output
- [x] Test categories planned: unit (pipeline stages), contract (API), integration (end-to-end), quality gates — **ADAPTED**: Unit tests (Notion query, voice resolution, audio generation, metadata generation, file storage), integration tests (full pipeline from Notion read → audio generation → Notion update)
- [N/A] Automated quality gate tests prevent bad content promotion — **N/A**: This script processes external content, not generating learning content for promotion

### III. User Experience Consistency
- [N/A] API schema consistency verified (JSON structure, error codes) — **N/A**: Not an API endpoint
- [N/A] Language + proficiency filtering strictly enforced — **N/A**: Not a learner-facing search feature
- [N/A] Session packs deliver complete learning units (content + questions + quiz + audio) — **N/A**: Not a session pack feature
- [x] Audio-text alignment validation planned — **PASS**: ElevenLabs TTS returns character-level timestamps that are converted to word/sentence levels (existing implementation in src/tools/audio/tts_with_elevenlabs.py)

### IV. Performance Requirements
- [N/A] Online API: <200ms p95 target documented — **N/A**: Batch processing script, not online API
- [x] Batch: Quality over speed (iterative LLM loops acceptable) — **PASS**: Success criteria allows 30 seconds per 1000 characters
- [N/A] Search index: <5min update window, denormalized for speed — **N/A**: No search index involved
- [N/A] Memory: API <500MB, batch workers horizontally scalable — **ADAPTED**: Script should handle records sequentially to avoid memory issues; error handling prevents batch termination

**Justification Required**: 

| Issue | Justification |
|-------|---------------|
| Python 3.13 vs 3.14 requirement | Constitution specifies >=3.14, but current pyproject.toml uses 3.13. NEEDS CLARIFICATION whether to update pyproject.toml or if constitution is aspirational |
| Many N/A checks | This feature is a batch processing script for audio generation, not an online API or learner-facing content generation system. Most constitution checks are specific to API endpoints or learning content pipelines. Core principles (code quality, testing, performance for batch) are satisfied |

---

### Post-Design Re-evaluation (Phase 1 Complete)

**Date**: 2026-02-12

After completing research, data model, contracts, and quickstart documentation, the Constitution Check evaluations remain valid:

✅ **Code Quality & Maintainability**: 
- Design follows single-responsibility principle with separate modules (VoiceResolver, MetadataGenerator, AudioProcessor)
- All new code will have type hints (enforced by Pydantic models)
- Reuses existing utilities (NotionClient, LLMClient, tts_with_elevenlabs)
- Python 3.13 decision documented in research.md with clear rationale

✅ **Testing Standards & Quality Gates**:
- Unit tests planned for: voice resolution, filename sanitization, metadata generation, duplicate detection
- Integration tests planned for: full pipeline (Notion → audio → Notion update)
- Quality gates adapted to audio processing domain: file existence, format validation, metadata format, timestamp presence

✅ **User Experience Consistency**:
- While not learner-facing, maintains consistency in Notion updates (Description and Tags fields)
- Error messages follow structured format for troubleshooting (see cli-contract.md)
- Audio-text alignment validated via existing ElevenLabs TTS wrapper

✅ **Performance Requirements**:
- Batch processing design prioritizes quality (LLM metadata, high-quality TTS) over speed
- Error handling isolates failures per record (95% success rate target)
- Sequential processing prevents rate limit issues with external APIs

**No changes to Constitution Check status required.** All gates that apply to batch processing scripts pass or have documented justifications.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── havachat/
│   ├── cli/
│   │   └── notion_audio_processor.py    # Main CLI script (NEW)
│   ├── integrations/
│   │   └── notion_audio/                # Feature module (NEW)
│   │       ├── __init__.py
│   │       ├── processor.py             # Core processing logic
│   │       ├── metadata_generator.py    # LLM-based metadata generation
│   │       └── voice_resolver.py        # Voice database lookup
│   └── utils/
│       ├── notion_client.py             # Existing Notion API client
│       └── llm_client.py                # Existing LLM client
├── tools/
│   └── audio/
│       └── tts_with_elevenlabs.py       # Existing ElevenLabs TTS
└── models/
    └── notion_audio.py                  # Pydantic models (NEW)

tests/
├── integration/
│   └── test_notion_audio_processor.py   # End-to-end tests (NEW)
└── unit/
    └── havachat/
        └── integrations/
            └── notion_audio/            # Unit tests for modules (NEW)
                ├── test_processor.py
                ├── test_metadata_generator.py
                └── test_voice_resolver.py
```

**Structure Decision**: Using "Option 1: Single project" pattern. The feature is organized as:
- **CLI entry point**: `src/havachat/cli/notion_audio_processor.py` - follows existing pattern of `notion_sync.py` in same directory
- **Feature module**: `src/havachat/integrations/notion_audio/` - new directory for audio-specific Notion integration logic
- **Reuse existing utilities**: `notion_client.py`, `llm_client.py`, and `tts_with_elevenlabs.py` - no duplication of existing functionality
- **Models**: `src/models/notion_audio.py` - Pydantic models for Audio Content Record, Voice Configuration, etc.
- **Tests organized by type**: Unit tests mirror source structure, integration tests validate full pipeline

## Complexity Tracking

No complexity violations detected. The Python version discrepancy (3.13 vs 3.14) is documented in Constitution Check and requires clarification.
