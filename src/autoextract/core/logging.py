"""Structured logging utility for AutoExtract Engine."""

import logging
import sys
from typing import Optional


def setup_logger(
    name: str = "autoextract",
    level: int = logging.INFO,
    verbose: bool = False,
) -> logging.Logger:
    """Configure and return a structured logger with formatting."""
    logger = logging.getLogger(name)

    if verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(level)

    # Avoid duplicate handlers if already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
