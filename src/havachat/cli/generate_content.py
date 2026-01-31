"""CLI for generating content with chain-of-thought reasoning.

This script generates conversations and/or stories using ALL learning item categories
together in a single LLM call with chain-of-thought:
1. Generate initial drafts
2. Critique coverage and quality
3. Revise based on critique
4. Assign scenario names

The script uses generated_content_info.json in the learning-items-dir to discover
and correctly parse learning item files (both original TSV/CSV and enriched JSON).

Usage:
    python -m src.havachat.cli.generate_content \\
        --language zh --level HSK1 \\
        --topic "Food" \\
        --learning-items-dir ../havachat-knowledge/generated\\ content/Mandarin/HSK1/ \\
        --output output/content/ \\
        --type both \\
        --num-conversations 5 \\
        --num-stories 5

Args:
    --language: ISO 639-1 code (zh, ja, fr, en, es)
    --level: Target level (A1, HSK1, N5, etc.)
    --topic: Topic name (e.g., "Food", "Travel", "Shopping")
    --learning-items-dir: Directory containing generated_content_info.json
    --output: Output directory for generated content
    --type: Type of content to generate (conversation, story, or both; default: both)
    --num-conversations: Number of conversations to generate (default: 5, ignored if --type=story)
    --num-stories: Number of stories to generate (default: 5, ignored if --type=conversation)
    --track-usage: Track learning item usage in usage_stats.json
    --dry-run: Print plan without generating

Examples:
    # Generate both conversations and stories for Food topic
    python -m src.havachat.cli.generate_content \\
        --language zh --level HSK1 \\
        --topic "Food" \\
        --learning-items-dir ../havachat-knowledge/generated\\ content/Mandarin/HSK1/ \\
        --output output/content/food/ \\
        --type both \\
        --track-usage

    # Generate only conversations (no stories)
    python -m src.havachat.cli.generate_content \\
        --language fr --level A1 \\
        --topic "Travel" \\
        --learning-items-dir ../havachat-knowledge/generated\\ content/French/A1/ \\
        --output output/content/travel/ \\
        --type conversation \\
        --num-conversations 10

    # Generate only stories (no conversations)
    python -m src.havachat.cli.generate_content \\
        --language ja --level N5 \\
        --topic "Daily Life" \\
        --learning-items-dir ../havachat-knowledge/generated\\ content/Japanese/N5/ \\
        --output output/content/daily/ \\
        --type story \\
        --num-stories 8
"""

import argparse
from dotenv import load_dotenv
import json
import logging
import sys
from pathlib import Path

from havachat.generators.content_generator import ContentGenerator
from havachat.utils.llm_client import LLMClient
from havachat.utils.usage_tracker import UsageTracker
from havachat.validators.schema import LevelSystem

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

def save_content_unit(content_unit, output_dir: Path) -> None:
    """Save content unit as JSON file.

    Args:
        content_unit: ContentUnit to save
        output_dir: Output directory
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create subdirectory by type
    type_dir = output_dir / content_unit.type.value
    type_dir.mkdir(exist_ok=True)
    
    filename = f"{content_unit.type.value}_{content_unit.id}.json"
    output_path = type_dir / filename
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(content_unit.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
    
    logger.debug(f"Saved {content_unit.type.value}: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate content with chain-of-thought reasoning",
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
        "--topic",
        required=True,
        help="Topic name (e.g., 'Food', 'Travel', 'Shopping')",
    )
    parser.add_argument(
        "--learning-items-dir",
        type=Path,
        required=True,
        help="Directory containing generated_content_info.json (auto-discovers learning item files)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory for generated content",
    )
    
    # Optional arguments
    parser.add_argument(
        "--type",
        choices=["conversation", "story", "both"],
        default="both",
        help="Type of content to generate: conversation, story, or both (default: both)",
    )
    parser.add_argument(
        "--num-conversations",
        type=int,
        default=5,
        help="Number of conversations to generate (default: 5, ignored if --type=story)",
    )
    parser.add_argument(
        "--num-stories",
        type=int,
        default=5,
        help="Number of stories to generate (default: 5, ignored if --type=conversation)",
    )
    parser.add_argument(
        "--track-usage",
        action="store_true",
        help="Track learning item usage in usage_stats.json",
    )
    parser.add_argument(
        "--use-azure-translation",
        action="store_true",
        help="Use Azure Translation API instead of LLM for segment translations",
    )
    parser.add_argument(
        "--use-google-translation",
        action="store_true",
        help="Use Google Translate API instead of LLM for segment translations (highest priority)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print plan without generating content",
    )
    
    args = parser.parse_args()
    
    # Validation
    if not args.learning_items_dir.exists():
        logger.error(f"Learning items directory not found: {args.learning_items_dir}")
        sys.exit(1)
    
    # Determine level system
    level_system = None
    level_upper = args.level.upper()
    if level_upper.startswith("HSK"):
        level_system = LevelSystem.HSK
    elif level_upper.startswith("N"):
        level_system = LevelSystem.JLPT
    else:
        level_system = LevelSystem.CEFR
    
    logger.info(f"Starting content generation:")
    logger.info(f"  Language: {args.language}")
    logger.info(f"  Level: {args.level} ({level_system.value})")
    logger.info(f"  Topic: {args.topic}")
    logger.info(f"  Type: {args.type}")
    if args.type in ["conversation", "both"]:
        logger.info(f"  Conversations: {args.num_conversations}")
    if args.type in ["story", "both"]:
        logger.info(f"  Stories: {args.num_stories}")
    logger.info(f"  Output: {args.output}")
    
    if args.dry_run:
        logger.info("DRY RUN - no content will be generated")
        sys.exit(0)
    
    # Initialize components
    llm_client = LLMClient()
    generator = ContentGenerator(
        language=args.language,
        level_system=level_system,
        level=args.level,
        llm_client=llm_client,
        use_azure_translation=args.use_azure_translation,
        use_google_translation=args.use_google_translation,
    )
    
    # Initialize usage tracker if requested
    usage_tracker = None
    if args.track_usage:
        stats_file = args.output / "usage_stats.json"
        usage_tracker = UsageTracker(stats_file)
        logger.info(f"Usage tracking enabled: {stats_file}")
    
    try:
        # Stage 1: Load ALL learning items
        logger.info("\n" + "=" * 80)
        logger.info("STAGE 1: Loading Learning Items")
        logger.info("=" * 80)
        
        num_items = generator.load_learning_items(args.learning_items_dir)
        
        if num_items == 0:
            logger.error("No learning items found. Generate learning items first.")
            logger.error("Use: python -m src.havachat.cli.generate_learning_items")
            sys.exit(1)
        
        logger.info(f"Loaded {num_items} learning items from all categories")
        
        # Load existing topics and scenarios (or initialize empty)
        generator.load_topics_and_scenarios(args.output)
        
        # Stage 2: Generate content with chain-of-thought
        logger.info("\n" + "=" * 80)
        logger.info("STAGE 2: Generating Content with Chain-of-Thought")
        logger.info("=" * 80)
        
        batch = generator.generate_content_batch(
            topic=args.topic,
            num_conversations=args.num_conversations,
            num_stories=args.num_stories,
            content_type=args.type,
        )
        
        logger.info(f"Generated {len(batch.conversations)} conversations")
        logger.info(f"Generated {len(batch.stories)} stories")
        
        # Save chain-of-thought for review
        if batch.chain_of_thought_raw:
            cot_file = args.output / "chain_of_thought.json"
            with open(cot_file, "w", encoding="utf-8") as f:
                json.dump(
                    batch.chain_of_thought_raw.model_dump(mode="json"),
                    f,
                    ensure_ascii=False,
                    indent=2
                )
            logger.info(f"Saved chain-of-thought to: {cot_file}")
        
        # Save content units
        logger.info("\n" + "=" * 80)
        logger.info("STAGE 3: Saving Content")
        logger.info("=" * 80)
        
        for conversation in batch.conversations:
            save_content_unit(conversation, args.output)
            
            # Track usage
            if usage_tracker:
                usage_tracker.update_batch(
                    content_unit_id=conversation.id,
                    learning_item_ids=conversation.learning_item_ids,
                    learning_items=generator.all_learning_items,
                )
        
        for story in batch.stories:
            save_content_unit(story, args.output)
            
            # Track usage
            if usage_tracker:
                usage_tracker.update_batch(
                    content_unit_id=story.id,
                    learning_item_ids=story.learning_item_ids,
                    learning_items=generator.all_learning_items,
                )
        
        # Save usage stats
        if usage_tracker:
            usage_tracker.save_stats()
            logger.info(f"Saved usage statistics")
        
        # Print summary
        logger.info("\n" + "=" * 80)
        logger.info("GENERATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Topic: {args.topic}")
        logger.info(f"Language: {args.language}, Level: {args.level}")
        logger.info(f"Conversations generated: {len(batch.conversations)}")
        logger.info(f"Stories generated: {len(batch.stories)}")
        logger.info(f"Total content units: {len(batch.conversations) + len(batch.stories)}")
        
        # Chain-of-thought metrics
        cot_metrics = batch.chain_of_thought_metadata
        logger.info(f"\nChain-of-Thought Quality Metrics:")
        logger.info(f"  Average coverage score: {cot_metrics.get('avg_coverage_score', 0):.2f}/10")
        logger.info(f"  Average level score: {cot_metrics.get('avg_level_score', 0):.2f}/10")
        logger.info(f"  Average flow score: {cot_metrics.get('avg_flow_score', 0):.2f}/10")
        logger.info(f"  Improvement rate: {cot_metrics.get('improvement_rate', 0):.2%}")
        logger.info(f"  Total improvements made: {cot_metrics.get('total_improvements', 0)}")
        
        # Token usage
        logger.info(f"\nToken Usage:")
        logger.info(f"  Prompt tokens: {llm_client.total_usage.prompt_tokens:,}")
        logger.info(f"  Completion tokens: {llm_client.total_usage.completion_tokens:,}")
        logger.info(f"  Total tokens: {llm_client.total_usage.total_tokens:,}")
        logger.info(f"  Cached tokens: {llm_client.total_usage.cached_tokens:,}")
        
        # TODO: Add estimate_cost() method to LLMClient
        # cost = llm_client.estimate_cost()
        # logger.info(f"  Estimated cost: ${cost:.4f}")
        
        # Usage statistics
        if usage_tracker:
            logger.info("\n")
            usage_tracker.print_report()
        
        logger.info("=" * 80)
        logger.info(f"Content saved to: {args.output}")
        logger.info("=" * 80 + "\n")
    
    except Exception as e:
        logger.error(f"Content generation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
