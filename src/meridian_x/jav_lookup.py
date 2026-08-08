import logging
import re
import subprocess
from bs4 import BeautifulSoup

from .core import load_config

logger = logging.getLogger(__name__)


def _ssh_curl(url: str, config: dict) -> str | None:
    """SSH 경유 (lt SSH alias 또는 default remote)로 OneJAV URL curl 조회 (Cloudflare 우회)."""
    remote = config.get("sources", {}).get("onejav", {}).get("remote") or config.get("remote", {})
    ssh_alias = remote.get("ssh_alias", "lt")
    
    if ssh_alias:
        args = ["ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no", ssh_alias, f'curl -sL "{url}"']
    elif remote.get("host"):
        args = ["ssh", "-i", remote["ssh_key"], "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no", f'{remote["user"]}@{remote["host"]}', f'curl -sL "{url}"']
    else:
        return None

    try:
        res = subprocess.run(args, capture_output=True, text=True, timeout=15)
        if res.returncode == 0 and res.stdout:
            return res.stdout
    except Exception as e:
        logger.debug(f"SSH curl failed for {url}: {e}")
    return None


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

    if ssh_alias:
        args = ["ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no", ssh_alias, f'curl -sL -d "sn={code}" "https://www.jav321.com/search"']
    elif remote.get("host"):
        args = ["ssh", "-i", remote["ssh_key"], "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no", f'{remote["user"]}@{remote["host"]}', f'curl -sL -d "sn={code}" "https://www.jav321.com/search"']
    else:
        return {"actresses": [], "makers": [], "genres": [], "title": None}

    try:
        res = subprocess.run(args, capture_output=True, text=True, timeout=15)
        if res.returncode != 0 or not res.stdout:
            return {"actresses": [], "makers": [], "genres": [], "title": None}

        soup = BeautifulSoup(res.stdout, "html.parser")
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
    except Exception as e:
        logger.debug(f"SSH curl web lookup failed for {code}: {e}")
        return {"actresses": [], "makers": [], "genres": [], "title": None}




