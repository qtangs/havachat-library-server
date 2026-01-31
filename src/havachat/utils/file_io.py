"""File I/O utilities for reading/writing pipeline data.

Supports JSON, TSV, CSV, and markdown parsing with language/level directory structure.
"""

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


# ============================================================================
# JSON Functions
# ============================================================================


def read_json(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Read JSON file and return parsed dictionary.

    Args:
        file_path: Path to JSON file

    Returns:
        Parsed JSON as dictionary

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file contains invalid JSON
    """
    file_path = Path(file_path)
    logger.debug(f"Reading JSON from {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(
    data: Union[Dict[str, Any], List[Any]],
    file_path: Union[str, Path],
    indent: int = 2,
    ensure_ascii: bool = False,
) -> None:
    """Write data to JSON file with pretty printing.

    Creates parent directories if they don't exist.

    Args:
        data: Data to write (dict or list)
        file_path: Path to output JSON file
        indent: Number of spaces for indentation (default: 2)
        ensure_ascii: If False, non-ASCII characters are preserved (default: False)
    """
    file_path = Path(file_path)

    # Create parent directories if they don't exist
    file_path.parent.mkdir(parents=True, exist_ok=True)

    logger.debug(f"Writing JSON to {file_path}")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)

    logger.info(f"Wrote JSON to {file_path}")


# ============================================================================
# TSV/CSV Functions
# ============================================================================


def read_tsv(file_path: Union[str, Path]) -> List[Dict[str, str]]:
    """Read TSV file and return list of dictionaries.

    Args:
        file_path: Path to TSV file

    Returns:
        List of dictionaries, one per row (header as keys)

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    return read_csv(file_path, delimiter="\t")


def read_csv(
    file_path: Union[str, Path], delimiter: str = ","
) -> List[Dict[str, str]]:
    """Read CSV file and return list of dictionaries.

    Args:
        file_path: Path to CSV file
        delimiter: Field delimiter (default: ',')

    Returns:
        List of dictionaries, one per row (header as keys)

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    file_path = Path(file_path)
    logger.debug(f"Reading CSV from {file_path} (delimiter={repr(delimiter)})")

    rows = []
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            rows.append(row)

    logger.info(f"Read {len(rows)} rows from {file_path}")
    return rows


def write_tsv(data: List[Dict[str, Any]], file_path: Union[str, Path]) -> None:
    """Write list of dictionaries to TSV file.

    Args:
        data: List of dictionaries to write
        file_path: Path to output TSV file
    """
    write_csv(data, file_path, delimiter="\t")


def write_csv(
    data: List[Dict[str, Any]],
    file_path: Union[str, Path],
    delimiter: str = ",",
) -> None:
    """Write list of dictionaries to CSV file.

    Creates parent directories if they don't exist.

    Args:
        data: List of dictionaries to write
        file_path: Path to output CSV file
        delimiter: Field delimiter (default: ',')

    Raises:
        ValueError: If data is empty or rows have inconsistent keys
    """
    if not data:
        raise ValueError("Cannot write empty data to CSV")

    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    logger.debug(f"Writing CSV to {file_path} (delimiter={repr(delimiter)})")

    # Get fieldnames from first row
    fieldnames = list(data[0].keys())

    with open(file_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
        writer.writeheader()
        writer.writerows(data)

    logger.info(f"Wrote {len(data)} rows to {file_path}")


# ============================================================================
# Markdown Functions
# ============================================================================


def read_markdown(file_path: Union[str, Path]) -> str:
    """Read markdown file and return content as string.

    Args:
        file_path: Path to markdown file

    Returns:
        File content as string

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    file_path = Path(file_path)
    logger.debug(f"Reading markdown from {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    logger.info(f"Read {len(content)} characters from {file_path}")
    return content


def parse_markdown_sections(markdown_text: str) -> Dict[str, str]:
    """Parse markdown into sections based on headers.

    Args:
        markdown_text: Markdown content as string

    Returns:
        Dictionary mapping header text to content
        (e.g., {"Introduction": "content...", "Methods": "content..."})
    """
    sections = {}
    current_header = "preamble"  # Content before first header
    current_content = []

    for line in markdown_text.split("\n"):
        # Check if line is a header (starts with #)
        if line.strip().startswith("#"):
            # Save previous section
            if current_content:
                sections[current_header] = "\n".join(current_content).strip()
                current_content = []

            # Extract header text (remove # and strip)
            current_header = line.strip().lstrip("#").strip()
        else:
            current_content.append(line)

    # Save last section
    if current_content:
        sections[current_header] = "\n".join(current_content).strip()

    return sections


# ============================================================================
# Directory Management
# ============================================================================


def create_language_level_dir(
    base_dir: Union[str, Path],
    language: str,
    level: str,
    category: Optional[str] = None,
) -> Path:
    """Create directory structure: base_dir/language/level/[category]/

    Args:
        base_dir: Base directory (e.g., 'havachat-knowledge/generated content')
        language: ISO 639-1 language code (e.g., 'zh', 'ja', 'fr')
        level: Proficiency level (e.g., 'HSK1', 'A1', 'N5')
        category: Optional category subdirectory (e.g., 'vocab', 'grammar')

    Returns:
        Path object for created directory

    Example:
        >>> create_language_level_dir('/data', 'zh', 'HSK1', 'vocab')
        Path('/data/zh/HSK1/vocab')
    """
    base_dir = Path(base_dir)

    if category:
        target_dir = base_dir / language / level / category
    else:
        target_dir = base_dir / language / level

    target_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Created directory: {target_dir}")

    return target_dir


def get_language_level_path(
    base_dir: Union[str, Path],
    language: str,
    level: str,
    category: Optional[str] = None,
    filename: Optional[str] = None,
) -> Path:
    """Get path for language/level/[category]/[filename] structure.

    Does not create directories. Use create_language_level_dir() for that.

    Args:
        base_dir: Base directory
        language: ISO 639-1 language code
        level: Proficiency level
        category: Optional category subdirectory
        filename: Optional filename to append

    Returns:
        Path object

    Example:
        >>> get_language_level_path('/data', 'fr', 'A1', 'vocab', 'item-123.json')
        Path('/data/fr/A1/vocab/item-123.json')
    """
    base_dir = Path(base_dir)

    if category:
        path = base_dir / language / level / category
    else:
        path = base_dir / language / level

    if filename:
        path = path / filename

    return path


def list_files(
    directory: Union[str, Path],
    pattern: str = "*",
    recursive: bool = False,
) -> List[Path]:
    """List files in directory matching pattern.

    Args:
        directory: Directory to search
        pattern: Glob pattern (default: '*' = all files)
        recursive: If True, search recursively (default: False)

    Returns:
        List of Path objects matching pattern

    Example:
        >>> list_files('/data/zh/HSK1/vocab', '*.json')
        [Path('/data/zh/HSK1/vocab/item-1.json'), ...]
    """
    directory = Path(directory)

    if not directory.exists():
        logger.warning(f"Directory does not exist: {directory}")
        return []

    if recursive:
        files = list(directory.rglob(pattern))
    else:
        files = list(directory.glob(pattern))

    # Filter to only files (exclude directories)
    files = [f for f in files if f.is_file()]

    logger.debug(f"Found {len(files)} files in {directory} matching '{pattern}'")
    return files
