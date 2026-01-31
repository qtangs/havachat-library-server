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
    python -m havachat.cli.generate_content \\
        --language zh --level HSK1 \\
        --topic "Food" \\
        --learning-items-dir ../havachat-knowledge/generated\\ content/Chinese/HSK1/ \\
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
    python -m havachat.cli.generate_content \\
        --language zh --level HSK1 \\
        --topic "Food" \\
        --learning-items-dir ../havachat-knowledge/generated\\ content/Chinese/HSK1/ \\
        --output output/content/food/ \\
        --type both \\
        --track-usage

    # Generate only conversations (no stories)
    python -m havachat.cli.generate_content \\
        --language fr --level A1 \\
        --topic "Travel" \\
        --learning-items-dir ../havachat-knowledge/generated\\ content/French/A1/ \\
        --output output/content/travel/ \\
        --type conversation \\
        --num-conversations 10

    # Generate only stories (no conversations)
    python -m havachat.cli.generate_content \\
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
import os
import sys
from pathlib import Path

from havachat.generators.content_generator import ContentGenerator
from havachat.utils.llm_client import LLMClient
from havachat.utils.usage_tracker import UsageTracker
from havachat.validators.schema import LevelSystem
from src.pipeline.validators.llm_judge import LLMJudge
from src.pipeline.utils.notion_client import NotionClient, NotionSchemaError
from src.pipeline.utils.notion_mapping_manager import NotionMappingManager

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
    
    parser.add_argument(
        "--enable-notion",
        action="store_true",
        help="Enable LLM judge evaluation and Notion push after generation",
    )
    
    parser.add_argument(
        "--skip-judge",
        action="store_true",
        help="Skip LLM judge evaluation (use with --enable-notion to push without evaluation)",
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
    
    # Initialize separate LLM client for judge with dedicated model
    llm_judge_model = os.getenv("LLM_JUDGE_MODEL", "gpt-4")
    llm_judge_client = LLMClient(model=llm_judge_model)
    
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
            logger.error("Use: python -m havachat.cli.generate_learning_items")
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
        
        # Stage 3: LLM Judge Evaluation and Notion Push (if enabled)
        if args.enable_notion and not args.skip_judge:
            logger.info("\n" + "=" * 80)
            logger.info("STAGE 3: LLM Quality Judge Evaluation")
            logger.info("=" * 80)
            logger.info(f"Using LLM Judge model: {llm_judge_model}")
            
            llm_judge = LLMJudge(llm_client=llm_judge_client)
            
            # Evaluate conversations
            for conversation in batch.conversations:
                logger.info(f"Evaluating conversation: {conversation.title}")
                
                # Format segments as text
                text = "\n".join([
                    f"{seg.speaker}: {seg.text}"
                    for seg in conversation.segments
                ])
                
                evaluation = llm_judge.evaluate_conversation(
                    content_id=conversation.id,
                    text=text,
                    language=args.language,
                    level=args.level,
                    content_type="conversation"
                )
                
                # Store evaluation in content unit
                conversation.llm_judge_evaluation = evaluation
                
                logger.info(
                    f"  Average score: {evaluation.average_score():.1f}/10 - "
                    f"Recommendation: {evaluation.overall_recommendation}"
                )
                
            # Evaluate stories
            for story in batch.stories:
                logger.info(f"Evaluating story: {story.title}")
                
                # Format segments as text
                text = "\n".join([seg.text for seg in story.segments])
                
                evaluation = llm_judge.evaluate_conversation(
                    content_id=story.id,
                    text=text,
                    language=args.language,
                    level=args.level,
                    content_type="story"
                )
                
                # Store evaluation in content unit
                story.llm_judge_evaluation = evaluation
                
                logger.info(
                    f"  Average score: {evaluation.average_score():.1f}/10 - "
                    f"Recommendation: {evaluation.overall_recommendation}"
                )
        
        # Stage 4: Push to Notion (if enabled)
        if args.enable_notion:
            logger.info("\n" + "=" * 80)
            logger.info("STAGE 4: Pushing to Notion")
            logger.info("=" * 80)
            
            # Get Notion credentials
            notion_token = os.getenv("NOTION_API_TOKEN")
            database_id = os.getenv("NOTION_DATABASE_ID")
            
            if not notion_token or not database_id:
                logger.warning(
                    "Notion credentials not found. Set NOTION_API_TOKEN and "
                    "NOTION_DATABASE_ID environment variables to enable Notion push."
                )
            else:
                try:
                    notion_client = NotionClient(
                        api_token=notion_token,
                        database_id=database_id
                    )
                    notion_client.validate_database_schema()
                    mapping_manager = NotionMappingManager()
                    
                    # Push conversations
                    for conversation in batch.conversations:
                        try:
                            # Skip if already pushed
                            if mapping_manager.get_notion_page_id(conversation.id):
                                logger.info(f"Already in Notion: {conversation.title}")
                                continue
                                
                            notion_page_id = notion_client.push_conversation(
                                content_id=conversation.id,
                                content_type="conversation",
                                title=conversation.title,
                                description=conversation.description or "",
                                topic=conversation.topic_name,
                                scenario=conversation.scenario_name,
                                segments=[seg.model_dump() for seg in conversation.segments],
                                llm_evaluation=conversation.llm_judge_evaluation,
                                language=args.language,
                                level=args.level
                            )
                            
                            # Add mapping
                            mapping_manager.add_mapping(
                                content_id=conversation.id,
                                notion_page_id=notion_page_id,
                                language=args.language,
                                level=args.level,
                                content_type="conversation",
                                title=conversation.title
                            )
                            
                            logger.info(f"Pushed to Notion: {conversation.title}")
                            
                        except Exception as e:
                            logger.error(f"Failed to push {conversation.title}: {e}")
                    
                    # Push stories
                    for story in batch.stories:
                        try:
                            # Skip if already pushed
                            if mapping_manager.get_notion_page_id(story.id):
                                logger.info(f"Already in Notion: {story.title}")
                                continue
                                
                            notion_page_id = notion_client.push_conversation(
                                content_id=story.id,
                                content_type="story",
                                title=story.title,
                                description=story.description or "",
                                topic=story.topic_name,
                                scenario=story.scenario_name,
                                segments=[seg.model_dump() for seg in story.segments],
                                llm_evaluation=story.llm_judge_evaluation,
                                language=args.language,
                                level=args.level
                            )
                            
                            # Add mapping
                            mapping_manager.add_mapping(
                                content_id=story.id,
                                notion_page_id=notion_page_id,
                                language=args.language,
                                level=args.level,
                                content_type="story",
                                title=story.title
                            )
                            
                            logger.info(f"Pushed to Notion: {story.title}")
                            
                        except Exception as e:
                            logger.error(f"Failed to push {story.title}: {e}")
                            
                    logger.info("Notion push completed")
                    
                except NotionSchemaError as e:
                    logger.error(f"Notion schema validation failed: {e}")
                except Exception as e:
                    logger.error(f"Notion push failed: {e}")
        
        # Save content units
        logger.info("\n" + "=" * 80)
        logger.info("STAGE 5: Saving Content")
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
