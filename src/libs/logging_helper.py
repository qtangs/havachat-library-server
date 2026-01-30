import inspect
import json
import logging
import os
import sys
import traceback
from datetime import datetime

from loguru import logger

from constants import ENV
from constants import PRODUCT

__all__ = ["logger"]


class JSONFormatter(logging.Formatter):
    def format(self, record):
        record.msg = json.dumps(
            {
                "process": f"{record.process} {record.processName}",
                "time": datetime.utcnow().isoformat(
                    sep=" ", timespec="milliseconds"
                ),
                "level": record.levelname,
                "file": record.filename,
                "line": record.lineno,
                "func": record.funcName,
                "msg": record.msg,
                **(
                    {"error_trace": traceback.format_exc()}
                    if record.levelname == "ERROR"
                    else {}
                ),
            },
        )
        return super().format(record)


class JSONMessageFormatter(logging.Formatter):
    def format(self, record):
        record.msg = "{} | {} | {} | {} | {} | {} | {} {}".format(
            datetime.utcnow().isoformat(sep=" ", timespec="milliseconds"),
            f"{record.process} {record.processName}",
            record.levelname,
            record.filename,
            record.lineno,
            record.funcName,
            (
                json.dumps(record.msg, default=pydantic_encoder)
                if isinstance(record.msg, dict)
                else record.msg
            ),
            (
                f"\n{traceback.format_exc()}"
                if record.levelname == "ERROR"
                else ""
            ),
        )
        return super().format(record)


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists.
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = inspect.currentframe(), 0
        while frame:
            filename = frame.f_code.co_filename
            is_logging = filename == logging.__file__
            is_frozen = "importlib" in filename and "_bootstrap" in filename
            if depth > 0 and not (is_logging or is_frozen):
                break
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


if ENV == "dev":
    logger.add(f"/tmp/{PRODUCT}-{ENV}.log")
logger.remove()  # Remove default configuration
if os.getenv("LOG_FORMAT") == "json":
    logger.add(sys.stdout, backtrace=True, diagnose=False, serialize=True)
else:
    logger.add(sys.stdout, backtrace=True, diagnose=False)
logger.info("Logging setup completed")

# stdout_log = logging.StreamHandler(sys.stdout)
# if os.getenv("LOG_FORMAT") == "json":
#     stdout_log.setFormatter(JSONFormatter())
# else:
#     stdout_log.setFormatter(JSONMessageFormatter())
#
# logging.basicConfig(force=True, handlers=[stdout_log])

# logger = logging.getLogger(PRODUCT)

# Configure log levels (what to filter to outputs).
# logger.setLevel(os.getenv("LOG_LEVEL", "DEBUG"))
# logging.getLogger("openai").setLevel(os.getenv("LOG_LEVEL", "DEBUG"))
