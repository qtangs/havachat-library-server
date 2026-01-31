# Setting Up the Notion Database

## Problem
Your Notion database currently has no properties/columns defined. The database exists but is completely empty.

## Solution Options

### Option 1: Manual Setup in Notion (Recommended)

1. Go to your Notion database: https://www.notion.so/2f9dd30aa93a80a99e11dce4c26c3863

2. Add the following columns with exact names and types:

| Column Name | Type | Configuration |
|------------|------|---------------|
| **Type** | Select | Options: `conversation`, `story` |
| **Title** | Title | (Default title property) |
| **Description** | Text | (Rich text) |
| **Topic** | Text | (Rich text) |
| **Scenario** | Text | (Rich text) |
| **Script** | Text | (Rich text) |
| **Translation** | Text | (Rich text) |
| **Audio** | URL | (URL type) |
| **LLM Comment** | Text | (Rich text) |
| **Human Comment** | Text | (Rich text) |
| **Status** | Select | Options: `Not started`, `Ready for Review`, `Reviewing`, `Ready for Audio`, `Rejected`, `OK` |

### Option 2: Create New Database from Template

If you want to start fresh:

1. Create a new database in Notion
2. Set up the columns as described above
3. Share the database with your integration
4. Copy the new database ID (the hex part after the last `/` in the URL)
5. Update `NOTION_DATABASE_ID` in your `.env` file

## Verification

After setting up the columns, run the debug script to verify:

```bash
PYTHONPATH=src uv run python debug_notion_schema.py
```

You should see all columns marked with ✓ checkmarks.

## Current Database Info

- **Database ID**: `2f9dd30aa93a80a99e11dce4c26c3863`
- **Database Name**: "Chinese Content"
- **Status**: Empty (no properties defined)
- **Created**: 2026-01-31
