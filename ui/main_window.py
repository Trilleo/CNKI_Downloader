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
from PyQt6.QtGui import QAction, QActionGroup
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
from utils.translator import Translator, tr, SUPPORTED_LANGUAGES
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
        self._logged_in_username: Optional[str] = None
        self._login_state: str = "logged_out"  # logged_out | logged_in | cookie_logged_in | failed | cookie_failed

        # Initialise the translator with the persisted language preference
        self._translator = Translator.instance()
        saved_lang = self._settings.get("language", "en")
        if saved_lang != self._translator.language:
            self._translator.set_language(saved_lang)
        self._translator.language_changed.connect(self._on_language_changed)

        self.setWindowTitle(config.APP_NAME)
        self.setMinimumSize(900, 660)

        self._build_menu()
        self._build_ui()
        self._build_status_bar()

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        mb = self.menuBar()

        # File
        self._file_menu = mb.addMenu(tr("menu.file"))
        self._login_action = QAction(tr("menu.file.login"), self)
        self._login_action.triggered.connect(self._open_login_dialog)
        self._file_menu.addAction(self._login_action)

        self._cookie_login_action = QAction(tr("menu.file.cookie_login"), self)
        self._cookie_login_action.triggered.connect(self._open_cookie_login_dialog)
        self._file_menu.addAction(self._cookie_login_action)

        self._logout_action = QAction(tr("menu.file.logout"), self)
        self._logout_action.triggered.connect(self._logout)
        self._file_menu.addAction(self._logout_action)

        self._file_menu.addSeparator()
        self._settings_action = QAction(tr("menu.file.settings"), self)
        self._settings_action.triggered.connect(self._open_settings_dialog)
        self._file_menu.addAction(self._settings_action)

        self._file_menu.addSeparator()
        self._quit_action = QAction(tr("menu.file.quit"), self)
        self._quit_action.triggered.connect(self.close)
        self._file_menu.addAction(self._quit_action)

        # Language
        self._language_menu = mb.addMenu(tr("menu.language"))
        self._lang_action_group = QActionGroup(self)
        self._lang_actions: dict[str, QAction] = {}
        for lang_code in SUPPORTED_LANGUAGES:
            action = QAction(tr(f"lang.{lang_code}"), self)
            action.setCheckable(True)
            action.setChecked(lang_code == self._translator.language)
            action.setData(lang_code)
            action.triggered.connect(self._on_language_action_triggered)
            self._lang_action_group.addAction(action)
            self._language_menu.addAction(action)
            self._lang_actions[lang_code] = action

        # Help
        self._help_menu = mb.addMenu(tr("menu.help"))
        self._about_action = QAction(tr("menu.help.about"), self)
        self._about_action.triggered.connect(self._show_about)
        self._help_menu.addAction(self._about_action)

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
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_search_tab(), tr("tab.search"))
        self._tabs.addTab(self._build_history_tab(), tr("tab.history"))
        self._tabs.addTab(self._build_settings_tab(), tr("tab.settings"))
        root_layout.addWidget(self._tabs, stretch=1)

    def _make_login_banner(self) -> QWidget:
        banner = QWidget()
        banner.setStyleSheet("background-color: #fff3cd; border-radius: 4px;")
        h = QHBoxLayout(banner)
        h.setContentsMargins(12, 6, 12, 6)
        self._login_status_label = QLabel(tr("banner.not_logged_in"))
        h.addWidget(self._login_status_label, stretch=1)
        self._banner_login_btn = QPushButton(tr("banner.login_btn"))
        self._banner_login_btn.setFixedWidth(80)
        self._banner_login_btn.clicked.connect(self._open_login_dialog)
        h.addWidget(self._banner_login_btn)
        return banner

    # ── Search tab ────────────────────────────────────────────────────────────

    def _build_search_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        # ── Search form ──────────────────────────────────────────────────────
        self._search_form_group = QGroupBox(tr("search.parameters"))
        form_layout = QVBoxLayout(self._search_form_group)

        row1 = QHBoxLayout()
        self._method_label = QLabel(tr("search.method"))
        row1.addWidget(self._method_label)
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
        self._query_label = QLabel(tr("search.query"))
        row2.addWidget(self._query_label)
        self._query_edit = QLineEdit()
        self._query_edit.setPlaceholderText(tr("search.query_placeholder"))
        self._query_edit.returnPressed.connect(self._do_search)
        row2.addWidget(self._query_edit, stretch=1)
        form_layout.addLayout(row2)

        # Year range filter
        year_row = QHBoxLayout()
        self._year_from_label = QLabel(tr("search.year_from"))
        year_row.addWidget(self._year_from_label)
        self._year_from_edit = QLineEdit()
        self._year_from_edit.setPlaceholderText(tr("search.year_from_placeholder"))
        self._year_from_edit.setFixedWidth(80)
        year_row.addWidget(self._year_from_edit)
        self._year_to_label = QLabel(tr("search.year_to"))
        year_row.addWidget(self._year_to_label)
        self._year_to_edit = QLineEdit()
        self._year_to_edit.setPlaceholderText(tr("search.year_to_placeholder"))
        self._year_to_edit.setFixedWidth(80)
        year_row.addWidget(self._year_to_edit)
        year_row.addStretch()
        form_layout.addLayout(year_row)

        # Max results
        max_row = QHBoxLayout()
        self._max_results_label = QLabel(tr("search.max_results"))
        max_row.addWidget(self._max_results_label)
        self._max_results_spin = QSpinBox()
        self._max_results_spin.setRange(5, 100)
        self._max_results_spin.setSingleStep(5)
        self._max_results_spin.setValue(self._settings.get("results_per_page", 20))
        max_row.addWidget(self._max_results_spin)
        max_row.addStretch()
        form_layout.addLayout(max_row)

        # Search button row
        btn_row = QHBoxLayout()
        self._search_btn = QPushButton(tr("search.search_btn"))
        self._search_btn.setFixedWidth(100)
        self._search_btn.clicked.connect(self._do_search)
        self._search_btn.setDefault(True)
        btn_row.addStretch()
        btn_row.addWidget(self._search_btn)
        form_layout.addLayout(btn_row)

        layout.addWidget(self._search_form_group)

        # ── Results table ────────────────────────────────────────────────────
        self._results_group = QGroupBox(tr("results.title"))
        results_layout = QVBoxLayout(self._results_group)

        self._results_table = QTableWidget(0, 5)
        self._results_table.setHorizontalHeaderLabels(
            ["", tr("results.col.title"), tr("results.col.authors"),
             tr("results.col.journal"), tr("results.col.year")]
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
        self._select_all_btn = QPushButton(tr("results.select_all"))
        self._select_all_btn.setFixedWidth(100)
        self._select_all_btn.clicked.connect(self._select_all_results)
        dl_row.addWidget(self._select_all_btn)

        self._deselect_all_btn = QPushButton(tr("results.deselect_all"))
        self._deselect_all_btn.setFixedWidth(100)
        self._deselect_all_btn.clicked.connect(self._deselect_all_results)
        dl_row.addWidget(self._deselect_all_btn)

        dl_row.addStretch()

        self._download_btn = QPushButton(tr("results.download_selected"))
        self._download_btn.setFixedWidth(180)
        self._download_btn.clicked.connect(self._download_selected)
        dl_row.addWidget(self._download_btn)

        results_layout.addLayout(dl_row)
        layout.addWidget(self._results_group, stretch=1)

        return widget

    # ── History tab ───────────────────────────────────────────────────────────

    def _build_history_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        self._history_table = QTableWidget(0, 4)
        self._history_table.setHorizontalHeaderLabels(
            [tr("history.col.date"), tr("history.col.method"),
             tr("history.col.query"), tr("history.col.results")]
        )
        self._history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._history_table.setAlternatingRowColors(True)
        self._history_table.doubleClicked.connect(self._rerun_history_entry)
        layout.addWidget(self._history_table)

        btn_row = QHBoxLayout()
        self._reload_history_btn = QPushButton(tr("history.reload"))
        self._reload_history_btn.clicked.connect(self._refresh_history_table)
        btn_row.addWidget(self._reload_history_btn)

        self._delete_history_btn = QPushButton(tr("history.delete"))
        self._delete_history_btn.clicked.connect(self._delete_history_entry)
        btn_row.addWidget(self._delete_history_btn)

        self._clear_history_btn = QPushButton(tr("history.clear"))
        self._clear_history_btn.clicked.connect(self._clear_history)
        btn_row.addWidget(self._clear_history_btn)

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

        self._settings_section_label = SectionLabel(tr("settings.quick_settings"))
        layout.addWidget(self._settings_section_label)
        self._settings_note_label = QLabel(tr("settings.note"))
        self._settings_note_label.setWordWrap(True)
        layout.addWidget(self._settings_note_label)

        form = QFormLayout()

        # Download directory
        dir_row = QHBoxLayout()
        self._settings_dir_edit = QLineEdit(
            self._settings.get("download_dir", config.DEFAULT_SETTINGS["download_dir"])
        )
        self._settings_dir_edit.setReadOnly(True)
        self._settings_browse_btn = QPushButton(tr("settings.browse"))
        self._settings_browse_btn.clicked.connect(self._browse_download_dir)
        dir_row.addWidget(self._settings_dir_edit, stretch=1)
        dir_row.addWidget(self._settings_browse_btn)
        self._settings_dir_label = QLabel(tr("settings.download_dir"))
        form.addRow(self._settings_dir_label, dir_row)

        # Headless
        self._settings_headless_cb = QCheckBox()
        self._settings_headless_cb.setChecked(self._settings.get("headless_browser", True))
        self._settings_headless_cb.toggled.connect(
            lambda v: self._settings.set("headless_browser", v)
        )
        self._settings_headless_label = QLabel(tr("settings.headless"))
        form.addRow(self._settings_headless_label, self._settings_headless_cb)

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
            self._app_status_bar.set_message(tr("status.logging_in"))
            self._app_status_bar.show_progress(0, 0)
            self.setEnabled(False)
            self.repaint()

            ok = self._auth.login(dlg.username, dlg.password, dlg.portal_url)
            self.setEnabled(True)
            self._app_status_bar.hide_progress()

            if ok:
                self._logged_in_username = dlg.username
                self._login_state = "logged_in"
                self._login_status_label.setText(
                    tr("banner.logged_in", username=dlg.username)
                )
                self._login_banner.setStyleSheet(
                    "background-color: #d4edda; border-radius: 4px;"
                )
                self._app_status_bar.set_message(tr("status.logged_in"))
            else:
                self._login_state = "failed"
                self._login_banner.setStyleSheet(
                    "background-color: #f8d7da; border-radius: 4px;"
                )
                self._login_status_label.setText(tr("banner.login_failed"))
                self._app_status_bar.set_message(tr("status.login_failed"))
                QMessageBox.warning(
                    self,
                    tr("msg.login_failed_title"),
                    tr("msg.login_failed"),
                )

    def _open_cookie_login_dialog(self) -> None:
        dlg = CookieLoginDialog(self._settings, parent=self)
        if dlg.exec() == CookieLoginDialog.DialogCode.Accepted:
            self._app_status_bar.set_message(tr("status.logging_in_cookies"))
            self._app_status_bar.show_progress(0, 0)
            self.setEnabled(False)
            self.repaint()

            ok = self._auth.login_with_cookies(dlg.cookies)
            self.setEnabled(True)
            self._app_status_bar.hide_progress()

            if ok:
                self._login_state = "cookie_logged_in"
                self._login_status_label.setText(tr("banner.cookie_logged_in"))
                self._login_banner.setStyleSheet(
                    "background-color: #d4edda; border-radius: 4px;"
                )
                self._app_status_bar.set_message(tr("status.cookie_login_ok"))
            else:
                self._login_state = "cookie_failed"
                self._login_banner.setStyleSheet(
                    "background-color: #f8d7da; border-radius: 4px;"
                )
                self._login_status_label.setText(tr("banner.cookie_login_failed"))
                self._app_status_bar.set_message(tr("status.cookie_login_failed"))
                QMessageBox.warning(
                    self,
                    tr("msg.cookie_login_failed_title"),
                    tr("msg.cookie_login_failed"),
                )

    def _logout(self) -> None:
        self._auth.logout()
        self._login_state = "logged_out"
        self._logged_in_username = None
        self._login_banner.setStyleSheet("background-color: #fff3cd; border-radius: 4px;")
        self._login_status_label.setText(tr("banner.not_logged_in"))
        self._app_status_bar.set_message(tr("status.logged_out"))

    # ── Slots: settings ───────────────────────────────────────────────────────

    def _open_settings_dialog(self) -> None:
        dlg = SettingsDialog(self._settings, parent=self)
        dlg.exec()

    def _browse_download_dir(self) -> None:
        from PyQt6.QtWidgets import QFileDialog
        current = self._settings_dir_edit.text() or os.path.expanduser("~")
        chosen = QFileDialog.getExistingDirectory(self, tr("settings.select_dir"), current)
        if chosen:
            self._settings_dir_edit.setText(chosen)
            self._settings.set("download_dir", chosen)

    # ── Slots: search ─────────────────────────────────────────────────────────

    def _do_search(self) -> None:
        if self._search_thread and self._search_thread.isRunning():
            return

        if not self._auth.is_logged_in:
            QMessageBox.information(
                self, tr("msg.login_required_title"), tr("msg.login_required")
            )
            return

        query = self._query_edit.text().strip()
        if not query:
            QMessageBox.information(self, tr("msg.empty_query_title"), tr("msg.empty_query"))
            return

        method = self._method_combo.currentText()
        year_from = self._year_from_edit.text().strip()
        year_to = self._year_to_edit.text().strip()
        max_results = self._max_results_spin.value()

        self._search_btn.setEnabled(False)
        self._search_btn.setText(tr("search.searching_btn"))
        self._app_status_bar.set_message(tr("status.searching", query=query))
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
        self._search_btn.setText(tr("search.search_btn"))
        self._app_status_bar.hide_progress()
        self._app_status_bar.set_message(tr("status.found_results", count=len(results)))

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
        self._search_btn.setText(tr("search.search_btn"))
        self._app_status_bar.hide_progress()
        self._app_status_bar.set_message(tr("status.search_failed"))
        QMessageBox.critical(self, tr("msg.search_error_title"),
                             tr("msg.search_error", message=message))

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
                self, tr("msg.no_selection_title"), tr("msg.no_selection")
            )
            return

        if self._downloader.is_running:
            QMessageBox.information(
                self, tr("msg.busy_title"), tr("msg.busy")
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
            tr("status.downloading", count=len(selected_papers))
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
        self._tabs.setCurrentIndex(0)

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
            tr("history.clear_confirm_title"),
            tr("history.clear_confirm_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._history.clear()
            self._refresh_history_table()

    # ── Slots: language ─────────────────────────────────────────────────────

    def _on_language_action_triggered(self) -> None:
        action = self.sender()
        if action:
            lang = action.data()
            self._translator.set_language(lang)
            self._settings.set("language", lang)

    def _on_language_changed(self, lang: str) -> None:
        """Update all visible UI text after a language switch."""
        self._retranslate_ui()

    def _retranslate_ui(self) -> None:
        """Re-apply translated strings to every stored widget reference."""
        # Menu bar
        self._file_menu.setTitle(tr("menu.file"))
        self._login_action.setText(tr("menu.file.login"))
        self._cookie_login_action.setText(tr("menu.file.cookie_login"))
        self._logout_action.setText(tr("menu.file.logout"))
        self._settings_action.setText(tr("menu.file.settings"))
        self._quit_action.setText(tr("menu.file.quit"))
        self._language_menu.setTitle(tr("menu.language"))
        self._help_menu.setTitle(tr("menu.help"))
        self._about_action.setText(tr("menu.help.about"))

        # Language radio items (label text stays the same but update check)
        for lang_code, action in self._lang_actions.items():
            action.setText(tr(f"lang.{lang_code}"))
            action.setChecked(lang_code == self._translator.language)

        # Tabs
        self._tabs.setTabText(0, tr("tab.search"))
        self._tabs.setTabText(1, tr("tab.history"))
        self._tabs.setTabText(2, tr("tab.settings"))

        # Login banner – update based on current login state
        banner_text_map = {
            "logged_out": lambda: tr("banner.not_logged_in"),
            "logged_in": lambda: tr("banner.logged_in",
                                    username=self._logged_in_username or ""),
            "cookie_logged_in": lambda: tr("banner.cookie_logged_in"),
            "failed": lambda: tr("banner.login_failed"),
            "cookie_failed": lambda: tr("banner.cookie_login_failed"),
        }
        text_fn = banner_text_map.get(self._login_state, banner_text_map["logged_out"])
        self._login_status_label.setText(text_fn())
        self._banner_login_btn.setText(tr("banner.login_btn"))

        # Search tab
        self._search_form_group.setTitle(tr("search.parameters"))
        self._method_label.setText(tr("search.method"))
        self._query_label.setText(tr("search.query"))
        self._query_edit.setPlaceholderText(tr("search.query_placeholder"))
        self._year_from_label.setText(tr("search.year_from"))
        self._year_from_edit.setPlaceholderText(tr("search.year_from_placeholder"))
        self._year_to_label.setText(tr("search.year_to"))
        self._year_to_edit.setPlaceholderText(tr("search.year_to_placeholder"))
        self._max_results_label.setText(tr("search.max_results"))
        if self._search_btn.isEnabled():
            self._search_btn.setText(tr("search.search_btn"))
        else:
            self._search_btn.setText(tr("search.searching_btn"))

        # Results
        self._results_group.setTitle(tr("results.title"))
        self._results_table.setHorizontalHeaderLabels(
            ["", tr("results.col.title"), tr("results.col.authors"),
             tr("results.col.journal"), tr("results.col.year")]
        )
        self._select_all_btn.setText(tr("results.select_all"))
        self._deselect_all_btn.setText(tr("results.deselect_all"))
        self._download_btn.setText(tr("results.download_selected"))

        # History tab
        self._history_table.setHorizontalHeaderLabels(
            [tr("history.col.date"), tr("history.col.method"),
             tr("history.col.query"), tr("history.col.results")]
        )
        self._reload_history_btn.setText(tr("history.reload"))
        self._delete_history_btn.setText(tr("history.delete"))
        self._clear_history_btn.setText(tr("history.clear"))

        # Settings tab
        self._settings_section_label.setText(tr("settings.quick_settings"))
        self._settings_note_label.setText(tr("settings.note"))
        self._settings_dir_label.setText(tr("settings.download_dir"))
        self._settings_browse_btn.setText(tr("settings.browse"))
        self._settings_headless_label.setText(tr("settings.headless"))

        # Status bar
        self._app_status_bar.set_message(tr("status.ready"))

    # ── Slots: about ─────────────────────────────────────────────────────────

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            tr("about.title", app_name=config.APP_NAME),
            tr("about.text", app_name=config.APP_NAME, version=config.APP_VERSION),
        )

    # ── Window close ─────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        if self._downloader.is_running:
            reply = QMessageBox.question(
                self,
                tr("msg.downloads_in_progress_title"),
                tr("msg.downloads_in_progress"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._downloader.cancel()

        self._auth.quit()
        event.accept()
