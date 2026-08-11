"""
XXXClub Source
RSS 수집 → magnet link 직접 추출
"""
import html
import logging
import re
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup
import requests
from meridian_x.classify import (
    _normalize_name,
    get_artist_folders,
    get_studio_mappings,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://xxxclub.to"


def is_whitelisted_title(title: str, config: dict) -> bool:
    """Check if title contains any configured WEST artist, WEST studio, or genre keyword."""
    genres = config.get("genres", {})

    keywords = set(get_artist_folders(config, region="WEST"))
    for studio, aliases in get_studio_mappings(config, region="WEST").items():
        keywords.add(studio)
        keywords.update(aliases)

    for genre_name, rules in genres.items():
        keywords.add(genre_name)
        keywords.update(rules.get("keywords", []))
        keywords.update(rules.get("prefixes", []))

    norm_title = _normalize_name(title)
    for kw in keywords:
        if kw and _normalize_name(kw) in norm_title:
            return True
    return False



def discover(config: dict) -> list[dict]:
    """XXXClub RSS에서 수집 항목 반환."""
    rss_url = config.get("rss_url")
    if not rss_url:
        logger.error("xxxclub rss_url not configured")
        return []

    user_agent = config.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    timeout = config.get("request_timeout", 30)

    try:
        response = requests.get(rss_url, headers={"User-Agent": user_agent}, timeout=timeout)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"XXXClub RSS fetch failed: {e}")
        return []

    items = _parse_rss(response.text)
    if config.get("selective_only", True):
        items = [i for i in items if is_whitelisted_title(i["title"], config)]
    return items


def resolve(item: dict, config: dict) -> dict | None:
    """magnet link를 그대로 반환 (페이지 방문 불필요)."""
    magnet_url = item.get("magnet_url")
    if not magnet_url:
        return None
    return {"type": "magnet", "data": magnet_url}


def _parse_rss(rss_content: str) -> list[dict]:
    """XXXClub RSS에서 title + magnet link 추출."""
    links = []
    item_pattern = re.compile(
        r"<item><title>(.*?)</title><link>(.*?)</link>",
    )
    for match in item_pattern.finditer(rss_content):
        title = html.unescape(match.group(1)).strip()
        link = html.unescape(match.group(2)).strip()

        # infohash 추출 (Codex 검증 반영: title 기반 ID 충돌 방지)
        hash_match = re.search(r'btih:([a-fA-F0-9]{40})', link)
        if hash_match:
            torrent_id = "xxxclub:" + hash_match.group(1).lower()
        else:
            # fallback: title 기반
            clean_id = re.sub(r'[^\w\s]', '', title).replace(' ', '_')[:50]
            torrent_id = "xxxclub:" + clean_id

        links.append({
            "id": torrent_id,
            "title": title,
            "magnet_url": link,
            "page_url": link,
            "description": ""
        })
    return links


def search(query: str, category: str = "1080p", config: dict = None) -> list[dict]:
    """XXXClub 카테고리/키워드 검색 결과 반환."""
    if config is None:
        config = {}

    encoded_query = quote(query)
    search_url = f"{BASE_URL}/search/{category}/{encoded_query}"

    user_agent = config.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    timeout = config.get("request_timeout", 30)

    try:
        response = requests.get(search_url, headers={"User-Agent": user_agent}, timeout=timeout)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"XXXClub search request failed for '{query}': {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    items = []

    # tr parsing (or specific row selectors based on site structure)
    for row in soup.select("tr.torrents-row, table tr"):
        name_elem = row.select_one("td.name a, a[href*='/details/']")
        if not name_elem or not name_elem.get("href"):
            continue

        href = name_elem.get("href")
        details_url = urljoin(BASE_URL, href)
        title = name_elem.get_text(strip=True)

        # Torrent ID generation
        hash_match = re.search(r'/details/([^/]+)', href)
        slug_id = hash_match.group(1) if hash_match else title
        torrent_id = f"xxxclub:{slug_id}"

        size_elem = row.select_one("td.size, td:nth-of-type(4)")
        seed_elem = row.select_one("td.seeders, td:nth-of-type(5)")
        leech_elem = row.select_one("td.leechers, td:nth-of-type(6)")

        size = size_elem.get_text(strip=True) if size_elem else ""
        seeders = seed_elem.get_text(strip=True) if seed_elem else "0"
        leechers = leech_elem.get_text(strip=True) if leech_elem else "0"

        items.append({
            "id": torrent_id,
            "title": title,
            "details_url": details_url,
            "size": size,
            "seeders": seeders,
            "leechers": leechers,
        })

    return items


def resolve_magnet(details_url: str, config: dict = None) -> str | None:
    """상세 페이지 URL에서 magnet link 추출."""
    if config is None:
        config = {}

    user_agent = config.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    timeout = config.get("request_timeout", 30)

    try:
        response = requests.get(details_url, headers={"User-Agent": user_agent}, timeout=timeout)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"XXXClub details fetch failed for {details_url}: {e}")
        return None

    match = re.search(r'href=["\'](magnet:\?xt=urn:btih:[^"\']+)["\']', response.text, re.IGNORECASE)
    if match:
        return html.unescape(match.group(1))
    return None

