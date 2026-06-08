"""
Meridian-X Core Module
공통 함수 및 유틸리티
"""

import json
import logging
import re
from pathlib import Path
from typing import List, Set

logger = logging.getLogger(__name__)


def load_config() -> dict:
    """
    config/settings.json에서 설정을 로드합니다.
    """
    config_path = Path(__file__).parent.parent.parent / "config" / "settings.json"

    if not config_path.exists():
        logger.error(f"Config not found: {config_path}")
        raise FileNotFoundError(f"Config not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_downloaded_history(history_file: str) -> Set[str]:
    """
    이미 다운로드한 토렌트 ID 목록을 로드합니다.
    """
    history_path = Path(history_file)
    if not history_path.exists():
        return set()

    with open(history_path, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_downloaded_history(history_file: str, downloaded: Set[str]) -> None:
    """
    다운로드한 토렌트 ID 목록을 저장합니다.
    """
    history_path = Path(history_file)
    history_path.parent.mkdir(parents=True, exist_ok=True)

    with open(history_path, "w", encoding="utf-8") as f:
        for torrent_id in sorted(downloaded):
            f.write(f"{torrent_id}\n")


def extract_page_links(rss_content: str) -> List[dict]:
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
