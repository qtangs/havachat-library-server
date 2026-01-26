<!--
SYNC IMPACT REPORT (2026-01-26)
════════════════════════════════════════════════════════════════════════════════
Version Change: Initial → 1.0.0
Added Principles:
  - I. Code Quality & Maintainability
  - II. Testing Standards & Quality Gates
  - III. User Experience Consistency
  - IV. Performance Requirements
Added Sections:
  - Technology Stack
  - Development Workflow
Templates Requiring Updates:
  ✅ plan-template.md (Constitution Check section updated)
  ✅ spec-template.md (Requirements validation aligned)
  ✅ tasks-template.md (QA gate tasks aligned)
Follow-up TODOs: None
════════════════════════════════════════════════════════════════════════════════
-->

# Havachat Library Server Constitution

## Core Principles

### I. Code Quality & Maintainability

**MUST enforce**: Separation of concerns between offline batch generation and online serving. Batch pipelines (LangGraph orchestration) MUST be independently testable from API endpoints. All learning content generation logic MUST be modular, reusable, and documented.

**MUST enforce**: Use `uv` package manager exclusively. Python >=3.14 required. Type hints mandatory for all public functions and class methods.

**MUST enforce**: No mixing of batch generation concerns into online serving code. Online server optimizes for speed; batch optimizes for quality and thoroughness.

**Rationale**: The system has two distinct performance profiles—batch can take hours to generate high-quality content with iterative LLM refinement; online must return results in milliseconds. Mixing these concerns creates complexity and performance degradation.

### II. Testing Standards & Quality Gates

**MUST enforce**: All QA gates (schema validation, duplication checks, link correctness, question answerability, audio-text alignment) MUST have automated tests that fail when violations occur.

**MUST enforce**: Test categories:
- **Unit tests**: Individual batch pipeline stages (seed selection, content generation, linking, question generation)
- **Contract tests**: Search API responses, session pack structure, analytics payload schema
- **Integration tests**: End-to-end batch pipeline execution, search index synchronization
- **Quality gate tests**: Automated validation of generated content quality

**MUST enforce**: All generated content MUST pass QA gates before promotion from staging to production. Human spot-checks are optional but automated gates are mandatory.

**Rationale**: Pre-generated content at scale cannot be manually reviewed. Automated quality gates ensure learners receive validated, high-quality educational material. Failed QA gates catch issues before they reach production.

### III. User Experience Consistency

**MUST enforce**: All API responses MUST follow consistent JSON schema. Error responses MUST include actionable error codes and human-readable messages in both English and the target learning language when applicable.

**MUST enforce**: Search results MUST respect language + proficiency filtering strictly (no Chinese results for French learners; no HSK 6 content for HSK 1 learners). Hybrid search (keyword + semantic) MUST produce deterministic ordering for identical queries.

**MUST enforce**: Session packs MUST deliver complete learning units in one API call: content + questions + quiz items + audio with timestamps. No partial responses requiring multiple round-trips.

**MUST enforce**: TTS audio MUST include word-level timestamps when available; segment-level timestamps are acceptable fallback. Audio-text alignment MUST be validated before publication.

**Rationale**: Language learners require predictable, complete learning experiences. Inconsistent content levels, incomplete packs, or misaligned audio/text create confusion and reduce learning effectiveness. API consistency enables client apps to provide reliable UX.

### IV. Performance Requirements

**MUST enforce**: Online API endpoints MUST respond within 200ms at p95 for search queries and session pack retrieval under normal load.

**MUST enforce**: Batch generation pipelines MUST prioritize quality over speed. Iterative LLM enrichment loops are acceptable and encouraged for content quality. Track and report batch processing metrics (items/hour, failure rates, retry counts).

**MUST enforce**: Search index updates MUST complete within 5 minutes of batch promotion to production. Denormalized search documents MUST include all necessary fields to avoid join queries at search time.

**MUST enforce**: Memory constraints: API server <500MB resident memory under normal load. Batch workers can scale horizontally; prefer parallelizable stages over single-threaded sequential processing.

**Rationale**: Fast online serving ensures smooth client app experience. Batch can be slow because it runs offline and pre-generates all content. Search denormalization trades storage for query speed—critical for multilingual semantic search at scale.

## Technology Stack

**Package Manager**: `uv` exclusively (specified in AGENTS.md)

**Languages**: Python >=3.14 for batch pipelines and API prototyping. Online server may migrate to Go/Rust/TypeScript for production speed (not yet decided per README).

**Batch Orchestration**: LangGraph for multi-stage LLM agent pipelines with iterative refinement loops.

**Core Dependencies**:
- `langgraph` >=1.0.7 for batch orchestration
- `docling` >=2.70.0 for PDF processing (if needed for input syllabi)
- `pandas` >=2.0.0 for data wrangling in batch
- `pytest` >=8.0.0 for testing
- `black` >=24.8.0 for code formatting

**Search Provider**: Not yet specified—must support multilingual hybrid search (keyword + semantic) with strict filtering on language and proficiency dimensions.

**Storage**: Not yet specified—must persist learning items, content units, questions, audio files, segment↔item links, and topic/scenario metadata.

## Development Workflow

**Branch Strategy**: Feature branches named `###-feature-name` branching from main. Each feature MUST have corresponding spec in `/specs/###-feature-name/`.

**Code Review**: All changes MUST pass automated QA gates before merge. Reviews MUST verify constitution compliance (separation of concerns, test coverage, performance impact).

**Testing Workflow**:
1. Write tests for QA gates and API contracts first
2. Implement batch pipeline stage or API endpoint
3. Verify all tests pass (including quality gate validations)
4. Run performance benchmarks for API changes
5. Update documentation if behavior changes

**Batch Pipeline Deployment**:
1. Develop pipeline stage locally with test fixtures
2. Run on small batch subset (e.g., 100 learning items)
3. Validate QA gate pass rates and processing time
4. Deploy to staging environment for full batch
5. Manual spot-check sample (optional)
6. Promote staging → production via atomic index swap

**API Deployment**: TBD (depends on final choice of Go/Rust/TypeScript for online server).

## Governance

This constitution supersedes all other development practices. Every feature specification, implementation plan, and task list MUST demonstrate alignment with the four core principles before work begins.

**Amendment Process**:
- Proposed changes MUST document: rationale, affected systems, migration plan
- Version bump rules (semantic versioning):
  - **MAJOR**: Principle removal or redefinition that breaks existing workflows
  - **MINOR**: New principle or section added
  - **PATCH**: Clarifications, wording fixes, non-semantic changes
- All amendments MUST update this file and propagate changes to `.specify/templates/` for consistency

**Compliance Review**: QA gates in batch pipelines are constitutional requirements. Disabling or bypassing gates requires explicit justification and temporary exception approval in spec documentation.

**Runtime Guidance**: See [AGENTS.md](../../../AGENTS.md) for agent-specific development instructions (e.g., package manager requirements).

**Version**: 1.0.0 | **Ratified**: 2026-01-26 | **Last Amended**: 2026-01-26
