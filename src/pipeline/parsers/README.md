# Source File Parsers

This module provides reusable parsers for loading vocabulary and grammar content from original source files in various formats (TSV, CSV, JSON) for different languages.

## Overview

Previously, each enricher had its own `parse_source()` method to load and parse source files. This led to code duplication and made it difficult to reuse parsing logic in other parts of the pipeline (e.g., when generating derived learning items like pronunciation or idioms).

The parsers have now been centralized in `src/pipeline/parsers/source_parsers.py` and can be used by:
- Enrichers (for initial content enrichment)
- Learning item generators (for creating derived content)
- CLI tools (for bulk processing)
- Tests (for validation)

## Supported Formats

### Mandarin Vocabulary (TSV)
**Format:** `Word\tPart of Speech`

```tsv
Word    Part of Speech
唱      动
点1     量、（名）
和1     介、连
```

**Features:**
- Cleans sense markers from words (e.g., "本1" → "本")
- Extracts sense markers for disambiguation
- Translates Chinese POS tags to English
- Handles compound POS (e.g., "量、（名）" → "measure word/noun")

**Parser:** `parse_mandarin_vocab_tsv(source_path)`

### Japanese Vocabulary (JSON)
**Format:** JSON array or object with `vocabulary` key

```json
[
  {
    "word": "学校",
    "meaning": "school",
    "furigana": "がっこう",
    "romaji": "gakkou",
    "level": "N5"
  }
]
```

**Features:**
- Auto-generates romaji if missing (using pykakasi)
- Normalizes JLPT levels (e.g., "5" → "N5")
- Handles both array and object formats

**Parser:** `parse_japanese_vocab_json(source_path)`

### French Vocabulary (TSV)
**Format:** `Mot\tCatégorie`

```tsv
Mot                     Catégorie
Bonjour. / Bonsoir.     Saluer
Ça va ?                 Saluer
```

**Features:**
- Preserves functional categories
- Handles multi-line entries
- Skips BOM if present

**Parser:** `parse_french_vocab_tsv(source_path)`

### Mandarin Grammar (CSV)
**Format:** `类别,类别名称,细目,语法内容`

```csv
类别,类别名称,细目,语法内容
词类,动词,能愿动词,会、能
词类,代词,人称代词,我、你、您、他、她
```

**Features:**
- Splits multi-item patterns (e.g., "会、能" → ["会", "能"])
- Cleans trailing numbers and prefixes
- Preserves original content for context
- Prevents "mega-items" by creating individual entries

**Parser:** `parse_mandarin_grammar_csv(source_path)`

## Usage

### Direct Parser Usage

```python
from pipeline.parsers.source_parsers import (
    parse_mandarin_vocab_tsv,
    parse_japanese_vocab_json,
    parse_french_vocab_tsv,
    parse_mandarin_grammar_csv,
)

# Parse Mandarin vocab
items = parse_mandarin_vocab_tsv("data/mandarin_vocab_hsk1.tsv")
# Returns: [{"target_item": "唱", "pos": "verb", "sense_marker": "", ...}, ...]

# Parse Japanese vocab
items = parse_japanese_vocab_json("data/japanese_vocab_n5.json")
# Returns: [{"target_item": "学校", "romanization": "gakkou", ...}, ...]
```

### Generic Loader

```python
from pipeline.parsers.source_parsers import load_source_file

# Automatically routes to correct parser based on language/content_type
items = load_source_file("data/vocab.tsv", language="zh", content_type="vocab")
items = load_source_file("data/grammar.csv", language="zh", content_type="grammar")
items = load_source_file("data/vocab.json", language="ja", content_type="vocab")
```

### In Enrichers

Enrichers now delegate to centralized parsers:

```python
from pipeline.parsers.source_parsers import parse_mandarin_vocab_tsv

class MandarinVocabEnricher(BaseEnricher):
    def parse_source(self, source_path):
        return parse_mandarin_vocab_tsv(source_path)
```

### In CLI Tools

The `generate_learning_items.py` CLI now supports loading from original source files:

```bash
# Load from original TSV file (not enriched JSON)
python -m src.pipeline.cli.generate_learning_items \
    --language zh --level HSK1 \
    --category pronunciation \
    --source-type original \
    --source-file data/mandarin_vocab_hsk1.tsv \
    --content-type vocab \
    --output output/pronunciation/

# Load from enriched JSON directory (old behavior)
python -m src.pipeline.cli.generate_learning_items \
    --language zh --level HSK1 \
    --category pronunciation \
    --source-type enriched \
    --source-dir output/enriched/vocab/ \
    --output output/pronunciation/
```

## Return Format

All parsers return a list of dictionaries with normalized field names:

```python
{
    "target_item": str,        # The word/phrase/pattern
    "pos": str,                # Part of speech (if applicable)
    "sense_marker": str,       # Sense marker for disambiguation (Mandarin)
    "romanization": str,       # Romanization/romaji (if applicable)
    "level_min": str,          # Minimum proficiency level
    "level_max": str,          # Maximum proficiency level
    "context_category": str,   # Functional category (French)
    "source_row": int,         # Row number in source file
    # ... other language-specific fields
}
```

## Testing

Comprehensive tests are available in `tests/unit/test_source_parsers.py`:

```bash
# Run all parser tests
PYTHONPATH=src uv run python -m pytest tests/unit/test_source_parsers.py -v

# Run specific test class
PYTHONPATH=src uv run python -m pytest tests/unit/test_source_parsers.py::TestMandarinVocabParser -v
```

Test fixtures are located in `tests/fixtures/`:
- `mandarin_vocab_sample.tsv`
- `japanese_vocab_sample.json`
- `french_vocab_sample.tsv`
- `mandarin_grammar_sample.csv`

## Adding New Parsers

To add support for a new language or format:

1. **Create the parser function** in `source_parsers.py`:
   ```python
   def parse_spanish_vocab_json(source_path: Union[str, Path]) -> List[Dict[str, Any]]:
       """Parse Spanish vocabulary JSON file."""
       # Implementation
       pass
   ```

2. **Add to the generic loader**:
   ```python
   def load_source_file(source_path, language, content_type):
       parsers = {
           ("zh", "vocab"): parse_mandarin_vocab_tsv,
           ("ja", "vocab"): parse_japanese_vocab_json,
           ("fr", "vocab"): parse_french_vocab_tsv,
           ("zh", "grammar"): parse_mandarin_grammar_csv,
           ("es", "vocab"): parse_spanish_vocab_json,  # Add here
       }
       # ...
   ```

3. **Export from `__init__.py`**:
   ```python
   from pipeline.parsers.source_parsers import (
       parse_mandarin_vocab_tsv,
       parse_japanese_vocab_json,
       parse_french_vocab_tsv,
       parse_mandarin_grammar_csv,
       parse_spanish_vocab_json,  # Add here
   )
   ```

4. **Add tests** in `tests/unit/test_source_parsers.py`

5. **Create test fixtures** in `tests/fixtures/`

## Benefits of Centralization

1. **Code Reuse**: Parsers can be used across enrichers, generators, and CLI tools
2. **Consistency**: Single source of truth for parsing logic
3. **Testability**: Centralized tests ensure all parsing works correctly
4. **Maintainability**: Updates to parsing logic only need to be made once
5. **Flexibility**: Easy to add support for new languages and formats
6. **Documentation**: All parsing logic documented in one place

## Migration Notes

### For Existing Enrichers

Enrichers that previously implemented `parse_source()` inline should now import and delegate:

**Before:**
```python
def parse_source(self, source_path):
    items = []
    with open(source_path, "r") as f:
        # ... parsing logic ...
    return items
```

**After:**
```python
from pipeline.parsers.source_parsers import parse_mandarin_vocab_tsv

def parse_source(self, source_path):
    return parse_mandarin_vocab_tsv(source_path)
```

### For CLI Tools

CLI tools that previously required enriched JSON can now load from original sources:

**Before:**
```python
# Only supported loading from enriched JSON
items = load_learning_items_from_dir(enriched_dir)
```

**After:**
```python
# Support both enriched JSON and original sources
if source_type == "enriched":
    items = load_learning_items_from_dir(enriched_dir)
else:
    items = load_source_items_from_file(source_file, language, content_type)
```

## See Also

- [Enrichers Documentation](../enrichers/README.md)
- [Learning Item Generator](../generators/README.md)
- [CLI Tools](../cli/README.md)
