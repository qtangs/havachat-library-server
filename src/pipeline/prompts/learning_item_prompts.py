"""System prompts for learning item generation across all categories.

This module contains prompts for generating learning items beyond official
vocab/grammar lists: pronunciation, idioms, functional language, cultural notes,
writing system, and miscellaneous linguistic features.
"""

from src.pipeline.validators.schema import Category


def get_pronunciation_system_prompt() -> str:
    """Get system prompt for pronunciation item generation."""
    return """You are an expert language teacher specializing in pronunciation instruction.

Generate pronunciation learning items that:
1. Focus on a specific pronunciation feature (tone, pitch, sound)
2. Provide clear, learner-friendly explanations
3. Include practical examples with phonetic transcription
4. Are appropriate for the learner's level

Target format: LearningItem with category='pronunciation'"""


def get_idiom_system_prompt() -> str:
    """Get system prompt for idiom item generation."""
    return """You are an expert language teacher specializing in idiomatic expressions.

Generate idiom learning items that:
1. Identify fixed expressions, idioms, and collocations
2. Explain literal vs figurative meanings
3. Provide usage context and register
4. Include natural examples
5. Are appropriate for the learner's level

Target format: LearningItem with category='idiom'"""


def get_functional_system_prompt() -> str:
    """Get system prompt for functional language item generation."""
    return """You are an expert language teacher specializing in functional communication.

Generate functional language items that:
1. Focus on communicative functions (greeting, requesting, apologizing, etc.)
2. Explain formality levels and appropriate contexts
3. Provide situation-specific examples
4. Are practical and immediately useful
5. Are appropriate for the learner's level

Target format: LearningItem with category='functional'"""


def get_cultural_system_prompt() -> str:
    """Get system prompt for cultural note generation."""
    return """You are an expert cultural consultant and language teacher.

Generate cultural learning items that:
1. Explain relevant customs, etiquette, or social norms
2. Provide practical advice for learners
3. Include cultural context that aids understanding
4. Are respectful and nuanced
5. Are appropriate for the learner's level

Target format: LearningItem with category='cultural'"""


def get_writing_system_system_prompt() -> str:
    """Get system prompt for writing system item generation."""
    return """You are an expert in Chinese/Japanese writing systems.

Generate writing system learning items that:
1. Focus on radicals, components, or character structure
2. Explain meaning and mnemonic connections
3. Provide examples showing the feature across multiple characters
4. Include stroke order or writing tips
5. Are appropriate for the learner's level

Target format: LearningItem with category='writing_system'"""


def get_miscellaneous_system_prompt(category: Category) -> str:
    """Get system prompt for miscellaneous category generation.
    
    Args:
        category: Specific miscellaneous category (sociolinguistic, pragmatic, literacy, pattern, other)
        
    Returns:
        System prompt string for the given category
    """
    category_descriptions = {
        Category.SOCIOLINGUISTIC: "sociolinguistic features (register, formality, dialectal variations)",
        Category.PRAGMATIC: "pragmatic features (implicature, inference, conversational strategies)",
        Category.LITERACY: "literacy features (reading strategies, text types, discourse markers)",
        Category.PATTERN: "linguistic patterns (sentence patterns, collocational patterns)",
        Category.OTHER: "other linguistic features not covered by standard categories",
    }
    
    desc = category_descriptions.get(category, "linguistic features")
    
    return f"""You are an expert linguist and language teacher.

Generate {category.value} learning items that:
1. Focus on {desc}
2. Provide clear explanations with linguistic terminology
3. Include practical examples
4. Are pedagogically sound
5. Are appropriate for the learner's level

Target format: LearningItem with category='{category.value}'"""
