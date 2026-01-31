# Character Validation in Content Generation

## Overview

This feature ensures that generated conversations and stories only use characters present in the provided vocabulary. When content contains characters not in the vocabulary, it is automatically marked for review.

## Implementation

### 1. Schema Changes

**File:** `src/pipeline/validators/schema.py`

Added two new fields to the `ContentUnit` model:

```python
class ContentStatus(str, Enum):
    """Status of content unit."""
    ACTIVE = "active"
    FOR_REVIEW = "for_review"

class ContentUnit(BaseModel):
    # ... existing fields ...
    
    status: ContentStatus = Field(
        default=ContentStatus.ACTIVE,
        description="Content validation status (active or for_review)"
    )
    validation_notes: Optional[List[str]] = Field(
        default=None,
        description="List of validation issues requiring review"
    )
```

### 2. Character Validator

**File:** `src/pipeline/validators/character_validator.py`

Core validation logic for detecting characters not present in vocabulary:

- `extract_chinese_characters(text)` - Extracts all Chinese characters from text
- `validate_chinese_characters(content, vocab)` - Validates Chinese content against vocabulary
- `validate_japanese_characters(content, vocab)` - Placeholder for Japanese (to be implemented)
- `validate_french_characters(content, vocab)` - Placeholder for French (to be implemented)
- `validate_content_characters(content, vocab, language)` - Language-agnostic validation

#### Chinese Character Detection

Chinese characters are detected using the Unicode range U+4E00 to U+9FFF (CJK Unified Ideographs), which covers most common Chinese characters.

```python
def extract_chinese_characters(text: str) -> Set[str]:
    """Extract all Chinese characters from text."""
    chinese_chars = set(char for char in text if '\u4e00' <= char <= '\u9fff')
    return chinese_chars
```

### 3. Integration with Content Generator

**File:** `src/pipeline/generators/content_generator.py`

The validation is integrated into the `_convert_to_content_batch` method, which processes generated content:

```python
# Validate character coverage for language-specific content
vocab_items = [
    item.target_item 
    for item in self.all_learning_items.values()
    if item.category == Category.VOCAB
]
is_valid, missing_chars = validate_content_characters(
    full_text, vocab_items, self.language
)

# Set status and validation notes based on character validation
if is_valid:
    content_status = ContentStatus.ACTIVE
    validation_notes = None
else:
    content_status = ContentStatus.FOR_REVIEW
    validation_notes = [
        f"Missing characters not in vocabulary: {', '.join(missing_chars)}"
    ]
```

## Language Support

### ✅ Chinese (Mandarin)

**Status:** Fully implemented

**Validation Logic:**
- Extracts all Chinese characters from content text
- Extracts all Chinese characters from vocabulary items
- Identifies characters in content but not in vocabulary
- Marks content as "for_review" if missing characters found

**Example:**
```python
vocab = ["我", "爱", "学习"]  # I, love, study
content = "我爱你"  # I love you

# Validation fails: '你' (you) not in vocabulary
# Status: for_review
# Validation note: "Missing characters not in vocabulary: 你"
```

### ⚪ Japanese

**Status:** Placeholder

**Coverage:** Hiragana, Katakana, and Kanji characters (Unicode ranges U+3040-U+309F, U+30A0-U+30FF, U+4E00-U+9FFF)

**To be implemented:** Similar to Chinese validation, but considering all Japanese character types.

### ⚪ French

**Status:** Placeholder

**Coverage:** Special characters with accents (à, â, é, è, ê, ë, î, ï, ô, ù, û, ü, ÿ, ç, æ, œ)

**To be implemented:** Validation will focus on ensuring accented characters are covered in vocabulary.

### Other Languages

For languages without character validation implemented (English, Spanish, etc.), the validation automatically passes and sets status to "active".

## Usage in CLI

When generating content using the CLI:

```bash
python -m src.pipeline.cli.generate_content \
    --language zh \
    --level HSK1 \
    --topic "Daily Life" \
    --learning-items-dir ./learning_items \
    --output ./output
```

The generated JSON files will include the validation status:

```json
{
  "id": "b50e8400-e29b-41d4-a716-446655440000",
  "language": "zh",
  "type": "conversation",
  "title": "Greeting at School",
  "status": "for_review",
  "validation_notes": [
    "Missing characters not in vocabulary: 您, 呢"
  ],
  ...
}
```

## Filtering Content

To find content that needs review:

```python
from pathlib import Path
import json

def find_content_for_review(output_dir: Path):
    """Find all content units marked for review."""
    for_review = []
    
    for json_file in output_dir.rglob("*.json"):
        with open(json_file) as f:
            content = json.load(f)
            
        if content.get("status") == "for_review":
            for_review.append({
                "file": json_file.name,
                "title": content.get("title"),
                "notes": content.get("validation_notes")
            })
    
    return for_review
```

## Testing

### Unit Tests

**File:** `tests/unit/test_character_validator.py`

- Character extraction tests
- Validation logic tests
- Language routing tests

### Integration Tests

**File:** `tests/integration/test_character_validation.py`

- End-to-end validation with sample vocabulary
- Placeholder behavior for Japanese and French

### Demo Script

**File:** `demo_character_validation.py`

Run the demo to see character validation in action:

```bash
uv run python demo_character_validation.py
```

## Future Enhancements

1. **Japanese Implementation**
   - Validate Hiragana, Katakana, and Kanji separately
   - Consider different reading variations (kun/on)

2. **French Implementation**
   - Validate accented character coverage
   - Consider word forms (masculine/feminine, singular/plural)

3. **Configurable Strictness**
   - Allow some percentage of unknown characters
   - Configure per-level thresholds

4. **Morphological Variations**
   - Account for inflected forms in validation
   - Use lemmatization for better matching

5. **Manual Override**
   - CLI flag to manually approve flagged content
   - Batch review tools for content editors

## Related Files

- `src/pipeline/validators/schema.py` - Schema definitions
- `src/pipeline/validators/character_validator.py` - Validation logic
- `src/pipeline/generators/content_generator.py` - Integration with content generation
- `tests/unit/test_character_validator.py` - Unit tests
- `tests/integration/test_character_validation.py` - Integration tests
- `demo_character_validation.py` - Demo script
