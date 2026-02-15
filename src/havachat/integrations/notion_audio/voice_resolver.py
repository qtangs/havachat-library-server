"""
Voice Resolver for Notion Voice Database

Resolves voice IDs from Notion Voice Database with caching to minimize API calls.
Uses shared NotionClient for consistency with other database operations.
"""

from typing import Dict, Optional

from loguru import logger

from src.havachat.utils.notion_client import NotionClient


class VoiceResolver:
    """
    Resolves ElevenLabs voice IDs from Notion Voice Database relations.
    
    Caches voice lookups in memory during batch processing to minimize
    Notion API calls. Falls back to default voice if lookup fails.
    """
    
    def __init__(
        self,
        notion_client: NotionClient,
        voice_db_id: str,
        default_voice_id: str
    ):
        """
        Initialize VoiceResolver with shared NotionClient.
        
        Args:
            notion_client: Shared NotionClient instance for database queries
            voice_db_id: Notion Voice Database ID
            default_voice_id: Fallback voice ID when resolution fails
        """
        self.notion_client = notion_client
        self.voice_db_id = voice_db_id
        self.default_voice_id = default_voice_id
        
        # In-memory cache: {relation_id -> voice_id}
        self._cache: Dict[str, str] = {}
        
        logger.debug(
            f"VoiceResolver initialized (database: {voice_db_id}, "
            f"default: {default_voice_id})"
        )
    
    def _get_default_voice(self) -> str:
        """
        Get default voice ID.
        
        Returns:
            Default voice ID from configuration
        """
        return self.default_voice_id
    
    def _load_voice(self, voice_page_id: str) -> Optional[str]:
        """
        Load voice ID from Notion Voice Database by page ID.
        
        Uses NotionClient.query_database_filtered() to find the voice page
        and extract the "Voice ID" property.
        
        Args:
            voice_page_id: Notion page ID in Voice Database
        
        Returns:
            Voice ID string if found, None otherwise
        """
        try:
            # Query Voice Database for the specific page
            # Note: We need to get the page directly, not query
            # Using Notion REST API to get page by ID
            import requests
            
            url = f"{self.notion_client.NOTION_API_BASE}/pages/{voice_page_id}"
            response = requests.get(url, headers=self.notion_client.headers)
            response.raise_for_status()
            page = response.json()
            
            # Extract "Voice ID" property (text field)
            properties = page.get("properties", {})
            voice_id_prop = properties.get("Voice ID", {})
            
            if voice_id_prop.get("type") == "rich_text" and voice_id_prop.get("rich_text"):
                voice_id = "".join([
                    t.get("plain_text", "") 
                    for t in voice_id_prop["rich_text"]
                ])
                
                if voice_id:
                    logger.debug(f"Loaded voice ID: {voice_id} from page {voice_page_id}")
                    return voice_id
            
            logger.warning(f"Voice ID property not found in page {voice_page_id}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to load voice from page {voice_page_id}: {str(e)}")
            return None
    
    def resolve_voice(self, voice_relation_id: Optional[str]) -> str:
        """
        Resolve voice ID from Notion Voice Database relation.
        
        Workflow:
        1. Check cache for existing lookup
        2. Query Voice Database using relation ID
        3. Extract "Voice ID" property
        4. Cache result for future lookups
        5. Fall back to default voice if any step fails
        
        Args:
            voice_relation_id: Notion relation ID pointing to Voice Database page
                              (None or empty string triggers default)
        
        Returns:
            ElevenLabs voice ID (or default if resolution fails)
        """
        # Handle empty/None relation
        if not voice_relation_id:
            logger.info(f"No voice relation specified, using default: {self.default_voice_id}")
            return self._get_default_voice()
        
        # Check cache
        if voice_relation_id in self._cache:
            voice_id = self._cache[voice_relation_id]
            logger.debug(f"Cache hit for voice relation {voice_relation_id} -> {voice_id}")
            return voice_id
        
        # Load voice from database
        logger.debug(f"Loading voice for relation: {voice_relation_id}")
        voice_id = self._load_voice(voice_relation_id)
        
        if voice_id:
            # Cache successful lookup
            self._cache[voice_relation_id] = voice_id
            logger.info(
                f"Resolved voice: {voice_id} "
                f"(relation: {voice_relation_id})"
            )
            return voice_id
        
        # Fallback to default
        logger.warning(
            f"Voice resolution failed for relation {voice_relation_id}, "
            f"using default: {self.default_voice_id}"
        )
        
        # Cache the fallback to avoid repeated failed lookups
        self._cache[voice_relation_id] = self.default_voice_id
        
        return self._get_default_voice()
    
    def clear_cache(self):
        """
        Clear the voice cache.
        
        Useful for testing or when Voice Database is updated during runtime.
        """
        self._cache.clear()
        logger.debug("Voice cache cleared")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache size and hit count
        """
        return {
            "cache_size": len(self._cache),
            "cached_voices": list(self._cache.keys())
        }
