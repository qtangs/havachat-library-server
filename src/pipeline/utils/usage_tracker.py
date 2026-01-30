"""Usage tracker for learning item appearances.

This module tracks how many times each learning item appears in generated content.
Maintains usage_stats.json files per language/level with appearance counts.

Usage statistics help identify:
- Underutilized learning items (need more content)
- Overused learning items (need variation)
- Content coverage gaps
"""

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from pipeline.validators.schema import LearningItem

logger = logging.getLogger(__name__)


class UsageStats(BaseModel):
    """Usage statistics for a learning item."""
    
    item_id: str
    target_item: str
    category: str
    appearances_count: int = 0
    content_unit_ids: List[str] = Field(default_factory=list)
    
    
class UsageTracker:
    """Track learning item usage across generated content.

    Maintains a JSON file with appearance counts for each learning item.
    Updates are incremental - load existing stats, modify, and save.
    """

    def __init__(self, stats_file: Path):
        """Initialize usage tracker.

        Args:
            stats_file: Path to usage_stats.json file
        """
        self.stats_file = stats_file
        self.stats: Dict[str, Dict] = {}
        
        # Load existing stats if file exists
        if stats_file.exists():
            self.load_stats()
        
        logger.info(f"UsageTracker initialized: {stats_file}")

    def load_stats(self) -> None:
        """Load existing usage statistics from file."""
        try:
            with open(self.stats_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.stats = data
            logger.info(f"Loaded stats for {len(self.stats)} items from {self.stats_file}")
        except Exception as e:
            logger.warning(f"Failed to load stats from {self.stats_file}: {e}")
            self.stats = {}

    def save_stats(self) -> None:
        """Save usage statistics to file."""
        self.stats_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(self.stats_file, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved stats for {len(self.stats)} items to {self.stats_file}")
        except Exception as e:
            logger.error(f"Failed to save stats to {self.stats_file}: {e}")
            raise

    def increment_appearances(
        self,
        learning_item_id: str,
        content_unit_id: str,
        learning_item: Optional[LearningItem] = None,
    ) -> None:
        """Increment appearance count for a learning item.

        Args:
            learning_item_id: UUID of the learning item
            content_unit_id: UUID of the content unit
            learning_item: Optional full LearningItem for metadata
        """
        if learning_item_id not in self.stats:
            # Initialize new entry
            self.stats[learning_item_id] = {
                "item_id": learning_item_id,
                "target_item": learning_item.target_item if learning_item else "Unknown",
                "category": learning_item.category.value if learning_item else "unknown",
                "appearances_count": 0,
                "content_unit_ids": [],
            }
        
        # Update counts
        self.stats[learning_item_id]["appearances_count"] += 1
        
        # Track content unit IDs (avoid duplicates)
        if content_unit_id not in self.stats[learning_item_id]["content_unit_ids"]:
            self.stats[learning_item_id]["content_unit_ids"].append(content_unit_id)
        
        logger.debug(
            f"Updated usage: {learning_item_id} -> "
            f"{self.stats[learning_item_id]['appearances_count']} appearances"
        )

    def update_batch(
        self,
        content_unit_id: str,
        learning_item_ids: List[str],
        learning_items: Optional[Dict[str, LearningItem]] = None,
    ) -> None:
        """Update usage statistics for a batch of learning items.

        Args:
            content_unit_id: UUID of the content unit
            learning_item_ids: List of learning item UUIDs used in content
            learning_items: Optional dict mapping IDs to full LearningItem objects
        """
        for item_id in learning_item_ids:
            learning_item = learning_items.get(item_id) if learning_items else None
            self.increment_appearances(item_id, content_unit_id, learning_item)
        
        logger.info(f"Updated usage for {len(learning_item_ids)} items in content {content_unit_id}")

    def get_usage_report(self) -> Dict:
        """Generate usage statistics report.

        Returns:
            Dictionary with summary statistics and detailed breakdown
        """
        if not self.stats:
            return {
                "total_items": 0,
                "total_appearances": 0,
                "avg_appearances_per_item": 0.0,
                "unused_items": 0,
                "underutilized_items": 0,
                "well_utilized_items": 0,
                "overused_items": 0,
                "by_category": {},
            }

        total_items = len(self.stats)
        total_appearances = sum(item["appearances_count"] for item in self.stats.values())
        avg_appearances = total_appearances / total_items if total_items > 0 else 0

        # Categorize by utilization
        unused = sum(1 for item in self.stats.values() if item["appearances_count"] == 0)
        underutilized = sum(1 for item in self.stats.values() if 0 < item["appearances_count"] < 3)
        well_utilized = sum(1 for item in self.stats.values() if 3 <= item["appearances_count"] <= 10)
        overused = sum(1 for item in self.stats.values() if item["appearances_count"] > 10)

        # Breakdown by category
        by_category = defaultdict(lambda: {"count": 0, "total_appearances": 0})
        for item in self.stats.values():
            category = item["category"]
            by_category[category]["count"] += 1
            by_category[category]["total_appearances"] += item["appearances_count"]

        # Calculate averages per category
        for category in by_category:
            count = by_category[category]["count"]
            total = by_category[category]["total_appearances"]
            by_category[category]["avg_appearances"] = total / count if count > 0 else 0

        report = {
            "total_items": total_items,
            "total_appearances": total_appearances,
            "avg_appearances_per_item": round(avg_appearances, 2),
            "unused_items": unused,
            "underutilized_items": underutilized,
            "well_utilized_items": well_utilized,
            "overused_items": overused,
            "by_category": dict(by_category),
        }

        return report

    def get_underutilized_items(self, threshold: int = 3) -> List[Dict]:
        """Get list of underutilized learning items.

        Args:
            threshold: Maximum appearance count to be considered underutilized

        Returns:
            List of item statistics with appearances < threshold
        """
        underutilized = [
            item for item in self.stats.values()
            if item["appearances_count"] < threshold
        ]
        
        # Sort by appearance count (ascending)
        underutilized.sort(key=lambda x: x["appearances_count"])
        
        return underutilized

    def get_overused_items(self, threshold: int = 10) -> List[Dict]:
        """Get list of overused learning items.

        Args:
            threshold: Minimum appearance count to be considered overused

        Returns:
            List of item statistics with appearances > threshold
        """
        overused = [
            item for item in self.stats.values()
            if item["appearances_count"] > threshold
        ]
        
        # Sort by appearance count (descending)
        overused.sort(key=lambda x: x["appearances_count"], reverse=True)
        
        return overused

    def print_report(self) -> None:
        """Print formatted usage report to console."""
        report = self.get_usage_report()
        
        print("\n" + "=" * 80)
        print("USAGE STATISTICS REPORT")
        print("=" * 80)
        print(f"Total learning items: {report['total_items']}")
        print(f"Total appearances: {report['total_appearances']}")
        print(f"Average appearances per item: {report['avg_appearances_per_item']:.2f}")
        print()
        print("Utilization Breakdown:")
        print(f"  Unused (0 appearances): {report['unused_items']}")
        print(f"  Underutilized (1-2): {report['underutilized_items']}")
        print(f"  Well-utilized (3-10): {report['well_utilized_items']}")
        print(f"  Overused (>10): {report['overused_items']}")
        print()
        print("By Category:")
        for category, stats in report["by_category"].items():
            print(
                f"  {category}: {stats['count']} items, "
                f"{stats['total_appearances']} appearances, "
                f"avg {stats['avg_appearances']:.2f}"
            )
        print("=" * 80 + "\n")
