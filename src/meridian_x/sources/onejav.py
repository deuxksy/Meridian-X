"""
OneJAV Source
RSS 수집 → 페이지 방문 → .torrent 바이트
onejav.com은 사이트 전체에 Cloudflare JS challenge가 걸려 있어 FlareSolverr(brla)로 통과한다.
- RSS/페이지: FlareSolverr(gluetun egress) 경유
- .torrent: FlareSolverr가 발급한 cf_clearance + User-Agent로 gluetun 프록시 직접 다운로드
"""
import html
import logging
import re
from urllib.parse import urljoin, urlparse

from ..remote import download_via_proxy, fetch_via_flaresolverr

logger = logging.getLogger(__name__)

ALLOWED_HOSTS = {"onejav.com", "www.onejav.com"}

DOWNLOAD_HREF_RE = re.compile(r'href="(/torrent/[^/]+/download/\d+/[^"]+\.torrent)"')


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


def _to_https(url: str) -> str:
    """RSS link는 http:// 형식이므로 https로 승격 (KR http DPI 회피)."""
    return "https://" + url[len("http://"):] if url.startswith("http://") else url


def discover(config: dict) -> list[dict]:
    """OneJAV RSS에서 수집 항목 반환 (FlareSolverr 경유)."""
    rss_url = config.get("rss_url", "https://onejav.com/feeds/")
    if not _validate_url(rss_url):
        logger.error(f"Invalid RSS URL (allowlist check failed): {rss_url[:100]}")
        return []

    fs = fetch_via_flaresolverr(rss_url, config, timeout=_safe_timeout(config))
    if not fs:
        logger.error("OneJAV RSS fetch failed")
        return []
    # Chromium XML viewer가 RSS를 HTML-escape된 <pre>로 감싸 반환하므로 복원
    return _parse_rss(html.unescape(fs["html"]))


def resolve(item: dict, config: dict) -> dict | None:
    """페이지에서 .torrent 바이트를 가져와 metainfo payload 반환."""
    page_url = item["page_url"]
    base_url = config.get("base_url", "https://onejav.com")
    timeout = _safe_timeout(config)

    if not _validate_url(page_url):
        logger.warning(f"URL validation failed, skipping: {page_url[:100]}")
        return None

    fs = fetch_via_flaresolverr(_to_https(page_url), config, timeout=timeout)
    if not fs:
        logger.error(f"OneJAV page fetch failed for {page_url}")
        return None

    match = DOWNLOAD_HREF_RE.search(fs["html"])
    if not match:
        logger.warning(f"No download link on {page_url}")
        return None

    download_url = urljoin(base_url, match.group(1))
    if not _validate_url(download_url):
        logger.warning(f"Download URL validation failed, skipping: {download_url[:100]}")
        return None

    data = download_via_proxy(
        download_url, config, timeout=timeout + 10,
        cookies=fs["cookies"], user_agent=fs["user_agent"],
    )
    if not data:
        logger.error(f"OneJAV torrent download failed for {page_url}")
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
