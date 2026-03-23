"""
Settings management for CNKI Downloader.

Reads and writes settings to/from the JSON file defined in config.py.
"""

import json
import os
from typing import Any

import config
from utils.logger import get_logger

logger = get_logger("cnki_downloader.settings")


class SettingsManager:
    """Persist and retrieve application settings using a JSON file."""

    def __init__(self, filepath: str = config.SETTINGS_FILE) -> None:
        self._filepath = filepath
        self._settings: dict = {}
        self._load()

    # ── Public API ───────────────────────────────────────────────────────────

    def get(self, key: str, fallback: Any = None) -> Any:
        """Return the value for *key*, falling back to *fallback* (then the
        compiled-in default, then *None*)."""
        if key in self._settings:
            return self._settings[key]
        return config.DEFAULT_SETTINGS.get(key, fallback)

    def set(self, key: str, value: Any) -> None:
        """Persist *key* → *value* immediately."""
        self._settings[key] = value
        self._save()

    def update(self, data: dict) -> None:
        """Merge *data* into settings and persist."""
        self._settings.update(data)
        self._save()

    def all(self) -> dict:
        """Return a merged copy of defaults + user overrides."""
        merged = dict(config.DEFAULT_SETTINGS)
        merged.update(self._settings)
        return merged

    def reset(self) -> None:
        """Reset all settings to compiled-in defaults."""
        self._settings = {}
        self._save()

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _load(self) -> None:
        dirpath = os.path.dirname(self._filepath)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        if os.path.isfile(self._filepath):
            try:
                with open(self._filepath, "r", encoding="utf-8") as fh:
                    self._settings = json.load(fh)
                logger.debug("Settings loaded from %s", self._filepath)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not read settings file: %s", exc)
                self._settings = {}
        else:
            self._settings = {}

    def _save(self) -> None:
        dirpath = os.path.dirname(self._filepath)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        try:
            with open(self._filepath, "w", encoding="utf-8") as fh:
                json.dump(self._settings, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            logger.error("Could not write settings file: %s", exc)
