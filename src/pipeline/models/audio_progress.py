"""Audio generation progress tracking model."""

from datetime import UTC, datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class AudioProgressItem(BaseModel):
    """Progress tracking for a single item."""
    
    item_id: str = Field(..., description="Learning item or content unit ID")
    item_type: str = Field(..., description="learning_item or content_unit")
    category: Optional[str] = Field(None, description="Category for learning items")
    status: str = Field(
        ...,
        description="pending, processing, completed, failed"
    )
    versions_generated: int = Field(default=0, description="Number of versions generated")
    attempts: int = Field(default=0, description="Number of generation attempts")
    error_message: Optional[str] = Field(None, description="Last error message if failed")
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AudioGenerationProgress(BaseModel):
    """Progress tracking for audio generation batch."""
    
    batch_id: str = Field(..., description="Unique batch identifier")
    language: str = Field(..., description="ISO 639-1 language code")
    level: str = Field(..., description="Proficiency level")
    category: Optional[str] = Field(None, description="Category filter if specified")
    item_type: str = Field(..., description="learning_item or content_unit")
    
    # Progress tracking
    total_items: int = Field(..., description="Total items to process")
    items: List[AudioProgressItem] = Field(
        default_factory=list,
        description="Progress for each item"
    )
    
    # Statistics
    completed_count: int = Field(default=0)
    failed_count: int = Field(default=0)
    pending_count: int = Field(default=0)
    
    # Metadata
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_checkpoint: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: Optional[datetime] = Field(None)
    
    # Configuration
    versions_per_item: int = Field(default=1, description="Number of versions to generate")
    audio_format: str = Field(default="opus", description="Audio format: opus or mp3")
    
    def update_statistics(self):
        """Recalculate statistics from items."""
        self.completed_count = sum(1 for item in self.items if item.status == "completed")
        self.failed_count = sum(1 for item in self.items if item.status == "failed")
        self.pending_count = sum(1 for item in self.items if item.status in ["pending", "processing"])
        self.last_checkpoint = datetime.now(UTC)
        
        if self.completed_count + self.failed_count >= self.total_items:
            self.completed_at = datetime.now(UTC)
    
    def get_item_progress(self, item_id: str) -> AudioProgressItem | None:
        """Get progress for a specific item."""
        for item in self.items:
            if item.item_id == item_id:
                return item
        return None
    
    def is_complete(self) -> bool:
        """Check if all items are processed (completed or failed)."""
        return self.completed_count + self.failed_count >= self.total_items
    
    def get_success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.total_items == 0:
            return 0.0
        return (self.completed_count / self.total_items) * 100
