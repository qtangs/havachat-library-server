"""CLI tool for selecting audio versions from generated alternatives."""

import argparse
import json
import logging
import sys
from pathlib import Path

from src.libs.logging_helper import setup_logging
from src.pipeline.models.audio_metadata import ContentUnitAudio, LearningItemAudio
from src.pipeline.utils.language_utils import get_language_code, get_language_name

logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Select preferred audio version for learning items or content units"
    )
    
    parser.add_argument(
        "--language",
        required=True,
        help="Language name or ISO 639-1 code (e.g., 'Mandarin' or 'zh', 'French' or 'fr')"
    )
    parser.add_argument(
        "--level",
        required=True,
        help="Proficiency level (e.g., HSK1, A1, N5)"
    )
    parser.add_argument(
        "--item-type",
        required=True,
        choices=["learning_item", "content_unit"],
        help="Type of item"
    )
    parser.add_argument(
        "--item-id",
        required=True,
        help="UUID of the item"
    )
    parser.add_argument(
        "--version",
        type=int,
        required=True,
        choices=[1, 2, 3],
        help="Version number to select (1-3)"
    )
    parser.add_argument(
        "--segment-index",
        type=int,
        help="Segment index for content units (required for content_unit type)"
    )
    parser.add_argument(
        "--knowledge-path",
        help="Path to havachat-knowledge repository"
    )
    
    return parser.parse_args()


def main():
    """Main entry point for audio selection CLI."""
    args = parse_args()
    
    setup_logging(log_level=logging.INFO)
    
    # Convert language to code
    try:
        lang_code = get_language_code(args.language)
        lang_name = get_language_name(lang_code)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    
    logger.info("=" * 80)
    logger.info("Audio Version Selection CLI")
    logger.info("=" * 80)
    logger.info(f"Language: {lang_name} ({lang_code})")
    
    # Validate segment-index requirement
    if args.item_type == "content_unit" and args.segment_index is None:
        logger.error("--segment-index required for content_unit type")
        sys.exit(1)
    
    # Determine knowledge path
    import os
    knowledge_path = Path(
        args.knowledge_path or 
        os.getenv("HAVACHAT_KNOWLEDGE_PATH", "../havachat-knowledge/generated content")
    )
    
    # Build metadata file path
    item_type_key = "learning_items" if args.item_type == "learning_item" else "content_units"
    metadata_file = (
        knowledge_path / lang_name / args.level / "02_Generated" / 
        "audio" / f"{item_type_key}_media.json"
    )
    
    if not metadata_file.exists():
        logger.error(f"Metadata file not found: {metadata_file}")
        sys.exit(1)
    
    # Load metadata
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if args.item_type == "learning_item":
            metadata_list = [LearningItemAudio(**item) for item in data]
        else:
            metadata_list = [ContentUnitAudio(**item) for item in data]
            
    except Exception as e:
        logger.error(f"Failed to load metadata: {e}")
        sys.exit(1)
    
    # Find the item
    target_metadata = None
    for metadata in metadata_list:
        item_id_field = (
            "learning_item_id" if args.item_type == "learning_item" 
            else "content_unit_id"
        )
        if getattr(metadata, item_id_field) == args.item_id:
            target_metadata = metadata
            break
    
    if not target_metadata:
        logger.error(f"Item not found: {args.item_id}")
        sys.exit(1)
    
    # Select version
    try:
        if args.item_type == "learning_item":
            success = target_metadata.select_version(args.version)
            if success:
                logger.info(
                    f"✓ Selected version {args.version} for item: "
                    f"{target_metadata.target_item}"
                )
            else:
                logger.error(f"Version {args.version} not found")
                sys.exit(1)
        else:
            segment_audio = target_metadata.get_segment_audio(args.segment_index)
            if not segment_audio:
                logger.error(f"Segment {args.segment_index} not found")
                sys.exit(1)
            
            success = segment_audio.select_version(args.version)
            if success:
                logger.info(
                    f"✓ Selected version {args.version} for segment {args.segment_index} "
                    f"of content unit: {target_metadata.title}"
                )
            else:
                logger.error(f"Version {args.version} not found for segment")
                sys.exit(1)
    
    except Exception as e:
        logger.error(f"Failed to select version: {e}")
        sys.exit(1)
    
    # Save updated metadata
    try:
        updated_data = [item.model_dump(mode='json') for item in metadata_list]
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(updated_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✓ Metadata updated: {metadata_file}")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Failed to save metadata: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
