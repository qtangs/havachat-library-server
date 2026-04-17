"""CLI for rerunning LLM Judge + Notion sync on existing content.

This script processes already-generated content files that either:
1. Don't have LLM judge evaluations yet (due to errors during generation)
2. Need to be synced to Notion

Usage:
    # Rerun LLM judge and push to Notion for all content in a directory
    python -m havachat.cli.rerun_judge_notion \\
        --content-dir output/content/food/ \\
        --language zh --level HSK1

    # Skip LLM judge, only push to Notion
    python -m havachat.cli.rerun_judge_notion \\
        --content-dir output/content/food/ \\
        --language zh --level HSK1 \\
        --skip-judge

    # Only rerun judge, don't push to Notion
    python -m havachat.cli.rerun_judge_notion \\
        --content-dir output/content/food/ \\
        --language zh --level HSK1 \\
        --judge-only

Args:
    --content-dir: Directory containing content JSON files (conversation/ and story/ subdirs)
    --language: ISO 639-1 code (zh, ja, fr, en, es)
    --level: Target level (A1, HSK1, N5, etc.)
    --skip-judge: Skip LLM judge evaluation (only push to Notion)
    --judge-only: Only run LLM judge, don't push to Notion
    --force-judge: Re-evaluate even if evaluation already exists
    --dry-run: Print what would be done without processing
"""

import argparse
from dotenv import load_dotenv
import json
import logging
import os
import sys
from pathlib import Path
from typing import List

from havachat.utils.llm_client import LLMClient
from havachat.validators.schema import ContentUnit
from src.models.llm_judge_evaluation import LLMJudgeEvaluation
from havachat.validators.llm_judge import LLMJudge
from havachat.utils.notion_client import NotionClient, NotionSchemaError
from havachat.utils.notion_mapping_manager import NotionMappingManager

# Rebuild ContentUnit model now that LLMJudgeEvaluation is imported
ContentUnit.model_rebuild()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()


def load_content_files(content_dir: Path) -> List[ContentUnit]:
    """Load all content JSON files from directory.
    
    Args:
        content_dir: Directory containing conversation/ and story/ subdirectories
        
    Returns:
        List of ContentUnit objects
    """
    content_units = []
    
    # Check for conversation and story subdirectories
    for subdir in ["conversation", "story"]:
        subdir_path = content_dir / subdir
        if not subdir_path.exists():
            logger.warning(f"Subdirectory not found: {subdir_path}")
            continue
        
        # Load all JSON files (skip manifest files)
        for json_file in subdir_path.glob("*.json"):
            # Skip manifest and other non-content files
            if json_file.name in ["manifest.json", "chain_of_thought.json", "notion_mapping.json"]:
                continue
            
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    content_unit = ContentUnit.model_validate(data)
                    content_units.append(content_unit)
                    logger.debug(f"Loaded: {json_file.name}")
            except Exception as e:
                logger.error(f"Failed to load {json_file.name}: {e}")
    
    logger.info(f"Loaded {len(content_units)} content units from {content_dir}")
    return content_units


def save_content_unit(content_unit: ContentUnit, content_dir: Path) -> None:
    """Save updated content unit back to JSON file.
    
    Args:
        content_unit: ContentUnit to save
        content_dir: Base directory containing conversation/ and story/ subdirs
    """
    # Create subdirectory by type
    type_dir = content_dir / content_unit.type.value
    type_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"{content_unit.type.value}_{content_unit.id}.json"
    filepath = type_dir / filename
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(
            content_unit.model_dump(mode="json"),
            f,
            ensure_ascii=False,
            indent=2
        )
    logger.debug(f"Saved: {filename}")


def get_llm_judge_eval_path(
    content_dir: Path,
    content_type: str,
    content_id: str
) -> Path:
    eval_dir = content_dir / "llm_judge"
    return eval_dir / f"{content_type}_{content_id}_llm_judge.txt"


def save_llm_judge_evaluation_text(
    evaluation: LLMJudgeEvaluation,
    content_dir: Path,
    content_type: str
) -> Path:
    """Save LLM judge evaluation as human-readable text."""
    eval_dir = content_dir / "llm_judge"
    eval_dir.mkdir(parents=True, exist_ok=True)
    output_path = get_llm_judge_eval_path(content_dir, content_type, evaluation.content_id)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(evaluation.to_readable_text())

    logger.debug(f"Saved LLM judge evaluation: {output_path}")
    return output_path


def load_llm_judge_evaluation_text(
    content_dir: Path,
    content_type: str,
    content_id: str
) -> str | None:
    eval_path = get_llm_judge_eval_path(content_dir, content_type, content_id)
    if not eval_path.exists():
        return None
    return eval_path.read_text(encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Rerun LLM Judge + Notion sync on existing content"
    )
    parser.add_argument(
        "--content-dir",
        type=Path,
        required=True,
        help="Directory containing content JSON files",
    )
    parser.add_argument(
        "--language",
        type=str,
        required=True,
        help="ISO 639-1 language code (e.g., zh, ja, fr)",
    )
    parser.add_argument(
        "--level",
        type=str,
        required=True,
        help="Target proficiency level (e.g., HSK1, A1, N5)",
    )
    parser.add_argument(
        "--skip-judge",
        action="store_true",
        help="Skip LLM judge evaluation (only push to Notion)",
    )
    parser.add_argument(
        "--judge-only",
        action="store_true",
        help="Only run LLM judge (don't push to Notion)",
    )
    parser.add_argument(
        "--force-judge",
        action="store_true",
        help="Re-evaluate even if evaluation already exists",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force Notion push even if ID already exists",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without processing",
    )
    
    args = parser.parse_args()
    
    # Validation
    if not args.content_dir.exists():
        logger.error(f"Content directory not found: {args.content_dir}")
        sys.exit(1)
    
    if args.skip_judge and args.judge_only:
        logger.error("Cannot use --skip-judge and --judge-only together")
        sys.exit(1)
    
    logger.info("Starting rerun of LLM Judge + Notion sync:")
    logger.info(f"  Content directory: {args.content_dir}")
    logger.info(f"  Language: {args.language}")
    logger.info(f"  Level: {args.level}")
    logger.info(f"  Skip judge: {args.skip_judge}")
    logger.info(f"  Judge only: {args.judge_only}")
    logger.info(f"  Force re-evaluation: {args.force_judge}")
    logger.info(f"  Force Notion push: {args.force}")
    
    if args.dry_run:
        logger.info("DRY RUN - no processing will be done")
    
    # Load content files
    content_units = load_content_files(args.content_dir)
    
    if not content_units:
        logger.error("No content files found")
        sys.exit(1)
    
    # Initialize LLM judge if needed
    llm_judge = None
    if not args.skip_judge:
        llm_judge_model = os.getenv("LLM_JUDGE_MODEL", "gpt-4")
        llm_judge_client = LLMClient(model=llm_judge_model)
        llm_judge = LLMJudge(llm_client=llm_judge_client)
        logger.info(f"Using LLM Judge model: {llm_judge_model}")
    
    # Initialize Notion client if needed
    notion_client = None
    notion_mapping_manager = None
    if not args.judge_only:
        try:
            notion_database_id = os.getenv("NOTION_DATABASE_ID")
            NOTION_API_KEY = os.getenv("NOTION_API_KEY")
            
            if not notion_database_id:
                logger.error("NOTION_DATABASE_ID not set in environment")
                sys.exit(1)
            
            if not NOTION_API_KEY:
                logger.error("NOTION_API_KEY not set in environment")
                sys.exit(1)
            
            notion_client = NotionClient(
                api_token=NOTION_API_KEY,
                database_id=notion_database_id
            )
            
            # Validate schema
            notion_client.validate_database_schema()
            logger.info("Notion schema validation passed")
            
            # Initialize mapping manager
            mapping_file = args.content_dir / "notion_mapping.json"
            notion_mapping_manager = NotionMappingManager(mapping_file)
            logger.info(f"Using mapping file: {mapping_file}")
            
        except NotionSchemaError as e:
            logger.error(f"Notion schema validation failed: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to initialize Notion client: {e}")
            sys.exit(1)
    
    # Process each content unit
    stats = {
        "total": len(content_units),
        "judge_needed": 0,
        "judge_success": 0,
        "judge_failed": 0,
        "notion_needed": 0,
        "notion_success": 0,
        "notion_failed": 0,
        "skipped": 0
    }
    
    for i, content_unit in enumerate(content_units, 1):
        logger.info(f"\n[{i}/{len(content_units)}] Processing: {content_unit.title} ({content_unit.type.value})")
        
        # Check if LLM judge evaluation needed
        existing_eval_text = load_llm_judge_evaluation_text(
            content_dir=args.content_dir,
            content_type=content_unit.type.value,
            content_id=content_unit.id,
        )
        needs_evaluation = (
            not args.skip_judge and
            (args.force_judge or existing_eval_text is None)
        )
        if existing_eval_text is not None and not args.force_judge:
            logger.info("  • Evaluation already exists (skipping LLM judge)")
            needs_evaluation = False

        eval_text: str | None = existing_eval_text

        if needs_evaluation:
            stats["judge_needed"] += 1
            
            if args.dry_run:
                logger.info(f"  [DRY RUN] Would evaluate with LLM judge")
            else:
                try:
                    logger.info(f"  Running LLM judge evaluation...")
                    
                    # Format segments as text
                    if content_unit.type.value == "conversation":
                        text = "\n".join([
                            f"{seg.speaker}: {seg.text}"
                            for seg in content_unit.segments
                        ])
                    else:  # story
                        text = "\n".join([seg.text for seg in content_unit.segments])
                    
                    evaluation = llm_judge.evaluate_conversation(
                        content_id=content_unit.id,
                        text=text,
                        language=args.language,
                        level=args.level,
                        content_type=content_unit.type.value
                    )
                    
                    eval_text = evaluation.to_readable_text()
                    save_llm_judge_evaluation_text(
                        evaluation=evaluation,
                        content_dir=args.content_dir,
                        content_type=content_unit.type.value,
                    )
                    
                    logger.info(
                        f"  ✓ Evaluation complete: avg_score={evaluation.average_score():.1f}/10, "
                        f"recommendation={evaluation.overall_recommendation}"
                    )
                    stats["judge_success"] += 1
                    
                except Exception as e:
                    logger.error(f"  ✗ LLM judge evaluation failed: {e}")
                    stats["judge_failed"] += 1
                    continue  # Skip Notion push if evaluation failed
        else:
            if existing_eval_text:
                logger.info("  • Evaluation already exists (llm_judge text file)")
            else:
                logger.info("  • Skipping evaluation (--skip-judge)")
        
        # Check if Notion push needed
        if not args.judge_only and notion_client:
            stats["notion_needed"] += 1
            
            if args.dry_run:
                logger.info(f"  [DRY RUN] Would push to Notion")
            else:
                try:
                    logger.info(f"  Pushing to Notion...")
                    
                    page_id = notion_client.push_conversation(
                        content_id=content_unit.id,
                        content_type=content_unit.type.value,
                        title=content_unit.title,
                        description=content_unit.description or "",
                        topic=", ".join(content_unit.topic_ids) if content_unit.topic_ids else "",
                        scenario=", ".join(content_unit.scenario_ids) if content_unit.scenario_ids else "",
                        segments=[seg.model_dump() for seg in content_unit.segments],
                        llm_comment_text=eval_text or "",
                        language=args.language,
                        level=args.level,
                        force=args.force
                    )
                    
                    logger.info(f"  ✓ Pushed to Notion: {page_id}")
                    stats["notion_success"] += 1
                    
                except Exception as e:
                    logger.error(f"  ✗ Notion push failed: {e}")
                    stats["notion_failed"] += 1
        else:
            if args.judge_only:
                logger.info(f"  • Skipping Notion push (--judge-only)")
    
    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total content units: {stats['total']}")
    
    if not args.skip_judge:
        logger.info(f"\nLLM Judge:")
        logger.info(f"  Needed evaluation: {stats['judge_needed']}")
        logger.info(f"  Success: {stats['judge_success']}")
        logger.info(f"  Failed: {stats['judge_failed']}")
    
    if not args.judge_only:
        logger.info(f"\nNotion Push:")
        logger.info(f"  Needed push: {stats['notion_needed']}")
        logger.info(f"  Success: {stats['notion_success']}")
        logger.info(f"  Failed: {stats['notion_failed']}")
    
    if stats["judge_failed"] > 0 or stats["notion_failed"] > 0:
        logger.warning("\n⚠ Some operations failed. Check logs above for details.")
        sys.exit(1)
    else:
        logger.info("\n✓ All operations completed successfully!")


if __name__ == "__main__":
    main()
