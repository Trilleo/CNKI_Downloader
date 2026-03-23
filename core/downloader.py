"""
Download manager for CNKI Downloader.

Downloads run on a dedicated background thread so the UI stays responsive.
Progress is communicated back to the UI via Qt signals attached to
``DownloadWorker``.
"""

import os
import re
import time
from typing import Optional

import requests
from selenium.common.exceptions import WebDriverException

from PyQt6.QtCore import QObject, QThread, pyqtSignal

import config
from utils.logger import get_logger

logger = get_logger("cnki_downloader.downloader")


def _safe_filename(name: str, fallback: str = "paper") -> str:
    """Strip characters that are invalid in file-system names."""
    safe = re.sub(r'[\\/:*?"<>|]', "_", name).strip()
    return safe[:120] or fallback  # keep filenames reasonable


class DownloadWorker(QObject):
    """
    Qt worker that downloads a list of papers.

    Signals
    -------
    progress(current: int, total: int, filename: str)
        Emitted after each file finishes (successfully or not).
    file_done(index: int, success: bool, path: str)
        Emitted when a single download completes.
    all_done(success_count: int, fail_count: int)
        Emitted once all downloads have been attempted.
    error(message: str)
        Emitted on an unrecoverable error.
    """

    progress = pyqtSignal(int, int, str)
    file_done = pyqtSignal(int, bool, str)
    all_done = pyqtSignal(int, int)
    error = pyqtSignal(str)

    def __init__(
        self,
        papers: list,          # list[PaperMetadata]
        auth_manager,
        scraper,
        download_dir: str,
    ) -> None:
        super().__init__()
        self._papers = papers
        self._auth = auth_manager
        self._scraper = scraper
        self._download_dir = download_dir
        self._cancelled = False

    # ── Public API ───────────────────────────────────────────────────────────

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        """Called by the owning QThread's ``started`` signal."""
        total = len(self._papers)
        success_count = 0
        fail_count = 0

        for index, paper in enumerate(self._papers):
            if self._cancelled:
                logger.info("Download cancelled by user")
                break

            filename = _safe_filename(paper.title or f"paper_{index + 1}") + ".pdf"
            dest_path = os.path.join(self._download_dir, filename)

            try:
                ok = self._download_one(paper, dest_path)
            except Exception as exc:
                logger.error("Unexpected error downloading '%s': %s", paper.title, exc)
                ok = False

            if ok:
                success_count += 1
            else:
                fail_count += 1

            self.progress.emit(index + 1, total, filename)
            self.file_done.emit(index, ok, dest_path if ok else "")

        self.all_done.emit(success_count, fail_count)

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _download_one(self, paper, dest_path: str) -> bool:
        dirpath = os.path.dirname(dest_path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)

        # Retrieve the download URL if not already present
        dl_url = paper.download_url
        if not dl_url and paper.detail_url:
            dl_url = self._scraper.get_download_url(paper)
            paper.download_url = dl_url

        if not dl_url:
            logger.warning("No download URL for '%s'", paper.title)
            return False

        # Get cookies from the Selenium session to authenticate the request
        cookies = {}
        driver = self._auth.driver
        if driver:
            try:
                for cookie in driver.get_cookies():
                    cookies[cookie["name"]] = cookie["value"]
            except WebDriverException:
                pass

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": config.CNKI_BASE_URL,
        }

        try:
            with requests.get(
                dl_url,
                headers=headers,
                cookies=cookies,
                stream=True,
                timeout=config.DOWNLOAD_TIMEOUT,
            ) as resp:
                resp.raise_for_status()
                content_type = resp.headers.get("Content-Type", "")
                if "pdf" not in content_type and "octet-stream" not in content_type:
                    logger.warning(
                        "Unexpected content type '%s' for '%s'", content_type, paper.title
                    )
                with open(dest_path, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if self._cancelled:
                            return False
                        fh.write(chunk)

            logger.info("Downloaded: %s", dest_path)
            return True
        except requests.RequestException as exc:
            logger.error("Download failed for '%s': %s", paper.title, exc)
            # Remove partial file
            if os.path.exists(dest_path):
                try:
                    os.remove(dest_path)
                except OSError:
                    pass
            return False


class DownloadManager:
    """High-level helper that creates and manages ``DownloadWorker`` threads."""

    def __init__(self, auth_manager, scraper, settings) -> None:
        self._auth = auth_manager
        self._scraper = scraper
        self._settings = settings
        self._thread: Optional[QThread] = None
        self._worker: Optional[DownloadWorker] = None

    # ── Public API ───────────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def start(self, papers: list, callbacks: dict) -> None:
        """
        Start downloading *papers* in a background thread.

        *callbacks* is a dict with optional keys:
            ``progress``  → callable(current, total, filename)
            ``file_done`` → callable(index, success, path)
            ``all_done``  → callable(success_count, fail_count)
            ``error``     → callable(message)
        """
        if self.is_running:
            logger.warning("A download is already in progress")
            return

        download_dir = self._settings.get(
            "download_dir", config.DEFAULT_SETTINGS["download_dir"]
        )
        os.makedirs(download_dir, exist_ok=True)

        self._thread = QThread()
        self._worker = DownloadWorker(papers, self._auth, self._scraper, download_dir)
        self._worker.moveToThread(self._thread)

        # Connect signals to callbacks
        self._thread.started.connect(self._worker.run)
        if "progress" in callbacks:
            self._worker.progress.connect(callbacks["progress"])
        if "file_done" in callbacks:
            self._worker.file_done.connect(callbacks["file_done"])
        if "all_done" in callbacks:
            self._worker.all_done.connect(callbacks["all_done"])
        if "error" in callbacks:
            self._worker.error.connect(callbacks["error"])

        # Cleanup
        self._worker.all_done.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup)

        self._thread.start()
        logger.info("Download thread started for %d papers", len(papers))

    def cancel(self) -> None:
        if self._worker:
            self._worker.cancel()

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _cleanup(self) -> None:
        self._thread = None
        self._worker = None
        logger.debug("Download thread cleaned up")
