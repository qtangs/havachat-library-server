"""Tests for source file parsers."""

import pytest
from pathlib import Path

from havachat.parsers.source_parsers import (
    parse_mandarin_vocab_tsv,
    parse_japanese_vocab_json,
    parse_french_vocab_tsv,
    parse_mandarin_grammar_csv,
    load_source_file,
)


class TestMandarinVocabParser:
    """Tests for Mandarin vocabulary TSV parser."""
    
    def test_parse_mandarin_vocab_tsv(self):
        """Test parsing Mandarin vocab TSV file."""
        fixture_path = Path("tests/fixtures/mandarin_vocab_sample.tsv")
        items = parse_mandarin_vocab_tsv(fixture_path)
        
        assert len(items) > 0
        assert all("target_item" in item for item in items)
        assert all("pos" in item for item in items)
        
        # Check first item
        first_item = items[0]
        assert first_item["target_item"] == "唱"
        assert first_item["pos"] == "verb"
        assert first_item["source_row"] == 1
    
    def test_sense_marker_handling(self):
        """Test that sense markers are properly cleaned and extracted."""
        fixture_path = Path("tests/fixtures/mandarin_vocab_sample.tsv")
        items = parse_mandarin_vocab_tsv(fixture_path)
        
        # Find item with sense marker (e.g., "点1")
        sense_items = [item for item in items if item.get("sense_marker")]
        assert len(sense_items) > 0
        
        # Check that target_item is clean and sense_marker is extracted
        for item in sense_items:
            assert item["sense_marker"].isdigit()
            assert not item["target_item"][-1].isdigit()
    
    def test_chinese_pos_translation(self):
        """Test that Chinese POS tags are translated to English."""
        fixture_path = Path("tests/fixtures/mandarin_vocab_sample.tsv")
        items = parse_mandarin_vocab_tsv(fixture_path)
        
        # Should have English POS tags
        pos_tags = [item["pos"] for item in items if item.get("pos")]
        assert all(pos in ["verb", "noun", "measure word", "number", "interjection", 
                          "preposition", "conjunction", "preposition/conjunction",
                          "measure word/noun"] for pos in pos_tags if pos)


class TestJapaneseVocabParser:
    """Tests for Japanese vocabulary JSON parser."""
    
    def test_parse_japanese_vocab_json(self):
        """Test parsing Japanese vocab JSON file."""
        fixture_path = Path("tests/fixtures/japanese_vocab_sample.json")
        items = parse_japanese_vocab_json(fixture_path)
        
        assert len(items) > 0
        assert all("target_item" in item for item in items)
        assert all("romanization" in item for item in items)
        assert all("level_min" in item for item in items)
        
        # Check first item
        first_item = items[0]
        assert first_item["target_item"] == "学校"
        assert first_item["meaning"] == "school"
        assert first_item["furigana"] == "がっこう"
        assert first_item["level_min"] == "N5"
    
    def test_romaji_auto_generation(self):
        """Test that romaji is auto-generated if missing."""
        fixture_path = Path("tests/fixtures/japanese_vocab_sample.json")
        items = parse_japanese_vocab_json(fixture_path)
        
        # All items should have romanization
        assert all(item.get("romanization") for item in items)
    
    def test_level_normalization(self):
        """Test that JLPT levels are normalized."""
        fixture_path = Path("tests/fixtures/japanese_vocab_sample.json")
        items = parse_japanese_vocab_json(fixture_path)
        
        # All levels should be in N5, N4, N3, N2, N1 format
        levels = [item["level_min"] for item in items]
        assert all(level.startswith("N") and level[1].isdigit() for level in levels)


class TestFrenchVocabParser:
    """Tests for French vocabulary TSV parser."""
    
    def test_parse_french_vocab_tsv(self):
        """Test parsing French vocab TSV file."""
        fixture_path = Path("tests/fixtures/french_vocab_sample.tsv")
        items = parse_french_vocab_tsv(fixture_path)
        
        assert len(items) > 0
        assert all("target_item" in item for item in items)
        assert all("context_category" in item for item in items)
        
        # Check first item
        first_item = items[0]
        assert first_item["target_item"] == "Bonjour. / Bonsoir."
        assert first_item["context_category"] == "Saluer"
        assert first_item["source_row"] == 1
    
    def test_functional_categories(self):
        """Test that functional categories are preserved."""
        fixture_path = Path("tests/fixtures/french_vocab_sample.tsv")
        items = parse_french_vocab_tsv(fixture_path)
        
        categories = set(item["context_category"] for item in items if item.get("context_category"))
        assert "Saluer" in categories
        assert "Prendre congé" in categories
        assert "Exprimer ses goûts" in categories


class TestMandarinGrammarParser:
    """Tests for Mandarin grammar CSV parser."""
    
    def test_parse_mandarin_grammar_csv(self):
        """Test parsing Mandarin grammar CSV file."""
        fixture_path = Path("tests/fixtures/mandarin_grammar_sample.csv")
        items = parse_mandarin_grammar_csv(fixture_path)
        
        assert len(items) > 0
        assert all("pattern" in item for item in items)
        assert all("type" in item for item in items)
        assert all("category_name" in item for item in items)
        
        # Check that items are split (e.g., "会、能" -> ["会", "能"])
        patterns = [item["pattern"] for item in items]
        assert "会" in patterns
        assert "能" in patterns
    
    def test_pattern_splitting(self):
        """Test that multi-item patterns are split into individual items."""
        fixture_path = Path("tests/fixtures/mandarin_grammar_sample.csv")
        items = parse_mandarin_grammar_csv(fixture_path)
        
        # Find items from the same original_content
        grouped = {}
        for item in items:
            content = item["original_content"]
            if content not in grouped:
                grouped[content] = []
            grouped[content].append(item["pattern"])
        
        # Check that patterns with 、 are split
        for content, patterns in grouped.items():
            if "、" in content:
                # Should have multiple patterns
                assert len(patterns) > 1
                # Each pattern should be a single item
                assert all("、" not in p for p in patterns)
    
    def test_pattern_cleaning(self):
        """Test that patterns are cleaned of numbers and prefixes."""
        fixture_path = Path("tests/fixtures/mandarin_grammar_sample.csv")
        items = parse_mandarin_grammar_csv(fixture_path)
        
        # Patterns should not have trailing numbers
        patterns = [item["pattern"] for item in items]
        assert all(not p.strip()[-1].isdigit() for p in patterns if p.strip())


class TestGenericLoader:
    """Tests for generic load_source_file function."""
    
    def test_load_mandarin_vocab(self):
        """Test loading Mandarin vocab via generic loader."""
        fixture_path = Path("tests/fixtures/mandarin_vocab_sample.tsv")
        items = load_source_file(fixture_path, "zh", "vocab")
        assert len(items) > 0
    
    def test_load_japanese_vocab(self):
        """Test loading Japanese vocab via generic loader."""
        fixture_path = Path("tests/fixtures/japanese_vocab_sample.json")
        items = load_source_file(fixture_path, "ja", "vocab")
        assert len(items) > 0
    
    def test_load_french_vocab(self):
        """Test loading French vocab via generic loader."""
        fixture_path = Path("tests/fixtures/french_vocab_sample.tsv")
        items = load_source_file(fixture_path, "fr", "vocab")
        assert len(items) > 0
    
    def test_load_mandarin_grammar(self):
        """Test loading Mandarin grammar via generic loader."""
        fixture_path = Path("tests/fixtures/mandarin_grammar_sample.csv")
        items = load_source_file(fixture_path, "zh", "grammar")
        assert len(items) > 0
    
    def test_unsupported_combination(self):
        """Test that unsupported language/content_type raises ValueError."""
        fixture_path = Path("tests/fixtures/mandarin_vocab_sample.tsv")
        with pytest.raises(ValueError, match="No parser available"):
            load_source_file(fixture_path, "de", "vocab")  # German not supported
    
    def test_file_not_found(self):
        """Test that missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_source_file(Path("nonexistent.tsv"), "zh", "vocab")
