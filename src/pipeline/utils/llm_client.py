"""LLM client with Instructor integration for structured responses.

This module provides a wrapper around OpenAI's API with Instructor for
structured output generation, retry logic, and request/response logging.
"""

import hashlib
import logging
import os
import time
from typing import Any, Optional, Type, TypeVar

import instructor
from openai import OpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class TokenUsage(BaseModel):
    """Token usage statistics."""
    
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0  # Prompt cache hits


class LLMClient:
    """LLM client with Instructor-wrapped OpenAI for structured responses.

    Features:
    - Structured response generation with Pydantic model validation
    - Automatic retry logic (3 attempts with exponential backoff)
    - Prompt caching support (OpenAI automatic caching)
    - Token usage tracking and cost estimation
    - Request/response logging (prompt hash, tokens, latency)
    - Support for different OpenAI models
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
    ):
        """Initialize LLM client with Instructor.

        Args:
            api_key: OpenAI API key (if None, uses OPENAI_API_KEY env var)
            model: OpenAI model to use (if None, uses LLM_MODEL env var or defaults to gpt-4o-mini)
            max_retries: Maximum number of retry attempts (default: 3)
            base_delay: Base delay for exponential backoff in seconds (default: 1.0)
            max_delay: Maximum delay between retries in seconds (default: 60.0)
        """
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        
        # Token tracking
        self.total_usage = TokenUsage()

        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)

        # Wrap with Instructor for structured outputs
        self.client = instructor.from_openai(client)

        logger.info(f"LLMClient initialized with model={self.model}, max_retries={max_retries}")

    def generate(
        self,
        prompt: str,
        response_model: Type[T],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_prompt: Optional[str] = None,
        use_cache: bool = True,
    ) -> T:
        """Generate structured response using Pydantic model validation.

        This method automatically retries on failures with exponential backoff.
        Supports OpenAI prompt caching for repeated system prompts.

        Args:
            prompt: User prompt/instruction
            response_model: Pydantic model class for structured output
            temperature: Sampling temperature (0.0 - 2.0, default: 0.7)
            max_tokens: Maximum tokens to generate (default: 2048)
            system_prompt: Optional system prompt for context (cached if use_cache=True)
            use_cache: Enable prompt caching for system_prompt (default: True)

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
            # OpenAI automatically caches system messages that are:
            # - Longer than 1024 tokens
            # - Reused within a short time window
            # See: https://platform.openai.com/docs/guides/prompt-caching
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        last_exception = None
        for attempt in range(1, self.max_retries + 1):
            try:
                start_time = time.time()

                # Prepare API parameters
                api_params = {
                    "model": self.model,
                    "messages": messages,
                    "response_model": response_model,
                    "temperature": temperature,
                }
                
                # GPT-5 models use max_completion_tokens instead of max_tokens
                # and only the default temperature (1) is supported
                if self.model.startswith("gpt-5"):
                    api_params["max_completion_tokens"] = max_tokens
                    api_params["temperature"] = 1.0
                else:
                    api_params["max_tokens"] = max_tokens

                # Use Instructor's structured output generation
                response = self.client.chat.completions.create(**api_params)

                latency_ms = (time.time() - start_time) * 1000

                # Track token usage
                usage = self._extract_usage(response)
                self._update_total_usage(usage)

                # Log successful response
                self._log_response(
                    prompt_hash=prompt_hash,
                    response_model=response_model.__name__,
                    latency_ms=latency_ms,
                    attempt=attempt,
                    success=True,
                    usage=usage,
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

    def _extract_usage(self, response: T) -> TokenUsage:
        """Extract token usage from response.

        Args:
            response: Pydantic model response from Instructor

        Returns:
            TokenUsage object with token counts
        """
        usage = TokenUsage()
        
        # Try to get usage from _raw_response attribute (Instructor stores it)
        if hasattr(response, "_raw_response") and hasattr(response._raw_response, "usage"):
            raw_usage = response._raw_response.usage
            usage.prompt_tokens = getattr(raw_usage, "prompt_tokens", 0)
            usage.completion_tokens = getattr(raw_usage, "completion_tokens", 0)
            usage.total_tokens = getattr(raw_usage, "total_tokens", 0)
            
            # Check for cached tokens (OpenAI returns this in usage)
            if hasattr(raw_usage, "prompt_tokens_details"):
                details = raw_usage.prompt_tokens_details
                usage.cached_tokens = getattr(details, "cached_tokens", 0)
        
        return usage
    
    def _update_total_usage(self, usage: TokenUsage) -> None:
        """Update cumulative token usage.

        Args:
            usage: Token usage from current request
        """
        self.total_usage.prompt_tokens += usage.prompt_tokens
        self.total_usage.completion_tokens += usage.completion_tokens
        self.total_usage.total_tokens += usage.total_tokens
        self.total_usage.cached_tokens += usage.cached_tokens
    
    def get_usage_summary(self) -> dict:
        """Get summary of total token usage.

        Returns:
            Dictionary with usage stats and cost estimates
        """
        # Cost estimates (per 1M tokens)
        # https://openai.com/api/pricing/
        costs = {
            "gpt-4.1-nano": {"input": 0.1, "output": 0.4, "cached": 0.025},
            "gpt-4.1-mini": {"input": 0.4, "output": 1.6, "cached": 0.1},
            "gpt-4.1": {"input": 2, "output": 8, "cached": 0.5},
            "gpt-5-mini": {"input": 0.25, "output": 2, "cached": 0.025},
            "gpt-5.2": {"input": 1.75, "output": 14, "cached": 0.175},
            "claude-sonnet-4.5": {"input": 3, "output": 15, "cached": 1.5},
            "google/gemini-3-pro-preview": {"input": 2, "output": 12, "cached": 1},
        }
        
        model_cost = costs.get(self.model, costs["gpt-4.1-mini"])
        
        # Calculate costs (cached tokens cost 50% less)
        uncached_prompt = self.total_usage.prompt_tokens - self.total_usage.cached_tokens
        input_cost = (uncached_prompt * model_cost["input"] + 
                     self.total_usage.cached_tokens * model_cost["cached"]) / 1_000_000
        output_cost = self.total_usage.completion_tokens * model_cost["output"] / 1_000_000
        
        return {
            "model": self.model,
            "prompt_tokens": self.total_usage.prompt_tokens,
            "completion_tokens": self.total_usage.completion_tokens,
            "total_tokens": self.total_usage.total_tokens,
            "cached_tokens": self.total_usage.cached_tokens,
            "cache_hit_rate": (
                f"{self.total_usage.cached_tokens / self.total_usage.prompt_tokens * 100:.1f}%"
                if self.total_usage.prompt_tokens > 0 else "0.0%"
            ),
            "estimated_cost_usd": round(input_cost + output_cost, 4),
            "input_cost_usd": round(input_cost, 4),
            "output_cost_usd": round(output_cost, 4),
        }
    
    def reset_usage(self) -> None:
        """Reset token usage counters."""
        self.total_usage = TokenUsage()

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
        usage: Optional[TokenUsage] = None,
        error: Optional[str] = None,
    ) -> None:
        """Log structured response metadata.

        Args:
            prompt_hash: Hash of the prompt
            response_model: Name of the response model
            latency_ms: Response latency in milliseconds
            attempt: Attempt number
            success: Whether the request succeeded
            usage: Token usage statistics
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
        
        if usage:
            log_data["tokens"] = {
                "prompt": usage.prompt_tokens,
                "completion": usage.completion_tokens,
                "total": usage.total_tokens,
                "cached": usage.cached_tokens,
            }

        if error:
            log_data["error"] = error

        if success:
            logger.info(f"LLM response: {log_data}")
        else:
            logger.warning(f"LLM response failed: {log_data}")
