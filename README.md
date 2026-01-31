# Havachat Library Server

**Pre-generation Pipeline for Learning Content**

This project contains the batch processing pipeline for generating and enriching language learning content (vocabulary, grammar, conversations, questions) from source materials. It uses LangGraph for LLM agent orchestration and Instructor for structured outputs with Pydantic validation.

**Supported Languages**: Mandarin (HSK 1-6), Japanese (JLPT N5-N1), French (CEFR A1-C2)  
**Python Version**: >=3.14  
**Package Manager**: uv


## Architecture

The pipeline follows a two-tier architecture:

1. **Batch Pipeline** (this project): Python scripts orchestrated with LangGraph for:
   - Manual vocab/grammar enrichment from official sources
   - LLM-generated additional categories (pronunciation, idioms, cultural notes)
   - Content unit generation with semantic deduplication
   - Question generation and QA validation gates

2. **Live API** (future): On-demand content generation with:
   - Scenario similarity search using embeddings
   - Learning item selection and content generation
   - JSON output partitioned by language and level

## Project Structure

```
havachat-library-server/
├── src/
│   ├── pipeline/
│   │   ├── __init__.py              # Package metadata
│   │   ├── enrichers/               # Content enrichment stages
│   │   │   ├── base.py              # BaseEnricher abstract class
│   │   │   ├── vocab/               # Language-specific vocab enrichers
│   │   │   └── grammar/             # Language-specific grammar enrichers
│   │   ├── validators/              # Pydantic schemas and validation
│   │   │   └── schema.py            # Core data models
│   │   └── utils/                   # Shared utilities
│   │       ├── llm_client.py        # Instructor-wrapped LLM client
│   │       ├── file_io.py           # File operations
│   │       ├── logging_config.py    # Structured logging
│   │       └── similarity.py        # Semantic similarity
│   └── tools/                       # Existing tools
├── tests/
│   ├── unit/                        # Unit tests (fast, mocked)
│   ├── contract/                    # Schema validation tests
│   ├── integration/                 # End-to-end tests
│   └── fixtures/                    # Test data and fixtures
├── specs/
│   └── 001-pregen-pipeline/        # Feature specification
│       ├── spec.md                  # Requirements
│       ├── plan.md                  # Implementation plan
│       ├── data-model.md            # Entity schemas
│       ├── tasks.md                 # Task breakdown
│       └── contracts/               # JSON schemas
├── pyproject.toml                   # Project dependencies
├── pytest.ini                       # Test configuration
└── .env.template                    # Environment variables template
```

## Setup Instructions

### Prerequisites

- Python 3.14 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- OpenAI API key (or Anthropic API key)
- Access to havachat-knowledge repository

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd havachat-library-server
```

2. Install dependencies with uv:
```bash
uv sync
```

3. Configure environment variables:
```bash
cp .env.template .env
# Edit .env and fill in your API keys and paths
```

4. Verify setup:
```bash
# Check Python version
python --version  # Should be >=3.14

# Run tests
uv run pytest -m unit
```

### Required Environment Variables

Create a `.env` file with the following (see `.env.template` for all options):

```bash
# Required
OPENAI_API_KEY=sk-...
HAVACHAT_KNOWLEDGE_PATH=/path/to/havachat-knowledge

# Optional
LLM_MODEL=gpt-4-turbo-preview
MAX_RETRIES=3
LOG_LEVEL=INFO
```

## Pipeline Stages 
## Pipeline Stages

### 1. Seed Selection
- Import vocab and grammar lists from official/authoritative sources
- For HSK (Mandarin): Use official HSK word lists
- For JLPT (Japanese): Use official JLPT vocabulary
- For CEFR (French): Use standardized CEFR references

### 2. Learning Item Enrichment
- Generate complete learning items with all 12 categories:
  - Vocabulary, Grammar, Pronunciation, Idioms, Functional Language
  - Cultural Notes, Writing System, Sociolinguistic, Pragmatic, Literacy, Patterns
- Structured LLM responses via Instructor with Pydantic validation
- Iterative enrichment with retry logic (max 3 attempts)
- Manual review queue for failed validations

### 3. Content Unit Generation
- Generate conversations/stories partitioned by (language, level, topic)
- Semantic deduplication using sentence embeddings
- Segment-level learning item linking
- Usage tracking per learning item

### 4. Question Generation
- Comprehension questions per content segment
- Multiple choice, fill-in-blank, true/false formats
- Validate question answerability

### 5. Quality Gates (Constitutional Requirements)
- Schema validation (all required fields present)
- Duplication detection (avoid redundant content)
- Link correctness (learning items ↔ segments)
- Question answerability verification
- Language isolation (no cross-language contamination)

## Development Workflow

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test categories
uv run pytest -m unit           # Fast unit tests
uv run pytest -m contract       # Schema validation
uv run pytest -m integration    # End-to-end tests
uv run pytest -m quality_gate   # QA validations

# Run with coverage
uv run pytest --cov=src/pipeline --cov-report=html
```

### Code Formatting

```bash
# Format code with black
uv run black src/ tests/
```

### Running the Pipeline

```bash
# TBD: CLI commands will be added in later phases
# Example: python -m src.havachat.enrichers.vocab.mandarin --input vocab.tsv
```

## Key Features

- **Structured LLM Outputs**: All LLM responses validated with Pydantic schemas via Instructor
- **Language Partitioning**: Data organized by language and level for optimal isolation
- **Retry Logic**: Automatic retries with exponential backoff for LLM failures
- **Quality Gates**: Constitutional requirements enforced via automated validation
- **Semantic Similarity**: Scenario deduplication using sentence embeddings
- **Observability**: Structured JSON logging for all pipeline stages

## Dependencies

**Core**:
- `langgraph>=1.0.7` - LLM agent orchestration
- `instructor>=1.0.0` - Structured LLM outputs
- `pydantic>=2.0.0` - Data validation

**Data Processing**:
- `docling>=2.70.0` - PDF parsing
- `pandas>=2.0.0` - TSV/CSV handling

**ML & Embeddings**:
- `sentence-transformers>=2.0.0` - Semantic similarity
- `openai>=1.0.0` - LLM API client

**Testing**:
- `pytest>=8.0.0` - Test framework
- `black>=24.8.0` - Code formatting

## Constitutional Alignment

This project adheres to the Havachat Development Constitution:

- **I. Code Quality**: Batch/online separation, Python 3.14, uv package manager, type hints
- **II. Testing Standards**: Unit, contract, integration, and quality gate tests
- **III. UX Consistency**: Language + level filtering, schema validation
- **IV. Performance**: Batch prioritizes quality over speed (acceptable 30min for 500 items)

## License

[License information here]

## Contributing

[Contributing guidelines here]

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
