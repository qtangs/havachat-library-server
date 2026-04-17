"""
CLI Script for Notion Audio Content Processor

Command-line interface for batch processing audio content from Notion database.

Usage:
    # Process all records marked "Ready for Audio"
    uv run python -m src.havachat.integrations.notion_audio.cli
    
    # Dry run (validate config without processing)
    uv run python -m src.havachat.integrations.notion_audio.cli --dry-run
    
    # Process with limit
    uv run python -m src.havachat.integrations.notion_audio.cli --limit 10
    
    # Process specific record
    uv run python -m src.havachat.integrations.notion_audio.cli --record-id "abc123"
    
    # Verbose output
    uv run python -m src.havachat.integrations.notion_audio.cli --verbose
"""

import sys
import json
from typing import Optional
import argparse
from pathlib import Path

from loguru import logger
from pydantic import ValidationError
from dotenv import load_dotenv

from src.havachat.utils.notion_client import NotionClient
from src.havachat.integrations.notion_audio.config import load_config_from_env
from src.havachat.integrations.notion_audio.processor import AudioProcessor
from src.havachat.integrations.notion_audio.voice_resolver import VoiceResolver


def setup_logging(verbose: bool = False, quiet: bool = False):
    """Configure logging with JSON format."""
    logger.remove()  # Remove default handler
    
    if quiet:
        # Only errors
        logger.add(
            sys.stderr,
            format="<red>{level}</red>: {message}",
            level="ERROR",
            colorize=True
        )
    elif verbose:
        # Detailed logging
        logger.add(
            sys.stderr,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
            level="DEBUG",
            colorize=True
        )
    else:
        # Normal logging
        logger.add(
            sys.stderr,
            format="<level>{level: <8}</level> | {message}",
            level="INFO",
            colorize=True
        )


def validate_environment() -> tuple[bool, list[str]]:
    """
    Validate required environment variables.
    
    Returns:
        Tuple of (is_valid, list of missing variables)
    """
    required_vars = [
        "NOTION_API_KEY",
        "NOTION_VOICE_DATABASE_ID",
        "HAVACHAT_KNOWLEDGE_PATH",
        "ELEVENLABS_API_KEY",
        "DEFAULT_VOICE_ID"
    ]
    
    # At least one LLM key required (for US2 metadata)
    llm_keys = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
    
    import os
    missing = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    # Check LLM keys
    if not any(os.getenv(key) for key in llm_keys):
        missing.append("OPENAI_API_KEY or ANTHROPIC_API_KEY")
    
    return len(missing) == 0, missing


def format_output(summary: any, format_type: str = "text") -> str:
    """
    Format batch processing summary for output.
    
    Args:
        summary: BatchProcessingSummary object
        format_type: "text" or "json"
    
    Returns:
        Formatted string
    """
    if format_type == "json":
        return json.dumps({
            "total_records": summary.total_records,
            "successful": summary.successful,
            "failed": summary.failed,
            "skipped": summary.skipped,
            "success_rate": summary.success_rate,
            "total_time": summary.total_time,
            "results": [
                {
                    "record_id": r.record_id,
                    "record_name": r.record_name,
                    "success": r.success,
                    "error": r.error,
                    "skipped": r.skipped,
                    "processing_time": r.processing_time
                }
                for r in summary.results
            ]
        }, indent=2)
    
    # Text format
    lines = [
        "",
        "=" * 60,
        "BATCH PROCESSING SUMMARY",
        "=" * 60,
        f"Total Records: {summary.total_records}",
        f"Successful: {summary.successful}",
        f"Failed: {summary.failed}",
        f"Skipped: {summary.skipped}",
        f"Success Rate: {summary.success_rate:.1f}%",
        f"Total Time: {summary.total_time:.1f}s",
        "",
        "RESULTS:",
        "-" * 60
    ]
    
    for result in summary.results:
        lines.append(str(result))
    
    lines.extend([
        "-" * 60,
        ""
    ])
    
    return "\n".join(lines)


def main():
    """Main CLI entry point."""
    # Load environment variables from .env
    load_dotenv()
    
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Process Notion Audio Content Database records",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Process all ready records
  %(prog)s --dry-run                     # Validate config only
  %(prog)s --limit 5                     # Process max 5 records
  %(prog)s --record-id abc123            # Process specific record
  %(prog)s --verbose                     # Detailed logging
  %(prog)s --quiet                       # Errors only
        """
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without processing"
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="Maximum number of records to process"
    )
    
    parser.add_argument(
        "--record-id",
        type=str,
        metavar="ID",
        help="Process specific record by ID"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress all output except errors"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(verbose=args.verbose, quiet=args.quiet)
    
    logger.info("Notion Audio Content Processor")
    logger.info("-" * 40)
    
    # Validate environment
    is_valid, missing = validate_environment()
    if not is_valid:
        logger.error("Missing required environment variables:")
        for var in missing:
            logger.error(f"  - {var}")
        logger.error("\nPlease set these variables in your .env file")
        logger.error("See .env.example for reference")
        sys.exit(1)
    
    logger.success("Environment variables validated")
    
    # Load configuration
    try:
        config = load_config_from_env()
        logger.success(f"Configuration loaded")
        logger.info(f"Storage path: {config.storage_path}")
        logger.info(f"Audio format: {config.audio_format}")
        logger.info(f"TTS model: {config.tts_model}")
    except ValidationError as e:
        logger.error("Configuration validation failed:")
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to load configuration: {str(e)}")
        sys.exit(1)
    
    # Dry run - exit after validation
    if args.dry_run:
        logger.success("Dry run complete - configuration is valid")
        logger.info(f"Would process records from database: {config.notion_audio_db_id}")
        if args.limit:
            logger.info(f"Would limit to {args.limit} records")
        if args.record_id:
            logger.info(f"Would process record: {args.record_id}")
        sys.exit(0)
    
    # Initialize Notion client
    # Initialize Notion client
    try:
        notion_client = NotionClient(
            api_token=config.notion_api_key,
            database_id=config.notion_audio_db_id
        )
        logger.success("Notion client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Notion client: {str(e)}")
        sys.exit(2)
    
    # Initialize VoiceResolver (US3 - Voice Selection)
    try:
        voice_resolver = VoiceResolver(
            notion_client=notion_client,
            voice_db_id=config.notion_voice_db_id,
            default_voice_id=config.default_voice_id
        )
        logger.success("VoiceResolver initialized")
    except Exception as e:
        logger.error(f"Failed to initialize VoiceResolver: {str(e)}")
        sys.exit(2)
    
    # Initialize AudioProcessor with US1 (audio) + US3 (voice selection)
    try:
        processor = AudioProcessor(
            notion_client=notion_client,
            config=config,
            voice_resolver=voice_resolver,  # US3 - Voice Selection ✅
            metadata_generator=None  # US2 - not implemented yet
        )
        logger.success("AudioProcessor initialized")
    except Exception as e:
        logger.error(f"Failed to initialize AudioProcessor: {str(e)}")
        sys.exit(2)
    
    # Process batch
    try:
        logger.info("Starting batch processing...")
        logger.info("")
        
        summary = processor.process_batch(
            limit=args.limit,
            record_id=args.record_id
        )
        
        # Output results
        output = format_output(summary, format_type="json" if args.json else "text")
        print(output)
        
        # Determine exit code based on success criteria
        if summary.total_records == 0:
            logger.warning("No records found to process")
            sys.exit(0)
        
        if not summary.meets_success_criteria():
            logger.error(
                f"Success rate {summary.success_rate:.1f}% is below 95% threshold"
            )
            sys.exit(4)
        
        logger.success("Batch processing completed successfully")
        sys.exit(0)
        
    except KeyboardInterrupt:
        logger.warning("Processing interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error during processing: {str(e)}")
        logger.exception(e)
        sys.exit(3)


if __name__ == "__main__":
    main()
