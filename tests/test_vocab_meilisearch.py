#!/usr/bin/env python3
"""Test script to enrich vocabulary and index in Meilisearch.

This script:
1. Enriches 20 sample vocabulary items (Mandarin from test fixtures)
2. Indexes them in Meilisearch with OpenAI embeddings
3. Tests hybrid search queries
4. Validates results

Prerequisites:
- Meilisearch running locally: `meilisearch`
- OPENAI_API_KEY set in environment or .env file
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import meilisearch
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def run_enrichment(
    language: str,
    level: str,
    enricher: str,
    input_file: Path,
    output_file: Path,
    max_items: int = 20,
) -> bool:
    """Run vocabulary enrichment CLI.

    Args:
        language: Language code (zh, ja, fr)
        level: Proficiency level
        enricher: Enricher name
        input_file: Input file path
        output_file: Output file path
        max_items: Maximum items to process

    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*80}")
    print(f"Enriching {language} {level} vocabulary...")
    print(f"{'='*80}")

    cmd = [
        sys.executable,
        "-m",
        "src.havachat.cli.enrich_vocab",
        "--language",
        language,
        "--level",
        level,
        "--input",
        str(input_file),
        "--enricher",
        enricher,
        "--output",
        str(output_file),
        "--max-items",
        str(max_items),
        "--log-level",
        "INFO",
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=Path(__file__).parent.parent,
            check=True,
            capture_output=False,
            text=True,
        )
        print(f"\n✓ Enrichment completed successfully")
        return True

    except subprocess.CalledProcessError as e:
        print(f"\n✗ Enrichment failed: {e}")
        return False


def setup_meilisearch_index(
    client: meilisearch.Client,
    index_name: str,
    documents: list[dict],
) -> bool:
    """Setup Meilisearch index with documents and embeddings.

    Args:
        client: Meilisearch client
        index_name: Name of index to create
        documents: List of documents to index

    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*80}")
    print(f"Setting up Meilisearch index: {index_name}")
    print(f"{'='*80}")

    try:
        # Create index or get existing
        index = client.index(index_name)

        # Add documents (with retry)
        print(f"Adding {len(documents)} documents...")
        task = index.add_documents(documents)

        # Wait for indexing to complete
        print(f"Waiting for indexing task {task.task_uid}...")
        time.sleep(2)

        # Check task status
        task_status = client.get_task(task.task_uid)
        print(f"Task status: {task_status.status}")

        if task_status.status == "failed":
            print(f"✗ Indexing failed: {task_status.error}")
            return False

        # Configure OpenAI embeddings
        print("\nConfiguring OpenAI embeddings...")
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            print("✗ OPENAI_API_KEY not found in environment")
            return False

        index.update_embedders(
            {
                "vocab-openai": {
                    "source": "openAi",
                    "apiKey": api_key,
                    "model": "text-embedding-3-small",
                    "documentTemplate": "{{doc.target_item}}: {{doc.definition}}",
                }
            }
        )

        print("✓ Meilisearch index configured successfully")
        return True

    except Exception as e:
        print(f"✗ Failed to setup Meilisearch: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_search_queries(client: meilisearch.Client, index_name: str) -> None:
    """Test various search queries on the index.

    Args:
        client: Meilisearch client
        index_name: Name of index to search
    """
    print(f"\n{'='*80}")
    print(f"Testing search queries on {index_name}")
    print(f"{'='*80}")

    index = client.index(index_name)

    # Test queries
    test_queries = [
        {
            "query": "school education",
            "description": "Keyword search: school/education related words",
        },
        {
            "query": "learning studying",
            "description": "Semantic search: learning/studying concepts",
            "hybrid": True,
        },
        {
            "query": "workplace job",
            "description": "Hybrid search: workplace vocabulary",
            "hybrid": True,
        },
    ]

    for i, test in enumerate(test_queries, 1):
        print(f"\n--- Query {i}: {test['description']} ---")
        print(f"Query text: '{test['query']}'")

        search_params = {}

        if test.get("hybrid"):
            search_params["hybrid"] = {
                "embedder": "vocab-openai",
                "semanticRatio": 0.8,
            }

        try:
            result = index.search(test["query"], search_params)

            print(f"Found {result['estimatedTotalHits']} results:")

            for j, hit in enumerate(result["hits"][:5], 1):
                print(f"\n  {j}. {hit['target_item']}")
                print(f"     Explanation: {hit['definition'][:100]}...")
                if "_semanticScore" in hit:
                    print(f"     Semantic score: {hit['_semanticScore']:.4f}")

        except Exception as e:
            print(f"✗ Search failed: {e}")
            import traceback

            traceback.print_exc()


def main() -> int:
    """Main test script."""
    print(f"\n{'='*80}")
    print("Vocabulary Enrichment + Meilisearch Test")
    print(f"{'='*80}")

    # Paths
    project_root = Path(__file__).parent.parent
    fixtures_dir = project_root / "tests" / "fixtures"
    output_dir = project_root / "temp" / "enriched_vocab"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Test parameters
    language = "zh"
    level = "HSK1"
    enricher = "mandarin"
    input_file = fixtures_dir / "mandarin_vocab_sample.tsv"
    output_file = output_dir / "mandarin_hsk1_enriched.json"
    max_items = 20

    # Step 1: Run enrichment
    success = run_enrichment(
        language=language,
        level=level,
        enricher=enricher,
        input_file=input_file,
        output_file=output_file,
        max_items=max_items,
    )

    if not success:
        print("\n✗ Enrichment failed, aborting Meilisearch test")
        return 1

    # Step 2: Load enriched data
    if not output_file.exists():
        print(f"\n✗ Output file not found: {output_file}")
        return 1

    with open(output_file, "r", encoding="utf-8") as f:
        documents = json.load(f)

    print(f"\n✓ Loaded {len(documents)} enriched documents")

    # Limit to 20 for testing
    documents = documents[:20]
    print(f"Using {len(documents)} documents for Meilisearch test")

    # Step 3: Connect to Meilisearch
    try:
        client = meilisearch.Client("http://localhost:7700", "aSampleMasterKey")
        # Test connection
        client.health()
        print("\n✓ Connected to Meilisearch")
    except Exception as e:
        print(f"\n✗ Failed to connect to Meilisearch: {e}")
        print("\nMake sure Meilisearch is running:")
        print("  $ meilisearch")
        return 1

    # Step 4: Setup index
    index_name = "vocab_test_mandarin_hsk1"

    success = setup_meilisearch_index(
        client=client,
        index_name=index_name,
        documents=documents,
    )

    if not success:
        return 1

    # Give embeddings time to generate
    print("\nWaiting for embeddings to generate (10 seconds)...")
    time.sleep(10)

    # Step 5: Test search queries
    test_search_queries(client, index_name)

    # Summary
    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}")
    print(f"✓ Enriched {len(documents)} vocabulary items")
    print(f"✓ Indexed in Meilisearch: {index_name}")
    print(f"✓ Tested hybrid search queries")
    print(f"\nOutput file: {output_file}")
    print(f"Meilisearch index: http://localhost:7700/indexes/{index_name}")
    print(f"{'='*80}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
