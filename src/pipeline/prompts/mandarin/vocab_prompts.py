"""Prompts for Mandarin Chinese vocabulary enrichment."""

SYSTEM_PROMPT = """You are an expert Mandarin Chinese teacher specializing in vocabulary pedagogy.
Your task is to enrich vocabulary entries with accurate, learner-friendly information.

Key requirements:
1. **Pinyin Romanization**: Pinyin will be provided automatically, do NOT include it in your response
2. **Clarity**: Explanations must be clear and suitable for learners at the specified level
3. **Examples**: Provide 2-3 contextual examples with pinyin and English translations
4. **Polysemy**: If a word has multiple meanings, specify the sense with sense_gloss
5. **Cultural Context**: Include cultural notes when relevant (e.g., formal vs. informal usage)

**Understanding Chinese POS (词性) Labels:**
The source data uses Chinese part-of-speech labels. Here are the equivalents:
- 名 = noun (people/things/places)
- 动 = verb (actions/states)
- 形 = adjective (describes qualities)
- 副 = adverb (modifies verbs/adjectives)
- 代 = pronoun (substitutes for nouns)
- 数 = numeral (numbers/quantity)
- 量 = measure word/classifier (counting unit like 个, 杯)
- 介 = preposition (at/in/with/to)
- 助 = particle (grammatical particles like 吗, 的, 了)
- 叹 = interjection (exclamations)
- 连 = conjunction (links clauses/words)

**Understanding Sense Markers (trailing numbers):**
Words with trailing numbers (e.g., 本1, 点1, 会1) indicate disambiguation for homographs:
- The number is NOT part of the word itself
- It marks which specific meaning/usage from multiple senses
- Example: 会1 (huì) = "can/know how to" vs. another 会 meaning "meeting"
- Example: 和1 (hé) = "and/with" vs. another 和 meaning "harmony"
- Remove the number from target_item, but note the specific sense in sense_gloss

Output format: Structured JSON matching the LearningItem schema.
"""

USER_PROMPT_TEMPLATE = """Enrich the following Mandarin Chinese vocabulary item:

**Word**: {target_item}
**Part of Speech**: {pos}
**Proficiency Level**: {level_min} to {level_max}

**Missing Fields to Complete**:
{missing_fields_description}

**Pinyin (Provided)**: {romanization}

**Instructions**:
1. Write a clear, learner-friendly explanation in English
2. Translate the POS label (if Chinese): {pos}
3. Create 2-3 original example sentences showing varied usage contexts
4. Each example must include:
   - Chinese characters
   - Pinyin (in parentheses with tone marks)
   - English translation
5. If the word has multiple common meanings, specify which sense with sense_gloss

**Example Format for Examples**:
"我去银行取钱。(Wǒ qù yínháng qǔ qián.) - I go to the bank to withdraw money."

Ensure examples are:
- Natural and commonly used
- Appropriate for {level_min}-{level_max} learners
- Demonstrating different contexts/collocations
"""

POLYSEMY_DETECTION_PROMPT = """Analyze this Mandarin word for polysemy (multiple distinct meanings):

**Word**: {target_item}
**Context from source**: {context}

Does this word have multiple distinct meanings that a learner should know about?
If yes, provide:
1. Primary sense (most common meaning) with short English gloss
2. Secondary sense(s) with short English glosses

Example for 银行:
- Primary: "bank (financial institution)"
- Secondary: None (单一meaning)

Example for 打:
- Primary: "to hit, to strike"
- Secondary: "to play (sports)", "to make (phone call)", "to type"

For the current word, provide the sense disambiguation.
"""


def build_vocab_enrichment_prompt(
    target_item: str,
    pos: str,
    level_min: str,
    level_max: str,
    missing_fields: list[str],
    existing_data: dict | None = None,
) -> str:
    """Build vocabulary enrichment prompt for Mandarin.

    Args:
        target_item: Chinese word/phrase
        pos: Part of speech (noun, verb, adj, etc.)
        level_min: Minimum proficiency level (HSK1, HSK2, etc.)
        level_max: Maximum proficiency level
        missing_fields: List of field names needing enrichment
        existing_data: Optional dict with pre-existing partial data

    Returns:
        Formatted prompt string
    """
    # Build description of missing fields
    field_descriptions = {
        "definition": "- **English explanation** (clear, learner-friendly, note POS meaning)",
        "examples": "- **2-3 usage examples** with Chinese, pinyin, and English",
        "sense_gloss": "- **Sense disambiguation** (if word has multiple meanings or has sense marker like 1,2)",
        "lemma": "- **Lemma/base form** (if this is an inflected form)",
    }

    missing_descriptions = "\n".join(
        field_descriptions.get(field, f"- {field}")
        for field in missing_fields
        if field in field_descriptions
    )

    # Add context from existing data if available
    context_info = ""
    if existing_data:
        if existing_data.get("definition"):
            context_info += f"\n**Existing Explanation**: {existing_data['definition']}"
        if existing_data.get("examples"):
            context_info += f"\n**Existing Examples**: {existing_data['examples'][:2]}"

    return USER_PROMPT_TEMPLATE.format(
        target_item=target_item,
        romanization=existing_data.get("romanization", "(not yet generated)") if existing_data else "(not yet generated)",
        pos=pos or "unknown",
        level_min=level_min,
        level_max=level_max,
        missing_fields_description=missing_descriptions,
    ) + context_info
