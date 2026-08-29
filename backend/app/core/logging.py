"""Structured logging configuration for the SatQuery AI backend."""

from __future__ import annotations

import logging
import sys
from typing import Optional

from app.core.config import settings


class StructuredFormatter(logging.Formatter):
    """JSON-like structured log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return str(log_entry)


def setup_logging(level: Optional[str] = None) -> None:
    """Configure structured logging for the application."""
    log_level = getattr(logging, (level or settings.LLM_PROVIDER).upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
