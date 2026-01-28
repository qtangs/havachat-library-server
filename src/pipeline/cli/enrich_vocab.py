"""CLI for vocabulary enrichment.

Usage:
    python -m pipeline.cli.enrich_vocab \
        --language zh \
        --level HSK1 \
        --input data/mandarin_hsk1.tsv \
        --enricher mandarin \
        --output output/mandarin/hsk1/vocab.json \
        --max-items 10 \
        --dry-run

Supports:
- Mandarin Chinese (--enricher mandarin, TSV input)
- Japanese (--enricher japanese, JSON input)
- French (--enricher french, TSV input)

Features:
- Parallel processing with ThreadPoolExecutor
- Checkpoint/resume capability
- Token usage tracking and reporting
- Progress bar with tqdm
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

from tqdm import tqdm

from pipeline.enrichers.base import BaseEnricher
from pipeline.enrichers.vocab import (
    FrenchVocabEnricher,
    JapaneseVocabEnricher,
    MandarinVocabEnricher,
)
from pipeline.utils.file_io import write_json
from pipeline.utils.llm_client import LLMClient
from pipeline.utils.logging_config import configure_logging
from pipeline.validators.schema import LevelSystem

logger = logging.getLogger(__name__)

load_dotenv()

# Enricher-language validation mapping
ENRICHER_LANGUAGE_MAP = {
    "mandarin": "zh",
    "japanese": "ja",
    "french": "fr",
}


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Enrich vocabulary items with LLM-generated content",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Enrich Mandarin HSK1 vocabulary
  python -m pipeline.cli.enrich_vocab \\
      --language zh --level HSK1 \\
      --input data/hsk1_vocab.tsv \\
      --enricher mandarin \\
      --output output/zh/hsk1/vocab.json

  # Enrich Japanese N5 vocabulary (dry run, 5 items)
  python -m pipeline.cli.enrich_vocab \\
      --language ja --level N5 \\
      --input data/jlpt_n5.json \\
      --enricher japanese \\
      --output output/ja/n5/vocab.json \\
      --dry-run --max-items 5

  # Enrich French A1 vocabulary with parallel processing
  python -m pipeline.cli.enrich_vocab \\
      --language fr --level A1 \\
      --input data/french_a1.tsv \\
      --enricher french \\
      --output output/fr/a1/vocab.json \\
      --parallel 5

  # Resume from checkpoint
  python -m pipeline.cli.enrich_vocab \\
      --language zh --level HSK1 \\
      --input data/hsk1_vocab.tsv \\
      --enricher mandarin \\
      --output output/zh/hsk1/vocab.json \\
      --resume
        """,
    )

    parser.add_argument(
        "--language",
        required=True,
        choices=["zh", "ja", "fr", "en", "es"],
        help="Target language ISO code",
    )

    parser.add_argument(
        "--level",
        required=True,
        help="Proficiency level (HSK1-HSK6, N5-N1, A1-C1)",
    )

    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Input file path (TSV for Mandarin/French, JSON for Japanese)",
    )

    parser.add_argument(
        "--enricher",
        required=True,
        choices=["mandarin", "japanese", "french"],
        help="Enricher to use (must match language)",
    )

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output JSON file path",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse input and show preview without calling LLM",
    )

    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="Maximum number of items to process (for testing)",
    )

    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Number of parallel workers for enrichment (default: 1)",
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint file (skip already processed items)",
    )

    parser.add_argument(
        "--manual-review-dir",
        type=Path,
        default=None,
        help="Directory for manual review queue (default: output_dir/manual_review)",
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )

    return parser.parse_args()


def get_enricher_class(enricher_name: str) -> BaseEnricher:
    """Get enricher class by name."""
    enrichers = {
        "mandarin": MandarinVocabEnricher,
        "japanese": JapaneseVocabEnricher,
        "french": FrenchVocabEnricher,
    }

    return enrichers.get(enricher_name)


def determine_level_system(language: str) -> LevelSystem:
    """Determine level system based on language.

    Args:
        language: ISO language code (zh, ja, fr, en, es)

    Returns:
        LevelSystem enum value
    """
    level_system_map = {
        "zh": LevelSystem.HSK,
        "ja": LevelSystem.JLPT,
        "fr": LevelSystem.CEFR,
        "en": LevelSystem.CEFR,
        "es": LevelSystem.CEFR,
    }

    return level_system_map.get(language, LevelSystem.CEFR)


def load_checkpoint(checkpoint_file: Path) -> set:
    """Load processed item IDs from checkpoint file.

    Args:
        checkpoint_file: Path to checkpoint JSON file

    Returns:
        Set of processed item IDs
    """
    if not checkpoint_file.exists():
        return set()

    try:
        with open(checkpoint_file, "r") as f:
            data = json.load(f)
            return set(data.get("processed_ids", []))
    except Exception as e:
        logger.warning(f"Failed to load checkpoint: {e}")
        return set()


def save_checkpoint(checkpoint_file: Path, processed_ids: set) -> None:
    """Save processed item IDs to checkpoint file.

    Args:
        checkpoint_file: Path to checkpoint JSON file
        processed_ids: Set of processed item IDs
    """
    try:
        checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        with open(checkpoint_file, "w") as f:
            json.dump({"processed_ids": list(processed_ids)}, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save checkpoint: {e}")


def enrich_single_item(
    item: dict,
    enricher: BaseEnricher,
    item_index: int,
    total_items: int,
) -> Optional[dict]:
    """Enrich a single vocabulary item.

    Args:
        item: Item dictionary
        enricher: Enricher instance
        item_index: Index of current item (for logging)
        total_items: Total number of items (for logging)

    Returns:
        Enriched item dict or None if failed
    """
    try:
        # Enrich item (enricher uses its own system_prompt property)
        result = enricher.enrich_item(
            item=item,
        )

        if result:
            return result.model_dump(mode="json")
        else:
            return None

    except Exception as e:
        logger.error(
            f"Unexpected error enriching item {item_index}/{total_items}: {e}",
            exc_info=True,
        )
        return None


def main() -> int:
    """Main CLI entry point."""
    args = parse_args()

    # Setup logging
    configure_logging(
        level=getattr(logging, args.log_level),
        json_format=False,  # Use simple format for CLI
        console_output=True,
    )

    logger.info("=" * 80)
    logger.info("Vocabulary Enrichment Pipeline")
    logger.info("=" * 80)
    logger.info(f"Language: {args.language}")
    logger.info(f"Level: {args.level}")
    logger.info(f"Enricher: {args.enricher}")
    logger.info(f"Input: {args.input}")
    logger.info(f"Output: {args.output}")
    logger.info(f"Dry Run: {args.dry_run}")
    if args.max_items:
        logger.info(f"Max Items: {args.max_items}")
    if args.parallel > 1:
        logger.info(f"Parallel Workers: {args.parallel}")
    if args.resume:
        logger.info("Resume Mode: Enabled")
    logger.info("=" * 80)

    # Validate enricher-language match
    expected_language = ENRICHER_LANGUAGE_MAP.get(args.enricher)
    if expected_language != args.language:
        logger.error(
            f"Enricher '{args.enricher}' requires language '{expected_language}', "
            f"but got '{args.language}'"
        )
        return 1

    # Validate input file exists
    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        return 1

    # Validate output is writable
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Cannot create output directory: {e}")
        return 1

    # Get enricher class and response model
    enricher_class = get_enricher_class(args.enricher)
    if not enricher_class:
        logger.error(f"Unknown enricher: {args.enricher}")
        return 1

    # Determine level system
    level_system = determine_level_system(args.language)

    # Setup manual review directory
    manual_review_dir = args.manual_review_dir or (args.output.parent / "manual_review")

    # Initialize enricher
    if args.dry_run:
        logger.info("DRY RUN MODE: No LLM calls will be made")
        enricher: BaseEnricher = enricher_class(
            llm_client=None,
            manual_review_dir=manual_review_dir,
        )
        llm_client = None
    else:
        llm_client = LLMClient()
        enricher: BaseEnricher = enricher_class(
            llm_client=llm_client,
            max_retries=3,
            manual_review_dir=manual_review_dir,
        )

    # Parse source file
    logger.info(f"Parsing source file: {args.input}")
    start_time = time.time()

    try:
        items = enricher.parse_source(args.input)
    except Exception as e:
        logger.error(f"Failed to parse source file: {e}", exc_info=True)
        return 1

    parse_time = time.time() - start_time
    logger.info(f"Parsed {len(items)} items in {parse_time:.2f}s")

    # Load checkpoint if resuming
    checkpoint_file = args.output.with_suffix(".checkpoint.json")
    processed_ids = set()
    if args.resume:
        processed_ids = load_checkpoint(checkpoint_file)
        logger.info(f"Loaded checkpoint: {len(processed_ids)} items already processed")

    # Filter out already-processed items
    if processed_ids:
        original_count = len(items)
        items = [
            item
            for i, item in enumerate(items)
            if str(i) not in processed_ids
        ]
        skipped = original_count - len(items)
        if skipped > 0:
            logger.info(f"Skipped {skipped} already-processed items")

    # Limit items if max_items specified
    if args.max_items:
        items = items[: args.max_items]
        logger.info(f"Limited to {len(items)} items for processing")

    # Dry run: show preview and exit
    if args.dry_run:
        logger.info("\n" + "=" * 80)
        logger.info("DRY RUN PREVIEW (first 3 items):")
        logger.info("=" * 80)

        for i, item in enumerate(items[:3], 1):
            logger.info(f"\nItem {i}:")
            logger.info(f"  Target: {item.get('target_item')}")
            logger.info(f"  Missing fields: {enricher.detect_missing_fields(item)}")

        logger.info("\n" + "=" * 80)
        logger.info(f"Total items to process: {len(items)}")
        logger.info("DRY RUN COMPLETE")
        logger.info("=" * 80)
        return 0

    # Enrich items
    logger.info(f"\nStarting enrichment of {len(items)} items...")
    enrichment_start = time.time()

    enriched_items = []
    failed_count = 0

    # Set language and level metadata
    for item in items:
        item["language"] = args.language
        item["level_system"] = level_system.value
        if "level_min" not in item:
            item["level_min"] = args.level
        if "level_max" not in item:
            item["level_max"] = args.level

    if args.parallel == 1:
        # Sequential processing with progress bar
        for i, item in enumerate(tqdm(items, desc="Enriching", unit="item"), 1):
            result = enrich_single_item(item, enricher, i, len(items))

            if result:
                enriched_items.append(result)
                processed_ids.add(str(i - 1))
            else:
                failed_count += 1

            # Save checkpoint every 10 items
            if i % 10 == 0:
                save_checkpoint(checkpoint_file, processed_ids)

    else:
        # Parallel processing with ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=args.parallel) as executor:
            # Submit all tasks
            future_to_item = {
                executor.submit(
                    enrich_single_item, item, enricher, i, len(items)
                ): (i, item)
                for i, item in enumerate(items, 1)
            }

            # Process completed tasks with progress bar
            with tqdm(total=len(items), desc="Enriching", unit="item") as pbar:
                for future in as_completed(future_to_item):
                    i, item = future_to_item[future]
                    try:
                        result = future.result()
                        if result:
                            enriched_items.append(result)
                            processed_ids.add(str(i - 1))
                        else:
                            failed_count += 1
                    except Exception as e:
                        logger.error(f"Task failed for item {i}: {e}")
                        failed_count += 1

                    pbar.update(1)

                    # Save checkpoint every 10 items
                    if len(enriched_items) % 10 == 0:
                        save_checkpoint(checkpoint_file, processed_ids)

    enrichment_time = time.time() - enrichment_start

    # Write output
    logger.info(f"\nWriting {len(enriched_items)} enriched items to: {args.output}")
    write_json(enriched_items, args.output)

    # Clean up checkpoint if all items processed
    if failed_count == 0 and checkpoint_file.exists():
        checkpoint_file.unlink()
        logger.info("Removed checkpoint file (all items processed)")

    # Get token usage summary
    logger.info("\n" + "=" * 80)
    logger.info("ENRICHMENT SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total items processed: {len(items)}")
    logger.info(f"Successfully enriched: {len(enriched_items)}")
    logger.info(f"Failed: {failed_count}")
    logger.info(f"Success rate: {len(enriched_items) / len(items) * 100:.1f}%")
    logger.info(f"Enrichment time: {enrichment_time:.2f}s")
    logger.info(
        f"Average time per item: {enrichment_time / len(items):.2f}s"
    )

    # Token usage and cost estimation
    if llm_client:
        usage = llm_client.get_usage_summary()
        logger.info("\n" + "-" * 80)
        logger.info("TOKEN USAGE & COST")
        logger.info("-" * 80)
        logger.info(f"Model: {usage['model']}")
        logger.info(f"Prompt tokens: {usage['prompt_tokens']:,}")
        logger.info(f"Completion tokens: {usage['completion_tokens']:,}")
        logger.info(f"Total tokens: {usage['total_tokens']:,}")
        logger.info(f"Cached tokens: {usage['cached_tokens']:,}")
        logger.info(f"Cache hit rate: {usage['cache_hit_rate']}")
        logger.info(f"Estimated cost: ${usage['estimated_cost_usd']:.4f}")
        logger.info(f"  - Input cost: ${usage['input_cost_usd']:.4f}")
        logger.info(f"  - Output cost: ${usage['output_cost_usd']:.4f}")

    logger.info("\n" + "-" * 80)
    logger.info(f"Output file: {args.output}")
    if failed_count > 0:
        logger.info(f"Manual review queue: {manual_review_dir}")
    logger.info("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
