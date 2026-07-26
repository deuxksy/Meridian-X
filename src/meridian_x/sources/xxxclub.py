"""
XXXClub Source
RSS 수집 → magnet link 직접 추출
"""
import html
import logging
import re

import requests
from meridian_x.classify import (
    _normalize_name,
    get_artist_folders,
    get_studio_mappings,
)

logger = logging.getLogger(__name__)


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
