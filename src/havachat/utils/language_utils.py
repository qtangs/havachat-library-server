"""Language code mapping utilities."""

# Language name to ISO 639-1 code mapping
LANGUAGE_NAME_TO_CODE = {
    "mandarin": "zh",
    "chinese": "zh",
    "japanese": "ja",
    "french": "fr",
    "english": "en",
}

# ISO 639-1 code to language name mapping
LANGUAGE_CODE_TO_NAME = {
    "zh": "Mandarin",
    "ja": "Japanese",
    "fr": "French",
    "en": "English",
}


def get_language_code(language_name_or_code: str) -> str:
    """Convert language name to ISO 639-1 code.
    
    Args:
        language_name_or_code: Language name (e.g., "Mandarin") or code (e.g., "zh")
        
    Returns:
        ISO 639-1 language code (e.g., "zh")
        
    Raises:
        ValueError: If language is not supported
    """
    lower_input = language_name_or_code.lower()
    
    # If already a valid code, return it
    if lower_input in LANGUAGE_CODE_TO_NAME:
        return lower_input
    
    # Try to get code from name
    if lower_input in LANGUAGE_NAME_TO_CODE:
        return LANGUAGE_NAME_TO_CODE[lower_input]
    
    raise ValueError(
        f"Unsupported language: '{language_name_or_code}'. "
        f"Supported: {', '.join(LANGUAGE_CODE_TO_NAME.values())}"
    )


def get_language_name(language_code: str) -> str:
    """Convert ISO 639-1 code to language name.
    
    Args:
        language_code: ISO 639-1 language code (e.g., "zh")
        
    Returns:
        Language name (e.g., "Mandarin")
        
    Raises:
        ValueError: If language code is not supported
    """
    lower_code = language_code.lower()
    
    if lower_code not in LANGUAGE_CODE_TO_NAME:
        raise ValueError(
            f"Unsupported language code: '{language_code}'. "
            f"Supported: {', '.join(LANGUAGE_CODE_TO_NAME.keys())}"
        )
    
    return LANGUAGE_CODE_TO_NAME[lower_code]
