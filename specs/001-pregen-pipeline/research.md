# Research & Technology Decisions

**Feature**: Pre-generation Pipeline for Learning Content  
**Phase**: 0 (Outline & Research)  
**Date**: 2026-01-26

## Decisions Summary

All NEEDS CLARIFICATION items from Technical Context have been resolved through specification review and technology research.

## 1. LLM Orchestration: LangGraph

**Decision**: Use LangGraph >=1.0.7 for multi-step batch pipelines

**Rationale**: 
- LangGraph provides state management for multi-step workflows (e.g., enrichment with validation → retry → flag for review)
- Built-in support for conditional edges (if validation passes → proceed, else → retry)
- Native async/parallel execution for processing multiple items
- Observable execution with checkpointing (resume failed batches)
- Constitutional requirement: batch can be slow, so graph overhead acceptable

**Alternatives Considered**:
- **Plain Python functions**: Simpler but no state management, retry logic would be manual, harder to debug multi-step failures
- **Celery task queues**: Good for distributed work but overkill for single-worker batch processing, adds complexity
- **Prefect/Airflow**: Better for scheduled DAGs, but we need interactive CLI tools with immediate feedback

**Implementation Notes**:
- Create `enrichment_graph.py` with nodes: load_source → parse_by_language → enrich_with_llm → validate_schema → (retry_loop or flag_for_review) → write_output
- Create `generation_graph.py` with nodes: check_similarity → (reuse_existing or generate_new) → link_items → validate_links → write_output

## 2. Structured LLM Outputs: Instructor

**Decision**: Use Instructor >=1.0.0 with Pydantic models for all LLM responses

**Rationale**:
- Forces LLM to return JSON matching Pydantic schemas (no parsing errors)
- Automatic retry with validation feedback ("field X is missing, regenerate")
- Type safety: vocabulary enrichment returns `EnrichedVocabItem` model, not raw dict
- Constitutional requirement: strict schema validation (FR-010, FR-011, FR-012)
- Works with OpenAI, Anthropic, local models (future-proof)

**Alternatives Considered**:
- **JSON mode + manual validation**: More error-prone, requires manual retry logic, no type hints
- **LangChain OutputParsers**: Less mature than Instructor, no Pydantic integration
- **Function calling API directly**: Requires more boilerplate, Instructor abstracts this cleanly

**Implementation Notes**:
- Define Pydantic models in `src/pipeline/validators/schema.py`: `LearningItem`, `ContentUnit`, `QuestionSet`
- Wrap LLM client in `src/pipeline/utils/llm_client.py`: `instructor.patch(openai.OpenAI())`
- Each enricher calls `client.chat.completions.create(response_model=EnrichedVocabItem, ...)`

## 3. Language-Specific Subclasses vs. Generic Config

**Decision**: Implement language-specific subclasses (e.g., `MandarinVocabEnricher`, `JapaneseVocabEnricher`, `FrenchVocabEnricher`) with their own parsing logic and LLM prompts

**Rationale** (from spec clarification):
- Source formats are fundamentally different:
  - Japanese JSON: `{word, meaning, furigana, romaji, level}`
  - French CSV: `{Mot, Définition, Exemple}`
  - Mandarin TSV: `{Word, Part of Speech}`
- Each language needs different LLM prompts:
  - Mandarin: "Generate Pinyin romanization and sense glosses"
  - Japanese: "Preserve existing furigana/romaji, only add examples"
  - French: "Preserve definitions, add contextual usage"
- Generic config would be complex (column mappings, conditional prompts per language)

**Alternatives Considered**:
- **Generic enricher with JSON config**: Too complex when formats are deeply different (CSV vs TSV vs JSON with nested fields)
- **Plugin system**: Overkill for 3 languages, subclasses are simpler

**Implementation Notes**:
- Base class `BaseEnricher` in `src/pipeline/enrichers/base.py` with abstract methods: `parse_source()`, `detect_missing_fields()`, `build_prompt()`, `validate_output()`
- Each subclass implements language-specific logic
- Prompts stored in `src/pipeline/prompts/{language}/vocab_prompts.py` as Python strings (easier to maintain than YAML)

## 4. Semantic Similarity for Content Reuse

**Decision**: Use sentence embeddings (sentence-transformers) to check for similar existing scenarios before generating new content

**Rationale**:
- FR-018 requires >85% similarity check to avoid duplicate conversations
- Embedding-based similarity is fast (<50ms for 1000 comparisons) and semantically accurate
- Can run locally (no API cost for similarity checks)
- Sentence-transformers has multilingual models (supports Mandarin, Japanese, French)

**Alternatives Considered**:
- **Keyword overlap**: Misses semantic similarity ("ordering food" vs "restaurant menu")
- **Exact string match**: Too strict, misses paraphrases
- **OpenAI embeddings API**: Costs money, adds latency, not needed for batch use case

**Implementation Notes**:
- Use `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` (50+ languages, 768-dim embeddings)
- Load model in `src/pipeline/utils/similarity.py`: `SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')`
- Store embeddings for existing scenarios in `{language}/{level}/scenario_embeddings.json` for fast lookup
- Cosine similarity >0.85 → reuse; 0.75-0.85 → prompt ops

## 5. Data Storage: JSON Files + Dual Indexing

**Decision**: Primary storage as JSON files, indexed in Meilisearch (search) and Postgres (relationships)

**Rationale**:
- JSON files are human-readable, git-friendly (ops can review/edit), and portable
- Meilisearch: Fast full-text + semantic search with language+level filtering (constitutional requirement)
- Postgres: Relational queries (find all content using learning item X, track usage counts)
- Dual indexing allows flexibility: search uses Meilisearch, analytics use Postgres

**Alternatives Considered**:
- **Single database (Postgres only)**: Slower for search, requires GIN indexes, harder to scale search separately
- **NoSQL only (MongoDB)**: Good for JSON but weaker for relational queries (usage tracking, link validation)
- **No database (files only)**: Too slow for API queries, no indexing

**Implementation Notes**:
- Pipeline outputs JSON files to `havachat-knowledge/generated content/{language}/{level}/{content_type}/`
- Separate indexing scripts (not in this phase): `index_to_meilisearch.py`, `index_to_postgres.py`
- Meilisearch indexes: `learning_items`, `content_units`, `questions` with filters: `language`, `level_system`, `level_min`, `level_max`
- Postgres schema: `learning_items`, `content_units`, `content_learning_items` (junction), `questions`, `usage_stats`

## 6. QA Gate Implementation

**Decision**: Separate validation functions per gate type, orchestrated by `run_qa_gates.py` CLI

**Rationale**:
- Gates are independent checks (presence, duplication, links, answerability)
- Each gate can be tested in isolation
- QA script runs all gates sequentially, collects failures, generates report
- Constitutional requirement: gates must block publication (FR-017)

**Alternatives Considered**:
- **Inline validation during generation**: Harder to test, can't rerun gates on existing content
- **Schema validation only**: Misses semantic issues (unanswerable questions, duplicate concepts with different IDs)

**Implementation Notes**:
- Each gate in `src/pipeline/validators/`: `presence.py`, `duplication.py`, `links.py`, `answerability.py`
- Gates return `ValidationResult` objects: `{item_id, passed, failure_reason, suggested_fix}`
- `run_qa_gates.py` CLI aggregates results → `qa_reports/report-{timestamp}.json` and `.md`

## 7. Logging and Observability

**Decision**: Structured JSON logging with request/response tracking for LLM calls

**Rationale**:
- FR-009 requires logging all LLM requests (prompt hash, tokens, latency) for cost tracking
- FR-025 requires structured logs (timestamp, stage, action, status) for debugging
- JSON logs can be ingested by log aggregators (Grafana Loki, CloudWatch)

**Alternatives Considered**:
- **Print statements**: Not searchable, not structured, hard to aggregate
- **Python logging with plain text**: Better but requires parsing, JSON is standard

**Implementation Notes**:
- Configure in `src/pipeline/utils/logging_config.py`: `logging.basicConfig(format='%(message)s')` + custom `JsonFormatter`
- Log fields: `timestamp`, `pipeline_stage`, `action`, `item_id`, `status`, `error_details`, `llm_tokens`, `llm_latency_ms`
- LLM client wrapper logs every call: `logger.info({"action": "llm_request", "prompt_hash": hash(prompt), "model": model, "tokens": response.usage.total_tokens})`

## 8. Retry Logic and Manual Review Queue

**Decision**: 3-attempt retry loop with exponential backoff, then flag for manual review

**Rationale**:
- FR-008 requires retry logic before flagging failures
- LLMs occasionally return malformed JSON (validation fails)
- Instructor auto-retries with validation feedback, but limit to 3 to avoid infinite loops
- Manual review queue prevents silent data loss

**Alternatives Considered**:
- **No retries**: Too strict, wastes LLM effort on recoverable errors
- **Infinite retries**: Wastes API cost on persistently malformed prompts
- **Immediate manual review**: Doesn't leverage LLM's ability to self-correct

**Implementation Notes**:
- Instructor handles retries internally: `client.chat.completions.create(max_retries=3, response_model=EnrichedVocabItem, ...)`
- If all retries fail, write to `{language}/{level}/manual_review/{stage_name}_failures.jsonl`
- JSONL format: one failed item per line with `{item_id, source_data, error_details, retry_count}`

## 9. Testing Strategy

**Decision**: Pytest with fixtures for sample data, organized by test type (unit/contract/integration/quality)

**Rationale**:
- Constitution requires test categories (Principle II)
- Pytest fixtures allow reusable sample data (test TSV files, expected outputs)
- Test categories match pipeline structure:
  - Unit: Test each enricher/generator in isolation
  - Contract: Test Pydantic schemas validate correctly
  - Integration: Test full pipeline runs
  - Quality: Test QA gates catch known violations

**Implementation Notes**:
- Fixtures in `tests/fixtures/`: `mandarin_vocab_sample.tsv`, `japanese_grammar_sample.tsv`
- Unit tests mock LLM responses using `instructor` test utilities
- Integration tests run on small real datasets (10 items) to verify end-to-end
- QA tests inject known violations (duplicate IDs, missing fields) and assert gates fail

## 10. Development Workflow

**Decision**: CLI-first development (scripts before LangGraph orchestration)

**Rationale**:
- Easier to test individual stages without graph complexity
- Ops can run stages manually for debugging
- LangGraph orchestration added after core logic works

**Workflow**:
1. Implement enricher subclasses with LLM prompts
2. Test with `python -m src.pipeline.cli.enrich_vocab --input test.tsv --output out/`
3. Add LangGraph orchestration in `enrichment_graph.py`
4. Run full graph: `python -m src.pipeline.langgraph.enrichment_graph --config config.json`

## 11. Two-Tier Architecture: Batch + Live API

**Decision**: Implement two complementary systems: batch pipeline for manual sources + live API for scenario-driven generation

**Rationale**:
- Vocab and grammar have official sources (HSK lists, JLPT vocab, textbook grammars) → batch pipeline with manual curation
- Other categories (pronunciation, idioms, functional language, cultural notes) lack comprehensive official sources → LLM-generated from existing vocab/grammar in batch
- Live API enables growing library: users request scenarios → system checks similarity → generates on-demand if new → library expands organically
- Partitioning by language enables horizontal scaling (each language is independent database/index)

**Batch Pipeline (Quality-First)**:
1. Enrich vocab from official sources (TSV/CSV/JSON)
2. Enrich grammar from official sources (CSV/TSV/Markdown)
3. Generate other categories from vocab/grammar using LLM (pronunciation rules, common idioms in vocab, functional patterns from grammar, cultural notes from vocab context)
4. Generate content units (conversations/stories) with learning item links
5. Generate comprehension questions
6. Run QA gates

**Live API (Speed-Acceptable Quality)**:
1. Accept scenario description (e.g., "ordering coffee at Starbucks, French A2")
2. Compute embedding and search for similar scenarios (cosine similarity >0.85)
3. If found: Return scenario metadata + associated content units + learning items
4. If not found:
   - Search for relevant learning items (vocab/grammar matching scenario context)
   - Generate missing learning items if needed (pronunciation, functional phrases)
   - Generate content unit (conversation/story)
   - Store scenario with rich tags (formality, setting, interaction type)
   - Return generated content
5. Track usage for popularity-based ranking

**Implementation Notes**:
- Live API uses FastAPI/Flask with async endpoints
- Scenario similarity search uses cached embeddings (precompute on save)
- LLM generation in live API has tighter timeouts (30s max vs unlimited in batch)
- Live API content goes through lightweight validation (schema only, no full QA gates)
- Batch workers can retroactively validate live-generated content and promote to "curated" tier

## 12. Database Partitioning by Language

**Decision**: Partition all data by language at storage and index level (no cross-language joins)

**Rationale**:
- API queries are always single-language ("find French A2 content", never "find French + Spanish content")
- Eliminates need for multi-language joins (performance bottleneck)
- Enables horizontal scaling (shard by language across servers)
- Simplifies backup/restore (export language independently)
- Allows per-language optimization (Chinese needs different tokenization than French)

**Implementation Notes**:
- Meilisearch: Separate indexes per language
  - `learning_items_zh`, `learning_items_ja`, `learning_items_fr`, `learning_items_en`, `learning_items_es`
  - `content_units_zh`, etc.
  - `scenarios_zh`, etc.
- Postgres: Table partitioning by language column OR separate schemas
  - Option A: `PARTITION BY LIST (language)` → `learning_items_zh`, `learning_items_ja`
  - Option B: Separate schemas → `zh.learning_items`, `ja.learning_items`
- JSON files: Already partitioned by directory structure (`Mandarin/HSK1/vocab/`)

## Open Questions (None)

All technical unknowns from spec have been resolved. Ready for Phase 1 (Design & Contracts).
