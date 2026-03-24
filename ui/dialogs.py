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

try:
    import browser_cookie3
    _BC3_AVAILABLE = True
except ImportError:
    browser_cookie3 = None  # type: ignore[assignment]
    _BC3_AVAILABLE = False

import config
from utils.logger import get_logger
from utils.translator import tr

logger = get_logger("cnki_downloader.dialogs")

# Mapping of UI browser names to browser_cookie3 loader functions.
_BROWSER_LOADERS: Dict[str, str] = {
    "Chrome": "chrome",
    "Firefox": "firefox",
    "Edge": "edge",
    "Opera": "opera",
    "Brave": "brave",
    "Chromium": "chromium",
}

# Domains from which CNKI session cookies should be captured.
_CNKI_DOMAINS = (".cnki.net",)


# ── Login dialog ─────────────────────────────────────────────────────────────

class LoginDialog(QDialog):
    """School-portal login form."""

    def __init__(self, settings, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle(tr("login.title"))
        self.setMinimumWidth(420)
        self._build_ui()
        self._load_saved()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel(tr("login.heading"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        form = QFormLayout()

        self._portal_edit = QLineEdit()
        self._portal_edit.setPlaceholderText(tr("login.portal_placeholder"))
        form.addRow(tr("login.portal_url"), self._portal_edit)

        self._user_edit = QLineEdit()
        self._user_edit.setPlaceholderText(tr("login.username_placeholder"))
        form.addRow(tr("login.username"), self._user_edit)

        self._pass_edit = QLineEdit()
        self._pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(tr("login.password"), self._pass_edit)

        self._save_cb = QCheckBox(tr("login.remember"))
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
            self._status_label.setText(tr("login.username_required"))
            return
        if not self._pass_edit.text():
            self._status_label.setText(tr("login.password_required"))
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
    """Dialog that captures browser cookies – either automatically from an
    installed browser or by manual paste as a fallback."""

    def __init__(self, settings, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle(tr("cookie_login.title"))
        self.setMinimumWidth(520)
        self._cookies: List[Dict[str, str]] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel(tr("cookie_login.heading"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # ── Auto-capture section ─────────────────────────────────────────
        if _BC3_AVAILABLE:
            auto_group = QGroupBox(tr("cookie_login.auto_group"))
            auto_layout = QVBoxLayout(auto_group)

            auto_instructions = QLabel(tr("cookie_login.auto_instructions"))
            auto_instructions.setWordWrap(True)
            auto_layout.addWidget(auto_instructions)

            row = QHBoxLayout()
            self._browser_combo = QComboBox()
            self._browser_combo.addItems(list(_BROWSER_LOADERS.keys()))
            row.addWidget(self._browser_combo)

            capture_btn = QPushButton(tr("cookie_login.capture_btn"))
            capture_btn.clicked.connect(self._auto_capture)
            row.addWidget(capture_btn)

            auto_layout.addLayout(row)

            self._auto_status = QLabel("")
            self._auto_status.setWordWrap(True)
            self._auto_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            auto_layout.addWidget(self._auto_status)

            layout.addWidget(auto_group)

        # ── Manual fallback section ──────────────────────────────────────
        manual_group = QGroupBox(tr("cookie_login.manual_group"))
        manual_layout = QVBoxLayout(manual_group)

        instructions = QLabel(tr("cookie_login.instructions"))
        instructions.setWordWrap(True)
        manual_layout.addWidget(instructions)

        self._cookie_edit = QTextEdit()
        self._cookie_edit.setPlaceholderText(tr("cookie_login.placeholder"))
        self._cookie_edit.setMinimumHeight(100)
        manual_layout.addWidget(self._cookie_edit)

        layout.addWidget(manual_group)

        # ── Status / buttons ─────────────────────────────────────────────
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

    # ── Auto-capture ─────────────────────────────────────────────────────

    def _auto_capture(self) -> None:
        """Read CNKI cookies from the selected browser's cookie store."""
        browser_name = self._browser_combo.currentText()
        loader_attr = _BROWSER_LOADERS.get(browser_name)
        if not loader_attr or browser_cookie3 is None:
            return

        loader = getattr(browser_cookie3, loader_attr, None)
        if loader is None:
            self._auto_status.setStyleSheet("color: red;")
            self._auto_status.setText(
                tr("cookie_login.browser_not_supported", browser=browser_name)
            )
            return

        try:
            cj = loader(domain_name=".cnki.net")
            cookies: List[Dict[str, str]] = [
                {"name": c.name, "value": c.value}
                for c in cj
                if c.name and c.value
            ]
        except Exception as exc:
            logger.warning("Failed to capture cookies from %s: %s", browser_name, exc)
            self._auto_status.setStyleSheet("color: red;")
            self._auto_status.setText(
                tr("cookie_login.capture_error", browser=browser_name)
            )
            return

        if not cookies:
            self._auto_status.setStyleSheet("color: orange;")
            self._auto_status.setText(
                tr("cookie_login.no_cookies_found", browser=browser_name)
            )
            return

        # Populate the manual text area so the user can review before OK.
        cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
        self._cookie_edit.setPlainText(cookie_str)

        self._auto_status.setStyleSheet("color: green;")
        self._auto_status.setText(
            tr("cookie_login.capture_ok", count=len(cookies), browser=browser_name)
        )

    # ── Accept / accessors ───────────────────────────────────────────────

    def accept(self) -> None:
        raw = self._cookie_edit.toPlainText().strip()
        if not raw:
            self._status_label.setText(tr("cookie_login.empty"))
            return

        parsed = _parse_cookie_string(raw)
        if not parsed:
            self._status_label.setText(tr("cookie_login.parse_error"))
            return

        self._cookies = parsed
        super().accept()

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
        self.setWindowTitle(tr("settings_dialog.title"))
        self.setMinimumWidth(480)
        self._build_ui()
        self._populate()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ── Download ─────────────────────────────────────────────────────────
        dl_group = QGroupBox(tr("settings_dialog.downloads"))
        dl_layout = QFormLayout(dl_group)

        dl_row = QHBoxLayout()
        self._dir_edit = QLineEdit()
        self._dir_edit.setReadOnly(True)
        browse_btn = QPushButton(tr("settings_dialog.browse"))
        browse_btn.clicked.connect(self._browse_dir)
        dl_row.addWidget(self._dir_edit)
        dl_row.addWidget(browse_btn)
        dl_layout.addRow(tr("settings_dialog.download_dir"), dl_row)

        self._max_dl_spin = QSpinBox()
        self._max_dl_spin.setRange(1, 10)
        dl_layout.addRow(tr("settings_dialog.max_concurrent"), self._max_dl_spin)

        layout.addWidget(dl_group)

        # ── Search ───────────────────────────────────────────────────────────
        search_group = QGroupBox(tr("settings_dialog.search"))
        search_layout = QFormLayout(search_group)

        self._default_method_combo = QComboBox()
        self._default_method_combo.addItems(config.SEARCH_METHODS)
        search_layout.addRow(tr("settings_dialog.default_method"), self._default_method_combo)

        self._results_per_page_spin = QSpinBox()
        self._results_per_page_spin.setRange(5, 100)
        self._results_per_page_spin.setSingleStep(5)
        search_layout.addRow(tr("settings_dialog.results_per_page"), self._results_per_page_spin)

        layout.addWidget(search_group)

        # ── Browser ──────────────────────────────────────────────────────────
        browser_group = QGroupBox(tr("settings_dialog.browser"))
        browser_layout = QFormLayout(browser_group)

        self._headless_cb = QCheckBox(tr("settings_dialog.headless"))
        browser_layout.addRow(self._headless_cb)

        self._portal_edit = QLineEdit()
        self._portal_edit.setPlaceholderText(config.SCHOOL_PORTAL_URL)
        browser_layout.addRow(tr("settings_dialog.portal_url"), self._portal_edit)

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
        chosen = QFileDialog.getExistingDirectory(
            self, tr("settings_dialog.select_dir"), current
        )
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
        self.setWindowTitle(tr("download_progress.title"))
        self.setMinimumWidth(400)
        self.setModal(False)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._current_label = QLabel(tr("download_progress.preparing"))
        layout.addWidget(self._current_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, self._total)
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        self._summary_label = QLabel(
            tr("download_progress.summary", current=0, total=self._total)
        )
        layout.addWidget(self._summary_label)

        cancel_btn = QPushButton(tr("download_progress.cancel"))
        cancel_btn.clicked.connect(self.cancel_requested.emit)
        layout.addWidget(cancel_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def update_progress(self, current: int, total: int, filename: str) -> None:
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(current)
        self._current_label.setText(
            tr("download_progress.downloading", filename=filename)
        )
        self._summary_label.setText(
            tr("download_progress.summary", current=current, total=total)
        )

    def finish(self, success_count: int, fail_count: int) -> None:
        self._current_label.setText(tr("download_progress.done"))
        self._summary_label.setText(
            tr("download_progress.finished",
               success=success_count, fail=fail_count)
        )
        close_btn = QPushButton(tr("download_progress.close"))
        close_btn.clicked.connect(self.accept)
        self.layout().addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
