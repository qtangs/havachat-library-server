"""Reusable source file parsers for vocabulary and grammar content.

These parsers extract raw data from original source files (TSV, CSV, JSON)
and return normalized dictionaries that can be used by enrichers or other
pipeline stages.

Supported formats:
- Chinese Vocab: TSV with "Word\tPart of Speech" columns
- Japanese Vocab: JSON with word, furigana, romaji, level fields
- French Vocab: TSV with "Mot\tCatégorie" columns
- Chinese Grammar: CSV with "类别,类别名称,细目,语法内容" columns
"""

import csv
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Union

from havachat.utils.romanization import get_japanese_romaji

logger = logging.getLogger(__name__)


# ============================================================================
# MANDARIN VOCABULARY PARSER
# ============================================================================


def clean_sense_marker(word: str) -> str:
    """Remove sense markers from Chinese words.
    
    Examples:
        本1 -> 本
        想2 -> 想
    
    Args:
        word: Word possibly containing sense marker
        
    Returns:
        Word without sense marker
    """
    return re.sub(r"\d+$", "", word.strip())


def extract_sense_marker(word: str) -> str:
    """Extract sense marker from Chinese word.
    
    Examples:
        本1 -> 1
        想2 -> 2
        本 -> ""
    
    Args:
        word: Word possibly containing sense marker
        
    Returns:
        Sense marker or empty string
    """
    match = re.search(r"(\d+)$", word.strip())
    return match.group(1) if match else ""


def translate_chinese_pos(chinese_pos: str) -> str:
    """Translate Chinese part-of-speech to English.
    
    Args:
        chinese_pos: Chinese POS tag
        
    Returns:
        English POS tag
    """
    pos_map = {
        "名": "noun",
        "动": "verb",
        "形": "adjective",
        "数": "number",
        "量": "measure word",
        "代": "pronoun",
        "副": "adverb",
        "介": "preposition",
        "连": "conjunction",
        "助": "particle",
        "叹": "interjection",
        "拟声": "onomatopoeia",
    }
    
    # Handle compound POS like "量、（名）" or "介、连"
    if "、" in chinese_pos or "，" in chinese_pos:
        parts = re.split(r"[、，]", chinese_pos)
        translated = []
        for part in parts:
            part = part.strip().strip("（）")
            if part in pos_map:
                translated.append(pos_map[part])
            else:
                translated.append(part)
        return "/".join(translated)
    
    chinese_pos = chinese_pos.strip().strip("（）")
    return pos_map.get(chinese_pos, chinese_pos)


def parse_chinese_vocab_tsv(source_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Parse Chinese vocabulary TSV file with Word and Part of Speech columns.

    Expected format:
        Word\tPart of Speech
        唱\t动
        点1\t量、（名）
        和1\t介、连

    Args:
        source_path: Path to TSV file

    Returns:
        List of dictionaries with normalized fields:
        - target_item: Cleaned word without sense markers
        - pos: English part of speech
        - original_pos: Original Chinese part of speech
        - sense_marker: Numeric sense marker if present
        - source_row: Row number in source file

    Raises:
        FileNotFoundError: If source file doesn't exist
        ValueError: If TSV format is invalid
    """
    source_path = Path(source_path)

    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    items = []

    with open(source_path, "r", encoding="utf-8") as f:
        # Skip BOM if present
        first_line = f.readline()
        if first_line.startswith("\ufeff"):
            first_line = first_line[1:]

        # Parse as TSV
        f.seek(0)
        reader = csv.DictReader(f, delimiter="\t")

        for i, row in enumerate(reader, start=1):
            # Handle various column name formats
            word = (
                row.get("Word")
                or row.get("word")
                or row.get("WORD")
                or row.get("汉字")
            )
            pos = (
                row.get("Part of Speech")
                or row.get("POS")
                or row.get("pos")
                or row.get("词性")
            )

            if not word:
                logger.warning(f"Row {i} missing 'Word' column, skipping: {row}")
                continue

            # Clean sense marker from word (e.g., "本1" → "本")
            clean_word = clean_sense_marker(word.strip())
            sense_marker = extract_sense_marker(word.strip())

            # Translate Chinese POS to English if needed
            english_pos = translate_chinese_pos(pos.strip()) if pos else None

            items.append(
                {
                    "target_item": clean_word,
                    "pos": english_pos,
                    "original_pos": pos.strip() if pos else None,
                    "sense_marker": sense_marker,
                    "source_row": i,
                }
            )

    logger.info(
        f"Parsed {len(items)} Chinese vocab items from {source_path}",
        extra={"source": str(source_path), "item_count": len(items)},
    )

    return items


# ============================================================================
# JAPANESE VOCABULARY PARSER
# ============================================================================


def normalize_jlpt_level(level: str) -> str:
    """Normalize JLPT level format.
    
    Args:
        level: Raw level string (e.g., "N5", "n5", "5")
        
    Returns:
        Normalized level (e.g., "N5")
    """
    if not level:
        return "N5"
    
    level = str(level).strip().upper()
    
    # Handle numeric only (5 -> N5)
    if level.isdigit():
        return f"N{level}"
    
    # Already formatted
    if level.startswith("N"):
        return level
    
    return "N5"


def parse_japanese_vocab_json(source_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Parse Japanese vocabulary JSON file.

    Expected format:
        [
          {
            "word": "学校",
            "meaning": "school",
            "furigana": "がっこう",
            "romaji": "gakkou",
            "level": "N5"
          },
          ...
        ]

    Or:
        {
          "vocabulary": [...]
        }

    Args:
        source_path: Path to JSON file

    Returns:
        List of dictionaries with normalized fields:
        - target_item: Japanese word
        - meaning: Brief meaning/definition
        - furigana: Reading in hiragana
        - romanization: Romaji (auto-generated if missing)
        - level_min: JLPT level (normalized)
        - level_max: Same as level_min
        - source_index: Index in source file

    Raises:
        FileNotFoundError: If source file doesn't exist
        json.JSONDecodeError: If JSON format is invalid
    """
    source_path = Path(source_path)

    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    with open(source_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Handle both array and object formats
    if isinstance(data, dict):
        items = data.get("vocabulary", [])
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError(f"Unexpected JSON format in {source_path}")

    # Normalize field names
    normalized_items = []
    for i, item in enumerate(items):
        target_word = item.get("word") or item.get("target_item")

        # Generate romaji if missing
        romaji = item.get("romaji") or item.get("romanization")
        if not romaji and target_word:
            romaji = get_japanese_romaji(target_word)

        level = normalize_jlpt_level(item.get("level"))

        normalized = {
            "target_item": target_word,
            "meaning": item.get("meaning") or item.get("definition"),
            "furigana": item.get("furigana"),
            "romanization": romaji,
            "level_min": level,
            "level_max": level,
            "source_index": i,
        }

        if not normalized["target_item"]:
            logger.warning(f"Item {i} missing 'word' field, skipping: {item}")
            continue

        normalized_items.append(normalized)

    logger.info(
        f"Parsed {len(normalized_items)} Japanese vocab items from {source_path}",
        extra={"source": str(source_path), "item_count": len(normalized_items)},
    )

    return normalized_items


# ============================================================================
# FRENCH VOCABULARY PARSER
# ============================================================================


def parse_french_vocab_tsv(source_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Parse French vocabulary TSV file with Mot and Catégorie columns.

    Expected format:
        Mot\tCatégorie
        Bonjour. / Bonsoir.\tSaluer
        Ça va ?\tSaluer
        Au revoir !\tPrendre congé

    Args:
        source_path: Path to TSV file

    Returns:
        List of dictionaries with normalized fields:
        - target_item: French word or phrase
        - context_category: Functional category (e.g., "Saluer", "Exprimer ses goûts")
        - source_row: Row number in source file

    Raises:
        FileNotFoundError: If source file doesn't exist
        ValueError: If TSV format is invalid
    """
    source_path = Path(source_path)

    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    items = []

    with open(source_path, "r", encoding="utf-8") as f:
        # Skip BOM if present
        content = f.read()
        if content.startswith("\ufeff"):
            content = content[1:]
        
        # Parse TSV
        lines = content.strip().split("\n")
        if len(lines) < 2:
            raise ValueError(f"TSV file must have at least header and one data row")
        
        # Parse header
        header = lines[0].split("\t")
        if len(header) < 2:
            raise ValueError(f"Expected at least 2 columns (Mot, Catégorie), got {len(header)}")

        for i, line in enumerate(lines[1:], start=1):
            parts = line.split("\t")
            if len(parts) < 2:
                logger.warning(f"Row {i} has insufficient columns, skipping: {line}")
                continue
            
            word = parts[0].strip()
            category = parts[1].strip()

            if not word:
                logger.warning(f"Row {i} missing 'Mot' value, skipping")
                continue

            item = {
                "target_item": word,
                "context_category": category if category else None,
                "source_row": i,
            }

            items.append(item)

    logger.info(
        f"Parsed {len(items)} French vocab items from {source_path}",
        extra={"source": str(source_path), "item_count": len(items)},
    )

    return items


# ============================================================================
# MANDARIN GRAMMAR PARSER
# ============================================================================


def parse_chinese_grammar_csv(source_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Parse Chinese grammar CSV file with official HSK grammar patterns.
    
    Expected format:
        类别,类别名称,细目,语法内容
        词类,动词,能愿动词,会、能
        词类,代词,人称代词,我、你、您、他、她
    
    Multi-item patterns (separated by 、) are split into individual items
    to avoid creating "mega-items" that cover too much scope.
    
    Args:
        source_path: Path to CSV file
        
    Returns:
        List of dictionaries with normalized fields:
        - type: Grammar type (类别)
        - category_name: Category name (类别名称)
        - detail: Detail subcategory (细目)
        - pattern: Individual grammar pattern (cleaned)
        - original_content: Original multi-pattern string for context
        
    Raises:
        FileNotFoundError: If source file doesn't exist
        ValueError: If CSV format is invalid
    """
    path = Path(source_path)
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")
    
    items = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        
        # Validate columns
        expected_cols = {"类别", "类别名称", "细目", "语法内容"}
        if not expected_cols.issubset(set(reader.fieldnames or [])):
            raise ValueError(
                f"CSV must have columns: {expected_cols}. Found: {reader.fieldnames}"
            )
        
        for row in reader:
            grammar_type = row["类别"].strip()
            category_name = row["类别名称"].strip()
            detail = row["细目"].strip()
            content = row["语法内容"].strip()
            
            # Split multi-item patterns by 、 or comma
            patterns = re.split(r"[、,，]", content)
            patterns = [p.strip() for p in patterns if p.strip()]
            
            # Create individual items for each pattern to avoid mega-items
            for pattern in patterns:
                # Remove any parenthetical numbers or notes for target_item
                # e.g., "会 1" → "会", "（1）专用名量词：本" → "本"
                clean_pattern = re.sub(r"\s*\d+\s*$", "", pattern)  # Remove trailing numbers
                clean_pattern = re.sub(r"^（\d+）[^：]*：", "", clean_pattern)  # Remove prefix like "（1）专用名量词："
                clean_pattern = clean_pattern.strip()
                
                if clean_pattern:
                    items.append({
                        "type": grammar_type,
                        "category_name": category_name,
                        "detail": detail,
                        "pattern": clean_pattern,
                        "original_content": content,  # Keep for context
                    })
    
    logger.info(
        f"Parsed {len(items)} Chinese grammar patterns from {source_path}",
        extra={"source": str(source_path), "item_count": len(items)},
    )
    
    return items


# ============================================================================
# GENERIC LOADER
# ============================================================================


def load_source_file(
    source_path: Union[str, Path],
    language: str,
    content_type: str
) -> List[Dict[str, Any]]:
    """Load and parse a source file based on language and content type.
    
    This is a convenience function that routes to the appropriate parser.
    
    Args:
        source_path: Path to source file
        language: Language code ("zh", "ja", "fr", etc.)
        content_type: Type of content ("vocab", "grammar")
        
    Returns:
        List of parsed items as dictionaries
        
    Raises:
        ValueError: If language/content_type combination not supported
        FileNotFoundError: If source file doesn't exist
    """
    language = language.lower()
    content_type = content_type.lower()
    
    parsers = {
        ("zh", "vocab"): parse_chinese_vocab_tsv,
        ("ja", "vocab"): parse_japanese_vocab_json,
        ("fr", "vocab"): parse_french_vocab_tsv,
        ("zh", "grammar"): parse_chinese_grammar_csv,
    }
    
    key = (language, content_type)
    if key not in parsers:
        raise ValueError(
            f"No parser available for language={language}, content_type={content_type}"
        )
    
    parser = parsers[key]
    return parser(source_path)
