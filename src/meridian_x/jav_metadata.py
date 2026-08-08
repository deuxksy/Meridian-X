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
    캐시 -> FANZA API -> Web DB (JavBus/Jav321) -> OneJAV Lookup 순서로 시도.
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

    # 1. FANZA API 시도
    api_id = api_id or os.getenv("FANZA_API_ID")
    affiliate_id = affiliate_id or os.getenv("FANZA_AFFILIATE_ID")

    actresses = []
    makers = []
    genres = []
    title = None
    cover_url = None
    source = "none"

    if api_id and affiliate_id and not code_upper.startswith("FC2"):
        try:
            client = FanzaClient(api_id, affiliate_id)
            fanza_data = client.fetch_metadata(code_upper)
            if fanza_data:
                actresses = fanza_data.get("actresses", [])
                makers = fanza_data.get("makers", [])
                genres = fanza_data.get("genres", [])
                source = "fanza"
        except Exception as e:
            logger.warning(f"[FANZA API Error] {code_upper}: {e}")

    # 2. Web DB (JavBus/Jav321) SSH Lookup (OneJAV보다 높은 우선순위)
    if not actresses and not makers:
        try:
            web_data = lookup_web_jav_metadata(code_upper, config)
            if web_data and (web_data.get("actresses") or web_data.get("makers")):
                actresses = web_data.get("actresses", [])
                makers = web_data.get("makers", [])
                genres = web_data.get("genres", [])
                title = web_data.get("title")
                source = "web_db"
        except Exception as e:
            logger.warning(f"[Web DB Lookup Error] {code_upper}: {e}")

    # 3. OneJAV SSH Lookup Fallback
    if not actresses and not makers:
        try:
            onejav_actresses = lookup_jav_actresses(code_upper, config)
            if onejav_actresses:
                actresses = onejav_actresses
                source = "onejav"
        except Exception as e:
            logger.warning(f"[OneJAV Lookup Error] {code_upper}: {e}")


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
