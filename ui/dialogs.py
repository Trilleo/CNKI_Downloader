"""
Dialog windows for CNKI Downloader.
"""

import os
from typing import Dict, List

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QCheckBox,
    QSpinBox,
    QComboBox,
    QGroupBox,
)

import config
from utils.logger import get_logger

logger = get_logger("cnki_downloader.dialogs")


# ── Login dialog ─────────────────────────────────────────────────────────────

class LoginDialog(QDialog):
    """School-portal login form."""

    def __init__(self, settings, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("Login – School Portal")
        self.setMinimumWidth(420)
        self._build_ui()
        self._load_saved()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("<b>Sign in with your school account</b>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        form = QFormLayout()

        self._portal_edit = QLineEdit()
        self._portal_edit.setPlaceholderText("https://your-school-portal/login")
        form.addRow("Portal URL:", self._portal_edit)

        self._user_edit = QLineEdit()
        self._user_edit.setPlaceholderText("Student / employee ID")
        form.addRow("Username:", self._user_edit)

        self._pass_edit = QLineEdit()
        self._pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Password:", self._pass_edit)

        self._save_cb = QCheckBox("Remember credentials (stored locally)")
        form.addRow("", self._save_cb)

        layout.addLayout(form)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet("color: red;")
        layout.addWidget(self._status_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_saved(self) -> None:
        self._portal_edit.setText(
            self._settings.get("school_portal_url", config.SCHOOL_PORTAL_URL)
        )
        if self._settings.get("save_credentials", False):
            self._save_cb.setChecked(True)
            self._user_edit.setText(self._settings.get("saved_username", ""))
            # NOTE: passwords are NOT stored in this implementation for security.

    def accept(self) -> None:
        if not self._user_edit.text().strip():
            self._status_label.setText("Username is required.")
            return
        if not self._pass_edit.text():
            self._status_label.setText("Password is required.")
            return

        # Persist settings
        self._settings.set("school_portal_url", self._portal_edit.text().strip())
        self._settings.set("save_credentials", self._save_cb.isChecked())
        if self._save_cb.isChecked():
            self._settings.set("saved_username", self._user_edit.text().strip())

        super().accept()

    # ── Accessors ────────────────────────────────────────────────────────────

    @property
    def username(self) -> str:
        return self._user_edit.text().strip()

    @property
    def password(self) -> str:
        return self._pass_edit.text()

    @property
    def portal_url(self) -> str:
        return self._portal_edit.text().strip()


# ── Cookie login dialog ──────────────────────────────────────────────────────

def _parse_cookie_string(raw: str) -> List[Dict[str, str]]:
    """Parse a cookie header string (``name=value; name2=value2``) into a list
    of dicts suitable for Selenium's ``add_cookie``."""
    cookies: List[Dict[str, str]] = []
    for pair in raw.split(";"):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        name, _, value = pair.partition("=")
        name = name.strip()
        value = value.strip()
        if name:
            cookies.append({"name": name, "value": value})
    return cookies


class CookieLoginDialog(QDialog):
    """Dialog that lets users paste browser cookies to authenticate."""

    def __init__(self, settings, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("Login with Browser Cookies")
        self.setMinimumWidth(520)
        self._cookies: List[Dict[str, str]] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("<b>Paste cookies from your browser</b>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        instructions = QLabel(
            "Open your browser where you are already logged in to CNKI, "
            "copy the cookie header value from the developer tools "
            "(Network tab → any request → <i>Cookie</i> header), "
            "and paste it below.\n\n"
            "Expected format: <code>name1=value1; name2=value2; …</code>"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        self._cookie_edit = QTextEdit()
        self._cookie_edit.setPlaceholderText("name1=value1; name2=value2; …")
        self._cookie_edit.setMinimumHeight(100)
        layout.addWidget(self._cookie_edit)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet("color: red;")
        layout.addWidget(self._status_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        raw = self._cookie_edit.toPlainText().strip()
        if not raw:
            self._status_label.setText("Please paste your cookie string.")
            return

        parsed = _parse_cookie_string(raw)
        if not parsed:
            self._status_label.setText(
                "Could not parse any cookies. "
                "Use the format: name=value; name2=value2"
            )
            return

        self._cookies = parsed
        super().accept()

    # ── Accessors ────────────────────────────────────────────────────────────

    @property
    def cookies(self) -> List[Dict[str, str]]:
        """Parsed list of cookie dicts (each with *name* and *value*)."""
        return self._cookies


# ── Settings dialog ───────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    """Application settings form."""

    def __init__(self, settings, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)
        self._build_ui()
        self._populate()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ── Download ─────────────────────────────────────────────────────────
        dl_group = QGroupBox("Downloads")
        dl_layout = QFormLayout(dl_group)

        dl_row = QHBoxLayout()
        self._dir_edit = QLineEdit()
        self._dir_edit.setReadOnly(True)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_dir)
        dl_row.addWidget(self._dir_edit)
        dl_row.addWidget(browse_btn)
        dl_layout.addRow("Download directory:", dl_row)

        self._max_dl_spin = QSpinBox()
        self._max_dl_spin.setRange(1, 10)
        dl_layout.addRow("Max concurrent downloads:", self._max_dl_spin)

        layout.addWidget(dl_group)

        # ── Search ───────────────────────────────────────────────────────────
        search_group = QGroupBox("Search")
        search_layout = QFormLayout(search_group)

        self._default_method_combo = QComboBox()
        self._default_method_combo.addItems(config.SEARCH_METHODS)
        search_layout.addRow("Default search method:", self._default_method_combo)

        self._results_per_page_spin = QSpinBox()
        self._results_per_page_spin.setRange(5, 100)
        self._results_per_page_spin.setSingleStep(5)
        search_layout.addRow("Results per page:", self._results_per_page_spin)

        layout.addWidget(search_group)

        # ── Browser ──────────────────────────────────────────────────────────
        browser_group = QGroupBox("Browser")
        browser_layout = QFormLayout(browser_group)

        self._headless_cb = QCheckBox("Run browser in headless mode (no visible window)")
        browser_layout.addRow(self._headless_cb)

        self._portal_edit = QLineEdit()
        self._portal_edit.setPlaceholderText(config.SCHOOL_PORTAL_URL)
        browser_layout.addRow("School portal URL:", self._portal_edit)

        layout.addWidget(browser_group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self) -> None:
        self._dir_edit.setText(
            self._settings.get("download_dir", config.DEFAULT_SETTINGS["download_dir"])
        )
        self._max_dl_spin.setValue(
            self._settings.get("max_concurrent_downloads", 3)
        )
        method = self._settings.get("default_search_method", "Keywords")
        idx = self._default_method_combo.findText(method)
        if idx >= 0:
            self._default_method_combo.setCurrentIndex(idx)
        self._results_per_page_spin.setValue(
            self._settings.get("results_per_page", 20)
        )
        self._headless_cb.setChecked(self._settings.get("headless_browser", True))
        self._portal_edit.setText(
            self._settings.get("school_portal_url", config.SCHOOL_PORTAL_URL)
        )

    def _browse_dir(self) -> None:
        current = self._dir_edit.text() or os.path.expanduser("~")
        chosen = QFileDialog.getExistingDirectory(self, "Select download directory", current)
        if chosen:
            self._dir_edit.setText(chosen)

    def accept(self) -> None:
        self._settings.update(
            {
                "download_dir": self._dir_edit.text(),
                "max_concurrent_downloads": self._max_dl_spin.value(),
                "default_search_method": self._default_method_combo.currentText(),
                "results_per_page": self._results_per_page_spin.value(),
                "headless_browser": self._headless_cb.isChecked(),
                "school_portal_url": self._portal_edit.text().strip(),
            }
        )
        super().accept()


# ── Download progress dialog ──────────────────────────────────────────────────

class DownloadProgressDialog(QDialog):
    """Non-modal dialog that shows batch download progress."""

    cancel_requested = pyqtSignal()

    def __init__(self, total: int, parent=None) -> None:
        super().__init__(parent)
        self._total = total
        self.setWindowTitle("Downloading…")
        self.setMinimumWidth(400)
        self.setModal(False)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._current_label = QLabel("Preparing…")
        layout.addWidget(self._current_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, self._total)
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        self._summary_label = QLabel(f"0 / {self._total} completed")
        layout.addWidget(self._summary_label)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.cancel_requested.emit)
        layout.addWidget(cancel_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def update_progress(self, current: int, total: int, filename: str) -> None:
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(current)
        self._current_label.setText(f"Downloading: {filename}")
        self._summary_label.setText(f"{current} / {total} completed")

    def finish(self, success_count: int, fail_count: int) -> None:
        self._current_label.setText("Done!")
        self._summary_label.setText(
            f"Completed: {success_count} succeeded, {fail_count} failed"
        )
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        self.layout().addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
