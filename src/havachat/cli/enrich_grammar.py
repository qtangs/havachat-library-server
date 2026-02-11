"""CLI for grammar enrichment.

Usage:
    python -m havachat.cli.enrich_grammar \
        --language zh \
        --level HSK1 \
        --input data/chinese_hsk1_grammar.csv \
        --enricher chinese \
        --output output/chinese/hsk1/grammar.json \
        --max-items 10 \
        --dry-run

    # Or use pre-generated LLM explanations:
    python -m havachat.cli.enrich_grammar \
        --language zh \
        --level HSK1 \
        --enricher chinese \
        --output output/chinese/hsk1/grammar.json \
        --llm-explained-file generated_content/Chinese/HSK1/Final/grammar_explained_by_llm.csv

Supports:
- Chinese (--enricher chinese, CSV input)

Features:
- Parallel processing with ThreadPoolExecutor
- Checkpoint/resume capability
- Token usage tracking and reporting
- Progress bar with tqdm
- Granularity warnings for potential mega-items
"""

import argparse
import csv
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from tqdm import tqdm

from havachat.enrichers.base import BaseEnricher
from havachat.enrichers.grammar import ChineseGrammarEnricher
from havachat.utils.file_io import write_json
from havachat.utils.llm_client import LLMClient
from havachat.utils.logging_config import configure_logging
from havachat.validators.schema import LevelSystem

logger = logging.getLogger(__name__)

load_dotenv()

# Enricher-language validation mapping
ENRICHER_LANGUAGE_MAP = {
    "chinese": "zh",
}


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Enrich grammar patterns with LLM-generated content",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Enrich Chinese HSK1 grammar
  python -m havachat.cli.enrich_grammar \\
      --language zh --level HSK1 \\
      --input data/hsk1_grammar.csv \\
      --enricher chinese \\
      --output output/zh/hsk1/grammar.json

  # Dry run with 5 items
  python -m havachat.cli.enrich_grammar \\
      --language zh --level HSK1 \\
      --input data/hsk1_grammar.csv \\
      --enricher chinese \\
      --output output/zh/hsk1/grammar.json \\
      --dry-run --max-items 5

  # Use pre-generated LLM explanations (skips LLM, ignores max-items)
  python -m havachat.cli.enrich_grammar \\
      --language zh --level HSK1 \\
      --enricher chinese \\
      --output output/zh/hsk1/grammar.json \\
      --llm-explained-file generated_content/Chinese/HSK1/Final/grammar_explained_by_llm.csv

  # Use pre-generated LLM explanations with translation skipped
  python -m havachat.cli.enrich_grammar \\
      --language zh --level HSK1 \\
      --enricher chinese \\
      --output output/zh/hsk1/grammar.json \\
      --llm-explained-file generated_content/Chinese/HSK1/Final/grammar_explained_by_llm.csv \\
      --skip-translation

  # Parallel processing with 5 workers
  python -m havachat.cli.enrich_grammar \\
      --language zh --level HSK1 \\
      --input data/hsk1_grammar.csv \\
      --enricher chinese \\
      --output output/zh/hsk1/grammar.json \\
      --parallel 5

  # Resume from checkpoint
  python -m havachat.cli.enrich_grammar \\
      --language zh --level HSK1 \\
      --input data/hsk1_grammar.csv \\
      --enricher chinese \\
      --output output/zh/hsk1/grammar.json \\
      --resume
        """,
    )

    parser.add_argument(
        "--language",
        required=True,
        choices=["zh"],
        help="Target language (ISO 639-1): zh=Chinese",
    )
    parser.add_argument(
        "--level",
        required=True,
        help="Proficiency level (e.g., HSK1, HSK2, HSK3)",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Input file path (CSV for Chinese). Not required when using --llm-explained-file.",
    )
    parser.add_argument(
        "--enricher",
        required=True,
        choices=["chinese"],
        help="Enricher type: chinese",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output JSON file path",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        help="Maximum number of items to process (for testing)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse input without calling LLM (validation mode)",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Number of parallel workers (default: 1, max: 10)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint file (load existing output)",
    )
    parser.add_argument(
        "--manual-review-dir",
        type=Path,
        help="Directory for manual review queue (default: ./manual_review)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM enrichment (generate structure with UUIDs only)",
    )

    parser.add_argument(
        "--skip-translation",
        action="store_true",
        help="Skip translation service (examples will have no translations)",
    )

    parser.add_argument(
        "--llm-explained-file",
        type=Path,
        help="CSV file with pre-generated LLM explanations (front,back,examples). "
        "When provided, skips LLM generation and ignores --max-items. "
        "Format: front=target_item, back=definition, examples=example1;;;example2;;;example3",
    )

    return parser.parse_args()


def validate_enricher_language(enricher: str, language: str) -> None:
    """Validate enricher-language compatibility.
    
    Args:
        enricher: Enricher type (e.g., "chinese")
        language: Language code (e.g., "zh")
        
    Raises:
        ValueError: If enricher doesn't match language
    """
    expected_lang = ENRICHER_LANGUAGE_MAP.get(enricher)
    if expected_lang != language:
        raise ValueError(
            f"Enricher '{enricher}' expects language '{expected_lang}', got '{language}'. "
            f"Use --language {expected_lang} with --enricher {enricher}."
        )


def load_checkpoint(checkpoint_path: Path) -> dict:
    """Load existing checkpoint file.
    
    Args:
        checkpoint_path: Path to checkpoint JSON file
        
    Returns:
        Dictionary mapping item IDs to enriched LearningItems
    """
    if not checkpoint_path.exists():
        return {}
    
    try:
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Loaded checkpoint with {len(data)} items from {checkpoint_path}")
        return {item["lemma"]: item for item in data}
    except Exception as e:
        logger.error(f"Failed to load checkpoint: {e}")
        return {}


def save_checkpoint(checkpoint_path: Path, items: list) -> None:
    """Save checkpoint to JSON file.
    
    Args:
        checkpoint_path: Path to checkpoint JSON file
        items: List of enriched LearningItem dictionaries
    """
    try:
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved checkpoint with {len(items)} items to {checkpoint_path}")
    except Exception as e:
        logger.error(f"Failed to save checkpoint: {e}")


def parse_llm_explained_file(file_path: Path) -> list[dict]:
    """Parse pre-generated LLM explanations CSV file.
    
    Expected format: front,back,examples
    - front: target_item
    - back: definition
    - examples: example1;;;example2;;;example3
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        List of dictionaries with 'target_item', 'definition', 'examples' keys
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If CSV format is invalid
    """
    if not file_path.exists():
        raise FileNotFoundError(f"LLM explained file not found: {file_path}")
    
    items = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            
            # Validate headers
            if not all(col in reader.fieldnames for col in ["front", "back", "examples"]):
                raise ValueError(
                    f"CSV must have 'front', 'back', 'examples' columns, got {reader.fieldnames}"
                )
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (1 is header)
                target_item = row["front"].strip()
                definition = row["back"].strip()
                examples_str = row["examples"].strip()
                
                if not target_item or not definition or not examples_str:
                    logger.warning(f"Skipping incomplete row {row_num}: {row}")
                    continue
                
                # Split examples by ";;;"
                examples = [ex.strip() for ex in examples_str.split(";;;") if ex.strip()]
                
                if not examples:
                    logger.warning(f"No examples found in row {row_num}: {row}")
                    continue
                
                items.append({
                    "target_item": target_item,
                    "definition": definition,
                    "examples": examples,
                })
        
        logger.info(f"Parsed {len(items)} items from {file_path}")
        return items
        
    except Exception as e:
        raise ValueError(f"Failed to parse LLM explained file: {e}")


def enrich_item_wrapper(enricher: BaseEnricher, item):
    """Wrapper for parallel enrichment."""
    try:
        return enricher.enrich_item(item)
    except Exception as e:
        logger.error(f"Failed to enrich item {item.get('pattern', 'unknown')}: {e}")
        return None


def main():
    """Main CLI entrypoint."""
    args = parse_args()
    
    # Configure logging
    configure_logging(level=args.log_level)
    
    # Validate enricher-language compatibility
    try:
        validate_enricher_language(args.enricher, args.language)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    
    # Validate inputs based on mode
    if args.llm_explained_file:
        # LLM explained mode: Only require llm_explained_file
        if not args.llm_explained_file.exists():
            logger.error(f"LLM explained file not found: {args.llm_explained_file}")
            sys.exit(1)
        logger.info(f"Using pre-generated LLM explanations from: {args.llm_explained_file}")
        
        # Input file is not required in this mode
        if args.input:
            logger.warning("--input is ignored when using --llm-explained-file")
        
        # max_items is ignored in this mode
        if args.max_items:
            logger.warning("--max-items is ignored when using --llm-explained-file")
    else:
        # Normal mode: Require input file
        if not args.input:
            logger.error("--input is required when not using --llm-explained-file")
            sys.exit(1)
        if not args.input.exists():
            logger.error(f"Input file not found: {args.input}")
            sys.exit(1)
    
    # Determine level system
    if args.language == "zh":
        if args.level.upper().startswith("HSK"):
            level_system = LevelSystem.HSK
        else:
            level_system = LevelSystem.CEFR
    else:
        level_system = LevelSystem.CEFR
    
    # Initialize LLM client (None for dry-run or skip-llm)
    # For llm_explained_file mode, we still need LLM for translation unless skip_translation
    if args.dry_run or args.skip_llm:
        llm_client = None
        if args.skip_llm:
            logger.info("SKIP LLM MODE: Generating structure with UUIDs only")
    elif args.llm_explained_file and args.skip_translation:
        # Don't need LLM if we have pre-generated explanations and skip translation
        llm_client = None
        logger.info("LLM EXPLAINED MODE with --skip-translation: No LLM client needed")
    else:
        llm_client = LLMClient()
    
    # Initialize enricher
    manual_review_dir = args.manual_review_dir or Path("./manual_review/grammar")
    
    if args.enricher == "chinese":
        enricher = ChineseGrammarEnricher(
            llm_client=llm_client,
            max_retries=3,
            manual_review_dir=manual_review_dir,
            skip_llm=args.dry_run or args.skip_llm,
            skip_translation=args.skip_translation,
        )
    else:
        logger.error(f"Unknown enricher: {args.enricher}")
        sys.exit(1)
    
    # Parse source file or LLM explained file
    if args.llm_explained_file:
        # Parse pre-generated LLM explanations
        logger.info(f"Parsing pre-generated LLM explanations: {args.llm_explained_file}")
        try:
            items = parse_llm_explained_file(args.llm_explained_file)
        except Exception as e:
            logger.error(f"Failed to parse LLM explained file: {e}")
            sys.exit(1)
    else:
        # Parse source file normally
        logger.info(f"Parsing source file: {args.input}")
        try:
            items = enricher.parse_source(args.input)
        except Exception as e:
            logger.error(f"Failed to parse source file: {e}")
            sys.exit(1)
        
        # Limit items if specified (only in normal mode)
        if args.max_items:
            items = items[:args.max_items]
            logger.info(f"Limited to first {args.max_items} items")
    
    logger.info(f"Found {len(items)} grammar patterns to enrich")
    
    # Add metadata to items for enricher
    for item in items:
        item["language"] = args.language
        item["level"] = args.level
        item["level_system"] = level_system
    
    # Determine the identifier key based on mode
    if args.llm_explained_file:
        # In LLM explained mode, use target_item as identifier
        identifier_key = "target_item"
    else:
        # In normal mode, use pattern as identifier
        identifier_key = "pattern"
    
    # Load checkpoint if resuming
    checkpoint_map = {}
    if args.resume:
        checkpoint_data = load_checkpoint(args.output)
        # Re-key checkpoint by identifier
        for item in checkpoint_data.values() if isinstance(checkpoint_data, dict) else checkpoint_data:
            # Use lemma or target_item as key
            key = item.get("lemma") or item.get("target_item")
            if key:
                checkpoint_map[key] = item
        logger.info(f"Resuming from checkpoint with {len(checkpoint_map)} existing items")
    
    # Filter out already enriched items
    items_to_enrich = [
        item for item in items if item[identifier_key] not in checkpoint_map
    ]
    logger.info(f"Items to enrich: {len(items_to_enrich)}")
    
    if args.dry_run:
        logger.info("[DRY RUN] Skipping LLM enrichment")
        for item in items[:5]:  # Show first 5 items
            if args.llm_explained_file:
                logger.info(f"  - {item['target_item']}: {item['definition'][:50]}...")
            else:
                logger.info(f"  - {item['pattern']} ({item['type']} > {item['category_name']})")
        return
    
    # Enrich items
    enriched_items = list(checkpoint_map.values())  # Start with checkpoint items
    failed_count = 0
    skipped_count = 0
    granularity_warnings = []
    
    start_time = time.time()
    
    # Choose the enrichment method based on mode
    if args.llm_explained_file:
        enrich_method = lambda item: enricher.enrich_from_llm_explained(item)
    else:
        enrich_method = lambda item: enricher.enrich_item(item)
    
    # Parallel or sequential processing
    if args.parallel > 1:
        # Limit parallel workers to max 10
        num_workers = min(args.parallel, 10)
        logger.info(f"Processing with {num_workers} parallel workers")
        
        def enrich_wrapper(item):
            try:
                return enrich_method(item)
            except Exception as e:
                logger.error(f"Failed to enrich item {item.get(identifier_key, 'unknown')}: {e}")
                return None
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Submit all tasks
            future_to_item = {
                executor.submit(enrich_wrapper, item): item
                for item in items_to_enrich
            }
            
            # Process results with progress bar
            with tqdm(total=len(items_to_enrich), desc="Enriching") as pbar:
                for future in as_completed(future_to_item):
                    item = future_to_item[future]
                    try:
                        result = future.result()
                        if result:
                            enriched_items.append(result.model_dump(mode="json"))
                            
                            # Check for granularity warnings
                            if len(result.definition) > 400:
                                granularity_warnings.append(result.target_item)
                        else:
                            failed_count += 1
                    except Exception as e:
                        logger.error(f"Task failed for {item.get(identifier_key, 'unknown')}: {e}")
                        failed_count += 1
                    finally:
                        pbar.update(1)
                        
                        # Save checkpoint every 10 items
                        if len(enriched_items) % 10 == 0:
                            save_checkpoint(args.output, enriched_items)
    else:
        # Sequential processing
        logger.info("Processing sequentially")
        with tqdm(total=len(items_to_enrich), desc="Enriching") as pbar:
            for item in items_to_enrich:
                result = enrich_method(item)
                if result:
                    enriched_items.append(result.model_dump(mode="json"))
                    
                    # Check for granularity warnings
                    if len(result.definition) > 400:
                        granularity_warnings.append(result.target_item)
                else:
                    failed_count += 1
                
                pbar.update(1)
                
                # Save checkpoint every 10 items
                if len(enriched_items) % 10 == 0:
                    save_checkpoint(args.output, enriched_items)
    
    # Save final output
    logger.info(f"Writing {len(enriched_items)} enriched items to {args.output}")
    write_json(enriched_items, args.output)
    
    # Summary statistics
    duration = time.time() - start_time
    success_count = len(enriched_items) - len(checkpoint_map)
    success_rate = (success_count / len(items_to_enrich) * 100) if items_to_enrich else 0
    
    logger.info("\n" + "=" * 60)
    logger.info("ENRICHMENT SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total items processed: {len(items_to_enrich)}")
    logger.info(f"Successfully enriched: {success_count}")
    logger.info(f"Failed/skipped: {failed_count}")
    logger.info(f"Success rate: {success_rate:.1f}%")
    logger.info(f"Duration: {duration:.1f}s")
    logger.info(f"Average time per item: {duration / len(items_to_enrich) if len(items_to_enrich) > 0  else 0:.2f}s")
    
    # Granularity warnings
    if granularity_warnings:
        logger.warning(f"\n⚠️  Granularity warnings for {len(granularity_warnings)} items:")
        logger.warning("   (Long definitions may indicate mega-items)")
        for pattern in granularity_warnings[:10]:  # Show first 10
            logger.warning(f"   - {pattern}")
        if len(granularity_warnings) > 10:
            logger.warning(f"   ... and {len(granularity_warnings) - 10} more")
    
    # Token usage summary
    if llm_client:
        usage = llm_client.get_usage_summary()
        logger.info(f"\nToken Usage:")
        logger.info(f"  Model: {usage['model']}")
        logger.info(f"  Prompt tokens: {usage['prompt_tokens']:,}")
        logger.info(f"  Completion tokens: {usage['completion_tokens']:,}")
        logger.info(f"  Total tokens: {usage['total_tokens']:,}")
        logger.info(f"  Cached tokens: {usage['cached_tokens']:,}")
        logger.info(f"  Cache hit rate: {usage['cache_hit_rate']}")
        logger.info(f"  Estimated cost: ${usage['estimated_cost_usd']:.4f}")
        logger.info(f"  - Input cost: ${usage['input_cost_usd']:.4f}")
        logger.info(f"  - Output cost: ${usage['output_cost_usd']:.4f}")
        if success_count > 0:
            logger.info(f"  Avg tokens per item: {usage['total_tokens'] / success_count:.1f}")
    
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
