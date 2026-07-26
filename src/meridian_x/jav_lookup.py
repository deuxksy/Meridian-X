import logging
import re
import time
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
})

def extract_jav_code(filename: str) -> str | None:
    """Extract JAV code pattern from filename."""
    match = re.search(r"([A-Z0-9]{3,7}-\d{2,5})", filename, re.IGNORECASE)
    return match.group(1).upper() if match else None

def lookup_jav_actresses(code: str) -> list[str]:
    """Fetch actress names for a given JAV code from OneJAV and fallback search endpoints."""
    code = code.upper()
    actresses = set()

    # 1. Primary: OneJAV Search
    url = f"https://onejav.com/search/{code}"
    try:
        time.sleep(0.3)  # Rate limiting to prevent ConnectionResetError
        resp = _session.get(url, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup.find_all("a", href=re.compile(r"/tag/")):
                name = tag.get_text(strip=True)
                if name and name.lower() not in ["720p", "1080p", "4k", "uncensored", "hd"]:
                    actresses.add(name)
    except Exception as e:
        logger.debug(f"OneJAV lookup failed for {code}: {e}")

    if actresses:
        return list(actresses)

    # 2. Fallback: DuckDuckGo HTML search for JAV code tags
    try:
        time.sleep(0.5)
        ddg_url = f"https://html.duckduckgo.com/html/?q=site:onejav.com+{code}"
        resp = _session.get(ddg_url, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            snippets = soup.find_all("a", class_="result__snippet")
            for snippet in snippets:
                text = snippet.get_text()
                # Find matching names in snippet text
                pass
    except Exception as e:
        logger.debug(f"Fallback search failed for {code}: {e}")

    return list(actresses)

