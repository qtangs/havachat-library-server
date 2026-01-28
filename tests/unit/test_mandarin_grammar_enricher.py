"""Unit tests for Mandarin grammar enricher."""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.pipeline.enrichers.grammar.mandarin import MandarinGrammarEnricher, ChineseGrammarEnriched
from src.pipeline.validators.schema import Category, LevelSystem


@pytest.fixture
def sample_csv_path(tmp_path):
    """Create a temporary CSV file for testing."""
    csv_content = """类别,类别名称,细目,语法内容
词类,动词,能愿动词,会、能
词类,代词,人称代词,我、你、他
语素,前缀,,小-、第-
"""
    csv_file = tmp_path / "test_grammar.csv"
    csv_file.write_text(csv_content, encoding="utf-8")
    return csv_file


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_azure_translator():
    """Create a mock Azure translator."""
    translator = MagicMock()
    translator.translate.return_value = "I can speak Chinese."
    return translator


def test_parse_source_valid_csv(sample_csv_path):
    """Test parsing valid CSV file."""
    enricher = MandarinGrammarEnricher(llm_client=None)
    items = enricher.parse_source(sample_csv_path)
    
    # Should split multi-item patterns
    assert len(items) == 7  # 会、能 (2) + 我、你、他 (3) + 小-、第- (2)
    
    # Check first item
    assert items[0]["pattern"] == "会"
    assert items[0]["type"] == "词类"
    assert items[0]["category_name"] == "动词"
    assert items[0]["detail"] == "能愿动词"
    
    # Check second item
    assert items[1]["pattern"] == "能"
    assert items[1]["type"] == "词类"
    
    # Check pronoun items
    assert items[2]["pattern"] == "我"
    assert items[3]["pattern"] == "你"
    assert items[4]["pattern"] == "他"


def test_parse_source_file_not_found():
    """Test parsing non-existent file."""
    enricher = MandarinGrammarEnricher(llm_client=None)
    
    with pytest.raises(FileNotFoundError):
        enricher.parse_source("nonexistent.csv")


def test_parse_source_invalid_columns(tmp_path):
    """Test parsing CSV with invalid columns."""
    csv_content = """wrong,columns,here
value1,value2,value3
"""
    csv_file = tmp_path / "invalid.csv"
    csv_file.write_text(csv_content, encoding="utf-8")
    
    enricher = MandarinGrammarEnricher(llm_client=None)
    
    with pytest.raises(ValueError, match="CSV must have columns"):
        enricher.parse_source(csv_file)


def test_detect_missing_fields():
    """Test detecting missing fields in grammar items."""
    enricher = MandarinGrammarEnricher(llm_client=None)
    
    # Item without definition or examples
    item = {"pattern": "会", "type": "词类"}
    missing = enricher.detect_missing_fields(item)
    assert "definition" in missing
    assert "examples" in missing
    
    # Item with definition but no examples
    item_with_def = {"pattern": "会", "definition": "can, able to"}
    missing = enricher.detect_missing_fields(item_with_def)
    assert "definition" not in missing
    assert "examples" in missing


def test_build_prompt():
    """Test building enrichment prompt."""
    enricher = MandarinGrammarEnricher(llm_client=None)
    
    item = {
        "pattern": "会",
        "type": "词类",
        "category_name": "动词",
        "detail": "能愿动词",
        "original_content": "会、能"
    }
    
    prompt = enricher.build_prompt(item, ["definition", "examples"], "zh", "HSK1")
    
    assert "会" in prompt
    assert "词类" in prompt
    assert "动词" in prompt
    assert "能愿动词" in prompt
    assert "HSK1" in prompt
    assert "CRITICAL" in prompt
    assert "mega-item" in prompt.lower()


def test_validate_output_valid():
    """Test validating a valid enriched item."""
    enricher = MandarinGrammarEnricher(llm_client=None)
    
    # Create mock enriched item
    from src.pipeline.validators.schema import LearningItem, Example
    from datetime import datetime, UTC
    
    enriched = LearningItem(
        id="test-id",
        language="zh",
        category=Category.GRAMMAR,
        target_item="会",
        definition="Modal verb expressing ability",
        examples=[
            Example(text="我会说中文。", translation="I can speak Chinese."),
            Example(text="他会游泳。", translation="He can swim."),
            Example(text="你会开车吗？", translation="Can you drive?"),
        ],
        romanization="huì",
        level_system=LevelSystem.HSK,
        level_min="HSK1",
        level_max="HSK1",
        created_at=datetime.now(UTC),
    )
    
    source_item = {"pattern": "会"}
    
    is_valid, error = enricher.validate_output(enriched, source_item)
    assert is_valid is True
    assert error is None


def test_validate_output_wrong_category():
    """Test validation fails for wrong category."""
    enricher = MandarinGrammarEnricher(llm_client=None)
    
    from src.pipeline.validators.schema import LearningItem, Example
    from datetime import datetime, UTC
    
    enriched = LearningItem(
        id="test-id",
        language="zh",
        category=Category.VOCAB,  # Wrong category
        target_item="会",
        definition="Modal verb expressing ability",
        examples=[
            Example(text="我会说中文。", translation="I can speak Chinese."),
            Example(text="他会游泳。", translation="He can swim."),
            Example(text="你会开车吗？", translation="Can you drive?"),
        ],
        romanization="huì",
        level_system=LevelSystem.HSK,
        level_min="HSK1",
        level_max="HSK1",
        created_at=datetime.now(UTC),
    )
    
    source_item = {"pattern": "会"}
    
    is_valid, error = enricher.validate_output(enriched, source_item)
    assert is_valid is False
    assert "Category must be 'grammar'" in error


def test_validate_output_mismatched_target():
    """Test validation fails for mismatched target_item."""
    enricher = MandarinGrammarEnricher(llm_client=None)
    
    from src.pipeline.validators.schema import LearningItem, Example
    from datetime import datetime, UTC
    
    enriched = LearningItem(
        id="test-id",
        language="zh",
        category=Category.GRAMMAR,
        target_item="能",  # Doesn't match source
        definition="Modal verb expressing ability",
        examples=[
            Example(text="我会说中文。", translation="I can speak Chinese."),
            Example(text="他会游泳。", translation="He can swim."),
            Example(text="你会开车吗？", translation="Can you drive?"),
        ],
        romanization="néng",
        level_system=LevelSystem.HSK,
        level_min="HSK1",
        level_max="HSK1",
        created_at=datetime.now(UTC),
    )
    
    source_item = {"pattern": "会"}
    
    is_valid, error = enricher.validate_output(enriched, source_item)
    assert is_valid is False
    assert "doesn't match pattern" in error


def test_validate_output_insufficient_examples():
    """Test validation fails for insufficient examples."""
    enricher = MandarinGrammarEnricher(llm_client=None)
    
    from src.pipeline.validators.schema import LearningItem, Example
    from datetime import datetime, UTC
    
    # This test verifies our validate_output logic
    # The Pydantic model won't allow < 3 examples, so we test with exactly 2
    enriched = LearningItem(
        id="test-id",
        language="zh",
        category=Category.GRAMMAR,
        target_item="会",
        definition="Modal verb expressing ability",
        examples=[
            Example(text="我会说中文。", translation="I can speak Chinese."),
            Example(text="他会游泳。", translation="He can swim."),
            Example(text="你会开车吗？", translation="Can you drive?"),
        ],
        romanization="huì",
        level_system=LevelSystem.HSK,
        level_min="HSK1",
        level_max="HSK1",
        created_at=datetime.now(UTC),
    )
    
    # Manually reduce examples to simulate insufficient examples
    enriched.examples = enriched.examples[:2]
    
    source_item = {"pattern": "会"}
    
    is_valid, error = enricher.validate_output(enriched, source_item)
    assert is_valid is False
    assert "at least 3 examples" in error


def test_validate_output_no_chinese_characters():
    """Test validation fails if examples don't contain Chinese."""
    enricher = MandarinGrammarEnricher(llm_client=None)
    
    from src.pipeline.validators.schema import LearningItem, Example
    from datetime import datetime, UTC
    
    enriched = LearningItem(
        id="test-id",
        language="zh",
        category=Category.GRAMMAR,
        target_item="会",
        definition="Modal verb expressing ability",
        examples=[
            Example(text="I can speak.", translation="I can speak."),
            Example(text="He can swim.", translation="He can swim."),
            Example(text="Can you drive?", translation="Can you drive?"),
        ],
        romanization="huì",
        level_system=LevelSystem.HSK,
        level_min="HSK1",
        level_max="HSK1",
        created_at=datetime.now(UTC),
    )
    
    source_item = {"pattern": "会"}
    
    is_valid, error = enricher.validate_output(enriched, source_item)
    assert is_valid is False
    assert "doesn't contain Chinese characters" in error


def test_system_prompt():
    """Test system prompt property."""
    enricher = MandarinGrammarEnricher(llm_client=None)
    prompt = enricher.system_prompt
    
    assert "Mandarin Chinese grammar teacher" in prompt
    assert "NO PINYIN" in prompt
    assert "CHINESE ONLY EXAMPLES" in prompt
    assert "mega-item" in prompt.lower()


@patch('src.pipeline.enrichers.grammar.mandarin.AzureTranslationHelper')
def test_enricher_initialization_with_azure(mock_azure_class):
    """Test enricher initialization with Azure Translation."""
    mock_translator = MagicMock()
    mock_azure_class.return_value = mock_translator
    
    enricher = MandarinGrammarEnricher(llm_client=None)
    
    assert enricher.azure_translator is not None


@patch('src.pipeline.enrichers.grammar.mandarin.AzureTranslationHelper')
def test_enricher_initialization_without_azure(mock_azure_class):
    """Test enricher initialization when Azure Translation fails."""
    mock_azure_class.side_effect = ValueError("No API key")
    
    enricher = MandarinGrammarEnricher(llm_client=None)
    
    assert enricher.azure_translator is None


def test_pattern_cleaning():
    """Test that patterns are cleaned correctly."""
    enricher = MandarinGrammarEnricher(llm_client=None)
    
    csv_content = """类别,类别名称,细目,语法内容
词类,副词,否定副词,不、没（有）、不要
词类,量词,名量词,（1）专用名量词：本、个
"""
    
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
        f.write(csv_content)
        temp_path = f.name
    
    try:
        items = enricher.parse_source(temp_path)
        
        # Check patterns are cleaned
        patterns = [item["pattern"] for item in items]
        assert "不" in patterns
        assert "没（有）" in patterns
        assert "不要" in patterns
        assert "本" in patterns
        assert "个" in patterns
        
        # Should not have prefixes like "（1）专用名量词："
        assert all("（1）" not in p for p in patterns)
        
    finally:
        Path(temp_path).unlink()


def test_enrich_dry_run():
    """Test enrichment in dry-run mode."""
    enricher = MandarinGrammarEnricher(llm_client=None)
    
    item = {
        "pattern": "会",
        "type": "词类",
        "category_name": "动词",
        "detail": "能愿动词",
        "original_content": "会、能",
        "language": "zh",
        "level": "HSK1",
        "level_system": LevelSystem.HSK,
    }
    
    result = enricher.enrich_item(item)
    
    # Should return None in dry-run mode
    assert result is None
