"""Unit tests for Pydantic schema models."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from src.pipeline.validators.schema import (
    LevelSystem,
    Category,
    ContentType,
    SegmentType,
    QuestionType,
    Difficulty,
    FailureType,
    LearningItem,
    Segment,
    ContentUnit,
    MCQOption,
    Question,
    Topic,
    Scenario,
    UsageStats,
    FlaggedItem,
    ValidationReport,
)


class TestLearningItem:
    """Test LearningItem model validation."""

    def test_valid_learning_item(self):
        """Test creating a valid learning item."""
        item = LearningItem(
            language="zh",
            category=Category.VOCAB,
            target_item="银行",
            definition_en="A financial institution",
            examples=[
                "Example 1",
                "Example 2",
                "Example 3",
            ],
            romanization="yínháng",
            level_system=LevelSystem.HSK,
            level_min="HSK1",
            level_max="HSK1",
        )
        assert item.language == "zh"
        assert item.category == Category.VOCAB
        assert len(item.examples) == 3
        assert item.id is not None  # UUID generated

    def test_learning_item_invalid_language_code(self):
        """Test that invalid language code raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            LearningItem(
                language="zhn",  # Invalid: 3 chars
                category=Category.VOCAB,
                target_item="test",
                definition_en="test",
                examples=["1", "2", "3"],
                level_system=LevelSystem.HSK,
                level_min="HSK1",
                level_max="HSK1",
            )
        assert "language" in str(exc_info.value)

    def test_learning_item_examples_too_few(self):
        """Test that fewer than 3 examples raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            LearningItem(
                language="zh",
                category=Category.VOCAB,
                target_item="test",
                definition_en="test",
                examples=["1", "2"],  # Only 2
                level_system=LevelSystem.HSK,
                level_min="HSK1",
                level_max="HSK1",
            )
        assert "examples" in str(exc_info.value).lower()

    def test_learning_item_examples_too_many(self):
        """Test that more than 5 examples raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            LearningItem(
                language="zh",
                category=Category.VOCAB,
                target_item="test",
                definition_en="test",
                examples=["1", "2", "3", "4", "5", "6"],  # 6 examples
                level_system=LevelSystem.HSK,
                level_min="HSK1",
                level_max="HSK1",
            )
        assert "examples" in str(exc_info.value).lower()

    def test_learning_item_optional_fields(self):
        """Test that optional fields work correctly."""
        item = LearningItem(
            language="ja",
            category=Category.GRAMMAR,
            target_item="は",
            definition_en="Topic marker particle",
            examples=["Example 1", "Example 2", "Example 3"],
            romanization="wa",
            sense_gloss_en="topic marker",
            lemma="は",
            pos="particle",
            aliases=["ha"],
            level_system=LevelSystem.JLPT,
            level_min="N5",
            level_max="N5",
        )
        assert item.romanization == "wa"
        assert item.sense_gloss_en == "topic marker"
        assert item.lemma == "は"
        assert item.pos == "particle"
        assert "ha" in item.aliases


class TestSegment:
    """Test Segment model validation."""

    def test_valid_dialogue_segment(self):
        """Test creating a valid dialogue segment."""
        segment = Segment(
            segment_id="seg-1",
            type=SegmentType.DIALOGUE,
            speaker="Alice",
            text="Bonjour!",
            translation_en="Hello!",
            learning_item_ids=["550e8400-e29b-41d4-a716-446655440000"],
        )
        assert segment.segment_id == "seg-1"
        assert segment.type == SegmentType.DIALOGUE
        assert segment.speaker == "Alice"

    def test_valid_narration_segment(self):
        """Test creating a valid narration segment without speaker."""
        segment = Segment(
            segment_id="seg-2",
            type=SegmentType.NARRATION,
            speaker=None,
            text="Once upon a time...",
            learning_item_ids=["550e8400-e29b-41d4-a716-446655440000"],
        )
        assert segment.type == SegmentType.NARRATION
        assert segment.speaker is None


class TestContentUnit:
    """Test ContentUnit model validation."""

    def test_valid_content_unit(self):
        """Test creating a valid content unit."""
        segment = Segment(
            segment_id="seg-1",
            type=SegmentType.DIALOGUE,
            speaker="Alice",
            text="Bonjour!",
            learning_item_ids=["550e8400-e29b-41d4-a716-446655440001"],
        )
        content = ContentUnit(
            language="fr",
            type=ContentType.CONVERSATION,
            title="Greeting",
            description="A simple greeting",
            text="Bonjour!",
            segments=[segment],
            learning_item_ids=["550e8400-e29b-41d4-a716-446655440001"],
            level_system=LevelSystem.CEFR,
            level_min="A1",
            level_max="A1",
            word_count=1,
            estimated_reading_time_seconds=5,
        )
        assert content.language == "fr"
        assert len(content.segments) == 1
        assert content.has_audio is False
        assert content.publishable is False

    def test_content_unit_missing_learning_item_ids(self):
        """Test that segments with IDs not in content list raise error."""
        segment = Segment(
            segment_id="seg-1",
            type=SegmentType.DIALOGUE,
            speaker="Alice",
            text="Bonjour!",
            learning_item_ids=["550e8400-e29b-41d4-a716-446655440001"],
        )
        with pytest.raises(ValidationError) as exc_info:
            ContentUnit(
                language="fr",
                type=ContentType.CONVERSATION,
                title="Greeting",
                description="A simple greeting",
                text="Bonjour!",
                segments=[segment],
                learning_item_ids=[],  # Missing the ID from segment
                level_system=LevelSystem.CEFR,
                level_min="A1",
                level_max="A1",
                word_count=1,
                estimated_reading_time_seconds=5,
            )
        assert "learning_item_ids" in str(exc_info.value).lower()

    def test_content_unit_audio_without_timestamps(self):
        """Test that has_audio=true requires timestamps on all segments."""
        segment = Segment(
            segment_id="seg-1",
            type=SegmentType.DIALOGUE,
            speaker="Alice",
            text="Bonjour!",
            learning_item_ids=["550e8400-e29b-41d4-a716-446655440001"],
            # Missing start_time_ms and end_time_ms
        )
        with pytest.raises(ValidationError) as exc_info:
            ContentUnit(
                language="fr",
                type=ContentType.CONVERSATION,
                title="Greeting",
                description="A simple greeting",
                text="Bonjour!",
                segments=[segment],
                learning_item_ids=["550e8400-e29b-41d4-a716-446655440001"],
                level_system=LevelSystem.CEFR,
                level_min="A1",
                level_max="A1",
                word_count=1,
                estimated_reading_time_seconds=5,
                has_audio=True,  # Requires timestamps
            )
        assert "timestamps" in str(exc_info.value).lower()

    def test_content_unit_with_valid_audio_timestamps(self):
        """Test that has_audio=true works with valid timestamps."""
        segment = Segment(
            segment_id="seg-1",
            type=SegmentType.DIALOGUE,
            speaker="Alice",
            text="Bonjour!",
            learning_item_ids=["550e8400-e29b-41d4-a716-446655440001"],
            start_time_ms=0,
            end_time_ms=1000,
        )
        content = ContentUnit(
            language="fr",
            type=ContentType.CONVERSATION,
            title="Greeting",
            description="A simple greeting",
            text="Bonjour!",
            segments=[segment],
            learning_item_ids=["550e8400-e29b-41d4-a716-446655440001"],
            level_system=LevelSystem.CEFR,
            level_min="A1",
            level_max="A1",
            word_count=1,
            estimated_reading_time_seconds=5,
            has_audio=True,
        )
        assert content.has_audio is True
        assert content.segments[0].start_time_ms == 0


class TestMCQOption:
    """Test MCQOption model validation."""

    def test_valid_mcq_option(self):
        """Test creating a valid MCQ option."""
        option = MCQOption(option_id="A", text="Paris")
        assert option.option_id == "A"
        assert option.text == "Paris"

    def test_invalid_mcq_option_id(self):
        """Test that invalid option_id raises validation error."""
        with pytest.raises(ValidationError):
            MCQOption(option_id="E", text="Invalid")  # Only A-D allowed


class TestQuestion:
    """Test Question model validation."""

    def test_valid_mcq_question(self):
        """Test creating a valid MCQ question."""
        question = Question(
            content_id="650e8400-e29b-41d4-a716-446655440000",
            question_type=QuestionType.MCQ,
            question_text="What is the capital of France?",
            options=[
                MCQOption(option_id="A", text="Paris"),
                MCQOption(option_id="B", text="London"),
                MCQOption(option_id="C", text="Berlin"),
                MCQOption(option_id="D", text="Madrid"),
            ],
            answer_key="A",
            rationale="Paris is the capital of France.",
            difficulty=Difficulty.EASY,
            tags=["detail"],
        )
        assert question.question_type == QuestionType.MCQ
        assert len(question.options) == 4
        assert question.answer_key == "A"

    def test_mcq_question_wrong_option_count(self):
        """Test that MCQ with != 4 options raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            Question(
                content_id="650e8400-e29b-41d4-a716-446655440000",
                question_type=QuestionType.MCQ,
                question_text="Test?",
                options=[
                    MCQOption(option_id="A", text="A"),
                    MCQOption(option_id="B", text="B"),
                ],  # Only 2 options
                answer_key="A",
                rationale="Test",
                difficulty=Difficulty.EASY,
                tags=["detail"],
            )
        assert "4 options" in str(exc_info.value)

    def test_mcq_question_invalid_answer_key(self):
        """Test that MCQ with invalid answer_key raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            Question(
                content_id="650e8400-e29b-41d4-a716-446655440000",
                question_type=QuestionType.MCQ,
                question_text="Test?",
                options=[
                    MCQOption(option_id="A", text="A"),
                    MCQOption(option_id="B", text="B"),
                    MCQOption(option_id="C", text="C"),
                    MCQOption(option_id="D", text="D"),
                ],
                answer_key="E",  # Invalid
                rationale="Test",
                difficulty=Difficulty.EASY,
                tags=["detail"],
            )
        assert "answer_key" in str(exc_info.value).lower()

    def test_valid_true_false_question(self):
        """Test creating a valid true/false question."""
        question = Question(
            content_id="650e8400-e29b-41d4-a716-446655440000",
            question_type=QuestionType.TRUE_FALSE,
            question_text="Paris is the capital of France.",
            options=None,
            answer_key="true",
            rationale="This is a fact.",
            difficulty=Difficulty.EASY,
            tags=["detail"],
        )
        assert question.question_type == QuestionType.TRUE_FALSE
        assert question.options is None
        assert question.answer_key == "true"

    def test_true_false_with_options_raises_error(self):
        """Test that true/false questions with options raise validation error."""
        with pytest.raises(ValidationError) as exc_info:
            Question(
                content_id="650e8400-e29b-41d4-a716-446655440000",
                question_type=QuestionType.TRUE_FALSE,
                question_text="Test?",
                options=[MCQOption(option_id="A", text="True")],  # Should be None
                answer_key="true",
                rationale="Test",
                difficulty=Difficulty.EASY,
                tags=["detail"],
            )
        assert "must not have options" in str(exc_info.value).lower()


class TestTopic:
    """Test Topic model validation."""

    def test_valid_topic(self):
        """Test creating a valid topic."""
        topic = Topic(
            id="food",
            name_en="Food & Dining",
            aliases=["cuisine", "eating"],
        )
        assert topic.id == "food"
        assert topic.name_en == "Food & Dining"
        assert len(topic.aliases) == 2
        assert topic.language is None


class TestScenario:
    """Test Scenario model validation."""

    def test_valid_scenario(self):
        """Test creating a valid scenario."""
        scenario = Scenario(
            id="ordering-at-restaurant",
            name_en="Ordering Food at a Restaurant",
            topic_id="food",
            description="Interacting with a server to order food",
            formality="informal",
            setting="public",
        )
        assert scenario.id == "ordering-at-restaurant"
        assert scenario.topic_id == "food"
        assert scenario.formality == "informal"
        assert scenario.usage_count == 0  # Default value


class TestUsageStats:
    """Test UsageStats model validation."""

    def test_valid_usage_stats(self):
        """Test creating valid usage stats."""
        stats = UsageStats(
            learning_item_id="550e8400-e29b-41d4-a716-446655440000",
            appearances_count=5,
            last_used_content_id="650e8400-e29b-41d4-a716-446655440000",
        )
        assert stats.learning_item_id == "550e8400-e29b-41d4-a716-446655440000"
        assert stats.appearances_count == 5
        assert stats.last_updated is not None


class TestFlaggedItem:
    """Test FlaggedItem model validation."""

    def test_valid_flagged_item(self):
        """Test creating a valid flagged item."""
        item = FlaggedItem(
            item_id="550e8400-e29b-41d4-a716-446655440000",
            item_type="learning_item",
            failure_type=FailureType.DUPLICATION,
            failure_reason="Duplicate target_item",
        )
        assert item.item_id == "550e8400-e29b-41d4-a716-446655440000"
        assert item.failure_type == FailureType.DUPLICATION


class TestValidationReport:
    """Test ValidationReport model validation."""

    def test_valid_validation_report(self):
        """Test creating a valid validation report."""
        flagged = FlaggedItem(
            item_id="550e8400-e29b-41d4-a716-446655440000",
            item_type="learning_item",
            failure_type=FailureType.DUPLICATION,
            failure_reason="Duplicate target_item",
        )
        report = ValidationReport(
            language="fr",
            level="A1",
            total_items=100,
            passed_count=95,
            failed_count=5,
            flagged_items=[flagged],
            summary_stats={
                "pass_rate_percent": 95,
                "most_common_failures": ["duplication"],
            },
        )
        assert report.language == "fr"
        assert report.total_items == 100
        assert report.passed_count == 95
        assert len(report.flagged_items) == 1
        assert report.batch_id is not None  # UUID generated


class TestEnums:
    """Test enum values."""

    def test_level_system_enum(self):
        """Test LevelSystem enum values."""
        assert LevelSystem.CEFR.value == "cefr"
        assert LevelSystem.HSK.value == "hsk"
        assert LevelSystem.JLPT.value == "jlpt"

    def test_category_enum(self):
        """Test Category enum has all 12 types."""
        categories = [e.value for e in Category]
        assert len(categories) == 12
        assert "vocab" in categories
        assert "grammar" in categories
        assert "pronunciation" in categories

    def test_content_type_enum(self):
        """Test ContentType enum values."""
        assert ContentType.CONVERSATION.value == "conversation"
        assert ContentType.STORY.value == "story"

    def test_question_type_enum(self):
        """Test QuestionType enum values."""
        assert QuestionType.MCQ.value == "mcq"
        assert QuestionType.TRUE_FALSE.value == "true_false"
        assert QuestionType.SHORT_ANSWER.value == "short_answer"

    def test_failure_type_enum(self):
        """Test FailureType enum has all gate types."""
        failures = [e.value for e in FailureType]
        assert "presence_check" in failures
        assert "duplication" in failures
        assert "link_correctness" in failures
        assert "answerability" in failures
