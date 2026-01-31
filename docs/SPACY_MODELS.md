# Language Tokenization for Dictionary Lookups

The translation dictionary system uses language-specific tokenization to provide accurate word-level dictionary lookups.

## Tokenization Approaches

### Mandarin Chinese (zh) - **jieba**

We use **jieba** for Chinese tokenization instead of spaCy due to Python 3.14 compatibility issues with spaCy.

```bash
pip install jieba
```

**Why jieba?**
- ✅ **Python 3.14 compatible** (spaCy requires Python < 3.14)
- ✅ **Excellent Chinese support**: Trained specifically for Chinese
- ✅ **POS tagging**: Includes part-of-speech tagging
- ✅ **Fast and accurate**: Industry-standard for Chinese NLP

### Other Languages - **Future**

For languages other than Chinese, we can use spaCy when Python < 3.14:

```bash
# Japanese
pip install spacy
python -m spacy download ja_core_news_sm

# French
python -m spacy download fr_core_news_sm
```

**Note**: Due to Python 3.14 compatibility issues, spaCy is currently not used. We'll add support when spaCy releases Python 3.14-compatible versions.

## Usage

The dictionary system automatically selects the appropriate tokenizer based on the language.

### Example: Chinese Dictionary Lookup with jieba

```python
from src.pipeline.utils.dictionary import DictionaryFactory

# Load dictionary (automatically uses jieba for Chinese)
dictionary = DictionaryFactory.get_dictionary("zh")

# Tokenize and lookup words
text = "我要一斤白菜"
word_defs = dictionary.tokenize_and_lookup(text)

# Returns: [
#   ("我", "PRON", "I; me"),
#   ("要", "VERB", "to want; to need"),
#   ("一", "NUM", "one"),
#   ("斤", "NOUN", "catty (unit of weight)"),
#   ("白菜", "NOUN", "Chinese cabbage; bok choy")
# ]
```

## Benefits for Translation

1. **Context-aware**: LLM receives individual word meanings with POS tags
2. **Accurate tokenization**: jieba handles Chinese word segmentation properly
3. **Better disambiguation**: Multiple dictionary meanings can be filtered by POS
4. **Natural output**: LLM combines word meanings to create natural translations

## jieba POS Tags

jieba uses Chinese-specific POS tags that are mapped to universal tags:

| jieba Tag | Universal Tag | Meaning |
|-----------|---------------|---------|
| n | NOUN | 名词 (noun) |
| v | VERB | 动词 (verb) |
| a | ADJ | 形容词 (adjective) |
| d | ADV | 副词 (adverb) |
| p | ADP | 介词 (preposition) |
| m | NUM | 数词 (number) |
| q | PART | 量词 (measure word) |
| r | PRON | 代词 (pronoun) |

## Python 3.14 Compatibility

**Issue**: spaCy uses Pydantic V1 which is incompatible with Python 3.14+

**Solution**: Use jieba for Chinese tokenization
- jieba is fully compatible with Python 3.14
- Provides excellent Chinese word segmentation
- Includes POS tagging functionality

**Future**: When spaCy releases Python 3.14 support, we can add it back for other languages.

## Without jieba

If jieba is not installed:
- Falls back to character-by-character lookup
- Less accurate for compound words
- No POS tagging
- Dictionary lookups will be basic string matches

**Recommendation**: Always install jieba for Chinese language processing:

```bash
pip install jieba
```
