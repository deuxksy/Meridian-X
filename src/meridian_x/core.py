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

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def load_config(config_path: str | Path | None = None) -> dict:
    """
    config/settings.json에서 설정을 로드합니다.
    일반 JSON 및 sops 바이너리 암호화 파일을 모두 지원합니다.
    """
    load_dotenv()
    if config_path is None:

        base_config_dir = Path(__file__).parent.parent.parent / "config"
        if (base_config_dir / "settings.json").exists():
            config_path = base_config_dir / "settings.json"
        elif (base_config_dir / "settings.json.sops").exists():
            config_path = base_config_dir / "settings.json.sops"
        else:
            config_path = base_config_dir / "settings.json"
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


def load_downloaded_history(history_file: str = "downloaded_history.txt") -> Set[str]:
    """
    이미 다운로드한 토렌트 ID 목록을 로드합니다.
    (MeridianDB 백엔드를 사용하며 legacy txt 파일이 존재하면 자동으로 마이그레이션합니다)
    """
    from .db import MeridianDB

    db = MeridianDB()
    if Path(history_file).exists():
        db.migrate_history_txt(history_file)
    return db.get_download_history()


def save_downloaded_history(history_file: str, downloaded: Set[str]) -> None:
    """
    다운로드한 토렌트 ID 목록을 저장합니다. (MeridianDB에 추가)
    """
    from .db import MeridianDB

    db = MeridianDB()
    db.add_download_history(downloaded)



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


FHD_4K_PATTERN = re.compile(
    r"(\[FHD\]|\[4K\]|\[4K/2160p\]|\b(fhd|1080p|1080i|fullhd|full-hd|4k|2160p|uhd|bluray|blu-ray|bdrip|bd-rip)\b)",
    re.IGNORECASE,
)
EXCLUDE_QUALITY_PATTERN = re.compile(
    r"(\[HD/720p\]|\[720p\]|\[HD\]|\[SD\]|\[8K\]|\[8KVR\]|\[8K\s+HEVC\]|\b(8k|8kvr|vr|3dsvr|3dvr|720p|480p|360p|540p|576p|dvdrip|dvd-rip|dvdiso|dvd)\b)",
    re.IGNORECASE,
)


def is_fhd_or_higher(title: str) -> bool:
    """제목에서 화질을 판별하여 FHD(1080p) 및 4K(2160p) 규격인지 검사 (VR/8K 및 720p/SD 제외).
    - 8K/VR 및 720p/SD/DVD 키워드가 포함되어 있으면 False
    - FHD/4K 키워드가 포함되어 있으면 True
    - 화질 태그가 없으면 기본 True
    """
    if not title:
        return True
    if EXCLUDE_QUALITY_PATTERN.search(title):
        return False
    if FHD_4K_PATTERN.search(title):
        return True
    return True


def extract_scene_key(title: str) -> str:
    """토렌트/게시글 제목에서 동일 에피소드 식별 키 추출 (릴 그룹 및 화질 태그 제거)."""
    clean = title.replace(".", " ").replace("_", " ").replace("-", " ")
    clean = re.sub(r"\[.*?\]", " ", clean)
    clean = re.sub(r"\(.*?\)", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip().lower()

    # West 날짜 패턴 (YY MM DD, YYYY MM DD)
    date_m = re.search(r"\b(\d{2,4})\s+(\d{2})\s+(\d{2})\b", clean)
    if date_m:
        date_str = "".join(date_m.groups())
        prefix = clean[:date_m.start()].strip().split()
        suffix = clean[date_m.end():].strip().split()
        noise = {"1080p", "2160p", "4k", "720p", "mp4", "mkv", "xxx", "wrb", "trb", "xc", "p2p", "xvid", "av1", "xfans", "h264", "h265", "hevc"}
        words = [w for w in (prefix + suffix) if w not in noise]
        w0 = words[0] if words else ""
        w1 = words[1] if len(words) > 1 else ""
        w2 = words[2] if len(words) > 2 else ""
        return f"west_{w0}_{date_str}_{w1}_{w2}"

    # JAV 메이커 코드 패턴 (예: SONE-446, IPX-123)
    jav_m = re.search(r"\b([a-z]{3,7})\s+(\d{2,5})\b", clean)
    if jav_m:
        return f"jav_{jav_m.group(1)}_{jav_m.group(2)}"

    # 기타 일반 제목
    words = [w for w in clean.split() if w not in {"1080p", "2160p", "4k", "720p", "mp4", "mkv", "xxx", "wrb", "trb", "xc", "p2p", "xvid", "av1", "xfans"}]
    return "other_" + "_".join(words[:4])


def score_release(item: dict) -> int:
    """릴리스 우선순위 점수 계산: 1080p 우선 > 안정적 릴 그룹(WRB/XC > TRB > P2P) > 시더 수."""
    title = (item.get("title") or "").lower()
    score = 0

    # 1. 1080p (FHD) 최우선
    if "1080p" in title or "1080i" in title or "fhd" in title:
        score += 1000
    elif "2160p" in title or "4k" in title or "uhd" in title:
        score += 500
    else:
        score += 100

    # 2. 안정적인 릴 그룹 (WRB / XC / XXXClub > TRB / theRarBg > P2P > 기타)
    if "wrb" in title or "xc" in title or "xxxclub" in title:
        score += 300
    elif "trb" in title or "therarbg" in title:
        score += 200
    elif "p2p" in title or "nbq" in title:
        score += 100

    # 3. 시더 수 가산점 (최대 50점)
    try:
        seeders = int(re.sub(r"[^\d]", "", str(item.get("seeders") or "0")))
        score += min(seeders, 50)
    except Exception:
        pass

    return score


def deduplicate_releases(items: list[dict]) -> list[dict]:
    """동일 에피소드/작품 중 가장 우선순위가 높은(1080p, 안정적 릴 그룹) 릴리스만 단일 선별."""
    from collections import defaultdict
    grouped = defaultdict(list)
    for item in items:
        key = extract_scene_key(item.get("title", ""))
        grouped[key].append(item)

    best_items = []
    for key, group in grouped.items():
        sorted_group = sorted(group, key=score_release, reverse=True)
        best_items.append(sorted_group[0])

    orig_indices = {id(item): idx for idx, item in enumerate(items)}
    best_items.sort(key=lambda item: orig_indices.get(id(item), 0))
    return best_items

