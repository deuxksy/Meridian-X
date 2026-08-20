"""
OneJAV Source
RSS 수집 → 페이지 방문 → .torrent 바이트
lt(Oracle Cloud KR datacenter) SSH 경유 (한국 residential ASN Cloudflare 차단 우회)
remote.ssh_alias("lt") 사용 → IPv4 강제(curl -4)
"""
import base64
import logging
import re
import shlex
import subprocess
from urllib.parse import urljoin, urlparse

from ..remote import fetch_remote_curl

logger = logging.getLogger(__name__)

ALLOWED_HOSTS = {"onejav.com", "www.onejav.com"}

# Backwards compatibility alias
fetch_url_remote = fetch_remote_curl


def _validate_url(url: str) -> bool:
    """URL scheme과 hostname 검증
    - hostname 사용: 소문자 정규화 + port/userinfo 제거가 보장
    - scheme.lower() 비교: 대소문자 구분 없음
    """
    try:
        parsed = urlparse(url)
        return bool(
            parsed.scheme and
            parsed.scheme.lower() in ("http", "https") and
            parsed.hostname and
            parsed.hostname in ALLOWED_HOSTS
        )
    except Exception:
        return False


def _safe_timeout(config: dict) -> int:
    """timeout 설정을 안전한 int로 변환
    - 실패 시 기본값 30 + WARNING
    - 음수/0 방지: max(1, timeout)
    """
    try:
        timeout = int(config.get("request_timeout", 30))
        return max(1, timeout)
    except (ValueError, TypeError):
        logger.warning("Invalid request_timeout, using default 30")
        return 30


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
    timeout = _safe_timeout(config)
    remote = _onejav_remote(config)

    if not remote.get("ssh_alias") and not remote.get("host"):
        logger.error("onejav remote not configured (ssh_alias or host/user/ssh_key)")
        return []

    if not _validate_url(rss_url):
        logger.error(f"Invalid RSS URL (allowlist check failed): {rss_url[:100]}")
        return []

    ssh_alias = remote.get("ssh_alias", "lt")
    output = fetch_remote_curl(rss_url, ssh_alias=ssh_alias, timeout=timeout)
    if not output:
        logger.error("OneJAV RSS fetch failed")
        return []

    return _parse_rss(output)


def resolve(item: dict, config: dict) -> dict | None:
    """페이지에서 .torrent 바이트를 가져와 metainfo payload 반환. lt SSH 경유 (curl -4 강제)."""
    page_url = item["page_url"]
    base_url = config.get("base_url", "https://onejav.com")
    timeout = _safe_timeout(config)
    remote = _onejav_remote(config)

    if not remote.get("ssh_alias") and not remote.get("host"):
        logger.error("onejav remote not configured (ssh_alias or host/user/ssh_key)")
        return None

    # 페이지 fetch
    if not _validate_url(page_url):
        logger.warning(f"URL validation failed, skipping: {page_url[:100]}")
        return None

    ssh_alias = remote.get("ssh_alias", "lt")
    html = fetch_remote_curl(page_url, ssh_alias=ssh_alias, timeout=timeout)
    if not html:
        logger.error(f"OneJAV page fetch failed for {page_url}")
        return None

    match = re.search(r'href="(/torrent/[^/]+/download/\d+/[^"]+\.torrent)"', html)
    if not match:
        logger.warning(f"No download link on {page_url}")
        return None

    download_url = urljoin(base_url, match.group(1))
    if not _validate_url(download_url):
        logger.warning(f"Download URL validation failed, skipping: {download_url[:100]}")
        return None
    # 바이너리는 base64 경유 (터미널 인코딩 이슈 방지)
    # download_url만 quote, base64는 쉘 빌트인이므로 quote 불필요
    curl_cmd = f"curl -4 -sL --max-time {timeout} --proto =http,https --proto-redir =http,https {shlex.quote(download_url)}"
    ok, b64 = _ssh(remote, f"{curl_cmd} | base64", timeout + 10)
    if not ok or not b64:
        logger.error(f"OneJAV torrent download failed: {b64[:200] if b64 else 'empty output'}")
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
