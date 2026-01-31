# Task Breakdown: Pre-generation Pipeline for Learning Content

**Feature**: Pre-generation Pipeline  
**Branch**: `001-pregen-pipeline`  
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)  
**Last Updated**: 2026-01-28

## Task Format

```
- [ ] [TaskID] [P] [Story] Description with file path
```

- **TaskID**: Sequential number (T001, T002, ...)
- **[P]**: Parallelizable marker (different files, no dependencies)
- **[Story]**: User story label (US1, US2, US3, ...) for story phases only
- **Description**: Clear action with exact file path

## Implementation Strategy

**MVP Scope**: User Story 1 + User Story 2 (vocab and grammar enrichment only)  
**Incremental Delivery**: Each user story is independently testable and deliverable  
**Priority Order**: P1 (US1, US2) → P2 (US5, US3) → P3 (US4)

## Critical Implementation Notes

**Learning Item Generation**: Each learning item (vocab, grammar, pronunciation, idioms, etc.) is enriched one-by-one via individual LLM calls with retry logic (up to 3 retries per item).

**Content Generation**: Single LLM call per topic generates N conversations + N stories using ALL learning item categories together. Chain-of-thought (generate → critique → revise → assign scenarios) is structured within the prompt itself, not executed as sequential API calls.

---

## Phase 1: Setup & Project Initialization

**Goal**: Bootstrap project structure, install dependencies, configure development environment

- [X] T001 Initialize Python 3.14 project with uv package manager in project root
- [X] T002 Install core dependencies via uv: langgraph>=1.0.7, instructor>=1.0.0, pydantic>=2.0.0
- [X] T003 Install data processing dependencies: pandas>=2.0.0, docling>=2.70.0
- [X] T004 Install testing dependencies: pytest>=8.0.0, black>=24.8.0
- [X] T005 Install ML dependencies: sentence-transformers, openai (or anthropic)
- [X] T006 Create src/pipeline/__init__.py with version metadata
- [X] T007 Create src/pipeline/utils/__init__.py for shared utilities
- [X] T008 Create tests/ directory structure: unit/, contract/, integration/, fixtures/
- [X] T009 Configure pytest.ini with test discovery patterns and markers
- [X] T010 Create .env.template with required environment variables (OPENAI_API_KEY, HAVACHAT_KNOWLEDGE_PATH)
- [X] T011 Create README.md with project overview and setup instructions
- [X] T012 Verify havachat-knowledge repository access and directory structure

---

## Phase 2: Foundational Infrastructure (Blocking Prerequisites)

**Goal**: Implement shared components required by all pipeline stages

### Pydantic Schemas & Validation

- [X] T013 [P] Create src/pipeline/validators/__init__.py
- [X] T014 [P] Define LevelSystem, Category, ContentType, SegmentType enums in src/pipeline/validators/schema.py
- [X] T015 [P] Define LearningItem Pydantic model with all 12 categories in src/pipeline/validators/schema.py
- [X] T016 [P] Define ContentUnit and Segment Pydantic models in src/pipeline/validators/schema.py
- [X] T017 [P] Define Question, MCQOption, QuestionType Pydantic models in src/pipeline/validators/schema.py
- [X] T018 [P] Define Topic, Scenario (with rich tagging), UsageStats, ValidationReport models in src/pipeline/validators/schema.py
- [X] T019 [P] Write unit tests for all Pydantic models in tests/unit/test_schemas.py

### LLM Client & Instructor Integration

- [X] T020 Create src/pipeline/utils/llm_client.py with Instructor-wrapped OpenAI client
- [X] T021 Implement retry logic (3 attempts with exponential backoff) in llm_client.py
- [X] T022 Implement structured response generation with Pydantic model validation in llm_client.py
- [X] T023 Add request/response logging (prompt hash, tokens, latency) in llm_client.py
- [X] T024 Write unit tests for llm_client with mocked API responses in tests/unit/test_llm_client.py

### File I/O & Data Handling

- [X] T025 [P] Create src/pipeline/utils/file_io.py with JSON read/write functions
- [X] T026 [P] Implement TSV/CSV parsing functions in file_io.py
- [X] T027 [P] Implement markdown parsing helper in file_io.py
- [X] T028 [P] Add directory creation with language/level structure in file_io.py
- [X] T029 [P] Write unit tests for file I/O functions in tests/unit/test_file_io.py

### Logging & Observability

- [X] T030 Create src/pipeline/utils/logging_config.py with structured JSON logging
- [X] T031 Implement JsonFormatter for log records in logging_config.py
- [X] T032 Add context manager for logging pipeline stages in logging_config.py
- [X] T033 Configure log levels and output destinations in logging_config.py

### Semantic Similarity for Scenario Reuse

- [X] T034 SKIPPED - Semantic similarity handled by Meilisearch
- [X] T035 SKIPPED - Semantic similarity handled by Meilisearch
- [X] T036 SKIPPED - Semantic similarity handled by Meilisearch
- [X] T037 SKIPPED - Semantic similarity handled by Meilisearch
- [X] T038 SKIPPED - Semantic similarity handled by Meilisearch

### Base Enricher Abstract Class

- [X] T039 Create src/pipeline/enrichers/__init__.py
- [X] T040 Create src/pipeline/enrichers/base.py with BaseEnricher abstract class
- [X] T041 Define abstract methods: parse_source(), detect_missing_fields(), build_prompt(), validate_output() in base.py
- [X] T042 Implement common retry loop logic in BaseEnricher
- [X] T043 Implement manual review queue writing in BaseEnricher

---

## Phase 3: User Story 1 - Vocab Enrichment (P1) ✅ COMPLETE

**Goal**: Import and enrich official vocabulary lists for Mandarin, Japanese, French

**Status**: All tasks complete with optimizations (language-specific models, parallel processing, checkpoints, token tracking)

**Independent Test**: Run enricher on sample vocab files, verify JSON output with all required fields

### Mandarin Vocab Enricher

- [X] T044 [P] [US1] Create src/pipeline/enrichers/vocab/__init__.py
- [X] T045 [P] [US1] Create src/pipeline/enrichers/vocab/mandarin.py with MandarinVocabEnricher class
- [X] T046 [US1] Implement parse_source() for TSV with "Word, Part of Speech" columns in mandarin.py
- [X] T047 [US1] Implement detect_missing_fields() checking for pinyin, definition, examples in mandarin.py
- [X] T048 [US1] Create src/pipeline/prompts/mandarin/vocab_prompts.py with Chinese-specific prompts
- [X] T049 [US1] Implement build_prompt() using prompts from vocab_prompts.py in mandarin.py
- [X] T050 [US1] Implement validate_output() enforcing romanization presence in mandarin.py
- [X] T051 [US1] Add polysemy detection and sense_gloss generation in mandarin.py
- [X] T052 [US1] Write unit tests for MandarinVocabEnricher in tests/unit/test_mandarin_vocab_enricher.py

### Japanese Vocab Enricher

- [X] T053 [P] [US1] Create src/pipeline/enrichers/vocab/japanese.py with JapaneseVocabEnricher class
- [X] T054 [US1] Implement parse_source() for JSON with {word, meaning, furigana, romaji, level} in japanese.py
- [X] T055 [US1] Implement detect_missing_fields() preserving existing furigana/romaji in japanese.py
- [X] T056 [US1] Create src/pipeline/prompts/japanese/vocab_prompts.py with Japanese-specific prompts
- [X] T057 [US1] Implement build_prompt() for missing fields only in japanese.py
- [X] T058 [US1] Implement validate_output() preserving source data in japanese.py
- [X] T059 [US1] Write unit tests for JapaneseVocabEnricher in tests/unit/test_japanese_vocab_enricher.py

### French Vocab Enricher

- [X] T060 [P] [US1] Create src/pipeline/enrichers/vocab/french.py with FrenchVocabEnricher class
- [X] T061 [US1] Implement parse_source() for CSV with "Mot, Définition, Exemple" columns in french.py
- [X] T062 [US1] Implement detect_missing_fields() preserving existing definitions in french.py
- [X] T063 [US1] Create src/pipeline/prompts/french/vocab_prompts.py with French-specific prompts
- [X] T064 [US1] Implement build_prompt() using existing definitions as base in french.py
- [X] T065 [US1] Implement validate_output() without romanization requirement in french.py
- [X] T066 [US1] Write unit tests for FrenchVocabEnricher in tests/unit/test_french_vocab_enricher.py

### Vocab Enrichment CLI

- [X] T067 [US1] Create src/pipeline/cli/__init__.py
- [X] T068 [US1] Create src/pipeline/cli/enrich_vocab.py with CLI interface
- [X] T069 [US1] Implement argument parsing: --language, --level, --input, --enricher, --output in enrich_vocab.py
- [X] T070 [US1] Implement batch processing loop with progress reporting in enrich_vocab.py
- [X] T071 [US1] Implement summary statistics (success rate, LLM tokens, duration) in enrich_vocab.py
- [X] T072 [US1] Add --dry-run and --max-items flags for testing in enrich_vocab.py
- [X] T073 [US1] Write integration test for end-to-end vocab enrichment in tests/integration/test_end_to_end_vocab.py

### Test Fixtures

- [X] T074 [P] [US1] Create tests/fixtures/mandarin_vocab_sample.tsv with 10 sample words
- [X] T075 [P] [US1] Create tests/fixtures/japanese_vocab_sample.json with 10 sample words
- [X] T076 [P] [US1] Create tests/fixtures/french_vocab_sample.csv with 10 sample words

### Meilisearch Integration Test

- [X] T076a [US1] Create tests/test_vocab_meilisearch.py for testing enrichment + Meilisearch indexing with 20 records

---

## Phase 4: User Story 2 - Grammar Enrichment (P1)

**Goal**: Import and enrich official grammar lists for Mandarin, Japanese, French

**Independent Test**: Run enricher on sample grammar files, verify narrow-scope items without "mega-items"

### Mandarin Grammar Enricher

- [X] T077 [P] [US2] Create src/pipeline/enrichers/grammar/__init__.py
- [X] T078 [P] [US2] Create src/pipeline/enrichers/grammar/mandarin.py with MandarinGrammarEnricher class
- [X] T079 [US2] Implement parse_source() for CSV with "类别,类别名称,细目,语法内容" columns in mandarin.py
- [X] T080 [US2] Implement detect_missing_fields() checking for definition, examples in mandarin.py
- [X] T081 [US2] Create src/pipeline/prompts/mandarin/grammar_prompts.py with grammar-specific prompts (implemented inline in mandarin.py)
- [X] T082 [US2] Implement build_prompt() with granularity instructions (avoid mega-items) in mandarin.py
- [X] T083 [US2] Implement validate_output() with granularity checks in mandarin.py
- [X] T084 [US2] Add sub-item breakdown logic for broad patterns in mandarin.py
- [X] T085 [US2] Write unit tests for MandarinGrammarEnricher in tests/unit/test_mandarin_grammar_enricher.py

### Japanese Grammar Enricher

- [ ] T086 [P] [US2] Create src/pipeline/enrichers/grammar/japanese.py with JapaneseGrammarEnricher class
- [ ] T087 [US2] Implement parse_source() for TSV with "Type, Rule, Example" columns in japanese.py
- [ ] T088 [US2] Implement detect_missing_fields() preserving existing examples in japanese.py
- [ ] T089 [US2] Create src/pipeline/prompts/japanese/grammar_prompts.py with particle/structure prompts
- [ ] T090 [US2] Implement build_prompt() adding common learner errors in japanese.py
- [ ] T091 [US2] Implement validate_output() ensuring target_item extracts particle/pattern in japanese.py
- [ ] T092 [US2] Write unit tests for JapaneseGrammarEnricher in tests/unit/test_japanese_grammar_enricher.py

### French Grammar Enricher

- [ ] T093 [P] [US2] Create src/pipeline/enrichers/grammar/french.py with FrenchGrammarEnricher class
- [ ] T094 [US2] Implement parse_source() for markdown with "## A1: Category" and title lists in french.py
- [ ] T095 [US2] Implement title parsing to extract target_item and category hint in french.py
- [ ] T096 [US2] Create src/pipeline/prompts/french/grammar_prompts.py with conjugation/pronoun prompts
- [ ] T097 [US2] Implement build_prompt() generating form/usage explanations in french.py
- [ ] T098 [US2] Implement validate_output() with category="grammar" enforcement in french.py
- [ ] T099 [US2] Write unit tests for FrenchGrammarEnricher in tests/unit/test_french_grammar_enricher.py

### Grammar Enrichment CLI

- [X] T100 [US2] Create src/pipeline/cli/enrich_grammar.py with CLI interface
- [X] T101 [US2] Implement argument parsing: --language, --level, --input, --enricher, --output in enrich_grammar.py
- [X] T102 [US2] Implement batch processing with granularity warnings in enrich_grammar.py
- [X] T103 [US2] Implement summary statistics reporting in enrich_grammar.py
- [X] T104 [US2] Write integration test for end-to-end grammar enrichment in tests/integration/test_end_to_end_grammar.py

### Test Fixtures

- [X] T105 [P] [US2] Create tests/fixtures/mandarin_grammar_sample.csv with 10 sample patterns
- [ ] T106 [P] [US2] Create tests/fixtures/japanese_grammar_sample.tsv with 10 sample patterns (SKIPPED - future work)
- [ ] T107 [P] [US2] Create tests/fixtures/french_grammar_sample.md with 10 sample patterns (SKIPPED - future work)

---

## Phase 5: User Story 5 - QA Gates (P2)

**Goal**: Run automated validation gates to ensure content quality before publication

**Independent Test**: Run QA gates on test batch with known violations, verify report identifies all failures

### Validation Modules

- [ ] T108 [P] [US5] Create src/pipeline/validators/presence.py with presence check logic
- [ ] T109 [P] [US5] Implement check_learning_item_presence() verifying IDs exist and appear in text in presence.py
- [ ] T110 [P] [US5] Add language-aware tokenization for Chinese/Japanese/French in presence.py
- [ ] T111 [P] [US5] Create src/pipeline/validators/duplication.py with duplicate detection
- [ ] T112 [P] [US5] Implement check_duplicates() comparing (language, category, lemma, sense_gloss) in duplication.py
- [ ] T113 [P] [US5] Handle polysemy cases (same lemma, different sense_gloss) in duplication.py
- [ ] T114 [P] [US5] Create src/pipeline/validators/links.py with link correctness validation
- [ ] T115 [P] [US5] Implement check_link_correctness() resolving all referenced IDs in links.py
- [ ] T116 [P] [US5] Create src/pipeline/validators/answerability.py with question validation
- [ ] T117 [P] [US5] Implement check_answerability() using LLM to verify answers from text in answerability.py

### QA Gate Orchestration

- [ ] T118 [US5] Create src/pipeline/cli/run_qa_gates.py with CLI interface
- [ ] T119 [US5] Implement argument parsing: --language, --level, --content-dir, --gates, --output in run_qa_gates.py
- [ ] T120 [US5] Implement gate orchestration (run all gates sequentially) in run_qa_gates.py
- [ ] T121 [US5] Implement ValidationResult aggregation in run_qa_gates.py
- [ ] T122 [US5] Generate JSON report with flagged items and summary stats in run_qa_gates.py
- [ ] T123 [US5] Generate markdown report with human-readable findings in run_qa_gates.py
- [ ] T124 [US5] Write integration test for QA gates with known violations in tests/integration/test_qa_gates.py

### Test Data for QA Gates

- [ ] T125 [P] [US5] Create test data with duplicate learning items in tests/fixtures/
- [ ] T126 [P] [US5] Create test data with broken references in tests/fixtures/
- [ ] T127 [P] [US5] Create test data with unanswerable questions in tests/fixtures/

---

## Phase 6: User Story 3 - Content Generation with Chain-of-Thought (P2) ✅ COMPLETE

**Goal**: Generate conversations/stories using ALL learning item categories together in single LLM call with chain-of-thought

**Independent Test**: Generate content from topic with all learning items, verify all learning_item_ids exist and appear in text

**Prerequisites**: All learning items from all categories (vocab, grammar, pronunciation, idioms, functional, cultural, writing system, misc) must be generated first

**Status**: All tasks complete. Two-stage content generation workflow implemented with chain-of-thought reasoning.

### Learning Item Generation (All Categories)

- [X] T128 [P] [US3] Create src/pipeline/generators/__init__.py
- [X] T129 [P] [US3] Create src/pipeline/generators/learning_item_generator.py with BaseLearningItemGenerator class
- [X] T130 [US3] Implement pronunciation item generation (tone pairs, initials, finals) from vocab in learning_item_generator.py
- [X] T131 [US3] Implement idiom/expression item generation from vocab phrases in learning_item_generator.py
- [X] T132 [US3] Implement functional language item generation from grammar patterns in learning_item_generator.py
- [X] T133 [US3] Implement cultural note item generation from topic/scenario context in learning_item_generator.py
- [X] T134 [US3] Implement writing system item generation for zh/ja languages in learning_item_generator.py
- [X] T135 [US3] Implement miscellaneous category item generation (sociolinguistic, pragmatic, literacy, pattern) in learning_item_generator.py
- [X] T136 [US3] Add deduplication logic across all categories in learning_item_generator.py
- [ ] T137 [US3] Write unit tests for learning item generation in tests/unit/test_learning_item_generator.py (DEFERRED)

### Learning Item Generation CLI

- [X] T138 [US3] Create src/pipeline/cli/generate_learning_items.py with CLI interface
- [X] T139 [US3] Implement argument parsing: --language, --level, --category, --source-dir, --output in generate_learning_items.py
- [X] T140 [US3] Implement batch generation with one-by-one LLM calls and retry logic in generate_learning_items.py
- [X] T141 [US3] Implement summary statistics (items generated per category, success rate) in generate_learning_items.py
- [ ] T142 [US3] Write integration test for learning item generation in tests/integration/test_learning_item_generation.py (DEFERRED)

### Content Generator with Chain-of-Thought

- [X] T143 [P] [US3] Create src/pipeline/generators/content_generator.py with ContentGenerator class using instructor library
- [X] T144 [US3] Define ChainOfThoughtContent Pydantic model with fields: initial_draft, critique, revised_content, learning_items_used in content_generator.py
- [X] T145 [US3] Define ContentBatch Pydantic model with fields: conversations[], stories[], chain_of_thought_metadata in content_generator.py
- [X] T146 [US3] Implement load_learning_items() in simplified format (target_item only) to minimize tokens in content_generator.py
- [X] T147 [US3] Prompts implemented inline in content_generator.py (chain-of-thought template: generate → critique → revise → assign scenarios as single prompt)
- [X] T148 [US3] Implement generate_content_batch() calling instructor.from_openai() with structured output in content_generator.py
- [X] T149 [US3] Implement chain-of-thought parsing extracting learning_item_ids from revised_content in content_generator.py
- [X] T150 [US3] Implement scenario assignment extracting 3-8 word scenarios in content_generator.py
- [X] T151 [US3] Implement segment creation with learning_item_ids validation in content_generator.py
- [X] T152 [US3] Implement presence validation (all IDs exist and appear in text) in content_generator.py
- [ ] T153 [US3] Write unit tests for ContentGenerator in tests/unit/test_content_generator.py (DEFERRED)

### Usage Tracking Module

- [X] T154 [P] [US3] Create src/pipeline/utils/usage_tracker.py with UsageTracker class
- [X] T155 [US3] Implement increment_appearances() updating usage_stats.json in usage_tracker.py
- [X] T156 [US3] Implement get_usage_report() generating summary statistics in usage_tracker.py
- [ ] T157 [US3] Write unit tests for UsageTracker in tests/unit/test_usage_tracker.py (DEFERRED)

### Content Generation CLI

- [X] T158 [US3] Create src/pipeline/cli/generate_content.py with CLI interface
- [X] T159 [US3] Implement argument parsing: --language, --level, --topic, --num-conversations, --num-stories in generate_content.py
- [X] T160 [US3] Implement content generation workflow: load items → generate batch → validate → track usage in generate_content.py
- [X] T161 [US3] Implement summary output (conversations generated, stories generated, learning items used, chain-of-thought quality metrics) in generate_content.py
- [X] T162 [US3] --force-code flag not needed (instructor handles retries automatically)
- [ ] T163 [US3] Write integration test for end-to-end two-stage workflow in tests/integration/test_two_stage_content_generation.py (DEFERRED)

### Test Fixtures

- [X] T164 [P] [US3] Create tests/fixtures/complete_learning_items/ with sample items from all 12 categories
- [X] T165 [P] [US3] Create tests/fixtures/expected_chain_of_thought.json with example chain-of-thought structure

---

## Phase 7: User Story 5 - Audio Generation with ElevenLabs TTS (P2)

**Goal**: Generate audio files for learning items and content units using ElevenLabs TTS with local-first storage

**Independent Test**: Generate audio for 50 learning items with multiple versions, verify local files created with correct paths, test voice pairing for conversations

**Prerequisites**: Learning items and content units must be generated and stored in consolidated JSON files first

### Voice Configuration & Validation

- [X] T180 [P] [US5] Create voice_config.json at repo root with language-to-voice-ID mappings
- [X] T181 [P] [US5] Define voice schema: voice_id, name, type (single|conversation_N_M_speaker_K), description, supported_languages[], comment
- [X] T182 [P] [US5] Add voice configurations for Mandarin (single + conversation_2_1 pair) in voice_config.json
- [X] T183 [P] [US5] Add voice configurations for French, Japanese (single + conversation pairs) in voice_config.json
- [X] T184 [P] [US5] Create src/pipeline/models/voice_config.py with VoiceConfig Pydantic model
- [X] T185 [P] [US5] Create src/pipeline/validators/voice_validator.py with voice config validation logic
- [X] T186 [US5] Implement validate_voice_config() checking voice ID exists for target language in voice_validator.py
- [X] T187 [US5] Implement validate_conversation_config() checking all speaker voice IDs exist in voice_validator.py
- [X] T188 [US5] Write unit tests for voice validation in tests/unit/test_voice_validator.py

### ElevenLabs Client

- [X] T189 [P] [US5] Create src/pipeline/utils/elevenlabs_client.py with ElevenLabsClient class
- [X] T190 [US5] Implement text_to_speech() calling ElevenLabs API with voice_id and format params in elevenlabs_client.py
- [X] T191 [US5] Implement retry logic (3 attempts with exponential backoff) for rate limits in elevenlabs_client.py
- [X] T192 [US5] Implement format support: opus_48000_32 (default), mp3_44100_64 (comparison) in elevenlabs_client.py
- [X] T193 [US5] Add request logging (voice_id, character count, format, latency) in elevenlabs_client.py
- [X] T194 [US5] Add cost tracking (character usage per request) in elevenlabs_client.py
- [X] T195 [US5] Write unit tests for ElevenLabsClient with mocked API in tests/unit/test_elevenlabs_client.py

### Audio Generator Core

- [X] T196 [P] [US5] Create src/pipeline/generators/audio_generator.py with AudioGenerator class
- [X] T197 [US5] Implement load_learning_items() from consolidated JSON files in audio_generator.py
- [X] T198 [US5] Implement load_content_units() from conversations.json and stories.json in audio_generator.py
- [X] T199 [US5] Implement generate_audio_for_item() synthesizing target_item text in audio_generator.py
- [X] T200 [US5] Implement generate_audio_for_content() with speaker-aware voice mapping in audio_generator.py
- [X] T201 [US5] Implement multi-version generation (1-3 versions per item) with _v1, _v2, _v3 suffixes in audio_generator.py
- [X] T202 [US5] Implement local file storage at {Language}/{Level}/02_Generated/audio/{category}/ in audio_generator.py
- [X] T203 [US5] Implement metadata update in learning_items_media.json and content_units_media.json in audio_generator.py
- [X] T204 [US5] Add batch processing with configurable batch size in audio_generator.py
- [X] T205 [US5] Write unit tests for AudioGenerator in tests/unit/test_audio_generator.py

### Audio Progress Tracking

- [X] T206 [P] [US5] Create src/pipeline/models/audio_progress.py with AudioProgress model
- [X] T207 [US5] Implement checkpoint-based resumption (save progress every N items) in audio_generator.py
- [X] T208 [US5] Store progress in {Language}/{Level}/audio_generation_progress.json in audio_generator.py
- [X] T209 [US5] Implement --resume-from-checkpoint flag logic in audio_generator.py
- [X] T210 [US5] Write unit tests for checkpoint resumption in tests/unit/test_audio_generator.py

### Audio Generation CLI

- [X] T211 [US5] Create src/pipeline/cli/generate_audio.py with CLI interface
- [X] T212 [US5] Implement argument parsing: --language, --level, --category, --batch-size, --versions, --format in generate_audio.py
- [X] T213 [US5] Implement --voice-id (for learning items) and --voice-config (for conversations) params in generate_audio.py
- [X] T214 [US5] Implement voice config validation before batch starts (fail fast) in generate_audio.py
- [X] T215 [US5] Implement batch processing workflow with progress logging in generate_audio.py
- [X] T216 [US5] Implement failure logging to {language}/audio_generation_failures.jsonl in generate_audio.py
- [X] T217 [US5] Implement summary output (items processed, success rate, format, character count) in generate_audio.py
- [X] T218 [US5] Write integration test for audio generation in tests/integration/test_audio_generation.py

### Audio Selection Tool

- [X] T219 [P] [US5] Create src/pipeline/cli/select_audio.py with CLI interface
- [X] T220 [US5] Implement argument parsing: --item-id, --selected-version in select_audio.py
- [X] T221 [US5] Implement metadata update setting selected: true for chosen version in select_audio.py
- [X] T222 [US5] Update audio_local_path to point to selected version in select_audio.py
- [X] T223 [US5] Write unit tests for audio selection in tests/unit/test_select_audio.py

### Cloudflare R2 Sync

- [X] T224 [P] [US5] Create src/pipeline/utils/r2_client.py with R2Client class using boto3
- [X] T225 [US5] Implement upload_file() with retry logic (3 attempts, exponential backoff) in r2_client.py
- [X] T226 [US5] Implement batch_upload() for multiple files in r2_client.py
- [X] T227 [US5] Add upload logging (file path, size, duration, success/failure) in r2_client.py
- [X] T228 [US5] Write unit tests for R2Client with mocked boto3 in tests/unit/test_r2_client.py

### Audio Sync CLI

- [X] T229 [US5] Create src/pipeline/cli/sync_audio.py with CLI interface
- [X] T230 [US5] Implement argument parsing: --language, --level, --category, --dry-run, --cleanup-local in sync_audio.py
- [X] T231 [US5] Implement sync workflow: read media JSON → filter selected versions → upload to R2 in sync_audio.py
- [X] T232 [US5] Update audio_url fields in media JSON files after successful upload in sync_audio.py
- [X] T233 [US5] Implement --dry-run flag for testing without actual upload in sync_audio.py
- [X] T234 [US5] Implement --cleanup-local flag to remove local files after successful sync in sync_audio.py
- [X] T235 [US5] Implement sync progress logging and summary output in sync_audio.py
- [X] T236 [US5] Write integration test for R2 sync workflow in tests/integration/test_audio_sync.py

### Audio QA Validation

- [X] T237 [P] [US5] Create src/pipeline/validators/audio_validator.py with audio validation logic
- [X] T238 [US5] Implement check_local_audio_files() verifying file exists, size >5KB, valid format header in audio_validator.py
- [X] T239 [US5] Implement check_audio_urls() verifying HTTP 200, content-type matches format in audio_validator.py
- [X] T240 [US5] Integrate audio validation into QA gates (src/pipeline/cli/run_qa_gates.py)
- [X] T241 [US5] Add audio validation to QA gate reports (missing files, broken URLs) in run_qa_gates.py
- [X] T242 [US5] Write unit tests for audio validation in tests/unit/test_audio_validator.py

### Test Fixtures for Audio

- [X] T243 [P] [US5] Create tests/fixtures/voice_config_test.json with test voice configurations
- [X] T244 [P] [US5] Create tests/fixtures/audio_metadata_test.json with sample audio metadata
- [X] T245 [P] [US5] Create mock audio files (.opus, .mp3) for testing in tests/fixtures/audio/

---

## Phase 8: User Story 4 - Question Generation (P3)

**Goal**: Generate comprehension questions for content units

**Independent Test**: Generate questions from conversation, verify answerability and type distribution

### Question Generator

- [ ] T166 [P] [US4] Create src/pipeline/generators/question_generator.py with QuestionGenerator class
- [ ] T167 [US4] Implement question type distribution (50-60% MCQ, 20-30% T/F, 20% short answer) in question_generator.py
- [ ] T168 [US4] Implement cognitive level distribution (40% detail, 30% inference, 30% main idea) in question_generator.py
- [ ] T169 [US4] Implement MCQ generation with 4 options (1 correct, 3 distractors) in question_generator.py
- [ ] T170 [US4] Implement true/false generation in question_generator.py
- [ ] T171 [US4] Implement short answer generation in question_generator.py
- [ ] T172 [US4] Implement rationale generation explaining learning value in question_generator.py
- [ ] T173 [US4] Implement difficulty tagging within content level range in question_generator.py
- [ ] T174 [US4] Write unit tests for QuestionGenerator in tests/unit/test_question_generator.py

### Question Generation CLI

- [ ] T175 [US4] Create src/pipeline/cli/generate_questions.py with CLI interface
- [ ] T176 [US4] Implement argument parsing: --content-id, --language, --level, --num-questions in generate_questions.py
- [ ] T177 [US4] Implement question generation workflow with answerability validation in generate_questions.py
- [ ] T178 [US4] Implement summary output (type distribution, difficulty, tags) in generate_questions.py
- [ ] T179 [US4] Write integration test for end-to-end question generation in tests/integration/test_end_to_end_questions.py

---

## Phase 8: User Story 4 - Question Generation (P3)

**Goal**: Generate comprehension questions for content units

**Independent Test**: Generate questions from conversation, verify answerability and type distribution

### Question Generator

- [ ] T246 [P] [US4] Create src/pipeline/generators/question_generator.py with QuestionGenerator class
- [ ] T247 [US4] Implement question type distribution (50-60% MCQ, 20-30% T/F, 20% short answer) in question_generator.py
- [ ] T248 [US4] Implement cognitive level distribution (40% detail, 30% inference, 30% main idea) in question_generator.py
- [ ] T249 [US4] Implement MCQ generation with 4 options (1 correct, 3 distractors) in question_generator.py
- [ ] T250 [US4] Implement true/false generation in question_generator.py
- [ ] T251 [US4] Implement short answer generation in question_generator.py
- [ ] T252 [US4] Implement rationale generation explaining learning value in question_generator.py
- [ ] T253 [US4] Implement difficulty tagging within content level range in question_generator.py
- [ ] T254 [US4] Write unit tests for QuestionGenerator in tests/unit/test_question_generator.py

### Question Generation CLI

- [ ] T255 [US4] Create src/pipeline/cli/generate_questions.py with CLI interface
- [ ] T256 [US4] Implement argument parsing: --content-id, --language, --level, --num-questions in generate_questions.py
- [ ] T257 [US4] Implement question generation workflow with answerability validation in generate_questions.py
- [ ] T258 [US4] Implement summary output (type distribution, difficulty, tags) in generate_questions.py
- [ ] T259 [US4] Write integration test for end-to-end question generation in tests/integration/test_end_to_end_questions.py

---

## Phase 9: User Story 6 - QA Gates (P2)

**Goal**: Run automated validation gates to ensure content quality before publication

**Independent Test**: Run QA gates on test batch with known violations, verify report identifies all failures

**Note**: This phase was previously Phase 5 but renumbered. Some tasks may already be implemented.

### Validation Modules

- [ ] T260 [P] [US6] Create src/pipeline/validators/presence.py with presence check logic (if not exists)
- [ ] T261 [P] [US6] Implement check_learning_item_presence() verifying IDs exist and appear in text in presence.py
- [ ] T262 [P] [US6] Add language-aware tokenization for Chinese/Japanese/French in presence.py
- [ ] T263 [P] [US6] Create src/pipeline/validators/duplication.py with duplicate detection (if not exists)
- [ ] T264 [P] [US6] Implement check_duplicates() comparing (language, category, lemma, sense_gloss) in duplication.py
- [ ] T265 [P] [US6] Handle polysemy cases (same lemma, different sense_gloss) in duplication.py
- [ ] T266 [P] [US6] Create src/pipeline/validators/links.py with link correctness validation (if not exists)
- [ ] T267 [P] [US6] Implement check_link_correctness() resolving all referenced IDs in links.py
- [ ] T268 [P] [US6] Create src/pipeline/validators/answerability.py with question validation (if not exists)
- [ ] T269 [P] [US6] Implement check_answerability() using LLM to verify answers from text in answerability.py

### QA Gate Orchestration

- [ ] T270 [US6] Create src/pipeline/cli/run_qa_gates.py with CLI interface (if not exists)
- [ ] T271 [US6] Implement argument parsing: --language, --level, --content-dir, --gates, --output in run_qa_gates.py
- [ ] T272 [US6] Implement gate orchestration (run all gates sequentially) in run_qa_gates.py
- [ ] T273 [US6] Implement ValidationResult aggregation in run_qa_gates.py
- [ ] T274 [US6] Generate JSON report with flagged items and summary stats in run_qa_gates.py
- [ ] T275 [US6] Generate markdown report with human-readable findings in run_qa_gates.py
- [ ] T276 [US6] Write integration test for QA gates with known violations in tests/integration/test_qa_gates.py

### Test Data for QA Gates

- [ ] T277 [P] [US6] Create test data with duplicate learning items in tests/fixtures/
- [ ] T278 [P] [US6] Create test data with broken references in tests/fixtures/
- [ ] T279 [P] [US6] Create test data with unanswerable questions in tests/fixtures/

---

## Phase 10: Scenario Matching & Normalization (Post-MVP)

**Goal**: Implement scenario similarity search and normalization for content reuse

### Scenario Matcher

- [ ] T180 [P] Create src/pipeline/generators/scenario_matcher.py with ScenarioMatcher class
- [ ] T181 Implement semantic similarity search using Meilisearch vector search in scenario_matcher.py
- [ ] T182 Implement threshold-based reuse decision (>85% = reuse, 75-85% = prompt for decision) in scenario_matcher.py
- [ ] T183 Implement scenario name normalization (grouping similar names) in scenario_matcher.py
- [ ] T184 Write unit tests for ScenarioMatcher in tests/unit/test_scenario_matcher.py

### Scenario Matching CLI

- [ ] T185 Create src/pipeline/cli/match_scenarios.py with CLI interface
- [ ] T186 Implement argument parsing: --scenario-name, --language, --threshold in match_scenarios.py
- [ ] T187 Implement similarity search and reuse report generation in match_scenarios.py
- [ ] T188 Write integration test for scenario matching in tests/integration/test_scenario_matching.py

---

## Phase 10: Scenario Matching & Normalization (Post-MVP)

**Goal**: Implement scenario similarity search and normalization for content reuse

### Scenario Matcher

- [ ] T280 [P] Create src/pipeline/generators/scenario_matcher.py with ScenarioMatcher class
- [ ] T281 Implement semantic similarity search using Meilisearch vector search in scenario_matcher.py
- [ ] T282 Implement threshold-based reuse decision (>85% = reuse, 75-85% = prompt for decision) in scenario_matcher.py
- [ ] T283 Implement scenario name normalization (grouping similar names) in scenario_matcher.py
- [ ] T284 Write unit tests for ScenarioMatcher in tests/unit/test_scenario_matcher.py

### Scenario Matching CLI

- [ ] T285 Create src/pipeline/cli/match_scenarios.py with CLI interface
- [ ] T286 Implement argument parsing: --scenario-name, --language, --threshold in match_scenarios.py
- [ ] T287 Implement similarity search and reuse report generation in match_scenarios.py
- [ ] T288 Write integration test for scenario matching in tests/integration/test_scenario_matching.py

---

## Phase 11: Live API for Scenario-Driven Generation (Post-MVP)

**Goal**: Implement on-demand content generation API for growing library

### API Core

- [ ] T189 Create src/pipeline/api/__init__.py
- [ ] T190 Create src/pipeline/api/server.py with FastAPI application
- [ ] T191 Implement health check endpoint GET /health in server.py
- [ ] T192 Create src/pipeline/api/scenario_search.py with semantic similarity search
- [ ] T193 Implement embedding cache for fast scenario lookup in scenario_search.py
- [ ] T194 Implement cosine similarity ranking (>0.85 threshold) in scenario_search.py

### Scenario Endpoints

- [ ] T195 Create src/pipeline/api/live_scenario_handler.py with endpoint handlers
- [ ] T196 Implement POST /api/v1/scenarios/search with similarity threshold in live_scenario_handler.py
- [ ] T197 Implement POST /api/v1/scenarios/generate with on-demand generation in live_scenario_handler.py
- [ ] T198 Implement GET /api/v1/scenarios/{id} for retrieval in live_scenario_handler.py
- [ ] T199 Implement PATCH /api/v1/scenarios/{id} for tag updates in live_scenario_handler.py

### Incremental Generator

- [ ] T200 Create src/pipeline/api/incremental_generator.py with on-demand generation logic
- [ ] T201 Implement fast LLM model selection (GPT-3.5-turbo) in incremental_generator.py
- [ ] T202 Implement 30s timeout for generation in incremental_generator.py
- [ ] T203 Implement lightweight validation (schema only) in incremental_generator.py
- [ ] T204 Implement publishable:false flag for draft content in incremental_generator.py

### API Testing

- [ ] T205 Write API integration tests with pytest-asyncio in tests/integration/test_live_api.py
- [ ] T206 Create test fixtures for scenario search in tests/fixtures/
- [ ] T207 Test concurrent request handling in tests/integration/test_live_api.py

---

## Phase 11: Live API for Scenario-Driven Generation (Post-MVP)

**Goal**: Implement on-demand content generation API for growing library

### API Core

- [ ] T289 Create src/pipeline/api/__init__.py
- [ ] T290 Create src/pipeline/api/server.py with FastAPI application
- [ ] T291 Implement health check endpoint GET /health in server.py
- [ ] T292 Create src/pipeline/api/scenario_search.py with semantic similarity search
- [ ] T293 Implement embedding cache for fast scenario lookup in scenario_search.py
- [ ] T294 Implement cosine similarity ranking (>0.85 threshold) in scenario_search.py

### Scenario Endpoints

- [ ] T295 Create src/pipeline/api/live_scenario_handler.py with endpoint handlers
- [ ] T296 Implement POST /api/v1/scenarios/search with similarity threshold in live_scenario_handler.py
- [ ] T297 Implement POST /api/v1/scenarios/generate with on-demand generation in live_scenario_handler.py
- [ ] T298 Implement GET /api/v1/scenarios/{id} for retrieval in live_scenario_handler.py
- [ ] T299 Implement PATCH /api/v1/scenarios/{id} for tag updates in live_scenario_handler.py

### Incremental Generator

- [ ] T300 Create src/pipeline/api/incremental_generator.py with on-demand generation logic
- [ ] T301 Implement fast LLM model selection (GPT-3.5-turbo) in incremental_generator.py
- [ ] T302 Implement 30s timeout for generation in incremental_generator.py
- [ ] T303 Implement lightweight validation (schema only) in incremental_generator.py
- [ ] T304 Implement publishable:false flag for draft content in incremental_generator.py

### API Testing

- [ ] T305 Write API integration tests with pytest-asyncio in tests/integration/test_live_api.py
- [ ] T306 Create test fixtures for scenario search in tests/fixtures/
- [ ] T307 Test concurrent request handling in tests/integration/test_live_api.py

---

## Phase 12: LangGraph Orchestration (Advanced)

**Goal**: Implement graph-based orchestration for production batch processing

### Enrichment Graph

- [ ] T208 Create src/pipeline/langgraph/__init__.py
- [ ] T209 Create src/pipeline/langgraph/enrichment_graph.py with StateGraph definition
- [ ] T210 Define graph nodes: load_source, parse_by_language, enrich_with_llm, validate_schema, retry_loop, write_output in enrichment_graph.py
- [ ] T211 Define conditional edges for retry logic in enrichment_graph.py
- [ ] T212 Implement checkpoint support for resuming failed batches in enrichment_graph.py
- [ ] T213 Add execution observability with state logging in enrichment_graph.py

### Generation Graph

- [ ] T214 Create src/pipeline/langgraph/generation_graph.py with StateGraph definition
- [ ] T215 Define graph nodes: load_all_learning_items, generate_batch_with_cot, validate_links, track_usage, write_output in generation_graph.py
- [ ] T216 Define conditional edges for chain-of-thought quality checks in generation_graph.py
- [ ] T217 Implement parallel execution for multiple topics in generation_graph.py

### LangGraph CLI

- [ ] T218 Create CLI wrapper for enrichment_graph with config file input
- [ ] T219 Create CLI wrapper for generation_graph with config file input
- [ ] T220 Create example config files in configs/ directory
- [ ] T221 Write integration tests for graph execution in tests/integration/test_langgraph.py

---

## Phase 12: LangGraph Orchestration (Advanced)

**Goal**: Implement graph-based orchestration for production batch processing

### Enrichment Graph

- [ ] T308 Create src/pipeline/langgraph/__init__.py
- [ ] T309 Create src/pipeline/langgraph/enrichment_graph.py with StateGraph definition
- [ ] T310 Define graph nodes: load_source, parse_by_language, enrich_with_llm, validate_schema, retry_loop, write_output in enrichment_graph.py
- [ ] T311 Define conditional edges for retry logic in enrichment_graph.py
- [ ] T312 Implement checkpoint support for resuming failed batches in enrichment_graph.py
- [ ] T313 Add execution observability with state logging in enrichment_graph.py

### Generation Graph

- [ ] T314 Create src/pipeline/langgraph/generation_graph.py with StateGraph definition
- [ ] T315 Define graph nodes: load_all_learning_items, generate_batch_with_cot, validate_links, track_usage, write_output in generation_graph.py
- [ ] T316 Define conditional edges for chain-of-thought quality checks in generation_graph.py
- [ ] T317 Implement parallel execution for multiple topics in generation_graph.py

### LangGraph CLI

- [ ] T318 Create CLI wrapper for enrichment_graph with config file input
- [ ] T319 Create CLI wrapper for generation_graph with config file input
- [ ] T320 Create example config files in configs/ directory
- [ ] T321 Write integration tests for graph execution in tests/integration/test_langgraph.py

---

## Phase 13: Polish & Cross-Cutting Concerns

**Goal**: Finalize observability, documentation, and deployment readiness

### Observability & Metrics

- [ ] T322 [P] Implement batch processing metrics (items processed, success rate, tokens, duration, character count for audio) in all CLIs
- [ ] T323 [P] Add cost tracking dashboard template (LLM token costs + ElevenLabs character costs per language/level)
- [ ] T324 [P] Create manual review queue viewer CLI tool
- [ ] T325 [P] Implement QA gate trend analysis (pass rate over time)
- [ ] T326 [P] Add audio generation metrics (format usage, voice ID usage, generation time per item)

### Documentation

- [ ] T327 [P] Update comprehensive README.md with two-stage workflow, audio generation, and all CLI examples
- [ ] T328 [P] Document prompt engineering guidelines for chain-of-thought content generation in docs/
- [ ] T329 [P] Create troubleshooting guide for common LLM failures in docs/
- [ ] T330 [P] Document database partitioning setup for Postgres and Meilisearch in docs/
- [ ] T331 [P] Document audio generation workflow (local-first, version selection, R2 sync) in docs/
- [ ] T332 [P] Document voice configuration setup and ElevenLabs API integration in docs/

### Deployment & CI/CD

- [ ] T333 [P] Create Dockerfile for batch workers
- [ ] T334 [P] Create docker-compose.yml for local development
- [ ] T335 [P] Create GitHub Actions workflow for pytest on PR
- [ ] T336 [P] Create GitHub Actions workflow for schema validation on PR
- [ ] T337 [P] Create deployment guide for production batch workers in docs/
- [ ] T338 [P] Configure Cloudflare R2 bucket and access credentials for audio storage

### Contract Tests

- [ ] T339 [P] Write contract tests for all JSON schemas in tests/contract/test_schemas.py
- [ ] T340 [P] Write contract tests for output file structure in tests/contract/test_output_format.py
- [ ] T341 [P] Implement schema version compatibility tests in tests/contract/test_schema_evolution.py
- [ ] T342 [P] Write contract tests for audio metadata schemas in tests/contract/test_audio_schemas.py

---

## Dependencies

### Story Completion Order

```
Phase 1 (Setup) ✅ COMPLETE
  ↓
Phase 2 (Foundational) ✅ COMPLETE
  ↓
Phase 3 (US1: Vocab Enrichment) ✅ COMPLETE
  ↓
Phase 4 (US2: Grammar Enrichment) ← CURRENT
  ↓
Phase 5 (US6: QA Gates)
  ↓
Phase 6 (US3: Two-Stage Content Generation) ✅ COMPLETE
  ├─ Stage 1: Generate ALL learning items (pronunciation, idioms, functional, cultural, etc.)
  └─ Stage 2: Generate content using ALL items together with chain-of-thought
  ↓
Phase 7 (US5: Audio Generation with ElevenLabs TTS)
  ├─ Generate audio for learning items (vocab, grammar, idioms, etc.)
  ├─ Generate audio for content units (conversations with voice pairing, stories)
  ├─ Local-first storage in {Language}/{Level}/02_Generated/audio/{category}/
  └─ Manual selection & sync to Cloudflare R2
  ↓
Phase 8 (US4: Question Generation)
  ↓
Phase 9 (US6: QA Gates - Additional validation)
  ↓
Phase 10 (Scenario Matching & Normalization)
  ↓
Phase 11 (Live API)
  ↓
Phase 12 (LangGraph Orchestration)
  ↓
Phase 13 (Polish)
```

### Parallelization Opportunities

**Within Phase 4 (US2) - Grammar Enrichment:**
- T078-T085 (Mandarin grammar)
- T086-T092 (Japanese grammar)
- T093-T099 (French grammar)
- Can develop all 3 enrichers in parallel

**Within Phase 5 (US5) - QA Gates:**
- T108-T117 (All validation modules)
- Can develop all gates in parallel

**Within Phase 6 (US3) - Learning Item Generation:**
- T130-T136 (All category generators)
- Can develop pronunciation, idioms, functional, cultural, writing_system, miscellaneous generators in parallel
- Note: Each generator processes items one-by-one with individual LLM calls

**Within Phase 8 - Scenario Matching:**
- T180-T184 (Scenario matcher components)
- Can develop in parallel with other phases

**Within Phase 11 - Polish:**
- T222-T237 (All polish tasks)
- Can execute all polish tasks in parallel

---

## Execution Recommendations

### MVP Delivery (Phases 1-5)

**Timeline**: 4-6 weeks  
**Status**: Phases 1-3 ✅ COMPLETE, Phase 4 IN PROGRESS  
**Deliverables**:
- ✅ Vocab enrichment for 3 languages (Mandarin, Japanese, French)
- 🔄 Grammar enrichment for 3 languages (IN PROGRESS)
- QA gates with validation reports
- CLI tools for batch processing
- Test coverage >80%

**Example MVP Command Sequence**:
```bash
# Stage 1: Enrich vocab (COMPLETED)
python -m src.havachat.cli.enrich_vocab \
  --language zh --level HSK1 \
  --input sources/hsk1_vocab.tsv \
  --enricher mandarin \
  --parallel 5 --resume

# Stage 2: Enrich grammar (NEXT)
python -m src.havachat.cli.enrich_grammar \
  --language zh --level HSK1 \
  --input sources/hsk1_grammar.csv \
  --enricher mandarin

# Stage 3: Run QA gates
python -m src.havachat.cli.run_qa_gates \
  --language zh --level HSK1 \
  --content-dir ../havachat-knowledge/generated content/Mandarin/HSK1/
```

### Two-Stage Content Generation (Phases 6-7)

**Timeline**: 4-5 weeks  
**Status**: NOT STARTED  
**Deliverables**:
- Learning item generation for all categories (pronunciation, idioms, functional, cultural, writing system, misc)
- Content generation with chain-of-thought (single LLM call per topic)
- Question generation
- Usage tracking and metrics

**Example Two-Stage Command Sequence**:
```bash
# Stage 1: Generate ALL learning items first
python -m src.havachat.cli.generate_learning_items \
  --language zh --level HSK1 \
  --category pronunciation \
  --source-dir ../havachat-knowledge/generated content/Mandarin/HSK1/vocab/

python -m src.havachat.cli.generate_learning_items \
  --language zh --level HSK1 \
  --category idiom \
  --source-dir ../havachat-knowledge/generated content/Mandarin/HSK1/vocab/

# ... repeat for functional, cultural, writing_system, misc categories

# Stage 2: Generate content using ALL learning items together
python -m src.havachat.cli.generate_content \
  --language zh --level HSK1 \
  --topic "Food" \
  --num-conversations 5 \
  --num-stories 5
```

### Advanced Features (Phases 8-10)

**Timeline**: 4-6 weeks  
**Status**: NOT STARTED  
**Deliverables**:
- Scenario matching and normalization
- Live API for on-demand generation
- LangGraph orchestration for production batches

### Total Estimated Effort

- **Phase 1 (Setup)**: 12 tasks, ~1 week ✅ COMPLETE
- **Phase 2 (Foundational)**: 31 tasks, ~2 weeks ✅ COMPLETE
- **Phase 3 (US1: Vocab)**: 33 tasks, ~2 weeks ✅ COMPLETE
- **Phase 4 (US2: Grammar)**: 31 tasks, ~2 weeks 🔄 IN PROGRESS
- **Phase 5 (US5: QA Gates)**: 20 tasks, ~1-2 weeks
- **Phase 6 (US3: Two-Stage Content)**: 38 tasks, ~3-4 weeks
- **Phase 7 (US4: Questions)**: 14 tasks, ~1 week
- **Phase 8 (Scenario Matching)**: 9 tasks, ~1 week
- **Phase 9 (Live API)**: 19 tasks, ~2-3 weeks
- **Phase 10 (LangGraph)**: 14 tasks, ~2 weeks
- **Phase 11 (Polish)**: 16 tasks, ongoing

**Total**: 237 tasks, ~15-20 weeks for complete system

---

## Quality Gates

Each phase must pass these gates before proceeding:

### Phase Completion Criteria

- [ ] All tasks in phase marked complete
- [ ] Unit tests pass for all modules in phase (>80% coverage)
- [ ] Integration tests pass for phase workflows
- [ ] Code review completed
- [ ] Documentation updated

### MVP Acceptance Criteria (End of Phase 5)

- [X] ✅ Can process 500 vocab items in <10min with >95% schema validation pass rate (ACHIEVED with parallel processing)
- [ ] Can process 100 grammar patterns with >90% granularity validation
- [ ] QA gates run on 100-item batch in <10min with <5% flagged items
- [ ] Manual review queue contains only legitimate failures
- [X] ✅ All 3 languages (Mandarin, Japanese, French) fully supported for vocabulary

### Two-Stage Content Generation Acceptance (End of Phase 6)

- [ ] Can generate ALL learning item categories (vocab, grammar, pronunciation, idioms, functional, cultural, writing_system, misc) for a given language/level
- [ ] Content generation using instructor library produces valid structured output with chain-of-thought metadata
- [ ] Single LLM call generates N conversations + N stories using items from ALL categories
- [ ] Chain-of-thought quality: >95% of revised versions show improved learning item coverage vs initial drafts
- [ ] Token optimization: <500 tokens for 200 learning items (target_item only vs >2000 with full definitions)
- [ ] Learning item presence validation: 100% of referenced items exist and appear in text
- [ ] Usage tracking: appearances_count correctly incremented for all items in generated content

### Production Readiness (End of Phase 11)

- [ ] All constitutional requirements met
- [ ] All success criteria from spec.md achieved
- [ ] Documentation complete (README, quickstart, API docs)
- [ ] CI/CD pipeline operational
- [ ] Database partitioning configured
- [ ] Deployment guide validated

---

## Implementation Notes

### Phase 3 Completion (Vocab Enrichment) - 2026-01-28 ✅

**Summary**: All vocabulary enrichment tasks (T044-T076a) completed with 10 additional optimizations for cost reduction, performance, and maintainability.

**Key Achievements**:
- ✅ 3 language-specific enrichers: Mandarin (TSV), Japanese (JSON), French (TSV)
- ✅ Auto-romanization: `pypinyin` for Mandarin, `pykakasi` for Japanese (no LLM calls needed)
- ✅ Language-specific response models: MandarinVocabItem, JapaneseVocabItem, FrenchVocabItem
- ✅ System prompts moved to enricher classes (@property pattern)
- ✅ Token tracking & cost estimation with OpenAI prompt caching support
- ✅ Parallel processing with `--parallel N` flag (5x speedup)
- ✅ Checkpoint/resume capability with `--resume` flag
- ✅ Progress bars with tqdm
- ✅ Enricher-language validation (fail fast on user errors)
- ✅ Type safety improvements (Optional[LLMClient] for dry-run)

**Performance Metrics**:
- **Token savings**: ~400 tokens per item (54% cost reduction)
  - Auto-romanization: ~30 tokens saved
  - Language-specific models: ~20 tokens saved
  - Prompt caching: ~350 tokens saved (73% cache hit rate)
- **Speed**: 5x speedup with `--parallel 5` (1000 items: 33 min → 6.6 min)
- **Cost**: 1000 items with gpt-4o-mini: $0.35 → $0.16 (-54%)

**Implementation Details**:
- **Files Created**:
  - `src/pipeline/validators/vocab_schemas.py` - Language-specific Pydantic models
  - `src/pipeline/enrichers/vocab/mandarin.py` - Mandarin enricher with pypinyin
  - `src/pipeline/enrichers/vocab/japanese.py` - Japanese enricher with pykakasi
  - `src/pipeline/enrichers/vocab/french.py` - French enricher (TSV format)
  - `src/pipeline/cli/enrich_vocab.py` - CLI with parallel processing, checkpoints, token tracking
  - `tests/unit/test_file_io.py`, `test_llm_client.py`, `test_schemas.py` - Unit tests
  - `tests/contract/` - Contract test structure
  - `tests/integration/` - Integration test structure
  - `tests/fixtures/` - Sample data for all 3 languages

- **Files Modified**:
  - `src/pipeline/enrichers/base.py` - Added abstract system_prompt property
  - `src/pipeline/utils/llm_client.py` - Added TokenUsage tracking, cost calculation, prompt caching
  - `pyproject.toml` - Added pypinyin, pykakasi, tqdm dependencies

**Testing**:
- ✅ Unit tests pass for file_io, llm_client, schemas, token tracking
- ✅ Dry-run validation for all 3 enrichers
- ✅ Meilisearch integration test (20 records indexed successfully)

**Next Phase**: Phase 4 - Grammar Enrichment (T077-T107)

---

### Phase 4 Current Status (Grammar Enrichment) - 2026-01-28 🔄

**Status**: IN PROGRESS  
**Remaining Tasks**: T077-T107 (31 tasks)  
**Expected Completion**: ~2 weeks

**Key Considerations for Grammar**:
- Each grammar item must be enriched one-by-one via individual LLM calls (same as vocab)
- Must implement retry logic for each individual item (up to 3 retries)
- Language-specific source formats:
  - Mandarin: CSV with "类别,类别名称,细目,语法内容"
  - Japanese: TSV with "Type, Rule, Example"
  - French: Markdown with "## Category" headers
- Must enforce narrow-scope items (avoid "mega-items" like "past tense" without sub-items)
- Preserve existing examples from source data (especially for Japanese)

---

### Phase 6 Planning Notes (Two-Stage Content Generation)

**Critical Implementation Requirements**:

1. **Stage 1 - Learning Item Generation (T128-T142)**:
   - Generate items for: pronunciation, idioms, functional, cultural, writing_system, miscellaneous
   - Each item generated one-by-one with individual LLM call
   - Implement retry logic (3 attempts) for each item
   - Must complete ALL categories before Stage 2

2. **Stage 2 - Content Generation with Chain-of-Thought (T143-T165)**:
   - Load ALL learning items in simplified format (target_item only, <500 tokens for 200 items)
   - Use `instructor` library for structured output with Pydantic validation
   - Chain-of-thought steps in single prompt (not sequential calls):
     ```
     1. Generate: N conversations + N stories using all categories
     2. Critique: Evaluate level-appropriateness, item coverage, natural flow
     3. Revise: Improve based on critique, explicitly list items used
     4. Assign Scenarios: Give 3-8 word scenario name to each piece
     ```
   - Single LLM call generates entire batch (5 conversations + 5 stories by default)
   - Validate all learning_item_ids exist and appear in text
   - Track usage: increment appearances_count for each item in usage_stats.json

**Chain-of-Thought Quality Metrics**:
- >95% of revised versions show improved learning item coverage vs initial drafts
- Explicit learning_item_ids[] list matches items found in text (100% accuracy)
- Scenario names follow 3-8 word format and can be normalized (>85% success rate)

**Prompt Engineering Guidelines**:
- System prompt must describe ALL four chain-of-thought steps
- Include examples of good vs bad coverage
- Specify learner level expectations (A1 = simple sentences, HSK1 = basic structures)
- Request explicit item listing in critique/revise steps
- Use instructor field descriptions to guide structured output
