"""
TorrentGalaxy (TGx) Source for 서양 신사 실사 (WEST)
RSS 수집 및 미러 폴백 → magnet link 추출
"""
import html
import logging
import re
import shlex
import subprocess
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from meridian_x.classify import (
    _normalize_name,
    get_artist_folders,
    get_studio_mappings,
)
from meridian_x.core import is_fhd_or_higher
from ..remote import fetch_remote_curl

logger = logging.getLogger(__name__)

# Backwards compatibility alias
fetch_url_remote = fetch_remote_curl

DEFAULT_BASE_URL = "https://torrentgalaxy.one"
DEFAULT_MIRRORS = [
    "https://torrentgalaxy.one",
    "https://torrentgalaxy.hair",
    "https://torrentgalaxy.to",
    "https://tgx.rs",
    "https://torrentgalaxy.mx",
]
DEFAULT_CATEGORY = "42"


def _tgx_remote(config: dict) -> dict:
    """torrentgalaxy 전용 remote. sources.torrentgalaxy.remote / sources.tgx.remote 우선, 없으면 최상위 remote fallback."""
    return (
        config.get("sources", {}).get("torrentgalaxy", {}).get("remote")
        or config.get("sources", {}).get("tgx", {}).get("remote")
        or config.get("remote", {})
    )


def _safe_timeout(config: dict) -> int:
    """timeout 설정을 안전한 int로 변환 (기본값 30)."""
    try:
        val = (
            config.get("sources", {}).get("torrentgalaxy", {}).get("request_timeout")
            or config.get("sources", {}).get("tgx", {}).get("request_timeout")
            or config.get("request_timeout")
            or 30
        )
        return max(1, int(val))
    except (ValueError, TypeError):
        return 30


def _ssh(remote: dict, cmd: str, timeout: int = 60) -> tuple[bool, str]:
    """SSH 명령 실행 (ssh_alias 또는 explicit host/user/ssh_key)."""
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


def _fetch_url(url: str, config: dict, candidate_urls: list[str] = None) -> tuple[bool, str]:
    """URL 요청 수행. remote SSH curl 우선 사용 및 mirror 순회 지원."""
    timeout = _safe_timeout(config)
    remote = _tgx_remote(config)

    urls = [url]
    if candidate_urls:
        for u in candidate_urls:
            if u not in urls:
                urls.append(u)

    user_agent = config.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    proxies = config.get("proxies") or ({"http": config["proxy"], "https": config["proxy"]} if config.get("proxy") else None)

    for target_url in urls:
        if remote and (remote.get("ssh_alias") or remote.get("host")):
            ssh_alias = remote.get("ssh_alias", "lt")
            out = fetch_remote_curl(target_url, ssh_alias=ssh_alias, timeout=timeout)
            if out and out.strip():
                return True, out
            logger.warning(f"TorrentGalaxy fetch failed on {target_url[:60]} via remote")
        else:
            try:
                resp = requests.get(target_url, headers={"User-Agent": user_agent}, proxies=proxies, timeout=timeout)
                if resp.status_code == 200 and resp.text.strip():
                    return True, resp.text
            except Exception as e:
                logger.warning(f"TorrentGalaxy direct fetch failed on {target_url[:60]}: {e}")

    return False, "All candidate mirrors failed"


def is_whitelisted_title(title: str, config: dict) -> bool:
    """Check if title matches WEST artist, WEST studio, or genre keyword AND is FHD+."""
    if not is_fhd_or_higher(title):
        return False

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


def _parse_rss(rss_content: str) -> list[dict]:
    """TorrentGalaxy RSS XML 파싱하여 title, page_url, magnet_url 추출."""
    items = []
    try:
        root = ET.fromstring(rss_content)
    except Exception as e:
        logger.error(f"Failed to parse TorrentGalaxy RSS XML: {e}")
        return []

    channel = root.find("channel")
    item_nodes = channel.findall("item") if channel is not None else root.findall(".//item")

    for item_elem in item_nodes:
        title_elem = item_elem.find("title")
        link_elem = item_elem.find("link")
        enclosure = item_elem.find("enclosure")
        if title_elem is None or link_elem is None:
            continue

        title = (title_elem.text or "").strip()
        link = (link_elem.text or "").strip()
        magnet_url = enclosure.attrib.get("url", "") if enclosure is not None else ""

        match = re.search(r'/torrent/(\d+)', link)
        tgx_id = match.group(1) if match else link.split("/")[-1]
        torrent_id = f"tgx:{tgx_id}"

        items.append({
            "id": torrent_id,
            "title": title,
            "page_url": link,
            "magnet_url": html.unescape(magnet_url).strip(),
        })
    return items


def discover(config: dict) -> list[dict]:
    """TorrentGalaxy RSS에서 항목 수집 및 화이트리스트 필터링."""
    rss_url = (
        config.get("sources", {}).get("torrentgalaxy", {}).get("rss_url")
        or config.get("sources", {}).get("tgx", {}).get("rss_url")
        or config.get("rss_url")
        or f"{DEFAULT_BASE_URL}/rss?cat={DEFAULT_CATEGORY}"
    )
    mirrors = (
        config.get("sources", {}).get("torrentgalaxy", {}).get("mirrors")
        or config.get("sources", {}).get("tgx", {}).get("mirrors")
        or config.get("mirrors")
        or DEFAULT_MIRRORS
    )
    candidate_rss = [rss_url] + [f"{m.rstrip('/')}/rss?cat={DEFAULT_CATEGORY}" for m in mirrors]

    ok, content = _fetch_url(rss_url, config, candidate_urls=candidate_rss)
    if not ok or not content:
        logger.error(f"TorrentGalaxy RSS discover failed: {content}")
        return []

    parsed = _parse_rss(content)
    if config.get("selective_only", True):
        return [item for item in parsed if is_whitelisted_title(item["title"], config)]
    return parsed


def _parse_search_html(html_content: str, base_url: str, allow_all_quality: bool = False) -> list[dict]:
    """TorrentGalaxy 검색 결과 HTML 파싱."""
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, "html.parser")
    items = []

    rows = soup.select("div.tgxtablerow")
    if not rows:
        rows = soup.select("table.tgxtable tr, table tr")

    for row in rows:
        link_elem = row.select_one("a[href*='/post-detail/'], a[href*='/torrent/'], a.txlight")
        if not link_elem:
            continue

        href = link_elem.get("href", "").strip()
        if not href or href.startswith("#"):
            continue

        title = link_elem.get("title", "").strip() or link_elem.get_text(strip=True)
        if not title:
            continue

        details_url = urljoin(base_url, href)

        match = re.search(r'/(?:torrent|post-detail)/([a-zA-Z0-9_-]+)', href)
        tgx_id = match.group(1) if match else href.rstrip("/").split("/")[-1]
        torrent_id = f"tgx:{tgx_id}"

        magnet_elem = row.select_one('a[href^="magnet:"]')
        magnet_url = html.unescape(magnet_elem.get("href", "").strip()) if magnet_elem else ""

        size_elem = row.select_one("span.badge, .badge")
        size = size_elem.get_text(strip=True) if size_elem else ""

        seed_elem = row.select_one('span[style*="green"], font[color*="green"], span.seeders, td.seeders')
        leech_elem = row.select_one('span[style*="red"], font[color*="red"], span.leechers, td.leechers')

        seeders = re.sub(r'[^\d]', '', seed_elem.get_text(strip=True)) if seed_elem else "0"
        leechers = re.sub(r'[^\d]', '', leech_elem.get_text(strip=True)) if leech_elem else "0"

        if not size:
            cells = row.find_all("td") or row.find_all(class_="tgxtablecell")
            for c in cells:
                txt = c.get_text(strip=True)
                if re.search(r'\b\d+(?:\.\d+)?\s*(?:[KMGTP]?B|Bytes)\b', txt, re.IGNORECASE):
                    size = txt
                    break

        items.append({
            "id": torrent_id,
            "title": title,
            "details_url": details_url,
            "magnet_url": magnet_url,
            "size": size,
            "seeders": seeders,
            "leechers": leechers,
        })

    if not allow_all_quality:
        items = [item for item in items if is_fhd_or_higher(item["title"])]

    return items


def _format_size(size_bytes: int) -> str:
    if size_bytes >= 1024**4:
        return f"{size_bytes / (1024**4):.2f} TB"
    if size_bytes >= 1024**3:
        return f"{size_bytes / (1024**3):.2f} GB"
    if size_bytes >= 1024**2:
        return f"{size_bytes / (1024**2):.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def _parse_json_results(json_data: list, base_url: str, allow_all_quality: bool = False) -> list[dict]:
    items = []
    for entry in json_data:
        pk = str(entry.get("pk") or "").strip()
        name = str(entry.get("n") or "").strip()
        if not pk or not name:
            continue

        info_hash = str(entry.get("h") or "").strip()
        encoded_name = quote_plus(name)
        magnet_url = f"magnet:?xt=urn:btih:{info_hash}&dn={encoded_name}" if info_hash else ""

        size_bytes = entry.get("s") or 0
        size_str = _format_size(size_bytes) if size_bytes else ""

        seeders = str(entry.get("se") or "0")
        leechers = str(entry.get("le") or "0")

        slug = re.sub(r'[^a-zA-Z0-9_-]+', '-', name).strip('-').lower()
        details_url = f"{base_url.rstrip('/')}/post-detail/{pk}/{slug}/"

        items.append({
            "id": f"tgx:{pk}",
            "title": name,
            "details_url": details_url,
            "magnet_url": magnet_url,
            "size": size_str,
            "seeders": seeders,
            "leechers": leechers,
        })

    if not allow_all_quality:
        items = [item for item in items if is_fhd_or_higher(item["title"])]
    return items


def search(query: str, category: str = DEFAULT_CATEGORY, config: dict = None) -> list[dict]:
    """TorrentGalaxy 키워드 및 카테고리 검색 결과 반환 (JSON API 우선, HTML fallback)."""
    import json

    if config is None:
        config = {}

    base_url = (
        config.get("sources", {}).get("torrentgalaxy", {}).get("base_url")
        or config.get("sources", {}).get("tgx", {}).get("base_url")
        or config.get("base_url")
        or DEFAULT_BASE_URL
    )
    mirrors = (
        config.get("sources", {}).get("torrentgalaxy", {}).get("mirrors")
        or config.get("sources", {}).get("tgx", {}).get("mirrors")
        or config.get("mirrors")
        or DEFAULT_MIRRORS
    )

    allow_all_quality = config.get("allow_all_quality", False)
    encoded_query = quote_plus(query)

    # 1. JSON API 검색 시도
    json_path = f"/get-posts/keywords:{encoded_query}:format:json/"
    json_url = f"{base_url.rstrip('/')}{json_path}"
    candidate_json = [json_url] + [f"{m.rstrip('/')}{json_path}" for m in mirrors]

    ok, content = _fetch_url(json_url, config, candidate_urls=candidate_json)
    if ok and content and (content.strip().startswith("[") or content.strip().startswith("{")):
        try:
            data = json.loads(content)
            results = data if isinstance(data, list) else data.get("results", [])
            if results:
                return _parse_json_results(results, base_url, allow_all_quality=allow_all_quality)
        except Exception as e:
            logger.debug(f"TGx JSON parse fallback to HTML: {e}")

    # 2. HTML 검색 fallback
    cat = category if category is not None else DEFAULT_CATEGORY
    search_path = f"/torrents.php?search={encoded_query}&cat={cat}&sort=seeders&order=desc"
    search_url = f"{base_url.rstrip('/')}{search_path}"
    candidate_urls = [search_url] + [f"{m.rstrip('/')}{search_path}" for m in mirrors]

    ok, content = _fetch_url(search_url, config, candidate_urls=candidate_urls)
    if not ok or not content:
        logger.error(f"TorrentGalaxy search fetch failed for '{query}': {content[:200] if content else 'empty'}")
        return []

    return _parse_search_html(content, base_url, allow_all_quality=allow_all_quality)


def resolve_magnet(item_or_details_url: dict | str, config: dict = None) -> str | None:
    """TorrentGalaxy 항목 또는 상세 페이지 URL에서 magnet link 추출."""
    if config is None:
        config = {}

    if isinstance(item_or_details_url, dict):
        magnet = item_or_details_url.get("magnet_url")
        if magnet and magnet.startswith("magnet:"):
            return magnet
        details_url = item_or_details_url.get("details_url") or item_or_details_url.get("page_url")
    elif isinstance(item_or_details_url, str):
        if item_or_details_url.startswith("magnet:"):
            return item_or_details_url
        details_url = item_or_details_url
    else:
        return None

    if not details_url:
        return None

    mirrors = (
        config.get("sources", {}).get("torrentgalaxy", {}).get("mirrors")
        or config.get("sources", {}).get("tgx", {}).get("mirrors")
        or config.get("mirrors")
        or DEFAULT_MIRRORS
    )

    candidate_urls = [details_url]
    parsed_u = urlparse(details_url)
    if parsed_u.path:
        for m in mirrors:
            m_cand = f"{m.rstrip('/')}{parsed_u.path}"
            if parsed_u.query:
                m_cand += f"?{parsed_u.query}"
            if m_cand not in candidate_urls:
                candidate_urls.append(m_cand)

    ok, html_text = _fetch_url(details_url, config, candidate_urls=candidate_urls)
    if not ok or not html_text:
        logger.error(f"TorrentGalaxy details fetch failed for {details_url}")
        return None

    match = re.search(r'href=["\'](magnet:\?xt=urn:btih:[^"\']+)["\']', html_text, re.IGNORECASE)
    if not match:
        match = re.search(r'(magnet:\?xt=urn:btih:[^"\'<>\s]+)', html_text, re.IGNORECASE)
    if match:
        return html.unescape(match.group(1)).strip()
    return None


def resolve(item: dict, config: dict) -> dict | None:
    """Transmission 전송용 magnet payload 반환."""
    magnet = item.get("magnet_url")
    if not magnet:
        magnet = resolve_magnet(item, config)
    if magnet:
        return {"type": "magnet", "data": magnet, "magnet_url": magnet, "metainfo": None}
    return None
