"""LLM client with Instructor integration for structured responses.

This module provides a wrapper around OpenAI's API with Instructor for
structured output generation, retry logic, and request/response logging.
"""

import hashlib
import logging
import time
from typing import Any, Optional, Type, TypeVar

import instructor
from openai import OpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class LLMClient:
    """LLM client with Instructor-wrapped OpenAI for structured responses.

    Features:
    - Structured response generation with Pydantic model validation
    - Automatic retry logic (3 attempts with exponential backoff)
    - Request/response logging (prompt hash, tokens, latency)
    - Support for different OpenAI models
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
    ):
        """Initialize LLM client with Instructor.

        Args:
            api_key: OpenAI API key (if None, uses OPENAI_API_KEY env var)
            model: OpenAI model to use (default: gpt-4o-mini)
            max_retries: Maximum number of retry attempts (default: 3)
            base_delay: Base delay for exponential backoff in seconds (default: 1.0)
            max_delay: Maximum delay between retries in seconds (default: 60.0)
        """
        self.model = model
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)

        # Wrap with Instructor for structured outputs
        self.client = instructor.from_openai(client)

        logger.info(f"LLMClient initialized with model={model}, max_retries={max_retries}")

    def generate(
        self,
        prompt: str,
        response_model: Type[T],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> T:
        """Generate structured response using Pydantic model validation.

        This method automatically retries on failures with exponential backoff.

        Args:
            prompt: User prompt/instruction
            response_model: Pydantic model class for structured output
            temperature: Sampling temperature (0.0 - 2.0, default: 0.7)
            max_tokens: Maximum tokens to generate (default: None = model max)
            system_prompt: Optional system prompt for context

        Returns:
            Validated Pydantic model instance

        Raises:
            Exception: If all retry attempts fail
        """
        prompt_hash = self._hash_prompt(prompt)
        logger.info(
            f"Generating structured response: model={self.model}, "
            f"response_model={response_model.__name__}, "
            f"prompt_hash={prompt_hash}, "
            f"temperature={temperature}"
        )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        last_exception = None
        for attempt in range(1, self.max_retries + 1):
            try:
                start_time = time.time()

                # Use Instructor's structured output generation
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_model=response_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                latency_ms = (time.time() - start_time) * 1000

                # Log successful response
                self._log_response(
                    prompt_hash=prompt_hash,
                    response_model=response_model.__name__,
                    latency_ms=latency_ms,
                    attempt=attempt,
                    success=True,
                )

                return response

            except Exception as e:
                last_exception = e
                latency_ms = (time.time() - start_time) * 1000

                logger.warning(
                    f"Attempt {attempt}/{self.max_retries} failed: {str(e)[:200]}",
                    exc_info=True,
                )

                self._log_response(
                    prompt_hash=prompt_hash,
                    response_model=response_model.__name__,
                    latency_ms=latency_ms,
                    attempt=attempt,
                    success=False,
                    error=str(e)[:200],
                )

                if attempt < self.max_retries:
                    delay = self._calculate_backoff_delay(attempt)
                    logger.info(f"Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
                else:
                    logger.error(
                        f"All {self.max_retries} attempts failed for prompt_hash={prompt_hash}"
                    )

        # If we get here, all retries failed
        raise Exception(
            f"Failed to generate structured response after {self.max_retries} attempts. "
            f"Last error: {last_exception}"
        )

    def _hash_prompt(self, prompt: str) -> str:
        """Generate SHA256 hash of prompt for logging.

        Args:
            prompt: Text prompt to hash

        Returns:
            First 16 characters of SHA256 hash
        """
        return hashlib.sha256(prompt.encode()).hexdigest()[:16]

    def _calculate_backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay.

        Args:
            attempt: Current attempt number (1-indexed)

        Returns:
            Delay in seconds (capped at max_delay)
        """
        delay = self.base_delay * (2 ** (attempt - 1))
        return min(delay, self.max_delay)

    def _log_response(
        self,
        prompt_hash: str,
        response_model: str,
        latency_ms: float,
        attempt: int,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Log structured response metadata.

        Args:
            prompt_hash: Hash of the prompt
            response_model: Name of the response model
            latency_ms: Response latency in milliseconds
            attempt: Attempt number
            success: Whether the request succeeded
            error: Error message if failed
        """
        log_data = {
            "prompt_hash": prompt_hash,
            "response_model": response_model,
            "model": self.model,
            "latency_ms": round(latency_ms, 2),
            "attempt": attempt,
            "success": success,
        }

        if error:
            log_data["error"] = error

        if success:
            logger.info(f"LLM response: {log_data}")
        else:
            logger.warning(f"LLM response failed: {log_data}")
