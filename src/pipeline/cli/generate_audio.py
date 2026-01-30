"""CLI for generating audio files using ElevenLabs TTS."""

import argparse
from dotenv import load_dotenv
import logging
import sys
from pathlib import Path
from typing import Literal


from src.pipeline.generators.audio_generator import AudioGenerator
from src.pipeline.utils.audio_progress_manager import AudioProgressManager
from src.pipeline.utils.elevenlabs_client import ElevenLabsClient
from src.pipeline.utils.language_utils import get_language_code, get_language_name
from src.pipeline.validators.voice_validator import VoiceConfigValidator

logger = logging.getLogger(__name__)

load_dotenv()


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate audio files for learning items or content units"
    )
    
    # Required arguments
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
        help="Type of items to generate audio for"
    )
    
    # Optional filters
    parser.add_argument(
        "--category",
        help="Category filter for learning items (vocab, grammar, idiom, etc.)"
    )
    parser.add_argument(
        "--content-type",
        choices=["conversation", "story"],
        help="Content type filter for content units"
    )
    
    # Audio configuration
    parser.add_argument(
        "--voice-id",
        help="Provider/Voice ID for learning items (e.g., 'elevenlabs/abc123')"
    )
    parser.add_argument(
        "--versions",
        type=int,
        default=1,
        choices=[1, 2, 3],
        help="Number of versions to generate per item (1-3, default: 1)"
    )
    parser.add_argument(
        "--format",
        default="opus",
        choices=["opus", "mp3"],
        help="Audio format (default: opus)"
    )
    
    # Batch control
    parser.add_argument(
        "--batch-size",
        type=int,
        help="Number of items to process (default: all)"
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=10,
        help="Save checkpoint every N items (default: 10)"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint if available"
    )
    
    # Paths
    parser.add_argument(
        "--knowledge-path",
        help="Path to havachat-knowledge repository (default: from env HAVACHAT_KNOWLEDGE_PATH)"
    )
    parser.add_argument(
        "--config-dir",
        help="Directory containing voice_config_{lang}.json files (default: repo root)"
    )
    
    return parser.parse_args()


def main():
    """Main entry point for audio generation CLI."""
    args = parse_args()
    
    # Convert language to code
    try:
        lang_code = get_language_code(args.language)
        lang_name = get_language_name(lang_code)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    
    logger.info("=" * 80)
    logger.info("Audio Generation CLI")
    logger.info("=" * 80)
    logger.info(f"Language: {lang_name} ({lang_code})")
    logger.info(f"Level: {args.level}")
    logger.info(f"Item Type: {args.item_type}")
    logger.info(f"Format: {args.format}")
    logger.info(f"Versions: {args.versions}")
    
    # Determine knowledge path
    import os
    knowledge_path = Path(args.knowledge_path or os.getenv("HAVACHAT_KNOWLEDGE_PATH", "../havachat-knowledge/generated content"))
    
    if not knowledge_path.exists():
        logger.error(f"Knowledge path not found: {knowledge_path}")
        sys.exit(1)
    
    # Determine config directory
    config_dir = Path(args.config_dir) if args.config_dir else Path.cwd()
    
    # Initialize components
    try:
        elevenlabs_client = ElevenLabsClient()
        voice_validator = VoiceConfigValidator(lang_code, config_dir)
        
        audio_generator = AudioGenerator(
            elevenlabs_client=elevenlabs_client,
            voice_validator=voice_validator,
            output_base_path=knowledge_path,
            knowledge_base_path=knowledge_path
        )
        
        # Setup progress tracking
        progress_file = (
            knowledge_path / lang_name / args.level / "02_Generated" / 
            "audio" / "audio_generation_progress.json"
        )
        progress_manager = AudioProgressManager(progress_file)
        
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        sys.exit(1)
    
    # Load or create progress
    if args.resume:
        progress = progress_manager.load_from_checkpoint()
        if progress:
            logger.info("Resuming from checkpoint...")
            pending_items = progress_manager.get_pending_items()
            logger.info(f"Found {len(pending_items)} pending items")
        else:
            logger.info("No checkpoint found, starting fresh")
            progress = None
    else:
        progress = None
    
    # Load items if starting fresh
    if not progress:
        logger.info(f"Loading {args.item_type}s...")
        
        if args.item_type == "learning_item":
            items = audio_generator.load_learning_items(
                lang_name,
                args.level,
                args.category
            )
            item_ids = [item.id for item in items]
        else:
            content_units = audio_generator.load_content_units(
                lang_name,
                args.level,
                args.content_type
            )
            item_ids = [unit.id for unit in content_units]
            items = content_units
        
        if not items:
            logger.error("No items found to process")
            sys.exit(1)
        
        # Apply batch size limit
        if args.batch_size:
            items = items[:args.batch_size]
            item_ids = item_ids[:args.batch_size]
            logger.info(f"Limited to {args.batch_size} items")
        
        # Create new progress tracking
        progress = progress_manager.create_new_batch(
            language=lang_name,
            level=args.level,
            item_ids=item_ids,
            item_type=args.item_type,
            category=args.category,
            versions_per_item=args.versions,
            audio_format=args.format
        )
    else:
        # Reload items for resume
        if args.item_type == "learning_item":
            items = audio_generator.load_learning_items(
                lang_name,
                args.level,
                args.category
            )
        else:
            items = audio_generator.load_content_units(
                lang_name,
                args.level,
                args.content_type
            )
    
    # Determine voice configuration
    if args.item_type == "learning_item":
        # Single voice for learning items
        if args.voice_id:
            voice_id = args.voice_id
        else:
            # Get default voice for language
            default_voice = voice_validator.get_single_voice_for_language()
            if not default_voice:
                logger.error("No voice ID specified and no default voice found")
                sys.exit(1)
            voice_id = default_voice.voice_id
            logger.info(f"Using default voice: {default_voice.name} ({voice_id})")
    else:
        # Get speaker genders from first content unit
        first_unit = items[0]
        speaker_genders = [speaker.gender for speaker in first_unit.speakers]
        
        # Validate conversation voices exist for these genders
        is_valid, error = voice_validator.validate_conversation_config(speaker_genders)
        if not is_valid:
            logger.error(f"Conversation validation failed: {error}")
            sys.exit(1)
        
        logger.info(f"Conversation setup: {len(speaker_genders)} speakers ({', '.join(speaker_genders)})")
    
    # Process items
    audio_metadata_list = []
    checkpoint_counter = 0
    
    # Create item lookup dict
    item_dict = {item.id: item for item in items}
    
    for progress_item in progress_manager.get_pending_items():
        item = item_dict.get(progress_item.item_id)
        if not item:
            logger.warning(f"Item not found: {progress_item.item_id}")
            progress_manager.update_item_status(
                progress_item.item_id,
                "failed",
                error_message="Item not found in loaded data"
            )
            continue
        
        # Update status to processing
        progress_manager.update_item_status(progress_item.item_id, "processing")
        
        try:
            if args.item_type == "learning_item":
                # Generate audio for learning item
                audio_metadata = audio_generator.generate_audio_for_item(
                    item=item,
                    voice_id=voice_id,
                    language_full=lang_name,
                    level=args.level,
                    versions=args.versions,
                    audio_format=args.format
                )
            else:
                # Generate audio for content unit with speaker-to-voice mapping
                speaker_genders = [speaker.gender for speaker in item.speakers]
                voice_mapping = voice_validator.get_conversation_voices_for_speakers(speaker_genders)
                
                # Use Text-to-Dialogue API for more natural conversations
                audio_metadata = audio_generator.generate_audio_for_content_dialogue(
                    content_unit=item,
                    voice_mapping=voice_mapping,
                    language_full=lang_name,
                    level=args.level,
                    versions=args.versions,
                    audio_format=args.format
                )
            
            if audio_metadata:
                audio_metadata_list.append(audio_metadata)
                progress_manager.update_item_status(
                    progress_item.item_id,
                    "completed",
                    versions_generated=args.versions
                )
                logger.info(f"✓ Completed: {progress_item.item_id}")
            else:
                progress_manager.update_item_status(
                    progress_item.item_id,
                    "failed",
                    error_message="Audio generation returned None"
                )
                logger.error(f"✗ Failed: {progress_item.item_id}")
                
        except Exception as e:
            logger.error(f"Error processing {progress_item.item_id}: {e}")
            progress_manager.update_item_status(
                progress_item.item_id,
                "failed",
                error_message=str(e)
            )
        
        # Save checkpoint periodically
        checkpoint_counter += 1
        if checkpoint_counter >= args.checkpoint_interval:
            progress_manager.save_checkpoint()
            checkpoint_counter = 0
    
    # Final checkpoint save
    progress_manager.save_checkpoint()
    
    # Save audio metadata
    if audio_metadata_list:
        item_type_key = "learning_items" if args.item_type == "learning_item" else "content_units"
        audio_generator.save_metadata(
            audio_metadata_list,
            args.language,
            args.level,
            item_type_key
        )
    
    # Print summary
    summary = progress_manager.get_summary()
    logger.info("\n" + "=" * 80)
    logger.info("GENERATION SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total items: {summary['total_items']}")
    logger.info(f"Completed: {summary['completed']}")
    logger.info(f"Failed: {summary['failed']}")
    logger.info(f"Success rate: {summary['success_rate']:.1f}%")
    logger.info(f"Versions per item: {summary['versions_per_item']}")
    logger.info(f"Format: {summary['audio_format']}")
    
    # ElevenLabs cost tracking
    cost_info = elevenlabs_client.get_cost_estimate()
    logger.info("\n" + "-" * 80)
    logger.info("COST TRACKING")
    logger.info("-" * 80)
    logger.info(f"Total characters: {cost_info['character_count']:,}")
    logger.info(f"Estimated cost: ${cost_info['estimated_cost_usd']:.2f}")
    logger.info(f"ElevenLabs requests: {cost_info['total_requests']}")
    logger.info(f"Failed requests: {cost_info['failed_requests']}")
    logger.info("=" * 80)
    
    # Cleanup checkpoint if complete
    if progress_manager.is_complete():
        progress_manager.cleanup_checkpoint()
        logger.info("✓ All items processed successfully!")
        sys.exit(0)
    else:
        logger.warning("⚠ Some items failed. Run with --resume to retry failed items.")
        sys.exit(1)


if __name__ == "__main__":
    main()
