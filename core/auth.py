"""
Authentication module for CNKI Downloader.

Handles school-portal login via Selenium.  The driver instance is created once
and reused for all subsequent scraping / download requests.
"""

import time
from typing import Any, Dict, List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
)

try:
    from webdriver_manager.chrome import ChromeDriverManager
    _WDM_AVAILABLE = True
except ImportError:
    _WDM_AVAILABLE = False

import config
from utils.logger import get_logger

logger = get_logger("cnki_downloader.auth")


class AuthManager:
    """Manage a Selenium WebDriver session and school-portal authentication."""

    def __init__(self, settings) -> None:
        self._settings = settings
        self._driver: Optional[webdriver.Chrome] = None
        self._logged_in: bool = False

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def driver(self) -> Optional[webdriver.Chrome]:
        return self._driver

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in

    # ── Public API ───────────────────────────────────────────────────────────

    def login(self, username: str, password: str, portal_url: str = "") -> bool:
        """
        Open the school portal and authenticate with *username* / *password*.

        Returns *True* on success, *False* on failure.
        """
        portal_url = portal_url or self._settings.get("school_portal_url", config.SCHOOL_PORTAL_URL)
        logger.info("Attempting login to %s", portal_url)

        try:
            self._ensure_driver()
            self._driver.get(portal_url)
            wait = WebDriverWait(self._driver, config.BROWSER_TIMEOUT)

            # ── Locate username field ────────────────────────────────────────
            user_field = self._find_field(
                wait,
                [
                    (By.ID, "username"),
                    (By.NAME, "username"),
                    (By.CSS_SELECTOR, "input[type='text']"),
                    (By.CSS_SELECTOR, "input[autocomplete='username']"),
                ],
            )
            if user_field is None:
                logger.error("Could not find username field on login page")
                return False
            user_field.clear()
            user_field.send_keys(username)

            # ── Locate password field ────────────────────────────────────────
            pass_field = self._find_field(
                wait,
                [
                    (By.ID, "password"),
                    (By.NAME, "password"),
                    (By.CSS_SELECTOR, "input[type='password']"),
                ],
            )
            if pass_field is None:
                logger.error("Could not find password field on login page")
                return False
            pass_field.clear()
            pass_field.send_keys(password)

            # ── Submit ───────────────────────────────────────────────────────
            submit_btn = self._find_field(
                wait,
                [
                    (By.CSS_SELECTOR, "button[type='submit']"),
                    (By.CSS_SELECTOR, "input[type='submit']"),
                    (By.ID, "login-button"),
                    (By.CSS_SELECTOR, ".login-btn"),
                ],
            )
            if submit_btn:
                submit_btn.click()
            else:
                pass_field.submit()

            time.sleep(config.PAGE_LOAD_SLEEP)
            self._logged_in = self._verify_login()
            if self._logged_in:
                logger.info("Login successful")
            else:
                logger.warning("Login may have failed – could not verify session")
            return self._logged_in

        except WebDriverException as exc:
            logger.error("WebDriver error during login: %s", exc)
            return False

    def login_with_cookies(self, cookies: List[Dict[str, Any]], target_url: str = "") -> bool:
        """
        Authenticate by injecting browser cookies into the WebDriver session.

        *cookies* is a list of cookie dicts, each containing at least ``name``
        and ``value`` keys (and optionally ``domain``, ``path``, ``secure``,
        etc.).  The method navigates to CNKI so that the domain matches, adds
        the cookies, then reloads the page and verifies the session.

        Returns *True* on success, *False* on failure.
        """
        target_url = target_url or self._settings.get(
            "school_portal_url", config.CNKI_BASE_URL
        )
        logger.info("Attempting cookie-based login to %s", target_url)

        if not cookies:
            logger.error("No cookies provided")
            return False

        try:
            self._ensure_driver()

            # Navigate to the target domain first – Selenium requires an
            # active page on the same domain before cookies can be set.
            self._driver.get(target_url)
            time.sleep(config.PAGE_LOAD_SLEEP)

            # Inject each cookie into the driver session.
            for cookie in cookies:
                # Selenium expects at minimum 'name' and 'value'.
                if "name" not in cookie or "value" not in cookie:
                    logger.debug("Skipping malformed cookie: %s", cookie)
                    continue
                # Build a clean cookie dict accepted by Selenium.
                clean = {"name": cookie["name"], "value": cookie["value"]}
                for optional_key in ("domain", "path", "secure", "httpOnly", "expiry"):
                    if optional_key in cookie:
                        clean[optional_key] = cookie[optional_key]
                try:
                    self._driver.add_cookie(clean)
                except WebDriverException as exc:
                    logger.debug("Could not add cookie %s: %s", cookie["name"], exc)

            # Reload so the server sees the new cookies.
            self._driver.get(target_url)
            time.sleep(config.PAGE_LOAD_SLEEP)

            self._logged_in = self._verify_login()
            if self._logged_in:
                logger.info("Cookie-based login successful")
            else:
                logger.warning(
                    "Cookie-based login may have failed – could not verify session"
                )
            return self._logged_in

        except WebDriverException as exc:
            logger.error("WebDriver error during cookie login: %s", exc)
            return False

    def logout(self) -> None:
        """Clear the browser session."""
        self._logged_in = False
        if self._driver:
            try:
                self._driver.delete_all_cookies()
            except WebDriverException:
                pass
        logger.info("Logged out")

    def quit(self) -> None:
        """Quit the WebDriver and release resources."""
        if self._driver:
            try:
                self._driver.quit()
            except WebDriverException:
                pass
            self._driver = None
        self._logged_in = False
        logger.info("WebDriver quit")

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _ensure_driver(self) -> None:
        """Create a Chrome WebDriver if one doesn't exist yet."""
        if self._driver is not None:
            return

        options = ChromeOptions()
        headless = self._settings.get("headless_browser", True)
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280,900")
        # Allow automatic PDF downloads without dialog
        prefs = {
            "download.default_directory": self._settings.get(
                "download_dir", config.DEFAULT_SETTINGS["download_dir"]
            ),
            "download.prompt_for_download": False,
            "plugins.always_open_pdf_externally": True,
        }
        options.add_experimental_option("prefs", prefs)

        if _WDM_AVAILABLE:
            service = ChromeService(ChromeDriverManager().install())
            self._driver = webdriver.Chrome(service=service, options=options)
        else:
            self._driver = webdriver.Chrome(options=options)

        logger.debug("WebDriver created (headless=%s)", headless)

    def _find_field(self, wait: WebDriverWait, locators: list) -> Optional[object]:
        """Try each locator in turn and return the first visible element."""
        for by, value in locators:
            try:
                element = wait.until(EC.presence_of_element_located((by, value)))
                if element.is_displayed():
                    return element
            except (TimeoutException, NoSuchElementException):
                continue
        return None

    def _verify_login(self) -> bool:
        """Return *True* if there is evidence of a successful login."""
        current_url = self._driver.current_url
        # If redirected away from the login page, assume success
        portal = self._settings.get("school_portal_url", config.SCHOOL_PORTAL_URL)
        if "login" not in current_url.lower():
            return True
        # Look for common error messages
        page_source = self._driver.page_source.lower()
        error_indicators = ["incorrect", "invalid", "error", "failed", "错误", "失败"]
        for indicator in error_indicators:
            if indicator in page_source:
                return False
        # No clear success / failure signal – assume success
        return True
