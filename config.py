"""
Application-wide configuration defaults for CNKI Downloader.
"""

import os

# ─── Application Info ──────────────────────────────────────────────────────────
APP_NAME = "CNKI Downloader"
APP_VERSION = "1.0.0"

# ─── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")

HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
LOG_FILE = os.path.join(LOG_DIR, "cnki_downloader.log")

# ─── CNKI URLs ─────────────────────────────────────────────────────────────────
CNKI_BASE_URL = "https://www.cnki.net"
CNKI_SEARCH_URL = "https://kns.cnki.net/kns8/defaultresult/index"

# ─── School Portal ─────────────────────────────────────────────────────────────
# Update this URL to match your institution's CNKI login portal.
SCHOOL_PORTAL_URL = "https://sso.cnki.net/ssoserver/login"
CNKI_FSSO_URL = "https://fsso.cnki.net"

# ─── Search Methods ────────────────────────────────────────────────────────────
SEARCH_METHODS = [
    "Keywords",
    "Title",
    "Author",
    "Publication Year",
    "Journal Name",
    "Abstract",
    "Subject",
    "DOI",
    "Fund",
]

# ─── Default Settings ──────────────────────────────────────────────────────────
DEFAULT_SETTINGS = {
    "download_dir": os.path.join(os.path.expanduser("~"), "Downloads", "CNKI"),
    "default_search_method": "Keywords",
    "results_per_page": 20,
    "max_concurrent_downloads": 3,
    "school_portal_url": SCHOOL_PORTAL_URL,
    "save_credentials": False,
    "headless_browser": True,
    "log_level": "INFO",
    "language": "en",
}

# ─── Browser ───────────────────────────────────────────────────────────────────
BROWSER_TIMEOUT = 30          # seconds to wait for page elements
DOWNLOAD_TIMEOUT = 120        # seconds allowed per file download
PAGE_LOAD_SLEEP = 2           # polite delay after page navigation (seconds)
