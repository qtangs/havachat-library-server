"""Integration test for end-to-end grammar enrichment."""

import json
from pathlib import Path

import pytest

from havachat.enrichers.grammar.chinese import ChineseGrammarEnricher
from havachat.validators.schema import LevelSystem


@pytest.fixture
def sample_grammar_csv(tmp_path):
    """Create a sample grammar CSV file."""
    csv_content = """类别,类别名称,细目,语法内容
词类,动词,能愿动词,会、能
词类,代词,人称代词,我、你
词类,副词,否定副词,不
"""
    csv_file = tmp_path / "grammar_sample.csv"
    csv_file.write_text(csv_content, encoding="utf-8")
    return csv_file


@pytest.fixture
def output_dir(tmp_path):
    """Create output directory."""
    output = tmp_path / "output"
    output.mkdir()
    return output


def test_end_to_end_grammar_enrichment_dry_run(sample_grammar_csv, output_dir):
    """Test end-to-end grammar enrichment in dry-run mode."""
    # Initialize enricher without LLM client (dry-run)
    enricher = ChineseGrammarEnricher(llm_client=None)
    
    # Parse source
    items = enricher.parse_source(sample_grammar_csv)
    
    # Should split patterns: 会、能 (2) + 我、你 (2) + 不 (1) = 5 items
    assert len(items) == 5
    
    # Check parsing
    patterns = [item["pattern"] for item in items]
    assert "会" in patterns
    assert "能" in patterns
    assert "我" in patterns
    assert "你" in patterns
    assert "不" in patterns
    
    # Check metadata
    for item in items:
        assert "type" in item
        assert "category_name" in item
        assert "pattern" in item
    
    # Verify detect_missing_fields works
    missing = enricher.detect_missing_fields(items[0])
    assert "definition" in missing
    assert "examples" in missing
    
    # Verify build_prompt works
    prompt = enricher.build_prompt(items[0], missing, "zh", "HSK1")
    assert len(prompt) > 0
    assert items[0]["pattern"] in prompt
    assert "HSK1" in prompt


def test_grammar_csv_format_variations(tmp_path):
    """Test parsing CSV with various format variations."""
    csv_content = """类别,类别名称,细目,语法内容
词类,动词,能愿动词,会 1 、能 2
语素,前缀,,小-、第-
词类,量词,名量词,（1）专用名量词：本、个、家
"""
    csv_file = tmp_path / "variations.csv"
    csv_file.write_text(csv_content, encoding="utf-8")
    
    enricher = ChineseGrammarEnricher(llm_client=None)
    items = enricher.parse_source(csv_file)
    
    # Check pattern cleaning
    patterns = [item["pattern"] for item in items]
    
    # Should clean trailing numbers
    assert "会" in patterns or "会 1" in patterns
    
    # Should clean prefix markers
    assert "本" in patterns
    assert "个" in patterns
    assert "家" in patterns
    
    # Should not have the full prefix text
    assert not any("（1）专用名量词：" in p for p in patterns)


def test_granularity_validation(tmp_path):
    """Test that parsing splits multi-item patterns correctly."""
    csv_content = """类别,类别名称,细目,语法内容
词类,代词,人称代词,我、你、您、他、她、我们、你们、他们、她们
"""
    csv_file = tmp_path / "multi_item.csv"
    csv_file.write_text(csv_content, encoding="utf-8")
    
    enricher = ChineseGrammarEnricher(llm_client=None)
    items = enricher.parse_source(csv_file)
    
    # Should split into 9 individual items
    assert len(items) == 9
    
    # Each item should be a single character/word
    patterns = [item["pattern"] for item in items]
    assert "我" in patterns
    assert "你" in patterns
    assert "您" in patterns
    assert "他" in patterns
    assert "她" in patterns
    assert "我们" in patterns
    assert "你们" in patterns
    assert "他们" in patterns
    assert "她们" in patterns


def test_empty_detail_field(tmp_path):
    """Test parsing when detail field is empty."""
    csv_content = """类别,类别名称,细目,语法内容
语素,前缀,,小-、第-
"""
    csv_file = tmp_path / "empty_detail.csv"
    csv_file.write_text(csv_content, encoding="utf-8")
    
    enricher = ChineseGrammarEnricher(llm_client=None)
    items = enricher.parse_source(csv_file)
    
    assert len(items) == 2
    
    # Detail should be empty string
    for item in items:
        assert item["detail"] == ""


@pytest.mark.skipif(
    not Path(".env").exists(),
    reason="Requires .env file with LLM API credentials"
)
def test_live_enrichment_single_item(tmp_path):
    """Test live enrichment with LLM (requires API key).
    
    This test is skipped by default. Run with:
    pytest -v -m "not skipif" tests/integration/test_end_to_end_grammar.py
    """
    from havachat.utils.llm_client import LLMClient
    
    # Create simple CSV
    csv_content = """类别,类别名称,细目,语法内容
词类,动词,能愿动词,会
"""
    csv_file = tmp_path / "single.csv"
    csv_file.write_text(csv_content, encoding="utf-8")
    
    # Initialize with real LLM client
    llm_client = LLMClient()
    enricher = ChineseGrammarEnricher(
        llm_client=llm_client,
        manual_review_dir=tmp_path / "manual_review"
    )
    
    # Parse and enrich
    items = enricher.parse_source(csv_file)
    assert len(items) == 1
    
    # Add metadata
    items[0]["language"] = "zh"
    items[0]["level"] = "HSK1"
    items[0]["level_system"] = LevelSystem.HSK
    
    result = enricher.enrich_item(items[0])
    
    # Validate result
    assert result is not None
    assert result.category.value == "grammar"
    assert result.target_item == "会"
    assert len(result.definition) > 0
    assert len(result.examples) >= 3
    
    # Check examples are in Chinese
    for example in result.examples:
        assert any('\u4e00' <= char <= '\u9fff' for char in example.text)
    
    # Check romanization was added
    assert result.romanization is not None
    assert len(result.romanization) > 0
    
    print(f"\n✅ Successfully enriched: {result.target_item}")
    print(f"   Definition: {result.definition}")
    print(f"   Examples: {len(result.examples)}")
    print(f"   Romanization: {result.romanization}")
