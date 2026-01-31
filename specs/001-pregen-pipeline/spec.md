# Feature Specification: Pre-generation Pipeline for Learning Content

**Feature Branch**: `001-pregen-pipeline`  
**Created**: 2026-01-26  
**Status**: Draft  
**Input**: User description: "Build Pre-generation Pipeline for learning content using Python scripts and LangGraph agents. The pipeline processes official vocab/grammar lists, generates learning items with LLM enrichment, creates content units (conversations/stories), links content to learning items, generates comprehension questions, TTS audio with timestamps, and runs QA gates before publishing."

## Clarifications

### Session 2026-01-26

- Q: Should the enrichment script use a flexible column-mapping configuration to handle different source formats (CSV/TSV/JSON) across languages? → A: **No**. Use language-specific subclasses (e.g., `JapaneseVocabEnricher`, `ChineseVocabEnricher`, `FrenchVocabEnricher`) where each implements its own file parsing logic, field mapping, and LLM prompts. This is cleaner than generic configuration because each language has fundamentally different source structures (Japanese has furigana+romaji already, French has definitions, Chinese needs Pinyin generation) and requires domain-specific prompts.
- Q: Do grammar lists follow the same format across languages? → A: **No**. Chinese uses CSV with hierarchical categories (类别,类别名称,细目,语法内容), Japanese uses TSV with Type/Rule/Example columns, French uses markdown with category headers and descriptive title lists. Grammar enrichment also requires language-specific subclasses (e.g., `JapaneseGrammarEnricher`, `ChineseGrammarEnricher`, `FrenchGrammarEnricher`) to parse these different formats and apply appropriate enrichment strategies.

### Session 2026-01-29

- Q: Should audio generation be integrated into the main pipeline or run as a separate post-processing stage? → A: Separate post-processing stage. Audio generation runs after learning items and content units are complete and validated, allowing ops to control which items/content get audio and how many versions to generate per item.
- Q: How should audio file versioning be handled when generating multiple versions for manual selection? → A: Store all versions with suffix pattern `{uuid}_v1.{format}`, `{uuid}_v2.{format}`, `{uuid}_v3.{format}`. The selected version's URL is saved to the learning item/content unit metadata. Unselected versions remain in storage for potential future use.
- Q: What audio format and quality settings should be used? → A: Default is `opus_48000_32` (Opus codec, 48kHz, 32kbps) for optimal quality-to-size ratio. Alternative `mp3_44100_64` (MP3, 44.1kHz, 64kbps) available for comparison testing. Format is configurable per batch.
- Q: Should audio files be uploaded directly to R2 or stored locally first? → A: Store locally first in `havachat-knowledge/generated content/{Language}/{Level}/02_Generated/audio/{category}/` (e.g., `Chinese/HSK1/02_Generated/audio/vocab/`) for testing and review, then sync to R2 bucket via separate sync command. This allows ops to validate audio before publishing.
- Q: How are learning items and content units stored? → A: Consolidated JSON files per category: `vocab.json`, `grammar.json`, `conversations.json`, etc. (not individual item files). Each file contains array of items. Enables efficient batch loading and updates.

### Session 2026-01-31

- Q: Which aspects should the LLM judge evaluate for conversation quality? → A: Comprehensive evaluation (naturalness, level fit, grammar, vocabulary diversity, cultural accuracy, engagement - 6+ dimensions). Each dimension receives a score and explanation to provide actionable feedback for human reviewers.
- Q: When should the system push conversation data to the Notion database? → A: Immediately after LLM quality judge completes (before any audio generation). This enables parallel workflows where human reviewers can start evaluating content while the system prepares for audio generation of approved items.
- Q: What status transitions should the system automatically handle vs. require human action? → A: System auto-transitions: Ready for Audio → OK (after audio upload). Human controls all other transitions (Not started → Ready for Review, Ready for Review → Ready for Audio/Rejected/Reviewing). This keeps humans in control of quality gates while automating technical tasks.
- Q: How should the follow-up CLI detect changes in the Notion database? → A: Manual trigger - ops runs CLI with --check-notion flag when ready to process changes. This avoids unnecessary API polling and gives ops full control over processing timing and batch sizes.
- Q: When user requests audio regeneration for a specific title, how should the system locate and update the item? → A: Search both Notion and local JSON files, regenerate audio, update local JSON + sync to Notion if item exists there. This handles edge cases like items not yet pushed to Notion or needing re-push after regeneration.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Import and Enrich Official Vocabulary Lists (Priority: P1)

Content ops imports an official HSK1 vocabulary list (TSV with Word and Part of Speech columns) and runs the enrichment script. The system identifies missing fields, invokes LLM to generate explanations, examples, romanization, and sense glosses, validates the output against the schema, and writes enriched learning items to `havachat-knowledge/generated content/Chinese/HSK1/vocab/`.

**Why this priority**: Vocabulary is the foundation of all learning content. Without enriched vocab items, no other pipeline stages can proceed. This delivers immediate value by transforming raw word lists into structured, searchable learning resources.

**Independent Test**: Can be fully tested by providing an official vocab TSV, running the enrichment script, and verifying that output JSON files contain all required fields (target_item, definition, examples, romanization, level_system, level_min/max) and pass schema validation.

**Acceptance Scenarios**:

1. **Given** an official HSK1 vocab TSV with columns "Word, Part of Speech", **When** the ChineseVocabEnricher runs, **Then** each word is enriched one-by-one via individual LLM calls, generating definition, 2-3 examples, pinyin romanization, sense_gloss for each item, and written to `Chinese/HSK1/vocab/item-{uuid}.json`
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

1. **Given** an official HSK1 grammar CSV with columns "类别,类别名称,细目,语法内容" where 类别="句型", 细目="是...的", **When** the ChineseGrammarEnricher runs, **Then** each grammar pattern is enriched one-by-one via individual LLM calls, creating a learning item with target_item="是...的", definition describing form and use, 2-3 contextual examples, and category="grammar"
2. **Given** a Japanese JLPT N5 grammar TSV with columns "Type, Rule, Example" where Type="Basic Particles", Rule="は (wa) - Topic Marker", Example="私は学生です。", **When** the JapaneseGrammarEnricher runs, **Then** the existing example is preserved and each grammar item is enriched one-by-one with definition, additional usage examples, common learner errors, and the particle "は" is stored as target_item
3. **Given** a French A1 grammar markdown with category "## A1: Pronouns" and item "Il/elle/ils/elles = it/he/she/they (French Subject Pronouns)", **When** the FrenchGrammarEnricher runs, **Then** each grammar item is enriched one-by-one, parsing the title into target_item="Il/elle/ils/elles", generating definition for form/usage, 2-3 contextual examples, and category="grammar"
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

1. **Given** complete Chinese HSK2 learning items (vocab, grammar, pronunciation, idioms, functional, cultural) have been generated, **When** content generation runs with topic="Food", num-conversations=5, num-stories=5, **Then** 5 conversations (6-8 turns each) and 5 stories (200-300 words) are generated using items from ALL categories, each with explicit learning_item_ids[] and a 3-8 word scenario name (e.g., "Ordering at a casual restaurant", "Shopping for groceries")
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

### User Story 5 - Generate Audio Using ElevenLabs TTS (Priority: P2)

Content ops runs audio generation on completed learning items or content units. The system processes items by category (e.g., all HSK1 vocab, then grammar separately), generates 1-3 audio versions per item using configured ElevenLabs voice IDs, uploads files to Cloudflare R2, and saves the audio URLs to each item's metadata. For conversation content units with multiple speakers, the system uses voice pairs configured for dialogue.

**Why this priority**: Audio enhances learning value significantly but depends on completed, validated content (P1/P2 dependencies). Can be added iteratively to existing content after text validation passes. Separate generation per category allows ops to control batch sizes and costs.

**Independent Test**: Can be fully tested by providing a batch of learning items (e.g., 50 vocab items), running audio generation with `--versions=2`, verifying that 2 MP3 files are generated and uploaded to R2 for each item, URLs are saved to item metadata, and ops can manually select the best version.

**Acceptance Scenarios**:

1. **Given** 50 completed Chinese HSK1 vocab learning items in `vocab.json`, **When** audio generation runs with `--category=vocab --versions=1 --voice-id=voice-zh-female-01 --format=opus_48000_32`, **Then** 50 audio files are generated (target_item text spoken), saved locally to `havachat-knowledge/generated content/Chinese/HSK1/02_Generated/audio/vocab/{uuid}.opus`, and file paths saved to `learning_items_media.json` with each item's `audio_local_path` field
2. **Given** the same 50 vocab items, **When** audio generation runs with `--versions=3`, **Then** 3 versions per item are generated (`{uuid}_v1.opus`, `{uuid}_v2.opus`, `{uuid}_v3.opus`), saved locally, and the item's metadata in `learning_items_media.json` includes `audio_versions: [{version: 1, local_path: "...", url: null, selected: false}, {version: 2, local_path: "...", url: null, selected: false}, {version: 3, local_path: "...", url: null, selected: false}]`
3. **Given** a French A1 conversation content unit with 8 turns (4 per speaker), **When** audio generation runs with `--voice-config=conversation_2_1` (which maps to 2-speaker voice pair group 1), **Then** audio is generated with alternating voices matching speaker labels, saved locally as `havachat-knowledge/generated content/French/A1/02_Generated/audio/conversations/{uuid}.opus`, and the content unit's `has_audio` field is set to `true` with `audio_local_path` populated in `content_units_media.json`
4. **Given** 20 Japanese JLPT N5 grammar items, **When** audio generation runs with `--category=grammar --batch-size=10 --format=mp3_44100_64`, **Then** the script processes 10 items at a time (two batches), preventing API rate limit issues, and all 20 items receive audio local paths in `learning_items_media.json` as MP3 files for comparison testing
5. **Given** audio generation completes for a batch, **When** ops reviews the local audio files in `havachat-knowledge/generated content/{Language}/{Level}/02_Generated/audio/{category}/`, **Then** they can update selected versions by running `python src/pipeline/audio_selection.py --item-id={uuid} --selected-version=2`, which updates the item's metadata in `learning_items_media.json` to reference `_v2.{format}` and sets `selected: true` for that version
6. **Given** selected audio files validated locally, **When** ops runs `python src/pipeline/audio_sync.py --language={lang} --category={cat}`, **Then** selected audio files are uploaded to R2 at `{language}/{category}/{uuid}.{format}`, URLs are updated in `learning_items_media.json` and `content_units_media.json`, and sync progress is logged
7. **Given** an audio generation request fails (ElevenLabs API error, file write failure), **When** retry logic executes, **Then** the system retries up to 3 times, and if still failing, logs the error to `{language}/audio_generation_failures.jsonl` with item_id, error details, and timestamp
8. **Given** different learning item categories (vocab, grammar, idioms), **When** audio is generated separately per category via `--category` flag, **Then** ops can control generation order and volume, and the system tracks per-category progress in `audio_generation_progress.json`

---

### User Story 6 - LLM Quality Judge and Notion Integration (Priority: P2)

Content ops generates conversations and runs the quality gate with LLM judge. The system evaluates each conversation across 6 dimensions (naturalness, level appropriateness, grammatical correctness, vocabulary diversity, cultural accuracy, engagement), provides scores and explanations, generates a proceed/review recommendation, and pushes conversation details with LLM comments to the Notion database for human review. Human reviewers update status in Notion, and ops runs a follow-up CLI to process approved items (generate audio) or rejected items (mark status locally).

**Why this priority**: Quality gates with human-in-the-loop review are constitutional requirements (Principle II). LLM judge provides consistent first-pass evaluation across all content while human reviewers make final quality decisions. Notion integration enables parallel workflows where review happens independently of audio generation.

**Independent Test**: Can be fully tested by providing generated conversations, running LLM judge, verifying comprehensive evaluation output (6 scores + explanations + recommendation), pushing to Notion with correct data structure, manually updating Notion status, then running follow-up CLI to verify audio generation for "Ready for Audio" items and local status updates for "Rejected" items.

**Acceptance Scenarios**:

1. **Given** a generated Chinese HSK1 conversation, **When** LLM quality judge runs, **Then** it produces a structured evaluation with 6 dimensions: naturalness (1-10 score + explanation), level_appropriateness (1-10 + explanation), grammatical_correctness (1-10 + explanation), vocabulary_diversity (1-10 + explanation), cultural_accuracy (1-10 + explanation), engagement (1-10 + explanation), plus overall_recommendation ("proceed" or "review") with justification
2. **Given** LLM judge completes evaluation, **When** Notion integration runs, **Then** a new row is created in the Notion database (https://www.notion.so/amika-hq/2f9dd30aa93a80a99e11dce4c26c3863) with fields: Type="conversation", Title=conversation title, Description=conversation description, Topic=topic name, Scenario=scenario name, Script=formatted conversation text with speaker names ("Speaker-1-name: ...\nSpeaker-2-name: ..."), Translation=formatted translation with same format, Audio=empty, LLM Comment=JSON string containing all 6 scores and explanations, Human Comment=empty, Status="Not started"
3. **Given** 5 conversations pushed to Notion with Status="Not started", **When** human reviewers evaluate and update some to Status="Ready for Audio" and others to Status="Rejected", **Then** the Notion database reflects these status changes and Human Comment fields contain reviewer notes
4. **Given** Notion database has items with Status="Ready for Audio" and Status="Rejected", **When** ops runs `python src/pipeline/notion_sync.py --check-notion`, **Then** the CLI fetches all rows, identifies status changes since last sync, generates audio for "Ready for Audio" items (using conversation voice config), uploads audio files to Notion Audio field, updates Notion Status to "OK", and updates local conversation JSON files with status="rejected" for "Rejected" items
5. **Given** ops requests audio regeneration for a specific conversation, **When** running `python src/pipeline/notion_sync.py --regenerate-audio --title="Shopping at the Supermarket"`, **Then** the CLI searches both Notion (by Title field) and local conversations.json files, finds the matching conversation, regenerates audio with same voice config, uploads to R2, updates Notion Audio field with new URL, updates local content_units_media.json with new audio_url, and sets Notion Status to "OK"
6. **Given** LLM judge evaluation produces overall_recommendation="review" (scores below threshold), **When** pushing to Notion, **Then** the system still creates the Notion row with all details but logs a warning that human review is strongly recommended before audio generation
7. **Given** duplicate titles exist in Notion database, **When** ops runs `--regenerate-audio --title="Meeting New People"`, **Then** CLI detects multiple matches and prompts user to select by providing list with additional context (language, level, topic, Notion row ID) or abort operation

---

### User Story 7 - Run QA Gates and Generate Validation Report (Priority: P2)

Content ops runs the QA gate script on a batch of content (e.g., all French A1 conversations for "Food" topic). The system executes presence checks (learning items appear in text), duplication checks (no near-duplicate items), link correctness (all references valid), question answerability (answers derivable), and generates a validation report with pass/fail status and flagged items for manual review.

**Why this priority**: QA gates are constitutional requirements (Principle II). They must run before any content is published. Higher priority than question generation because gates validate all content types (vocab, grammar, conversations), not just questions.

**Independent Test**: Can be fully tested by running the QA gate script on a test batch with known violations (duplicate learning items, invalid references, unanswerable questions) and verifying that the validation report correctly identifies all failures.

**Acceptance Scenarios**:

1. **Given** a batch of French A1 content, **When** the presence check runs, **Then** every learning_item_id referenced in content segments exists in the learning item directories (vocab/, grammar/, pronunciation/, idioms/, etc.) and the target_item appears in the segment text (using French tokenization)
2. **Given** two learning items with identical lemma "banco" but different sense_gloss ("bank financial" vs "bench seat"), **When** the duplication check runs, **Then** both items pass (sense disambiguation prevents collision)
3. **Given** a question with answer "tomorrow morning", **When** the answerability check runs, **Then** the system verifies the phrase appears in or is clearly inferrable from the conversation text
4. **Given** a validation report with 95% pass rate (5% flagged for review), **When** reviewed by ops, **Then** the report includes specific line references, failure reasons, and suggested fixes for each flagged item

---

### Edge Cases

- **Language-specific source formats**: 
  - **Vocab**: Japanese JSON has `{word, meaning, furigana, romaji, level}` while French might be CSV `{Mot, Définition, Exemple}` and Chinese TSV `{Word, Part of Speech}`. 
  - **Grammar**: Chinese CSV has hierarchical categories `{类别,类别名称,细目,语法内容}`, Japanese TSV has `{Type, Rule, Example}`, French markdown has category headers (`## A1: Pronouns`) followed by descriptive title lists. Each language subclass handles its own source format without requiring generic configuration.
- **Pre-existing fields**: Japanese vocab already includes romanization (furigana/romaji) and English meanings; Japanese grammar includes examples with romaji and translations. Enrichment subclasses must preserve these and only generate missing fields (additional examples, sense_gloss if polysemy detected, definition for grammar).
- **Grammar hierarchical parsing**: French grammar titles contain the pattern itself plus explanation (e.g., "Il/elle/ils/elles = it/he/she/they (French Subject Pronouns)"). The FrenchGrammarEnricher must parse title to extract target_item ("Il/elle/ils/elles") and category hint ("Subject Pronouns").
- **Missing romanization**: For Chinese, if source TSV lacks Pinyin, the ChineseVocabEnricher LLM must generate it; validation must enforce presence before writing output.
- **Polysemous words**: "banco" (bank/bench), "bat" (animal/sports equipment), Japanese "bank" (financial vs riverbank) must result in separate learning items with distinct sense_gloss to avoid quiz ambiguity.
- **LLM generation failures**: If LLM fails to generate required fields after 3 retries, the item must be flagged for manual review with error context (not silently dropped).
- **Content similarity edge cases**: If similarity score is 75-85% (borderline), the system should present both options to ops: reuse existing or generate new variant.
- **Broken learning item references**: If a content unit references a learning item ID that doesn't exist (e.g., item was deleted), the link validation must catch and report it.
- **Question difficulty misalignment**: If an A1-level conversation has a generated question requiring B1-level inference, the difficulty validation must flag it.
- **Cross-language contamination**: Japanese vocab must not appear in French content directories; validation must check language field matches directory structure.
- **Audio generation voice pairing**: For conversations with 2+ speakers, voice configuration must specify complete speaker mapping (e.g., conversation_2_1 requires both speaker_1 and speaker_2 voice IDs). If voice config is missing or incomplete, audio generation must fail with clear error message listing missing speaker mappings rather than using mismatched voices.
- **Audio generation retry failures**: If ElevenLabs API consistently fails for a specific item (e.g., text contains unsupported characters, voice ID invalid), system must log detailed error and skip item after 3 retries rather than blocking entire batch.
- **R2 sync failures**: If Cloudflare R2 upload fails during sync due to network issues or permission errors, system must retry with exponential backoff, log failures separately from generation failures, and continue with remaining files rather than aborting entire sync batch.
- **Local storage cleanup**: After successful R2 sync and validation, ops may want to archive or delete local audio files to save disk space. System should support `--cleanup-local` flag on sync command to optionally remove local files after successful upload.
- **Audio version selection edge case**: If ops manually deletes a selected audio file from local storage or R2, the learning item's `audio_local_path` or `audio_url` becomes broken. System should detect broken paths during validation (file exists check for local, HTTP 404 for R2) and flag for re-generation.
- **Large batch memory handling**: For batches >1000 items, audio generation must process in configurable sub-batches to prevent memory exhaustion and allow progress checkpointing.
- **Multi-language voice configuration**: Each language requires different voice IDs. System must validate voice config exists for target language and requested type (single vs conversation_N_M) before starting batch (fail fast) rather than discovering mismatch mid-generation.
- **Audio format migration**: If ops needs to regenerate all audio from opus to mp3 (or vice versa), system should support batch re-generation with `--force-regenerate --format=mp3_44100_64` flag that overwrites existing files and updates media JSON with new format and paths.
- **LLM judge evaluation inconsistency**: If LLM judge scores are contradictory (e.g., naturalness=9 but engagement=2 for same conversation), system should flag inconsistency in LLM Comment and recommend human review regardless of overall_recommendation value.
- **Notion API failures**: If Notion API is unavailable or rate-limited during push, system must retry with exponential backoff (3 attempts), queue failed items locally in `notion_push_queue.jsonl`, and allow manual retry via `--retry-failed-pushes` flag.
- **Notion row ID tracking**: After creating Notion rows, system must track mapping between local content_id and Notion page_id in `notion_mapping.json` to enable updates (e.g., audio URL updates after regeneration) rather than creating duplicate rows.
- **Audio upload to Notion**: Notion Audio field accepts file URLs or file attachments. System should upload audio files to R2 first, then store R2 public URL in Notion Audio field (not binary upload to Notion) for bandwidth efficiency.
- **Script/Translation formatting edge cases**: If conversation has 3+ speakers or complex turn-taking (interruptions, overlapping speech), system should maintain clear speaker labels in formatted output: "Speaker-1-name: ...\nSpeaker-2-name: ...\nSpeaker-3-name: ...". Translation format must match script format line-by-line.
- **Rejected item cascading effects**: If a conversation is marked "Rejected" in Notion, and that conversation is the only usage of certain learning items, usage_stats.json should be updated to decrement appearances_count for those items (maintain accurate usage tracking).
- **Manual Notion edits**: If human reviewers edit Script or Translation directly in Notion, those changes are NOT synced back to local JSON files (Notion is review-only, not source-of-truth). System should log warning if detecting Notion edits to Script/Translation fields during sync.
- **Title ambiguity in regeneration**: If `--regenerate-audio --title` matches multiple conversations (same title, different languages/levels), CLI must present disambiguation menu showing: language, level, topic, current Status, Notion row ID, and local file path for user selection.
- **Notion database schema mismatch**: Before any push operation, system should validate Notion database has expected columns (Type, Title, Description, Topic, Scenario, Script, Translation, Audio, LLM Comment, Human Comment, Status) and their types match. Fail fast with clear error if schema is incompatible.

## Requirements *(mandatory)*

### Functional Requirements

**Pipeline Architecture:**

- **FR-001**: Each pipeline stage (vocab enrichment, grammar enrichment, content generation, question generation, QA gates) MUST be executable independently via CLI with `python src/pipeline/{stage_name}.py --config {config.json}`
- **FR-002**: All scripts MUST use `uv` package manager and Python >=3.14 with type hints on all public functions
- **FR-003**: Pipeline stages MUST read input from configurable paths and write output to `havachat-knowledge/generated content/{language}/{level}/{content_type}/` following the directory structure convention (e.g., `vocab/`, `grammar/`, `conversations/`, `questions/`)

**Input Handling:**

- **FR-004**: Enrichment scripts MUST use language-specific subclasses (e.g., `JapaneseVocabEnricher`, `ChineseVocabEnricher`, `FrenchVocabEnricher`) where each subclass implements its own file parsing logic, field mapping, and validation rules specific to that language's source format
- **FR-005**: Each language subclass MUST detect which required fields are already present in the source data (e.g., Japanese already has furigana+romaji, French may have definitions) and only invoke LLM to generate missing required fields
- **FR-006**: Language subclasses MUST enforce language-specific validation: Chinese/Japanese subclasses MUST validate romanization presence (Pinyin/Romaji); English/French/French subclasses MUST NOT require romanization. All subclasses MUST use shared validation utilities for common rules (level_system validation, level_min <= level_max ordinal comparison).

**LLM Integration:**

- **FR-007**: Each language subclass MUST have its own prompt templates in `src/pipeline/prompts/{language}/{stage_name}_enrichment_prompts.py` (e.g., `prompts/japanese/vocab_enrichment_prompts.py`, `prompts/chinese/vocab_enrichment_prompts.py`, `prompts/japanese/grammar_enrichment_prompts.py`) with language-specific instructions and examples. Template structure will be provided as part of implementation. Learning items are enriched one-by-one via individual LLM calls.
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
- **FR-035-QA-JUDGE**: QA gate script MUST include LLM quality judge evaluation for conversations with 6 dimensions: naturalness (1-10 + explanation), level_appropriateness (1-10 + explanation), grammatical_correctness (1-10 + explanation), vocabulary_diversity (1-10 + explanation), cultural_accuracy (1-10 + explanation), engagement (1-10 + explanation), plus overall_recommendation ("proceed" or "review") with justification
- **FR-036-QA-JUDGE**: LLM judge evaluation output MUST be structured as JSON with schema: `{naturalness: {score: int, explanation: string}, level_appropriateness: {score: int, explanation: string}, grammatical_correctness: {score: int, explanation: string}, vocabulary_diversity: {score: int, explanation: string}, cultural_accuracy: {score: int, explanation: string}, engagement: {score: int, explanation: string}, overall_recommendation: string, recommendation_justification: string}` and stored in conversation metadata as `llm_judge_evaluation` field

**Notion Integration:**

- **FR-037-NOTION**: System MUST push conversation data to Notion database (https://www.notion.so/amika-hq/2f9dd30aa93a80a99e11dce4c26c3863) immediately after LLM quality judge completes, creating new rows with fields: Type="conversation" (or "story"), Title=content title, Description=content description, Topic=topic_name, Scenario=scenario_name, Script=formatted conversation text ("Speaker-1: ...\nSpeaker-2: ..."), Translation=formatted translation (same format as Script), Audio=empty (populated later), LLM Comment=JSON string of judge evaluation, Human Comment=empty, Status="Not started"
- **FR-038-NOTION**: Notion push operation MUST implement retry logic (3 attempts with exponential backoff), queue failed pushes to `notion_push_queue.jsonl`, and track content_id to Notion page_id mapping in `notion_mapping.json` for future updates
- **FR-039-NOTION**: System MUST validate Notion database schema before any push operation: verify existence and types of columns (Type, Title, Description, Topic, Scenario, Script, Translation, Audio, LLM Comment, Human Comment, Status); fail fast with clear error message if schema mismatch detected
- **FR-040-NOTION**: Notion sync CLI MUST be executable via `python src/pipeline/notion_sync.py --check-notion` to manually trigger processing of Notion status changes; no automatic polling or webhook integration required
- **FR-041-NOTION**: When ops runs `--check-notion`, system MUST fetch all Notion rows, identify items with Status="Ready for Audio" or Status="Rejected" that haven't been processed (by checking last_synced_at timestamp in notion_mapping.json), process each item: for "Ready for Audio" generate audio, upload to R2, update Notion Audio field with R2 URL, update Notion Status to "OK"; for "Rejected" update local conversation JSON status="rejected" and update usage_stats.json to decrement appearances_count for linked learning items
- **FR-042-NOTION**: Audio regeneration MUST be executable via `python src/pipeline/notion_sync.py --regenerate-audio --title="{conversation_title}"` which searches both Notion (Title field) and local conversations.json/stories.json files, handles duplicate title disambiguation by prompting user with list (language, level, topic, Status, Notion page_id, local path), regenerates audio with same voice config, uploads to R2, updates Notion Audio field and Status="OK", updates local content_units_media.json with new audio_url
- **FR-043-NOTION**: System MUST log warning if detecting human edits to Script or Translation fields in Notion during sync (field content differs from local JSON source); Notion is review interface only, not source-of-truth for content

**Error Handling & Observability:**

- **FR-044**: All scripts MUST log to structured JSON format (timestamp, stage, action, status, error_details, item_id, topic) for debugging and quality monitoring
- **FR-045**: LLM generation failures MUST create a manual review queue file `{language}/{level}/manual_review/{stage_name}_failures.jsonl` with failed items and error context
- **FR-046**: System MUST track and report batch processing metrics: items processed, success rate, average LLM tokens per item, total processing time, chain-of-thought steps executed

**Database & Search Infrastructure:**

- **FR-047**: System MUST implement database partitioning by language for both Meilisearch (separate indexes per language: `learning_items_zh`, `scenarios_ja`, etc.) and Postgres (table partitioning or separate schemas per language). Implementation includes index creation scripts, schema setup, and partition configuration validation.

**Audio Generation:**

- **FR-039**: Audio generation MUST be executable independently via CLI with `python src/pipeline/audio_generator.py --config {config.json} --category {vocab|grammar|idioms|functional|cultural|pronunciation|writing_system|misc|conversations|stories}` allowing per-category batch control
- **FR-040**: Audio generation script MUST accept parameters: `--language`, `--level`, `--category`, `--batch-size` (default: 50), `--versions` (1-3, default: 1), `--format` (opus_48000_32|mp3_44100_64, default: opus_48000_32), `--voice-id` (single voice for learning items) or `--voice-config` (conversation config like conversation_2_1 for multi-speaker)
- **FR-041**: For learning items, audio generation MUST synthesize the `target_item` text using ElevenLabs TTS API (https://elevenlabs.io/docs/api-reference/text-to-speech) with specified voice ID, output format Opus 48kHz 32kbps (default) or MP3 44.1kHz 64kbps (comparison), and save locally to `havachat-knowledge/generated content/{Language}/{Level}/02_Generated/audio/{category}/{uuid}.{opus|mp3}` (e.g., `Chinese/HSK1/02_Generated/audio/vocab/abc123.opus`)
- **FR-042**: For content units (conversations/stories), audio generation MUST synthesize the full text with speaker-aware voice mapping: conversations use voice configuration (e.g., conversation_2_1 maps to 2-speaker group 1 with speaker_1 and speaker_2 voice IDs), stories use single voice. Voice mapping loaded from `voice_config.json`.
- **FR-043**: Generated audio files MUST be saved locally first at paths: `havachat-knowledge/generated content/{Language}/{Level}/02_Generated/audio/{category}/{uuid}.{format}` (single version) or `{uuid}_v{N}.{format}` (multiple versions). Files remain local until synced to R2 via separate sync command.
- **FR-044**: After successful local file write, learning item/content unit metadata MUST be updated in consolidated JSON files: `learning_items_media.json` or `content_units_media.json` with fields: single version writes `audio_local_path: "{Language}/{Level}/02_Generated/audio/{category}/{uuid}.{format}"` (e.g., `"Chinese/HSK1/02_Generated/audio/vocab/abc123.opus"`), `audio_url: null` (until synced), `has_audio: true`; multiple versions writes `audio_versions: [{version: 1, local_path: "...", url: null, selected: false}, ...]` array
- **FR-045**: Audio generation MUST implement retry logic: attempt ElevenLabs API call → retry up to 3 times on failure (rate limit, network error) with exponential backoff → log failure to `{language}/audio_generation_failures.jsonl` if still failing
- **FR-046**: Audio generation MUST validate voice configuration before processing batch: for learning items, check voice ID exists in `voice_config.json` and supports target language; for conversations, check voice config group (e.g., conversation_2_1) has all required speaker voice IDs → fail fast with error message if invalid
- **FR-047**: System MUST track audio generation progress in `{language}/audio_generation_progress.json` per category with fields: category, language, level, total_items, processed_count, failed_count, format, last_updated, allowing resume after interruption
- **FR-048**: Audio selection tool MUST allow ops to mark selected version via `python src/pipeline/audio_selection.py --item-id {uuid} --selected-version {N}` which updates item's `audio_local_path` in `learning_items_media.json` to selected version and sets `audio_versions[N].selected: true`
- **FR-049**: R2 sync tool MUST be separate command: `python src/pipeline/audio_sync.py --language {lang} --category {cat} [--dry-run]` uploads selected local audio files to R2 at `{language}/{category}/{uuid}.{format}`, updates `audio_url` fields in media JSON files, implements retry logic (3 attempts with exponential backoff), and logs sync results
- **FR-050**: Audio generation for large batches (>1000 items) MUST support checkpoint-based resumption: process in sub-batches (configurable via `--checkpoint-interval`), save progress after each sub-batch, allow `--resume-from-checkpoint` flag to skip already-processed items
- **FR-051**: QA validation MUST include audio file checks: for items with `has_audio: true`, verify local file exists at `audio_local_path`, file size >5KB, and valid audio format; after R2 sync, verify `audio_url` is accessible (HTTP 200); flag missing/broken files for re-generation
- **FR-052**: Voice configuration MUST be stored in `voice_config.json` at repo root with schema: `{language: string, voices: [{voice_id: string, name: string, type: string, description: string, supported_languages: string[], comment: string}]}` where type follows pattern "single" or "conversation_{total_speakers}_{group_id}_speaker_{speaker_number}" (e.g., "conversation_2_1_speaker_1" for 2-speaker conversation group 1 speaker 1)
- **FR-053**: Learning items and content units MUST be stored in consolidated JSON files: `{language}/{level}/vocab.json`, `grammar.json`, `idioms.json`, `conversations.json`, `stories.json` containing arrays of items, enabling efficient batch loading. Media metadata (audio paths/URLs) stored separately in `learning_items_media.json` and `content_units_media.json` with fields: `{item_id: string, audio_local_path: string, audio_url: string, audio_versions: [...], has_audio: bool}`

### Key Entities

- **Learning Item**: Atomic pedagogical unit (vocabulary, grammar, pronunciation, idioms, functional language, cultural notes, writing system, miscellaneous categories) with fields: id, language, category, target_item, definition, examples, romanization (for zh/ja), level_system, level_min/max, sense_gloss (for polysemy), lemma, pos, aliases, created_at, version. Stored in consolidated JSON files: `{Language}/{Level}/vocab.json`, `grammar.json`, `idioms.json`, etc., each containing array of items. Audio metadata stored separately in `{Language}/{Level}/learning_items_media.json` with fields per item: `{item_id, audio_local_path, audio_url, audio_versions: [{version, local_path, url, selected}], has_audio, audio_format}`. Audio files stored at `{Language}/{Level}/02_Generated/audio/{category}/`.

- **Content Unit**: Conversation or story containing multiple segments. Fields: id, language, type (conversation|story), title, description, text, segments[] (each with type, speaker, text, learning_item_ids, start/end times), learning_item_ids[] (all featured items), topic_name, scenario_name (3-8 word description assigned by LLM), level_system, level_min/max, word_count, estimated_reading_time_seconds, has_questions, publishable, chain_of_thought_metadata (initial_draft, critique, revisions_made), created_at, version. Stored in consolidated JSON files: `{Language}/{Level}/conversations.json` and `stories.json`, each containing array of content units. Audio metadata stored separately in `{Language}/{Level}/content_units_media.json` with fields per unit: `{content_id, audio_local_path, audio_url, audio_versions: [{version, local_path, url, selected}], has_audio, audio_format, voice_config_used}`. Audio files stored at `{Language}/{Level}/02_Generated/audio/conversations/` and `{Language}/{Level}/02_Generated/audio/stories/`.

- **Question Set**: Comprehension questions for a content unit. Fields: id, content_id (reference), segment_range, question_type (mcq|true_false|short_answer|summary), question_text, options[] (for MCQ), answer_key, rationale, difficulty, tags[] (inference, detail, main-idea), created_at, version. Stored as `{language}/{level}/questions/questions-{content_id}.json`.

- **Topic**: Broad thematic category (~200 total across all languages). Fields: id, name, aliases[], language (or "universal"), parent_topic_id (optional). Example: "food", "travel", "work", "social-interaction".

- **Scenario**: Concrete situation within a topic (~2000 total). Fields: id, name, aliases[], topic_id (parent), language (or "universal"), description. Example: "ordering at restaurant", "airport check-in", "job interview".

- **Usage Metadata**: Tracks how often each learning item appears in published content. Fields: learning_item_id, appearances_count, last_used_content_id, last_updated. Stored in `{language}/{level}/usage_stats.json` as array.

- **Validation Report**: Output of QA gates for a batch. Fields: batch_id, language, level, timestamp, total_items, passed_count, failed_count, flagged_items[] (each with item_id, item_type, failure_reason, line_reference, suggested_fix), summary_stats (pass_rate_percent, most_common_failures). Stored as `{language}/{level}/qa_reports/report-{timestamp}.json` and `report-{timestamp}.md`.

- **LLM Judge Evaluation**: Quality assessment output for a conversation or story. Fields: content_id, naturalness (score 1-10, explanation string), level_appropriateness (score 1-10, explanation), grammatical_correctness (score 1-10, explanation), vocabulary_diversity (score 1-10, explanation), cultural_accuracy (score 1-10, explanation), engagement (score 1-10, explanation), overall_recommendation ("proceed"|"review"), recommendation_justification (string), evaluated_at (timestamp). Stored as `llm_judge_evaluation` field within Content Unit JSON.

- **Notion Database Row**: External review record for human reviewers. Fields match Notion database schema: Type (conversation|story), Title (content title), Description (content description), Topic (topic_name), Scenario (scenario_name), Script (formatted text with speaker labels: "Speaker-1: ...\nSpeaker-2: ..."), Translation (formatted translation matching Script format), Audio (R2 URL or empty), LLM Comment (JSON string of LLM Judge Evaluation), Human Comment (reviewer notes), Status (Not started|Ready for Review|Reviewing|Ready for Audio|Rejected|OK). Each row linked to local content via notion_mapping.json.

- **Notion Mapping**: Tracks relationship between local content and Notion database rows. Fields: content_id (local UUID), notion_page_id (Notion row ID), language, level, type (conversation|story), title, last_pushed_at (timestamp), last_synced_at (timestamp), status_in_notion (current Status field value), status_in_local (local JSON status field). Stored as `notion_mapping.json` at repo root as array of mappings.

- **Notion Push Queue**: Failed Notion push operations awaiting retry. Fields: content_id, type, title, language, level, attempt_count, last_error, failed_at, payload (full Notion row data). Stored as `notion_push_queue.jsonl` (newline-delimited JSON) at repo root.

- **Audio Generation Progress**: Tracks progress for resumable batch processing. Fields: category, language, level, total_items, processed_count, failed_count, checkpoint_interval, last_checkpoint_item_id, last_updated, status (in_progress|completed|failed). Stored as `{language}/{level}/audio_generation_progress.json`.

- **Voice Configuration**: Maps languages to ElevenLabs voice IDs with rich metadata. Fields: language, voices[] where each voice has: voice_id (ElevenLabs ID), name (human-readable), type ("single" or "conversation_{total_speakers}_{group_id}_speaker_{speaker_number}"), description (voice characteristics), supported_languages[] (array of ISO codes), comment (optional notes). Stored as `voice_config.json` at repo root. Example:
  ```json
  {
    "zh": {
      "voices": [
        {
          "voice_id": "21m00Tcm4TlvDq8ikWAM",
          "name": "Rachel - Calm Female",
          "type": "single",
          "description": "Calm, clear female voice suitable for educational content",
          "supported_languages": ["zh", "zh-CN"],
          "comment": "Best for vocab and grammar items"
        },
        {
          "voice_id": "pNInz6obpgDQGcFmaJgB",
          "name": "Adam - Conversational Male",
          "type": "conversation_2_1_speaker_1",
          "description": "Natural conversational male voice",
          "supported_languages": ["zh", "zh-CN"],
          "comment": "Pair with speaker_2 for dialogues"
        },
        {
          "voice_id": "EXAVITQu4vr4xnSDxMaL",
          "name": "Bella - Friendly Female",
          "type": "conversation_2_1_speaker_2",
          "description": "Warm, friendly female voice",
          "supported_languages": ["zh", "zh-CN"],
          "comment": "Pair with speaker_1 for dialogues"
        }
      ]
    }
  }
  ```

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
- **SC-014**: Audio generation for 500 learning items with `--versions=1 --format=opus_48000_32` completes within 30 minutes (including ElevenLabs API calls, local file writes, metadata updates), with >98% success rate and <2% requiring retry or manual review
- **SC-015**: Audio generation with `--versions=3` produces 3 distinct audio files per item (verifiable via different file sizes/durations), saves all locally with correct naming pattern `{uuid}_v{N}.{format}`, and updates `learning_items_media.json` with all 3 local paths
- **SC-016**: Voice configuration validation: 100% of conversation audio generation requests validate complete voice config (e.g., conversation_2_1 has both speaker_1 and speaker_2 voice IDs) before generation starts, preventing incomplete or mismatched voice pairs
- **SC-017**: Audio file validation: >99% of items with `has_audio: true` have valid local files at `audio_local_path` (file exists, size >5KB, valid format header); after R2 sync, >99% have accessible URLs (HTTP 200) with matching content-type (audio/opus or audio/mpeg)
- **SC-018**: Audio generation resumption: given 1000-item batch interrupted at 600 items, `--resume-from-checkpoint` flag successfully skips processed items and continues from item 601, completing remaining 400 items without re-generating earlier items
- **SC-019**: Audio sync workflow: ops can review all locally generated audio, select best versions via audio_selection.py, then run audio_sync.py to upload only selected versions to R2, updating URLs in media JSON files
- **SC-020**: Audio generation cost tracking: structured logs capture ElevenLabs API character usage per item and audio format used, enabling ops to calculate per-item cost and compare opus vs mp3 efficiency for budget planning
- **SC-021**: Format comparison: ops can generate parallel batches with `--format=opus_48000_32` and `--format=mp3_44100_64` for same items, producing files like `{uuid}_opus.opus` and `{uuid}_mp3.mp3` for A/B quality testing before selecting default format- **SC-022-JUDGE**: LLM quality judge evaluates 100 Chinese HSK1 conversations and produces comprehensive 6-dimension assessments (naturalness, level_appropriateness, grammatical_correctness, vocabulary_diversity, cultural_accuracy, engagement) with >95% evaluation completion rate (no LLM failures or timeouts), average evaluation time <30 seconds per conversation
- **SC-023-JUDGE**: LLM judge overall_recommendation ("proceed" vs "review") correlates with human reviewer decisions: >80% agreement rate when comparing judge recommendations against final human Status field (Ready for Audio/OK vs Rejected) from sample of 50 reviewed conversations
- **SC-024-NOTION**: Notion push operation for 50 conversations completes within 5 minutes with >98% success rate, correctly populating all required fields (Type, Title, Description, Topic, Scenario, Script, Translation, LLM Comment) with properly formatted Script/Translation text ("Speaker-1: ...\nSpeaker-2: ...") and JSON-serialized LLM Comment
- **SC-025-NOTION**: Notion database schema validation detects missing/mismatched columns with 100% accuracy, failing fast with actionable error messages (e.g., "Missing required column: LLM Comment" or "Column type mismatch: Status expected Select, found Text") before any push operation
- **SC-026-NOTION**: Notion sync CLI (`--check-notion`) processes 20 items with mixed statuses (10 "Ready for Audio", 5 "Rejected", 5 unchanged) in single execution: generates audio and updates Notion for all 10 "Ready for Audio" items, updates local JSON status for all 5 "Rejected" items, skips 5 unchanged items, all within 15 minutes
- **SC-027-NOTION**: Audio regeneration by title (`--regenerate-audio --title="Shopping"`) handles duplicate titles: when 3 conversations match "Shopping", CLI presents disambiguation menu with language/level/topic/Status/Notion ID, accepts user selection, regenerates only selected item, updates both Notion and local files correctly
- **SC-028-NOTION**: Notion mapping tracking: notion_mapping.json maintains accurate content_id ↔ notion_page_id relationships with 100% consistency after 100 push/sync operations, enabling updates to existing rows rather than creating duplicates (verify by checking Notion database has exactly 100 unique rows for 100 conversations)
- **SC-029-NOTION**: Rejected item cascading: when conversation marked "Rejected" in Notion is synced, system correctly updates usage_stats.json to decrement appearances_count for all linked learning items, preventing rejected content from inflating usage metrics (verify with test: conversation has 15 items, rejection decrements all 15 counts)