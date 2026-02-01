"""LLM Quality Judge Implementation

This module implements comprehensive conversation/story quality evaluation using LLM.
Evaluates content across 6 dimensions with detailed explanations and recommendations.
"""

import logging
from typing import Literal

from pydantic import ValidationError

from havachat.prompts.llm_judge_prompts import build_evaluation_prompt
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
        
        prompt = build_evaluation_prompt(text, language, level, content_type)
        
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
