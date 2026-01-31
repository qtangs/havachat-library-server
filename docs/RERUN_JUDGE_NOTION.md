# Rerun LLM Judge + Notion Script

This script allows you to reprocess existing content files that either:
1. Don't have LLM judge evaluations yet (due to errors during generation)
2. Need to be synced to Notion

## Usage

### Basic Usage - Rerun Both Judge and Notion

```bash
PYTHONPATH=src uv run python -m havachat.cli.rerun_judge_notion \
    --content-dir output/content/food/ \
    --language zh --level HSK1
```

### Skip LLM Judge (Only Push to Notion)

If content already has evaluations and you just want to sync to Notion:

```bash
PYTHONPATH=src uv run python -m havachat.cli.rerun_judge_notion \
    --content-dir output/content/food/ \
    --language zh --level HSK1 \
    --skip-judge
```

### Judge Only (Don't Push to Notion)

If you only want to evaluate content without pushing to Notion:

```bash
PYTHONPATH=src uv run python -m havachat.cli.rerun_judge_notion \
    --content-dir output/content/food/ \
    --language zh --level HSK1 \
    --judge-only
```

### Force Re-evaluation

To re-evaluate content that already has evaluations:

```bash
PYTHONPATH=src uv run python -m havachat.cli.rerun_judge_notion \
    --content-dir output/content/food/ \
    --language zh --level HSK1 \
    --force-judge
```

### Dry Run

To see what would be processed without actually doing it:

```bash
PYTHONPATH=src uv run python -m havachat.cli.rerun_judge_notion \
    --content-dir output/content/food/ \
    --language zh --level HSK1 \
    --dry-run
```

## Arguments

- `--content-dir`: Directory containing content JSON files (with `conversation/` and `story/` subdirs)
- `--language`: ISO 639-1 code (zh, ja, fr, en, es)
- `--level`: Target proficiency level (e.g., HSK1, A1, N5)
- `--skip-judge`: Skip LLM judge evaluation (only push to Notion)
- `--judge-only`: Only run LLM judge (don't push to Notion)
- `--force-judge`: Re-evaluate even if evaluation already exists
- `--dry-run`: Print what would be done without processing

## How It Works

1. **Loads all content files** from `conversation/` and `story/` subdirectories
2. **For each content unit:**
   - Checks if LLM judge evaluation is needed (missing or `--force-judge`)
   - If needed, runs evaluation and saves updated content file
   - If Notion push is enabled, pushes to Notion and updates mapping file
3. **Prints summary** of operations performed

## Expected Directory Structure

```
content-dir/
├── conversation/
│   ├── conversation_<uuid>.json
│   └── ...
├── story/
│   ├── story_<uuid>.json
│   └── ...
└── notion_mapping.json (created/updated by script)
```

## Configuration

The script uses these environment variables:

- `LLM_JUDGE_MODEL`: Model to use for LLM judge (default: `gpt-4`)
- `NOTION_DATABASE_ID`: Required for Notion push
- `NOTION_API_KEY`: Required for Notion push

See [.env.template](.env.template) for complete configuration options.

## Error Handling

- If LLM judge evaluation fails for a content unit, it skips Notion push for that unit
- Failed operations are reported in the summary
- Script exits with code 1 if any operations fail

## Output

The script provides:
- Progress updates for each content unit
- Evaluation scores and recommendations
- Notion page IDs for successful pushes
- Summary statistics at the end

Example output:

```
Starting rerun of LLM Judge + Notion sync:
  Content directory: output/content/food/
  Language: zh
  Level: HSK1
  Skip judge: False
  Judge only: False
  Force re-evaluation: False
Using LLM Judge model: claude-sonnet-4-5
Loaded 15 content units from output/content/food/

[1/15] Processing: At the Supermarket (conversation)
  Running LLM judge evaluation...
  ✓ Evaluation complete: avg_score=8.0/10, recommendation=proceed
  Pushing to Notion...
  ✓ Pushed to Notion: 123e4567-e89b-12d3-a456-426614174000

...

================================================================================
SUMMARY
================================================================================
Total content units: 15

LLM Judge:
  Needed evaluation: 5
  Success: 5
  Failed: 0

Notion Push:
  Needed push: 15
  Success: 15
  Failed: 0

✓ All operations completed successfully!
```
