import logging
import re
from bs4 import BeautifulSoup, Tag

from .core import load_config
from .remote import fetch_remote_curl, fetch_via_flaresolverr

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
    """Extract JAV code pattern from filename (excluding FC2-PPV releases)."""
    if re.search(r"(?:^|[^A-Z0-9])FC2[-\s_]*(?:PPV[-\s_]*)?\d+", filename, re.IGNORECASE):
        return None
    match = re.search(r"([A-Z0-9]{3,7}-\d{2,5})", filename, re.IGNORECASE)
    return match.group(1).upper() if match else None


def lookup_jav_actresses(code: str, config: dict | None = None) -> list[str]:
    """Read explicit performer links on the matching OneJAV release card."""
    if not re.fullmatch(r"[A-Za-z0-9]+-\d+", code):
        return []
    if config is None:
        try:
            config = load_config()
        except Exception:
            config = {}

    slug = code.lower().replace("-", "")
    path = f"/torrent/{slug}"
    url = f"https://onejav.com{path}"
    page = fetch_via_flaresolverr(url, config)
    html = page["html"] if page else _ssh_curl(url, config)
    soup = BeautifulSoup(html or "", "html.parser")
    for card in soup.select(".card-content"):
        if card.select_one(f'.title a[href="{path}"]'):
            names = [
                a.get_text(strip=True)
                for a in card.select('.panel a[href^="/actress/"]')
                if a["href"].rstrip("/") != "/actress"
            ]
            return list(dict.fromkeys(name for name in names if name))
    return []


def _lookup_jav321_via_ssh(code: str, ssh_alias: str = "lt", timeout: int = 15) -> dict:
    """Read the fields next to the exact catalog number on a Jav321 detail page."""
    result = {"actresses": [], "makers": [], "genres": [], "title": None}
    match = re.fullmatch(r"([a-z0-9]+)-(\d+)", code.lower())
    if not match:
        return result
    prefix, number = match.groups()
    url = f"https://www.jav321.com/video/{prefix}{number.zfill(5)}"
    html = fetch_remote_curl(url, ssh_alias=ssh_alias, timeout=timeout)
    soup = BeautifulSoup(html or "", "html.parser")
    for label in soup.select(".col-md-9 > b"):
        if label.get_text(strip=True) != "品番":
            continue
        page_code = str(label.next_sibling).strip().lstrip(":：").strip()
        if page_code.upper() == code.upper():
            details = label.parent
            break
    else:
        return result

    cast = details.find("b", string="出演者")
    if cast:
        for node in cast.next_siblings:
            if node.name in ("br", "b"):
                break
            value = node.get_text(strip=True) if isinstance(node, Tag) else str(node)
            for name in re.split(r"[,、，]", value):
                name = name.strip().strip(":：").strip()
                if name and name not in ("----", "-", "不明") and name not in result["actresses"]:
                    result["actresses"].append(name)

    for field, href in (("makers", "/company/"), ("genres", "/genre/")):
        names = [a.get_text(strip=True) for a in details.select(f'a[href^="{href}"]')]
        result[field] = list(dict.fromkeys(name for name in names if name and name.lower() != "hd"))
    if soup.title:
        result["title"] = soup.title.get_text(strip=True).split(" bittorrent")[0].removesuffix(" sone-").strip()
    return result


def _lookup_javbus_via_ssh(code: str, ssh_alias: str = "lt", timeout: int = 15) -> dict:
    """JavBus SSH curl 조회."""
    if not re.fullmatch(r"[A-Za-z0-9]+-\d+", code):
        return {"actresses": [], "makers": [], "genres": [], "title": None}
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

    details = soup.select_one(".movie .info")
    if details is None or not any(
        span.get_text(strip=True).upper() == code.upper() for span in details.select("p span")
    ):
        return {"actresses": [], "makers": [], "genres": [], "title": None}

    for a in details.find_all("a", href=True):
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




