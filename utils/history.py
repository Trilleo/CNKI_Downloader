"""
Search history management for CNKI Downloader.

History entries are stored as a JSON array in the file defined in config.py.
Each entry has the shape:

    {
        "id":        <str uuid4>,
        "timestamp": <ISO-8601 str>,
        "method":    <str search method>,
        "query":     <str query text>,
        "filters":   <dict extra filters>,
        "result_count": <int>
    }
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import config
from utils.logger import get_logger

logger = get_logger("cnki_downloader.history")


class HistoryManager:
    """Persist and retrieve search history using a JSON file."""

    def __init__(self, filepath: str = config.HISTORY_FILE) -> None:
        self._filepath = filepath
        self._entries: list[dict] = []
        self._load()

    # ── Public API ───────────────────────────────────────────────────────────

    def add(
        self,
        method: str,
        query: str,
        filters: Optional[dict] = None,
        result_count: int = 0,
    ) -> str:
        """Record a new search and return its ID."""
        entry: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": method,
            "query": query,
            "filters": filters or {},
            "result_count": result_count,
        }
        self._entries.insert(0, entry)   # most-recent first
        self._save()
        logger.debug("History entry added: %s", entry["id"])
        return entry["id"]

    def get_all(self) -> list[dict]:
        """Return all history entries (most-recent first)."""
        return list(self._entries)

    def get_by_id(self, entry_id: str) -> Optional[dict]:
        """Return a single entry by its ID, or *None* if not found."""
        for entry in self._entries:
            if entry.get("id") == entry_id:
                return entry
        return None

    def delete(self, entry_id: str) -> bool:
        """Remove the entry with *entry_id*. Returns *True* if found."""
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.get("id") != entry_id]
        if len(self._entries) < before:
            self._save()
            return True
        return False

    def clear(self) -> None:
        """Remove all history entries."""
        self._entries = []
        self._save()

    def __len__(self) -> int:
        return len(self._entries)

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _load(self) -> None:
        dirpath = os.path.dirname(self._filepath)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        if os.path.isfile(self._filepath):
            try:
                with open(self._filepath, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, list):
                    self._entries = data
                else:
                    self._entries = []
                logger.debug("Loaded %d history entries", len(self._entries))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not read history file: %s", exc)
                self._entries = []
        else:
            self._entries = []

    def _save(self) -> None:
        dirpath = os.path.dirname(self._filepath)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        try:
            with open(self._filepath, "w", encoding="utf-8") as fh:
                json.dump(self._entries, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            logger.error("Could not write history file: %s", exc)
