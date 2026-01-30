To generate **non–vocab / non–grammar** learning items with LLMs (pronunciation, idioms/expressions, functional language, cultural notes, writing system, misc subcategories), you need a few **inputs + guardrails** so the output is **level-appropriate, deduped, and linkable**.

## 1) Seed sources (preferred) or a candidate-generation plan
- **Authoritative lists where they exist** (best):
  - Pronunciation curricula (phoneme inventories, minimal pairs, prosody targets)
  - Idiom/expression lists graded by level (if available)
  - Functional language syllabi (requests/offers/politeness patterns)
  - Cultural note checklists (customs, norms) suitable for learners
  - Writing system references (characters/radicals/stroke-order targets)
- **If no official list exists:** you still need **a recipe to generate candidate lists** via the LLM conditioned on:
  - `(language, level)` and the language’s **level system**
  - the **official/curated vocab + grammar lists** for that level (so the LLM stays inside learner-known building blocks)

## 2) Level + language constraints (hard requirements)
- A declared `language` and valid `level_system` + `level_min/level_max`
- A clear **level-fit policy** for generation (e.g., “use only A2 vocab/grammar and A2-appropriate situations/register”)

## 3) A strict schema + validation loop
You need the same “iterative enrichment” approach described in the PRD:
- Generate → **validate against schema** → regenerate/fix until it passes (or send to human review).
- Enforce required fields (id, category, target_item, definition, examples, level fields, etc.) plus category-specific fields:
  - `romanization` (zh/ja where needed)
  - `lemma`, `pos`, `sense_gloss`, `aliases[]` when applicable

## 4) Category-specific generation guidelines (so items are teachable)
Examples of what must be defined per category:
- **Pronunciation:** phoneme/prosody target, common learner errors, minimal pairs / example words/sentences
- **Functional language:** intent + politeness/register + common variations
- **Idioms/expressions:** meaning, constraints (formality, region), literal vs idiomatic, usage examples
- **Cultural notes:** what to do/say + context boundaries (when it applies, what *not* to do)
- **Writing system:** character/radical targets, reading(s), stroke-order notes, example words
- **Misc (pragmatics/sociolinguistics/literacy/patterns):** scope must be narrow and assessable (like the PRD’s “granularity” rule for grammar)

## 5) QA gates to prevent low-quality or risky content
Minimum automated checks (from the PRD’s QA section, adapted to these categories):
- **Duplication / near-duplication** detection (items + definitions)
- **Sense collision** checks (polysemy needs `sense_gloss`)
- **Level leakage** checks (using advanced vocab/structures for beginner levels)
- **Safety/style constraints** (avoid disallowed topics; keep learner-friendly tone)
- **Linkability/presence checks** later when embedding items into content (items must actually appear in content where linked)
