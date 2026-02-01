def build_evaluation_prompt(
    text: str, 
    language: str, 
    level: str, 
    content_type: str
) -> str:
    """Build comprehensive evaluation prompt for LLM.
    
    Args:
        text: Content to evaluate
        language: Content language
        level: Proficiency level
        content_type: conversation or story
        
    Returns:
        Formatted prompt string
    """
    type_specific = _get_type_specific_guidance(content_type)
    level_guidance = _get_level_guidance(level)
    
    prompt = f"""You are an expert language learning content evaluator. Evaluate the following {content_type} for {language} learners at {level} level.

**Content to Evaluate:**
{text}

**Your Task:**
Provide a comprehensive quality assessment across 6 dimensions. For each dimension, give:
1. A score from 1 (poor) to 10 (excellent)
2. A detailed explanation (50-200 words) justifying the score

**Evaluation Dimensions:**

1. **Naturalness** (1-10)
- How authentic and natural does the {content_type} sound?
- Would native speakers use these expressions in real life?
- Is the flow smooth and conversational (for dialogue) or well-structured (for narrative)?

2. **Level Appropriateness** (1-10)
- Is the language suitable for {level} learners?
- {level_guidance}
- Are sentence structures appropriate for this level?

3. **Grammatical Correctness** (1-10)
- Are there any grammar errors?
- Is the syntax correct and consistent?
- Are verb tenses, particles, and word order appropriate?

4. **Vocabulary Diversity** (1-10)
- Is there good variety in vocabulary used?
- Are words repeated too often, or is there natural variation?
- Is the vocabulary level-appropriate while still introducing useful terms?

5. **Cultural Accuracy** (1-10)
- Are cultural references appropriate and accurate?
- Do scenarios reflect realistic cultural contexts?
- Are social norms and pragmatics handled correctly?

6. **Engagement** (1-10)
- Is the content interesting and engaging for learners?
- Does it maintain attention throughout?
- Are scenarios relevant and relatable?

{type_specific}

**Overall Recommendation:**
Based on all dimensions, provide:
- **overall_recommendation**: "proceed" (ready for audio generation) or "review" (needs human review)
- **recommendation_justification**: Clear reasoning for your recommendation (50-150 words)

**Important Guidelines:**
- Be honest and constructive in your evaluations
- Justify scores with specific examples from the text
- Consider the target learner level in all assessments
- Flag any major issues that would hinder learning
"""
    return prompt

    
def _get_type_specific_guidance(content_type: str) -> str:
    """Get type-specific evaluation guidance."""
    if content_type == "conversation":
        return """
**Conversation-Specific Considerations:**
- Are speaker turns natural and realistic?
- Do speakers respond appropriately to each other?
- Is the dialogue purpose clear (e.g., shopping, greeting, asking directions)?
- Are turn-taking and conversation flow natural?
"""
    else:  # story
        return """
**Story-Specific Considerations:**
- Is the narrative coherent and easy to follow?
- Are events sequenced logically?
- Is there a clear beginning, middle, and resolution?
- Does the story maintain reader interest throughout?
"""

def _get_level_guidance(level: str) -> str:
    """Get level-specific evaluation guidance."""
    level_lower = level.lower()
    
    if "hsk1" in level_lower or "a1" in level_lower or "n5" in level_lower:
        return "Expect very simple sentences, basic vocabulary, present tense focus, minimal complex structures"
    elif "hsk2" in level_lower or "a2" in level_lower or "n4" in level_lower:
        return "Expect simple sentences, common vocabulary, some past tense, basic conjunctions"
    elif "hsk3" in level_lower or "b1" in level_lower or "n3" in level_lower:
        return "Expect more complex sentences, broader vocabulary, multiple tenses, some subordination"
    elif "hsk4" in level_lower or "b2" in level_lower or "n2" in level_lower:
        return "Expect complex structures, idiomatic expressions, nuanced vocabulary, varied sentence patterns"
    else:
        return "Expect advanced structures, sophisticated vocabulary, and native-like fluency"
