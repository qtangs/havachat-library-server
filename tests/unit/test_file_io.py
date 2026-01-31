"""Unit tests for file I/O functions."""

import json
import tempfile
from pathlib import Path

import pytest

from havachat.utils.file_io import (
    create_language_level_dir,
    get_language_level_path,
    list_files,
    parse_markdown_sections,
    read_csv,
    read_json,
    read_markdown,
    read_tsv,
    write_csv,
    write_json,
    write_tsv,
)


class TestJSONFunctions:
    """Test JSON read/write functions."""

    def test_write_and_read_json(self, tmp_path):
        """Test writing and reading JSON files."""
        data = {"name": "Alice", "age": 30, "languages": ["en", "fr"]}
        file_path = tmp_path / "test.json"

        # Write JSON
        write_json(data, file_path)
        assert file_path.exists()

        # Read JSON
        loaded_data = read_json(file_path)
        assert loaded_data == data

    def test_write_json_creates_directories(self, tmp_path):
        """Test that write_json creates parent directories."""
        data = {"key": "value"}
        file_path = tmp_path / "subdir1" / "subdir2" / "test.json"

        write_json(data, file_path)
        assert file_path.exists()
        assert read_json(file_path) == data

    def test_write_json_with_unicode(self, tmp_path):
        """Test writing JSON with Unicode characters."""
        data = {"chinese": "你好", "japanese": "こんにちは", "french": "café"}
        file_path = tmp_path / "unicode.json"

        write_json(data, file_path, ensure_ascii=False)

        # Read and verify
        loaded_data = read_json(file_path)
        assert loaded_data == data

        # Verify file contains actual unicode chars (not escaped)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "你好" in content
            assert "こんにちは" in content

    def test_read_json_nonexistent_file(self, tmp_path):
        """Test reading non-existent JSON file raises error."""
        with pytest.raises(FileNotFoundError):
            read_json(tmp_path / "nonexistent.json")

    def test_write_json_list(self, tmp_path):
        """Test writing a list to JSON."""
        data = [{"id": 1}, {"id": 2}, {"id": 3}]
        file_path = tmp_path / "list.json"

        write_json(data, file_path)
        loaded_data = read_json(file_path)
        assert loaded_data == data


class TestCSVTSVFunctions:
    """Test CSV and TSV read/write functions."""

    def test_write_and_read_csv(self, tmp_path):
        """Test writing and reading CSV files."""
        data = [
            {"name": "Alice", "age": "30", "city": "Paris"},
            {"name": "Bob", "age": "25", "city": "Tokyo"},
        ]
        file_path = tmp_path / "test.csv"

        # Write CSV
        write_csv(data, file_path)
        assert file_path.exists()

        # Read CSV
        loaded_data = read_csv(file_path)
        assert loaded_data == data

    def test_write_and_read_tsv(self, tmp_path):
        """Test writing and reading TSV files."""
        data = [
            {"word": "银行", "pinyin": "yínháng", "pos": "noun"},
            {"word": "学校", "pinyin": "xuéxiào", "pos": "noun"},
        ]
        file_path = tmp_path / "test.tsv"

        # Write TSV
        write_tsv(data, file_path)
        assert file_path.exists()

        # Read TSV
        loaded_data = read_tsv(file_path)
        assert loaded_data == data

    def test_write_csv_empty_data_raises_error(self, tmp_path):
        """Test that writing empty data raises ValueError."""
        with pytest.raises(ValueError, match="Cannot write empty data"):
            write_csv([], tmp_path / "empty.csv")

    def test_csv_with_unicode(self, tmp_path):
        """Test CSV with Unicode characters."""
        data = [
            {"language": "Chinese", "word": "你好"},
            {"language": "Japanese", "word": "こんにちは"},
        ]
        file_path = tmp_path / "unicode.csv"

        write_csv(data, file_path)
        loaded_data = read_csv(file_path)
        assert loaded_data == data

    def test_read_csv_custom_delimiter(self, tmp_path):
        """Test reading CSV with custom delimiter."""
        file_path = tmp_path / "custom.csv"

        # Write file with pipe delimiter manually
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("name|age\n")
            f.write("Alice|30\n")
            f.write("Bob|25\n")

        # Read with custom delimiter
        data = read_csv(file_path, delimiter="|")
        assert len(data) == 2
        assert data[0]["name"] == "Alice"
        assert data[0]["age"] == "30"


class TestMarkdownFunctions:
    """Test markdown parsing functions."""

    def test_read_markdown(self, tmp_path):
        """Test reading markdown file."""
        content = "# Title\n\nSome content here.\n\n## Section\n\nMore content."
        file_path = tmp_path / "test.md"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        loaded_content = read_markdown(file_path)
        assert loaded_content == content

    def test_parse_markdown_sections(self):
        """Test parsing markdown into sections."""
        markdown = """# Introduction

This is the introduction.

## Methods

These are the methods.

### Subsection

Subsection content.

## Results

These are the results.
"""

        sections = parse_markdown_sections(markdown)

        assert "Introduction" in sections
        assert "Methods" in sections
        assert "Subsection" in sections
        assert "Results" in sections
        assert "This is the introduction" in sections["Introduction"]
        assert "These are the methods" in sections["Methods"]

    def test_parse_markdown_with_preamble(self):
        """Test parsing markdown with content before first header."""
        markdown = """Preamble content here.

# First Section

Section content.
"""

        sections = parse_markdown_sections(markdown)

        assert "preamble" in sections
        assert "Preamble content here" in sections["preamble"]
        assert "First Section" in sections


class TestDirectoryManagement:
    """Test directory creation and path functions."""

    def test_create_language_level_dir(self, tmp_path):
        """Test creating language/level directory structure."""
        result = create_language_level_dir(tmp_path, "zh", "HSK1", "vocab")

        expected_path = tmp_path / "zh" / "HSK1" / "vocab"
        assert result == expected_path
        assert result.exists()
        assert result.is_dir()

    def test_create_language_level_dir_without_category(self, tmp_path):
        """Test creating directory without category subdirectory."""
        result = create_language_level_dir(tmp_path, "fr", "A1")

        expected_path = tmp_path / "fr" / "A1"
        assert result == expected_path
        assert result.exists()

    def test_create_language_level_dir_idempotent(self, tmp_path):
        """Test that creating same directory twice is idempotent."""
        dir1 = create_language_level_dir(tmp_path, "ja", "N5", "grammar")
        dir2 = create_language_level_dir(tmp_path, "ja", "N5", "grammar")

        assert dir1 == dir2
        assert dir1.exists()

    def test_get_language_level_path(self, tmp_path):
        """Test getting path for language/level structure."""
        path = get_language_level_path(
            tmp_path, "zh", "HSK1", "vocab", "item-123.json"
        )

        expected = tmp_path / "zh" / "HSK1" / "vocab" / "item-123.json"
        assert path == expected

    def test_get_language_level_path_without_filename(self, tmp_path):
        """Test getting path without filename."""
        path = get_language_level_path(tmp_path, "fr", "A2", "grammar")

        expected = tmp_path / "fr" / "A2" / "grammar"
        assert path == expected

    def test_get_language_level_path_without_category(self, tmp_path):
        """Test getting path without category."""
        path = get_language_level_path(tmp_path, "ja", "N4")

        expected = tmp_path / "ja" / "N4"
        assert path == expected

    def test_list_files(self, tmp_path):
        """Test listing files in directory."""
        # Create test files
        (tmp_path / "file1.json").touch()
        (tmp_path / "file2.json").touch()
        (tmp_path / "file3.txt").touch()
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file4.json").touch()

        # List all JSON files (non-recursive)
        json_files = list_files(tmp_path, "*.json", recursive=False)
        assert len(json_files) == 2
        assert all(f.suffix == ".json" for f in json_files)

        # List all files (non-recursive)
        all_files = list_files(tmp_path, "*", recursive=False)
        assert len(all_files) == 3  # file1, file2, file3 (excludes subdir/file4)

        # List all JSON files (recursive)
        json_files_recursive = list_files(tmp_path, "*.json", recursive=True)
        assert len(json_files_recursive) == 3  # Includes subdir/file4.json

    def test_list_files_nonexistent_directory(self, tmp_path):
        """Test listing files in non-existent directory."""
        result = list_files(tmp_path / "nonexistent", "*.json")
        assert result == []

    def test_list_files_empty_directory(self, tmp_path):
        """Test listing files in empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = list_files(empty_dir, "*")
        assert result == []
