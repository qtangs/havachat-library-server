# Task Breakdown: Pre-generation Pipeline for Learning Content

**Feature**: Pre-generation Pipeline  
**Branch**: `001-pregen-pipeline`  
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)  
**Generated**: 2026-01-26

## Task Format

```
- [ ] [TaskID] [P] [Story] Description with file path
```

- **TaskID**: Sequential number (T001, T002, ...)
- **[P]**: Parallelizable marker (different files, no dependencies)
- **[Story]**: User story label (US1, US2, ...) for story phases only
- **Description**: Clear action with exact file path

## Implementation Strategy

**MVP Scope**: User Story 1 + User Story 2 (vocab and grammar enrichment only)  
**Incremental Delivery**: Each user story is independently testable and deliverable  
**Priority Order**: P1 (US1, US2) → P2 (US5, US3) → P3 (US4)

---

## Phase 1: Setup & Project Initialization

**Goal**: Bootstrap project structure, install dependencies, configure development environment

- [ ] T001 Initialize Python 3.14 project with uv package manager in project root
- [ ] T002 Install core dependencies via uv: langgraph>=1.0.7, instructor>=1.0.0, pydantic>=2.0.0
- [ ] T003 Install data processing dependencies: pandas>=2.0.0, docling>=2.70.0
- [ ] T004 Install testing dependencies: pytest>=8.0.0, black>=24.8.0
- [ ] T005 Install ML dependencies: sentence-transformers, openai (or anthropic)
- [ ] T006 Create src/pipeline/__init__.py with version metadata
- [ ] T007 Create src/pipeline/utils/__init__.py for shared utilities
- [ ] T008 Create tests/ directory structure: unit/, contract/, integration/, fixtures/
- [ ] T009 Configure pytest.ini with test discovery patterns and markers
- [ ] T010 Create .env.template with required environment variables (OPENAI_API_KEY, HAVACHAT_KNOWLEDGE_PATH)
- [ ] T011 Create README.md with project overview and setup instructions
- [ ] T012 Verify havachat-knowledge repository access and directory structure

---

## Phase 2: Foundational Infrastructure (Blocking Prerequisites)

**Goal**: Implement shared components required by all pipeline stages

### Pydantic Schemas & Validation

- [ ] T013 [P] Create src/pipeline/validators/__init__.py
- [ ] T014 [P] Define LevelSystem, Category, ContentType, SegmentType enums in src/pipeline/validators/schema.py
- [ ] T015 [P] Define LearningItem Pydantic model with all 12 categories in src/pipeline/validators/schema.py
- [ ] T016 [P] Define ContentUnit and Segment Pydantic models in src/pipeline/validators/schema.py
- [ ] T017 [P] Define Question, MCQOption, QuestionType Pydantic models in src/pipeline/validators/schema.py
- [ ] T018 [P] Define Topic, Scenario (with rich tagging), UsageStats, ValidationReport models in src/pipeline/validators/schema.py
- [ ] T019 [P] Write unit tests for all Pydantic models in tests/unit/test_schemas.py

### LLM Client & Instructor Integration

- [ ] T020 Create src/pipeline/utils/llm_client.py with Instructor-wrapped OpenAI client
- [ ] T021 Implement retry logic (3 attempts with exponential backoff) in llm_client.py
- [ ] T022 Implement structured response generation with Pydantic model validation in llm_client.py
- [ ] T023 Add request/response logging (prompt hash, tokens, latency) in llm_client.py
- [ ] T024 Write unit tests for llm_client with mocked API responses in tests/unit/test_llm_client.py

### File I/O & Data Handling

- [ ] T025 [P] Create src/pipeline/utils/file_io.py with JSON read/write functions
- [ ] T026 [P] Implement TSV/CSV parsing functions in file_io.py
- [ ] T027 [P] Implement markdown parsing helper in file_io.py
- [ ] T028 [P] Add directory creation with language/level structure in file_io.py
- [ ] T029 [P] Write unit tests for file I/O functions in tests/unit/test_file_io.py

### Logging & Observability

- [ ] T030 Create src/pipeline/utils/logging_config.py with structured JSON logging
- [ ] T031 Implement JsonFormatter for log records in logging_config.py
- [ ] T032 Add context manager for logging pipeline stages in logging_config.py
- [ ] T033 Configure log levels and output destinations in logging_config.py

### Semantic Similarity for Scenario Reuse

- [ ] T034 Create src/pipeline/utils/similarity.py with SentenceTransformer initialization
- [ ] T035 Implement embedding generation function in similarity.py
- [ ] T036 Implement cosine similarity comparison function in similarity.py
- [ ] T037 Implement scenario embedding cache (load/save) in similarity.py
- [ ] T038 Write unit tests for similarity functions in tests/unit/test_similarity.py

### Base Enricher Abstract Class

- [ ] T039 Create src/pipeline/enrichers/__init__.py
- [ ] T040 Create src/pipeline/enrichers/base.py with BaseEnricher abstract class
- [ ] T041 Define abstract methods: parse_source(), detect_missing_fields(), build_prompt(), validate_output() in base.py
- [ ] T042 Implement common retry loop logic in BaseEnricher
- [ ] T043 Implement manual review queue writing in BaseEnricher

---

## Phase 3: User Story 1 - Vocab Enrichment (P1)

**Goal**: Import and enrich official vocabulary lists for Mandarin, Japanese, French

**Independent Test**: Run enricher on sample vocab files, verify JSON output with all required fields

### Mandarin Vocab Enricher

- [ ] T044 [P] [US1] Create src/pipeline/enrichers/vocab/__init__.py
- [ ] T045 [P] [US1] Create src/pipeline/enrichers/vocab/mandarin.py with MandarinVocabEnricher class
- [ ] T046 [US1] Implement parse_source() for TSV with "Word, Part of Speech" columns in mandarin.py
- [ ] T047 [US1] Implement detect_missing_fields() checking for pinyin, explanation_en, examples in mandarin.py
- [ ] T048 [US1] Create src/pipeline/prompts/mandarin/vocab_prompts.py with Chinese-specific prompts
- [ ] T049 [US1] Implement build_prompt() using prompts from vocab_prompts.py in mandarin.py
- [ ] T050 [US1] Implement validate_output() enforcing romanization presence in mandarin.py
- [ ] T051 [US1] Add polysemy detection and sense_gloss_en generation in mandarin.py
- [ ] T052 [US1] Write unit tests for MandarinVocabEnricher in tests/unit/test_mandarin_vocab_enricher.py

### Japanese Vocab Enricher

- [ ] T053 [P] [US1] Create src/pipeline/enrichers/vocab/japanese.py with JapaneseVocabEnricher class
- [ ] T054 [US1] Implement parse_source() for JSON with {word, meaning, furigana, romaji, level} in japanese.py
- [ ] T055 [US1] Implement detect_missing_fields() preserving existing furigana/romaji in japanese.py
- [ ] T056 [US1] Create src/pipeline/prompts/japanese/vocab_prompts.py with Japanese-specific prompts
- [ ] T057 [US1] Implement build_prompt() for missing fields only in japanese.py
- [ ] T058 [US1] Implement validate_output() preserving source data in japanese.py
- [ ] T059 [US1] Write unit tests for JapaneseVocabEnricher in tests/unit/test_japanese_vocab_enricher.py

### French Vocab Enricher

- [ ] T060 [P] [US1] Create src/pipeline/enrichers/vocab/french.py with FrenchVocabEnricher class
- [ ] T061 [US1] Implement parse_source() for CSV with "Mot, Définition, Exemple" columns in french.py
- [ ] T062 [US1] Implement detect_missing_fields() preserving existing definitions in french.py
- [ ] T063 [US1] Create src/pipeline/prompts/french/vocab_prompts.py with French-specific prompts
- [ ] T064 [US1] Implement build_prompt() using existing definitions as base in french.py
- [ ] T065 [US1] Implement validate_output() without romanization requirement in french.py
- [ ] T066 [US1] Write unit tests for FrenchVocabEnricher in tests/unit/test_french_vocab_enricher.py

### Vocab Enrichment CLI

- [ ] T067 [US1] Create src/pipeline/cli/__init__.py
- [ ] T068 [US1] Create src/pipeline/cli/enrich_vocab.py with CLI interface
- [ ] T069 [US1] Implement argument parsing: --language, --level, --input, --enricher, --output in enrich_vocab.py
- [ ] T070 [US1] Implement batch processing loop with progress reporting in enrich_vocab.py
- [ ] T071 [US1] Implement summary statistics (success rate, LLM tokens, duration) in enrich_vocab.py
- [ ] T072 [US1] Add --dry-run and --max-items flags for testing in enrich_vocab.py
- [ ] T073 [US1] Write integration test for end-to-end vocab enrichment in tests/integration/test_end_to_end_vocab.py

### Test Fixtures

- [ ] T074 [P] [US1] Create tests/fixtures/mandarin_vocab_sample.tsv with 10 sample words
- [ ] T075 [P] [US1] Create tests/fixtures/japanese_vocab_sample.json with 10 sample words
- [ ] T076 [P] [US1] Create tests/fixtures/french_vocab_sample.csv with 10 sample words

---

## Phase 4: User Story 2 - Grammar Enrichment (P1)

**Goal**: Import and enrich official grammar lists for Mandarin, Japanese, French

**Independent Test**: Run enricher on sample grammar files, verify narrow-scope items without "mega-items"

### Mandarin Grammar Enricher

- [ ] T077 [P] [US2] Create src/pipeline/enrichers/grammar/__init__.py
- [ ] T078 [P] [US2] Create src/pipeline/enrichers/grammar/mandarin.py with MandarinGrammarEnricher class
- [ ] T079 [US2] Implement parse_source() for CSV with "类别,类别名称,细目,语法内容" columns in mandarin.py
- [ ] T080 [US2] Implement detect_missing_fields() checking for explanation_en, examples in mandarin.py
- [ ] T081 [US2] Create src/pipeline/prompts/mandarin/grammar_prompts.py with grammar-specific prompts
- [ ] T082 [US2] Implement build_prompt() with granularity instructions (avoid mega-items) in mandarin.py
- [ ] T083 [US2] Implement validate_output() with granularity checks in mandarin.py
- [ ] T084 [US2] Add sub-item breakdown logic for broad patterns in mandarin.py
- [ ] T085 [US2] Write unit tests for MandarinGrammarEnricher in tests/unit/test_mandarin_grammar_enricher.py

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

- [ ] T100 [US2] Create src/pipeline/cli/enrich_grammar.py with CLI interface
- [ ] T101 [US2] Implement argument parsing: --language, --level, --input, --enricher, --output in enrich_grammar.py
- [ ] T102 [US2] Implement batch processing with granularity warnings in enrich_grammar.py
- [ ] T103 [US2] Implement summary statistics reporting in enrich_grammar.py
- [ ] T104 [US2] Write integration test for end-to-end grammar enrichment in tests/integration/test_end_to_end_grammar.py

### Test Fixtures

- [ ] T105 [P] [US2] Create tests/fixtures/mandarin_grammar_sample.csv with 10 sample patterns
- [ ] T106 [P] [US2] Create tests/fixtures/japanese_grammar_sample.tsv with 10 sample patterns
- [ ] T107 [P] [US2] Create tests/fixtures/french_grammar_sample.md with 10 sample patterns

---

## Phase 5: User Story 5 - QA Gates (P2)

**Goal**: Run automated validation gates to ensure content quality before publication

**Independent Test**: Run QA gates on test batch with known violations, verify report identifies all failures

### Validation Modules

- [ ] T108 [P] [US5] Create src/pipeline/validators/presence.py with presence check logic
- [ ] T109 [P] [US5] Implement check_learning_item_presence() verifying IDs exist and appear in text in presence.py
- [ ] T110 [P] [US5] Add language-aware tokenization for Chinese/Japanese/French in presence.py
- [ ] T111 [P] [US5] Create src/pipeline/validators/duplication.py with duplicate detection
- [ ] T112 [P] [US5] Implement check_duplicates() comparing (language, category, lemma, sense_gloss_en) in duplication.py
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

## Phase 6: User Story 3 - Content Generation (P2)

**Goal**: Generate conversations/stories with explicit learning item links

**Independent Test**: Generate content from scenario, verify all learning_item_ids exist and appear in text

### Content Generator

- [ ] T128 [P] [US3] Create src/pipeline/generators/__init__.py
- [ ] T129 [US3] Create src/pipeline/generators/content.py with ContentGenerator class
- [ ] T130 [US3] Implement scenario similarity search using embeddings in content.py
- [ ] T131 [US3] Implement reuse decision logic (>85% = reuse, 75-85% = prompt ops) in content.py
- [ ] T132 [US3] Implement learning item selection (language, level, topic/scenario relevance) in content.py
- [ ] T133 [US3] Implement item distribution (60% vocab, 30% grammar, 10% other) in content.py
- [ ] T134 [US3] Implement conversation generation with 6-10 turns in content.py
- [ ] T135 [US3] Implement story generation with 3-8 paragraphs in content.py
- [ ] T136 [US3] Implement segment creation with learning_item_ids in content.py
- [ ] T137 [US3] Implement linking validation (all IDs exist and appear in text) in content.py
- [ ] T138 [US3] Implement usage count tracking in metadata file in content.py
- [ ] T139 [US3] Write unit tests for ContentGenerator in tests/unit/test_content_generator.py

### Content Generation CLI

- [ ] T140 [US3] Create src/pipeline/cli/generate_content.py with CLI interface
- [ ] T141 [US3] Implement argument parsing: --language, --level, --type, --topic, --scenario, --turns in generate_content.py
- [ ] T142 [US3] Implement content generation workflow with validation in generate_content.py
- [ ] T143 [US3] Implement summary output (segments, word count, linked items) in generate_content.py
- [ ] T144 [US3] Write integration test for end-to-end content generation in tests/integration/test_end_to_end_content.py

---

## Phase 7: User Story 4 - Question Generation (P3)

**Goal**: Generate comprehension questions for content units

**Independent Test**: Generate questions from conversation, verify answerability and type distribution

### Question Generator

- [ ] T145 [P] [US4] Create src/pipeline/generators/questions.py with QuestionGenerator class
- [ ] T146 [US4] Implement question type distribution (50-60% MCQ, 20-30% T/F, 20% short answer) in questions.py
- [ ] T147 [US4] Implement cognitive level distribution (40% detail, 30% inference, 30% main idea) in questions.py
- [ ] T148 [US4] Implement MCQ generation with 4 options (1 correct, 3 distractors) in questions.py
- [ ] T149 [US4] Implement true/false generation in questions.py
- [ ] T150 [US4] Implement short answer generation in questions.py
- [ ] T151 [US4] Implement rationale generation explaining learning value in questions.py
- [ ] T152 [US4] Implement difficulty tagging within content level range in questions.py
- [ ] T153 [US4] Write unit tests for QuestionGenerator in tests/unit/test_question_generator.py

### Question Generation CLI

- [ ] T154 [US4] Create src/pipeline/cli/generate_questions.py with CLI interface
- [ ] T155 [US4] Implement argument parsing: --content-id, --language, --level, --num-questions in generate_questions.py
- [ ] T156 [US4] Implement question generation workflow with answerability validation in generate_questions.py
- [ ] T157 [US4] Implement summary output (type distribution, difficulty, tags) in generate_questions.py
- [ ] T158 [US4] Write integration test for end-to-end question generation in tests/integration/test_end_to_end_questions.py

---

## Phase 8: Other Categories Generation (Post-MVP)

**Goal**: Generate pronunciation, idiom, functional, cultural learning items from vocab/grammar

### Base Generator for LLM-Generated Categories

- [ ] T159 [P] Create src/pipeline/enrichers/other_categories/__init__.py
- [ ] T160 Create src/pipeline/enrichers/other_categories/base_generator.py with BaseCategoryGenerator class
- [ ] T161 Implement analyze_source_items() extracting patterns from vocab/grammar in base_generator.py
- [ ] T162 Implement generate_category_items() with category-specific prompts in base_generator.py
- [ ] T163 Implement deduplication logic in base_generator.py

### Specific Category Generators

- [ ] T164 [P] Create src/pipeline/enrichers/other_categories/pronunciation.py from vocab (tone pairs, initials, finals)
- [ ] T165 [P] Create src/pipeline/enrichers/other_categories/idiom.py from vocab phrases
- [ ] T166 [P] Create src/pipeline/enrichers/other_categories/functional.py from grammar patterns
- [ ] T167 [P] Create src/pipeline/enrichers/other_categories/cultural.py from vocab/scenario context
- [ ] T168 [P] Create src/pipeline/enrichers/other_categories/writing_system.py for character-based languages

### Other Categories CLI

- [ ] T169 Create src/pipeline/cli/generate_other_categories.py with CLI interface
- [ ] T170 Implement argument parsing: --language, --level, --category, --source-items, --output in generate_other_categories.py
- [ ] T171 Implement batch generation workflow in generate_other_categories.py
- [ ] T172 Write integration tests for other category generation in tests/integration/test_other_categories.py

---

## Phase 9: Live API for Scenario-Driven Generation (Post-MVP)

**Goal**: Implement on-demand content generation API for growing library

### API Core

- [ ] T173 Create src/pipeline/api/__init__.py
- [ ] T174 Create src/pipeline/api/server.py with FastAPI application
- [ ] T175 Implement health check endpoint GET /health in server.py
- [ ] T176 Create src/pipeline/api/scenario_search.py with semantic similarity search
- [ ] T177 Implement embedding cache for fast scenario lookup in scenario_search.py
- [ ] T178 Implement cosine similarity ranking (>0.85 threshold) in scenario_search.py

### Scenario Endpoints

- [ ] T179 Create src/pipeline/api/live_scenario_handler.py with endpoint handlers
- [ ] T180 Implement POST /api/v1/scenarios/search with similarity threshold in live_scenario_handler.py
- [ ] T181 Implement POST /api/v1/scenarios/generate with on-demand generation in live_scenario_handler.py
- [ ] T182 Implement GET /api/v1/scenarios/{id} for retrieval in live_scenario_handler.py
- [ ] T183 Implement PATCH /api/v1/scenarios/{id} for tag updates in live_scenario_handler.py

### Incremental Generator

- [ ] T184 Create src/pipeline/api/incremental_generator.py with on-demand generation logic
- [ ] T185 Implement fast LLM model selection (GPT-3.5-turbo) in incremental_generator.py
- [ ] T186 Implement 30s timeout for generation in incremental_generator.py
- [ ] T187 Implement lightweight validation (schema only) in incremental_generator.py
- [ ] T188 Implement publishable:false flag for draft content in incremental_generator.py

### API Testing

- [ ] T189 Write API integration tests with pytest-asyncio in tests/integration/test_live_api.py
- [ ] T190 Create test fixtures for scenario search in tests/fixtures/
- [ ] T191 Test concurrent request handling in tests/integration/test_live_api.py

---

## Phase 10: LangGraph Orchestration (Advanced)

**Goal**: Implement graph-based orchestration for production batch processing

### Enrichment Graph

- [ ] T192 Create src/pipeline/langgraph/__init__.py
- [ ] T193 Create src/pipeline/langgraph/enrichment_graph.py with StateGraph definition
- [ ] T194 Define graph nodes: load_source, parse_by_language, enrich_with_llm, validate_schema, retry_loop, write_output in enrichment_graph.py
- [ ] T195 Define conditional edges for retry logic in enrichment_graph.py
- [ ] T196 Implement checkpoint support for resuming failed batches in enrichment_graph.py
- [ ] T197 Add execution observability with state logging in enrichment_graph.py

### Generation Graph

- [ ] T198 Create src/pipeline/langgraph/generation_graph.py with StateGraph definition
- [ ] T199 Define graph nodes: check_similarity, reuse_existing, generate_new, link_items, validate_links, write_output in generation_graph.py
- [ ] T200 Define conditional edges for reuse decision in generation_graph.py
- [ ] T201 Implement parallel execution for multiple content units in generation_graph.py

### LangGraph CLI

- [ ] T202 Create CLI wrapper for enrichment_graph with config file input
- [ ] T203 Create CLI wrapper for generation_graph with config file input
- [ ] T204 Create example config files in configs/ directory
- [ ] T205 Write integration tests for graph execution in tests/integration/test_langgraph.py

---

## Phase 11: Polish & Cross-Cutting Concerns

**Goal**: Finalize observability, documentation, and deployment readiness

### Observability & Metrics

- [ ] T206 [P] Implement batch processing metrics (items processed, success rate, tokens, duration) in all CLIs
- [ ] T207 [P] Add cost tracking dashboard template (LLM token costs per language/level)
- [ ] T208 [P] Create manual review queue viewer CLI tool
- [ ] T209 [P] Implement QA gate trend analysis (pass rate over time)

### Documentation

- [ ] T210 [P] Create comprehensive README.md with all CLI examples
- [ ] T211 [P] Document prompt engineering guidelines for new languages in docs/
- [ ] T212 [P] Create troubleshooting guide for common LLM failures in docs/
- [ ] T213 [P] Document database partitioning setup for Postgres and Meilisearch in docs/

### Deployment & CI/CD

- [ ] T214 [P] Create Dockerfile for batch workers
- [ ] T215 [P] Create docker-compose.yml for local development
- [ ] T216 [P] Create GitHub Actions workflow for pytest on PR
- [ ] T217 [P] Create GitHub Actions workflow for schema validation on PR
- [ ] T218 [P] Create deployment guide for production batch workers in docs/

### Contract Tests

- [ ] T219 [P] Write contract tests for all JSON schemas in tests/contract/test_schemas.py
- [ ] T220 [P] Write contract tests for output file structure in tests/contract/test_output_format.py
- [ ] T221 [P] Implement schema version compatibility tests in tests/contract/test_schema_evolution.py

---

## Dependencies

### Story Completion Order

```
Phase 1 (Setup)
  ↓
Phase 2 (Foundational) 
  ↓
Phase 3 (US1: Vocab Enrichment) ──┐
  ↓                                │
Phase 4 (US2: Grammar Enrichment) ─┤
  ↓                                │
Phase 5 (US5: QA Gates) ───────────┘  (can validate vocab+grammar immediately)
  ↓
Phase 6 (US3: Content Generation)  (depends on US1+US2)
  ↓
Phase 7 (US4: Question Generation) (depends on US3)
  ↓
Phase 8 (Other Categories)         (depends on US1+US2)
  ↓
Phase 9 (Live API)                 (depends on US1-US4)
  ↓
Phase 10 (LangGraph)               (optional enhancement)
  ↓
Phase 11 (Polish)                  (ongoing)
```

### Parallelization Opportunities

**Within Phase 3 (US1):**
- T045-T052 (Mandarin enricher)
- T053-T059 (Japanese enricher)
- T060-T066 (French enricher)
- Can develop all 3 enrichers in parallel

**Within Phase 4 (US2):**
- T078-T085 (Mandarin grammar)
- T086-T092 (Japanese grammar)
- T093-T099 (French grammar)
- Can develop all 3 enrichers in parallel

**Within Phase 5 (US5):**
- T108-T117 (All validation modules)
- Can develop all gates in parallel

**Within Phase 8:**
- T164-T168 (All category generators)
- Can develop all generators in parallel

**Within Phase 11:**
- T206-T221 (All polish tasks)
- Can execute all polish tasks in parallel

---

## Execution Recommendations

### MVP Delivery (Phases 1-5)

**Timeline**: 4-6 weeks  
**Deliverables**:
- ✅ Vocab enrichment for 3 languages
- ✅ Grammar enrichment for 3 languages
- ✅ QA gates with validation reports
- ✅ CLI tools for batch processing
- ✅ Test coverage >80%

**Example MVP Command Sequence**:
```bash
# Enrich Mandarin HSK1 vocab
python -m src.pipeline.cli.enrich_vocab --language zh --level HSK1 --input hsk1_vocab.tsv --enricher mandarin

# Enrich Mandarin HSK1 grammar
python -m src.pipeline.cli.enrich_grammar --language zh --level HSK1 --input hsk1_grammar.csv --enricher mandarin

# Run QA gates
python -m src.pipeline.cli.run_qa_gates --language zh --level HSK1 --content-dir ../havachat-knowledge/generated content/Mandarin/HSK1/
```

### Incremental Expansion (Phases 6-7)

**Timeline**: 2-3 weeks  
**Deliverables**:
- ✅ Content generation (conversations/stories)
- ✅ Question generation
- ✅ End-to-end pipeline from vocab → content → questions

### Advanced Features (Phases 8-10)

**Timeline**: 4-6 weeks  
**Deliverables**:
- ✅ Other category generation (pronunciation, idioms, etc.)
- ✅ Live API for on-demand generation
- ✅ LangGraph orchestration

### Total Estimated Effort

- **MVP (Phases 1-5)**: 221 tasks, ~4-6 weeks
- **Full Pipeline (Phases 1-7)**: 158 additional tasks, ~2-3 weeks
- **Complete System (Phases 1-11)**: 221 tasks total, ~10-15 weeks

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

- [ ] Can process 500 vocab items in <30min with >95% schema validation pass rate
- [ ] Can process 100 grammar patterns with >90% granularity validation
- [ ] QA gates run on 100-item batch in <10min with <5% flagged items
- [ ] Manual review queue contains only legitimate failures
- [ ] All 3 languages (Mandarin, Japanese, French) fully supported

### Production Readiness (End of Phase 11)

- [ ] All constitutional requirements met
- [ ] All success criteria from spec.md achieved
- [ ] Documentation complete (README, quickstart, API docs)
- [ ] CI/CD pipeline operational
- [ ] Database partitioning configured
- [ ] Deployment guide validated

---

**Next Steps**: Begin Phase 1 (Setup) by initializing the Python project with uv and installing core dependencies.
