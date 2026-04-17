# Tasks: Notion Audio Content Processor

**Feature Branch**: `001-notion-audio-processor`  
**Input**: Design documents from `/specs/001-notion-audio-processor/`  
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/cli-contract.md ✅

**Tests**: Tests are OPTIONAL for this feature (not explicitly requested in spec). Tasks are included but can be skipped if not needed.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create feature module directory structure: src/havachat/integrations/notion_audio/
- [X] T002 Create __init__.py files for new modules: src/havachat/integrations/notion_audio/__init__.py
- [X] T003 [P] Create test directories: tests/unit/havachat/integrations/notion_audio/ and tests/integration/
- [X] T004 [P] Verify existing dependencies are available: elevenlabs, requests, pydantic, instructor
- [X] T005 Create .env.example file with all required environment variables documented

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Create Pydantic models in src/models/notion_audio.py: AudioContentStatus enum, ContentMetadata, ProcessingResult, BatchProcessingSummary, AudioProcessorConfig
- [X] T007 [P] Implement filename sanitization utility function in src/havachat/integrations/notion_audio/utils.py: sanitize_filename()
- [X] T008 [P] Implement audio file path construction in src/havachat/integrations/notion_audio/utils.py: get_audio_storage_path()
- [X] T009 [P] Implement content hash utilities in src/havachat/integrations/notion_audio/utils.py: compute_content_hash(), save_content_hash(), should_regenerate_audio()
- [X] T010 Extend NotionClient for Audio Database queries in src/havachat/utils/notion_client.py: add query_audio_database() and update_audio_record() methods
- [X] T011 [P] Create configuration loader in src/havachat/integrations/notion_audio/config.py: load_config_from_env() using AudioProcessorConfig.from_env()
- [X] T012 [P] Write unit tests for filename sanitization in tests/unit/havachat/integrations/notion_audio/test_utils.py: test edge cases (special chars, unicode, length limits)
- [X] T013 [P] Write unit tests for content hash utilities in tests/unit/havachat/integrations/notion_audio/test_utils.py: test duplicate detection logic

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Audio Generation from Content (Priority: P1) 🎯 MVP

**Goal**: Process Notion records marked "Ready for Audio" and generate high-quality audio files with timestamps, organized by topic/sub-type

**Independent Test**: Mark a single content record as "Ready for Audio", run processor, verify audio file exists at correct path with valid timing information

<function_calls>
<invoke name="create_file">
<parameter name="content"># Tasks: Notion Audio Content Processor

**Feature Branch**: `001-notion-audio-processor`  
**Input**: Design documents from `/specs/001-notion-audio-processor/`  
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/cli-contract.md ✅

**Tests**: Tests are OPTIONAL for this feature (not explicitly requested in spec). Tasks are included but can be skipped if not needed.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create feature module directory structure: src/havachat/integrations/notion_audio/
- [X] T002 Create __init__.py files for new modules: src/havachat/integrations/notion_audio/__init__.py
- [X] T003 [P] Create test directories: tests/unit/havachat/integrations/notion_audio/ and tests/integration/
- [X] T004 [P] Verify existing dependencies are available: elevenlabs, requests, pydantic, instructor
- [X] T005 Create .env.example file with all required environment variables documented

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Create Pydantic models in src/models/notion_audio.py: AudioContentStatus enum, ContentMetadata, ProcessingResult, BatchProcessingSummary, AudioProcessorConfig
- [X] T007 [P] Implement filename sanitization utility function in src/havachat/integrations/notion_audio/utils.py: sanitize_filename()
- [X] T008 [P] Implement audio file path construction in src/havachat/integrations/notion_audio/utils.py: get_audio_storage_path()
- [X] T009 [P] Implement content hash utilities in src/havachat/integrations/notion_audio/utils.py: compute_content_hash(), save_content_hash(), should_regenerate_audio()
- [X] T010 Extend NotionClient for Audio Database queries in src/havachat/utils/notion_client.py: add query_audio_database() and update_audio_record() methods
- [X] T011 [P] Create configuration loader in src/havachat/integrations/notion_audio/config.py: load_config_from_env() using AudioProcessorConfig.from_env()
- [X] T012 [P] Write unit tests for filename sanitization in tests/unit/havachat/integrations/notion_audio/test_utils.py: test edge cases (special chars, unicode, length limits)
- [X] T013 [P] Write unit tests for content hash utilities in tests/unit/havachat/integrations/notion_audio/test_utils.py: test duplicate detection logic

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Audio Generation from Content (Priority: P1) 🎯 MVP

**Goal**: Process Notion records marked "Ready for Audio" and generate high-quality audio files with timestamps, organized by topic/sub-type

**Independent Test**: Mark a single content record as "Ready for Audio", run processor, verify audio file exists at correct path with valid timing information

### Tests for User Story 1 (OPTIONAL - only if comprehensive testing needed) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T014 [P] [US1] Write integration test in tests/integration/test_notion_audio_processor.py: test_audio_generation_end_to_end() with mocked Notion/ElevenLabs
- [X] T015 [P] [US1] Write unit test in tests/unit/havachat/integrations/notion_audio/test_processor.py: test_process_single_record()

### Implementation for User Story 1

- [X] T016 [US1] Create AudioProcessor class in src/havachat/integrations/notion_audio/processor.py: __init__(notion_client, storage_path), _query_records(), _create_storage_directories()
- [X] T017 [US1] Implement audio generation logic in src/havachat/integrations/notion_audio/processor.py: _generate_audio() method calling text_to_speech_with_timestamps() from src/tools/audio/tts_with_elevenlabs.py (REUSE existing tool with timestamps!)
- [X] T018 [US1] Implement duplicate detection in src/havachat/integrations/notion_audio/processor.py: check content hash before generating audio
- [X] T019 [US1] Implement per-record processing in src/havachat/integrations/notion_audio/processor.py: process_record() with error isolation
- [X] T020 [US1] Implement batch processing loop in src/havachat/integrations/notion_audio/processor.py: process_batch() returning BatchProcessingSummary
- [X] T021 [US1] Add detailed logging for audio generation in src/havachat/integrations/notion_audio/processor.py: log record ID, timing, file paths, errors
- [X] T022 [US1] Create CLI entry point in src/havachat/cli/notion_audio_processor.py: main() with argument parsing (--dry-run, --limit, --verbose, --quiet)
- [X] T023 [US1] Implement environment validation in src/havachat/cli/notion_audio_processor.py: validate_environment() checking all required env vars
- [X] T024 [US1] Implement CLI output formatting in src/havachat/cli/notion_audio_processor.py: progress reporting, batch summary, error listing
- [X] T025 [US1] Add exit code handling in src/havachat/cli/notion_audio_processor.py: return appropriate exit codes (0-4) per CLI contract

**Checkpoint**: At this point, User Story 1 should be fully functional - can generate audio files for Notion content

**Manual Test**: 
```bash
# Create test record in Notion with Status="Ready for Audio"
uv run python -m src.havachat.cli.notion_audio_processor --limit 1 --verbose
# Verify: audio file created, Notion Status updated to "Completed"
```

---

## Phase 4: User Story 2 - Automatic Metadata Generation (Priority: P2)

**Goal**: After generating audio, automatically analyze content and generate Description + Tags, updating Notion records

**Independent Test**: Process a content record and verify Description (50-200 chars) and Tags (3-7 hashtags, no spaces) are populated in Notion

### Tests for User Story 2 (OPTIONAL) ⚠️

- [ ] T026 [P] [US2] Write unit test in tests/unit/havachat/integrations/notion_audio/test_metadata_generator.py: test_generate_metadata() with mocked LLM
- [ ] T027 [P] [US2] Write unit test in tests/unit/havachat/integrations/notion_audio/test_metadata_generator.py: test_fallback_metadata() for error cases

### Implementation for User Story 2

- [ ] T028 [P] [US2] Create MetadataGenerator class in src/havachat/integrations/notion_audio/metadata_generator.py: __init__() with LLMClient
- [ ] T029 [US2] Implement LLM prompt template in src/havachat/integrations/notion_audio/metadata_generator.py: METADATA_PROMPT constant with content/topic/sub-type placeholders
- [ ] T030 [US2] Implement metadata generation in src/havachat/integrations/notion_audio/metadata_generator.py: generate_metadata() returning ContentMetadata with retry logic
- [ ] T031 [US2] Implement fallback metadata in src/havachat/integrations/notion_audio/metadata_generator.py: _generate_fallback() for when LLM fails
- [ ] T032 [US2] Integrate metadata generation into AudioProcessor in src/havachat/integrations/notion_audio/processor.py: call MetadataGenerator after audio generation
- [ ] T033 [US2] Implement Notion update logic in src/havachat/integrations/notion_audio/processor.py: update Description and Tags fields after metadata generation
- [ ] T034 [US2] Add metadata generation error handling in src/havachat/integrations/notion_audio/processor.py: log errors but continue (don't block audio file)
- [ ] T035 [US2] Add logging for metadata generation in src/havachat/integrations/notion_audio/processor.py: log generated descriptions, tags, fallback usage

**Checkpoint**: At this point, User Stories 1 AND 2 should both work - audio generation + metadata enrichment

**Manual Test**:
```bash
uv run python -m src.havachat.cli.notion_audio_processor --limit 1 --verbose
# Verify: Notion record has Description (50-200 chars) and Tags (e.g., "#grammar #english")
```

---

## Phase 5: User Story 3 - Voice Selection and Configuration (Priority: P3)

**Goal**: Allow content managers to assign specific voices from Voice Database; processor uses assigned voice or falls back to default

**Independent Test**: Assign different voices to content records, verify generated audio uses correct voice for each record

### Tests for User Story 3 (OPTIONAL) ⚠️

- [X] T036 [P] [US3] Write unit test in tests/unit/havachat/integrations/notion_audio/test_voice_resolver.py: test_resolve_voice() with cached voices
- [X] T037 [P] [US3] Write unit test in tests/unit/havachat/integrations/notion_audio/test_voice_resolver.py: test_fallback_to_default() when voice missing

### Implementation for User Story 3

- [X] T038 [P] [US3] Create VoiceResolver class in src/havachat/integrations/notion_audio/voice_resolver.py: __init__(notion_client, voice_db_id, default_voice_id) - accepts existing NotionClient for consistency
- [X] T039 [US3] Implement voice caching in src/havachat/integrations/notion_audio/voice_resolver.py: _cache dict and _load_voice() method using notion_client.query_database_filtered()
- [X] T040 [US3] Implement voice resolution in src/havachat/integrations/notion_audio/voice_resolver.py: resolve_voice(voice_relation_id) querying Voice Database via NotionClient with fallback to default
- [X] T041 [US3] Implement default voice handling in src/havachat/integrations/notion_audio/voice_resolver.py: _get_default_voice() from constructor parameter
- [X] T042 [US3] Integrate VoiceResolver into AudioProcessor in src/havachat/integrations/notion_audio/processor.py: initialize VoiceResolver with shared NotionClient, call before audio generation
- [X] T043 [US3] Update audio generation to use resolved voice in src/havachat/integrations/notion_audio/processor.py: pass voice_id to text_to_speech_with_timestamps() from tools module
- [X] T044 [US3] Add voice resolution logging in src/havachat/integrations/notion_audio/processor.py: log which voice used, fallback events, cache hits

**Checkpoint**: All user stories should now be independently functional - complete audio generation pipeline with voice selection

**Manual Test**:
```bash
# Create Voice Database in Notion with Name="Rachel" and Voice Id="21m00Tcm4TlvDq8ikWAM"
# Assign voice to content record via Voices relation field
uv run python -m src.havachat.cli.notion_audio_processor --record-id <notion-page-id> --verbose
# Verify: Log shows "Voice resolved: Rachel (21m00Tcm4TlvDq8ikWAM)"
```

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and final quality assurance

- [ ] T045 [P] Add comprehensive error messages in src/havachat/integrations/notion_audio/processor.py: follow error format from CLI contract (record ID, step, suggestion)
- [ ] T046 [P] Implement progress bar for long batches in src/havachat/cli/notion_audio_processor.py: show "[▓░] 50% (25/50) - ETA: 5m" when >10 records
- [ ] T047 [P] Add cost tracking in src/havachat/integrations/notion_audio/processor.py: log ElevenLabs character count and estimated cost per batch
- [ ] T048 [P] Optimize voice caching in src/havachat/integrations/notion_audio/voice_resolver.py: pre-load all voices if voice DB is small (<100 voices)
- [ ] T049 Add rate limit handling in src/havachat/integrations/notion_audio/processor.py: small delay between Notion API calls if needed (~0.3s)
- [ ] T050 [P] Update .env.example with all optional variables: TTS_MODEL, AUDIO_FORMAT, LLM_MODEL, LOG_LEVEL
- [ ] T051 [P] Create comprehensive docstrings in all new modules: follow Google style with Args, Returns, Raises sections
- [ ] T052 [P] Add type hints to all functions in src/havachat/integrations/notion_audio/: ensure mypy compliance
- [ ] T053 Run full integration test with real Notion/ElevenLabs (use test database): verify end-to-end with 5-10 test records
- [ ] T054 Verify success rate meets SC-001: run batch processing, ensure ≥95% success rate
- [ ] T055 Verify processing time meets SC-002: measure time per 1000 characters, ensure ≤30 seconds
- [ ] T056 Verify file organization meets SC-003: check all audio files are in correct Topic/Sub-Type folders
- [ ] T057 Verify metadata quality meets SC-004/SC-005: check Description is 50-200 chars, Tags are 3-7 hashtags with no spaces
- [ ] T058 [P] Update README.md or docs/: add section about Notion Audio Processor with link to quickstart.md
- [ ] T059 Manual walkthrough of quickstart.md: follow every step to verify accuracy
- [ ] T060 Code cleanup and refactoring: extract common patterns, improve readability, remove debug code

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if team has capacity)
  - Or sequentially in priority order: P1 (US1) → P2 (US2) → P3 (US3)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Extends US1 but should be independently testable (metadata generation is separate concern)
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Extends US1 but should be independently testable (voice resolution is separate concern)

**Note**: US2 and US3 both integrate with US1's AudioProcessor, but they modify different stages:
- US2 adds metadata generation AFTER audio is created
- US3 adds voice resolution BEFORE audio is created
- Both can be developed in parallel if coordination is maintained

### Within Each User Story

- Tests (if included) MUST be written and FAIL before implementation
- Utility/core classes before integration
- Integration into AudioProcessor after feature module is complete
- Logging after core functionality works
- Story complete before moving to next priority

### Parallel Opportunities

#### Phase 1 (Setup)
- T003, T004, T005 can all run in parallel

#### Phase 2 (Foundational)
- T007, T008, T009, T011, T012, T013 can all run in parallel (different utility functions)
- T006 should complete early as other phases depend on models

#### Phase 3 (User Story 1)
- T014, T015 (tests) can run in parallel
- T023, T024 (CLI formatting) can run in parallel with T016-T021 (processor logic)

#### Phase 4 (User Story 2)
- T026, T027 (tests) can run in parallel
- T028, T029, T030, T031 (MetadataGenerator) can run in parallel with US3 if coordination maintained

#### Phase 5 (User Story 3)
- T036, T037 (tests) can run in parallel
- T038, T039, T040, T041 (VoiceResolver) can run in parallel with US2 if coordination maintained

#### Phase 6 (Polish)
- T045, T046, T047, T048, T050, T051, T052, T058 can all run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch tests in parallel (if writing tests):
[Terminal 1] Write T014: tests/integration/test_notion_audio_processor.py
[Terminal 2] Write T015: tests/unit/.../test_processor.py

# Launch implementation in parallel:
[Terminal 1] Write T016-T021: AudioProcessor in processor.py
[Terminal 2] Write T022-T025: CLI entry point in notion_audio_processor.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

**Goal**: Get audio generation working end-to-end

1. Complete Phase 1: Setup (T001-T005) → ~30 minutes
2. Complete Phase 2: Foundational (T006-T013) → ~2-3 hours
3. Complete Phase 3: User Story 1 (T014-T025) → ~4-5 hours
4. **STOP and VALIDATE**: Test with real Notion record → Verify audio file created
5. **MVP Complete**: Can now generate audio from Notion content

**Total time estimate**: ~1 day for MVP

### Incremental Delivery

1. **Sprint 1** (Day 1): Setup + Foundational + US1 → MVP (audio generation)
2. **Sprint 2** (Day 2): Add US2 → Audio + Metadata (auto-generated descriptions/tags)
3. **Sprint 3** (Day 3): Add US3 → Audio + Metadata + Voice Selection (custom voices)
4. **Sprint 4** (Day 4): Polish → Production-ready (error handling, progress bars, docs)

Each sprint delivers working, testable functionality.

### Parallel Team Strategy

With 2-3 developers:

1. **Together** (Day 1 morning): Complete Setup + Foundational (T001-T013)
2. **Parallel** (Day 1 afternoon - Day 3):
   - **Developer A**: User Story 1 (T014-T025) - Core audio generation
   - **Developer B**: User Story 2 (T026-T035) - Metadata generation (waits for T016 core structure)
   - **Developer C**: User Story 3 (T036-T044) - Voice resolver (waits for T016 core structure)
3. **Together** (Day 4): Polish and QA (T045-T060)

**Note**: Developer B and C should coordinate on AudioProcessor integration points.

---

## Design Notes: Maximizing Reuse & Flexibility

### Existing Infrastructure Reused

1. **NotionClient** (`src/havachat/utils/notion_client.py`):
   - ✅ Generic query/update with retry logic
   - ✅ API v2025-09-03 support with data_source_id
   - ✅ Schema validation framework
   - 🔧 **Extended** with generic `query_database_filtered()` and `update_page_properties()` for reusability

2. **text_to_speech_with_timestamps()** (`src/tools/audio/tts_with_elevenlabs.py`):
   - ✅ **Directly reused** - already has timestamps support!
   - ✅ Returns Transcript object with character/word/sentence timing
   - ✅ Handles audio file saving, retry logic, cost tracking
   - ✅ Supports multiple output formats (mp3_44100_192 specified in config)
   - **Why not ElevenLabsClient?** The client in `utils/` doesn't support timestamps; the standalone tool does

3. **LLMClient** (`src/havachat/utils/llm_client.py`):
   - ✅ **Directly reused** for metadata generation
   - ✅ Instructor integration for structured Pydantic responses
   - ✅ Retry logic and token tracking built-in

### Design Principles for Future Flexibility

1. **NotionClient Extensions**: Generic methods (`query_database_filtered`, `update_page_properties`) can be reused for ANY Notion database integration, not just Audio Content

2. **Processor Pattern**: `AudioProcessor` design can be templated for future processors:
   - `XyzProcessor(notion_client, storage_path, config)` - same constructor pattern
   - `process_batch() → BatchProcessingSummary` - same interface
   - Per-record error isolation - same error handling

3. **Shared NotionClient Instance**: VoiceResolver and AudioProcessor share the same NotionClient instance (dependency injection pattern) - avoids multiple connections

4. **Tool Composition**: Using standalone `text_to_speech_with_timestamps()` keeps audio generation logic separate and testable

5. **Configuration Pattern**: `AudioProcessorConfig.from_env()` can be templated for other processors

### Future Extension Points

- **New Notion Processors**: Copy the pattern from `notion_audio/` to create `notion_xyz/`
- **Different TTS Providers**: Adapter pattern - wrap different providers with same interface as `text_to_speech_with_timestamps()`
- **Different Metadata Generators**: `MetadataGenerator` accepts any `LLMClient` - swap providers easily
- **Custom Voice Sources**: `VoiceResolver` can be extended to query different voice databases or APIs

---

## Task Count Summary

- **Phase 1 (Setup)**: 5 tasks
- **Phase 2 (Foundational)**: 8 tasks (BLOCKS all stories)
- **Phase 3 (User Story 1)**: 12 tasks (including 2 optional tests)
- **Phase 4 (User Story 2)**: 10 tasks (including 2 optional tests)
- **Phase 5 (User Story 3)**: 9 tasks (including 2 optional tests)
- **Phase 6 (Polish)**: 16 tasks

**Total**: 60 tasks

**Critical path** (minimum for MVP): T001-T013 (Setup + Foundational) + T016-T025 (US1 implementation) = ~23 tasks

**Parallel opportunities**: ~25 tasks marked [P] can run in parallel if team capacity allows

---

## Suggested MVP Scope

For fastest time-to-value, implement:
- ✅ Phase 1: Setup
- ✅ Phase 2: Foundational
- ✅ Phase 3: User Story 1 (audio generation only)
- ⏸️ Skip US2 and US3 initially
- ⏸️ Skip optional tests (T014, T015)
- ✅ Minimal polish: T045 (error messages), T053 (integration test)

**Minimum viable feature**: ~20 tasks → ~1 day of focused work

---

## Notes

- **[P] tasks**: Can run in parallel (different files, no shared dependencies)
- **[Story] label**: Maps task to specific user story for traceability
- **Test strategy**: Tests are optional; include if comprehensive QA needed
- **Integration points**: US2 and US3 both integrate with AudioProcessor (T016-T020) - coordinate if developed in parallel
- **Error handling**: Built into each story (per-record isolation, detailed logging)
- **Validation**: Manual tests at each checkpoint ensure story independence
- **Constitution compliance**: All tasks follow constitution principles (type hints, modularity, error handling, batch processing)

---

## Format Validation ✅

All tasks follow required format:
- ✅ Checkbox: `- [ ]`
- ✅ Task ID: T001, T002, etc. (sequential)
- ✅ [P] marker: Only on parallelizable tasks
- ✅ [Story] label: On user story tasks only (US1, US2, US3)
- ✅ Description: Clear action with exact file path
- ✅ No Setup/Foundational phase tasks have story labels (correct)
- ✅ User Story phase tasks have story labels (correct)
- ✅ Polish phase tasks do not have story labels (correct)
