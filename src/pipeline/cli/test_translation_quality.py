"""Test translation quality using BLEU score.

This script tests different translation engines (LLM vs Azure Translation) 
against a set of difficult Chinese phrases with expected translations.

Usage:
    python -m src.pipeline.cli.test_translation_quality \
        --test-file "path/to/test_cases.md" \
        --output-report "translation_quality_report.json"

The test file should contain entries in this format:
    "text": "Chinese text",
    "translation": "Actual translation",
    "expected": "Expected translation"

Requirements:
    pip install sacrebleu
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from dotenv import load_dotenv

try:
    from sacrebleu.metrics import BLEU
except ImportError:
    print("ERROR: sacrebleu not installed. Install with: pip install sacrebleu")
    sys.exit(1)

from src.pipeline.utils.azure_translation import AzureTranslationHelper
from src.pipeline.utils.dictionary import DictionaryFactory
from src.pipeline.utils.google_translate import GoogleTranslateHelper
from src.pipeline.utils.llm_client import LLMClient
from src.pipeline.utils.translation import translate_texts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()


def parse_test_file(file_path: Path) -> List[Dict[str, str]]:
    """Parse test file and extract test cases.
    
    Expected format:
        "text": "Chinese text",
        "translation": "Current translation",
        "expected": "Expected translation"
    
    Args:
        file_path: Path to test file
    
    Returns:
        List of test case dictionaries with 'text' and 'expected' keys
    """
    test_cases = []
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Extract test cases using regex
    pattern = r'"text":\s*"([^"]+)",\s*"translation":\s*"[^"]*",\s*"expected":\s*"([^"]+)"'
    matches = re.findall(pattern, content)
    
    for chinese_text, expected_translation in matches:
        test_cases.append({
            "text": chinese_text,
            "expected": expected_translation
        })
    
    logger.info(f"Parsed {len(test_cases)} test cases from {file_path}")
    return test_cases


def calculate_bleu(hypothesis: str, reference: str) -> float:
    """Calculate BLEU score for a single translation.
    
    Args:
        hypothesis: Generated translation
        reference: Expected/reference translation
    
    Returns:
        BLEU score (0-100)
    """
    bleu = BLEU(effective_order=True)
    score = bleu.sentence_score(hypothesis, [reference])
    return score.score


def test_llm_translation(
    test_cases: List[Dict[str, str]],
    llm_client: LLMClient,
    dictionary = None
) -> Tuple[List[str], List[float], float]:
    """Test LLM translation engine.
    
    Args:
        test_cases: List of test cases with 'text' and 'expected' keys
        llm_client: LLM client for translation
        dictionary: Optional dictionary for reference translations
    
    Returns:
        Tuple of (translations, bleu_scores, average_bleu)
    """
    logger.info("Testing LLM translation...")
    
    # Extract Chinese texts
    texts = [case["text"] for case in test_cases]
    
    # Translate using LLM with dictionary reference
    translations = translate_texts(
        texts=texts,
        from_language="zh",
        llm_client=llm_client,
        use_azure=False,
        dictionary=dictionary,
    )
    
    # Calculate BLEU scores
    bleu_scores = []
    for translation, case in zip(translations, test_cases):
        score = calculate_bleu(translation, case["expected"])
        bleu_scores.append(score)
        logger.debug(f"LLM: '{case['text']}' -> '{translation}' (BLEU: {score:.2f})")
    
    avg_bleu = sum(bleu_scores) / len(bleu_scores) if bleu_scores else 0.0
    
    return translations, bleu_scores, avg_bleu


def test_azure_translation(
    test_cases: List[Dict[str, str]],
    llm_client: LLMClient,
    azure_translator: AzureTranslationHelper,
    dictionary = None
) -> Tuple[List[str], List[float], float]:
    """Test Azure Translation engine.
    
    Args:
        test_cases: List of test cases with 'text' and 'expected' keys
        llm_client: LLM client (for fallback)
        azure_translator: Azure Translation helper
        dictionary: Optional dictionary for reference translations
    
    Returns:
        Tuple of (translations, bleu_scores, average_bleu)
    """
    logger.info("Testing Azure Translation...")
    
    # Extract Chinese texts
    texts = [case["text"] for case in test_cases]
    
    # Translate using Azure with dictionary reference
    translations = translate_texts(
        texts=texts,
        from_language="zh",
        llm_client=llm_client,
        azure_translator=azure_translator,
        use_azure=True,
        dictionary=dictionary,
    )
    
    # Calculate BLEU scores
    bleu_scores = []
    for translation, case in zip(translations, test_cases):
        score = calculate_bleu(translation, case["expected"])
        bleu_scores.append(score)
        logger.debug(f"Azure: '{case['text']}' -> '{translation}' (BLEU: {score:.2f})")
    
    avg_bleu = sum(bleu_scores) / len(bleu_scores) if bleu_scores else 0.0
    
    return translations, bleu_scores, avg_bleu


def test_google_translation(
    test_cases: List[Dict[str, str]],
    llm_client: LLMClient,
    google_translator: GoogleTranslateHelper,
    dictionary = None
) -> Tuple[List[str], List[float], float]:
    """Test Google Translation engine.
    
    Args:
        test_cases: List of test cases with 'text' and 'expected' keys
        llm_client: LLM client (for fallback)
        google_translator: Google Translation helper
        dictionary: Optional dictionary for reference translations
    
    Returns:
        Tuple of (translations, bleu_scores, average_bleu)
    """
    logger.info("Testing Google Translation...")
    
    # Extract Chinese texts
    texts = [case["text"] for case in test_cases]
    
    # Translate using Google with dictionary reference
    translations = translate_texts(
        texts=texts,
        from_language="zh",
        llm_client=llm_client,
        google_translator=google_translator,
        use_google=True,
        dictionary=dictionary,
    )
    
    # Calculate BLEU scores
    bleu_scores = []
    for translation, case in zip(translations, test_cases):
        score = calculate_bleu(translation, case["expected"])
        bleu_scores.append(score)
        logger.debug(f"Google: '{case['text']}' -> '{translation}' (BLEU: {score:.2f})")
    
    avg_bleu = sum(bleu_scores) / len(bleu_scores) if bleu_scores else 0.0
    
    return translations, bleu_scores, avg_bleu


def generate_report(
    test_cases: List[Dict[str, str]],
    llm_results: Tuple[List[str], List[float], float],
    azure_results: Tuple[List[str], List[float], float],
    google_results: Tuple[List[str], List[float], float],
    output_file: Path
) -> Dict:
    """Generate translation quality report.
    
    Args:
        test_cases: Original test cases
        llm_results: LLM translation results (translations, scores, avg)
        azure_results: Azure translation results (translations, scores, avg)
        google_results: Google translation results (translations, scores, avg)
        output_file: Path to save JSON report
    
    Returns:
        Report dictionary
    """
    llm_translations, llm_scores, llm_avg = llm_results
    azure_translations, azure_scores, azure_avg = azure_results
    google_translations, google_scores, google_avg = google_results
    
    # Build detailed results
    detailed_results = []
    for i, case in enumerate(test_cases):
        detailed_results.append({
            "source": case["text"],
            "expected": case["expected"],
            "llm": {
                "translation": llm_translations[i],
                "bleu_score": round(llm_scores[i], 2)
            },
            "azure": {
                "translation": azure_translations[i],
                "bleu_score": round(azure_scores[i], 2)
            },
            "google": {
                "translation": google_translations[i],
                "bleu_score": round(google_scores[i], 2)
            }
        })
    
    # Build summary
    # Determine winner
    scores_dict = {"LLM": llm_avg, "Azure": azure_avg, "Google": google_avg}
    winner = max(scores_dict, key=scores_dict.get)
    best_score = scores_dict[winner]
    second_best_score = sorted(scores_dict.values(), reverse=True)[1]
    
    report = {
        "summary": {
            "total_test_cases": len(test_cases),
            "llm": {
                "average_bleu": round(llm_avg, 2),
                "min_bleu": round(min(llm_scores), 2) if llm_scores else 0.0,
                "max_bleu": round(max(llm_scores), 2) if llm_scores else 0.0,
            },
            "azure": {
                "average_bleu": round(azure_avg, 2),
                "min_bleu": round(min(azure_scores), 2) if azure_scores else 0.0,
                "max_bleu": round(max(azure_scores), 2) if azure_scores else 0.0,
            },
            "google": {
                "average_bleu": round(google_avg, 2),
                "min_bleu": round(min(google_scores), 2) if google_scores else 0.0,
                "max_bleu": round(max(google_scores), 2) if google_scores else 0.0,
            },
            "winner": winner,
            "improvement": round(best_score - second_best_score, 2)
        },
        "detailed_results": detailed_results
    }
    
    # Save to file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Report saved to {output_file}")
    
    return report


def print_summary(report: Dict) -> None:
    """Print summary to console.
    
    Args:
        report: Report dictionary
    """
    summary = report["summary"]
    
    print("\n" + "=" * 70)
    print("TRANSLATION QUALITY TEST RESULTS")
    print("=" * 70)
    print(f"Total test cases: {summary['total_test_cases']}")
    print()
    print("LLM Translation:")
    print(f"  Average BLEU: {summary['llm']['average_bleu']:.2f}")
    print(f"  Min BLEU:     {summary['llm']['min_bleu']:.2f}")
    print(f"  Max BLEU:     {summary['llm']['max_bleu']:.2f}")
    print()
    print("Azure Translation:")
    print(f"  Average BLEU: {summary['azure']['average_bleu']:.2f}")
    print(f"  Min BLEU:     {summary['azure']['min_bleu']:.2f}")
    print(f"  Max BLEU:     {summary['azure']['max_bleu']:.2f}")
    print()
    print("Google Translation:")
    print(f"  Average BLEU: {summary['google']['average_bleu']:.2f}")
    print(f"  Min BLEU:     {summary['google']['min_bleu']:.2f}")
    print(f"  Max BLEU:     {summary['google']['max_bleu']:.2f}")
    print()
    print(f"Winner: {summary['winner']}")
    print(f"Improvement: {summary['improvement']:.2f} BLEU points")
    print("=" * 70)
    
    # Show top 3 best and worst translations
    detailed = report["detailed_results"]
    
    print("\nTop 3 Best LLM Translations:")
    sorted_by_llm = sorted(detailed, key=lambda x: x["llm"]["bleu_score"], reverse=True)
    for i, result in enumerate(sorted_by_llm[:3], 1):
        print(f"{i}. {result['source']}")
        print(f"   LLM: {result['llm']['translation']} (BLEU: {result['llm']['bleu_score']})")
        print(f"   Expected: {result['expected']}")
        print()
    
    print("Top 3 Worst LLM Translations:")
    for i, result in enumerate(sorted_by_llm[-3:][::-1], 1):
        print(f"{i}. {result['source']}")
        print(f"   LLM: {result['llm']['translation']} (BLEU: {result['llm']['bleu_score']})")
        print(f"   Expected: {result['expected']}")
        print()


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Test translation quality using BLEU score",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python -m src.pipeline.cli.test_translation_quality \\
      --test-file "path/to/test_cases.md" \\
      --output-report "translation_quality_report.json"
        """
    )
    
    parser.add_argument(
        "--test-file",
        type=Path,
        required=True,
        help="Path to test file with Chinese phrases and expected translations"
    )
    parser.add_argument(
        "--output-report",
        type=Path,
        default=Path("translation_quality_report.json"),
        help="Path to save JSON report (default: translation_quality_report.json)"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)"
    )
    
    args = parser.parse_args()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Validate test file exists
    if not args.test_file.exists():
        logger.error(f"Test file not found: {args.test_file}")
        sys.exit(1)
    
    # Parse test cases
    test_cases = parse_test_file(args.test_file)
    
    if not test_cases:
        logger.error("No test cases found in test file")
        sys.exit(1)
    
    # Initialize translation engines
    llm_client = LLMClient()
    
    # Load dictionary for Chinese
    dictionary = DictionaryFactory.get_dictionary("zh")
    if dictionary:
        logger.info(f"Loaded CC-CEDICT dictionary ({dictionary.size()} entries) for reference")
    else:
        logger.warning("No dictionary available for Chinese, translations will not use dictionary reference")
    
    try:
        azure_translator = AzureTranslationHelper()
        has_azure = True
    except ValueError as e:
        logger.warning(f"Azure Translation not available: {e}")
        logger.warning("Skipping Azure Translation tests")
        has_azure = False
    
    try:
        google_translator = GoogleTranslateHelper()
        has_google = True
    except (ValueError, Exception) as e:
        logger.warning(f"Google Translation not available: {e}")
        logger.warning("Skipping Google Translation tests")
        has_google = False
    
    # Test LLM translation
    llm_results = test_llm_translation(test_cases, llm_client, dictionary)
    
    # Test Azure translation if available
    if has_azure:
        azure_results = test_azure_translation(test_cases, llm_client, azure_translator, dictionary)
    else:
        # Use dummy results if Azure not available
        azure_results = (
            ["[Azure not available]"] * len(test_cases),
            [0.0] * len(test_cases),
            0.0
        )
    
    # Test Google translation if available
    if has_google:
        google_results = test_google_translation(test_cases, llm_client, google_translator, dictionary)
    else:
        # Use dummy results if Google not available
        google_results = (
            ["[Google not available]"] * len(test_cases),
            [0.0] * len(test_cases),
            0.0
        )
    
    # Generate report
    report = generate_report(
        test_cases,
        llm_results,
        azure_results,
        google_results,
        args.output_report
    )
    
    # Print summary
    print_summary(report)
    
    # Token usage summary
    usage = llm_client.get_usage_summary()
    print("\nLLM Token Usage:")
    print(f"  Total tokens: {usage['total_tokens']:,}")
    print(f"  Estimated cost: ${usage['estimated_cost_usd']:.4f}")


if __name__ == "__main__":
    main()
