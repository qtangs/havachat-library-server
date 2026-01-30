"""Base enricher abstract class for all enrichment pipeline stages.

Provides common functionality:
- Abstract methods for parsing, enrichment, and validation
- Retry logic with exponential backoff
- Manual review queue management
- Structured logging
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

from pydantic import BaseModel, ValidationError

from src.pipeline.utils.file_io import write_json
from src.pipeline.utils.llm_client import LLMClient

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class BaseEnricher(ABC):
    """Abstract base class for content enrichers.

    Subclasses must implement:
    - parse_source(): Read and parse input files
    - detect_missing_fields(): Identify fields requiring enrichment
    - build_prompt(): Construct LLM prompts for enrichment
    - validate_output(): Validate enriched content
    - system_prompt (property): System prompt for LLM context

    Provides:
    - Common retry loop logic
    - Manual review queue management
    - LLM client integration
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient],
        max_retries: int = 3,
        manual_review_dir: Optional[Union[str, Path]] = None,
        skip_llm: bool = False,
        skip_translation: bool = False,
    ):
        """Initialize base enricher.

        Args:
            llm_client: LLM client for structured response generation (None for dry-run)
            max_retries: Maximum retry attempts for failed enrichments (default: 3)
            manual_review_dir: Directory for manual review queue files (default: None)
            skip_llm: Skip LLM enrichment, only generate structure with UUIDs (default: False)
            skip_translation: Skip translation service calls (default: False)
        """
        self.llm_client = llm_client
        self.max_retries = max_retries
        self.manual_review_dir = Path(manual_review_dir) if manual_review_dir else None
        self.skip_llm = skip_llm
        self.skip_translation = skip_translation

        if self.manual_review_dir:
            self.manual_review_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"{self.__class__.__name__} initialized: max_retries={max_retries}"
        )
    
    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt for LLM context.
        
        Returns:
            System prompt string with instructions and guidelines
        """
        pass

    @abstractmethod
    def parse_source(self, source_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """Parse source file and return list of items to enrich.

        Args:
            source_path: Path to source file (TSV, CSV, JSON, markdown, etc.)

        Returns:
            List of dictionaries, each representing an item to process

        Example:
            [
                {"word": "银行", "pos": "noun"},
                {"word": "学校", "pos": "noun"},
            ]
        """
        pass

    @abstractmethod
    def detect_missing_fields(self, item: Dict[str, Any]) -> List[str]:
        """Detect which fields are missing or need enrichment.

        Args:
            item: Item dictionary from parse_source()

        Returns:
            List of field names that need enrichment

        Example:
            ["romanization", "definition", "examples"]
        """
        pass

    @abstractmethod
    def build_prompt(
        self,
        item: Dict[str, Any],
        missing_fields: List[str],
    ) -> str:
        """Build LLM prompt for enriching missing fields.

        Args:
            item: Item dictionary
            missing_fields: List of fields to enrich

        Returns:
            Formatted prompt string for LLM

        Example:
            "Enrich the following Chinese word with pinyin, English explanation,
            and 2-3 usage examples:\n\nWord: 银行\nPart of speech: noun"
        """
        pass

    @abstractmethod
    def validate_output(
        self,
        item: Dict[str, Any],
        enriched_data: BaseModel,
    ) -> bool:
        """Validate enriched output meets requirements.

        Args:
            item: Original item dictionary
            enriched_data: Enriched Pydantic model instance

        Returns:
            True if validation passes, False otherwise

        Example validation checks:
        - Chinese/Japanese items must have romanization
        - Examples list has 2-3 items
        - No prohibited content
        """
        pass

    @abstractmethod
    def enrich_item(
        self,
        item: Dict[str, Any],
        response_model: Type[T],
        system_prompt: Optional[str] = None,
    ) -> Optional[T]:
        """
        Enrich a single item with retry logic.
        """

    #     This method orchestrates the enrichment process:
    #     1. Detect missing fields
    #     2. Build prompt if enrichment needed
    #     3. Call LLM with retry logic
    #     4. Validate output
    #     5. Add to manual review queue if all retries fail

    #     Args:
    #         item: Item dictionary to enrich
    #         response_model: Pydantic model class for structured output
    #         system_prompt: Optional system prompt override (defaults to self.system_prompt)

    #     Returns:
    #         Enriched Pydantic model instance, or None if all retries failed
    #     """
    #     # Use enricher's system prompt if not provided
    #     if system_prompt is None:
    #         system_prompt = self.system_prompt
        
    #     # Detect missing fields
    #     missing_fields = self.detect_missing_fields(item)

    #     if not missing_fields:
    #         logger.debug(f"Item already complete, skipping enrichment: {item}")
    #         return None

    #     logger.info(
    #         f"Enriching item with missing fields: {missing_fields}",
    #         extra={"item_preview": str(item)[:100], "missing_fields": missing_fields},
    #     )

    #     # Build prompt
    #     prompt = self.build_prompt(item, missing_fields)

    #     # Retry loop
    #     for attempt in range(1, self.max_retries + 1):
    #         try:
    #             # Call LLM with structured output
    #             enriched_data = self.llm_client.generate(
    #                 prompt=prompt,
    #                 response_model=response_model,
    #                 system_prompt=system_prompt,
    #             )

    #             # Validate output
    #             if self.validate_output(item, enriched_data):
    #                 logger.info(
    #                     f"Successfully enriched item on attempt {attempt}",
    #                     extra={"attempt": attempt},
    #                 )
    #                 logger.info(
    #                     f"enriched_data: {enriched_data}",
    #                     extra={"enriched_data": enriched_data.model_dump_json()},
    #                 )
    #                 return enriched_data
    #             else:
    #                 logger.warning(
    #                     f"Validation failed on attempt {attempt}",
    #                     extra={"attempt": attempt, "item": item},
    #                 )

    #         except ValidationError as e:
    #             logger.warning(
    #                 f"Pydantic validation error on attempt {attempt}: {str(e)[:200]}",
    #                 extra={"attempt": attempt},
    #             )

    #         except Exception as e:
    #             logger.warning(
    #                 f"Enrichment error on attempt {attempt}: {str(e)[:200]}",
    #                 extra={"attempt": attempt},
    #                 exc_info=True,
    #             )

    #         # If not last attempt, continue to retry
    #         if attempt < self.max_retries:
    #             logger.info(f"Retrying... (attempt {attempt + 1}/{self.max_retries})")

    #     # All retries failed - add to manual review queue
    #     logger.error(
    #         f"All {self.max_retries} enrichment attempts failed",
    #         extra={"item": item, "missing_fields": missing_fields},
    #     )

    #     self.add_to_manual_review(item, missing_fields, "All retry attempts failed")

    #     return None

    def add_to_manual_review(
        self,
        item: Dict[str, Any],
        missing_fields: List[str],
        reason: str,
    ) -> None:
        """Add failed item to manual review queue.

        Creates a JSON file with item details for manual processing.

        Args:
            item: Original item dictionary
            missing_fields: Fields that failed to enrich
            reason: Failure reason description
        """
        if not self.manual_review_dir:
            logger.warning("No manual review directory configured, skipping queue write")
            return

        # Create review record
        review_record = {
            "item": item,
            "missing_fields": missing_fields,
            "reason": reason,
            "enricher_class": self.__class__.__name__,
        }

        # Generate filename (use first available identifier)
        item_id = (
            item.get("id")
            or item.get("word")
            or item.get("target_item")
            or f"item_{hash(str(item))}"
        )
        filename = f"review_{item_id}.json"
        output_path = self.manual_review_dir / filename

        # Write to manual review queue
        write_json(review_record, output_path)

        logger.info(
            f"Added item to manual review queue: {output_path}",
            extra={"item_id": item_id, "reason": reason},
        )

    def batch_enrich(
        self,
        items: List[Dict[str, Any]],
        response_model: Type[T],
        system_prompt: Optional[str] = None,
    ) -> List[T]:
        """Enrich a batch of items.

        Args:
            items: List of item dictionaries to enrich
            response_model: Pydantic model class for structured output
            system_prompt: Optional system prompt for LLM

        Returns:
            List of successfully enriched Pydantic model instances
        """
        enriched_items = []
        failed_count = 0

        logger.info(f"Starting batch enrichment: {len(items)} items")

        for i, item in enumerate(items, 1):
            logger.debug(f"Processing item {i}/{len(items)}")

            try:
                result = self.enrich_item(item, response_model, system_prompt)

                if result:
                    enriched_items.append(result)
                else:
                    failed_count += 1

            except Exception as e:
                logger.error(
                    f"Unexpected error processing item {i}: {str(e)[:200]}",
                    exc_info=True,
                )
                failed_count += 1

        logger.info(
            f"Batch enrichment complete: {len(enriched_items)} succeeded, {failed_count} failed",
            extra={
                "total": len(items),
                "succeeded": len(enriched_items),
                "failed": failed_count,
            },
        )

        return enriched_items
