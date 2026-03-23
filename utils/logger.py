"""
Logging utility for CNKI Downloader.
"""

import logging
import os

import config


def setup_logger(name: str = "cnki_downloader") -> logging.Logger:
    """Configure and return the application-wide logger."""
    logger = logging.getLogger(name)

    if logger.handlers:
        # Already configured – return as-is to avoid duplicate handlers.
        return logger

    log_level = getattr(logging, config.DEFAULT_SETTINGS.get("log_level", "INFO"), logging.INFO)
    logger.setLevel(log_level)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler – create log directory if needed
    os.makedirs(config.LOG_DIR, exist_ok=True)
    try:
        file_handler = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as exc:
        logger.warning("Could not open log file %s: %s", config.LOG_FILE, exc)

    return logger


def get_logger(name: str = "cnki_downloader") -> logging.Logger:
    """Return a child logger under the application root logger."""
    return logging.getLogger(name)
