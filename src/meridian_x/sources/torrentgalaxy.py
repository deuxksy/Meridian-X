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

import requests

from meridian_x.classify import (
    _normalize_name,
    get_artist_folders,
    get_studio_mappings,
)
from meridian_x.core import is_fhd_or_higher

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://torrentgalaxy.to"
DEFAULT_MIRRORS = ["https://tgx.rs", "https://torrentgalaxy.mx", "https://torrentgalaxy.one"]
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
            curl_cmd = f"curl -4 -sL --max-time {timeout} {shlex.quote(target_url)}"
            ok, out = _ssh(remote, curl_cmd, timeout + 10)
            if ok and out.strip():
                return True, out
            logger.warning(f"TorrentGalaxy fetch failed on {target_url[:60]} via remote: {out[:100]}")
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


def resolve(item: dict, config: dict) -> dict | None:
    """Transmission 전송용 magnet payload 반환."""
    magnet = item.get("magnet_url")
    if magnet:
        return {"type": "magnet", "data": magnet, "magnet_url": magnet, "metainfo": None}
    return None
