"""
Centralised logging configuration for the Amazon spider project.

Usage::

    from logging_config import configure_logging
    configure_logging()

    # Or explicitly name a logger:
    import logging
    logger = logging.getLogger("amazon_spider")
    logger.info("Starting crawl …")

Settings are read from environment variables:

- ``LOG_LEVEL`` — one of DEBUG / INFO / WARNING / ERROR / CRITICAL
  (default: INFO)
- ``LOG_FILE`` — path to a log file; unset → console only
"""

import logging
import os
import sys


def configure_logging(
    name: str = "amazon_spider",
    level: str | None = None,
    log_file: str | None = None,
) -> logging.Logger:
    """Set up the root logger with a console handler and optional file handler.

    Returns the named logger so callers can use it directly.
    """
    level = level or os.environ.get("LOG_LEVEL", "INFO").upper()
    log_file = log_file or os.environ.get("LOG_FILE", "")

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(getattr(logging, level, logging.INFO))
    root.handlers.clear()

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(root.level)
    console.setFormatter(fmt)
    root.addHandler(console)

    # Optional file handler
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(root.level)
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)

    return logging.getLogger(name)
