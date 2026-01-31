"""LLM Quality Judge Evaluation Models

This module defines Pydantic models for comprehensive conversation/story quality evaluation.
Each evaluation includes 6 dimensions with scores (1-10) and explanations, plus overall recommendation.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DimensionScore(BaseModel):
    """Score and explanation for a single evaluation dimension."""
    
    score: int = Field(..., ge=1, le=10, description="Score from 1 (poor) to 10 (excellent)")
    explanation: str = Field(..., min_length=10, max_length=500, description="Detailed explanation of the score")


class LLMJudgeEvaluation(BaseModel):
    """Comprehensive quality evaluation for a conversation or story.
    
    Evaluates content across 6 dimensions:
    1. Naturalness - How authentic the dialogue/narrative sounds
    2. Level Appropriateness - Suitability for target proficiency level
    3. Grammatical Correctness - Accuracy of grammar and syntax
    4. Vocabulary Diversity - Range and variety of vocabulary used
    5. Cultural Accuracy - Appropriateness of cultural references and context
    6. Engagement - How interesting and engaging the content is for learners
    """
    
    content_id: str = Field(..., description="UUID of the evaluated content unit")
    content_type: Literal["conversation", "story"] = Field(..., description="Type of content evaluated")
    
    # Six evaluation dimensions
    naturalness: DimensionScore = Field(..., description="Authenticity of dialogue/narrative")
    level_appropriateness: DimensionScore = Field(..., description="Fit for target proficiency level")
    grammatical_correctness: DimensionScore = Field(..., description="Grammar and syntax accuracy")
    vocabulary_diversity: DimensionScore = Field(..., description="Range of vocabulary used")
    cultural_accuracy: DimensionScore = Field(..., description="Cultural context appropriateness")
    engagement: DimensionScore = Field(..., description="Interest level for learners")
    
    # Overall assessment
    overall_recommendation: Literal["proceed", "review"] = Field(
        ..., 
        description="Recommendation: 'proceed' if content is ready, 'review' if manual review needed"
    )
    recommendation_justification: str = Field(
        ..., 
        min_length=20, 
        max_length=500,
        description="Detailed justification for the recommendation"
    )
    
    # Metadata
    evaluated_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of evaluation")
    evaluator_model: str = Field(default="gpt-4", description="LLM model used for evaluation")
    
    # Optional flags
    has_inconsistency: bool = Field(
        default=False,
        description="True if contradictory scores detected (e.g., high naturalness but low engagement)"
    )
    inconsistency_note: str | None = Field(
        default=None,
        description="Description of detected inconsistencies, if any"
    )
    
    def average_score(self) -> float:
        """Calculate average score across all 6 dimensions."""
        scores = [
            self.naturalness.score,
            self.level_appropriateness.score,
            self.grammatical_correctness.score,
            self.vocabulary_diversity.score,
            self.cultural_accuracy.score,
            self.engagement.score
        ]
        return sum(scores) / len(scores)
    
    def is_passing(self, threshold: float = 7.0) -> bool:
        """Check if average score meets minimum threshold."""
        return self.average_score() >= threshold
    
    def to_json_string(self) -> str:
        """Serialize to JSON string for Notion LLM Comment field."""
        return self.model_dump_json(indent=2, exclude={"content_id", "content_type", "evaluated_at"})
