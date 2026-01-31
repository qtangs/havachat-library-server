"""Google Translate API utility for translation.

Provides translation using Google Cloud Translation API.
Free tier: First 500,000 characters per month are free.

Default: Uses v3 (Advanced) API which provides better quality translations.
Fallback: Can use v2 (Basic) API if v3 is not available.
"""

import os
from typing import List, Literal

from google.cloud import translate_v2 as translate_v2
from google.cloud import translate_v3 as translate_v3
from loguru import logger


class GoogleTranslateHelper:
    """Helper for Google Cloud Translation API with character usage tracking."""
    
    def __init__(
        self, 
        enable_cache: bool = True, 
        cache_ttl_days: int = 30,
        version: Literal["v2", "v3"] = "v3",
        project_id: str = None,
        location: str = "global"
    ):
        """Initialize Google Translate client with credentials from environment.
        
        Args:
            enable_cache: Whether to enable translation caching (default: True)
            cache_ttl_days: Cache time-to-live in days (default: 30 / 1 month)
            version: API version to use - "v2" (Basic) or "v3" (Advanced) (default: "v3")
            project_id: GCP project ID (required for v3, auto-detected if not provided)
            location: Location for v3 API (default: "global")
        
        Raises:
            ValueError: If credentials are not set or client initialization fails
        """
        self.version = version
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = location
        
        try:
            if version == "v3":
                # V3 API (Advanced) - better quality translations
                if not self.project_id:
                    raise ValueError(
                        "Project ID required for v3 API. Set GOOGLE_CLOUD_PROJECT environment variable "
                        "or pass project_id parameter."
                    )
                self.client = translate_v3.TranslationServiceClient()
                self.parent = f"projects/{self.project_id}/locations/{self.location}"
                logger.info(f"Initialized Google Translate v3 (Advanced) for project: {self.project_id}")
            else:
                # V2 API (Basic) - simpler but older
                self.client = translate_v2.Client()
                logger.info("Initialized Google Translate v2 (Basic)")
        except Exception as e:
            raise ValueError(f"Failed to initialize Google Translate {version} client: {e}")
        
        # Character usage tracking
        self.total_characters = 0
        self.monthly_limit = 500_000  # 500K free characters per month
        
        # Translation cache for cost savings
        from src.pipeline.utils.translation_cache import TranslationCache
        self.cache = TranslationCache(enabled=enable_cache, ttl_days=cache_ttl_days)
    
    def translate_batch(
        self, 
        texts: List[str], 
        from_language: str, 
        to_language: str = "en"
    ) -> List[str]:
        """Translate a batch of texts and track character usage.
        
        Uses cache to avoid redundant API calls for previously translated texts.
        
        Args:
            texts: List of texts to translate
            from_language: Source language code (e.g., 'zh', 'ja', 'fr')
            to_language: Target language code (default: 'en')
        
        Returns:
            List of translated texts in the same order as input
        
        Raises:
            RuntimeError: If monthly character limit is exceeded
        """
        if not texts:
            return []
        
        # Check cache for existing translations
        cached_translations, missing_indices = self.cache.get_batch(
            texts, from_language, to_language, service="google"
        )
        
        # If all translations are cached, return immediately
        if not missing_indices:
            logger.info(f"All {len(texts)} translations retrieved from cache")
            return cached_translations
        
        # Prepare texts that need translation
        texts_to_translate = [texts[i] for i in missing_indices]
        
        # Count characters before translation (only for non-cached texts)
        char_count = sum(len(text) for text in texts_to_translate)
        
        # Check if this would exceed monthly limit
        if self.total_characters + char_count > self.monthly_limit:
            remaining = self.monthly_limit - self.total_characters
            logger.warning(
                f"Translation would exceed monthly limit. "
                f"Used: {self.total_characters:,} / {self.monthly_limit:,}, "
                f"Remaining: {remaining:,}, Requested: {char_count:,}"
            )
            raise RuntimeError(
                f"Google Translate monthly limit exceeded. "
                f"{remaining:,} characters remaining, but {char_count:,} requested."
            )
        
        try:
            # Translate based on API version
            if self.version == "v3":
                # V3 API - batch translate with advanced features
                response = self.client.translate_text(
                    parent=self.parent,
                    contents=texts_to_translate,
                    source_language_code=from_language,
                    target_language_code=to_language,
                    mime_type="text/plain"
                )
                
                # Extract translations from v3 response
                new_translations = [
                    translation.translated_text 
                    for translation in response.translations
                ]
            else:
                # V2 API - returns list of dicts with 'translatedText' key
                results = self.client.translate(
                    texts_to_translate,
                    source_language=from_language,
                    target_language=to_language
                )
                
                # Extract translations from v2 response
                new_translations = []
                for result in results:
                    if isinstance(result, dict) and 'translatedText' in result:
                        new_translations.append(result['translatedText'])
                    else:
                        logger.warning(f"Unexpected result format: {result}")
                        new_translations.append("")
            
            # Update character usage
            self.total_characters += char_count
            logger.debug(
                f"Translated {len(texts_to_translate)} texts ({char_count:,} chars) using {self.version}. "
                f"Total usage: {self.total_characters:,} / {self.monthly_limit:,} "
                f"({(self.total_characters / self.monthly_limit * 100):.2f}%)"
            )
            
            # Store new translations in cache
            self.cache.set_batch(
                texts_to_translate, 
                new_translations, 
                from_language, 
                to_language, 
                service="google"
            )
            
            # Merge cached and new translations
            final_translations = []
            new_translation_idx = 0
            for i in range(len(texts)):
                if i in missing_indices:
                    final_translations.append(new_translations[new_translation_idx])
                    new_translation_idx += 1
                else:
                    final_translations.append(cached_translations[i])
            
            return final_translations
            
        except Exception as e:
            logger.error(f"Google Translate API error: {e}")
            raise
    
    def translate_single(
        self, 
        text: str, 
        from_language: str, 
        to_language: str = "en"
    ) -> str:
        """Translate a single text.
        
        Args:
            text: Text to translate
            from_language: Source language code
            to_language: Target language code (default: 'en')
        
        Returns:
            Translated text
        """
        results = self.translate_batch([text], from_language, to_language)
        return results[0] if results else ""
    
    def get_usage_summary(self) -> dict:
        """Get current character usage statistics.
        
        Returns:
            Dictionary with usage stats:
            - api_version: API version being used (v2 or v3)
            - total_characters: Total characters translated
            - monthly_limit: Monthly character limit
            - remaining: Characters remaining
            - usage_percent: Percentage of limit used
            - cache_stats: Cache statistics
        """
        remaining = self.monthly_limit - self.total_characters
        usage_percent = (self.total_characters / self.monthly_limit) * 100
        
        return {
            "api_version": self.version,
            "total_characters": self.total_characters,
            "monthly_limit": self.monthly_limit,
            "remaining": remaining,
            "usage_percent": round(usage_percent, 2),
            "cache_stats": self.cache.get_stats()
        }
    
    def reset_usage(self):
        """Reset character usage counter (for testing or new month)."""
        self.total_characters = 0
        logger.info("Google Translate usage counter reset")
