# Implementation Plan: Pre-generation Pipeline for Learning Content

**Branch**: `001-pregen-pipeline` | **Date**: 2026-01-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-pregen-pipeline/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build a two-tier content generation system: (1) **Batch pipeline** using Python scripts orchestrated with LangGraph for manual vocab/grammar enrichment from official sources, then LLM-generated additional categories (pronunciation, idioms, functional language, cultural notes, etc.) based on existing vocab/grammar; (2) **Live API** that accepts scenario descriptions, searches for similar existing scenarios via embeddings, and generates missing learning items + content units on-demand, growing the library organically. All outputs use structured LLM responses via Instructor, with JSON files partitioned by language and indexed in Meilisearch (search) and Postgres (relationships). Constitutional requirement: batch prioritizes quality over speed; live API prioritizes speed with acceptable quality.

## Technical Context

**Language/Version**: Python 3.14 (minimum required by constitution)
**Primary Dependencies**: 
- LangGraph >=1.0.7 (LLM agent orchestration for multi-step pipelines)
- Instructor >=1.0.0 (structured LLM outputs with Pydantic validation)
- Docling >=2.70.0 (PDF processing for grammar sources)
- Pandas >=2.0.0 (TSV/CSV parsing)
**Storage**: 
- Primary: JSON files in `havachat-knowledge/generated content/{language}/{level}/{content_type}/`
- Partitioning: All data partitioned by language (no cross-language queries needed)
  - Meilisearch: One index per language (`learning_items_zh`, `content_units_ja`, `scenarios_fr`)
  - Postgres: Table partitioning by language or separate schemas per language
- Index: Meilisearch (search API with language+level filtering, semantic similarity for scenarios)
- Relations: Postgres (learning item links, usage tracking, QA reports, scenario metadata)
**Testing**: pytest >=8.0.0 with unit (pipeline stages), contract (output schemas), integration (end-to-end batch), quality gate (validation rules)
**Target Platform**: Linux/macOS batch workers (horizontally scalable)
**Project Type**: Single project with CLI batch scripts
**Performance Goals**: 
- Batch: Quality over speed—30min for 500 vocab items with LLM enrichment acceptable
- No online latency constraints (this is offline generation)
**Constraints**: 
- Constitutional: Strict separation from online serving code
- Constitutional: All content must pass QA gates before publication
- File I/O: Output directories must match language/level structure
- LLM: Retry logic (3 attempts) before flagging for manual review
**Scale/Scope**: 
- Initial: 3 languages (Mandarin HSK1-6, Japanese JLPT N5-N1, French A1-C1)
- Vocab: ~5000 items per language
- Grammar: ~500 patterns per language
- Content: ~200 conversations per level per language
- Questions: 5-8 per conversation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Code Quality & Maintainability
- [x] Batch generation logic separated from online serving (no mixed concerns) - Pipeline is purely offline, outputs JSON files for API to read
- [x] Using `uv` package manager, Python >=3.14 - Specified in Technical Context
- [x] Type hints on all public functions/methods - FR-002 requires type hints on all public functions
- [x] Modular, reusable components with clear documentation - Language-specific subclasses (FR-004), independent pipeline stages (FR-001), prompt templates per language (FR-007)

### II. Testing Standards & Quality Gates
- [x] QA gates identified (schema validation, duplication checks, link correctness, question answerability, audio-text alignment) - FR-013 to FR-017 specify all gates
- [x] Test categories planned: unit (pipeline stages), contract (API), integration (end-to-end), quality gates - Testing strategy documented in Technical Context
- [x] Automated quality gate tests prevent bad content promotion - FR-017 requires validation reports, gates block publication on failure

### III. User Experience Consistency
- [x] API schema consistency verified (JSON structure, error codes) - FR-010, FR-011, FR-012 define strict schemas for all output types
- [x] Language + proficiency filtering strictly enforced - FR-013 presence checks validate language field matches directory structure; FR-019 selects items by (language, level)
- [x] Session packs deliver complete learning units (content + questions + quiz + audio) - FR-020 requires conversations with learning_item_ids, FR-022 generates questions per content unit
- [ ] Audio-text alignment validation planned - DEFERRED: Audio generation (TTS + timestamps) is Phase 2, not in this initial pipeline spec

### IV. Performance Requirements
- [x] Online API: <200ms p95 target documented - N/A for batch pipeline, but JSON output structure optimized for API reads
- [x] Batch: Quality over speed (iterative LLM loops acceptable) - Technical Context explicitly states "30min for 500 vocab items acceptable", FR-008 allows 3 retry attempts
- [x] Search index: <5min update window, denormalized for speed - Outputs JSON files for Meilisearch indexing (denormalized with embedded learning item data)
- [x] Memory: API <500MB, batch workers horizontally scalable - Batch processes one item/content at a time, workers can scale horizontally per language/level

**Justification Required**: Audio-text alignment validation deferred because TTS generation is not implemented in this phase. The pipeline outputs text-only content units with placeholders for audio fields (`has_audio: false`). Audio validation gates will be added when TTS integration is implemented in Phase 2.

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
├── pipeline/
│   ├── __init__.py
│   ├── enrichers/
│   │   ├── __init__.py
│   │   ├── base.py                  # BaseEnricher abstract class
│   │   ├── vocab/
│   │   │   ├── __init__.py
│   │   │   ├── mandarin.py          # MandarinVocabEnricher
│   │   │   ├── japanese.py          # JapaneseVocabEnricher
│   │   │   └── french.py            # FrenchVocabEnricher
│   │   ├── grammar/
│   │   │   ├── __init__.py
│   │   │   ├── mandarin.py          # MandarinGrammarEnricher
│   │   │   ├── japanese.py          # JapaneseGrammarEnricher
│   │   │   └── french.py            # FrenchGrammarEnricher
│   │   └── other_categories/
│   │       ├── __init__.py
│   │       ├── pronunciation.py     # LLM-generated from vocab
│   │       ├── idiom.py             # LLM-generated from vocab phrases
│   │       ├── functional.py        # LLM-generated from grammar patterns
│   │       ├── cultural.py          # LLM-generated from vocab/scenarios
│   │       └── base_generator.py    # Base class for LLM-based category generation
│   ├── generators/
│   │   ├── __init__.py
│   │   ├── content.py               # ContentGenerator (conversations/stories)
│   │   └── questions.py             # QuestionGenerator
│   ├── validators/
│   │   ├── __init__.py
│   │   ├── schema.py                # Pydantic models for all entities
│   │   ├── presence.py              # Presence check gate
│   │   ├── duplication.py           # Duplication check gate
│   │   ├── links.py                 # Link correctness gate
│   │   └── answerability.py         # Question answerability gate
│   ├── prompts/
│   │   ├── mandarin/
│   │   │   ├── vocab_prompts.py
│   │   │   └── grammar_prompts.py
│   │   ├── japanese/
│   │   │   ├── vocab_prompts.py
│   │   │   └── grammar_prompts.py
│   │   └── french/
│   │       ├── vocab_prompts.py
│   │       └── grammar_prompts.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── llm_client.py            # Instructor-wrapped LLM calls
│   │   ├── file_io.py               # Read/write JSON/TSV/CSV
│   │   ├── similarity.py            # Semantic similarity for content reuse
│   │   └── logging_config.py        # Structured logging setup
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── enrich_vocab.py          # CLI: python -m src.pipeline.cli.enrich_vocab
│   │   ├── enrich_grammar.py        # CLI: python -m src.pipeline.cli.enrich_grammar
│   │   ├── generate_other_categories.py  # CLI: Generate pronunciation/idioms/etc from vocab/grammar
│   │   ├── generate_content.py      # CLI: python -m src.pipeline.cli.generate_content
│   │   ├── generate_questions.py    # CLI: python -m src.pipeline.cli.generate_questions
│   │   └── run_qa_gates.py          # CLI: python -m src.pipeline.cli.run_qa_gates
│   ├── langgraph/
│   │   ├── __init__.py
│   │   ├── enrichment_graph.py      # LangGraph orchestration for enrichment
│   │   └── generation_graph.py      # LangGraph orchestration for content generation
│   └── api/
│       ├── __init__.py
│       ├── live_scenario_handler.py # Live API: scenario → search → generate → return
│       ├── scenario_search.py       # Semantic similarity search for scenarios
│       └── incremental_generator.py # On-demand learning item + content generation

tests/
├── unit/
│   ├── test_enrichers.py
│   ├── test_generators.py
│   └── test_validators.py
├── contract/
│   ├── test_schemas.py              # Validate all Pydantic models
│   └── test_output_format.py       # Validate JSON structure
├── integration/
│   ├── test_end_to_end_vocab.py
│   ├── test_end_to_end_content.py
│   └── test_qa_gates.py
└── fixtures/
    ├── mandarin_vocab_sample.tsv
    ├── japanese_grammar_sample.tsv
    └── french_vocab_sample.csv
```

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
