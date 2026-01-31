"""Unit tests for LLM Judge implementation."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from src.models.llm_judge_evaluation import DimensionScore, LLMJudgeEvaluation
from src.pipeline.validators.llm_judge import LLMJudge


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = MagicMock()
    return client


@pytest.fixture
def sample_evaluation():
    """Create sample evaluation response."""
    return LLMJudgeEvaluation(
        content_id="test-uuid",
        content_type="conversation",
        naturalness=DimensionScore(score=8, explanation="Natural dialogue with good flow"),
        level_appropriateness=DimensionScore(score=9, explanation="Perfect for HSK1 learners"),
        grammatical_correctness=DimensionScore(score=7, explanation="Minor error in one sentence"),
        vocabulary_diversity=DimensionScore(score=6, explanation="Limited but appropriate variety"),
        cultural_accuracy=DimensionScore(score=9, explanation="Culturally accurate shopping scenario"),
        engagement=DimensionScore(score=8, explanation="Interesting and relatable scenario"),
        overall_recommendation="proceed",
        recommendation_justification="Strong performance across all dimensions, ready for production"
    )


class TestLLMJudge:
    """Test LLM Judge functionality."""
    
    def test_initialization(self, mock_llm_client):
        """Test LLM judge initialization."""
        judge = LLMJudge(mock_llm_client, model="gpt-4")
        assert judge.llm_client == mock_llm_client
        assert judge.model == "gpt-4"
        assert judge.inconsistency_threshold == 4
    
    def test_evaluate_conversation_success(self, mock_llm_client, sample_evaluation):
        """Test successful conversation evaluation."""
        mock_llm_client.generate.return_value = sample_evaluation
        
        judge = LLMJudge(mock_llm_client)
        result = judge.evaluate_conversation(
            content_id="test-123",
            text="Speaker 1: 你好\nSpeaker 2: 你好",
            language="zh",
            level="hsk1",
            content_type="conversation"
        )
        
        assert result.content_id == "test-123"
        assert result.content_type == "conversation"
        assert result.overall_recommendation == "proceed"
        assert mock_llm_client.generate.called
    
    def test_evaluate_story(self, mock_llm_client, sample_evaluation):
        """Test story evaluation."""
        sample_evaluation.content_type = "story"
        mock_llm_client.generate.return_value = sample_evaluation
        
        judge = LLMJudge(mock_llm_client)
        result = judge.evaluate_conversation(
            content_id="story-456",
            text="Once upon a time...",
            language="fr",
            level="a1",
            content_type="story"
        )
        
        assert result.content_type == "story"
        assert result.content_id == "story-456"
    
    def test_build_evaluation_prompt_conversation(self, mock_llm_client):
        """Test prompt building for conversations."""
        judge = LLMJudge(mock_llm_client)
        prompt = judge._build_evaluation_prompt(
            text="Test conversation",
            language="zh",
            level="hsk1",
            content_type="conversation"
        )
        
        assert "conversation" in prompt.lower()
        assert "hsk1" in prompt
        assert "Test conversation" in prompt
        assert "Naturalness" in prompt
        assert "speaker turns" in prompt.lower()
    
    def test_build_evaluation_prompt_story(self, mock_llm_client):
        """Test prompt building for stories."""
        judge = LLMJudge(mock_llm_client)
        prompt = judge._build_evaluation_prompt(
            text="Test story",
            language="fr",
            level="a2",
            content_type="story"
        )
        
        assert "story" in prompt.lower()
        assert "a2" in prompt
        assert "narrative" in prompt.lower()
        assert "Story-Specific" in prompt
    
    def test_get_level_guidance_beginner(self, mock_llm_client):
        """Test level guidance for beginner levels."""
        judge = LLMJudge(mock_llm_client)
        
        guidance_hsk1 = judge._get_level_guidance("hsk1")
        assert "simple sentences" in guidance_hsk1.lower()
        assert "basic vocabulary" in guidance_hsk1.lower()
        
        guidance_a1 = judge._get_level_guidance("a1")
        assert "simple" in guidance_a1.lower()
        
        guidance_n5 = judge._get_level_guidance("jlpt-n5")
        assert "simple" in guidance_n5.lower()
    
    def test_get_level_guidance_intermediate(self, mock_llm_client):
        """Test level guidance for intermediate levels."""
        judge = LLMJudge(mock_llm_client)
        
        guidance = judge._get_level_guidance("hsk3")
        assert "complex" in guidance.lower()
    
    def test_get_level_guidance_advanced(self, mock_llm_client):
        """Test level guidance for advanced levels."""
        judge = LLMJudge(mock_llm_client)
        
        guidance = judge._get_level_guidance("hsk5")
        assert "advanced" in guidance.lower() or "sophisticated" in guidance.lower()
    
    def test_inconsistency_detection_flagged(self, mock_llm_client):
        """Test inconsistency detection with large score differences."""
        judge = LLMJudge(mock_llm_client)
        
        evaluation = LLMJudgeEvaluation(
            content_id="test",
            content_type="conversation",
            naturalness=DimensionScore(score=9, explanation="Excellent naturalness in dialogue"),
            level_appropriateness=DimensionScore(score=9, explanation="Perfect level fit for learners"),
            grammatical_correctness=DimensionScore(score=9, explanation="No grammar errors detected"),
            vocabulary_diversity=DimensionScore(score=8, explanation="Good variety of words used"),
            cultural_accuracy=DimensionScore(score=9, explanation="Culturally accurate content"),
            engagement=DimensionScore(score=2, explanation="Very boring and uninteresting"),  # Inconsistent!
            overall_recommendation="review",
            recommendation_justification="High quality but low engagement"
        )
        
        judge._detect_inconsistencies(evaluation)
        
        assert evaluation.has_inconsistency is True
        assert evaluation.inconsistency_note is not None
        assert "engagement" in evaluation.inconsistency_note.lower()
        assert "9" in evaluation.inconsistency_note  # max score
        assert "2" in evaluation.inconsistency_note  # min score
    
    def test_inconsistency_detection_not_flagged(self, mock_llm_client, sample_evaluation):
        """Test inconsistency detection with consistent scores."""
        judge = LLMJudge(mock_llm_client)
        
        # All scores between 6-9, should not flag
        judge._detect_inconsistencies(sample_evaluation)
        
        assert sample_evaluation.has_inconsistency is False
        assert sample_evaluation.inconsistency_note is None
    
    def test_llm_validation_error_handling(self, mock_llm_client):
        """Test handling of LLM validation errors."""
        mock_llm_client.generate.side_effect = ValidationError.from_exception_data(
            "test", [{"type": "missing", "loc": ("field",), "msg": "field required", "input": {}}]
        )
        
        judge = LLMJudge(mock_llm_client)
        
        with pytest.raises(ValidationError):
            judge.evaluate_conversation(
                content_id="test",
                text="Test",
                language="zh",
                level="hsk1"
            )
    
    def test_llm_api_error_handling(self, mock_llm_client):
        """Test handling of LLM API errors."""
        mock_llm_client.generate.side_effect = Exception("API Error")
        
        judge = LLMJudge(mock_llm_client)
        
        with pytest.raises(Exception) as exc_info:
            judge.evaluate_conversation(
                content_id="test",
                text="Test",
                language="zh",
                level="hsk1"
            )
        
        assert "API Error" in str(exc_info.value)
    
    def test_type_specific_guidance_conversation(self, mock_llm_client):
        """Test conversation-specific guidance."""
        judge = LLMJudge(mock_llm_client)
        guidance = judge._get_type_specific_guidance("conversation")
        
        assert "speaker turns" in guidance.lower()
        assert "dialogue" in guidance.lower()
    
    def test_type_specific_guidance_story(self, mock_llm_client):
        """Test story-specific guidance."""
        judge = LLMJudge(mock_llm_client)
        guidance = judge._get_type_specific_guidance("story")
        
        assert "narrative" in guidance.lower()
        assert "beginning" in guidance.lower()
    
    def test_evaluation_metadata_override(self, mock_llm_client, sample_evaluation):
        """Test that content metadata is correctly overridden."""
        # LLM might return wrong content_id or model
        sample_evaluation.content_id = "wrong-id"
        sample_evaluation.evaluator_model = "wrong-model"
        
        mock_llm_client.generate.return_value = sample_evaluation
        
        judge = LLMJudge(mock_llm_client, model="gpt-4-turbo")
        result = judge.evaluate_conversation(
            content_id="correct-id",
            text="Test",
            language="zh",
            level="hsk1"
        )
        
        # Should be overridden with correct values
        assert result.content_id == "correct-id"
        assert result.evaluator_model == "gpt-4-turbo"
