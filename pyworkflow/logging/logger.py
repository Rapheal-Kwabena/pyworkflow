"""Structured logging module for PyWorkflow, supporting console and JSON logging."""

from __future__ import annotations

import json
import logging
from typing import Any

class JSONFormatter(logging.Formatter):
    """Custom formatter to output logs as structured JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Inject custom execution context if present
        for attr in ("workflow_name", "task_name", "duration"):
            if hasattr(record, attr):
                log_data[attr] = getattr(record, attr)
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)


logger = logging.getLogger("pyworkflow")


def setup_logging(level: int = logging.INFO, use_json: bool = False) -> None:
    """Configures the package-level logger handlers and formats."""
    logger.setLevel(level)
    for h in list(logger.handlers):
        logger.removeHandler(h)

    handler = logging.StreamHandler()
    if use_json:
        handler.setFormatter(JSONFormatter())
    else:
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
    logger.addHandler(handler)
