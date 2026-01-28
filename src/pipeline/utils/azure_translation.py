"""Azure Text Translation utility for adding English translations to examples.

Provides 2M free characters per month.
"""

import os
from typing import List, Tuple

from azure.ai.translation.text import TextTranslationClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from loguru import logger


class AzureTranslationHelper:
    """Helper for Azure Text Translation API with character usage tracking."""
    
    def __init__(self):
        """Initialize Azure Translation client with credentials from environment."""
        self.apikey = os.getenv("AZURE_TEXT_TRANSLATION_APIKEY")
        self.region = os.getenv("AZURE_TEXT_TRANSLATION_REGION")
        
        if not self.apikey or not self.region:
            raise ValueError(
                "Azure Translation credentials not set. Please set AZURE_TEXT_TRANSLATION_APIKEY "
                "and AZURE_TEXT_TRANSLATION_REGION environment variables."
            )
        
        credential = AzureKeyCredential(self.apikey)
        self.client = TextTranslationClient(credential=credential, region=self.region)
        
        # Character usage tracking
        self.total_characters = 0
        self.monthly_limit = 2_000_000  # 2M free characters per month
    
    def translate_batch(
        self, 
        texts: List[str], 
        from_language: str, 
        to_language: str = "en"
    ) -> List[str]:
        """Translate a batch of texts and track character usage.
        
        Args:
            texts: List of texts to translate
            from_language: Source language code (e.g., 'zh', 'ja', 'fr')
            to_language: Target language code (default: 'en')
        
        Returns:
            List of translated texts in the same order as input
        
        Raises:
            HttpResponseError: If translation API request fails
            RuntimeError: If monthly character limit is exceeded
        """
        if not texts:
            return []
        
        # Count characters before translation
        char_count = sum(len(text) for text in texts)
        
        # Check if this would exceed monthly limit
        if self.total_characters + char_count > self.monthly_limit:
            remaining = self.monthly_limit - self.total_characters
            logger.warning(
                f"Translation would exceed monthly limit. "
                f"Used: {self.total_characters:,} / {self.monthly_limit:,}, "
                f"Remaining: {remaining:,}, Requested: {char_count:,}"
            )
            raise RuntimeError(
                f"Azure Translation monthly limit exceeded. "
                f"{remaining:,} characters remaining, but {char_count:,} requested."
            )
        
        try:
            response = self.client.translate(
                body=texts,
                from_language=from_language,
                to_language=[to_language]
            )
            
            # Extract translations
            translations = []
            for translation in response:
                if translation.translations:
                    translations.append(translation.translations[0].text)
                else:
                    logger.warning(f"No translation returned for text: {texts[len(translations)]}")
                    translations.append("")  # Empty string for failed translations
            
            # Update character usage
            self.total_characters += char_count
            logger.debug(
                f"Translated {len(texts)} texts ({char_count:,} chars). "
                f"Total usage: {self.total_characters:,} / {self.monthly_limit:,} "
                f"({(self.total_characters / self.monthly_limit * 100):.2f}%)"
            )
            
            return translations
            
        except HttpResponseError as e:
            logger.error(f"Azure Translation API error: {e.error.code if e.error else 'Unknown'}")
            if e.error:
                logger.error(f"Message: {e.error.message}")
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
            - total_characters: Total characters translated
            - monthly_limit: Monthly character limit
            - remaining: Characters remaining
            - usage_percent: Percentage of limit used
        """
        remaining = self.monthly_limit - self.total_characters
        usage_percent = (self.total_characters / self.monthly_limit) * 100
        
        return {
            "total_characters": self.total_characters,
            "monthly_limit": self.monthly_limit,
            "remaining": remaining,
            "usage_percent": round(usage_percent, 2)
        }
    
    def reset_usage(self):
        """Reset character usage counter (for testing or new month)."""
        self.total_characters = 0
        logger.info("Azure Translation usage counter reset")
