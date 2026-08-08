"""
Meridian-X JAV Metadata Unified Resolver
FANZA API (1차) + OneJAV SSH Lookup (2차) 하이브리드 수집 및 캐싱 모듈
"""

import json
import logging
import os
from pathlib import Path

from .core import load_config
from .fanza import FanzaClient
from .jav_lookup import lookup_jav_actresses, lookup_web_jav_metadata

logger = logging.getLogger(__name__)

DEFAULT_CACHE_PATH = "logs/jav_metadata_cache.json"


def load_cache(cache_path: str = DEFAULT_CACHE_PATH) -> dict:
    path = Path(cache_path)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Cache load failed: {e}")
        return {}


def save_cache(cache_path: str, cache: dict) -> None:
    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.warning(f"Cache save failed: {e}")


def get_jav_metadata(
    code: str,
    config: dict | None = None,
    api_id: str | None = None,
    affiliate_id: str | None = None,
) -> dict:
    """
    품번(code)으로 FANZA 표준 데이터 수집.
    필드 단위 병합: FANZA API (1차) -> 비어있는 필드 JavBus/Jav321 (2차) -> 비어있는 필드 OneJAV (3차)
    """
    if config is None:
        try:
            config = load_config()
        except Exception:
            config = {}

    cache_path = config.get("jav_metadata_cache") or DEFAULT_CACHE_PATH
    cache = load_cache(cache_path)
    code_upper = code.upper()

    if code_upper in cache:
        logger.debug(f"[JAV Metadata Cache Hit] {code_upper}")
        return cache[code_upper]

    sources_used = []
    actresses = []
    makers = []
    genres = []
    title = None
    cover_url = None

    # 1. FANZA API 시도
    api_id = api_id or os.getenv("FANZA_API_ID")
    affiliate_id = affiliate_id or os.getenv("FANZA_AFFILIATE_ID")

    if api_id and affiliate_id and not code_upper.startswith("FC2"):
        try:
            client = FanzaClient(api_id, affiliate_id)
            fanza_data = client.fetch_metadata(code_upper)
            if fanza_data:
                actresses = fanza_data.get("actresses", [])
                makers = fanza_data.get("makers", [])
                genres = fanza_data.get("genres", [])
                title = fanza_data.get("title")
                cover_url = fanza_data.get("cover_url")
                if actresses or makers:
                    sources_used.append("fanza")
        except Exception as e:
            logger.warning(f"[FANZA API Error] {code_upper}: {e}")

    # 2. Web DB (JavBus/Jav321) SSH Lookup: 비어있는 항목 보완
    if not actresses or not makers or not title or not genres:
        try:
            web_data = lookup_web_jav_metadata(code_upper, config)
            if web_data:
                used = False
                if not actresses and web_data.get("actresses"):
                    actresses = web_data.get("actresses", [])
                    used = True
                if not makers and web_data.get("makers"):
                    makers = web_data.get("makers", [])
                    used = True
                if not title and web_data.get("title"):
                    title = web_data.get("title")
                    used = True
                if web_data.get("genres"):
                    for g in web_data.get("genres", []):
                        if g not in genres:
                            genres.append(g)
                            used = True
                if used:
                    sources_used.append("web_db")
        except Exception as e:
            logger.warning(f"[Web DB Lookup Error] {code_upper}: {e}")

    # 3. OneJAV SSH Lookup Fallback: 여전히 배우 정보가 없는 경우 보완
    if not actresses:
        try:
            onejav_actresses = lookup_jav_actresses(code_upper, config)
            if onejav_actresses:
                actresses = onejav_actresses
                sources_used.append("onejav")
        except Exception as e:
            logger.warning(f"[OneJAV Lookup Error] {code_upper}: {e}")

    source = "+".join(sources_used) if sources_used else "none"

    metadata = {
        "code": code_upper,
        "actresses": actresses,
        "makers": makers,
        "genres": genres,
        "title": title,
        "cover_url": cover_url,
        "source": source,
    }

    cache[code_upper] = metadata
    save_cache(cache_path, cache)
    return metadata

