"""
Meridian-X Core Module
공통 함수 및 유틸리티
"""

import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Set

logger = logging.getLogger(__name__)


def load_config(config_path: str | Path | None = None) -> dict:
    """
    config/settings.json에서 설정을 로드합니다.
    일반 JSON 및 sops 바이너리 암호화 파일을 모두 지원합니다.
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "settings.json"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        logger.error(f"Config not found: {config_path}")
        raise FileNotFoundError(f"Config not found: {config_path}")

    raw_bytes = config_path.read_bytes()

    # 1. 일반 UTF-8 JSON 파싱 시도
    try:
        raw_text = raw_bytes.decode("utf-8")
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict) and "sops" in parsed:
            raise json.JSONDecodeError("SOPS encrypted JSON wrapper detected", raw_text, 0)
        return parsed
    except (UnicodeDecodeError, json.JSONDecodeError):
        # 2. 파싱 실패 또는 SOPS 암호화 wrapper인 경우 SOPS 바이너리 복호화 시도
        logger.info(f"Attempting sops binary decryption for {config_path}")
        sops_bin = shutil.which("sops")
        if not sops_bin:
            logger.error("sops command not found for encrypted config")
            raise RuntimeError("sops command is required to load encrypted config")

        env = os.environ.copy()
        if "SOPS_AGE_KEY_FILE" not in env:
            default_key = Path.home() / ".config" / "sops" / "age" / "keys.txt"
            if default_key.exists():
                env["SOPS_AGE_KEY_FILE"] = str(default_key)

        cmd = [
            sops_bin,
            "--decrypt",
            "--input-type",
            "binary",
            "--output-type",
            "binary",
            str(config_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, env=env)
        if proc.returncode != 0:
            err_msg = proc.stderr.decode("utf-8", errors="replace")
            logger.error(f"Failed to decrypt config with sops: {err_msg}")
            raise ValueError(f"Failed to decrypt config with sops: {err_msg}")

        try:
            return json.loads(proc.stdout.decode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to parse decrypted config JSON: {e}")
            raise ValueError(f"Decrypted config is not valid JSON: {e}")


def load_downloaded_history(history_file: str) -> Set[str]:
    """
    이미 다운로드한 토렌트 ID 목록을 로드합니다.
    prefix 없는 기존 항목은 onejav: prefix 자동 추가 (migration).
    """
    history_path = Path(history_file)
    if not history_path.exists():
        return set()

    with open(history_path, "r", encoding="utf-8") as f:
        result = set()
        for line in f:
            item = line.strip()
            if not item:
                continue
            # prefix 없는 기존 항목은 onejav: prefix 추가
            if ":" not in item:
                item = "onejav:" + item
            result.add(item)
        return result


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
