import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

# Patterns to mask in logs
SENSITIVE_PATTERNS = [
    re.compile(r"(password=)[^&\s]+", re.IGNORECASE),
    re.compile(r"(key=)[^&\s]+", re.IGNORECASE),
    re.compile(r"(secret=)[^&\s]+", re.IGNORECASE),
    re.compile(r"(Bearer\s+)[a-zA-Z0-9_\-\.]+", re.IGNORECASE),
    re.compile(r"(Client-Secret[:=]\s*)[^\s,]+", re.IGNORECASE),
]


def mask_sensitive(text: str) -> str:
    """Mask sensitive credentials in logged strings."""
    if not isinstance(text, str):
        return str(text)
    masked = text
    for pattern in SENSITIVE_PATTERNS:
        masked = pattern.sub(r"\1***MASKED***", masked)
    return masked


class StructuredJsonFormatter(logging.Formatter):
    """Outputs log records as structured single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": mask_sensitive(record.getMessage()),
        }

        # Include standard extra attributes if attached
        if hasattr(record, "service"):
            log_entry["service"] = record.service
        if hasattr(record, "provider"):
            log_entry["provider"] = record.provider
        if hasattr(record, "run_id"):
            log_entry["run_id"] = record.run_id

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging(log_level: str = "INFO", log_json: bool = True) -> None:
    """Configures application-wide logging."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if log_json:
        handler.setFormatter(StructuredJsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
        )

    root_logger.addHandler(handler)

    # Silence overly verbose external loggers
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
