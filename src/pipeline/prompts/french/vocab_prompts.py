"""Prompts for French vocabulary enrichment."""

SYSTEM_PROMPT = """You are an expert French language teacher specializing in vocabulary pedagogy.
Your task is to enrich vocabulary entries with accurate, learner-friendly information.

Key requirements:
1. **Clarity**: Explanations must be clear and suitable for learners at the specified CEFR level (A1-C1)
2. **Examples**: Provide 3-5 contextual examples with English translations
3. **Gender**: Always note gender for nouns (le/la/l')
4. **Register**: Note if usage is formal, informal, or neutral
5. **Polysemy**: If a word has multiple meanings, specify the sense with sense_gloss

Output format: Structured JSON matching the LearningItem schema.
Note: French does not require romanization (uses Latin alphabet).
"""

USER_PROMPT_TEMPLATE = """Enrich the following French vocabulary item:

**Mot (Word)**: {target_item}
**Définition (Definition)**: {definition}
**CEFR Level**: {level_min}

**Missing Fields to Complete**:
{missing_fields_description}

**Instructions**:
1. Write or enhance the English explanation to be clear and learner-friendly
2. For nouns, include gender (masculine/feminine) in the explanation
3. Create 3-5 original example sentences showing varied usage contexts
4. Each example should include:
   - French sentence (with proper accents and spelling)
   - English translation
5. Note register if relevant (formal/informal/neutral)
6. If the word has multiple common meanings, specify which sense

**Example Format**:
"Je vais à l'école tous les jours. - I go to school every day."

Ensure examples are:
- Natural and commonly used by native speakers
- Appropriate for {level_min} learners
- Demonstrating different contexts/collocations
- Using proper French grammar and accents
"""


def build_vocab_enrichment_prompt(
    target_item: str,
    definition: str,
    level_min: str,
    level_max: str,
    missing_fields: list[str],
    existing_data: dict | None = None,
) -> str:
    """Build vocabulary enrichment prompt for French.

    Args:
        target_item: French word/phrase
        definition: Existing definition (if any)
        level_min: Minimum CEFR level (A1, A2, B1, B2, C1)
        level_max: Maximum CEFR level
        missing_fields: List of field names needing enrichment
        existing_data: Optional dict with pre-existing partial data

    Returns:
        Formatted prompt string
    """
    # Build description of missing fields
    field_descriptions = {
        "definition": "- **English explanation** (clear, learner-friendly, include gender for nouns)",
        "examples": "- **3-5 usage examples** with French and English",
        "sense_gloss": "- **Sense disambiguation** (if word has multiple meanings)",
        "lemma": "- **Lemma/base form** (if this is a conjugated verb or inflected form)",
    }

    missing_descriptions = "\n".join(
        field_descriptions.get(field, f"- {field}")
        for field in missing_fields
        if field in field_descriptions
    )

    # Add context from existing data
    context_info = ""
    if existing_data:
        if existing_data.get("examples"):
            context_info += f"\n**Existing Examples**: {existing_data['examples'][:2]}"

    return USER_PROMPT_TEMPLATE.format(
        target_item=target_item,
        definition=definition or "unknown",
        level_min=level_min,
        missing_fields_description=missing_descriptions,
    ) + context_info
