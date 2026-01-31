"""
Notion Mapping Manager for tracking content ↔ Notion page relationships.

This module manages the notion_mapping.json file which tracks the relationship
between local content IDs and Notion page IDs, along with sync status tracking.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.models.notion_mapping import NotionMapping

logger = logging.getLogger(__name__)


class NotionMappingManager:
    """Manager for Notion mapping persistence and lookups."""
    
    def __init__(self, mapping_file: str = "notion_mapping.json"):
        """
        Initialize mapping manager.
        
        Args:
            mapping_file: Path to mapping JSON file
        """
        self.mapping_file = Path(mapping_file)
        self._mappings: Dict[str, NotionMapping] = {}
        self._load_mapping()
        
    def _load_mapping(self) -> None:
        """Load mappings from file."""
        if not self.mapping_file.exists():
            logger.info(f"Mapping file not found: {self.mapping_file}. Starting with empty mappings.")
            return
            
        try:
            with open(self.mapping_file, "r") as f:
                data = json.load(f)
                
            # Convert to NotionMapping objects
            for entry in data:
                mapping = NotionMapping(**entry)
                self._mappings[mapping.content_id] = mapping
                
            logger.info(f"Loaded {len(self._mappings)} mappings from {self.mapping_file}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse mapping file: {e}")
            self._mappings = {}
        except Exception as e:
            logger.error(f"Failed to load mapping file: {e}")
            self._mappings = {}
            
    def save_mapping(self) -> None:
        """Save mappings to file."""
        try:
            # Convert to list of dicts
            data = [
                mapping.model_dump(mode="json")
                for mapping in self._mappings.values()
            ]
            
            # Write to file with pretty formatting
            with open(self.mapping_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
                
            logger.info(f"Saved {len(self._mappings)} mappings to {self.mapping_file}")
            
        except Exception as e:
            logger.error(f"Failed to save mapping file: {e}")
            raise
            
    def add_mapping(
        self,
        content_id: str,
        notion_page_id: str,
        language: str,
        level: str,
        content_type: str,
        title: str,
        status_in_notion: str = "Not started",
        status_in_local: str = "generated"
    ) -> NotionMapping:
        """
        Add new content ↔ Notion page mapping.
        
        Args:
            content_id: Local content UUID
            notion_page_id: Notion page ID
            language: Language code (e.g., "zh", "ja", "fr")
            level: Level code (e.g., "HSK3", "N5", "A2")
            content_type: "conversation" or "story"
            title: Content title
            status_in_notion: Current Notion status
            status_in_local: Current local JSON status
            
        Returns:
            Created NotionMapping object
        """
        now = datetime.now()
        
        mapping = NotionMapping(
            content_id=content_id,
            notion_page_id=notion_page_id,
            language=language,
            level=level,
            type=content_type,
            title=title,
            last_pushed_at=now,
            last_synced_at=now,
            status_in_notion=status_in_notion,
            status_in_local=status_in_local
        )
        
        self._mappings[content_id] = mapping
        self.save_mapping()
        
        logger.info(f"Added mapping: {content_id} → {notion_page_id}")
        return mapping
        
    def get_notion_page_id(self, content_id: str) -> Optional[str]:
        """
        Get Notion page ID for a content ID.
        
        Args:
            content_id: Local content UUID
            
        Returns:
            Notion page ID or None if not found
        """
        mapping = self._mappings.get(content_id)
        return mapping.notion_page_id if mapping else None
        
    def get_content_id(self, notion_page_id: str) -> Optional[str]:
        """
        Get content ID for a Notion page ID (reverse lookup).
        
        Args:
            notion_page_id: Notion page ID
            
        Returns:
            Content ID or None if not found
        """
        for content_id, mapping in self._mappings.items():
            if mapping.notion_page_id == notion_page_id:
                return content_id
        return None
        
    def get_mapping(self, content_id: str) -> Optional[NotionMapping]:
        """
        Get full mapping object for a content ID.
        
        Args:
            content_id: Local content UUID
            
        Returns:
            NotionMapping object or None if not found
        """
        return self._mappings.get(content_id)
        
    def update_sync_status(
        self,
        content_id: str,
        status_in_notion: Optional[str] = None,
        status_in_local: Optional[str] = None
    ) -> None:
        """
        Update sync status fields for a mapping.
        
        Args:
            content_id: Local content UUID
            status_in_notion: New Notion status (if provided)
            status_in_local: New local status (if provided)
        """
        mapping = self._mappings.get(content_id)
        if not mapping:
            logger.warning(f"Mapping not found for content_id: {content_id}")
            return
            
        # Update fields
        if status_in_notion is not None:
            mapping.status_in_notion = status_in_notion
        if status_in_local is not None:
            mapping.status_in_local = status_in_local
            
        mapping.last_synced_at = datetime.now()
        
        self.save_mapping()
        logger.info(f"Updated sync status for {content_id}")
        
    def find_by_title(
        self,
        title: str,
        language: Optional[str] = None,
        level: Optional[str] = None
    ) -> List[NotionMapping]:
        """
        Find mappings by title (case-insensitive search).
        
        Args:
            title: Content title to search for
            language: Optional language filter
            level: Optional level filter
            
        Returns:
            List of matching NotionMapping objects
        """
        title_lower = title.lower()
        results = []
        
        for mapping in self._mappings.values():
            # Check title match
            if title_lower not in mapping.title.lower():
                continue
                
            # Apply optional filters
            if language and mapping.language != language:
                continue
            if level and mapping.level != level:
                continue
                
            results.append(mapping)
            
        return results
        
    def get_all_mappings(self) -> List[NotionMapping]:
        """
        Get all mappings.
        
        Returns:
            List of all NotionMapping objects
        """
        return list(self._mappings.values())
        
    def delete_mapping(self, content_id: str) -> bool:
        """
        Delete a mapping.
        
        Args:
            content_id: Local content UUID
            
        Returns:
            True if deleted, False if not found
        """
        if content_id in self._mappings:
            del self._mappings[content_id]
            self.save_mapping()
            logger.info(f"Deleted mapping for {content_id}")
            return True
        return False
        
    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about mappings.
        
        Returns:
            Dict with counts by status
        """
        stats = {
            "total": len(self._mappings),
            "by_notion_status": {},
            "by_local_status": {},
            "by_language": {},
            "by_type": {}
        }
        
        for mapping in self._mappings.values():
            # Count by Notion status
            notion_status = mapping.status_in_notion or "unknown"
            stats["by_notion_status"][notion_status] = \
                stats["by_notion_status"].get(notion_status, 0) + 1
                
            # Count by local status
            local_status = mapping.status_in_local or "unknown"
            stats["by_local_status"][local_status] = \
                stats["by_local_status"].get(local_status, 0) + 1
                
            # Count by language
            stats["by_language"][mapping.language] = \
                stats["by_language"].get(mapping.language, 0) + 1
                
            # Count by type
            stats["by_type"][mapping.type] = \
                stats["by_type"].get(mapping.type, 0) + 1
                
        return stats
