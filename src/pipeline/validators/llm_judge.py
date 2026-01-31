"""LLM Quality Judge Implementation

This module implements comprehensive conversation/story quality evaluation using LLM.
Evaluates content across 6 dimensions with detailed explanations and recommendations.
"""

import logging
from typing import Literal

from pydantic import ValidationError

from src.models.llm_judge_evaluation import DimensionScore, LLMJudgeEvaluation
from havachat.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


class LLMJudge:
    """LLM-based quality judge for conversations and stories.
    
    Evaluates content across 6 dimensions:
    1. Naturalness - Authenticity of dialogue/narrative
    2. Level Appropriateness - Fit for target proficiency level
    3. Grammatical Correctness - Grammar and syntax accuracy
    4. Vocabulary Diversity - Range of vocabulary used
    5. Cultural Accuracy - Cultural context appropriateness
    6. Engagement - Interest level for learners
    """
    
    def __init__(self, llm_client: LLMClient, model: str = "gpt-4"):
        """Initialize LLM judge.
        
        Args:
            llm_client: Configured LLM client with instructor support
            model: LLM model to use for evaluation (default: gpt-4)
        """
        self.llm_client = llm_client
        self.model = model
        self.inconsistency_threshold = 4  # Score difference flagging inconsistency
    
    def evaluate_conversation(
        self, 
        content_id: str,
        text: str,
        language: str,
        level: str,
        content_type: Literal["conversation", "story"] = "conversation"
    ) -> LLMJudgeEvaluation:
        """Evaluate a conversation or story across 6 quality dimensions.
        
        Args:
            content_id: UUID of the content unit
            text: Full conversation or story text
            language: Content language (zh, ja, fr, etc.)
            level: Proficiency level (hsk1, jlpt-n5, a1, etc.)
            content_type: Type of content (conversation or story)
            
        Returns:
            LLMJudgeEvaluation with scores, explanations, and recommendation
            
        Raises:
            ValidationError: If LLM output doesn't match expected schema
            Exception: If LLM call fails after retries
        """
        logger.info(f"Evaluating {content_type} {content_id} ({language}/{level})")
        
        prompt = self._build_evaluation_prompt(text, language, level, content_type)
        
        try:
            # Use instructor to get structured output
            evaluation = self.llm_client.generate(
                prompt=prompt,
                response_model=LLMJudgeEvaluation,
                temperature=0.3,  # Lower temperature for consistent evaluation
                system_prompt="You are an expert language learning content evaluator. "
                             "Provide detailed, objective assessments of educational content quality."
            )
            
            # Override content metadata (LLM doesn't know these)
            evaluation.content_id = content_id
            evaluation.content_type = content_type
            evaluation.evaluator_model = self.model
            
            # Check for inconsistencies
            self._detect_inconsistencies(evaluation)
            
            logger.info(
                f"Evaluation complete: avg_score={evaluation.average_score():.1f}, "
                f"recommendation={evaluation.overall_recommendation}"
            )
            
            return evaluation
            
        except ValidationError as e:
            logger.error(f"LLM evaluation output validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"LLM evaluation failed: {e}")
            raise
    
    def _build_evaluation_prompt(
        self, 
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
        type_specific = self._get_type_specific_guidance(content_type)
        level_guidance = self._get_level_guidance(level)
        
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
    
    def _get_type_specific_guidance(self, content_type: str) -> str:
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
    
    def _get_level_guidance(self, level: str) -> str:
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
    
    def _detect_inconsistencies(self, evaluation: LLMJudgeEvaluation) -> None:
        """Detect contradictory scores and flag inconsistencies.
        
        Args:
            evaluation: Evaluation to check for inconsistencies (modified in-place)
        """
        scores = [
            ("naturalness", evaluation.naturalness.score),
            ("level_appropriateness", evaluation.level_appropriateness.score),
            ("grammatical_correctness", evaluation.grammatical_correctness.score),
            ("vocabulary_diversity", evaluation.vocabulary_diversity.score),
            ("cultural_accuracy", evaluation.cultural_accuracy.score),
            ("engagement", evaluation.engagement.score)
        ]
        
        # Find highest and lowest scores
        max_dim, max_score = max(scores, key=lambda x: x[1])
        min_dim, min_score = min(scores, key=lambda x: x[1])
        
        score_diff = max_score - min_score
        
        # Flag if difference is too large (e.g., 9 vs 2 = 7-point difference)
        if score_diff >= self.inconsistency_threshold:
            evaluation.has_inconsistency = True
            evaluation.inconsistency_note = (
                f"Large score disparity detected: {max_dim}={max_score} vs {min_dim}={min_score} "
                f"({score_diff}-point difference). This may indicate contradictory assessments."
            )
            logger.warning(f"Inconsistency detected in {evaluation.content_id}: {evaluation.inconsistency_note}")
