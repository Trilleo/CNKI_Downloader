"""
Main application window for CNKI Downloader.

Layout (QTabWidget with three tabs):
  1. Search   – search form + results table
  2. History  – previous searches
  3. Settings – quick settings panel (full settings via menu)
"""

import os
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import config
from core.auth import AuthManager
from core.cnki_scraper import CNKIScraper
from core.downloader import DownloadManager
from utils.history import HistoryManager
from utils.logger import get_logger
from ui.dialogs import LoginDialog, CookieLoginDialog, SettingsDialog, DownloadProgressDialog
from ui.widgets import StatusBar as AppStatusBar, SectionLabel

logger = get_logger("cnki_downloader.main_window")


# ─── Background search worker ─────────────────────────────────────────────────

class SearchWorker(QObject):
    """Run a CNKI search on a background thread."""

    finished = pyqtSignal(list)     # list[PaperMetadata]
    error = pyqtSignal(str)

    def __init__(self, scraper: CNKIScraper, query: str, method: str,
                 year_from: str, year_to: str, max_results: int) -> None:
        super().__init__()
        self._scraper = scraper
        self._query = query
        self._method = method
        self._year_from = year_from or None
        self._year_to = year_to or None
        self._max_results = max_results

    def run(self) -> None:
        try:
            results = self._scraper.search(
                self._query,
                method=self._method,
                year_from=self._year_from,
                year_to=self._year_to,
                max_results=self._max_results,
            )
            self.finished.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))


# ─── Main window ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self, settings) -> None:
        super().__init__()
        self._settings = settings
        self._auth = AuthManager(settings)
        self._scraper = CNKIScraper(self._auth)
        self._downloader = DownloadManager(self._auth, self._scraper, settings)
        self._history = HistoryManager()
        self._search_results: list = []
        self._search_thread: Optional[QThread] = None
        self._search_worker: Optional[SearchWorker] = None

        self.setWindowTitle(config.APP_NAME)
        self.setMinimumSize(900, 660)

        self._build_menu()
        self._build_ui()
        self._build_status_bar()

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("&File")
        login_action = QAction("&Login…", self)
        login_action.triggered.connect(self._open_login_dialog)
        file_menu.addAction(login_action)

        cookie_login_action = QAction("Login with &Cookies…", self)
        cookie_login_action.triggered.connect(self._open_cookie_login_dialog)
        file_menu.addAction(cookie_login_action)

        logout_action = QAction("Log&out", self)
        logout_action.triggered.connect(self._logout)
        file_menu.addAction(logout_action)

        file_menu.addSeparator()
        settings_action = QAction("&Settings…", self)
        settings_action.triggered.connect(self._open_settings_dialog)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()
        quit_action = QAction("&Quit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Help
        help_menu = mb.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    # ── Central widget ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(8, 8, 8, 4)

        # Login banner
        self._login_banner = self._make_login_banner()
        root_layout.addWidget(self._login_banner)

        # Tabs
        tabs = QTabWidget()
        tabs.addTab(self._build_search_tab(), "🔍  Search")
        tabs.addTab(self._build_history_tab(), "📋  History")
        tabs.addTab(self._build_settings_tab(), "⚙  Settings")
        root_layout.addWidget(tabs, stretch=1)

    def _make_login_banner(self) -> QWidget:
        banner = QWidget()
        banner.setStyleSheet("background-color: #fff3cd; border-radius: 4px;")
        h = QHBoxLayout(banner)
        h.setContentsMargins(12, 6, 12, 6)
        self._login_status_label = QLabel("⚠  Not logged in – please log in via File → Login…")
        h.addWidget(self._login_status_label, stretch=1)
        login_btn = QPushButton("Login")
        login_btn.setFixedWidth(80)
        login_btn.clicked.connect(self._open_login_dialog)
        h.addWidget(login_btn)
        return banner

    # ── Search tab ────────────────────────────────────────────────────────────

    def _build_search_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        # ── Search form ──────────────────────────────────────────────────────
        form_group = QGroupBox("Search Parameters")
        form_layout = QVBoxLayout(form_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Search method:"))
        self._method_combo = QComboBox()
        self._method_combo.addItems(config.SEARCH_METHODS)
        default_method = self._settings.get("default_search_method", "Keywords")
        idx = self._method_combo.findText(default_method)
        if idx >= 0:
            self._method_combo.setCurrentIndex(idx)
        self._method_combo.setFixedWidth(160)
        row1.addWidget(self._method_combo)
        row1.addStretch()
        form_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Query:"))
        self._query_edit = QLineEdit()
        self._query_edit.setPlaceholderText("Enter search terms…")
        self._query_edit.returnPressed.connect(self._do_search)
        row2.addWidget(self._query_edit, stretch=1)
        form_layout.addLayout(row2)

        # Year range filter
        year_row = QHBoxLayout()
        year_row.addWidget(QLabel("Year from:"))
        self._year_from_edit = QLineEdit()
        self._year_from_edit.setPlaceholderText("e.g. 2010")
        self._year_from_edit.setFixedWidth(80)
        year_row.addWidget(self._year_from_edit)
        year_row.addWidget(QLabel("to:"))
        self._year_to_edit = QLineEdit()
        self._year_to_edit.setPlaceholderText("e.g. 2024")
        self._year_to_edit.setFixedWidth(80)
        year_row.addWidget(self._year_to_edit)
        year_row.addStretch()
        form_layout.addLayout(year_row)

        # Max results
        max_row = QHBoxLayout()
        max_row.addWidget(QLabel("Max results:"))
        self._max_results_spin = QSpinBox()
        self._max_results_spin.setRange(5, 100)
        self._max_results_spin.setSingleStep(5)
        self._max_results_spin.setValue(self._settings.get("results_per_page", 20))
        max_row.addWidget(self._max_results_spin)
        max_row.addStretch()
        form_layout.addLayout(max_row)

        # Search button row
        btn_row = QHBoxLayout()
        self._search_btn = QPushButton("Search")
        self._search_btn.setFixedWidth(100)
        self._search_btn.clicked.connect(self._do_search)
        self._search_btn.setDefault(True)
        btn_row.addStretch()
        btn_row.addWidget(self._search_btn)
        form_layout.addLayout(btn_row)

        layout.addWidget(form_group)

        # ── Results table ────────────────────────────────────────────────────
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout(results_group)

        self._results_table = QTableWidget(0, 5)
        self._results_table.setHorizontalHeaderLabels(
            ["", "Title", "Authors", "Journal", "Year"]
        )
        self._results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._results_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._results_table.setColumnWidth(0, 30)
        self._results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._results_table.setAlternatingRowColors(True)
        results_layout.addWidget(self._results_table)

        # Select all / download buttons
        dl_row = QHBoxLayout()
        self._select_all_btn = QPushButton("Select all")
        self._select_all_btn.setFixedWidth(100)
        self._select_all_btn.clicked.connect(self._select_all_results)
        dl_row.addWidget(self._select_all_btn)

        self._deselect_all_btn = QPushButton("Deselect all")
        self._deselect_all_btn.setFixedWidth(100)
        self._deselect_all_btn.clicked.connect(self._deselect_all_results)
        dl_row.addWidget(self._deselect_all_btn)

        dl_row.addStretch()

        self._download_btn = QPushButton("⬇  Download selected")
        self._download_btn.setFixedWidth(180)
        self._download_btn.clicked.connect(self._download_selected)
        dl_row.addWidget(self._download_btn)

        results_layout.addLayout(dl_row)
        layout.addWidget(results_group, stretch=1)

        return widget

    # ── History tab ───────────────────────────────────────────────────────────

    def _build_history_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        self._history_table = QTableWidget(0, 4)
        self._history_table.setHorizontalHeaderLabels(["Date", "Method", "Query", "Results"])
        self._history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._history_table.setAlternatingRowColors(True)
        self._history_table.doubleClicked.connect(self._rerun_history_entry)
        layout.addWidget(self._history_table)

        btn_row = QHBoxLayout()
        reload_btn = QPushButton("Reload history")
        reload_btn.clicked.connect(self._refresh_history_table)
        btn_row.addWidget(reload_btn)

        delete_btn = QPushButton("Delete selected")
        delete_btn.clicked.connect(self._delete_history_entry)
        btn_row.addWidget(delete_btn)

        clear_btn = QPushButton("Clear all")
        clear_btn.clicked.connect(self._clear_history)
        btn_row.addWidget(clear_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._refresh_history_table()
        return widget

    # ── Settings tab ─────────────────────────────────────────────────────────

    def _build_settings_tab(self) -> QWidget:
        widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(SectionLabel("Quick Settings"))
        note = QLabel(
            "For full settings, use <b>File → Settings…</b>. "
            "Changes here are saved immediately."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        form = QFormLayout()

        # Download directory
        dir_row = QHBoxLayout()
        self._settings_dir_edit = QLineEdit(
            self._settings.get("download_dir", config.DEFAULT_SETTINGS["download_dir"])
        )
        self._settings_dir_edit.setReadOnly(True)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_download_dir)
        dir_row.addWidget(self._settings_dir_edit, stretch=1)
        dir_row.addWidget(browse_btn)
        form.addRow("Download directory:", dir_row)

        # Headless
        self._settings_headless_cb = QCheckBox()
        self._settings_headless_cb.setChecked(self._settings.get("headless_browser", True))
        self._settings_headless_cb.toggled.connect(
            lambda v: self._settings.set("headless_browser", v)
        )
        form.addRow("Headless browser:", self._settings_headless_cb)

        layout.addLayout(form)

        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)
        return outer

    # ── Status bar ────────────────────────────────────────────────────────────

    def _build_status_bar(self) -> None:
        self._app_status_bar = AppStatusBar()
        self.statusBar().addPermanentWidget(self._app_status_bar, 1)

    # ── Slots: login / logout ─────────────────────────────────────────────────

    def _open_login_dialog(self) -> None:
        dlg = LoginDialog(self._settings, parent=self)
        if dlg.exec() == LoginDialog.DialogCode.Accepted:
            self._app_status_bar.set_message("Logging in…")
            self._app_status_bar.show_progress(0, 0)
            self.setEnabled(False)
            self.repaint()

            ok = self._auth.login(dlg.username, dlg.password, dlg.portal_url)
            self.setEnabled(True)
            self._app_status_bar.hide_progress()

            if ok:
                self._login_status_label.setText(
                    f"✅  Logged in as {dlg.username}"
                )
                self._login_banner.setStyleSheet(
                    "background-color: #d4edda; border-radius: 4px;"
                )
                self._app_status_bar.set_message("Logged in successfully.")
            else:
                self._login_banner.setStyleSheet(
                    "background-color: #f8d7da; border-radius: 4px;"
                )
                self._login_status_label.setText("❌  Login failed – check credentials or portal URL")
                self._app_status_bar.set_message("Login failed.")
                QMessageBox.warning(
                    self,
                    "Login Failed",
                    "Could not log in. Please check your credentials and portal URL in Settings.",
                )

    def _open_cookie_login_dialog(self) -> None:
        dlg = CookieLoginDialog(self._settings, parent=self)
        if dlg.exec() == CookieLoginDialog.DialogCode.Accepted:
            self._app_status_bar.set_message("Logging in with cookies…")
            self._app_status_bar.show_progress(0, 0)
            self.setEnabled(False)
            self.repaint()

            ok = self._auth.login_with_cookies(dlg.cookies)
            self.setEnabled(True)
            self._app_status_bar.hide_progress()

            if ok:
                self._login_status_label.setText(
                    "✅  Logged in via browser cookies"
                )
                self._login_banner.setStyleSheet(
                    "background-color: #d4edda; border-radius: 4px;"
                )
                self._app_status_bar.set_message("Cookie login successful.")
            else:
                self._login_banner.setStyleSheet(
                    "background-color: #f8d7da; border-radius: 4px;"
                )
                self._login_status_label.setText(
                    "❌  Cookie login failed – cookies may be expired or invalid"
                )
                self._app_status_bar.set_message("Cookie login failed.")
                QMessageBox.warning(
                    self,
                    "Cookie Login Failed",
                    "Could not log in with the provided cookies.\n"
                    "They may be expired or not contain the required session data.",
                )

    def _logout(self) -> None:
        self._auth.logout()
        self._login_banner.setStyleSheet("background-color: #fff3cd; border-radius: 4px;")
        self._login_status_label.setText("⚠  Not logged in – please log in via File → Login…")
        self._app_status_bar.set_message("Logged out.")

    # ── Slots: settings ───────────────────────────────────────────────────────

    def _open_settings_dialog(self) -> None:
        dlg = SettingsDialog(self._settings, parent=self)
        dlg.exec()

    def _browse_download_dir(self) -> None:
        from PyQt6.QtWidgets import QFileDialog
        current = self._settings_dir_edit.text() or os.path.expanduser("~")
        chosen = QFileDialog.getExistingDirectory(self, "Select download directory", current)
        if chosen:
            self._settings_dir_edit.setText(chosen)
            self._settings.set("download_dir", chosen)

    # ── Slots: search ─────────────────────────────────────────────────────────

    def _do_search(self) -> None:
        if self._search_thread and self._search_thread.isRunning():
            return

        if not self._auth.is_logged_in:
            QMessageBox.information(
                self, "Login Required", "Please log in before searching."
            )
            return

        query = self._query_edit.text().strip()
        if not query:
            QMessageBox.information(self, "Empty Query", "Please enter a search term.")
            return

        method = self._method_combo.currentText()
        year_from = self._year_from_edit.text().strip()
        year_to = self._year_to_edit.text().strip()
        max_results = self._max_results_spin.value()

        self._search_btn.setEnabled(False)
        self._search_btn.setText("Searching…")
        self._app_status_bar.set_message(f'Searching for "{query}"…')
        self._app_status_bar.show_progress(0, 0)

        self._search_worker = SearchWorker(
            self._scraper, query, method, year_from, year_to, max_results
        )
        self._search_thread = QThread()
        self._search_worker.moveToThread(self._search_thread)
        self._search_thread.started.connect(self._search_worker.run)
        self._search_worker.finished.connect(self._on_search_finished)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.finished.connect(self._search_thread.quit)
        self._search_worker.error.connect(self._search_thread.quit)
        self._search_thread.start()

    def _on_search_finished(self, results: list) -> None:
        self._search_results = results
        self._search_btn.setEnabled(True)
        self._search_btn.setText("Search")
        self._app_status_bar.hide_progress()
        self._app_status_bar.set_message(f"Found {len(results)} results.")

        # Save to history
        self._history.add(
            method=self._method_combo.currentText(),
            query=self._query_edit.text().strip(),
            filters={
                "year_from": self._year_from_edit.text().strip(),
                "year_to": self._year_to_edit.text().strip(),
            },
            result_count=len(results),
        )

        self._populate_results_table(results)
        self._refresh_history_table()

    def _on_search_error(self, message: str) -> None:
        self._search_btn.setEnabled(True)
        self._search_btn.setText("Search")
        self._app_status_bar.hide_progress()
        self._app_status_bar.set_message("Search failed.")
        QMessageBox.critical(self, "Search Error", f"Search failed:\n{message}")

    def _populate_results_table(self, results: list) -> None:
        self._results_table.setRowCount(0)
        for paper in results:
            row = self._results_table.rowCount()
            self._results_table.insertRow(row)

            # Checkbox column
            cb = QTableWidgetItem()
            cb.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            cb.setCheckState(Qt.CheckState.Unchecked)
            self._results_table.setItem(row, 0, cb)

            self._results_table.setItem(row, 1, QTableWidgetItem(paper.title))
            self._results_table.setItem(row, 2, QTableWidgetItem(paper.authors))
            self._results_table.setItem(row, 3, QTableWidgetItem(paper.journal))
            self._results_table.setItem(row, 4, QTableWidgetItem(paper.year))

    # ── Slots: download ───────────────────────────────────────────────────────

    def _select_all_results(self) -> None:
        for row in range(self._results_table.rowCount()):
            item = self._results_table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Checked)

    def _deselect_all_results(self) -> None:
        for row in range(self._results_table.rowCount()):
            item = self._results_table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)

    def _download_selected(self) -> None:
        selected_papers = []
        for row in range(self._results_table.rowCount()):
            cb_item = self._results_table.item(row, 0)
            if cb_item and cb_item.checkState() == Qt.CheckState.Checked:
                if row < len(self._search_results):
                    selected_papers.append(self._search_results[row])

        if not selected_papers:
            QMessageBox.information(
                self, "No Selection", "Please check at least one paper to download."
            )
            return

        if self._downloader.is_running:
            QMessageBox.information(
                self, "Busy", "A download is already in progress. Please wait."
            )
            return

        progress_dlg = DownloadProgressDialog(len(selected_papers), parent=self)
        progress_dlg.cancel_requested.connect(self._downloader.cancel)
        progress_dlg.show()

        self._downloader.start(
            selected_papers,
            {
                "progress": progress_dlg.update_progress,
                "all_done": lambda s, f: progress_dlg.finish(s, f),
            },
        )
        self._app_status_bar.set_message(
            f"Downloading {len(selected_papers)} paper(s)…"
        )

    # ── Slots: history ────────────────────────────────────────────────────────

    def _refresh_history_table(self) -> None:
        entries = self._history.get_all()
        self._history_table.setRowCount(0)
        for entry in entries:
            row = self._history_table.rowCount()
            self._history_table.insertRow(row)
            ts = entry.get("timestamp", "")[:19].replace("T", " ")
            self._history_table.setItem(row, 0, QTableWidgetItem(ts))
            self._history_table.setItem(row, 1, QTableWidgetItem(entry.get("method", "")))
            self._history_table.setItem(row, 2, QTableWidgetItem(entry.get("query", "")))
            self._history_table.setItem(
                row, 3, QTableWidgetItem(str(entry.get("result_count", "")))
            )
            # Store the entry ID as user data in the first cell
            first_item = self._history_table.item(row, 0)
            if first_item:
                first_item.setData(Qt.ItemDataRole.UserRole, entry.get("id"))

    def _rerun_history_entry(self) -> None:
        rows = self._history_table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        method_item = self._history_table.item(row, 1)
        query_item = self._history_table.item(row, 2)
        if not method_item or not query_item:
            return

        self._method_combo.setCurrentText(method_item.text())
        self._query_edit.setText(query_item.text())

        # Switch to search tab (index 0)
        tabs = self.findChild(QTabWidget)
        if tabs:
            tabs.setCurrentIndex(0)

        self._do_search()

    def _delete_history_entry(self) -> None:
        rows = self._history_table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        first_item = self._history_table.item(row, 0)
        if first_item:
            entry_id = first_item.data(Qt.ItemDataRole.UserRole)
            if entry_id:
                self._history.delete(entry_id)
                self._refresh_history_table()

    def _clear_history(self) -> None:
        reply = QMessageBox.question(
            self,
            "Clear History",
            "Are you sure you want to delete all search history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._history.clear()
            self._refresh_history_table()

    # ── Slots: about ─────────────────────────────────────────────────────────

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            f"About {config.APP_NAME}",
            f"<b>{config.APP_NAME}</b> v{config.APP_VERSION}<br><br>"
            "Search and download papers from CNKI using your school account.<br><br>"
            "Built with Python, PyQt6, and Selenium.",
        )

    # ── Window close ─────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        if self._downloader.is_running:
            reply = QMessageBox.question(
                self,
                "Downloads in Progress",
                "A download is still running. Quit anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._downloader.cancel()

        self._auth.quit()
        event.accept()
