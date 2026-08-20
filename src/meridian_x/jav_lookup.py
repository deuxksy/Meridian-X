import logging
import re
from bs4 import BeautifulSoup

from .core import load_config
from .remote import fetch_remote_curl

logger = logging.getLogger(__name__)


def _fetch_page_via_ssh(url: str, config: dict | None = None, timeout: int = 15) -> str:
    """SSH 경유 (lt SSH alias 또는 default remote)로 URL curl 조회 (Cloudflare 우회)."""
    if config is None:
        try:
            config = load_config()
        except Exception:
            config = {}
    remote = config.get("sources", {}).get("onejav", {}).get("remote") or config.get("remote", {})
    ssh_alias = remote.get("ssh_alias", "lt")
    return fetch_remote_curl(url, ssh_alias=ssh_alias, timeout=timeout)


def _ssh_curl(url: str, config: dict | None = None, timeout: int = 15) -> str:
    """Backwards compatibility wrapper for _fetch_page_via_ssh."""
    return _fetch_page_via_ssh(url, config=config, timeout=timeout)


def extract_jav_code(filename: str) -> str | None:
    """Extract JAV code pattern from filename."""
    match = re.search(r"([A-Z0-9]{3,7}-\d{2,5})", filename, re.IGNORECASE)
    return match.group(1).upper() if match else None


def lookup_jav_actresses(code: str, config: dict | None = None) -> list[str]:
    """Fetch actress names for a given JAV code via SSH curl from OneJAV (Cloudflare bypass)."""
    if config is None:
        try:
            config = load_config()
        except Exception:
            config = {}

    code = code.upper()
    url = f"https://onejav.com/search/{code}"

    html = _ssh_curl(url, config)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    # 1. Prefer explicit /actress/ links
    actresses_list = []
    for tag in soup.find_all("a", href=re.compile(r"/actress/.+")):
        name = tag.get_text(strip=True)
        if name and name.lower() not in ["actresses", "tags"]:
            if name not in actresses_list:
                actresses_list.append(name)

    if actresses_list:
        return actresses_list

    # 2. Fallback to /tag/ links
    tags_set = set()
    for tag in soup.find_all("a", href=re.compile(r"/tag/")):
        name = tag.get_text(strip=True)
        if name and name.lower() not in ["720p", "1080p", "4k", "uncensored", "hd", "tags", "actresses"]:
            tags_set.add(name)

    return list(tags_set)


def _lookup_jav321_via_ssh(code: str, ssh_alias: str = "lt", timeout: int = 15) -> dict:
    """Jav321 SSH curl 조회."""
    url = f"https://www.jav321.com/search?sn={code}"
    html = fetch_remote_curl(url, ssh_alias=ssh_alias, timeout=timeout)
    if not html:
        return {"actresses": [], "makers": [], "genres": [], "title": None}

    soup = BeautifulSoup(html, "html.parser")
    actresses = []
    makers = []
    genres = []
    title = None

    title_tag = soup.find("title")
    if title_tag:
        t_text = title_tag.get_text(strip=True)
        if "JAV321" not in t_text:
            title = t_text.split(" sone-")[0].split(" bittorrent")[0].strip()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        name = a.get_text(strip=True)
        if not name:
            continue
        if "/star/" in href:
            if name not in actresses and name.lower() not in ["star", "actress"]:
                actresses.append(name)
        elif "/company/" in href:
            if name not in makers:
                makers.append(name)
        elif "/genre/" in href:
            if name not in genres and name.lower() not in ["genre", "hd"]:
                genres.append(name)

    return {"actresses": actresses, "makers": makers, "genres": genres, "title": title}


def _lookup_javbus_via_ssh(code: str, ssh_alias: str = "lt", timeout: int = 15) -> dict:
    """JavBus SSH curl 조회."""
    url = f"https://www.javbus.com/{code}"
    html = fetch_remote_curl(url, ssh_alias=ssh_alias, timeout=timeout)
    if not html:
        return {"actresses": [], "makers": [], "genres": [], "title": None}

    soup = BeautifulSoup(html, "html.parser")
    actresses = []
    makers = []
    genres = []
    title = None

    title_tag = soup.find("title")
    if title_tag:
        t_text = title_tag.get_text(strip=True)
        title = t_text.split(" - JavBus")[0].strip()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        name = a.get_text(strip=True)
        if not name:
            continue
        if "/star/" in href:
            if name not in actresses and name.lower() not in ["star", "actress"]:
                actresses.append(name)
        elif "/studio/" in href or "/label/" in href:
            if name not in makers:
                makers.append(name)
        elif "/genre/" in href:
            if name not in genres and name.lower() not in ["genre", "hd"]:
                genres.append(name)

    return {"actresses": actresses, "makers": makers, "genres": genres, "title": title}


def lookup_web_jav_metadata(code: str, config: dict | None = None) -> dict:
    """SSH curl 기반 웹 DB 조회 (Jav321/JavBus, OneJAV보다 높은 우선순위)."""
    if config is None:
        try:
            config = load_config()
        except Exception:
            config = {}

    remote = config.get("sources", {}).get("onejav", {}).get("remote") or config.get("remote", {})
    ssh_alias = remote.get("ssh_alias", "lt")
    code = code.upper()

    res = _lookup_jav321_via_ssh(code, ssh_alias=ssh_alias, timeout=15)
    if not res["actresses"] and not res["makers"] and not res["title"]:
        res = _lookup_javbus_via_ssh(code, ssh_alias=ssh_alias, timeout=15)

    return res




