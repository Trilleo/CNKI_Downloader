"""
CNKI Downloader – application entry point.

Usage:
    python main.py
"""

import sys
import os

# Ensure the project root is on the Python path so that sub-packages resolve
# correctly regardless of the working directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from utils.logger import setup_logger
from utils.settings import SettingsManager
from ui.main_window import MainWindow
import config


def main() -> None:
    # Ensure data / log directories exist before anything else
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.LOG_DIR, exist_ok=True)

    logger = setup_logger()
    logger.info("Starting %s v%s", config.APP_NAME, config.APP_VERSION)

    settings = SettingsManager()

    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setApplicationVersion(config.APP_VERSION)

    window = MainWindow(settings)
    window.show()

    exit_code = app.exec()
    logger.info("Application exited with code %d", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
