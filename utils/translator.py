"""
Translation utility for CNKI Downloader.

Provides a simple dictionary-based translation system supporting
English (en) and Simplified Chinese (zh_CN).
"""

from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from utils.logger import get_logger

logger = get_logger("cnki_downloader.translator")

# ─── Translation dictionaries ─────────────────────────────────────────────────

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        # Menu
        "menu.file": "&File",
        "menu.file.login": "&Login…",
        "menu.file.cookie_login": "Login with &Cookies…",
        "menu.file.logout": "Log&out",
        "menu.file.settings": "&Settings…",
        "menu.file.quit": "&Quit",
        "menu.language": "&Language",
        "menu.help": "&Help",
        "menu.help.about": "&About",

        # Language options
        "lang.en": "English",
        "lang.zh_CN": "简体中文",

        # Login banner
        "banner.not_logged_in": "⚠  Not logged in – please log in via File → Login…",
        "banner.logged_in": "✅  Logged in as {username}",
        "banner.login_failed": "❌  Login failed – check credentials or portal URL",
        "banner.cookie_logged_in": "✅  Logged in via browser cookies",
        "banner.cookie_login_failed": "❌  Cookie login failed – cookies may be expired or invalid",
        "banner.login_btn": "Login",

        # Tabs
        "tab.search": "🔍  Search",
        "tab.history": "📋  History",
        "tab.settings": "⚙  Settings",

        # Search tab
        "search.parameters": "Search Parameters",
        "search.method": "Search method:",
        "search.query": "Query:",
        "search.query_placeholder": "Enter search terms…",
        "search.year_from": "Year from:",
        "search.year_from_placeholder": "e.g. 2010",
        "search.year_to": "to:",
        "search.year_to_placeholder": "e.g. 2024",
        "search.max_results": "Max results:",
        "search.search_btn": "Search",
        "search.searching_btn": "Searching…",

        # Results
        "results.title": "Results",
        "results.col.title": "Title",
        "results.col.authors": "Authors",
        "results.col.journal": "Journal",
        "results.col.year": "Year",
        "results.select_all": "Select all",
        "results.deselect_all": "Deselect all",
        "results.download_selected": "⬇  Download selected",

        # History tab
        "history.col.date": "Date",
        "history.col.method": "Method",
        "history.col.query": "Query",
        "history.col.results": "Results",
        "history.reload": "Reload history",
        "history.delete": "Delete selected",
        "history.clear": "Clear all",
        "history.clear_confirm_title": "Clear History",
        "history.clear_confirm_msg": "Are you sure you want to delete all search history?",

        # Settings tab
        "settings.quick_settings": "Quick Settings",
        "settings.note": (
            "For full settings, use <b>File → Settings…</b>. "
            "Changes here are saved immediately."
        ),
        "settings.download_dir": "Download directory:",
        "settings.browse": "Browse…",
        "settings.headless": "Headless browser:",
        "settings.select_dir": "Select download directory",

        # Status bar
        "status.ready": "Ready",
        "status.logging_in": "Logging in…",
        "status.logged_in": "Logged in successfully.",
        "status.login_failed": "Login failed.",
        "status.logging_in_cookies": "Logging in with cookies…",
        "status.cookie_login_ok": "Cookie login successful.",
        "status.cookie_login_failed": "Cookie login failed.",
        "status.logged_out": "Logged out.",
        "status.searching": 'Searching for "{query}"…',
        "status.found_results": "Found {count} results.",
        "status.search_failed": "Search failed.",
        "status.downloading": "Downloading {count} paper(s)…",

        # Dialog messages
        "msg.login_required_title": "Login Required",
        "msg.login_required": "Please log in before searching.",
        "msg.empty_query_title": "Empty Query",
        "msg.empty_query": "Please enter a search term.",
        "msg.search_error_title": "Search Error",
        "msg.search_error": "Search failed:\n{message}",
        "msg.no_selection_title": "No Selection",
        "msg.no_selection": "Please check at least one paper to download.",
        "msg.busy_title": "Busy",
        "msg.busy": "A download is already in progress. Please wait.",
        "msg.login_failed_title": "Login Failed",
        "msg.login_failed": (
            "Could not log in. Please check your credentials "
            "and portal URL in Settings."
        ),
        "msg.cookie_login_failed_title": "Cookie Login Failed",
        "msg.cookie_login_failed": (
            "Could not log in with the provided cookies.\n"
            "They may be expired or not contain the required session data."
        ),
        "msg.downloads_in_progress_title": "Downloads in Progress",
        "msg.downloads_in_progress": "A download is still running. Quit anyway?",

        # About
        "about.title": "About {app_name}",
        "about.text": (
            "<b>{app_name}</b> v{version}<br><br>"
            "Search and download papers from CNKI using your school account."
            "<br><br>Built with Python, PyQt6, and Selenium."
        ),

        # Login dialog
        "login.title": "Login – School Portal",
        "login.heading": "<b>Sign in with your school account</b>",
        "login.portal_url": "Portal URL:",
        "login.portal_placeholder": "https://your-school-portal/login",
        "login.username": "Username:",
        "login.username_placeholder": "Student / employee ID",
        "login.password": "Password:",
        "login.remember": "Remember credentials (stored locally)",
        "login.username_required": "Username is required.",
        "login.password_required": "Password is required.",

        # Cookie login dialog
        "cookie_login.title": "Login with Browser Cookies",
        "cookie_login.heading": "<b>Paste cookies from your browser</b>",
        "cookie_login.instructions": (
            "Open your browser where you are already logged in to CNKI, "
            "copy the cookie header value from the developer tools "
            "(Network tab → any request → <i>Cookie</i> header), "
            "and paste it below.\n\n"
            "Expected format: <code>name1=value1; name2=value2; …</code>"
        ),
        "cookie_login.placeholder": "name1=value1; name2=value2; …",
        "cookie_login.empty": "Please paste your cookie string.",
        "cookie_login.parse_error": (
            "Could not parse any cookies. "
            "Use the format: name=value; name2=value2"
        ),

        # FSSO redirect login
        "menu.file.fsso_login": "Login with School &Portal (FSSO)…",
        "fsso_login.title": "School Portal Login (FSSO)",
        "fsso_login.instructions": (
            "A browser window will open the CNKI school login page.\n"
            "Select your institution, log in with your school account, "
            "and wait for the process to complete.\n\n"
            "Do <b>not</b> close the browser window manually."
        ),
        "status.logging_in_fsso": "Waiting for school portal login…",
        "status.fsso_login_ok": "School portal login successful.",
        "status.fsso_login_failed": "School portal login failed.",
        "banner.fsso_logged_in": "✅  Logged in via school portal (FSSO)",
        "banner.fsso_login_failed": (
            "❌  School portal login failed – timed out or browser was closed"
        ),
        "msg.fsso_login_failed_title": "School Portal Login Failed",
        "msg.fsso_login_failed": (
            "Could not complete the school portal login.\n"
            "The login may have timed out or the browser window was closed."
        ),
        "msg.login_error_title": "Login Error",
        "msg.login_error": "An unexpected error occurred during login:\n{message}",

        # Settings dialog
        "settings_dialog.title": "Settings",
        "settings_dialog.downloads": "Downloads",
        "settings_dialog.download_dir": "Download directory:",
        "settings_dialog.browse": "Browse…",
        "settings_dialog.max_concurrent": "Max concurrent downloads:",
        "settings_dialog.search": "Search",
        "settings_dialog.default_method": "Default search method:",
        "settings_dialog.results_per_page": "Results per page:",
        "settings_dialog.browser": "Browser",
        "settings_dialog.headless": "Run browser in headless mode (no visible window)",
        "settings_dialog.portal_url": "School portal URL:",
        "settings_dialog.select_dir": "Select download directory",

        # Download progress dialog
        "download_progress.title": "Downloading…",
        "download_progress.preparing": "Preparing…",
        "download_progress.cancel": "Cancel",
        "download_progress.close": "Close",
        "download_progress.downloading": "Downloading: {filename}",
        "download_progress.summary": "{current} / {total} completed",
        "download_progress.done": "Done!",
        "download_progress.finished": (
            "Completed: {success} succeeded, {fail} failed"
        ),
    },

    "zh_CN": {
        # Menu
        "menu.file": "文件(&F)",
        "menu.file.login": "登录(&L)…",
        "menu.file.cookie_login": "Cookie 登录(&C)…",
        "menu.file.logout": "退出登录(&O)",
        "menu.file.settings": "设置(&S)…",
        "menu.file.quit": "退出(&Q)",
        "menu.language": "语言(&L)",
        "menu.help": "帮助(&H)",
        "menu.help.about": "关于(&A)",

        # Language options
        "lang.en": "English",
        "lang.zh_CN": "简体中文",

        # Login banner
        "banner.not_logged_in": "⚠  未登录 - 请通过 文件 → 登录… 进行登录",
        "banner.logged_in": "✅  已登录：{username}",
        "banner.login_failed": "❌  登录失败 - 请检查账号密码或门户网址",
        "banner.cookie_logged_in": "✅  已通过浏览器 Cookie 登录",
        "banner.cookie_login_failed": "❌  Cookie 登录失败 - Cookie 可能已过期或无效",
        "banner.login_btn": "登录",

        # Tabs
        "tab.search": "🔍  搜索",
        "tab.history": "📋  历史记录",
        "tab.settings": "⚙  设置",

        # Search tab
        "search.parameters": "搜索参数",
        "search.method": "搜索方式：",
        "search.query": "关键词：",
        "search.query_placeholder": "请输入搜索词…",
        "search.year_from": "起始年份：",
        "search.year_from_placeholder": "如 2010",
        "search.year_to": "至：",
        "search.year_to_placeholder": "如 2024",
        "search.max_results": "最大结果数：",
        "search.search_btn": "搜索",
        "search.searching_btn": "搜索中…",

        # Results
        "results.title": "搜索结果",
        "results.col.title": "标题",
        "results.col.authors": "作者",
        "results.col.journal": "期刊",
        "results.col.year": "年份",
        "results.select_all": "全选",
        "results.deselect_all": "取消全选",
        "results.download_selected": "⬇  下载选中",

        # History tab
        "history.col.date": "日期",
        "history.col.method": "搜索方式",
        "history.col.query": "搜索词",
        "history.col.results": "结果数",
        "history.reload": "刷新历史",
        "history.delete": "删除选中",
        "history.clear": "清空全部",
        "history.clear_confirm_title": "清空历史记录",
        "history.clear_confirm_msg": "确定要删除所有搜索历史记录吗？",

        # Settings tab
        "settings.quick_settings": "快捷设置",
        "settings.note": (
            "如需完整设置，请使用 <b>文件 → 设置…</b>。"
            "此处的更改会立即保存。"
        ),
        "settings.download_dir": "下载目录：",
        "settings.browse": "浏览…",
        "settings.headless": "无头浏览器：",
        "settings.select_dir": "选择下载目录",

        # Status bar
        "status.ready": "就绪",
        "status.logging_in": "正在登录…",
        "status.logged_in": "登录成功。",
        "status.login_failed": "登录失败。",
        "status.logging_in_cookies": "正在通过 Cookie 登录…",
        "status.cookie_login_ok": "Cookie 登录成功。",
        "status.cookie_login_failed": "Cookie 登录失败。",
        "status.logged_out": "已退出登录。",
        "status.searching": '正在搜索"{query}"…',
        "status.found_results": "找到 {count} 条结果。",
        "status.search_failed": "搜索失败。",
        "status.downloading": "正在下载 {count} 篇论文…",

        # Dialog messages
        "msg.login_required_title": "需要登录",
        "msg.login_required": "请先登录后再搜索。",
        "msg.empty_query_title": "搜索词为空",
        "msg.empty_query": "请输入搜索词。",
        "msg.search_error_title": "搜索错误",
        "msg.search_error": "搜索失败：\n{message}",
        "msg.no_selection_title": "未选择",
        "msg.no_selection": "请至少选中一篇论文进行下载。",
        "msg.busy_title": "下载中",
        "msg.busy": "下载正在进行中，请稍候。",
        "msg.login_failed_title": "登录失败",
        "msg.login_failed": "无法登录，请检查您的账号密码和设置中的门户网址。",
        "msg.cookie_login_failed_title": "Cookie 登录失败",
        "msg.cookie_login_failed": (
            "无法使用提供的 Cookie 登录。\n"
            "Cookie 可能已过期或不包含所需的会话数据。"
        ),
        "msg.downloads_in_progress_title": "下载进行中",
        "msg.downloads_in_progress": "仍有下载任务正在运行，确定要退出吗？",

        # About
        "about.title": "关于 {app_name}",
        "about.text": (
            "<b>{app_name}</b> v{version}<br><br>"
            "使用学校账号从 CNKI 搜索和下载论文。"
            "<br><br>基于 Python、PyQt6 和 Selenium 构建。"
        ),

        # Login dialog
        "login.title": "登录 - 学校门户",
        "login.heading": "<b>使用学校账号登录</b>",
        "login.portal_url": "门户网址：",
        "login.portal_placeholder": "https://your-school-portal/login",
        "login.username": "用户名：",
        "login.username_placeholder": "学号 / 工号",
        "login.password": "密码：",
        "login.remember": "记住账号（本地存储）",
        "login.username_required": "请输入用户名。",
        "login.password_required": "请输入密码。",

        # Cookie login dialog
        "cookie_login.title": "使用浏览器 Cookie 登录",
        "cookie_login.heading": "<b>粘贴浏览器中的 Cookie</b>",
        "cookie_login.instructions": (
            "打开已登录 CNKI 的浏览器，从开发者工具"
            "（网络标签页 → 任意请求 → <i>Cookie</i> 头部）"
            "复制 Cookie 值，粘贴到下方。\n\n"
            "格式：<code>name1=value1; name2=value2; …</code>"
        ),
        "cookie_login.placeholder": "name1=value1; name2=value2; …",
        "cookie_login.empty": "请粘贴 Cookie 字符串。",
        "cookie_login.parse_error": "无法解析 Cookie。请使用格式：name=value; name2=value2",

        # FSSO redirect login
        "menu.file.fsso_login": "学校门户登录 (FSSO)(&P)…",
        "fsso_login.title": "学校门户登录 (FSSO)",
        "fsso_login.instructions": (
            "将打开浏览器窗口跳转到 CNKI 学校登录页面。\n"
            "请选择您的学校，使用学校账号登录，"
            "等待流程完成。\n\n"
            "<b>请勿</b>手动关闭浏览器窗口。"
        ),
        "status.logging_in_fsso": "正在等待学校门户登录…",
        "status.fsso_login_ok": "学校门户登录成功。",
        "status.fsso_login_failed": "学校门户登录失败。",
        "banner.fsso_logged_in": "✅  已通过学校门户 (FSSO) 登录",
        "banner.fsso_login_failed": "❌  学校门户登录失败 - 超时或浏览器已关闭",
        "msg.fsso_login_failed_title": "学校门户登录失败",
        "msg.fsso_login_failed": (
            "无法完成学校门户登录。\n"
            "登录可能已超时或浏览器窗口已关闭。"
        ),
        "msg.login_error_title": "登录错误",
        "msg.login_error": "登录过程中发生意外错误：\n{message}",

        # Settings dialog
        "settings_dialog.title": "设置",
        "settings_dialog.downloads": "下载",
        "settings_dialog.download_dir": "下载目录：",
        "settings_dialog.browse": "浏览…",
        "settings_dialog.max_concurrent": "最大并发下载数：",
        "settings_dialog.search": "搜索",
        "settings_dialog.default_method": "默认搜索方式：",
        "settings_dialog.results_per_page": "每页结果数：",
        "settings_dialog.browser": "浏览器",
        "settings_dialog.headless": "以无头模式运行浏览器（无可见窗口）",
        "settings_dialog.portal_url": "学校门户网址：",
        "settings_dialog.select_dir": "选择下载目录",

        # Download progress dialog
        "download_progress.title": "下载中…",
        "download_progress.preparing": "准备中…",
        "download_progress.cancel": "取消",
        "download_progress.close": "关闭",
        "download_progress.downloading": "正在下载：{filename}",
        "download_progress.summary": "{current} / {total} 已完成",
        "download_progress.done": "完成！",
        "download_progress.finished": "已完成：{success} 成功，{fail} 失败",
    },
}

SUPPORTED_LANGUAGES = ["en", "zh_CN"]
DEFAULT_LANGUAGE = "en"


class Translator(QObject):
    """Application-wide translator with language switching support.

    Use the module-level :func:`tr` function for convenience.
    """

    language_changed = pyqtSignal(str)

    _instance: "Translator | None" = None

    def __init__(self) -> None:
        super().__init__()
        self._language = DEFAULT_LANGUAGE

    @classmethod
    def instance(cls) -> "Translator":
        """Return the singleton *Translator* instance."""
        if cls._instance is None:
            cls._instance = Translator()
        return cls._instance

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, lang: str) -> None:
        """Switch the active language and emit *language_changed*."""
        if lang not in SUPPORTED_LANGUAGES:
            logger.warning("Unsupported language: %s", lang)
            return
        if lang == self._language:
            return
        self._language = lang
        logger.info("Language changed to %s", lang)
        self.language_changed.emit(lang)

    def translate(self, key: str, **kwargs: Any) -> str:
        """Return the translated string for *key* in the active language.

        Supports ``str.format``-style placeholders (e.g. ``{username}``).
        Falls back to the English translation, then to *key* itself.
        """
        text = TRANSLATIONS.get(self._language, {}).get(key)
        if text is None:
            text = TRANSLATIONS.get(DEFAULT_LANGUAGE, {}).get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError as exc:
                logger.warning("Missing placeholder %s in translation key '%s'", exc, key)
        return text


def tr(key: str, **kwargs: Any) -> str:
    """Module-level shortcut for ``Translator.instance().translate(key)``."""
    return Translator.instance().translate(key, **kwargs)
