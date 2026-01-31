# Quickstart: Pre-generation Pipeline

**Feature**: Pre-generation Pipeline for Learning Content  
**Branch**: `001-pregen-pipeline`  
**Last Updated**: 2026-01-26

## Overview

This pipeline generates structured learning content from official vocabulary and grammar sources using LLM enrichment. It outputs JSON files for indexing in Meilisearch (search) and Postgres (relationships).

## Prerequisites

- Python >=3.14
- `uv` package manager
- OpenAI API key (or compatible LLM provider)
- Git access to `havachat-knowledge` repository

## Installation

```bash
# Clone repo and install dependencies
git clone <repo-url> havachat-library-server
cd havachat-library-server
uv sync

# Set up environment variables
export OPENAI_API_KEY="sk-..."
export HAVACHAT_KNOWLEDGE_PATH="../havachat-knowledge"  # Path to content repository
```

## Pipeline Stages

### Overview

The system has two operational modes:

1. **Batch Pipeline (Offline)**: Process official sources → enrich vocab/grammar → generate other categories → create content → validate
2. **Live API (Online)**: Accept scenario requests → search for similar → generate on-demand → return results

### 1. Enrich Vocabulary ✅ COMPLETE

**Status**: Fully implemented with optimizations (parallel processing, checkpoints, token tracking, language-specific models)

**Input**: TSV/CSV/JSON file with official vocabulary list  
**Output**: JSON files in `havachat-knowledge/generated content/{language}/{level}/vocab/`

```bash
# Example: Enrich Chinese HSK1 vocabulary with parallel processing
python -m havachat.cli.enrich_vocab \
  --language zh \
  --level HSK1 \
  --input sources/chinese/hsk1_vocab.tsv \
  --enricher chinese \
  --output $HAVACHAT_KNOWLEDGE_PATH/generated content/Chinese/HSK1/vocab/ \
  --parallel 5 \
  --resume

# Example: Enrich Japanese JLPT N5 vocabulary
python -m havachat.cli.enrich_vocab \
  --language ja \
  --level N5 \
  --input sources/japanese/jlpt_n5_vocab.json \
  --enricher japanese \
  --output $HAVACHAT_KNOWLEDGE_PATH/generated content/Japanese/N5/vocab/ \
  --parallel 3

# Example: Enrich French A1 vocabulary from TSV
python -m havachat.cli.enrich_vocab \
  --language fr \
  --level A1 \
  --input sources/french/a1_vocab.tsv \
  --enricher french \
  --output $HAVACHAT_KNOWLEDGE_PATH/generated content/French/A1/vocab/ \
  --parallel 5
```

**Options**:
- `--language`: ISO 639-1 code (zh, ja, fr, en, es)
- `--level`: Proficiency level (HSK1-6, N5-N1, A1-C1)
- `--input`: Path to source file (TSV/CSV/JSON)
- `--enricher`: Language-specific enricher (chinese, japanese, french)
- `--output`: Directory for output JSON files
- `--parallel N`: Process N items in parallel (default: 1) - **NEW**
- `--resume`: Resume from checkpoint if interrupted - **NEW**
- `--dry-run`: Preview first 3 items without writing files
- `--max-items`: Limit processing (for testing)

**Expected Output** (with token tracking):
```
Processing 500 vocab items from hsk1_vocab.tsv...
Enriching: 100%|████████████████████████████| 500/500 [06:40<00:00, 1.25 items/s]

================================================================================
ENRICHMENT SUMMARY
================================================================================
Total items processed: 500
Successfully enriched: 485
Failed: 15
Success rate: 97.0%
Enrichment time: 400.00s
Average time per item: 0.80s

--------------------------------------------------------------------------------
TOKEN USAGE & COST
--------------------------------------------------------------------------------
Model: gpt-4o-mini
Prompt tokens: 480,000
Completion tokens: 270,000
Total tokens: 750,000
Cached tokens: 350,000
Cache hit rate: 72.9%
Estimated cost: $0.1850
  - Input cost: $0.0250
  - Output cost: $0.1600

Failed items saved to: output/zh/hsk1/failed_items.jsonl
```

**Performance Improvements**:
- Auto-romanization: Chinese uses `pypinyin`, Japanese uses `pykakasi` (~30 tokens saved per item)
- Language-specific models: Only required fields validated (~20 tokens saved per item)
- Prompt caching: OpenAI automatic caching for system messages >1024 tokens (~350 tokens saved per item)
- **Total savings**: ~400 tokens/item = 54% cost reduction
- Parallel processing: 5x speedup with `--parallel 5`
- Checkpoint/resume: No restart penalty after failures

---

### 2. Enrich Grammar

**Input**: CSV/TSV/Markdown file with grammar patterns  
**Output**: JSON files in `havachat-knowledge/generated content/{language}/{level}/grammar/`

```bash
# Example: Enrich Chinese HSK1 grammar
python -m havachat.cli.enrich_grammar \
  --language zh \
  --level HSK1 \
  --input sources/chinese/hsk1_grammar.csv \
  --enricher chinese \
  --output $HAVACHAT_KNOWLEDGE_PATH/generated content/Chinese/HSK1/grammar/

# Example: Enrich French A1 grammar
python -m havachat.cli.enrich_grammar \
  --language fr \
  --level A1 \
  --input sources/french/a1_grammar.md \
  --enricher french \
  --output $HAVACHAT_KNOWLEDGE_PATH/generated content/French/A1/grammar/
```

**Expected Output**:
```
Processing 120 grammar patterns from hsk1_grammar.csv...
[1/120] 是...的 -> item-850e8400-e29b-41d4-a716-446655440000.json ✓
[2/120] 了 (aspect marker) -> item-950e8400-e29b-41d4-a716-446655440001.json ✓
...
[120/120] 在 (location marker) -> item-a50e8400-e29b-41d4-a716-446655440119.json ✓

Summary:
- Total: 120
- Success: 118 (98.3%)
- Granularity warnings: 2 (mega-items split into sub-items)
- Failed: 0
- Duration: 12m 45s
```

---

### 3. Generate Other Categories (Pronunciation, Idioms, Functional, etc.)

**Input**: Enriched vocab + grammar learning items  
**Output**: JSON files in `havachat-knowledge/generated content/{language}/{level}/{category}/`

```bash
# Example: Generate pronunciation learning items from Chinese vocab
python -m havachat.cli.generate_other_categories \
  --language zh \
  --level HSK1 \
  --category pronunciation \
  --source-items $HAVACHAT_KNOWLEDGE_PATH/generated content/Chinese/HSK1/vocab/ \
  --output $HAVACHAT_KNOWLEDGE_PATH/generated content/Chinese/HSK1/pronunciation/

# Example: Generate functional language items from French grammar
python -m havachat.cli.generate_other_categories \
  --language fr \
  --level A1 \
  --category functional \
  --source-items $HAVACHAT_KNOWLEDGE_PATH/generated content/French/A1/grammar/ \
  --output $HAVACHAT_KNOWLEDGE_PATH/generated content/French/A1/functional/

# Example: Generate cultural notes from Japanese vocab
python -m havachat.cli.generate_other_categories \
  --language ja \
  --level N5 \
  --category cultural \
  --source-items $HAVACHAT_KNOWLEDGE_PATH/generated content/Japanese/N5/vocab/ \
  --output $HAVACHAT_KNOWLEDGE_PATH/generated content/Japanese/N5/cultural/
```

**Options**:
- `--category`: pronunciation, idiom, functional, cultural, writing_system, sociolinguistic, pragmatic, literacy, pattern, other
- `--source-items`: Directory of existing learning items to base generation on
- `--max-items`: Maximum number of items to generate
- `--prompts`: Override default prompts with custom file

**Expected Output**:
```
Analyzing 485 vocab items from Chinese/HSK1/vocab/...
Generating pronunciation learning items...

Generated items:
[1/25] Tone pairs: 1st + 2nd tone → item-a50e8400.json ✓
[2/25] Initial consonant: zh- vs j- → item-b50e8400.json ✓
[3/25] Final -ing vs -in → item-c50e8400.json ✓
...
[25/25] Tone sandhi: 不 tone change → item-x50e8400.json ✓

Summary:
- Total generated: 25
- Category: pronunciation
- Based on: 485 vocab items
- Duration: 8m 32s
```

---

### 4. Generate Content Units

**Input**: Topic/scenario description + enriched learning items  
**Output**: JSON files in `havachat-knowledge/generated content/{language}/{level}/conversations/` or `stories/`

```bash
# Example: Generate Chinese HSK2 conversation
python -m havachat.cli.generate_content \
  --language zh \
  --level HSK2 \
  --type conversation \
  --topic "ordering food" \
  --scenario "casual restaurant" \
  --turns 8 \
  --output $HAVACHAT_KNOWLEDGE_PATH/generated content/Chinese/HSK2/conversations/

# Example: Generate French A1 story
python -m havachat.cli.generate_content \
  --language fr \
  --level A1 \
  --type story \
  --topic "daily routine" \
  --scenario "morning activities" \
  --paragraphs 5 \
  --output $HAVACHAT_KNOWLEDGE_PATH/generated content/French/A1/stories/
```

**Options**:
- `--type`: conversation or story
- `--topic`: Broad category (food, travel, work)
- `--scenario`: Specific situation (ordering at restaurant, airport checkin)
- `--turns`: Number of dialogue turns (for conversations, default 8)
- `--paragraphs`: Number of paragraphs (for stories, default 5)
- `--check-similarity`: Check for existing similar content (default: true)

**Expected Output**:
```
Checking for similar existing scenarios...
Found 1 match with 78% similarity (below 85% threshold)
Generating new conversation: "Ordering Food at Casual Restaurant"...

Selected learning items:
- Vocab: 15 items (HSK2)
- Grammar: 6 items (HSK2)

Generated conversation: content-b50e8400-e29b-41d4-a716-446655440000.json
- Title: 在餐厅点菜 (Ordering at Restaurant)
- Segments: 8 turns
- Word count: 156
- Linked items: 21
- Reading time: 45 seconds

Validation:
✓ All learning_item_ids exist
✓ All items appear in text
✓ Level consistency (HSK2 only)
```

---

### 5. Generate Questions

**Input**: Completed content unit  
**Output**: JSON file in `havachat-knowledge/generated content/{language}/{level}/questions/`

```bash
# Example: Generate questions for a conversation
python -m havachat.cli.generate_questions \
  --content-id b50e8400-e29b-41d4-a716-446655440000 \
  --language zh \
  --level HSK2 \
  --num-questions 6 \
  --output $HAVACHAT_KNOWLEDGE_PATH/generated content/Chinese/HSK2/questions/
```

**Options**:
- `--content-id`: UUID of parent content unit
- `--num-questions`: Number of questions to generate (default 6)
- `--difficulty-distribution`: Comma-separated percentages (easy,medium,hard) default "40,40,20"

**Expected Output**:
```
Loading content unit b50e8400-e29b-41d4-a716-446655440000...
Generating 6 questions...

Generated questions: questions-b50e8400-e29b-41d4-a716-446655440000.json
- Type distribution: 3 MCQ, 2 true/false, 1 short answer
- Difficulty: 2 easy, 3 medium, 1 hard
- Tags: 2 detail, 2 inference, 2 main-idea

Answerability validation:
✓ All 6 questions answered correctly by LLM from text alone
```

---

### 6. Run QA Gates

**Input**: Directory of generated content  
**Output**: Validation report (JSON + Markdown)

```bash
# Example: Validate all French A1 content
python -m havachat.cli.run_qa_gates \
  --language fr \
  --level A1 \
  --content-dir $HAVACHAT_KNOWLEDGE_PATH/generated content/French/A1/ \
  --output $HAVACHAT_KNOWLEDGE_PATH/generated content/French/A1/qa_reports/

# Validate specific content type
python -m havachat.cli.run_qa_gates \
  --language zh \
  --level HSK2 \
  --content-type conversations \
  --content-dir $HAVACHAT_KNOWLEDGE_PATH/generated content/Chinese/HSK2/conversations/ \
  --output $HAVACHAT_KNOWLEDGE_PATH/generated content/Chinese/HSK2/qa_reports/
```

**Options**:
- `--content-dir`: Directory containing content to validate
- `--content-type`: Filter by type (vocab, grammar, conversations, stories, questions)
- `--gates`: Comma-separated gates to run (default: all)
  - `schema`: Schema validation
  - `presence`: Learning items appear in text
  - `duplication`: No duplicate learning items
  - `links`: All references resolve
  - `answerability`: Questions answerable from text
  - `language`: No cross-language contamination

**Expected Output**:
```
Running QA gates on French A1 content...

Gate: Schema Validation
✓ learning_items: 450/450 passed
✓ content_units: 95/95 passed
✓ questions: 570/570 passed

Gate: Presence Check
✓ 95/95 content units passed
✗ 0 failures

Gate: Duplication Check
✓ 450/450 learning items unique
✗ 2 duplicates flagged (see report)

Gate: Link Correctness
✓ 95/95 content units passed
✓ 570/570 questions passed

Gate: Answerability
✓ 565/570 questions passed
✗ 5 questions flagged (see report)

Gate: Language Contamination
✓ 0 contamination detected

Summary:
- Total items: 1,165
- Passed: 1,158 (99.4%)
- Failed: 7 (0.6%)
- Pass rate: 99.4%

Report saved:
- JSON: qa_reports/report-2026-01-26T12-00-00.json
- Markdown: qa_reports/report-2026-01-26T12-00-00.md

Review flagged items at:
French/A1/manual_review/flagged_items.jsonl
```

---

## Live API (Scenario-Driven On-Demand Generation)

The live API accepts scenario descriptions and generates content on-demand, building a growing library.

### Start API Server

```bash
# Start the live API server
python -m havachat.api.server \
  --host 0.0.0.0 \
  --port 8001 \
  --workers 4

# API will be available at http://localhost:8001
```

### API Endpoints

#### 1. Search for Similar Scenarios

```bash
# Search for existing scenarios
curl -X POST http://localhost:8001/api/v1/scenarios/search \
  -H "Content-Type: application/json" \
  -d '{
    "description": "ordering coffee at a café",
    "language": "fr",
    "level": "A2",
    "similarity_threshold": 0.85
  }'
```

**Response (if found)**:
```json
{
  "found": true,
  "scenario": {
    "id": "cafe-order-casual-fr-a2",
    "name": "Ordering at a Café",
    "description": "Casual interaction ordering coffee and pastries",
    "similarity_score": 0.92,
    "formality": "informal",
    "setting": "indoor",
    "interaction_type": "transactional",
    "content_unit_ids": ["b50e8400-...", "c50e8400-..."],
    "learning_item_ids": ["550e8400-...", "650e8400-..."],
    "usage_count": 47
  }
}
```

**Response (if not found)**:
```json
{
  "found": false,
  "similar_scenarios": [
    {
      "id": "restaurant-order-fr-a2",
      "name": "Ordering at a Restaurant",
      "similarity_score": 0.78,
      "description": "Formal restaurant ordering"
    }
  ]
}
```

#### 2. Generate New Scenario with Content

```bash
# Generate new scenario + content on-demand
curl -X POST http://localhost:8001/api/v1/scenarios/generate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "ordering coffee at a café",
    "language": "fr",
    "level": "A2",
    "formality": "informal",
    "setting": "indoor",
    "generate_content": true,
    "content_type": "conversation",
    "turns": 6
  }'
```

**Response**:
```json
{
  "scenario": {
    "id": "d50e8400-e29b-41d4-a716-446655440000",
    "name": "Ordering Coffee at Café",
    "description": "Casual café ordering interaction",
    "language": "fr",
    "formality": "informal",
    "setting": "indoor",
    "interaction_type": "transactional",
    "tags": ["food", "beverage", "service", "ordering"],
    "created_at": "2026-01-26T14:30:00Z",
    "source": "live-api"
  },
  "learning_items": [
    {
      "id": "550e8400-...",
      "category": "vocab",
      "target_item": "un café",
      "definition": "a coffee"
    },
    {
      "id": "650e8400-...",
      "category": "functional",
      "target_item": "Je voudrais...",
      "definition": "I would like... (polite request)"
    }
  ],
  "content_unit": {
    "id": "750e8400-...",
    "type": "conversation",
    "title": "Au Café",
    "segments": [
      {
        "segment_id": "seg-1",
        "speaker": "Client",
        "text": "Bonjour! Je voudrais un café, s'il vous plaît.",
        "translation": "Hello! I would like a coffee, please.",
        "learning_item_ids": ["550e8400-...", "650e8400-..."]
      }
    ],
    "publishable": false
  },
  "generation_time_ms": 4500
}
```

#### 3. Get Scenario by ID

```bash
# Retrieve full scenario details
curl http://localhost:8001/api/v1/scenarios/d50e8400-e29b-41d4-a716-446655440000
```

#### 4. Update Scenario Tags

```bash
# Enrich scenario metadata after manual review
curl -X PATCH http://localhost:8001/api/v1/scenarios/d50e8400-e29b-41d4-a716-446655440000 \
  -H "Content-Type: application/json" \
  -d '{
    "tags": ["food", "beverage", "service", "ordering", "morning"],
    "participant_count": "one-on-one",
    "embedding": [0.123, 0.456, ...]
  }'
```

### Live API Configuration

**Environment Variables**:
```bash
export HAVACHAT_LIVE_API_LLM_MODEL="gpt-3.5-turbo"  # Faster model for speed
export HAVACHAT_LIVE_API_TIMEOUT=30  # Max 30s per generation
export HAVACHAT_LIVE_API_CACHE_EMBEDDINGS=true  # Cache scenario embeddings
export HAVACHAT_LIVE_API_VALIDATION_MODE="schema_only"  # Lightweight validation
```

**Performance Targets**:
- Scenario search: <100ms (embedding similarity)
- On-demand generation: <30s total (scenario + learning items + content)
- Concurrent requests: 10 simultaneous generations per worker

### Live API vs Batch Pipeline

| Aspect | Live API | Batch Pipeline |
|--------|----------|----------------|
| **Trigger** | User request | Manual/scheduled |
| **Speed** | <30s per scenario | Hours per batch |
| **Quality** | Acceptable (schema validation only) | High (full QA gates) |
| **LLM Model** | GPT-3.5-turbo (fast) | GPT-4 (accurate) |
| **Validation** | Lightweight | Comprehensive |
| **Retry Logic** | 1 attempt | 3 attempts |
| **Output Status** | `publishable: false` | `publishable: true` (after QA) |
| **Use Case** | Rapid prototyping, user-driven | Curated library |

**Workflow**: Live API generates draft content → Batch workers retroactively validate → Promote to curated tier

---

## LangGraph Orchestration (Advanced)

For production batch processing, use LangGraph orchestration:

```bash
# Run full enrichment pipeline with retries and checkpointing
python -m havachat.langgraph.enrichment_graph \
  --config configs/mandarin_hsk1_enrichment.json

# Run full content generation pipeline
python -m havachat.langgraph.generation_graph \
  --config configs/french_a1_content_generation.json
```

**Config Example** (`configs/mandarin_hsk1_enrichment.json`):
```json
{
  "language": "zh",
  "level": "HSK1",
  "stages": {
    "vocab": {
      "input": "sources/chinese/hsk1_vocab.tsv",
      "enricher": "chinese",
      "output": "../havachat-knowledge/generated content/Chinese/HSK1/vocab/"
    },
    "grammar": {
      "input": "sources/chinese/hsk1_grammar.csv",
      "enricher": "chinese",
      "output": "../havachat-knowledge/generated content/Chinese/HSK1/grammar/"
    }
  },
  "llm": {
    "provider": "openai",
    "model": "gpt-4",
    "max_retries": 3,
    "timeout": 60
  },
  "checkpoint": {
    "enabled": true,
    "path": "checkpoints/mandarin_hsk1_enrichment/"
  }
}
```

---

## Troubleshooting

### LLM Failures

If enrichment fails with validation errors:

```bash
# Check manual review queue
cat $HAVACHAT_KNOWLEDGE_PATH/generated content/Chinese/HSK1/manual_review/vocab_failures.jsonl

# Retry failed items with higher temperature
python -m havachat.cli.enrich_vocab \
  --input manual_review/vocab_failures.jsonl \
  --retry-mode \
  --temperature 0.9
```

### Schema Validation Errors

```bash
# Validate individual file against schema
python -m havachat.validators.schema \
  --file French/A1/vocab/item-550e8400.json \
  --schema contracts/learning_item.schema.json

# Auto-fix common issues (missing fields, type mismatches)
python -m havachat.validators.schema \
  --file French/A1/vocab/item-550e8400.json \
  --auto-fix
```

### Performance Tuning

```bash
# Process in parallel (8 workers)
python -m havachat.cli.enrich_vocab \
  --input hsk1_vocab.tsv \
  --workers 8

# Use faster model for simple enrichment
python -m havachat.cli.enrich_vocab \
  --input hsk1_vocab.tsv \
  --model gpt-3.5-turbo  # Default: gpt-4

# Cache LLM responses (avoid re-processing)
export HAVACHAT_LLM_CACHE_PATH=".cache/llm_responses/"
```

---

## Next Steps

1. **Indexing**: Run indexing scripts to populate Meilisearch and Postgres
   ```bash
   python scripts/index_to_meilisearch.py --language fr --level A1
   python scripts/index_to_postgres.py --language fr --level A1
   ```

2. **TTS Generation**: Add audio with timestamps (Phase 2)
   ```bash
   python scripts/generate_tts.py --content-id b50e8400-e29b-41d4-a716-446655440000
   ```

3. **API Testing**: Test search and session pack endpoints
   ```bash
   curl "http://localhost:8000/api/search?q=restaurant&language=fr&level=A1"
   ```

---

## Documentation

- [Data Model](data-model.md): Full entity schemas
- [Research](research.md): Technology decisions
- [Implementation Plan](plan.md): Technical architecture
- [Contracts](contracts/): JSON schemas for all entities
- [Spec](spec.md): Feature requirements

---

## Support

For questions or issues, see:
- GitHub Issues: `<repo-url>/issues`
- Internal Docs: `.specify/memory/constitution.md`
