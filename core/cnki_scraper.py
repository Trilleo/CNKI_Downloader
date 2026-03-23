"""
CNKI scraper – search CNKI and parse paper metadata.

All browser interaction is delegated to the ``AuthManager``'s WebDriver so
that a single authenticated session is shared throughout the application.
"""

import time
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
)
from bs4 import BeautifulSoup

import config
from utils.logger import get_logger

logger = get_logger("cnki_downloader.scraper")

# CNKI search field codes used in the URL / form
SEARCH_FIELD_MAP = {
    "Keywords":         "KY",
    "Title":            "TI",
    "Author":           "AU",
    "Abstract":         "AB",
    "Journal Name":     "JN",
    "Subject":          "SU",
    "DOI":              "DOI",
    "Fund":             "FU",
    "Publication Year": "YE",
}


class PaperMetadata:
    """Simple value-object for a single CNKI search result."""

    def __init__(
        self,
        title: str = "",
        authors: str = "",
        journal: str = "",
        year: str = "",
        abstract: str = "",
        doi: str = "",
        cnki_id: str = "",
        download_url: str = "",
        detail_url: str = "",
    ) -> None:
        self.title = title
        self.authors = authors
        self.journal = journal
        self.year = year
        self.abstract = abstract
        self.doi = doi
        self.cnki_id = cnki_id
        self.download_url = download_url
        self.detail_url = detail_url

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "authors": self.authors,
            "journal": self.journal,
            "year": self.year,
            "abstract": self.abstract,
            "doi": self.doi,
            "cnki_id": self.cnki_id,
            "download_url": self.download_url,
            "detail_url": self.detail_url,
        }

    def __repr__(self) -> str:
        return f"PaperMetadata(title={self.title!r}, year={self.year!r})"


class CNKIScraper:
    """Perform searches on CNKI and return structured paper metadata."""

    def __init__(self, auth_manager) -> None:
        self._auth = auth_manager

    # ── Public API ───────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        method: str = "Keywords",
        year_from: Optional[str] = None,
        year_to: Optional[str] = None,
        max_results: int = 20,
    ) -> list[PaperMetadata]:
        """
        Search CNKI for *query* using *method* and return a list of
        ``PaperMetadata`` objects (up to *max_results*).
        """
        if not query.strip():
            return []

        driver = self._auth.driver
        if driver is None:
            logger.error("No WebDriver available – please log in first")
            return []

        try:
            results = self._run_search(driver, query, method, year_from, year_to, max_results)
            logger.info("Search returned %d results", len(results))
            return results
        except WebDriverException as exc:
            logger.error("WebDriver error during search: %s", exc)
            return []

    def get_download_url(self, paper: PaperMetadata) -> str:
        """
        Navigate to the paper's detail page and extract the PDF download link.
        Returns an empty string if the link could not be found.
        """
        driver = self._auth.driver
        if driver is None or not paper.detail_url:
            return ""

        try:
            driver.get(paper.detail_url)
            wait = WebDriverWait(driver, config.BROWSER_TIMEOUT)
            time.sleep(config.PAGE_LOAD_SLEEP)

            # Common selectors for the PDF download button on CNKI
            selectors = [
                (By.CSS_SELECTOR, "a.btn-pdf"),
                (By.CSS_SELECTOR, "a[href*='.pdf']"),
                (By.LINK_TEXT, "PDF下载"),
                (By.PARTIAL_LINK_TEXT, "PDF"),
                (By.CSS_SELECTOR, ".download-btn"),
            ]
            for by, value in selectors:
                try:
                    element = wait.until(EC.element_to_be_clickable((by, value)))
                    href = element.get_attribute("href") or ""
                    if href:
                        logger.debug("PDF link found: %s", href)
                        return href
                except TimeoutException:
                    continue

            logger.warning("Could not find PDF download link for: %s", paper.title)
            return ""
        except WebDriverException as exc:
            logger.error("Error fetching download URL: %s", exc)
            return ""

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _run_search(
        self,
        driver,
        query: str,
        method: str,
        year_from: Optional[str],
        year_to: Optional[str],
        max_results: int,
    ) -> list[PaperMetadata]:
        search_url = config.CNKI_SEARCH_URL
        driver.get(search_url)
        time.sleep(config.PAGE_LOAD_SLEEP)

        wait = WebDriverWait(driver, config.BROWSER_TIMEOUT)

        # ── Select search field ──────────────────────────────────────────────
        try:
            field_select_el = driver.find_element(By.CSS_SELECTOR, "select.search-field, #txt_1_sel")
            sel = Select(field_select_el)
            field_code = SEARCH_FIELD_MAP.get(method, "SU")
            try:
                sel.select_by_value(field_code)
            except NoSuchElementException:
                pass  # keep whatever default is selected
        except NoSuchElementException:
            pass

        # ── Enter query ──────────────────────────────────────────────────────
        input_box = None
        for selector in [
            (By.CSS_SELECTOR, "input#txt_1_value1"),
            (By.CSS_SELECTOR, "input.search-input"),
            (By.CSS_SELECTOR, "input[type='text']"),
            (By.NAME, "querystring"),
        ]:
            try:
                input_box = driver.find_element(*selector)
                break
            except NoSuchElementException:
                continue

        if input_box is None:
            logger.error("Could not find search input box")
            return []

        input_box.clear()
        input_box.send_keys(query)

        # ── Year filter ──────────────────────────────────────────────────────
        if year_from or year_to:
            self._apply_year_filter(driver, year_from, year_to)

        # ── Submit ───────────────────────────────────────────────────────────
        input_box.send_keys(Keys.RETURN)
        time.sleep(config.PAGE_LOAD_SLEEP * 2)

        # ── Parse results page ───────────────────────────────────────────────
        return self._parse_results_page(driver, max_results)

    def _apply_year_filter(
        self, driver, year_from: Optional[str], year_to: Optional[str]
    ) -> None:
        try:
            if year_from:
                el = driver.find_element(By.CSS_SELECTOR, "input#dateFrom, input[name='yearFrom']")
                el.clear()
                el.send_keys(year_from)
            if year_to:
                el = driver.find_element(By.CSS_SELECTOR, "input#dateTo, input[name='yearTo']")
                el.clear()
                el.send_keys(year_to)
        except NoSuchElementException:
            logger.debug("Year filter fields not found on this page")

    def _parse_results_page(self, driver, max_results: int) -> list[PaperMetadata]:
        soup = BeautifulSoup(driver.page_source, "html.parser")
        papers: list[PaperMetadata] = []

        # CNKI result rows use different class names depending on the portal.
        row_selectors = [
            {"class": "result-table-list"},   # kns8
            {"class": "search-result"},
            {"id": "gridTable"},
        ]

        result_rows = []
        for selector in row_selectors:
            container = soup.find("table", selector) or soup.find("div", selector)
            if container:
                result_rows = container.find_all("tr") or container.find_all("div", class_="item")
                break

        # Fallback: look for <tr> elements with title links
        if not result_rows:
            result_rows = soup.select("tr.odd, tr.even, tr[class*='result']")

        for row in result_rows[:max_results]:
            paper = self._parse_row(row)
            if paper and paper.title:
                papers.append(paper)

        return papers

    def _parse_row(self, row) -> Optional[PaperMetadata]:
        try:
            # Title and detail URL
            title_tag = (
                row.find("a", class_="fz14")
                or row.find("td", class_="name")
                or row.find("a", attrs={"title": True})
                or row.find("a")
            )
            if not title_tag:
                return None

            title = title_tag.get_text(strip=True)
            detail_url = title_tag.get("href", "")
            if detail_url and not detail_url.startswith("http"):
                detail_url = config.CNKI_BASE_URL + detail_url

            # Authors
            author_tags = row.find_all("a", attrs={"data-author": True}) or row.find_all("a", class_="author")
            authors = ", ".join(a.get_text(strip=True) for a in author_tags)
            if not authors:
                author_td = row.find("td", class_="author") or row.find("td", class_="creator")
                if author_td:
                    authors = author_td.get_text(strip=True)

            # Journal
            journal_tag = row.find("a", class_="journal") or row.find("td", class_="source")
            journal = journal_tag.get_text(strip=True) if journal_tag else ""

            # Year
            year_td = row.find("td", class_="year") or row.find("td", class_="date")
            year = year_td.get_text(strip=True)[:4] if year_td else ""

            # CNKI ID from the URL
            cnki_id = ""
            if "filename=" in detail_url:
                cnki_id = detail_url.split("filename=")[-1].split("&")[0]

            return PaperMetadata(
                title=title,
                authors=authors,
                journal=journal,
                year=year,
                detail_url=detail_url,
                cnki_id=cnki_id,
            )
        except Exception as exc:
            logger.debug("Could not parse result row: %s", exc)
            return None
