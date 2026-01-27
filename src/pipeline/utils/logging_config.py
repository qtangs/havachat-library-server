"""Logging configuration for pipeline with structured JSON logging.

Provides JSON-formatted logging for better parsing and analysis of pipeline execution.
"""

import json
import logging
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured log records.

    Converts log records to JSON with consistent structure:
    - timestamp: ISO 8601 UTC timestamp
    - level: Log level (INFO, WARNING, ERROR, etc.)
    - logger: Logger name
    - message: Log message
    - extra: Any additional context fields
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted log string
        """
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add any extra fields from record
        # (exclude standard logging attributes)
        standard_attrs = {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "thread",
            "threadName",
            "exc_info",
            "exc_text",
            "stack_info",
        }

        extra_fields = {
            k: v for k, v in record.__dict__.items() if k not in standard_attrs
        }

        if extra_fields:
            log_data["extra"] = extra_fields

        return json.dumps(log_data, ensure_ascii=False)


def configure_logging(
    level: Union[str, int] = logging.INFO,
    log_file: Optional[Union[str, Path]] = None,
    json_format: bool = True,
    console_output: bool = True,
) -> None:
    """Configure logging for the pipeline.

    Args:
        level: Logging level (default: INFO)
        log_file: Optional file path for log output (default: None = console only)
        json_format: If True, use JSON formatter; if False, use standard format (default: True)
        console_output: If True, log to console (default: True)

    Example:
        >>> configure_logging(
        ...     level=logging.INFO,
        ...     log_file="pipeline.log",
        ...     json_format=True,
        ... )
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Choose formatter
    if json_format:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    logging.info(f"Logging configured: level={logging.getLevelName(level)}, json_format={json_format}")


@contextmanager
def pipeline_stage_logger(stage_name: str, **context):
    """Context manager for logging pipeline stage execution.

    Logs entry and exit of pipeline stages with timing information.

    Args:
        stage_name: Name of the pipeline stage
        **context: Additional context fields to include in logs

    Yields:
        Logger instance for the stage

    Example:
        >>> with pipeline_stage_logger("vocab_enrichment", language="zh", level="HSK1") as logger:
        ...     logger.info("Processing vocabulary items")
        ...     # ... do work ...
    """
    logger = logging.getLogger(f"pipeline.{stage_name}")

    # Log stage entry
    start_time = datetime.now(UTC)
    logger.info(
        f"Starting pipeline stage: {stage_name}",
        extra={"stage": stage_name, "status": "started", **context},
    )

    try:
        yield logger

        # Log stage success
        end_time = datetime.now(UTC)
        duration_ms = (end_time - start_time).total_seconds() * 1000

        logger.info(
            f"Completed pipeline stage: {stage_name}",
            extra={
                "stage": stage_name,
                "status": "completed",
                "duration_ms": round(duration_ms, 2),
                **context,
            },
        )

    except Exception as e:
        # Log stage failure
        end_time = datetime.now(UTC)
        duration_ms = (end_time - start_time).total_seconds() * 1000

        logger.error(
            f"Failed pipeline stage: {stage_name}",
            extra={
                "stage": stage_name,
                "status": "failed",
                "duration_ms": round(duration_ms, 2),
                "error": str(e)[:200],
                **context,
            },
            exc_info=True,
        )
        raise


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing item", extra={"item_id": "123"})
    """
    return logging.getLogger(name)
