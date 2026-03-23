"""
Custom Qt widgets used throughout the CNKI Downloader UI.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
)
from PyQt6.QtGui import QFont


class StatusBar(QWidget):
    """A thin status bar that shows a text message and an optional progress bar."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)

        self._label = QLabel("Ready")
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._progress = QProgressBar()
        self._progress.setFixedWidth(160)
        self._progress.setRange(0, 100)
        self._progress.setTextVisible(True)
        self._progress.hide()

        layout.addWidget(self._label)
        layout.addWidget(self._progress)

    def set_message(self, text: str) -> None:
        self._label.setText(text)

    def show_progress(self, value: int, maximum: int = 100) -> None:
        self._progress.setRange(0, maximum)
        self._progress.setValue(value)
        self._progress.show()

    def hide_progress(self) -> None:
        self._progress.hide()


class SectionLabel(QLabel):
    """Bold section heading label."""

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        self.setFont(font)
        self.setContentsMargins(0, 8, 0, 4)
