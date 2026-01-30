"""Progress manager for audio generation with checkpoint support."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import List
from uuid import uuid4

from src.pipeline.models.audio_progress import (
    AudioGenerationProgress,
    AudioProgressItem,
)

logger = logging.getLogger(__name__)


class AudioProgressManager:
    """Manager for tracking audio generation progress with checkpoints."""
    
    def __init__(self, progress_file_path: str | Path):
        """Initialize progress manager.
        
        Args:
            progress_file_path: Path to progress JSON file
        """
        self.progress_file_path = Path(progress_file_path)
        self.progress: AudioGenerationProgress | None = None
    
    def create_new_batch(
        self,
        language: str,
        level: str,
        item_ids: List[str],
        item_type: str,
        category: str | None = None,
        versions_per_item: int = 1,
        audio_format: str = "opus"
    ) -> AudioGenerationProgress:
        """Create a new audio generation batch.
        
        Args:
            language: Language code
            level: Proficiency level
            item_ids: List of item IDs to process
            item_type: "learning_item" or "content_unit"
            category: Optional category filter
            versions_per_item: Number of versions to generate
            audio_format: Audio format
            
        Returns:
            New AudioGenerationProgress object
        """
        batch_id = str(uuid4())
        
        # Create progress items
        items = [
            AudioProgressItem(
                item_id=item_id,
                item_type=item_type,
                category=category,
                status="pending"
            )
            for item_id in item_ids
        ]
        
        self.progress = AudioGenerationProgress(
            batch_id=batch_id,
            language=language,
            level=level,
            category=category,
            item_type=item_type,
            total_items=len(item_ids),
            items=items,
            versions_per_item=versions_per_item,
            audio_format=audio_format
        )
        
        self.save_checkpoint()
        logger.info(f"Created new batch {batch_id} with {len(item_ids)} items")
        
        return self.progress
    
    def load_from_checkpoint(self) -> AudioGenerationProgress | None:
        """Load progress from checkpoint file.
        
        Returns:
            AudioGenerationProgress object or None if file doesn't exist
        """
        if not self.progress_file_path.exists():
            logger.info("No checkpoint file found")
            return None
        
        try:
            with open(self.progress_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.progress = AudioGenerationProgress(**data)
            logger.info(
                f"Loaded checkpoint: {self.progress.completed_count}/"
                f"{self.progress.total_items} completed, "
                f"{self.progress.failed_count} failed, "
                f"{self.progress.pending_count} pending"
            )
            
            return self.progress
            
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None
    
    def save_checkpoint(self):
        """Save current progress to checkpoint file."""
        if not self.progress:
            logger.warning("No progress to save")
            return
        
        # Update statistics before saving
        self.progress.update_statistics()
        
        # Create directory if needed
        self.progress_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save to file
        with open(self.progress_file_path, 'w', encoding='utf-8') as f:
            json.dump(
                self.progress.model_dump(mode='json'),
                f,
                indent=2,
                ensure_ascii=False
            )
        
        logger.debug(
            f"Checkpoint saved: {self.progress.completed_count}/"
            f"{self.progress.total_items} completed"
        )
    
    def update_item_status(
        self,
        item_id: str,
        status: str,
        versions_generated: int = 0,
        error_message: str | None = None
    ):
        """Update status for a specific item.
        
        Args:
            item_id: Item ID
            status: New status (pending, processing, completed, failed)
            versions_generated: Number of versions generated
            error_message: Error message if failed
        """
        if not self.progress:
            logger.warning("No progress loaded")
            return
        
        item_progress = self.progress.get_item_progress(item_id)
        if not item_progress:
            logger.warning(f"Item not found in progress: {item_id}")
            return
        
        item_progress.status = status
        item_progress.versions_generated = versions_generated
        item_progress.attempts += 1
        item_progress.error_message = error_message
        item_progress.last_updated = datetime.now(UTC)
        
        # Update overall statistics
        self.progress.update_statistics()
    
    def get_pending_items(self) -> List[AudioProgressItem]:
        """Get list of items that haven't been processed yet.
        
        Returns:
            List of pending AudioProgressItem objects
        """
        if not self.progress:
            return []
        
        return [
            item for item in self.progress.items 
            if item.status in ["pending", "failed"]
        ]
    
    def is_complete(self) -> bool:
        """Check if all items have been processed.
        
        Returns:
            True if all items are completed or failed
        """
        if not self.progress:
            return False
        
        return self.progress.is_complete()
    
    def get_summary(self) -> dict:
        """Get summary of current progress.
        
        Returns:
            Dict with summary statistics
        """
        if not self.progress:
            return {}
        
        return {
            "batch_id": self.progress.batch_id,
            "language": self.progress.language,
            "level": self.progress.level,
            "category": self.progress.category,
            "item_type": self.progress.item_type,
            "total_items": self.progress.total_items,
            "completed": self.progress.completed_count,
            "failed": self.progress.failed_count,
            "pending": self.progress.pending_count,
            "success_rate": self.progress.get_success_rate(),
            "versions_per_item": self.progress.versions_per_item,
            "audio_format": self.progress.audio_format,
            "started_at": self.progress.started_at.isoformat(),
            "last_checkpoint": self.progress.last_checkpoint.isoformat(),
            "completed_at": (
                self.progress.completed_at.isoformat()
                if self.progress.completed_at else None
            ),
            "is_complete": self.progress.is_complete()
        }
    
    def cleanup_checkpoint(self):
        """Remove checkpoint file after successful completion."""
        if self.progress_file_path.exists():
            self.progress_file_path.unlink()
            logger.info(f"Removed checkpoint file: {self.progress_file_path}")
