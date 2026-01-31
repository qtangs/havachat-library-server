"""
Notion Sync CLI - Synchronize content status between Notion and local files.

This CLI handles:
- Fetching status changes from Notion database
- Generating audio for content marked "Ready for Audio"
- Updating local status for rejected content
- Audio regeneration by title
- Retrying failed Notion pushes
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from havachat.utils.llm_client import LLMClient
from src.pipeline.utils.notion_client import NotionClient, NotionSchemaError
from src.pipeline.utils.notion_mapping_manager import NotionMappingManager
from src.models.notion_mapping import NotionMapping

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NotionSyncCLI:
    """CLI for synchronizing Notion database with local content."""
    
    def __init__(
        self,
        notion_token: str,
        database_id: str,
        data_root: str = "data"
    ):
        """
        Initialize Notion sync CLI.
        
        Args:
            notion_token: Notion API token
            database_id: Notion database ID
            data_root: Root directory for language data
        """
        self.notion_client = NotionClient(
            api_token=notion_token,
            database_id=database_id
        )
        self.mapping_manager = NotionMappingManager()
        self.data_root = Path(data_root)
        
        # Validate Notion schema on initialization
        try:
            self.notion_client.validate_database_schema()
            logger.info("Notion database schema validated successfully")
        except NotionSchemaError as e:
            logger.error(f"Notion schema validation failed: {e}")
            raise
            
    def check_notion(self, since: Optional[datetime] = None) -> None:
        """
        Check Notion for status changes and process them.
        
        Args:
            since: Only process changes after this timestamp
        """
        logger.info("Fetching status changes from Notion...")
        
        try:
            pages = self.notion_client.fetch_status_changes(since=since)
            logger.info(f"Found {len(pages)} pages in Notion")
            
            # Group by status
            ready_for_audio = []
            rejected = []
            
            for page in pages:
                status = page.get("status")
                if status == "Ready for Audio":
                    ready_for_audio.append(page)
                elif status == "Rejected":
                    rejected.append(page)
                    
            logger.info(f"Ready for Audio: {len(ready_for_audio)}, Rejected: {len(rejected)}")
            
            # Process each group
            if ready_for_audio:
                logger.info("Processing 'Ready for Audio' items...")
                for page in ready_for_audio:
                    self._process_ready_for_audio(page)
                    
            if rejected:
                logger.info("Processing 'Rejected' items...")
                for page in rejected:
                    self._process_rejected(page)
                    
            logger.info("Notion sync completed")
            
        except Exception as e:
            logger.error(f"Failed to check Notion: {e}")
            raise
            
    def _process_ready_for_audio(self, page: Dict) -> None:
        """
        Process page marked "Ready for Audio".
        
        Args:
            page: Page data from Notion
        """
        notion_page_id = page["notion_page_id"]
        title = page["title"]
        
        logger.info(f"Processing Ready for Audio: {title}")
        
        # Get content ID from mapping
        content_id = self.mapping_manager.get_content_id(notion_page_id)
        if not content_id:
            logger.warning(f"No mapping found for Notion page: {notion_page_id}")
            return
            
        # Get full mapping to find file location
        mapping = self.mapping_manager.get_mapping(content_id)
        if not mapping:
            logger.warning(f"No mapping found for content: {content_id}")
            return
            
        # Load content unit from local file
        content_unit = self._load_content_unit(
            language=mapping.language,
            level=mapping.level,
            content_type=mapping.type,
            content_id=content_id
        )
        
        if not content_unit:
            logger.error(f"Content unit not found: {content_id}")
            return
            
        # Generate audio
        logger.info(f"Generating audio for: {title}")
        audio_url = self._generate_audio(
            content_unit=content_unit,
            language=mapping.language,
            level=mapping.level
        )
        
        if audio_url:
            # Update Notion with audio URL
            self.notion_client.update_audio_field(notion_page_id, audio_url)
            
            # Update status to "OK"
            self.notion_client.update_status(notion_page_id, "OK")
            
            # Update mapping
            self.mapping_manager.update_sync_status(
                content_id=content_id,
                status_in_notion="OK",
                status_in_local="published"
            )
            
            logger.info(f"Audio generated and Notion updated: {title}")
        else:
            logger.error(f"Failed to generate audio for: {title}")
            
    def _process_rejected(self, page: Dict) -> None:
        """
        Process page marked "Rejected".
        
        Args:
            page: Page data from Notion
        """
        notion_page_id = page["notion_page_id"]
        title = page["title"]
        
        logger.info(f"Processing Rejected: {title}")
        
        # Get content ID from mapping
        content_id = self.mapping_manager.get_content_id(notion_page_id)
        if not content_id:
            logger.warning(f"No mapping found for Notion page: {notion_page_id}")
            return
            
        # Get full mapping
        mapping = self.mapping_manager.get_mapping(content_id)
        if not mapping:
            logger.warning(f"No mapping found for content: {content_id}")
            return
            
        # Update local content status
        self._update_local_status(
            language=mapping.language,
            level=mapping.level,
            content_type=mapping.type,
            content_id=content_id,
            new_status="rejected"
        )
        
        # Decrement usage stats for learning items
        self._decrement_usage_stats(
            language=mapping.language,
            level=mapping.level,
            content_id=content_id
        )
        
        # Update mapping
        self.mapping_manager.update_sync_status(
            content_id=content_id,
            status_in_notion="Rejected",
            status_in_local="rejected"
        )
        
        logger.info(f"Local status updated for rejected content: {title}")
        
    def _load_content_unit(
        self,
        language: str,
        level: str,
        content_type: str,
        content_id: str
    ) -> Optional[Dict]:
        """
        Load content unit from local JSON file.
        
        Args:
            language: Language code
            level: Level code
            content_type: "conversation" or "story"
            content_id: Content UUID
            
        Returns:
            Content unit dict or None if not found
        """
        # Construct file path
        filename = f"{content_type}s.json"  # conversations.json or stories.json
        file_path = self.data_root / language / level / filename
        
        if not file_path.exists():
            logger.error(f"Content file not found: {file_path}")
            return None
            
        try:
            with open(file_path, "r") as f:
                content_units = json.load(f)
                
            # Find content unit by ID
            for unit in content_units:
                if unit.get("id") == content_id:
                    return unit
                    
            logger.error(f"Content unit {content_id} not found in {file_path}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to load content file {file_path}: {e}")
            return None
            
    def _update_local_status(
        self,
        language: str,
        level: str,
        content_type: str,
        content_id: str,
        new_status: str
    ) -> None:
        """
        Update status field in local JSON file.
        
        Args:
            language: Language code
            level: Level code
            content_type: "conversation" or "story"
            content_id: Content UUID
            new_status: New status value
        """
        filename = f"{content_type}s.json"
        file_path = self.data_root / language / level / filename
        
        if not file_path.exists():
            logger.error(f"Content file not found: {file_path}")
            return
            
        try:
            # Load current data
            with open(file_path, "r") as f:
                content_units = json.load(f)
                
            # Update status
            updated = False
            for unit in content_units:
                if unit.get("id") == content_id:
                    unit["status"] = new_status
                    unit["updated_at"] = datetime.now().isoformat()
                    updated = True
                    break
                    
            if updated:
                # Save back to file
                with open(file_path, "w") as f:
                    json.dump(content_units, f, indent=2, ensure_ascii=False)
                logger.info(f"Updated local status to '{new_status}' for {content_id}")
            else:
                logger.warning(f"Content unit not found: {content_id}")
                
        except Exception as e:
            logger.error(f"Failed to update local status: {e}")
            
    def _decrement_usage_stats(
        self,
        language: str,
        level: str,
        content_id: str
    ) -> None:
        """
        Decrement usage stats for learning items in rejected content.
        
        Args:
            language: Language code
            level: Level code
            content_id: Content UUID
        """
        # Load content to get learning item IDs
        content_units_file = self.data_root / language / level / "conversations.json"
        stories_file = self.data_root / language / level / "stories.json"
        
        learning_item_ids = []
        
        # Try conversations first
        if content_units_file.exists():
            try:
                with open(content_units_file, "r") as f:
                    content_units = json.load(f)
                for unit in content_units:
                    if unit.get("id") == content_id:
                        learning_item_ids = unit.get("learning_item_ids", [])
                        break
            except Exception as e:
                logger.error(f"Failed to load conversations: {e}")
                
        # Try stories if not found
        if not learning_item_ids and stories_file.exists():
            try:
                with open(stories_file, "r") as f:
                    stories = json.load(f)
                for story in stories:
                    if story.get("id") == content_id:
                        learning_item_ids = story.get("learning_item_ids", [])
                        break
            except Exception as e:
                logger.error(f"Failed to load stories: {e}")
                
        if not learning_item_ids:
            logger.warning(f"No learning items found for content: {content_id}")
            return
            
        # Load and update usage stats
        usage_stats_file = self.data_root / language / level / "usage_stats.json"
        
        if not usage_stats_file.exists():
            logger.warning(f"Usage stats file not found: {usage_stats_file}")
            return
            
        try:
            with open(usage_stats_file, "r") as f:
                usage_stats = json.load(f)
                
            # Decrement counts
            updated_count = 0
            for stat in usage_stats:
                if stat.get("learning_item_id") in learning_item_ids:
                    current_count = stat.get("appearances_count", 0)
                    stat["appearances_count"] = max(0, current_count - 1)
                    updated_count += 1
                    
            # Save back
            if updated_count > 0:
                with open(usage_stats_file, "w") as f:
                    json.dump(usage_stats, f, indent=2, ensure_ascii=False)
                logger.info(f"Decremented usage stats for {updated_count} learning items")
                
        except Exception as e:
            logger.error(f"Failed to update usage stats: {e}")
            
    def _generate_audio(
        self,
        content_unit: Dict,
        language: str,
        level: str
    ) -> Optional[str]:
        """
        Generate audio for content unit and upload to R2.
        
        Args:
            content_unit: Content unit dict
            language: Language code
            level: Level code
            
        Returns:
            R2 URL of generated audio or None if failed
        """
        # TODO: Import and use actual audio generation logic
        # For now, return a placeholder
        logger.info(f"Audio generation not yet implemented for content: {content_unit.get('id')}")
        return None
        
    def regenerate_audio(
        self,
        title: str,
        language: Optional[str] = None,
        level: Optional[str] = None
    ) -> None:
        """
        Regenerate audio for content by title.
        
        Args:
            title: Content title to search for
            language: Optional language filter
            level: Optional level filter
        """
        logger.info(f"Searching for content with title: {title}")
        
        # Search in mapping manager
        mappings = self.mapping_manager.find_by_title(
            title=title,
            language=language,
            level=level
        )
        
        if not mappings:
            logger.warning(f"No content found with title: {title}")
            return
            
        if len(mappings) > 1:
            logger.warning(f"Found {len(mappings)} content items with title '{title}':")
            for i, mapping in enumerate(mappings, 1):
                logger.info(
                    f"  {i}. {mapping.language}/{mapping.level} - {mapping.type} "
                    f"(ID: {mapping.content_id})"
                )
            logger.info("Please specify language and/or level to disambiguate")
            return
            
        # Single match found
        mapping = mappings[0]
        logger.info(
            f"Found content: {mapping.language}/{mapping.level} - {mapping.type} "
            f"(ID: {mapping.content_id})"
        )
        
        # Load content unit
        content_unit = self._load_content_unit(
            language=mapping.language,
            level=mapping.level,
            content_type=mapping.type,
            content_id=mapping.content_id
        )
        
        if not content_unit:
            logger.error(f"Failed to load content unit: {mapping.content_id}")
            return
            
        # Generate audio
        audio_url = self._generate_audio(
            content_unit=content_unit,
            language=mapping.language,
            level=mapping.level
        )
        
        if audio_url:
            # Update Notion with new audio URL
            self.notion_client.update_audio_field(
                notion_page_id=mapping.notion_page_id,
                audio_url=audio_url
            )
            logger.info(f"Audio regenerated and Notion updated: {title}")
        else:
            logger.error(f"Failed to regenerate audio for: {title}")
            
    def push_failed_queue(self) -> None:
        """
        Retry pushing items from the failed queue.
        """
        queue_file = Path(self.notion_client.queue_file)
        
        if not queue_file.exists():
            logger.info("No failed push queue found")
            return
            
        logger.info("Processing failed push queue...")
        
        # Read queue entries
        failed_entries = []
        try:
            with open(queue_file, "r") as f:
                for line in f:
                    if line.strip():
                        failed_entries.append(json.loads(line))
        except Exception as e:
            logger.error(f"Failed to read queue file: {e}")
            return
            
        logger.info(f"Found {len(failed_entries)} failed entries")
        
        # Try to push each entry
        successful = []
        still_failed = []
        
        for entry in failed_entries:
            content_id = entry["content_id"]
            payload = entry["payload"]
            
            try:
                response = self.notion_client.client.pages.create(
                    parent={"database_id": self.notion_client.database_id},
                    properties=payload
                )
                notion_page_id = response["id"]
                
                # Update mapping
                self.mapping_manager.add_mapping(
                    content_id=content_id,
                    notion_page_id=notion_page_id,
                    language=entry["language"],
                    level=entry["level"],
                    content_type=entry["type"],
                    title=entry["title"]
                )
                
                successful.append(content_id)
                logger.info(f"Successfully pushed: {entry['title']}")
                
            except Exception as e:
                logger.warning(f"Still failing: {entry['title']} - {str(e)}")
                still_failed.append(entry)
                
        # Rewrite queue with still-failed entries
        if still_failed:
            with open(queue_file, "w") as f:
                for entry in still_failed:
                    f.write(json.dumps(entry) + "\n")
            logger.info(f"Queue updated: {len(successful)} succeeded, {len(still_failed)} still failing")
        else:
            # All succeeded, delete queue file
            queue_file.unlink()
            logger.info(f"All {len(successful)} entries successfully pushed. Queue cleared.")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Notion Sync CLI - Synchronize content with Notion database"
    )
    
    parser.add_argument(
        "--check-notion",
        action="store_true",
        help="Check Notion for status changes and process them"
    )
    
    parser.add_argument(
        "--since",
        type=str,
        help="Only process changes after this timestamp (ISO format)"
    )
    
    parser.add_argument(
        "--regenerate-audio",
        type=str,
        metavar="TITLE",
        help="Regenerate audio for content by title"
    )
    
    parser.add_argument(
        "--language",
        type=str,
        help="Filter by language (use with --regenerate-audio)"
    )
    
    parser.add_argument(
        "--level",
        type=str,
        help="Filter by level (use with --regenerate-audio)"
    )
    
    parser.add_argument(
        "--push-failed",
        action="store_true",
        help="Retry pushing items from the failed queue"
    )
    
    parser.add_argument(
        "--data-root",
        type=str,
        default="data",
        help="Root directory for language data (default: data)"
    )
    
    args = parser.parse_args()
    
    # Get Notion credentials from environment
    notion_token = os.getenv("NOTION_API_TOKEN")
    database_id = os.getenv("NOTION_DATABASE_ID")
    
    if not notion_token or not database_id:
        logger.error(
            "Missing Notion credentials. Set NOTION_API_TOKEN and NOTION_DATABASE_ID "
            "environment variables."
        )
        sys.exit(1)
        
    # Initialize CLI
    try:
        cli = NotionSyncCLI(
            notion_token=notion_token,
            database_id=database_id,
            data_root=args.data_root
        )
    except NotionSchemaError as e:
        logger.error(f"Notion schema validation failed: {e}")
        sys.exit(1)
        
    # Execute command
    try:
        if args.check_notion:
            since = None
            if args.since:
                since = datetime.fromisoformat(args.since)
            cli.check_notion(since=since)
            
        elif args.regenerate_audio:
            cli.regenerate_audio(
                title=args.regenerate_audio,
                language=args.language,
                level=args.level
            )
            
        elif args.push_failed:
            cli.push_failed_queue()
            
        else:
            parser.print_help()
            
    except Exception as e:
        logger.error(f"Command failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
