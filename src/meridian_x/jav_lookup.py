import logging
import re
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def extract_jav_code(filename: str) -> str | None:
    """Extract JAV code pattern from filename."""
    match = re.search(r"([A-Z0-9]{3,7}-\d{2,5})", filename, re.IGNORECASE)
    return match.group(1).upper() if match else None

def lookup_jav_actresses(code: str) -> list[str]:
    """Fetch actress names for a given JAV code from OneJAV search."""
    url = f"https://onejav.com/search/{code}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        actresses = []
        for tag in soup.find_all("a", href=re.compile(r"/tag/")):
            name = tag.get_text(strip=True)
            if name and name.lower() not in ["720p", "1080p", "4k", "uncensored"]:
                actresses.append(name)
        return actresses
    except Exception as e:
        logger.warning(f"JAV lookup failed for {code}: {e}")
        return []
