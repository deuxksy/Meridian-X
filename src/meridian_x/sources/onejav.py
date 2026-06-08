"""
OneJAV Source
RSS 수집 → 페이지 방문 → .torrent 바이트
"""
import logging
import re
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)


def discover(config: dict) -> list[dict]:
    """OneJAV RSS에서 수집 항목 반환."""
    rss_url = config.get("rss_url", "https://onejav.com/feeds/")
    user_agent = config.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    timeout = config.get("request_timeout", 30)

    try:
        response = requests.get(rss_url, headers={"User-Agent": user_agent}, timeout=timeout)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"OneJAV RSS fetch failed: {e}")
        return []

    return _parse_rss(response.text)


def resolve(item: dict, config: dict) -> dict | None:
    """페이지에서 .torrent 바이트를 가져와 metainfo payload 반환."""
    page_url = item["page_url"]
    base_url = config.get("base_url", "https://onejav.com")
    user_agent = config.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    timeout = config.get("request_timeout", 30)

    try:
        headers = {"User-Agent": user_agent}
        response = requests.get(page_url, headers=headers, timeout=timeout)
        response.raise_for_status()

        match = re.search(r'href="(/torrent/[^/]+/download/\d+/[^"]+\.torrent)"', response.text)
        if match:
            download_url = urljoin(base_url, match.group(1))
            torrent_response = requests.get(download_url, headers=headers, timeout=timeout)
            torrent_response.raise_for_status()
            return {"type": "metainfo", "data": torrent_response.content}

        logger.warning(f"No download link on {page_url}")
        return None
    except Exception as e:
        logger.error(f"OneJAV resolve failed for {page_url}: {e}")
        return None


def _parse_rss(rss_content: str) -> list[dict]:
    """OneJAV RSS에서 항목 추출."""
    links = []
    item_pattern = re.compile(
        r"<item>.*?<title>(?:<!\[CDATA\[)?(.+?)(?:\]\]>)?</title>.*?"
        r"<link>(.+?)</link>.*?"
        r"<description>(?:<!\[CDATA\[)?(.+?)(?:\]\]>)?</description>.*?</item>",
        re.DOTALL
    )
    for match in item_pattern.finditer(rss_content):
        title = match.group(1).strip()
        link = match.group(2).strip()
        description = match.group(3).strip()
        torrent_id = "onejav:" + link.split("/")[-1].upper()
        links.append({
            "id": torrent_id,
            "title": title,
            "page_url": link,
            "description": description
        })
    return links
