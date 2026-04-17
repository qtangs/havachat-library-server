"""
Utility Functions for Notion Audio Content Processor

Filename sanitization, path construction, and content hash management.
"""

import hashlib
import unicodedata
from pathlib import Path
from typing import Optional


def sanitize_filename(name: str, max_length: int = 255) -> str:
    """
    Sanitize filename for filesystem compatibility.
    
    Rules:
    - Remove/replace invalid filesystem characters: < > : " / \\ | ? *
    - Normalize Unicode (NFC form)
    - Truncate to max_length bytes
    - Strip leading/trailing dots and spaces
    
    Args:
        name: Original filename or directory name
        max_length: Maximum length in bytes (default: 255 for most filesystems)
    
    Returns:
        Sanitized filename safe for filesystem use
    
    Examples:
        >>> sanitize_filename("Hello/World")
        'Hello-World'
        >>> sanitize_filename("Test: Example?")
        'Test- Example-'
        >>> sanitize_filename("  .hidden.txt  ")
        'hidden.txt'
    """
    # Normalize Unicode (combining diacritics to composed form)
    name = unicodedata.normalize('NFC', name)
    
    # Replace invalid filesystem characters with dash
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '-')
    
    # Remove control characters (ASCII 0-31 and 127)
    name = ''.join(char for char in name if ord(char) >= 32 and ord(char) != 127)
    
    # Strip leading/trailing dots and spaces
    name = name.strip('. ')
    
    # Truncate to max_length bytes (UTF-8 encoding)
    # Ensure we don't cut in the middle of a multi-byte character
    encoded = name.encode('utf-8')
    if len(encoded) > max_length:
        # Find safe truncation point
        truncated = encoded[:max_length]
        # Try to decode; if it fails, keep removing bytes until it works
        while len(truncated) > 0:
            try:
                name = truncated.decode('utf-8')
                break
            except UnicodeDecodeError:
                truncated = truncated[:-1]
    
    # Final fallback if name becomes empty
    if not name:
        name = "untitled"
    
    return name


def get_audio_storage_path(
    base_path: Path,
    topic: str,
    sub_type: str,
    record_id: str,
    record_name: str,
    extension: str = "mp3"
) -> Path:
    """
    Construct hierarchical audio file path.
    
    Structure: {base_path}/{topic}/{sub_type}/{id}-{name}.{extension}
    
    Args:
        base_path: Root storage directory (e.g., /Users/user/havachat-knowledge)
        topic: Topic category (sanitized for directory name)
        sub_type: Sub-type category (sanitized for directory name)
        record_id: Notion page ID (used as prefix for uniqueness)
        record_name: Human-readable name (sanitized for filename)
        extension: File extension (default: mp3)
    
    Returns:
        Complete Path object for audio file
    
    Example:
        >>> get_audio_storage_path(
        ...     Path("/data/audio"),
        ...     "Education",
        ...     "Grammar",
        ...     "abc123",
        ...     "Present Tense"
        ... )
        Path('/data/audio/Education/Grammar/abc123-Present Tense.mp3')
    """
    # Sanitize directory names
    topic_dir = sanitize_filename(topic)
    subtype_dir = sanitize_filename(sub_type)
    
    # Sanitize filename (id-name.extension)
    sanitized_name = sanitize_filename(record_name)
    filename = f"{record_id}-{sanitized_name}.{extension}"
    
    # Construct full path
    full_path = base_path / topic_dir / subtype_dir / filename
    
    # Create parent directories if they don't exist
    full_path.parent.mkdir(parents=True, exist_ok=True)
    
    return full_path


def compute_content_hash(content: str) -> str:
    """
    Compute SHA-256 hash of content for duplicate detection.
    
    Args:
        content: Text content to hash
    
    Returns:
        Hexadecimal hash digest (64 characters)
    
    Example:
        >>> compute_content_hash("Hello, world!")
        '315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3'
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def save_content_hash(audio_path: Path, content_hash: str) -> None:
    """
    Save content hash to sidecar file.
    
    Sidecar file format: {audio_path}.hash
    Content: Just the hash string (no metadata)
    
    Args:
        audio_path: Path to audio file
        content_hash: Hash to save
    
    Example:
        >>> save_content_hash(Path("/data/audio.mp3"), "abc123...")
        # Creates /data/audio.mp3.hash with content "abc123..."
    """
    hash_path = Path(str(audio_path) + ".hash")
    hash_path.write_text(content_hash, encoding='utf-8')


def load_content_hash(audio_path: Path) -> Optional[str]:
    """
    Load content hash from sidecar file.
    
    Args:
        audio_path: Path to audio file
    
    Returns:
        Hash string if file exists, None otherwise
    
    Example:
        >>> load_content_hash(Path("/data/audio.mp3"))
        'abc123...'
    """
    hash_path = Path(str(audio_path) + ".hash")
    if hash_path.exists():
        return hash_path.read_text(encoding='utf-8').strip()
    return None


def should_regenerate_audio(audio_path: Path, current_content: str) -> bool:
    """
    Determine if audio should be regenerated based on content changes.
    
    Logic:
    1. If audio file doesn't exist → regenerate
    2. If hash file doesn't exist → regenerate
    3. If current content hash != saved hash → regenerate
    4. Otherwise → skip (no changes)
    
    Args:
        audio_path: Path to audio file
        current_content: Current text content from Notion
    
    Returns:
        True if audio should be regenerated, False to skip
    
    Example:
        >>> should_regenerate_audio(Path("/data/audio.mp3"), "New content")
        True  # If file is missing or content changed
    """
    # Audio file doesn't exist → regenerate
    if not audio_path.exists():
        return True
    
    # Load saved hash
    saved_hash = load_content_hash(audio_path)
    if saved_hash is None:
        # Hash file missing → regenerate for safety
        return True
    
    # Compare hashes
    current_hash = compute_content_hash(current_content)
    return current_hash != saved_hash
