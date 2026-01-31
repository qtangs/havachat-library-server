"""Translation cache for deterministic translation services.

Provides persistent caching with TTL support to avoid redundant API calls
and reduce costs for deterministic translation services like Azure Translation.

Default TTL: 1 month (30 days)
Storage: CSV file-based cache in data/cache/ (one file per language pair)
"""

import csv
import hashlib
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loguru import logger


class TranslationCache:
    """Persistent cache for translation results with TTL support."""
    
    DEFAULT_TTL_DAYS = 30  # 1 month default TTL
    
    def __init__(
        self, 
        cache_dir: Optional[Path] = None,
        ttl_days: int = DEFAULT_TTL_DAYS,
        enabled: bool = True
    ):
        """Initialize translation cache.
        
        Args:
            cache_dir: Directory for cache storage (default: data/cache/)
            ttl_days: Time-to-live in days (default: 30 days / 1 month)
            enabled: Whether caching is enabled (default: True)
        """
        self.enabled = enabled
        self.ttl_days = ttl_days
        self.ttl_seconds = ttl_days * 24 * 60 * 60
        
        # Set up cache directory
        if cache_dir is None:
            cache_dir = Path(__file__).parent.parent.parent.parent / "data" / "cache"
        
        self.cache_dir = cache_dir
        
        # Create cache directory if it doesn't exist
        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache: key -> dict with cache data
        # Cache files are per language pair
        self.cache: Dict[str, dict] = {}
        self.loaded_language_pairs = set()  # Track which language pairs have been loaded
    
    def _get_cache_file(
        self,
        from_language: str,
        to_language: str
    ) -> Path:
        """Get cache file path for a language pair.
        
        Args:
            from_language: Source language code
            to_language: Target language code
        
        Returns:
            Path to cache file for this language pair
        """
        filename = f"translation_cache_{from_language}_{to_language}.csv"
        return self.cache_dir / filename
    
    def _generate_cache_key(
        self, 
        text: str, 
        from_language: str, 
        to_language: str,
        service: str
    ) -> str:
        """Generate cache key from translation parameters.
        
        Args:
            text: Source text
            from_language: Source language code
            to_language: Target language code
            service: Translation service name (e.g., 'azure', 'google')
        
        Returns:
            Cache key as hex digest
        """
        # Create deterministic key from all parameters
        key_data = f"{service}:{from_language}:{to_language}:{text}"
        return hashlib.sha256(key_data.encode('utf-8')).hexdigest()
    
    def _load_cache_for_language_pair(
        self,
        from_language: str,
        to_language: str
    ) -> None:
        """Load cache from disk for a specific language pair.
        
        Args:
            from_language: Source language code
            to_language: Target language code
        """
        lang_pair = f"{from_language}_{to_language}"
        if lang_pair in self.loaded_language_pairs:
            return  # Already loaded
        
        cache_file = self._get_cache_file(from_language, to_language)
        
        if not cache_file.exists():
            logger.debug(f"No cache file found at {cache_file}")
            self.loaded_language_pairs.add(lang_pair)
            return
        
        try:
            entries_loaded = 0
            current_time = time.time()
            
            with open(cache_file, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Skip expired entries during load
                    expires_at = float(row['expires_at'])
                    if current_time <= expires_at:
                        cache_key = self._generate_cache_key(
                            row['text'],
                            from_language,
                            to_language,
                            row['service']
                        )
                        self.cache[cache_key] = {
                            'text': row['text'],
                            'translation': row['translation'],
                            'from_language': from_language,
                            'to_language': to_language,
                            'service': row['service'],
                            'created_at': float(row['created_at']),
                            'expires_at': float(row['expires_at'])
                        }
                        entries_loaded += 1
            
            logger.debug(f"Loaded {entries_loaded} cache entries from {cache_file}")
            self.loaded_language_pairs.add(lang_pair)
            
        except (IOError, ValueError, KeyError) as e:
            logger.error(f"Failed to load cache from {cache_file}: {e}")
            self.loaded_language_pairs.add(lang_pair)
    
    def _save_cache_for_language_pair(
        self,
        from_language: str,
        to_language: str
    ) -> None:
        """Save cache to disk for a specific language pair.
        
        Args:
            from_language: Source language code
            to_language: Target language code
        """
        cache_file = self._get_cache_file(from_language, to_language)
        
        try:
            # Filter entries for this language pair
            entries = [
                entry for entry in self.cache.values()
                if entry['from_language'] == from_language and entry['to_language'] == to_language
            ]
            
            if not entries:
                # No entries for this language pair, remove file if exists
                if cache_file.exists():
                    cache_file.unlink()
                return
            
            # Write to CSV
            with open(cache_file, 'w', encoding='utf-8', newline='') as f:
                fieldnames = ['text', 'translation', 'service', 'created_at', 'expires_at']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for entry in entries:
                    writer.writerow({
                        'text': entry['text'],
                        'translation': entry['translation'],
                        'service': entry['service'],
                        'created_at': entry['created_at'],
                        'expires_at': entry['expires_at']
                    })
            
            logger.debug(f"Saved {len(entries)} cache entries to {cache_file}")
            
        except IOError as e:
            logger.error(f"Failed to save cache to {cache_file}: {e}")
    
    def get(
        self, 
        text: str, 
        from_language: str, 
        to_language: str,
        service: str = "azure"
    ) -> Optional[str]:
        """Get cached translation if available and not expired.
        
        Args:
            text: Source text
            from_language: Source language code
            to_language: Target language code
            service: Translation service name (default: 'azure')
        
        Returns:
            Cached translation or None if not found/expired
        """
        if not self.enabled:
            return None
        
        # Load cache for this language pair if not already loaded
        self._load_cache_for_language_pair(from_language, to_language)
        
        cache_key = self._generate_cache_key(text, from_language, to_language, service)
        
        if cache_key not in self.cache:
            return None
        
        entry = self.cache[cache_key]
        
        # Check if expired
        if time.time() > entry.get('expires_at', 0):
            logger.debug(f"Cache entry expired for: {text[:50]}...")
            del self.cache[cache_key]
            return None
        
        logger.debug(f"Cache hit for: {text[:50]}...")
        return entry['translation']
    
    def get_batch(
        self,
        texts: List[str],
        from_language: str,
        to_language: str,
        service: str = "azure"
    ) -> Tuple[List[Optional[str]], List[int]]:
        """Get cached translations for a batch of texts.
        
        Args:
            texts: List of source texts
            from_language: Source language code
            to_language: Target language code
            service: Translation service name (default: 'azure')
        
        Returns:
            Tuple of (cached_translations, missing_indices)
            - cached_translations: List with cached values or None for cache misses
            - missing_indices: List of indices where cache was missed
        """
        if not self.enabled:
            return [None] * len(texts), list(range(len(texts)))
        
        cached_translations = []
        missing_indices = []
        
        for i, text in enumerate(texts):
            cached = self.get(text, from_language, to_language, service)
            cached_translations.append(cached)
            if cached is None:
                missing_indices.append(i)
        
        hit_count = len(texts) - len(missing_indices)
        if hit_count > 0:
            logger.info(f"Cache hits: {hit_count}/{len(texts)} ({hit_count/len(texts)*100:.1f}%)")
        
        return cached_translations, missing_indices
    
    def set(
        self,
        text: str,
        translation: str,
        from_language: str,
        to_language: str,
        service: str = "azure"
    ) -> None:
        """Store translation in cache.
        
        Args:
            text: Source text
            translation: Translated text
            from_language: Source language code
            to_language: Target language code
            service: Translation service name (default: 'azure')
        """
        if not self.enabled:
            return
        
        cache_key = self._generate_cache_key(text, from_language, to_language, service)
        
        entry = {
            'text': text,
            'translation': translation,
            'from_language': from_language,
            'to_language': to_language,
            'service': service,
            'created_at': time.time(),
            'expires_at': time.time() + self.ttl_seconds
        }
        
        self.cache[cache_key] = entry
    
    def set_batch(
        self,
        texts: List[str],
        translations: List[str],
        from_language: str,
        to_language: str,
        service: str = "azure"
    ) -> None:
        """Store batch translations in cache.
        
        Args:
            texts: List of source texts
            translations: List of translated texts
            from_language: Source language code
            to_language: Target language code
            service: Translation service name (default: 'azure')
        """
        if not self.enabled:
            return
        
        if len(texts) != len(translations):
            logger.error(f"Text and translation count mismatch: {len(texts)} vs {len(translations)}")
            return
        
        for text, translation in zip(texts, translations):
            self.set(text, translation, from_language, to_language, service)
        
        # Save after batch operations for this language pair
        self._save_cache_for_language_pair(from_language, to_language)
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache = {}
        self.loaded_language_pairs = set()
        
        # Remove all cache files
        if self.cache_dir.exists():
            for cache_file in self.cache_dir.glob("translation_cache_*.csv"):
                cache_file.unlink()
        
        logger.info("Cache cleared")
    
    def get_stats(self) -> dict:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache stats:
            - total_entries: Total number of cached entries
            - cache_size_mb: Total size of all cache files in MB
            - ttl_days: Time-to-live in days
            - cache_dir: Path to cache directory
            - language_pairs: List of language pairs with cache files
        """
        cache_size_mb = 0.0
        language_pairs = []
        
        if self.cache_dir.exists():
            for cache_file in self.cache_dir.glob("translation_cache_*.csv"):
                cache_size_mb += cache_file.stat().st_size / (1024 * 1024)
                # Extract language pair from filename
                name = cache_file.stem.replace("translation_cache_", "")
                language_pairs.append(name)
        
        return {
            "total_entries": len(self.cache),
            "cache_size_mb": round(cache_size_mb, 3),
            "ttl_days": self.ttl_days,
            "cache_dir": str(self.cache_dir),
            "language_pairs": language_pairs,
            "enabled": self.enabled
        }
