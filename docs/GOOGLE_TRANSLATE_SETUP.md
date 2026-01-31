# Google Translate Integration

This document explains how to set up and use Google Cloud Translation API with the havachat-library-server.

## Setup

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Cloud Translation API:
   - Go to **APIs & Services** > **Library**
   - Search for "Cloud Translation API"
   - Click **Enable**

### 2. Create Service Account

1. Go to **IAM & Admin** > **Service Accounts**
2. Click **Create Service Account**
3. Give it a name (e.g., "havachat-translator")
4. Grant the role: **Cloud Translation API User**
5. Click **Done**

### 3. Create Service Account Key

1. Click on the service account you just created
2. Go to the **Keys** tab
3. Click **Add Key** > **Create new key**
4. Choose **JSON** format
5. Download the JSON key file

### 4. Set Environment Variable

```bash
# In your .env file or shell
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your-service-account-key.json"
```

Or add to your `.env` file:
```bash
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your-service-account-key.json
```

## Usage

### Python API

```python
from havachat.utils.google_translate import GoogleTranslateHelper

# Initialize (automatically uses credentials from environment)
translator = GoogleTranslateHelper()

# Translate single text
translation = translator.translate_single("你好", "zh", "en")
print(translation)  # "Hello"

# Translate batch
texts = ["你好", "谢谢", "再见"]
translations = translator.translate_batch(texts, "zh", "en")
print(translations)  # ["Hello", "Thank you", "Goodbye"]

# Get usage statistics
stats = translator.get_usage_summary()
print(f"Used: {stats['total_characters']} / {stats['monthly_limit']}")
```

### CLI Usage

```bash
# Generate content with Google Translate
python -m havachat.cli.generate_content \
    --language zh \
    --level HSK1 \
    --topic "Daily Life" \
    --learning-items-dir data/learning_items/zh/HSK1 \
    --output output/ \
    --num-conversations 2 \
    --num-stories 2 \
    --use-google-translation
```

### Translation Priority

When multiple translation services are enabled, the priority is:
1. **Google Translate** (if `--use-google-translation`)
2. **Azure Translation** (if `--use-azure-translation`)
3. **LLM Translation** (default fallback)

Example with fallback:
```bash
# Try Google first, fall back to Azure, then LLM
python -m havachat.cli.generate_content \
    --use-google-translation \
    --use-azure-translation \
    ... other args ...
```

## Free Tier Limits

**Google Cloud Translation API Free Tier:**
- **500,000 characters** per month free
- $20 per 1M characters after that

For comparison:
- **Azure Translation**: 2M characters/month free
- **LLM Translation**: No character limits, but uses API tokens

## Caching

Translation caching is enabled by default to reduce API costs:

```python
# Cache enabled (default, 30-day TTL)
translator = GoogleTranslateHelper(enable_cache=True, cache_ttl_days=30)

# Disable cache
translator = GoogleTranslateHelper(enable_cache=False)

# Custom TTL (7 days)
translator = GoogleTranslateHelper(cache_ttl_days=7)
```

Cache files are stored per language pair:
```
data/cache/
├── translation_cache_zh_en.csv   # Chinese → English
├── translation_cache_ja_en.csv   # Japanese → English
└── translation_cache_fr_en.csv   # French → English
```

## Monitoring Usage

```python
from havachat.utils.google_translate import GoogleTranslateHelper

translator = GoogleTranslateHelper()

# Translate some text...
translator.translate_batch(["你好", "谢谢"], "zh", "en")

# Check usage
summary = translator.get_usage_summary()
print(f"Total characters: {summary['total_characters']}")
print(f"Monthly limit: {summary['monthly_limit']}")
print(f"Remaining: {summary['remaining']}")
print(f"Usage: {summary['usage_percent']:.2f}%")

# Cache statistics
print(f"Cache entries: {summary['cache_stats']['total_entries']}")
print(f"Language pairs: {summary['cache_stats']['language_pairs']}")
```

## Error Handling

```python
from havachat.utils.google_translate import GoogleTranslateHelper

try:
    translator = GoogleTranslateHelper()
    translations = translator.translate_batch(texts, "zh", "en")
except ValueError as e:
    print(f"Configuration error: {e}")
    # Fall back to LLM or Azure Translation
except RuntimeError as e:
    print(f"Monthly limit exceeded: {e}")
    # Fall back to LLM or Azure Translation
except Exception as e:
    print(f"Translation failed: {e}")
    # Fall back to LLM translation
```

## Troubleshooting

### Error: "Google Translate credentials not set"

**Solution:** Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

### Error: "Failed to initialize Google Translate client"

**Possible causes:**
1. Invalid JSON key file
2. Service account doesn't have Translation API permissions
3. Translation API not enabled for the project

**Solution:**
1. Verify the JSON key file is valid
2. Grant "Cloud Translation API User" role to the service account
3. Enable Cloud Translation API in the Google Cloud Console

### Error: "Google Translate monthly limit exceeded"

**Solution:**
- Wait until next month for limit reset
- Enable billing on your Google Cloud project for overage charges
- Use Azure Translation or LLM as fallback

### Cache not working

**Check:**
```python
translator = GoogleTranslateHelper()
stats = translator.cache.get_stats()
print(f"Cache enabled: {stats['enabled']}")
print(f"Cache entries: {stats['total_entries']}")
```

If cache is disabled, enable it:
```python
translator = GoogleTranslateHelper(enable_cache=True)
```

## Cost Optimization Tips

1. **Enable caching** (default) to avoid redundant API calls
2. **Longer TTL** (30+ days) for stable content
3. **Batch translations** instead of individual calls
4. **Monitor usage** regularly to stay within free tier
5. **Use LLM translation** for non-critical translations

## Comparison

| Feature | Google Translate | Azure Translation | LLM Translation |
|---------|-----------------|-------------------|-----------------|
| Free tier | 500K chars/month | 2M chars/month | Token-based |
| Quality | Excellent | Excellent | Very Good |
| Speed | Fast (~100-500ms) | Fast (~100-500ms) | Slower (~1-3s) |
| Deterministic | Yes | Yes | No |
| Cache-friendly | Yes | Yes | Yes (with structured output) |
| Cost after free | $20/1M chars | Paid tier required | Token cost |

## Security Notes

- **Never commit** service account JSON keys to version control
- Store keys securely (environment variables, secret managers)
- Rotate keys periodically
- Use least-privilege IAM roles
- Monitor API usage for anomalies

## Support

For Google Cloud Translation API issues:
- [Official Documentation](https://cloud.google.com/translate/docs)
- [Python Client Library](https://googleapis.dev/python/translate/latest/)
- [Pricing](https://cloud.google.com/translate/pricing)
- [Quotas & Limits](https://cloud.google.com/translate/quotas)
