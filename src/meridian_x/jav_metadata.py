"""
Meridian-X JAV Metadata Unified Resolver
Jav321/JavBus Web DB (1차) + OneJAV Lookup (2차) 하이브리드 수집 및 캐싱 모듈
"""

import json
import logging
from pathlib import Path

from .core import load_config
from .jav_lookup import lookup_jav_actresses, lookup_web_jav_metadata

logger = logging.getLogger(__name__)

DEFAULT_CACHE_PATH = "data/jav_metadata_cache.json"


def _get_db_from_config_or_cache_path(config: dict | None = None, cache_path: str = DEFAULT_CACHE_PATH):
    from .db import MeridianDB
    db_path = None
    if config:
        db_path = config.get("db_path")
    if not db_path and cache_path:
        p = Path(cache_path)
        db_path = p.with_suffix(".db") if p.suffix == ".json" else p
    return MeridianDB(db_path=db_path)


def load_cache(cache_path: str = DEFAULT_CACHE_PATH) -> dict:
    db = _get_db_from_config_or_cache_path(cache_path=cache_path)
    path = Path(cache_path)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, dict):
                            db.save_jav_metadata(k, v)
        except Exception as e:
            logger.warning(f"Cache load failed: {e}")
    return db.get_all_jav_metadata()


def save_cache(cache_path: str, cache: dict) -> None:
    db = _get_db_from_config_or_cache_path(cache_path=cache_path)
    for k, v in cache.items():
        if isinstance(v, dict):
            db.save_jav_metadata(k, v)


def get_jav_metadata(
    code: str,
    config: dict | None = None,
) -> dict:
    """
    품번(code)으로 JAV 메타데이터 수집.
    필드 단위 병합: JavBus/Jav321 Web DB (1차) -> 비어있는 배우 정보 OneJAV (2차)
    """
    if config is None:
        try:
            config = load_config()
        except Exception:
            config = {}

    cache_path = config.get("jav_metadata_cache") or DEFAULT_CACHE_PATH
    db = _get_db_from_config_or_cache_path(config=config, cache_path=cache_path)
    if Path(cache_path).exists():
        db.migrate_json_caches(jav_json=cache_path)

    code_upper = code.upper()
    if code_upper.startswith("FC2"):
        return {
            "code": code_upper,
            "actresses": [],
            "makers": [],
            "genres": [],
            "title": None,
            "cover_url": None,
            "source": "none",
        }

    cached = db.get_jav_metadata(code_upper)
    if cached and (cached.get("cast_checked") or cached.get("source") == "manual_fix"):
        logger.debug(f"[JAV Metadata Cache Hit] {code_upper}")
        return cached

    sources_used = []
    actresses = []
    makers = []
    genres = []
    title = None
    cover_url = None

    # 1. Web DB (JavBus/Jav321) SSH Lookup
    try:
        web_data = lookup_web_jav_metadata(code_upper, config)
        if web_data:
            used = False
            if web_data.get("actresses"):
                actresses = web_data.get("actresses", [])
                used = True
            if web_data.get("makers"):
                makers = web_data.get("makers", [])
                used = True
            if web_data.get("title"):
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

    # 2. OneJAV Lookup Fallback: 여전히 배우 정보가 없는 경우 보완
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

    if cached:
        for field in ("title", "makers", "genres", "cover_url"):
            if not metadata[field]:
                metadata[field] = cached.get(field)

    # Inconclusive lookups stay retryable. Never return a legacy unverified cast.
    if actresses:
        metadata["cast_checked"] = True
        db.save_jav_metadata(code_upper, metadata)
    elif not cached and sources_used:
        db.save_jav_metadata(code_upper, metadata)
    return metadata


