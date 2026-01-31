# Translation Cache

Persistent caching system for deterministic translation services to reduce API costs and improve performance.

## Overview

The translation cache stores translation results from deterministic services (like Azure Translation and Google Translate) with a configurable TTL (Time-To-Live). This avoids redundant API calls for the same text, significantly reducing costs and improving response times.

Cache files are stored in CSV format with one file per language pair (e.g., `translation_cache_zh_en.csv` for Chinese to English), keeping file sizes manageable and easy to inspect.

**Supported Translation Services:**
1. **LLM Translation** (default): Uses structured output for reliable translations
2. **Azure Translation**: 2M free characters/month
3. **Google Translate**: 500K free characters/month

## Features

- **Persistent Storage**: CSV-based cache with one file per language pair
- **Compact Format**: CSV files are smaller than JSON and easier to view
- **Language Pair Files**: Separate cache files (e.g., `translation_cache_zh_en.csv`, `translation_cache_ja_en.csv`)
- **Automatic TTL**: Default 30-day expiration (configurable)
- **Service Isolation**: Separate cache entries for different translation services
- **Language Pair Awareness**: Caches based on source/target language combinations
- **Batch Operations**: Efficient batch caching with partial hit support
- **Auto-cleanup**: Expired entries are automatically removed on load
- **Cost Tracking**: Integrated with Azure Translation usage tracking

## Usage

### With Translation Services

#### Azure Translation

The cache is automatically enabled when using `AzureTranslationHelper`:

```python
from pipeline.utils.azure_translation import AzureTranslationHelper

# Initialize with cache enabled (default)
translator = AzureTranslationHelper(enable_cache=True, cache_ttl_days=30)

# Translate - first call hits API
translations = translator.translate_batch(
    texts=["你好", "谢谢", "再见"],
    from_language="zh",
    to_language="en"
)

# Same request - retrieved from cache (no API call)
cached_translations = translator.translate_batch(
    texts=["你好", "谢谢", "再见"],
    from_language="zh",
    to_language="en"
)
```

#### Google Translate

```python
from pipeline.utils.google_translate import GoogleTranslateHelper

# Initialize with cache enabled (default)
translator = GoogleTranslateHelper(enable_cache=True, cache_ttl_days=30)

# Translate - first call hits API
translations = translator.translate_batch(
    texts=["你好", "谢谢", "再见"],
    from_language="zh",
    to_language="en"
)

# Same request - retrieved from cache (no API call)
cached_translations = translator.translate_batch(
    texts=["你好", "谢谢", "再见"],
    from_language="zh",
    to_language="en"
)
```

### Disable Cache

```python
# Disable caching
translator = AzureTranslationHelper(enable_cache=False)
```

### Custom TTL

```python
# Set custom TTL (e.g., 7 days)
translator = AzureTranslationHelper(enable_cache=True, cache_ttl_days=7)
```

### Direct Cache Usage

For advanced use cases, you can use the cache directly:

```python
from pipeline.utils.translation_cache import TranslationCache

# Initialize cache
cache = TranslationCache(ttl_days=30, enabled=True)

# Single text operations
cache.set("你好", "Hello", "zh", "en", "azure")
translation = cache.get("你好", "zh", "en", "azure")  # Returns "Hello"

# Batch operations
texts = ["你好", "谢谢", "再见"]
translations = ["Hello", "Thank you", "Goodbye"]
cache.set_batch(texts, translations, "zh", "en", "azure")

# Check for cached translations
cached, missing_indices = cache.get_batch(texts, "zh", "en", "azure")
# cached: ["Hello", "Thank you", "Goodbye"]
# missing_indices: []
```

## Cache Statistics

Get cache usage statistics:

```python
translator = AzureTranslationHelper()

# Translate some text
translator.translate_batch(["你好", "谢谢"], "zh", "en")

# Get statistics
stats = translator.get_usage_summary()
print(stats)
```

Output:
```json
{
  "total_characters": 4,
  "monthly_limit": 2000000,
  "remaining": 1999996,
  "usage_percent": 0.0,
  "cache_stats": {
    "total_entries": 2,
    "cache_size_mb": 0.001,
    "ttl_days": 30,
    "cache_dir": "data/cache",
    "language_pairs": ["zh_en"],
    "enabled": true
  }
}
```

## Cache Management

### Clear Cache

```python
# Clear all cache entries
translator.cache.clear()
```

### View Cache Contents

Cache files are stored per language pair in CSV format:

```bash
# View cache files
ls -lh data/cache/
# translation_cache_zh_en.csv
# translation_cache_ja_en.csv

# View specific cache file
cat data/cache/translation_cache_zh_en.csv
```

Example CSV content:
```csv
text,translation,service,created_at,expires_at
你好,Hello,azure,1706745600.0,1709337600.0
谢谢,Thank you,azure,1706745601.0,1709337601.0
再见,Goodbye,azure,1706745602.0,1709337602.0
```

CSV files can be opened in Excel, Google Sheets, or any spreadsheet program for easy inspection.

## Cost Savings

### Example Scenario

- Generate 100 conversations with 600 segments total
- Each segment translated once = 600 API calls
- Regenerate same conversations 5 times = 3,000 API calls without cache
- With cache: First run = 600 API calls, subsequent runs = 0 API calls
- **Savings: 80% reduction in API calls**

### Character Savings

Azure Translation: 2M free characters/month

- Without cache: Re-translating 10,000 characters 10 times = 100,000 characters
- With cache: First translation = 10,000 characters, next 9 times = 0 characters
- **Savings: 90,000 characters (90% reduction)**

## Technical Details

### Cache Key Generation

Cache keys are SHA-256 hashes of:
- Service name (e.g., "azure")
- Source language code
- Target language code
- Source text

This ensures deterministic lookups and prevents collisions.

### TTL Implementation

- Default: 30 days (configurable)
- Stored as Unix timestamp
- Checked on retrieval
- Expired entries cleaned on cache load
- Auto-cleanup keeps cache size manageable

### Performance

- **Cache Hit**: ~0.1ms (no network call)
- **Cache Miss**: ~100-500ms (network call + caching)
- **Batch Operations**: Efficiently handles partial hits

### Storage

- Format: CSV (compact, human-readable, spreadsheet-compatible)
- Location: `data/cache/translation_cache_{from_lang}_{to_lang}.csv`
- Examples:
  - Chinese → English: `data/cache/translation_cache_zh_en.csv`
  - Japanese → English: `data/cache/translation_cache_ja_en.csv`
  - French → English: `data/cache/translation_cache_fr_en.csv`
- Excluded from git via `.gitignore`
- Persists across application restarts
- One file per language pair keeps files small and manageable

## Testing

Run unit tests:

```bash
uv run python -m pytest tests/unit/test_translation_cache.py -v
```

Test coverage includes:
- Basic set/get operations
- Batch operations
- Cache expiration
- Persistence across instances
- Service isolation
- Language pair handling
- TTL management

## Best Practices

1. **Enable for Production**: Always enable cache in production to reduce costs
2. **Longer TTL for Stable Content**: Use 30+ days TTL for content that doesn't change
3. **Monitor Cache Size**: Check cache stats periodically to ensure efficient storage
4. **Clear After Major Changes**: Clear cache if translation logic changes significantly
5. **Backup Cache File**: Consider backing up `translation_cache.json` for disaster recovery

## Configuration

### Environment Variables

**Azure Translation:**
```bash
AZURE_TEXT_TRANSLATION_APIKEY=your_api_key
AZURE_TEXT_TRANSLATION_REGION=your_region
```

**Google Translate:**
```bash
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

No additional environment variables required for cache. Cache is configured via constructor parameters.

### File Locations

- Cache directory: `data/cache/`
- Cache files: `data/cache/translation_cache_{from_lang}_{to_lang}.csv`
- Example: `data/cache/translation_cache_zh_en.csv`
- Excluded from git: Yes (via `.gitignore`)

## Troubleshooting

### Cache Not Working

Check if cache is enabled:
```python
translator = AzureTranslationHelper()
print(translator.cache.enabled)  # Should be True
```

### Cache File Missing

Cache files are created automatically on first write for each language pair. If missing, they will be recreated when translations are cached.

```bash
# Check for cache files
ls -lh data/cache/translation_cache_*.csv
```

### Expired Entries

Entries expire after TTL. Check expiration:
```python
stats = translator.cache.get_stats()
print(f"Total entries: {stats['total_entries']}")
print(f"TTL: {stats['ttl_days']} days")
```

### Cache Size Growing

Clear old entries:
```python
translator.cache.clear()
```

Or adjust TTL for future entries:
```python
translator = AzureTranslationHelper(cache_ttl_days=7)  # Shorter TTL
```

## CSV Format Advantages

1. **Smaller File Size**: CSV is more compact than JSON for tabular data
2. **Easy Inspection**: Open directly in Excel, Google Sheets, or text editors
3. **Language Pair Isolation**: One file per pair keeps files manageable
4. **Fast Loading**: CSV parsing is efficient for large datasets
5. **Manual Editing**: Easy to edit translations manually if needed
6. **Git-Friendly**: Smaller diffs when cache changes (if tracked)

## Limitations

1. **Deterministic Services Only**: Cache is designed for deterministic services (Azure Translation, Google Translate). Not recommended for LLM-based translation due to variability.
2. **Disk Space**: Large caches may consume significant disk space. Monitor with `get_stats()`.
3. **No Invalidation**: Cache entries are not invalidated on translation updates. Clear cache manually if needed.
4. **Single Machine**: Cache is local to the machine. Not shared across distributed systems.

## Future Enhancements

Potential improvements:
- Redis/Memcached support for distributed caching
- Compression for large cache files
- LRU eviction policy for size-limited caches
- Cache warming from previous exports
- Analytics on cache hit rates
