"""CLI tool for syncing audio files to Cloudflare R2 storage."""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List

from src.libs.logging_helper import setup_logging
from havachat.models.audio_metadata import ContentUnitAudio, LearningItemAudio
from havachat.utils.language_utils import get_language_code, get_language_name
from havachat.utils.r2_client import R2Client

logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Sync audio files to Cloudflare R2 storage"
    )
    
    parser.add_argument(
        "--language",
        required=True,
        help="Language name or ISO 639-1 code (e.g., 'Chinese' or 'zh', 'French' or 'fr')"
    )
    parser.add_argument(
        "--level",
        required=True,
        help="Proficiency level (e.g., HSK1, A1, N5)"
    )
    parser.add_argument(
        "--item-type",
        required=True,
        choices=["learning_item", "content_unit", "all"],
        help="Type of items to sync (or 'all' for both)"
    )
    parser.add_argument(
        "--category",
        help="Category filter for learning items"
    )
    parser.add_argument(
        "--selected-only",
        action="store_true",
        help="Only sync selected versions (default: sync all versions)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be uploaded without actually uploading"
    )
    parser.add_argument(
        "--cleanup-local",
        action="store_true",
        help="Delete local files after successful upload (use with caution!)"
    )
    parser.add_argument(
        "--knowledge-path",
        help="Path to havachat-knowledge repository"
    )
    
    return parser.parse_args()


def get_r2_path(
    language: str,
    category: str,
    filename: str
) -> str:
    """Build R2 path for audio file.
    
    Args:
        language: ISO 639-1 language code (zh, fr, ja)
        category: Category (vocab, grammar, conversation, etc.)
        filename: Audio filename
        
    Returns:
        R2 path (e.g., "zh/vocab/uuid.opus")
    """
    return f"{language}/{category}/{filename}"


def get_public_url(account_id: str, r2_path: str) -> str:
    """Generate public URL for R2 file.
    
    Args:
        account_id: Cloudflare account ID
        r2_path: Path in R2 bucket
        
    Returns:
        Public URL
    """
    return f"https://pub-{account_id}.r2.dev/{r2_path}"


def main():
    """Main entry point for R2 sync CLI."""
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
    logger.info("Cloudflare R2 Audio Sync CLI")
    logger.info("=" * 80)
    logger.info(f"Language: {lang_name} ({lang_code})")
    
    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No files will be uploaded")
        logger.info("=" * 80)
    
    # Determine knowledge path
    import os
    knowledge_path = Path(
        args.knowledge_path or 
        os.getenv("HAVACHAT_KNOWLEDGE_PATH", "../havachat-knowledge/generated content")
    )
    
    audio_base_path = knowledge_path / lang_name / args.level / "02_Generated" / "audio"
    
    if not audio_base_path.exists():
        logger.error(f"Audio directory not found: {audio_base_path}")
        sys.exit(1)
    
    # Language code mapping
    language_codes = {
        "Chinese": "zh",
        "French": "fr",
        "Japanese": "ja"
    }
    lang_code = language_codes.get(args.language, "zh")
    
    # Initialize R2 client (only if not dry-run)
    r2_client = None
    if not args.dry_run:
        try:
            r2_client = R2Client()
            logger.info("✓ R2 client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize R2 client: {e}")
            sys.exit(1)
    
    # Determine which item types to sync
    item_types = []
    if args.item_type == "all":
        item_types = ["learning_items", "content_units"]
    elif args.item_type == "learning_item":
        item_types = ["learning_items"]
    else:
        item_types = ["content_units"]
    
    total_files = 0
    total_uploaded = 0
    total_failed = 0
    total_bytes = 0
    
    # Process each item type
    for item_type_key in item_types:
        logger.info(f"\nProcessing {item_type_key}...")
        
        # Load metadata
        metadata_file = audio_base_path / f"{item_type_key}_media.json"
        
        if not metadata_file.exists():
            logger.warning(f"Metadata file not found: {metadata_file}")
            continue
        
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if item_type_key == "learning_items":
                metadata_list = [LearningItemAudio(**item) for item in data]
            else:
                metadata_list = [ContentUnitAudio(**item) for item in data]
                
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            continue
        
        # Collect files to upload
        files_to_upload: List[tuple[Path, str, str]] = []  # (local_path, r2_path, metadata_id)
        
        for metadata in metadata_list:
            # Apply category filter for learning items
            if item_type_key == "learning_items" and args.category:
                if metadata.category != args.category:
                    continue
            
            # Get versions to sync
            if item_type_key == "learning_items":
                versions = [metadata.get_selected_version()] if args.selected_only else metadata.versions
                
                for version in versions:
                    if version is None:
                        continue
                    
                    local_path = audio_base_path / version.audio_local_path
                    if not local_path.exists():
                        logger.warning(f"Local file not found: {local_path}")
                        continue
                    
                    # Build R2 path
                    r2_path = get_r2_path(
                        lang_code,
                        metadata.category,
                        local_path.name
                    )
                    
                    files_to_upload.append((local_path, r2_path, metadata.learning_item_id))
                    
            else:  # content_units
                for segment in metadata.segments:
                    versions = [segment.get_selected_version()] if args.selected_only else segment.versions
                    
                    for version in versions:
                        if version is None:
                            continue
                        
                        local_path = audio_base_path / version.audio_local_path
                        if not local_path.exists():
                            logger.warning(f"Local file not found: {local_path}")
                            continue
                        
                        # Build R2 path
                        r2_path = get_r2_path(
                            lang_code,
                            metadata.type,  # conversation or story
                            local_path.name
                        )
                        
                        files_to_upload.append((local_path, r2_path, metadata.content_unit_id))
        
        logger.info(f"Found {len(files_to_upload)} files to sync")
        total_files += len(files_to_upload)
        
        if args.dry_run:
            for local_path, r2_path, item_id in files_to_upload:
                file_size = local_path.stat().st_size
                logger.info(f"Would upload: {local_path.name} -> {r2_path} ({file_size} bytes)")
            continue
        
        # Upload files
        metadata_updates = {}  # Track which metadata needs URL updates
        
        for local_path, r2_path, item_id in files_to_upload:
            success, upload_metadata = r2_client.upload_file(local_path, r2_path)
            
            if success:
                total_uploaded += 1
                total_bytes += upload_metadata.get("file_size_bytes", 0)
                
                # Track URL for metadata update
                if item_id not in metadata_updates:
                    metadata_updates[item_id] = []
                metadata_updates[item_id].append({
                    "local_path": version.audio_local_path,
                    "url": upload_metadata["url"]
                })
                
                # Delete local file if requested
                if args.cleanup_local:
                    try:
                        local_path.unlink()
                        logger.info(f"🗑️  Deleted local file: {local_path.name}")
                    except Exception as e:
                        logger.warning(f"Failed to delete local file: {e}")
                        
            else:
                total_failed += 1
                logger.error(f"Failed to upload: {local_path.name}")
        
        # Update metadata with R2 URLs
        if metadata_updates:
            logger.info(f"Updating metadata with R2 URLs...")
            
            for metadata in metadata_list:
                item_id = (
                    metadata.learning_item_id if item_type_key == "learning_items" 
                    else metadata.content_unit_id
                )
                
                if item_id in metadata_updates:
                    url_mappings = {u["local_path"]: u["url"] for u in metadata_updates[item_id]}
                    
                    if item_type_key == "learning_items":
                        for version in metadata.versions:
                            if version.audio_local_path in url_mappings:
                                version.audio_url = url_mappings[version.audio_local_path]
                    else:
                        for segment in metadata.segments:
                            for version in segment.versions:
                                if version.audio_local_path in url_mappings:
                                    version.audio_url = url_mappings[version.audio_local_path]
            
            # Save updated metadata
            try:
                updated_data = [item.model_dump(mode='json') for item in metadata_list]
                
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(updated_data, f, indent=2, ensure_ascii=False)
                
                logger.info(f"✓ Updated metadata file: {metadata_file}")
                
            except Exception as e:
                logger.error(f"Failed to save metadata: {e}")
    
    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("SYNC SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total files: {total_files}")
    
    if not args.dry_run:
        logger.info(f"Uploaded: {total_uploaded}")
        logger.info(f"Failed: {total_failed}")
        logger.info(f"Total bytes: {total_bytes:,}")
        success_rate = (total_uploaded / total_files * 100) if total_files > 0 else 0
        logger.info(f"Success rate: {success_rate:.1f}%")
        
        if r2_client:
            stats = r2_client.get_statistics()
            logger.info(f"\nR2 client statistics:")
            logger.info(f"  Total uploads: {stats['total_uploads']}")
            logger.info(f"  Failed uploads: {stats['failed_uploads']}")
            logger.info(f"  Total bytes: {stats['total_bytes_uploaded']:,}")
    
    logger.info("=" * 80)
    
    if args.dry_run:
        logger.info("✓ Dry run complete - no files were uploaded")
        sys.exit(0)
    elif total_failed > 0:
        logger.warning("⚠ Some uploads failed")
        sys.exit(1)
    else:
        logger.info("✓ All files synced successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
