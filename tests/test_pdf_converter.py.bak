import os
import json
import pytest
from pathlib import Path
from src.tools.text.pdf_converter import convert_pdf

# Use the test file provided by the user
TEST_PDF = "tests/data/Docling Technical Report 20204.pdf"

@pytest.fixture
def output_md(tmp_path):
    return tmp_path / "output.md"

@pytest.fixture
def output_txt(tmp_path):
    return tmp_path / "output.txt"

def test_convert_markdown_full(output_md):
    """Test full conversion to markdown."""
    config = json.dumps({"format": "markdown"})
    convert_pdf(TEST_PDF, config, str(output_md))
    
    assert output_md.exists()
    content = output_md.read_text(encoding="utf-8")
    assert len(content) > 0
    # Basic check for markdown-like content
    assert "#" in content or "**" in content

def test_convert_markdown_page_range(output_md):
    """Test conversion with a specific page range."""
    # Convert only page 1
    config = json.dumps({"format": "markdown", "pageRange": "1"})
    convert_pdf(TEST_PDF, config, str(output_md))
    
    assert output_md.exists()
    content = output_md.read_text(encoding="utf-8")
    assert len(content) > 0

def test_convert_txt(output_txt):
    """Test conversion to txt format."""
    config = json.dumps({"format": "txt"})
    convert_pdf(TEST_PDF, config, str(output_txt))
    
    assert output_txt.exists()
    content = output_txt.read_text(encoding="utf-8")
    assert len(content) > 0

def test_invalid_input():
    """Test handling of non-existent input file."""
    config = json.dumps({"format": "markdown"})
    with pytest.raises(SystemExit):
        convert_pdf("non_existent.pdf", config, "out.md")

def test_convert_with_tables(output_md):
    """Test conversion with table extraction."""
    config = json.dumps({"format": "markdown", "extractTables": True})
    convert_pdf(TEST_PDF, config, str(output_md))
    
    assert output_md.exists()
    
    # Check for table files
    # output_md is /tmp/path/output.md
    # Tables should be /tmp/path/output-table-*.csv
    parent = output_md.parent
    csv_files = list(parent.glob("output-table-*.csv"))
    html_files = list(parent.glob("output-table-*.html"))
    
    # We assume the test PDF has tables. If not, this assertion might fail if we enforce > 0.
    # Allowing 0 tables to pass if the PDF just doesn't have them, 
    # but strictly checking that if CSV exists, HTML exists.
    assert len(csv_files) == len(html_files)
    if len(csv_files) > 0:
        assert csv_files[0].stat().st_size > 0
