"""Prompts for Japanese vocabulary enrichment."""

SYSTEM_PROMPT = """You are an expert Japanese language teacher specializing in vocabulary pedagogy.
Your task is to enrich vocabulary entries with accurate, learner-friendly information.

Key requirements:
1. **Romanization**: Romaji will be provided automatically, do NOT include it in your response
2. **Furigana**: Include hiragana readings for kanji when applicable
3. **Clarity**: Explanations must be clear and suitable for learners at the specified level (N5-N1)
4. **Examples**: Provide 3-5 contextual examples with English translations
5. **Polysemy**: If a word has multiple meanings, specify the sense with sense_gloss_en
6. **Formality**: Note if usage is formal, informal, or neutral

Output format: Structured JSON matching the LearningItem schema.
"""

USER_PROMPT_TEMPLATE = """Enrich the following Japanese vocabulary item:

**Word**: {target_item}
**Meaning**: {meaning}
**JLPT Level**: {level_min}

**Missing Fields to Complete**:
{missing_fields_description}

**Instructions**:
1. Write or enhance the English explanation to be clear and learner-friendly
2. For nouns and verbs, note formality level if relevant (formal/informal/neutral)
3. Create 3-5 original example sentences showing varied usage contexts
4. Each example should include:
   - Japanese text (with kanji)
   - English translation
6. Note formality level if relevant (formal/informal/neutral)

**Example Format**:
"今日は学校に行きます。- I go to school today."

Ensure examples are:
- Natural and commonly used
- Appropriate for {level_min} learners
- Demonstrating different contexts/collocations
"""


def build_vocab_enrichment_prompt(
    target_item: str,
    meaning: str,
    level_min: str,
    level_max: str,
    missing_fields: list[str],
    existing_data: dict | None = None,
) -> str:
    """Build vocabulary enrichment prompt for Japanese.

    Args:
        target_item: Japanese word/phrase
        meaning: Existing meaning/definition
        level_min: Minimum proficiency level (N5, N4, etc.)
        level_max: Maximum proficiency level
        missing_fields: List of field names needing enrichment
        existing_data: Optional dict with pre-existing partial data

    Returns:
        Formatted prompt string
    """
    # Build description of missing fields
    field_descriptions = {
        "romanization": "- **Romaji romanization** (Hepburn style)",
        "definition_en": "- **English explanation** (clear, learner-friendly)",
        "examples": "- **3-5 usage examples** with Japanese and English",
        "sense_gloss_en": "- **Sense disambiguation** (if word has multiple meanings)",
    }

    missing_descriptions = "\n".join(
        field_descriptions.get(field, f"- {field}")
        for field in missing_fields
        if field in field_descriptions
    )

    # Add context from existing data
    context_info = ""
    if existing_data:
        if existing_data.get("furigana"):
            context_info += f"\n**Existing Furigana**: {existing_data['furigana']}"
        if existing_data.get("romaji"):
            context_info += f"\n**Existing Romaji**: {existing_data['romaji']}"

    return USER_PROMPT_TEMPLATE.format(
        target_item=target_item,
        meaning=meaning or "unknown",
        level_min=level_min,
        missing_fields_description=missing_descriptions,
    ) + context_info
