"""Unit tests for LLM client with mocked API responses."""

from unittest.mock import MagicMock, patch
import pytest
from pydantic import BaseModel, Field

from src.havachat.utils.llm_client import LLMClient


class MockResponse(BaseModel):
    """Mock response model for testing."""

    text: str = Field(..., description="Response text")
    count: int = Field(..., description="Word count")


class TestLLMClient:
    """Test LLMClient with mocked API responses."""

    @patch("src.havachat.utils.llm_client.OpenAI")
    @patch("src.havachat.utils.llm_client.instructor.from_openai")
    def test_client_initialization(self, mock_from_openai, mock_openai):
        """Test that LLMClient initializes correctly."""
        mock_instructor_client = MagicMock()
        mock_from_openai.return_value = mock_instructor_client

        client = LLMClient(api_key="test-key", model="gpt-4o")

        assert client.model == "gpt-4o"
        assert client.max_retries == 3
        assert client.base_delay == 1.0
        mock_openai.assert_called_once_with(api_key="test-key")
        mock_from_openai.assert_called_once()

    @patch("src.havachat.utils.llm_client.OpenAI")
    @patch("src.havachat.utils.llm_client.instructor.from_openai")
    def test_successful_generate(self, mock_from_openai, mock_openai):
        """Test successful structured response generation."""
        # Mock the Instructor client
        mock_instructor_client = MagicMock()
        mock_from_openai.return_value = mock_instructor_client

        # Mock successful response
        mock_response = MockResponse(text="Hello world", count=2)
        mock_instructor_client.chat.completions.create.return_value = mock_response

        client = LLMClient(api_key="test-key")
        result = client.generate(
            prompt="Generate a greeting",
            response_model=MockResponse,
            temperature=0.5,
        )

        assert result.text == "Hello world"
        assert result.count == 2
        mock_instructor_client.chat.completions.create.assert_called_once()

    @patch("src.havachat.utils.llm_client.OpenAI")
    @patch("src.havachat.utils.llm_client.instructor.from_openai")
    def test_generate_with_system_prompt(self, mock_from_openai, mock_openai):
        """Test generation with system prompt."""
        mock_instructor_client = MagicMock()
        mock_from_openai.return_value = mock_instructor_client
        mock_response = MockResponse(text="Response", count=1)
        mock_instructor_client.chat.completions.create.return_value = mock_response

        client = LLMClient(api_key="test-key")
        result = client.generate(
            prompt="User prompt",
            response_model=MockResponse,
            system_prompt="You are a helpful assistant",
        )

        # Verify system prompt was included in messages
        call_args = mock_instructor_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "User prompt"

    @patch("src.havachat.utils.llm_client.OpenAI")
    @patch("src.havachat.utils.llm_client.instructor.from_openai")
    @patch("src.havachat.utils.llm_client.time.sleep")  # Mock sleep to speed up test
    def test_retry_on_failure(self, mock_sleep, mock_from_openai, mock_openai):
        """Test retry logic on API failure."""
        mock_instructor_client = MagicMock()
        mock_from_openai.return_value = mock_instructor_client

        # First two attempts fail, third succeeds
        mock_response = MockResponse(text="Success", count=1)
        mock_instructor_client.chat.completions.create.side_effect = [
            Exception("API Error 1"),
            Exception("API Error 2"),
            mock_response,
        ]

        client = LLMClient(api_key="test-key", max_retries=3)
        result = client.generate(
            prompt="Test prompt",
            response_model=MockResponse,
        )

        assert result.text == "Success"
        assert mock_instructor_client.chat.completions.create.call_count == 3
        # Verify sleep was called twice (after first two failures)
        assert mock_sleep.call_count == 2

    @patch("src.havachat.utils.llm_client.OpenAI")
    @patch("src.havachat.utils.llm_client.instructor.from_openai")
    @patch("src.havachat.utils.llm_client.time.sleep")
    def test_all_retries_fail(self, mock_sleep, mock_from_openai, mock_openai):
        """Test that exception is raised when all retries fail."""
        mock_instructor_client = MagicMock()
        mock_from_openai.return_value = mock_instructor_client

        # All attempts fail
        mock_instructor_client.chat.completions.create.side_effect = Exception(
            "Persistent API Error"
        )

        client = LLMClient(api_key="test-key", max_retries=3)

        with pytest.raises(Exception) as exc_info:
            client.generate(
                prompt="Test prompt",
                response_model=MockResponse,
            )

        assert "Failed to generate structured response after 3 attempts" in str(
            exc_info.value
        )
        assert mock_instructor_client.chat.completions.create.call_count == 3

    def test_hash_prompt(self):
        """Test prompt hashing."""
        client = LLMClient(api_key="test-key")

        hash1 = client._hash_prompt("Hello world")
        hash2 = client._hash_prompt("Hello world")
        hash3 = client._hash_prompt("Different prompt")

        # Same prompt should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 16  # First 16 chars of SHA256

        # Different prompt should produce different hash
        assert hash1 != hash3

    def test_calculate_backoff_delay(self):
        """Test exponential backoff calculation."""
        client = LLMClient(api_key="test-key", base_delay=1.0, max_delay=10.0)

        # Exponential backoff: 1, 2, 4, 8...
        assert client._calculate_backoff_delay(1) == 1.0
        assert client._calculate_backoff_delay(2) == 2.0
        assert client._calculate_backoff_delay(3) == 4.0
        assert client._calculate_backoff_delay(4) == 8.0

        # Should cap at max_delay
        assert client._calculate_backoff_delay(5) == 10.0  # Would be 16, capped at 10
        assert client._calculate_backoff_delay(10) == 10.0  # Would be 512, capped at 10

    @patch("src.havachat.utils.llm_client.OpenAI")
    @patch("src.havachat.utils.llm_client.instructor.from_openai")
    def test_generate_with_max_tokens(self, mock_from_openai, mock_openai):
        """Test generation with max_tokens parameter."""
        mock_instructor_client = MagicMock()
        mock_from_openai.return_value = mock_instructor_client
        mock_response = MockResponse(text="Response", count=1)
        mock_instructor_client.chat.completions.create.return_value = mock_response

        client = LLMClient(api_key="test-key")
        client.generate(
            prompt="Test",
            response_model=MockResponse,
            max_tokens=100,
        )

        call_args = mock_instructor_client.chat.completions.create.call_args
        assert call_args.kwargs["max_tokens"] == 100

    @patch("src.havachat.utils.llm_client.OpenAI")
    @patch("src.havachat.utils.llm_client.instructor.from_openai")
    def test_generate_with_custom_temperature(self, mock_from_openai, mock_openai):
        """Test generation with custom temperature."""
        mock_instructor_client = MagicMock()
        mock_from_openai.return_value = mock_instructor_client
        mock_response = MockResponse(text="Response", count=1)
        mock_instructor_client.chat.completions.create.return_value = mock_response

        client = LLMClient(api_key="test-key")
        client.generate(
            prompt="Test",
            response_model=MockResponse,
            temperature=0.2,
        )

        call_args = mock_instructor_client.chat.completions.create.call_args
        assert call_args.kwargs["temperature"] == 0.2
