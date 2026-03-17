"""
Meridian-X Collect Module
OneJAV RSS 수집 및 자동 다운로드
"""

import json
import logging
import re
from pathlib import Path
from typing import List, Set
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

# ==========================================
# LOAD CONFIGURATION
# ==========================================

def _load_config() -> dict:
    """
    config/settings.json에서 설정을 로드합니다.
    """
    config_path = Path(__file__).parent.parent.parent / "config" / "settings.json"
    
    if not config_path.exists():
        logger.error(f"Config not found: {config_path}")
        raise FileNotFoundError(f"Config not found: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


# Load config
CONFIG = _load_config()
ONEJAV = CONFIG.get("onejav", {})
DOWNLOAD = CONFIG.get("download", {})

# OneJAV settings
ONEJAV_BASE_URL = ONEJAV.get("base_url", "https://onejav.com")
ONEJAV_RSS_URL = ONEJAV.get("rss_url", "https://onejav.com/feeds/")

# Download settings
WATCH_PATH = DOWNLOAD.get("watch_path", "/mnt/data1/torrent/downloads/watch")
DOWNLOADED_HISTORY_FILE = DOWNLOAD.get("history_file", "logs/downloads.txt")
REQUEST_TIMEOUT = DOWNLOAD.get("request_timeout", 30)
USER_AGENT = DOWNLOAD.get(
    "user_agent",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
)


# ==========================================
# FUNCTIONS
# ==========================================


def _load_downloaded_history() -> Set[str]:
    """
    이미 다운로드한 토렌트 ID 목록을 로드합니다.
    """
    history_path = Path(DOWNLOADED_HISTORY_FILE)
    if not history_path.exists():
        return set()
    
    with open(history_path, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def _save_downloaded_history(downloaded: Set[str]) -> None:
    """
    다운로드한 토렌트 ID 목록을 저장합니다.
    """
    history_path = Path(DOWNLOADED_HISTORY_FILE)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(history_path, "w", encoding="utf-8") as f:
        for torrent_id in sorted(downloaded):
            f.write(f"{torrent_id}\n")


def _extract_page_links(rss_content: str) -> List[dict]:
    """
    RSS 피드에서 페이지 링크를 추출합니다.
    """
    links = []
    
    # RSS에서 <item> 태그 찾기
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
        
        # 토렌트 ID 추출 (예: 200GANA3353)
        torrent_id = link.split("/")[-1].upper()
        
        links.append({
            "id": torrent_id,
            "title": title,
            "page_url": link,
            "description": description
        })
    
    return links


def _get_download_url(page_url: str) -> str | None:
    """
    페이지에서 실제 다운로드 URL을 추출합니다.
    """
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(page_url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        # 다운로드 링크 패턴: /torrent/{ID}/download/{NUMBER}/onejav.com_{ID}.torrent
        match = re.search(r'href="(/torrent/[^/]+/download/\d+/[^"]+\.torrent)"', response.text)
        if match:
            return urljoin(ONEJAV_BASE_URL, match.group(1))
        
        logger.warning(f"No download link found on {page_url}")
        return None
    except Exception as e:
        logger.error(f"Failed to fetch page {page_url}: {e}")
        return None


def _download_torrent(link: str, save_path: Path, dry_run: bool = False) -> bool:
    """
    토렌트 파일을 다운로드합니다.
    """
    if dry_run:
        logger.info(f"  [Dry-run] Would download: {link}")
        return True
    
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(link, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        with open(save_path, "wb") as f:
            f.write(response.content)
        
        logger.info(f"  [Downloaded] {save_path.name}")
        return True
    except Exception as e:
        logger.error(f"  [Error Downloading] {link}: {e}")
        return False


def run(max_count: int = 30, favorite_url: str = None, dry_run: bool = False) -> None:
    """
    OneJAV RSS 피드를 수집하고 토렌트를 다운로드합니다.
    
    Args:
        max_count: 최대 다운로드 수 (기본 30개)
        favorite_url: 즐겨찾기 배우 URL (옵션)
        dry_run: 실제 다운로드 하지 않음
    """
    logger.info("=== Meridian-X Collect Started ===")
    logger.info(f"Dry-run: {dry_run}")
    logger.info(f"RSS URL: {ONEJAV_RSS_URL}")
    logger.info(f"Watch Path: {WATCH_PATH}")
    
    # 1. RSS 피드 가져오기
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(ONEJAV_RSS_URL, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        rss_content = response.text
        logger.info(f"Fetched RSS feed ({len(rss_content)} bytes)")
    except Exception as e:
        logger.error(f"Failed to fetch RSS: {e}")
        return
    
    # 2. 페이지 링크 추출
    page_links = _extract_page_links(rss_content)
    logger.info(f"Found {len(page_links)} page links")
    
    if not page_links:
        logger.warning("No page links found")
        return
    
    # 3. 이미 다운로드한 것 제외
    downloaded_history = _load_downloaded_history()
    new_links = [t for t in page_links if t["id"] not in downloaded_history]
    logger.info(f"New torrents: {len(new_links)} (History: {len(downloaded_history)})")
    
    if not new_links:
        logger.info("No new torrents to download")
        return
    
    # 4. 최대 개수 제한
    links_to_download = new_links[:max_count]
    logger.info(f"Will process {len(links_to_download)} torrents")
    
    # 5. 다운로드
    watch_path = Path(WATCH_PATH)
    watch_path.mkdir(parents=True, exist_ok=True)
    
    downloaded_count = 0
    for torrent in links_to_download:
        torrent_id = torrent["id"]
        page_url = torrent["page_url"]
        
        # 로컬 파일명 생성
        filename = f"{torrent_id}.torrent"
        save_path = watch_path / filename
        
        if save_path.exists():
            logger.info(f"  [Skipped] {filename} (Already exists)")
            downloaded_history.add(torrent_id)
            continue
        
        # 페이지에서 다운로드 URL 가져오기
        if dry_run:
            logger.info(f"  [Dry-run] Would process: {torrent_id} from {page_url}")
            downloaded_history.add(torrent_id)
            downloaded_count += 1
            continue
        
        download_url = _get_download_url(page_url)
        if not download_url:
            logger.warning(f"  [Skip] {torrent_id} - No download URL")
            continue
        
        if _download_torrent(download_url, save_path, dry_run=False):
            downloaded_history.add(torrent_id)
            downloaded_count += 1
    
    # 6. 히스토리 저장
    _save_downloaded_history(downloaded_history)
    
    logger.info(f"=== Meridian-X Collect Completed ({downloaded_count} downloaded) ===")
