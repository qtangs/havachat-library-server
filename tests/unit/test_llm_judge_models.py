"""Unit tests for LLM Judge Evaluation and Notion Mapping models."""

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from src.models.llm_judge_evaluation import DimensionScore, LLMJudgeEvaluation
from src.models.notion_mapping import NotionMapping, NotionPushQueue


class TestDimensionScore:
    """Test DimensionScore model validation."""
    
    def test_valid_dimension_score(self):
        """Test creating valid dimension score."""
        score = DimensionScore(score=8, explanation="Good naturalness with minor issues")
        assert score.score == 8
        assert len(score.explanation) > 0
    
    def test_score_out_of_range(self):
        """Test score validation (1-10 range)."""
        with pytest.raises(ValidationError):
            DimensionScore(score=0, explanation="Too low")
        
        with pytest.raises(ValidationError):
            DimensionScore(score=11, explanation="Too high")
    
    def test_explanation_too_short(self):
        """Test explanation minimum length."""
        with pytest.raises(ValidationError):
            DimensionScore(score=5, explanation="Too short")


class TestLLMJudgeEvaluation:
    """Test LLMJudgeEvaluation model and methods."""
    
    @pytest.fixture
    def sample_evaluation(self):
        """Create sample evaluation for testing."""
        return LLMJudgeEvaluation(
            content_id="test-uuid-123",
            content_type="conversation",
            naturalness=DimensionScore(score=8, explanation="Natural dialogue flow with minor awkwardness"),
            level_appropriateness=DimensionScore(score=9, explanation="Perfect for HSK1 learners"),
            grammatical_correctness=DimensionScore(score=7, explanation="Mostly correct, one minor error"),
            vocabulary_diversity=DimensionScore(score=6, explanation="Limited variety, appropriate for level"),
            cultural_accuracy=DimensionScore(score=9, explanation="Culturally appropriate scenarios"),
            engagement=DimensionScore(score=8, explanation="Interesting shopping scenario"),
            overall_recommendation="proceed",
            recommendation_justification="Strong performance across all dimensions, ready for audio generation"
        )
    
    def test_create_valid_evaluation(self, sample_evaluation):
        """Test creating valid LLM judge evaluation."""
        assert sample_evaluation.content_id == "test-uuid-123"
        assert sample_evaluation.content_type == "conversation"
        assert sample_evaluation.overall_recommendation == "proceed"
    
    def test_average_score_calculation(self, sample_evaluation):
        """Test average score calculation across 6 dimensions."""
        # Scores: 8, 9, 7, 6, 9, 8 = 47/6 ≈ 7.83
        avg = sample_evaluation.average_score()
        assert 7.8 <= avg <= 7.9
    
    def test_is_passing_threshold(self, sample_evaluation):
        """Test passing threshold check."""
        assert sample_evaluation.is_passing(threshold=7.0) is True
        assert sample_evaluation.is_passing(threshold=8.0) is False
    
    def test_to_json_string(self, sample_evaluation):
        """Test JSON serialization for Notion."""
        json_str = sample_evaluation.to_json_string()
        data = json.loads(json_str)
        
        # Should contain dimension scores
        assert "naturalness" in data
        assert data["naturalness"]["score"] == 8
        
        # Should exclude metadata fields
        assert "content_id" not in data
        assert "evaluated_at" not in data
    
    def test_invalid_recommendation(self):
        """Test invalid recommendation value."""
        with pytest.raises(ValidationError):
            LLMJudgeEvaluation(
                content_id="test",
                content_type="conversation",
                naturalness=DimensionScore(score=5, explanation="Test explanation here"),
                level_appropriateness=DimensionScore(score=5, explanation="Test explanation here"),
                grammatical_correctness=DimensionScore(score=5, explanation="Test explanation here"),
                vocabulary_diversity=DimensionScore(score=5, explanation="Test explanation here"),
                cultural_accuracy=DimensionScore(score=5, explanation="Test explanation here"),
                engagement=DimensionScore(score=5, explanation="Test explanation here"),
                overall_recommendation="maybe",  # Invalid value
                recommendation_justification="This should fail validation"
            )
    
    def test_inconsistency_flagging(self):
        """Test inconsistency detection flag."""
        eval_with_inconsistency = LLMJudgeEvaluation(
            content_id="test",
            content_type="story",
            naturalness=DimensionScore(score=9, explanation="Very natural narrative flow"),
            level_appropriateness=DimensionScore(score=8, explanation="Good level fit"),
            grammatical_correctness=DimensionScore(score=9, explanation="Excellent grammar"),
            vocabulary_diversity=DimensionScore(score=8, explanation="Good variety"),
            cultural_accuracy=DimensionScore(score=9, explanation="Culturally accurate"),
            engagement=DimensionScore(score=2, explanation="Boring, repetitive content"),  # Inconsistent!
            overall_recommendation="review",
            recommendation_justification="High quality but low engagement is concerning",
            has_inconsistency=True,
            inconsistency_note="High scores on all metrics but very low engagement score"
        )
        
        assert eval_with_inconsistency.has_inconsistency is True
        assert eval_with_inconsistency.inconsistency_note is not None


class TestNotionMapping:
    """Test NotionMapping model."""
    
    def test_create_valid_mapping(self):
        """Test creating valid Notion mapping."""
        mapping = NotionMapping(
            content_id="abc-123",
            notion_page_id="notion-xyz-789",
            language="zh",
            level="hsk1",
            type="conversation",
            title="Test Conversation",
            last_pushed_at=datetime(2026, 1, 31, 10, 30),
            status_in_notion="Not started"
        )
        
        assert mapping.content_id == "abc-123"
        assert mapping.notion_page_id == "notion-xyz-789"
        assert mapping.status_in_local == "pending_review"  # Default value
    
    def test_sync_tracking(self):
        """Test sync timestamp tracking."""
        mapping = NotionMapping(
            content_id="abc-123",
            notion_page_id="notion-xyz",
            language="fr",
            level="a1",
            type="story",
            title="Test Story",
            last_pushed_at=datetime(2026, 1, 31, 10, 0),
            last_synced_at=datetime(2026, 1, 31, 15, 0),
            status_in_notion="Ready for Audio"
        )
        
        assert mapping.last_synced_at is not None
        assert mapping.last_synced_at > mapping.last_pushed_at
    
    def test_invalid_status(self):
        """Test invalid status value."""
        with pytest.raises(ValidationError):
            NotionMapping(
                content_id="abc-123",
                notion_page_id="notion-xyz",
                language="ja",
                level="jlpt-n5",
                type="conversation",
                title="Test",
                last_pushed_at=datetime.utcnow(),
                status_in_notion="Invalid Status"  # Not in allowed list
            )


class TestNotionPushQueue:
    """Test NotionPushQueue model."""
    
    def test_create_valid_queue_entry(self):
        """Test creating valid push queue entry."""
        queue_entry = NotionPushQueue(
            content_id="abc-123",
            type="conversation",
            title="Test Conversation",
            language="zh",
            level="hsk1",
            attempt_count=2,
            last_error="Notion API rate limit exceeded",
            payload={
                "Type": "conversation",
                "Title": "Test Conversation",
                "Script": "Speaker 1: Hello..."
            }
        )
        
        assert queue_entry.content_id == "abc-123"
        assert queue_entry.attempt_count == 2
        assert "Type" in queue_entry.payload
    
    def test_retry_tracking(self):
        """Test retry attempt tracking."""
        queue_entry = NotionPushQueue(
            content_id="test",
            type="story",
            title="Test",
            language="fr",
            level="a2",
            attempt_count=3,
            last_error="Network timeout",
            payload={}
        )
        
        assert queue_entry.attempt_count == 3
        assert isinstance(queue_entry.failed_at, datetime)
    
    def test_invalid_attempt_count(self):
        """Test attempt count must be >= 1."""
        with pytest.raises(ValidationError):
            NotionPushQueue(
                content_id="test",
                type="conversation",
                title="Test",
                language="zh",
                level="hsk1",
                attempt_count=0,  # Invalid: must be >= 1
                last_error="Error",
                payload={}
            )
