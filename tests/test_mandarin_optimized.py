"""Test the optimized Mandarin enricher with cost reduction strategy."""

import json
import os
from pathlib import Path

from src.pipeline.enrichers.vocab.mandarin_optimized import MandarinVocabEnricherOptimized
from src.pipeline.utils.llm_client import LLMClient


def test_optimized_enricher():
    """Test optimized Mandarin enricher with sample data."""
    
    # Check for required environment variables
    required_vars = [
        "OPENAI_API_KEY",
        "AZURE_TEXT_TRANSLATION_APIKEY",
        "AZURE_TEXT_TRANSLATION_REGION"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(f"Missing environment variables: {', '.join(missing_vars)}")
        print("Please set these variables before running the test.")
        return
    
    # Initialize clients
    llm_client = LLMClient()
    enricher = MandarinVocabEnricherOptimized(llm_client=llm_client)
    
    # Test item
    test_item = {
        "target_item": "爱",
        "pos": "verb",
        "level_min": "HSK1",
        "level_max": "HSK1",
    }
    
    print("=" * 80)
    print("TESTING OPTIMIZED MANDARIN ENRICHER")
    print("=" * 80)
    print(f"\nTest item: {test_item['target_item']} ({test_item['pos']})")
    print(f"Level: {test_item['level_min']}")
    print("\nEnriching...")
    
    # Enrich the item
    result = enricher.enrich_item(test_item)
    
    if result:
        print("\n✓ Enrichment successful!")
        print("\n" + "-" * 80)
        print("RESULT")
        print("-" * 80)
        
        # Display the result
        result_dict = result.model_dump()
        print(json.dumps(result_dict, indent=2, ensure_ascii=False))
        
        print("\n" + "-" * 80)
        print("KEY OBSERVATIONS")
        print("-" * 80)
        
        print(f"Target item: {result.target_item}")
        print(f"Romanization (tone marks): {result.romanization}")
        print(f"Aliases: {result.aliases}")
        if result.aliases:
            print(f"  - Traditional Chinese: {result.aliases[0] if len(result.aliases) > 0 else 'N/A'}")
            print(f"  - Numeric pinyin: {result.aliases[1] if len(result.aliases) > 1 else 'N/A'}")
        
        print(f"\nExamples ({len(result.examples)} total):")
        for i, example in enumerate(result.examples, 1):
            print(f"  {i}. {example}")
        
        # Get translation usage
        translation_usage = enricher.get_translation_usage()
        if translation_usage:
            print("\n" + "-" * 80)
            print("AZURE TRANSLATION USAGE")
            print("-" * 80)
            print(f"Total characters: {translation_usage['total_characters']:,}")
            print(f"Monthly limit: {translation_usage['monthly_limit']:,}")
            print(f"Remaining: {translation_usage['remaining']:,}")
            print(f"Usage: {translation_usage['usage_percent']:.2f}%")
        
        # Get LLM token usage
        llm_usage = llm_client.get_usage_summary()
        print("\n" + "-" * 80)
        print("LLM TOKEN USAGE")
        print("-" * 80)
        print(f"Model: {llm_usage['model']}")
        print(f"Prompt tokens: {llm_usage['prompt_tokens']:,}")
        print(f"Completion tokens: {llm_usage['completion_tokens']:,}")
        print(f"Total tokens: {llm_usage['total_tokens']:,}")
        print(f"Cached tokens: {llm_usage['cached_tokens']:,}")
        print(f"Cache hit rate: {llm_usage['cache_hit_rate']}")
        print(f"Estimated cost: ${llm_usage['estimated_cost']:.6f}")
        
        print("\n" + "=" * 80)
        print("TEST COMPLETED SUCCESSFULLY")
        print("=" * 80)
        
    else:
        print("\n✗ Enrichment failed!")
        return


if __name__ == "__main__":
    test_optimized_enricher()
