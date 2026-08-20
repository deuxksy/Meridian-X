"""
Sukebei (Nyaa) Source for 신사 실사 (JAV/FC2/무수정)
RSS 수집 및 HTML 검색 → magnet link 추출
"""
import html
import logging
import re
import shlex
import subprocess
from urllib.parse import quote, urljoin, urlparse
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup
from meridian_x.classify import (
    _normalize_name,
    get_artist_folders,
    get_studio_mappings,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://sukebei.nyaa.si"
NYAA_NS = {"nyaa": "https://nyaa.si/xmlns/nyaa"}
JPN_CODE_PATTERN = re.compile(r'\b[A-Za-z]{2,8}[-_]?\d{3,5}\b|\bFC2[-_ ]?PPV[-_ ]?\d+\b', re.IGNORECASE)


def _safe_timeout(config: dict) -> int:
    try:
        timeout = int(config.get("request_timeout", 30))
        return max(1, timeout)
    except (ValueError, TypeError):
        return 30


def _ssh(remote: dict, cmd: str, timeout: int = 60) -> tuple[bool, str]:
    try:
        if remote.get("ssh_alias"):
            args = [
                "ssh",
                "-o", "ConnectTimeout=5",
                "-o", "StrictHostKeyChecking=no",
                remote["ssh_alias"],
                cmd,
            ]
        elif remote.get("host") and remote.get("user"):
            args = [
                "ssh",
                "-o", "ConnectTimeout=5",
                "-o", "StrictHostKeyChecking=no",
            ]
            if remote.get("ssh_key"):
                args.extend(["-i", remote["ssh_key"]])
            args.extend([f"{remote['user']}@{remote['host']}", cmd])
        else:
            return False, "SSH remote not configured"

        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            return False, result.stderr or result.stdout
        return True, result.stdout
    except Exception as e:
        return False, str(e)


def _fetch_url(url: str, config: dict) -> tuple[bool, str]:
    timeout = _safe_timeout(config)
    remote = config.get("remote", {})
    if remote and (remote.get("ssh_alias") or remote.get("host")):
        curl_cmd = f"curl -4 -sL --max-time {timeout} {shlex.quote(url)}"
        return _ssh(remote, curl_cmd, timeout + 10)

    user_agent = config.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    proxies = config.get("proxies") or ({"http": config["proxy"], "https": config["proxy"]} if config.get("proxy") else None)

    try:
        resp = requests.get(url, headers={"User-Agent": user_agent}, proxies=proxies, timeout=timeout)
        resp.raise_for_status()
        return True, resp.text
    except Exception as e:
        return False, str(e)


def is_whitelisted_title(title: str, config: dict) -> bool:
    """Check if title contains registered JPN favorite artist, JPN studio, or JPN code pattern."""
    keywords = set(get_artist_folders(config, region="JPN"))
    for studio, aliases in get_studio_mappings(config, region="JPN").items():
        keywords.add(studio)
        keywords.update(aliases)

    norm_title = _normalize_name(title)
    for kw in keywords:
        if kw and _normalize_name(kw) in norm_title:
            return True

    if JPN_CODE_PATTERN.search(title):
        return True

    return False


def _parse_rss(rss_content: str) -> list[dict]:
    items = []
    try:
        root = ET.fromstring(rss_content)
    except Exception as e:
        logger.error(f"Failed to parse Sukebei RSS XML: {e}")
        return []

    for item in root.findall(".//item"):
        title_elem = item.find("title")
        link_elem = item.find("link")
        guid_elem = item.find("guid")
        info_hash_elem = item.find("nyaa:infoHash", NYAA_NS)
        seeders_elem = item.find("nyaa:seeders", NYAA_NS)
        leechers_elem = item.find("nyaa:leechers", NYAA_NS)
        size_elem = item.find("nyaa:size", NYAA_NS)

        title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
        link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
        if not link and guid_elem is not None and guid_elem.text:
            link = guid_elem.text.strip()

        info_hash = info_hash_elem.text.strip() if info_hash_elem is not None and info_hash_elem.text else ""
        seeders = seeders_elem.text.strip() if seeders_elem is not None and seeders_elem.text else "0"
        leechers = leechers_elem.text.strip() if leechers_elem is not None and leechers_elem.text else "0"
        size = size_elem.text.strip() if size_elem is not None and size_elem.text else ""

        match = re.search(r'/view/(\d+)', link)
        sukebei_id = match.group(1) if match else link.split("/")[-1]
        torrent_id = f"sukebei:{sukebei_id}"

        magnet_url = f"magnet:?xt=urn:btih:{info_hash}&dn={quote(title)}" if info_hash else ""

        items.append({
            "id": torrent_id,
            "title": title,
            "details_url": link,
            "magnet_url": magnet_url,
            "info_hash": info_hash,
            "size": size,
            "seeders": seeders,
            "leechers": leechers,
        })
    return items


def discover(config: dict) -> list[dict]:
    """Sukebei RSS에서 항목 수집 및 화이트리스트 필터링."""
    rss_url = config.get("rss_url", f"{BASE_URL}/?page=rss&c=2_2")
    ok, content = _fetch_url(rss_url, config)
    if not ok or not content:
        logger.error(f"Sukebei RSS fetch failed: {content[:200] if content else 'empty response'}")
        return []

    items = _parse_rss(content)
    filtered = [item for item in items if is_whitelisted_title(item["title"], config)]
    return filtered


def resolve(item: dict, config: dict) -> dict | None:
    """Transmission 전송용 magnet payload 반환."""
    magnet = item.get("magnet_url")
    if not magnet and item.get("info_hash"):
        magnet = f"magnet:?xt=urn:btih:{item['info_hash']}&dn={quote(item.get('title', ''))}"

    if not magnet and item.get("details_url"):
        magnet = resolve_magnet(item["details_url"], config)

    if magnet:
        return {"type": "magnet", "data": magnet}
    return None


def resolve_magnet(details_url: str, config: dict = None) -> str | None:
    """상세 페이지 URL에서 magnet link 추출."""
    if config is None:
        config = {}

    ok, html_text = _fetch_url(details_url, config)
    if not ok or not html_text:
        logger.error(f"Sukebei details fetch failed for {details_url}")
        return None

    match = re.search(r'href=["\'](magnet:\?xt=urn:btih:[^"\']+)["\']', html_text, re.IGNORECASE)
    if match:
        return html.unescape(match.group(1))
    return None
