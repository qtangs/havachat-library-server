"""CLI for generating learning items from enriched content.

This script generates learning items for categories beyond official vocab/grammar:
- pronunciation: Tone pairs, initials, finals (from vocab)
- idiom: Fixed expressions, collocations (from vocab/grammar)
- functional: Greetings, requests, apologies (from grammar)
- cultural: Customs, etiquette, context (from topic/scenario)
- writing_system: Radicals, components, stroke order (from vocab)
- misc: sociolinguistic, pragmatic, literacy, pattern (from vocab/grammar)

Usage:
    python -m havachat.cli.generate_learning_items \\
        --language zh --level HSK1 \\
        --category pronunciation \\
        --source-dir ../havachat-knowledge/generated\\ content/Chinese/HSK1/ \\
        --output output/learning_items/pronunciation/

Args:
    --language: ISO 639-1 code (zh, ja, fr, en, es)
    --level: Target level (A1, HSK1, N5, etc.)
    --category: Category to generate (pronunciation, idiom, functional, etc.)
    --source-dir: Directory containing enriched vocab/grammar JSON files
    --output: Output directory for generated items
    --topic: Optional topic name for cultural items
    --scenario: Optional scenario description for cultural items
    --max-items: Maximum items to generate (default: unlimited)
    --dry-run: Print plan without generating

Examples:
    # Generate pronunciation items from vocab
    python -m havachat.cli.generate_learning_items \\
        --language zh --level HSK1 \\
        --category pronunciation \\
        --source-dir ../havachat-knowledge/generated\\ content/Chinese/HSK1/vocab/

    # Generate cultural items for a topic
    python -m havachat.cli.generate_learning_items \\
        --language zh --level HSK1 \\
        --category cultural \\
        --topic "Food" \\
        --scenario "Ordering at a restaurant"
"""

import argparse
from dotenv import load_dotenv
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Union

from havachat.generators.learning_item_generator import BaseLearningItemGenerator
from havachat.parsers.source_parsers import load_source_file
from havachat.utils.azure_translation import AzureTranslationHelper
from havachat.utils.item_processing import post_process_learning_item
from havachat.utils.llm_client import LLMClient
from havachat.validators.schema import Category, LearningItem, LevelSystem

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SourceItem:
    """Lightweight wrapper for raw source items to provide attribute access.
    
    This allows generators to access fields using dot notation (item.target_item)
    even when working with raw dictionaries from source parsers.
    """
    
    def __init__(self, data: Dict[str, Any]):
        self._data = data
    
    def __getattr__(self, name: str) -> Any:
        """Allow attribute-style access to dictionary keys."""
        if name.startswith('_'):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        return self._data.get(name)
    
    def __repr__(self) -> str:
        return f"SourceItem({self._data.get('target_item', 'unknown')})"

load_dotenv()


def load_learning_items_from_dir(source_dir: Path) -> List[LearningItem]:
    """Load all learning items from JSON files in a directory.
    
    This function loads already-enriched learning items that have been
    saved as JSON files by the enrichment havachat.

    Args:
        source_dir: Directory containing learning item JSON files

    Returns:
        List of LearningItem objects
    """
    items = []
    json_files = list(source_dir.rglob("*.json"))
    
    logger.info(f"Loading learning items from {len(json_files)} files in {source_dir}")
    
    for json_file in json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                item = LearningItem(**data)
                items.append(item)
        except Exception as e:
            logger.warning(f"Failed to load {json_file}: {e}")
            continue
    
    logger.info(f"Loaded {len(items)} learning items")
    return items


def load_source_items_from_file(
    source_file: Path, 
    language: str, 
    content_type: str
) -> List[Union[LearningItem, SourceItem]]:
    """Load raw items from original source files (TSV, CSV, JSON).
    
    This function loads from the raw input files used by enrichers,
    NOT from enriched JSON outputs. Returns SourceItem wrappers that
    allow attribute-style access to fields, compatible with generators.
    
    Args:
        source_file: Path to source file (TSV, CSV, or JSON)
        language: Language code (zh, ja, fr, etc.)
        content_type: Type of content (vocab, grammar)
        
    Returns:
        List of SourceItem objects with parsed fields
        
    Raises:
        ValueError: If file format or language not supported
    """
    try:
        # Parse source file using centralized parsers
        parsed_items = load_source_file(source_file, language, content_type)
        
        # Add metadata and wrap in SourceItem for attribute access
        wrapped_items = []
        for item in parsed_items:
            item["language"] = language
            item["content_type"] = content_type
            item["category"] = Category.GRAMMAR if content_type == "grammar" else Category.VOCAB
            
            # Set default level if not present
            if "level_min" not in item:
                if language == "zh":
                    item["level_min"] = "HSK1"
                    item["level_max"] = "HSK1"
                elif language == "ja":
                    item["level_min"] = "N5"
                    item["level_max"] = "N5"
                else:
                    item["level_min"] = "A1"
                    item["level_max"] = "A1"
            
            wrapped_items.append(SourceItem(item))
        
        logger.info(f"Loaded {len(wrapped_items)} raw items from source file {source_file}")
        return wrapped_items
        
    except Exception as e:
        logger.error(f"Failed to load source file {source_file}: {e}", exc_info=True)
        raise


def load_items_from_directory_or_file(
    source_path: Path,
    language: str,
    content_type: str,
    is_enriched: bool = False
) -> List[Union[LearningItem, SourceItem]]:
    """Load items from either enriched JSON directory or original source files.
    
    Args:
        source_path: Path to directory (enriched JSON) or file (original source)
        language: Language code (zh, ja, fr, etc.)
        content_type: Type of content (vocab, grammar)
        is_enriched: True if loading from enriched JSON files, False for original sources
        
    Returns:
        List of LearningItem objects (if enriched) or SourceItem objects (if original)
    """
    if is_enriched:
        # Load from enriched JSON files in directory
        if not source_path.is_dir():
            raise ValueError(f"Expected directory for enriched items, got file: {source_path}")
        return load_learning_items_from_dir(source_path)
    else:
        # Load from original source file (returns SourceItem wrappers)
        if not source_path.is_file():
            raise ValueError(f"Expected file for source items, got directory: {source_path}")
        return load_source_items_from_file(source_path, language, content_type)



def filter_items_by_category(
    items: List[LearningItem], category: Category
) -> List[LearningItem]:
    """Filter learning items by category.

    Args:
        items: List of learning items
        category: Category to filter by

    Returns:
        Filtered list
    """
    filtered = [item for item in items if item.category == category]
    logger.info(f"Filtered {len(filtered)} items with category={category.value}")
    return filtered


def save_learning_items(items: List[LearningItem], output_dir: Path, single_file: bool = False, category: str = None) -> None:
    """Save learning items as individual JSON files or a single JSON file.

    Args:
        items: List of learning items to save
        output_dir: Output directory
        single_file: If True, save all items in one JSON file; if False, save individually
        category: Category name for generating filename (e.g., "idiom" -> "idiom_generated.json")
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if single_file:
        # Save all items in a single JSON file with category-specific name
        if category:
            filename = f"{category}_generated.json"
        else:
            filename = "learning_items.json"
        output_path = output_dir / filename
        items_data = [item.model_dump(mode="json") for item in items]
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(items_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved {len(items)} items to {output_path}")
    else:
        # Save as individual files (original behavior)
        for item in items:
            filename = f"{item.category.value}_{item.id}.json"
            output_path = output_dir / filename
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(item.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved {len(items)} items to {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate learning items from enriched content",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    # Required arguments
    parser.add_argument(
        "--language",
        required=True,
        choices=["zh", "ja", "fr", "en", "es"],
        help="ISO 639-1 language code",
    )
    parser.add_argument(
        "--level",
        required=True,
        help="Target proficiency level (A1, HSK1, N5, etc.)",
    )
    parser.add_argument(
        "--category",
        required=True,
        choices=[
            "pronunciation",
            "idiom",
            "functional",
            "cultural",
            "writing_system",
            "sociolinguistic",
            "pragmatic",
            "literacy",
            "pattern",
            "other",
        ],
        help="Category of learning items to generate",
    )
    
    # Optional arguments
    parser.add_argument(
        "--source-dir",
        type=Path,
        help="Directory containing enriched JSON files (if --source-type=enriched)",
    )
    parser.add_argument(
        "--source-file",
        type=Path,
        help="Source file (TSV/CSV/JSON) to load from (if --source-type=original)",
    )
    parser.add_argument(
        "--vocab-source-file",
        type=Path,
        help="Vocab source file for categories needing both vocab and grammar",
    )
    parser.add_argument(
        "--grammar-source-file",
        type=Path,
        help="Grammar source file for categories needing both vocab and grammar",
    )
    parser.add_argument(
        "--source-type",
        choices=["enriched", "original"],
        default="enriched",
        help="Type of source: 'enriched' (JSON dir) or 'original' (TSV/CSV/JSON file)",
    )
    parser.add_argument(
        "--content-type",
        choices=["vocab", "grammar"],
        default="vocab",
        help="Content type for original source files (required if --source-type=original)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory for generated items",
    )
    parser.add_argument(
        "--single-file",
        action="store_true",
        help="Save all items in a single JSON file instead of individual files",
    )
    parser.add_argument(
        "--topic",
        help="Topic name for cultural items (required for cultural category)",
    )
    parser.add_argument(
        "--scenario",
        help="Scenario description for cultural items (required for cultural category)",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        help="Maximum number of items to generate",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print plan without generating items",
    )
    
    args = parser.parse_args()
    
    # Validation
    if args.category == "cultural" and (not args.topic or not args.scenario):
        parser.error("--topic and --scenario are required for cultural category")
    
    if args.category != "cultural":
        if args.source_type == "enriched" and not args.source_dir:
            parser.error("--source-dir is required when --source-type=enriched")
        if args.source_type == "original":
            # Allow either --source-file OR specific source files (--vocab-source-file, --grammar-source-file)
            has_source_file = args.source_file is not None
            has_specific_files = args.vocab_source_file is not None or args.grammar_source_file is not None
            if not has_source_file and not has_specific_files:
                parser.error("--source-file or --vocab-source-file/--grammar-source-file is required when --source-type=original")
    
    # Determine level system
    level_system = None
    level_upper = args.level.upper()
    if level_upper.startswith("HSK"):
        level_system = LevelSystem.HSK
    elif level_upper.startswith("N"):
        level_system = LevelSystem.JLPT
    else:
        level_system = LevelSystem.CEFR
    
    logger.info(f"Starting learning item generation:")
    logger.info(f"  Language: {args.language}")
    logger.info(f"  Level: {args.level} ({level_system.value})")
    logger.info(f"  Category: {args.category}")
    logger.info(f"  Source type: {args.source_type}")
    logger.info(f"  Output: {args.output}")
    
    if args.dry_run:
        logger.info("DRY RUN - no items will be generated")
        sys.exit(0)
    
    # Initialize generator
    llm_client = LLMClient()
    generator = BaseLearningItemGenerator(
        language=args.language,
        level_system=level_system,
        level=args.level,
        llm_client=llm_client,
    )
    
    # Generate items based on category
    generated_items = []
    
    try:
        if args.category == "pronunciation":
            # Load vocab items
            if args.source_type == "enriched":
                vocab_items = load_learning_items_from_dir(args.source_dir)
                vocab_items = filter_items_by_category(vocab_items, Category.VOCAB)
            else:
                vocab_items = load_source_items_from_file(
                    args.source_file, args.language, args.content_type
                )
            
            if args.max_items:
                vocab_items = vocab_items[:args.max_items]
            
            generated_items = generator.generate_pronunciation_items(vocab_items)
        
        elif args.category == "idiom":
            # Load vocab and grammar items
            if args.source_type == "enriched":
                all_items = load_learning_items_from_dir(args.source_dir)
                vocab_items = filter_items_by_category(all_items, Category.VOCAB)
                grammar_items = filter_items_by_category(all_items, Category.GRAMMAR)
            else:
                # Load from multiple source files
                vocab_items = []
                grammar_items = []
                
                if args.vocab_source_file:
                    vocab_items = load_source_items_from_file(
                        args.vocab_source_file, args.language, "vocab"
                    )
                elif args.source_file:
                    vocab_items = load_source_items_from_file(
                        args.source_file, args.language, "vocab"
                    )
                
                if args.grammar_source_file:
                    grammar_items = load_source_items_from_file(
                        args.grammar_source_file, args.language, "grammar"
                    )
            
            if args.max_items:
                vocab_items = vocab_items[:args.max_items]
            
            generated_items = generator.generate_idiom_items(vocab_items, grammar_items)
        
        elif args.category == "functional":
            # Load grammar items
            if args.source_type == "enriched":
                grammar_items = load_learning_items_from_dir(args.source_dir)
                grammar_items = filter_items_by_category(grammar_items, Category.GRAMMAR)
            else:
                grammar_items = []
                if args.grammar_source_file:
                    grammar_items = load_source_items_from_file(
                        args.grammar_source_file, args.language, "grammar"
                    )
                elif args.source_file:
                    grammar_items = load_source_items_from_file(
                        args.source_file, args.language, "grammar"
                    )
            
            if args.max_items:
                grammar_items = grammar_items[:args.max_items]
            
            generated_items = generator.generate_functional_items(grammar_items)
        
        elif args.category == "cultural":
            # Generate from topic/scenario
            num_items = args.max_items or 3
            for _ in range(num_items):
                items = generator.generate_cultural_items(args.topic, args.scenario)
                generated_items.extend(items)
                if len(generated_items) >= num_items:
                    break
        
        elif args.category == "writing_system":
            # Load vocab items
            if args.source_type == "enriched":
                vocab_items = load_learning_items_from_dir(args.source_dir)
                vocab_items = filter_items_by_category(vocab_items, Category.VOCAB)
            else:
                vocab_items = []
                if args.vocab_source_file:
                    vocab_items = load_source_items_from_file(
                        args.vocab_source_file, args.language, "vocab"
                    )
                elif args.source_file:
                    vocab_items = load_source_items_from_file(
                        args.source_file, args.language, "vocab"
                    )
            
            if args.max_items:
                vocab_items = vocab_items[:args.max_items]
            
            generated_items = generator.generate_writing_system_items(vocab_items)
        
        else:
            # Miscellaneous categories
            if args.source_type == "enriched":
                all_items = load_learning_items_from_dir(args.source_dir)
                vocab_items = filter_items_by_category(all_items, Category.VOCAB)
                grammar_items = filter_items_by_category(all_items, Category.GRAMMAR)
            else:
                # Load from multiple source files
                vocab_items = []
                grammar_items = []
                
                if args.vocab_source_file:
                    vocab_items = load_source_items_from_file(
                        args.vocab_source_file, args.language, "vocab"
                    )
                elif args.source_file:
                    vocab_items = load_source_items_from_file(
                        args.source_file, args.language, "vocab"
                    )
                
                if args.grammar_source_file:
                    grammar_items = load_source_items_from_file(
                        args.grammar_source_file, args.language, "grammar"
                    )
            
            if args.max_items:
                combined = vocab_items + grammar_items
                combined = combined[:args.max_items]
                vocab_items = [i for i in combined if i.category == Category.VOCAB]
                grammar_items = [i for i in combined if i.category == Category.GRAMMAR]
            
            category_enum = Category[args.category.upper()]
            generated_items = generator.generate_miscellaneous_items(
                vocab_items, grammar_items, category_enum
            )
    
    except Exception as e:
        logger.error(f"Generation failed: {e}", exc_info=True)
        sys.exit(1)
    
    # Apply post-processing (romanization, translation, etc.)
    if generated_items:
        logger.info(f"Applying post-processing to {len(generated_items)} items...")
        
        # Initialize Azure Translation
        translation_helper = AzureTranslationHelper()
        
        # Process each item
        processed_items = []
        for item in generated_items:
            try:
                processed_item = post_process_learning_item(
                    item, args.language, translation_helper
                )
                processed_items.append(processed_item)
            except Exception as e:
                logger.warning(f"Failed to post-process item {item.id}: {e}")
                # Keep original item if processing fails
                processed_items.append(item)
        
        logger.info(f"Post-processing complete for {len(processed_items)} items")
        generated_items = processed_items
    
    # Save generated items
    if generated_items:
        save_learning_items(generated_items, args.output, single_file=args.single_file, category=args.category)
        
        # Print summary
        logger.info("\n" + "=" * 80)
        logger.info("GENERATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total items generated: {len(generated_items)}")
        logger.info(f"Category: {args.category}")
        logger.info(f"Language: {args.language}, Level: {args.level}")
        logger.info(f"Output: {args.output}")
        if args.single_file:
            logger.info(f"  Mode: Single JSON file")
        else:
            logger.info(f"  Mode: Individual JSON files per item")
        
        # Token usage
        logger.info(f"\nToken Usage:")
        logger.info(f"  Prompt tokens: {llm_client.total_usage.prompt_tokens:,}")
        logger.info(f"  Completion tokens: {llm_client.total_usage.completion_tokens:,}")
        logger.info(f"  Total tokens: {llm_client.total_usage.total_tokens:,}")
        logger.info(f"  Cached tokens: {llm_client.total_usage.cached_tokens:,}")
        
        # TODO: Add cost estimation method to LLMClient
        # cost = llm_client.estimate_cost()
        # logger.info(f"  Estimated cost: ${cost:.4f}")
        logger.info("=" * 80)
    else:
        logger.warning("No items were generated")
        sys.exit(1)


if __name__ == "__main__":
    main()
