# Havachat Library Server

Build an API server that powers a **pre-generated learning library** for English, Chinese (Mandarin), French, Japanese, and Spanish. It serves **Learning Items**, **conversations/stories**, **pre-generated comprehension questions**, and **TTS audio with word-level timestamps**. It supports **multilingual hybrid search** (keyword + semantic) with strict **language + proficiency filtering** across different level systems (CEFR / HSK / JLPT). The API returns **session packs** (content + questions + quiz items in one call) and captures **high-fidelity analytics** to continuously improve retrieval quality and learning outcomes.

## Offline Batch 
### Goal
Do as much work as possible offline (pre-generation), so online serving stays simple, fast, and cheap.

### Technology
Use Python as the main language and LangGraph as the LLM Agent Orchestrator.

### Inputs (Human-Guided)
- Syllabi / word lists / grammar pattern lists per language and level (can follow textbooks, online resources, official exams)
- Curated topic and scenario vocabularies (IDs + English names + aliases)
- Style constraints (register, length, learner-facing tone)
- Safety constraints (no disallowed content)

### Pipeline Stages (Batch)
1. **Seed selection**
  - **Manual (source-of-truth first):** find and import vocab lists and grammar lists from official/authoritative sources where available (e.g., HSK official lists for Mandarin).
  - For other learning target categories (pronunciation, idioms/expressions, functional language, etc.):
    - Use an official list if one exists.
    - If no official list exists, generate a candidate list via LLM conditioned on `(language, level)` and the official vocab + grammar lists.
   
2. **Generate learning items**
  - Generate learning items with all desired attributes (English explanation, examples, sense disambiguation fields where needed, etc.).
  - Prefer sense-aware items when needed (lemma + sense gloss + usage constraints).
  - **Iterative enrichment (LLM while-loop):** for each item, repeatedly invoke the LLM until the item passes schema/validation checks for required attributes (or reaches a retry limit for human review).
3. **Usage tracking (v1)**
  - Track per-learning-item usage counts while generating and publishing content units (e.g., number of appearances in published content segments).
  - Do **not** enforce a target frequency policy yet (no `min_uses_per_item` / `max_uses_per_item` constraints in v1).
4. **Generate (or reuse) content units (conversations/stories)**
  - **Given a text input** (e.g., a proposed topic/scenario description), search the existing library for highly similar topics/scenarios.
  - If a highly similar topic/scenario already exists, **reuse/return** the already-created resources for that one (content units, links, questions, audio) instead of generating new content.
  - If not similar enough:
    - Determine whether the input is a **broad topic** or a **specific scenario**, and create/resolve the appropriate topic/scenario entry in the library.
    - Select the **appropriate vocab** to use (based on topic/scenario + level) and include the relevant **grammar list** for that level.
    - Generate a **suite** of conversations/stories, each with multiple segments.
    - Within each generated content unit, record which vocab and which grammar are used **per segment** (for later linking).
5. **Linking**
  - Create explicit links between content segments and learning items (vocab + grammar used in each segment) in the segment↔learning-item linking table.
  - Link each content unit to its topic/scenario IDs in the library.
6. **Generate comprehension questions (per segment)**
  - For each segment in each content unit, generate the relevant comprehension questions intended to test **both reading and listening**.
7. **Generate TTS audio + alignment**
  - Generate audio and word-level timestamps; fallback to segment-level if needed
8. **Indexing**
  - Create denormalized search documents, generate embeddings, upsert into the search provider
9. **QA gates (automated first, human optional)**
  - Schema validation, duplication checks, link correctness checks, question answerability
  - Optional spot-check queue (small sample per batch)
10. **Publish**
  - Promote batch from `staging` to `production`

### QA Gates (Recommended Minimum)
- **Presence checks:** every linked learning item must appear in the content text (language-aware tokenization)
- **Sense collision checks:** prevent multiple meanings sharing a single item without disambiguation
- **Duplication checks:** near-duplicate learning items and near-duplicate content detection
- **Question answerability:** answers must be derivable from the text/audio
- **Audio-text alignment:** transcript matches exact content version


## Online Server

Not yet decided the technology. Most important is speed so it may be Go, Rust or just Typescript.
