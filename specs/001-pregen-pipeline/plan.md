# Implementation Plan: Pre-generation Pipeline

**Branch**: `001-pregen-pipeline` | **Date**: 2026-01-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-pregen-pipeline/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build a Python-based pre-generation pipeline that transforms official vocabulary and grammar lists into enriched learning items, generates additional learning items for all categories (pronunciation, idioms, functional language, cultural notes, etc.), then generates level-appropriate content units (conversations/stories) per topic using ALL learning item categories together in a single LLM call with chain-of-thought reasoning. Content generation uses the instructor library for structured output and includes: generate → critique → revise → assign scenarios. All generated content is written to the havachat-knowledge repository for version control and ops review.

## Technical Context

**Language/Version**: Python 3.14+  
**Primary Dependencies**: LangGraph (agent orchestration), OpenAI/Anthropic SDK (LLM), Pydantic (schema validation), uv (package manager)  
**Storage**: File-based JSON output to havachat-knowledge repo; Postgres + Meilisearch for search (FR-028)  
**Testing**: pytest with contract/unit/integration test structure  
**Target Platform**: macOS/Linux development; Docker-based deployment (future)  
**Project Type**: Single Python project (batch pipeline + CLI)  
**Performance Goals**: 
  - Vocab enrichment: 500 words in <10 minutes with LLM retries
  - Content generation: 1 conversation in <2 minutes
  - QA gates: 100-item batch validation in <10 minutes
**Constraints**: 
  - LLM retry budget: max 3 retries per item before manual review flagging
  - Schema validation: >95% pass rate for enriched items
  - Link correctness: 100% (all referenced IDs must exist)
**Scale/Scope**: 
  - Initial: 5 languages × 3-7 levels × 500-1500 learning items per level (all categories)
  - Content units per topic: ~5 conversations + ~5 stories (generated together in single LLM call)
  - Growth: Additional topics per language-level (ops runs CLI for each desired topic)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Code Quality & Maintainability
- [ ] Batch generation logic separated from online serving (no mixed concerns)
- [ ] Using `uv` package manager, Python >=3.14
- [ ] Type hints on all public functions/methods
- [ ] Modular, reusable components with clear documentation

### II. Testing Standards & Quality Gates
- [ ] QA gates identified (schema validation, duplication checks, link correctness, question answerability, audio-text alignment)
- [ ] Test categories planned: unit (pipeline stages), contract (API), integration (end-to-end), quality gates
- [ ] Automated quality gate tests prevent bad content promotion

### III. User Experience Consistency
- [ ] API schema consistency verified (JSON structure, error codes)
- [ ] Language + proficiency filtering strictly enforced
- [ ] Session packs deliver complete learning units (content + questions + quiz + audio)
- [ ] Audio-text alignment validation planned

### IV. Performance Requirements
- [ ] Online API: <200ms p95 target documented
- [ ] Batch: Quality over speed (iterative LLM loops acceptable)
- [ ] Search index: <5min update window, denormalized for speed
- [ ] Memory: API <500MB, batch workers horizontally scalable

**Justification Required**: If any gate fails, document why violation is necessary and what simpler alternative was rejected.

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
│   │   ├── base_enricher.py          # Abstract base class
│   │   ├── vocab/
│   │   │   ├── japanese_vocab_enricher.py
│   │   │   ├── mandarin_vocab_enricher.py
│   │   │   ├── french_vocab_enricher.py
│   │   │   ├── english_vocab_enricher.py
│   │   │   └── spanish_vocab_enricher.py
│   │   └── grammar/
│   │       ├── japanese_grammar_enricher.py
│   │       ├── mandarin_grammar_enricher.py
│   │       ├── french_grammar_enricher.py
│   │       ├── english_grammar_enricher.py
│   │       └── spanish_grammar_enricher.py
│   ├── generators/
│   │   ├── __init__.py
│   │   ├── learning_item_generator.py  # Generate non-official items (pronunciation, idioms, etc.)
│   │   ├── content_generator.py        # Chain-of-thought content generation
│   │   ├── question_generator.py
│   │   └── scenario_matcher.py         # Similarity search for reuse
│   ├── validators/
│   │   ├── __init__.py
│   │   ├── schema_validator.py
│   │   ├── qa_gates.py                 # All QA gates (presence, duplication, links, answerability)
│   │   └── language_validators.py      # Language-specific rules
│   ├── prompts/
│   │   ├── japanese/
│   │   │   ├── vocab_enrichment_prompts.py
│   │   │   ├── grammar_enrichment_prompts.py
│   │   │   └── content_generation_prompts.py  # Chain-of-thought template
│   │   ├── mandarin/
│   │   ├── french/
│   │   ├── english/
│   │   └── spanish/
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── enrich_vocab.py
│   │   ├── enrich_grammar.py
│   │   ├── generate_learning_items.py   # Generate pronunciation, idioms, etc.
│   │   ├── generate_content.py          # Per-topic content generation
│   │   ├── generate_questions.py
│   │   └── run_qa_gates.py
│   └── utils/
│       ├── __init__.py
│       ├── file_utils.py
│       ├── llm_client.py                # Retry logic + logging + instructor integration
│       ├── usage_tracker.py             # Track learning item appearances
│       └── logging_config.py
├── models/
│   ├── __init__.py
│   ├── learning_item.py
│   ├── content_unit.py
│   ├── question.py
│   └── validation_report.py
└── constants.py

tests/
├── contract/
│   ├── __init__.py
│   ├── test_learning_item_schema.py
│   ├── test_content_unit_schema.py
│   └── test_question_schema.py
├── integration/
│   ├── test_vocab_enrichment_pipeline.py
│   ├── test_content_generation_pipeline.py  # Two-stage workflow integration tests
│   └── test_qa_gates_pipeline.py
└── unit/
    ├── test_japanese_vocab_enricher.py
    ├── test_mandarin_grammar_enricher.py
    ├── test_content_generator_chain_of_thought.py
    ├── test_scenario_matcher.py
    ├── test_qa_gates.py
    └── test_usage_tracker.py
```

**Structure Decision**: Single Python project with modular pipeline stages. Each stage (enrichment, learning item generation, content generation, question generation, QA gates) is independently executable via CLI. Language-specific logic uses subclasses to avoid configuration complexity. Content generation uses two-stage approach: (1) Generate ALL learning items first, (2) Generate content per topic using all items together with chain-of-thought reasoning via instructor library.

## Complexity Tracking

No constitutional violations. All complexity is essential:
- Language-specific subclasses: Necessary due to fundamentally different source formats and validation rules across languages (Japanese has furigana, Chinese needs Pinyin generation, French has different grammar markdown structure)
- Chain-of-thought content generation: Required for quality; generating content without self-critique would compromise learning item coverage and level-appropriateness
- LLM retry loops: Required for quality (FR-008); without retries, schema validation pass rate would fall below 95% threshold

---

## Content Generation Workflow (Simplified Approach)

**Critical Design Decision:**

Content generation happens AFTER all learning items have been generated for a given (language, level). This allows the generator to use ALL learning item categories (vocab, grammar, pronunciation, idioms, functional, cultural, writing system, miscellaneous) in a single generation pass, maximizing natural integration while keeping the implementation simple.

### Two-Stage Pipeline

**Stage 1: Generate All Learning Items**
- Run enrichment for ALL categories first:
  - Vocab enrichment (from official lists)
  - Grammar enrichment (from official lists)  
  - Pronunciation item generation (LLM-generated based on vocab/grammar)
  - Idioms/expressions generation (LLM-generated, level-appropriate)
  - Functional language generation (LLM-generated, level-appropriate)
  - Cultural notes generation (LLM-generated, level-appropriate)
  - Writing system items (for zh/ja only)
  - Miscellaneous categories (sociolinguistics, pragmatics, literacy, patterns)
- Output: Complete library of learning items in `{language}/{level}/{category}/`

**Stage 2: Generate Content Units (Per Topic)**
- **Input**: 
  - Topic (e.g., "Food", "Meeting New People")
  - All learning items from Stage 1 in simplified format (just target_item, no full definitions to save tokens)
  - Target: N conversations and N stories (default N=5)
- **Process**: Single LLM prompt with structured output (using `instructor` library) and chain-of-thought:
  1. **Generate**: Create N conversations (6-8 lines each) and N stories (200-300 words) using as many learning items as possible, in spoken/learner-friendly language
  2. **Critique**: LLM evaluates its own output for level-appropriateness, learning item coverage, natural flow
  3. **Revise**: LLM revises based on critique AND explicitly lists which learning items are present in each conversation/story
  4. **Assign Scenarios**: LLM assigns a 3-8 word scenario name to each conversation/story (e.g., "Ordering at a casual restaurant", "Meeting a friend at park")
- **Output**: 
  - N conversations with segments, learning_item_ids[], scenario_name
  - N stories with paragraphs, learning_item_ids[], scenario_name
  - Stored in `{language}/{level}/conversations/` and `{language}/{level}/stories/`

### CLI Interface

```bash
# Stage 1: Generate all learning items first
uv run python -m pipeline.cli.enrich_vocab --language zh --level hsk1 --source official_hsk1.tsv
uv run python -m pipeline.cli.enrich_grammar --language zh --level hsk1 --source official_hsk1_grammar.csv
uv run python -m pipeline.cli.generate_learning_items --language zh --level hsk1 --categories pronunciation,idioms,functional,cultural

# Stage 2: Generate content units per topic
uv run python -m pipeline.cli.generate_content \
  --language zh \
  --level hsk1 \
  --topic "Food" \
  --num-conversations 5 \
  --num-stories 5 \
  --output-dir havachat-knowledge/generated content/Mandarin/HSK1/

# Repeat Stage 2 for each desired topic
uv run python -m pipeline.cli.generate_content \
  --language zh \
  --level hsk1 \
  --topic "Meeting New People" \
  --num-conversations 5 \
  --num-stories 5 \
  --output-dir havachat-knowledge/generated content/Mandarin/HSK1/
```

### Key Implementation Details

**Learning Item Simplification (Token Optimization)**
To reduce token usage in the content generation prompt:
- Vocab: Include only `target_item` (e.g., "你好", "libro", "bonjour")
- Grammar: Include only the pattern/rule (e.g., "Subject + 是 + Noun", "ne...pas", "です/だ")
- Pronunciation: Include only the rule description (e.g., "3rd tone + 3rd tone → 2nd tone + 3rd tone")
- Idioms: Include only the expression (e.g., "break a leg", "塞翁失马")
- Functional: Include only the phrase template (e.g., "Could you please...", "お願いします")
- Cultural: Include only the concept name (e.g., "bowing etiquette", "Chinese New Year customs")
- Writing system: Include only character/radical (e.g., "人", "亻", "口")

**Structured Output with Instructor Library**
- Use `instructor` library to enforce Pydantic schema for LLM output
- Schema includes: conversations[], stories[], each with segments[], learning_item_ids[], scenario_name
- Chain-of-thought fields: initial_draft, critique, final_version (for observability)

**Learning Item Linking**
After LLM generates content and lists which items are present:
- Validate that all listed learning_item_ids exist in the directories
- Language-aware tokenization to verify items actually appear in text (presence check)
- If presence check fails, add to manual review queue

### Updated Functional Requirements

**FR-022-SIMPLIFIED**: Content generation MUST happen in two stages: (1) Generate all learning items for all categories first, (2) Generate content units per topic using ALL learning items together

**FR-023-SIMPLIFIED**: Content generator MUST use `instructor` library for structured output with Pydantic schema validation

**FR-024-SIMPLIFIED**: Content generation prompt MUST implement chain-of-thought: generate → critique → revise → assign scenarios, with all steps in a single LLM call to maintain context

**FR-025-SIMPLIFIED**: Content generator MUST accept `--num-conversations` and `--num-stories` parameters (default: 5 each) and generate exactly N of each type in one LLM call

**FR-026-SIMPLIFIED**: Learning items MUST be passed to LLM in simplified format (target_item only) to minimize token usage; full definitions are NOT needed for content generation

**FR-027-SIMPLIFIED**: LLM MUST explicitly list which learning items are present in each generated conversation/story; this list becomes the learning_item_ids[] field

**FR-028-SIMPLIFIED**: LLM MUST assign a 3-8 word scenario name to each conversation/story; these scenario names are later normalized into the scenario vocabulary

---

## Phase 0: Research & Design (Continued)
