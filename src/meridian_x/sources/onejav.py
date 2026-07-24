"""
OneJAV Source
RSS 수집 → 페이지 방문 → .torrent 바이트
lt(Oracle Cloud KR datacenter) SSH 경유 (한국 residential ASN Cloudflare 차단 우회)
remote.ssh_alias("lt") 사용 → IPv4 강제(curl -4)
"""
import base64
import logging
import re
import subprocess
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


def _ssh(remote: dict, cmd: str, timeout: int = 60) -> tuple[bool, str]:
    """SSH 명령 실행.
    remote.ssh_alias 있으면 ssh config alias(lt) 사용, 없으면 explicit(user@host + ssh_key).
    """
    try:
        if remote.get("ssh_alias"):
            args = [
                "ssh",
                "-o", "ConnectTimeout=5",
                "-o", "StrictHostKeyChecking=no",
                remote["ssh_alias"],
                cmd,
            ]
        else:
            args = [
                "ssh", "-i", remote["ssh_key"],
                "-o", "ConnectTimeout=5",
                "-o", "StrictHostKeyChecking=no",
                f'{remote["user"]}@{remote["host"]}',
                cmd,
            ]
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def _onejav_remote(config: dict) -> dict:
    """onejav 전용 remote. sources.onejav.remote 우선, 없으면 최상위 remote fallback."""
    return (
        config.get("sources", {}).get("onejav", {}).get("remote")
        or config.get("remote", {})
    )


def discover(config: dict) -> list[dict]:
    """OneJAV RSS에서 수집 항목 반환. lt SSH 경유 (curl -4 강제)."""
    rss_url = config.get("rss_url", "https://onejav.com/feeds/")
    timeout = config.get("request_timeout", 30)
    remote = _onejav_remote(config)

    if not remote.get("ssh_alias") and not remote.get("host"):
        logger.error("onejav remote not configured (ssh_alias or host/user/ssh_key)")
        return []

    ok, output = _ssh(remote, f'curl -4 -sL --max-time {timeout} "{rss_url}"', timeout + 10)
    if not ok or not output:
        logger.error(f"OneJAV RSS fetch failed: {output[:200]}")
        return []

    return _parse_rss(output)


def resolve(item: dict, config: dict) -> dict | None:
    """페이지에서 .torrent 바이트를 가져와 metainfo payload 반환. lt SSH 경유 (curl -4 강제)."""
    page_url = item["page_url"]
    base_url = config.get("base_url", "https://onejav.com")
    timeout = config.get("request_timeout", 30)
    remote = _onejav_remote(config)

    if not remote.get("ssh_alias") and not remote.get("host"):
        logger.error("onejav remote not configured (ssh_alias or host/user/ssh_key)")
        return None

    # 페이지 fetch
    ok, html = _ssh(remote, f'curl -4 -sL --max-time {timeout} "{page_url}"', timeout + 10)
    if not ok or not html:
        logger.error(f"OneJAV page fetch failed for {page_url}: {html[:200]}")
        return None

    match = re.search(r'href="(/torrent/[^/]+/download/\d+/[^"]+\.torrent)"', html)
    if not match:
        logger.warning(f"No download link on {page_url}")
        return None

    download_url = urljoin(base_url, match.group(1))
    # 바이너리는 base64 경유 (터미널 인코딩 이슈 방지)
    ok, b64 = _ssh(remote, f'curl -4 -sL --max-time {timeout} "{download_url}" | base64', timeout + 10)
    if not ok or not b64:
        logger.error(f"OneJAV torrent download failed: {b64[:200]}")
        return None

    try:
        data = base64.b64decode(b64)
    except Exception as e:
        logger.error(f"base64 decode failed: {e}")
        return None

    return {"type": "metainfo", "data": data}


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
