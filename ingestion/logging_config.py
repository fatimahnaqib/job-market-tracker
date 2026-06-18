"""Shared logging configuration for the ingestion package."""

import logging
import os

_CONFIGURED = False
_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str | None = None) -> None:
    """Configure root logging once for CLI and Airflow entry points."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level = level or os.getenv("LOG_LEVEL", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format=_LOG_FORMAT,
        datefmt=_LOG_DATE_FORMAT,
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module logger, configuring handlers on first use."""
    setup_logging()
    return logging.getLogger(name)
