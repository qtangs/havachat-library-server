# Feature Specification: Pre-generation Pipeline for Learning Content

**Feature Branch**: `001-pregen-pipeline`  
**Created**: 2026-01-26  
**Status**: Draft  
**Input**: User description: "Build Pre-generation Pipeline for learning content using Python scripts and LangGraph agents. The pipeline processes official vocab/grammar lists, generates learning items with LLM enrichment, creates content units (conversations/stories), links content to learning items, generates comprehension questions, TTS audio with timestamps, and runs QA gates before publishing."

## Clarifications

### Session 2026-01-26

- Q: Should the enrichment script use a flexible column-mapping configuration to handle different source formats (CSV/TSV/JSON) across languages? → A: **No**. Use language-specific subclasses (e.g., `JapaneseVocabEnricher`, `MandarinVocabEnricher`, `FrenchVocabEnricher`) where each implements its own file parsing logic, field mapping, and LLM prompts. This is cleaner than generic configuration because each language has fundamentally different source structures (Japanese has furigana+romaji already, French has definitions, Chinese needs Pinyin generation) and requires domain-specific prompts.
- Q: Do grammar lists follow the same format across languages? → A: **No**. Chinese uses CSV with hierarchical categories (类别,类别名称,细目,语法内容), Japanese uses TSV with Type/Rule/Example columns, French uses markdown with category headers and descriptive title lists. Grammar enrichment also requires language-specific subclasses (e.g., `JapaneseGrammarEnricher`, `MandarinGrammarEnricher`, `FrenchGrammarEnricher`) to parse these different formats and apply appropriate enrichment strategies.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Import and Enrich Official Vocabulary Lists (Priority: P1)

Content ops imports an official HSK1 vocabulary list (TSV with Word and Part of Speech columns) and runs the enrichment script. The system identifies missing fields, invokes LLM to generate explanations, examples, romanization, and sense glosses, validates the output against the schema, and writes enriched learning items to `havachat-knowledge/generated content/Mandarin/HSK1/vocab/`.

**Why this priority**: Vocabulary is the foundation of all learning content. Without enriched vocab items, no other pipeline stages can proceed. This delivers immediate value by transforming raw word lists into structured, searchable learning resources.

**Independent Test**: Can be fully tested by providing an official vocab TSV, running the enrichment script, and verifying that output JSON files contain all required fields (target_item, definition, examples, romanization, level_system, level_min/max) and pass schema validation.

**Acceptance Scenarios**:

1. **Given** an official HSK1 vocab TSV with columns "Word, Part of Speech", **When** the MandarinVocabEnricher runs, **Then** each word is enriched one-by-one via individual LLM calls, generating definition, 3-5 examples, pinyin romanization, sense_gloss for each item, and written to `Mandarin/HSK1/vocab/item-{uuid}.json`
2. **Given** a Japanese JLPT N1 vocab JSON with fields `{word, meaning, furigana, romaji, level}`, **When** the JapaneseVocabEnricher runs, **Then** existing meaning/furigana/romaji are preserved, and only missing fields (examples, sense_gloss for polysemy, aliases) are LLM-generated one-by-one via individual LLM calls for each item
3. **Given** a French CEFR A1 vocab file with existing definitions, **When** the FrenchVocabEnricher runs, **Then** existing definitions are preserved as definition base, and only missing fields (contextual examples, sense_gloss for polysemy, aliases, pos) are LLM-generated one-by-one via individual LLM calls and written to `French/A1/vocab/item-{uuid}.json`
4. **Given** an enriched vocab item fails schema validation (missing required field), **When** the LLM retry loop executes, **Then** the system retries up to 3 times for that specific item before flagging it for manual review with error context
5. **Given** an enriched vocab list, **When** the validation script runs, **Then** all items pass presence checks (romanization for zh/ja, definition for all) and duplicate detection (no items with identical lemma+sense_gloss)

---

### User Story 2 - Import and Enrich Grammar Lists (Priority: P1)

Content ops imports an official grammar list and runs the language-specific grammar enrichment script. The system parses the source format (Chinese CSV with hierarchical categories, Japanese TSV with Type/Rule/Example columns, French markdown with category headers and title lists), generates learner-friendly explanations, creates usage examples, breaks down broad patterns into teachable sub-items, and writes enriched grammar learning items to `havachat-knowledge/generated content/{language}/{level}/grammar/`.

**Why this priority**: Grammar items are equally critical for content generation. Without them, conversations and stories lack structural targets. Grammar enrichment must handle language-specific source formats and category structures, and avoid over-broad items (as specified in PRD).

**Independent Test**: Can be fully tested by providing an official grammar source file for any language, running the appropriate language enricher subclass, and verifying that output contains narrow-scope grammar items (each with form, meaning/use, examples) and passes granularity checks (no "mega-items" like "past tense" without sub-items).

**Acceptance Scenarios**:

1. **Given** an official HSK1 grammar CSV with columns "类别,类别名称,细目,语法内容" where 类别="句型", 细目="是...的", **When** the MandarinGrammarEnricher runs, **Then** each grammar pattern is enriched one-by-one via individual LLM calls, creating a learning item with target_item="是...的", definition describing form and use, 3-5 contextual examples, and category="grammar"
2. **Given** a Japanese JLPT N5 grammar TSV with columns "Type, Rule, Example" where Type="Basic Particles", Rule="は (wa) - Topic Marker", Example="私は学生です。", **When** the JapaneseGrammarEnricher runs, **Then** the existing example is preserved and each grammar item is enriched one-by-one with definition, additional usage examples, common learner errors, and the particle "は" is stored as target_item
3. **Given** a French A1 grammar markdown with category "## A1: Pronouns" and item "Il/elle/ils/elles = it/he/she/they (French Subject Pronouns)", **When** the FrenchGrammarEnricher runs, **Then** each grammar item is enriched one-by-one, parsing the title into target_item="Il/elle/ils/elles", generating definition for form/usage, 3-5 contextual examples, and category="grammar"
4. **Given** a broad grammar pattern like "past tense" in any language, **When** the LLM generates that specific item, **Then** the enricher prompts for sub-item breakdown (e.g., "regular past -ed", "irregular past forms", "past continuous") and creates linked learning items with narrower scope, processing each sub-item individually
5. **Given** enriched grammar lists from multiple languages (English CEFR, Chinese HSK, Japanese JLPT), **When** stored in respective directories, **Then** each item includes correct level_system (cefr|hsk|jlpt) and level_min/max values

---

### User Story 3 - Generate Content Units Using All Learning Items with Chain-of-Thought (Priority: P2)

Content ops generates all learning items first (vocab, grammar, pronunciation, idioms, functional, cultural, etc.), then runs content generation for a specific topic (e.g., "Food", "Meeting New People"). The system uses a single LLM call with chain-of-thought reasoning (generate → critique → revise → assign scenarios) to create N conversations (6-8 lines each) and N stories (200-300 words) using as many learning items as possible. The LLM explicitly lists which items are present, and the system validates all references.

**Why this priority**: Content generation depends on enriched learning items (P1 dependencies). This is the first "synthesis" stage that creates learner-facing materials. Using all learning item categories together in one generation produces more natural, integrated content compared to category-by-category approaches. Chain-of-thought ensures quality through self-critique.

**Independent Test**: Can be fully tested by:
1. Providing complete learning items for all categories
2. Running content generation with a topic
3. Verifying output contains N conversations and N stories with learning_item_ids[], scenario names
4. Validating all linked items exist and appear in text

**Acceptance Scenarios**:

1. **Given** complete Mandarin HSK2 learning items (vocab, grammar, pronunciation, idioms, functional, cultural) have been generated, **When** content generation runs with topic="Food", num-conversations=5, num-stories=5, **Then** 5 conversations (6-8 turns each) and 5 stories (200-300 words) are generated using items from ALL categories, each with explicit learning_item_ids[] and a 3-8 word scenario name (e.g., "Ordering at a casual restaurant", "Shopping for groceries")
2. **Given** learning items in simplified format (target_item only), **When** passed to LLM, **Then** the prompt uses <500 tokens for learning items (compared to >2000 tokens with full definitions), enabling efficient generation
3. **Given** LLM generates initial draft, **When** chain-of-thought executes, **Then** the output includes: initial_draft, self_critique, revised_version, and the revised version has measurably better learning item coverage (e.g., 15-20 unique items vs 8-10 in initial draft)
4. **Given** generated conversations and stories with LLM-provided learning_item_ids[], **When** presence validation runs, **Then** every listed item exists in the directories AND target_item appears in the conversation/story text (using language-aware tokenization for Chinese)
5. **Given** LLM assigns scenario names like "Ordering food at restaurant" and "Meeting friend at café", **When** scenario normalization runs, **Then** similar scenarios are grouped (both become "Food - Restaurant/Café") and stored in the scenario vocabulary for reuse
6. **Given** content generation for topic="Food" completes, **When** usage tracking updates, **Then** each learning item's `appearances_count` in `{language}/{level}/usage_stats.json` increments for every conversation/story where it appears
7. **Given** French A1 learning items include writing system items (should not exist for French), **When** content generation runs, **Then** the system logs a warning about inappropriate category but does NOT block generation
8. **Given** instructor library structured output schema, **When** LLM returns invalid format (missing required field), **Then** the retry mechanism catches the validation error, retries up to 3 times, and flags for manual review if still failing

---

### User Story 4 - Generate Comprehension Questions (Priority: P3)

Content ops runs the question generation script on a completed conversation. The system analyzes each segment and the full conversation, generates 5-8 questions (MCQ, true/false, short answer) testing detail recall, inference, and main idea, validates answerability against the text, and writes the question set to `havachat-knowledge/generated content/{language}/{level}/questions/`.

**Why this priority**: Questions depend on content units (P2 dependency). They enhance learning value but are not blocking for basic content consumption. Can be added iteratively to existing content.

**Independent Test**: Can be fully tested by providing a completed conversation, running the question generation script, and verifying that all questions are answerable from the text, include correct answer keys, and cover specified question types.

**Acceptance Scenarios**:

1. **Given** a French A1 conversation, **When** the question generation script runs, **Then** 5-8 questions are generated with types distributed: 3-4 MCQ, 1-2 true/false, 1-2 short answer, covering detail recall (40%), inference (30%), main idea (30%)
2. **Given** generated questions, **When** the answerability validation runs, **Then** each question's answer can be derived from the text (verified by LLM re-reading the text and answering the question)
3. **Given** MCQ questions, **When** generated, **Then** each includes 4 options with 1 correct answer, 3 plausible distractors, and a rationale explaining why the answer is correct and the learning value
4. **Given** questions with difficulty tags, **When** stored, **Then** each question includes difficulty level (easy/medium/hard within the content's level range) and tags (inference, detail, main-idea, vocabulary-focus, grammar-focus)

---

### User Story 5 - Run QA Gates and Generate Validation Report (Priority: P2)

Content ops runs the QA gate script on a batch of content (e.g., all French A1 conversations for "Food" topic). The system executes presence checks (learning items appear in text), duplication checks (no near-duplicate items), link correctness (all references valid), question answerability (answers derivable), and generates a validation report with pass/fail status and flagged items for manual review.

**Why this priority**: QA gates are constitutional requirements (Principle II). They must run before any content is published. Higher priority than question generation because gates validate all content types (vocab, grammar, conversations), not just questions.

**Independent Test**: Can be fully tested by running the QA gate script on a test batch with known violations (duplicate learning items, invalid references, unanswerable questions) and verifying that the validation report correctly identifies all failures.

**Acceptance Scenarios**:

1. **Given** a batch of French A1 content, **When** the presence check runs, **Then** every learning_item_id referenced in content segments exists in the learning item directories (vocab/, grammar/, pronunciation/, idioms/, etc.) and the target_item appears in the segment text (using French tokenization)
2. **Given** two learning items with identical lemma "banco" but different sense_gloss ("bank financial" vs "bench seat"), **When** the duplication check runs, **Then** both items pass (sense disambiguation prevents collision)
3. **Given** a question with answer "tomorrow morning", **When** the answerability check runs, **Then** the system verifies the phrase appears in or is clearly inferrable from the conversation text
4. **Given** a validation report with 95% pass rate (5% flagged for review), **When** reviewed by ops, **Then** the report includes specific line references, failure reasons, and suggested fixes for each flagged item
4. **Given** a validation report with 95% pass rate (5% flagged for review), **When** reviewed by ops, **Then** the report includes specific line references, failure reasons, and suggested fixes for each flagged item

---

### Edge Cases

- **Language-specific source formats**: 
  - **Vocab**: Japanese JSON has `{word, meaning, furigana, romaji, level}` while French might be CSV `{Mot, Définition, Exemple}` and Chinese TSV `{Word, Part of Speech}`. 
  - **Grammar**: Chinese CSV has hierarchical categories `{类别,类别名称,细目,语法内容}`, Japanese TSV has `{Type, Rule, Example}`, French markdown has category headers (`## A1: Pronouns`) followed by descriptive title lists. Each language subclass handles its own source format without requiring generic configuration.
- **Pre-existing fields**: Japanese vocab already includes romanization (furigana/romaji) and English meanings; Japanese grammar includes examples with romaji and translations. Enrichment subclasses must preserve these and only generate missing fields (additional examples, sense_gloss if polysemy detected, definition for grammar).
- **Grammar hierarchical parsing**: French grammar titles contain the pattern itself plus explanation (e.g., "Il/elle/ils/elles = it/he/she/they (French Subject Pronouns)"). The FrenchGrammarEnricher must parse title to extract target_item ("Il/elle/ils/elles") and category hint ("Subject Pronouns").
- **Missing romanization**: For Chinese, if source TSV lacks Pinyin, the MandarinVocabEnricher LLM must generate it; validation must enforce presence before writing output.
- **Polysemous words**: "banco" (bank/bench), "bat" (animal/sports equipment), Japanese "bank" (financial vs riverbank) must result in separate learning items with distinct sense_gloss to avoid quiz ambiguity.
- **LLM generation failures**: If LLM fails to generate required fields after 3 retries, the item must be flagged for manual review with error context (not silently dropped).
- **Content similarity edge cases**: If similarity score is 75-85% (borderline), the system should present both options to ops: reuse existing or generate new variant.
- **Broken learning item references**: If a content unit references a learning item ID that doesn't exist (e.g., item was deleted), the link validation must catch and report it.
- **Question difficulty misalignment**: If an A1-level conversation has a generated question requiring B1-level inference, the difficulty validation must flag it.
- **Cross-language contamination**: Japanese vocab must not appear in French content directories; validation must check language field matches directory structure.

## Requirements *(mandatory)*

### Functional Requirements

**Pipeline Architecture:**

- **FR-001**: Each pipeline stage (vocab enrichment, grammar enrichment, content generation, question generation, QA gates) MUST be executable independently via CLI with `python src/pipeline/{stage_name}.py --config {config.json}`
- **FR-002**: All scripts MUST use `uv` package manager and Python >=3.14 with type hints on all public functions
- **FR-003**: Pipeline stages MUST read input from configurable paths and write output to `havachat-knowledge/generated content/{language}/{level}/{content_type}/` following the directory structure convention (e.g., `vocab/`, `grammar/`, `conversations/`, `questions/`)

**Input Handling:**

- **FR-004**: Enrichment scripts MUST use language-specific subclasses (e.g., `JapaneseVocabEnricher`, `MandarinVocabEnricher`, `FrenchVocabEnricher`) where each subclass implements its own file parsing logic, field mapping, and validation rules specific to that language's source format
- **FR-005**: Each language subclass MUST detect which required fields are already present in the source data (e.g., Japanese already has furigana+romaji, French may have definitions) and only invoke LLM to generate missing required fields
- **FR-006**: Language subclasses MUST enforce language-specific validation: Chinese/Japanese subclasses MUST validate romanization presence (Pinyin/Romaji); English/French/French subclasses MUST NOT require romanization. All subclasses MUST use shared validation utilities for common rules (level_system validation, level_min <= level_max ordinal comparison).

**LLM Integration:**

- **FR-007**: Each language subclass MUST have its own prompt templates in `src/pipeline/prompts/{language}/{stage_name}_enrichment_prompts.py` (e.g., `prompts/japanese/vocab_enrichment_prompts.py`, `prompts/mandarin/vocab_enrichment_prompts.py`, `prompts/japanese/grammar_enrichment_prompts.py`) with language-specific instructions and examples. Template structure will be provided as part of implementation. Learning items are enriched one-by-one via individual LLM calls.
- **FR-008**: LLM enrichment MUST implement retry logic for each individual item: attempt generation → validate against schema → retry up to 3 times on failure → flag for manual review if still failing. Each learning item is processed with its own LLM call.
- **FR-009**: System MUST log all LLM requests (prompt hash, model, token counts, latency) and responses (success/failure, validation errors) for cost tracking and quality monitoring

**Schema Validation:**

- **FR-010**: All generated learning items MUST conform to the schema: `{id, language, category, target_item, definition, examples[], level_system, level_min, level_max, created_at, version}` with additional fields per category (romanization for zh/ja, sense_gloss for vocab, lemma/pos where applicable)
- **FR-011**: All generated content units MUST conform to: `{id, language, type, title, description, text, segments[], learning_item_ids[], topic_ids[], scenario_ids[], level_system, level_min, level_max, word_count, estimated_reading_time_seconds, has_audio, has_questions, publishable, created_at, version}`
- **FR-012**: All generated questions MUST conform to: `{id, content_id, question_type, question_text, options[], answer_key, rationale, difficulty, tags[], created_at, version}`

**QA Gates (Constitutional Requirement):**

- **FR-013**: QA gate script MUST execute presence checks: every learning_item_id in content segments must exist in vocab/grammar directories AND target_item text must appear in segment text (language-aware tokenization)
- **FR-014**: QA gate script MUST execute duplication checks: no two learning items with identical (language, category, lemma, sense_gloss) unless explicitly marked as variants
- **FR-015**: QA gate script MUST execute link correctness checks: all referenced IDs (learning_item_ids, topic_ids, scenario_ids, content_id) must resolve to existing files
- **FR-016**: QA gate script MUST execute question answerability checks: LLM must confirm each question's answer is derivable from the content text (automated re-reading test)
- **FR-017**: QA gate script MUST generate a validation report (JSON + markdown) with pass/fail status per item, failure reasons, line references, and summary statistics (total items, pass rate, flagged count)
- **FR-018-PHASED**: QA gates MUST support phase-aware validation: For Phase 2-7 content, validate that BOTH current-category learning items AND foundation vocab/grammar items from Phase 1 are correctly linked and present in text.
- **FR-019-PHASED**: QA gate reports MUST include phase context in error messages (e.g., "Phase 3 (idioms): item-xyz referenced but not found" or "Phase 2 → Phase 1 foundation link broken: vocab item-abc not found").
- **FR-020-PHASED**: QA gates MUST support cross-phase validation: Given complete Phase 1-7 content for a topic/scenario, generate a usage report showing which foundation items appear in which phases (for usage tracking verification).

**Content Generation:**

- **FR-018**: Content generation MUST implement two-stage workflow: Stage 1 generates ALL learning items for all categories (vocab, grammar, pronunciation, idioms, functional, cultural, writing system, miscellaneous) one-by-one via individual LLM calls; Stage 2 generates content per topic using all items together in a single LLM call
- **FR-019**: Content generator MUST use `instructor` library for structured output with Pydantic schema validation
- **FR-020**: Content generation prompt MUST structure chain-of-thought steps (generate → critique → revise → assign scenarios) within the prompt itself for a single LLM call to maintain context and reduce API overhead. The chain-of-thought is described in the prompt, not executed as sequential API calls.
- **FR-021**: Content generator MUST accept `--topic`, `--num-conversations` (default: 5), and `--num-stories` (default: 5) parameters and generate exactly N conversations and N stories in one LLM call
- **FR-022**: Learning items MUST be passed to LLM in simplified format (target_item only, no full definitions) to minimize token usage; full definitions are NOT needed for content generation
- **FR-023**: Generated conversations MUST have 6-10 turns with speaker labels; stories MUST have 200-400 words divided into 3-8 paragraphs; each segment MUST reference 2-4 learning items explicitly in learning_item_ids[]. Note: A "segment" is a logical grouping (typically 2-3 turns for dialogues, 1 paragraph for stories).
- **FR-024**: LLM MUST explicitly list which learning items are present in each generated conversation/story during the "revise" step of chain-of-thought; this list becomes the learning_item_ids[] field
- **FR-025**: LLM MUST assign a 3-8 word scenario name to each conversation/story during the "assign scenarios" step; these scenario names are later normalized into the scenario vocabulary
- **FR-026**: System MUST implement usage tracking: after each content generation batch, update `{language}/{level}/usage_stats.json` to increment appearances_count for each learning item referenced. This requires a dedicated usage tracking module with write operations to the metadata file.

**Question Generation:**

- **FR-027**: Question generation MUST produce 5-8 questions per content unit with type distribution targets: 50-60% MCQ, 20-30% true/false, 20% short answer. These are target ranges, not strict requirements; small question sets (5 questions) may not satisfy all ranges exactly.
- **FR-028**: Questions MUST cover cognitive levels: 40% detail recall, 30% inference, 30% main idea/summary
- **FR-029**: MCQ questions MUST include 4 options (1 correct, 3 plausible distractors) and a rationale field explaining the learning value

**QA Gates (Constitutional Requirement):**

- **FR-030**: QA gate script MUST execute presence checks: every learning_item_id in content segments must exist in learning item directories (vocab/, grammar/, pronunciation/, idioms/, functional/, cultural/, writing_system/, misc/) AND target_item text must appear in segment text (language-aware tokenization)
- **FR-031**: QA gate script MUST execute duplication checks: no two learning items with identical (language, category, lemma, sense_gloss) unless explicitly marked as variants
- **FR-032**: QA gate script MUST execute link correctness checks: all referenced IDs (learning_item_ids, content_id) and names (topic_name, scenario_name) must resolve to existing files or valid vocabulary entries
- **FR-033**: QA gate script MUST execute question answerability checks: LLM must confirm each question's answer is derivable from the content text (automated re-reading test)
- **FR-034**: QA gate script MUST generate a validation report (JSON + markdown) with pass/fail status per item, failure reasons, line references, and summary statistics (total items, pass rate, flagged count)

**Error Handling & Observability:**

- **FR-035**: All scripts MUST log to structured JSON format (timestamp, stage, action, status, error_details, item_id, topic) for debugging and quality monitoring
- **FR-036**: LLM generation failures MUST create a manual review queue file `{language}/{level}/manual_review/{stage_name}_failures.jsonl` with failed items and error context
- **FR-037**: System MUST track and report batch processing metrics: items processed, success rate, average LLM tokens per item, total processing time, chain-of-thought steps executed

**Database & Search Infrastructure:**

- **FR-038**: System MUST implement database partitioning by language for both Meilisearch (separate indexes per language: `learning_items_zh`, `scenarios_ja`, etc.) and Postgres (table partitioning or separate schemas per language). Implementation includes index creation scripts, schema setup, and partition configuration validation.

### Key Entities

- **Learning Item**: Atomic pedagogical unit (vocabulary, grammar, pronunciation, idioms, functional language, cultural notes, writing system, miscellaneous categories) with fields: id, language, category, target_item, definition, examples, romanization (for zh/ja), level_system, level_min/max, sense_gloss (for polysemy), lemma, pos, aliases, created_at, version. Stored as individual JSON files in `{language}/{level}/{category}/item-{uuid}.json`.

- **Content Unit**: Conversation or story containing multiple segments. Fields: id, language, type (conversation|story), title, description, text, segments[] (each with type, speaker, text, learning_item_ids, start/end times), learning_item_ids[] (all featured items), topic_name, scenario_name (3-8 word description assigned by LLM), level_system, level_min/max, word_count, estimated_reading_time_seconds, has_audio, has_questions, publishable, chain_of_thought_metadata (initial_draft, critique, revisions_made), created_at, version. Stored as `{language}/{level}/conversations/content-{uuid}.json` or `stories/content-{uuid}.json`.

- **Question Set**: Comprehension questions for a content unit. Fields: id, content_id (reference), segment_range, question_type (mcq|true_false|short_answer|summary), question_text, options[] (for MCQ), answer_key, rationale, difficulty, tags[] (inference, detail, main-idea), created_at, version. Stored as `{language}/{level}/questions/questions-{content_id}.json`.

- **Topic**: Broad thematic category (~200 total across all languages). Fields: id, name, aliases[], language (or "universal"), parent_topic_id (optional). Example: "food", "travel", "work", "social-interaction".

- **Scenario**: Concrete situation within a topic (~2000 total). Fields: id, name, aliases[], topic_id (parent), language (or "universal"), description. Example: "ordering at restaurant", "airport check-in", "job interview".

- **Usage Metadata**: Tracks how often each learning item appears in published content. Fields: learning_item_id, appearances_count, last_used_content_id, last_updated. Stored in `{language}/{level}/usage_stats.json` as array.

- **Validation Report**: Output of QA gates for a batch. Fields: batch_id, language, level, timestamp, total_items, passed_count, failed_count, flagged_items[] (each with item_id, item_type, failure_reason, line_reference, suggested_fix), summary_stats (pass_rate_percent, most_common_failures). Stored as `{language}/{level}/qa_reports/report-{timestamp}.json` and `report-{timestamp}.md`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

<!--
  Constitution alignment: Include performance targets (<200ms API p95),
  UX consistency metrics (error rate, alignment accuracy),
  and quality gate pass rates (batch validation success).
-->

- **SC-001**: Vocab enrichment script processes 500 HSK1 words from TSV input and generates complete learning items (all required fields) with >95% schema validation pass rate
- **SC-002**: Grammar enrichment script processes 100 grammar patterns and produces narrow-scope items (explanation <500 chars, no mega-items flagged) with >90% granularity validation pass rate
- **SC-003**: Content generation with chain-of-thought produces 5 French A1 conversations + 5 stories for topic="Food" in a single LLM call, with >95% of revised versions showing improved learning item coverage compared to initial drafts (measured by unique item count)
- **SC-004**: Generated content achieves 100% link correctness (all referenced learning_item_ids exist in learning item directories) and >95% presence validation (items appear in text using language-aware tokenization)
- **SC-005**: Learning item simplification reduces token usage to <500 tokens for 200 items (target_item only) compared to >2000 tokens with full definitions, enabling efficient batch generation
- **SC-006**: Question generation produces 5-8 questions per conversation with >98% answerability pass rate (LLM can answer from text alone) and correct type distribution (50-60% MCQ, 20-30% T/F, 20% short answer)
- **SC-007**: QA gate validation runs on 100-item batch (conversations + stories across multiple topics) and completes within 10 minutes, generating a validation report with <5% flagged items requiring manual review
- **SC-008**: LLM retry loop (including instructor schema validation) reduces generation failures from 15% (first attempt) to <2% (after 3 retries), with remaining failures correctly flagged for manual review
- **SC-009**: All pipeline stages log structured metrics (items processed, success rate, tokens used, processing time, topic, chain-of-thought steps) enabling ops to track cost and quality trends per topic and per batch
- **SC-010**: Content generation for one topic (5 conversations + 5 stories) uses 60-80% of available learning items for that level, demonstrating broad coverage across all categories (vocab, grammar, pronunciation, idioms, functional, cultural)
- **SC-011**: Cross-language validation prevents contamination: 0% of generated content has language field mismatching directory structure (e.g., Japanese vocab in French directories)
- **SC-012**: Manual review queue contains only legitimate failures (schema violations, ambiguous polysemy, unanswerable questions, missing learning items), not false positives from validation bugs
- **SC-013**: Scenario name normalization: >85% of LLM-assigned scenario names (3-8 words) can be automatically grouped into existing scenario vocabulary entries using semantic similarity
- **SC-009**: All pipeline stages log structured metrics (items processed, success rate, tokens used, processing time, generation_phase) enabling ops to track cost and quality trends per phase and per batch
- **SC-010**: Cross-phase validation report shows foundation vocab/grammar usage across phases: For complete Phase 1-7 content, >90% of Phase 1 foundation items appear in at least 2 additional phases (demonstrating consistent vocabulary reuse)
- **SC-011**: Cross-language validation prevents contamination: 0% of generated content has language field mismatching directory structure (e.g., Japanese vocab in French directories)
- **SC-012**: Manual review queue contains only legitimate failures (schema violations, ambiguous polysemy, unanswerable questions, broken foundation links), not false positives from validation bugs
- **SC-013**: Phase sequencing validation: 0% of Phase 2-7 content generated without valid Phase 1 foundation reference (all non-Phase-1 content must link to Phase 1)
