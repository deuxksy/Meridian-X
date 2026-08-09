"""
Meridian-X West Metadata Resolver
StashDB GraphQL API (searchScene) 및 디스크 캐싱 모듈
"""

import json
import logging
import os
import re
from pathlib import Path
import requests

from .core import load_config

logger = logging.getLogger(__name__)

DEFAULT_CACHE_PATH = "logs/stashdb_metadata_cache.json"
STASHDB_GRAPHQL_URL = "https://stashdb.org/graphql"


def clean_search_term(filename: str) -> str:
    """파일명에서 릴리즈 그룹, 해상도, 날짜, 확장자 등 불필요한 태그 제거."""
    stem = Path(filename).stem
    # 1. 확장자 및 특수 구문 제거
    stem = re.sub(r"\[.*?\]|\(.*?\)", " ", stem)
    # 2. 해상도/코덱/품질/그룹 키워드 제거
    keywords = [
        r"\b1080p\b", r"\b720p\b", r"\b2160p\b", r"\b4k\b", r"\bhd\b",
        r"\bmp4\b", r"\bmkv\b", r"\bavi\b", r"\bxxx\b", r"\bp2p\b",
        r"\bwrb\b", r"\bnbq\b", r"\bhevc\b", r"\bx264\b", r"\bx265\b",
    ]
    for kw in keywords:
        stem = re.sub(kw, " ", stem, flags=re.IGNORECASE)
    # 3. 날짜 패턴 (예: 26.08.05, 2026.08.05) 제거
    stem = re.sub(r"\b\d{2,4}[\.\-_]\d{2}[\.\-_]\d{2}\b", " ", stem)
    # 4. 특수 기호 변환 및 연속 공백 정리
    cleaned = re.sub(r"[\._\-\s]+", " ", stem).strip()
    return cleaned


def load_cache(cache_path: str = DEFAULT_CACHE_PATH) -> dict:
    path = Path(cache_path)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"StashDB cache load failed: {e}")
        return {}


def save_cache(cache_path: str, cache: dict) -> None:
    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.warning(f"StashDB cache save failed: {e}")


def get_west_metadata(
    filename: str,
    config: dict | None = None,
    api_key: str | None = None,
) -> dict:
    """StashDB GraphQL API를 통해 West 미디어 메타데이터 수집."""
    if config is None:
        try:
            config = load_config()
        except Exception:
            config = {}

    cache_path = config.get("stashdb_metadata_cache") or DEFAULT_CACHE_PATH
    cache = load_cache(cache_path)
    term = clean_search_term(filename)

    if not term:
        return {"query_term": "", "performers": [], "studio": None, "tags": [], "title": None, "date": None, "source": "none"}

    if term in cache:
        logger.debug(f"[StashDB Cache Hit] {term}")
        return cache[term]

    api_key = api_key or os.getenv("STASHDB_API_KEY") or config.get("stashdb", {}).get("api_key")

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["ApiKey"] = api_key

    query = """
    query QueryScenes($input: SceneQueryInput!) {
      queryScenes(input: $input) {
        count
        scenes {
          id
          title
          date
          studio {
            name
          }
          performers {
            performer {
              name
            }
          }
          tags {
            name
          }
        }
      }
    }
    """

    performers = []
    studio = None
    tags = []
    title = None
    date = None
    source = "none"

    try:
        resp = requests.post(
            STASHDB_GRAPHQL_URL,
            json={"query": query, "variables": {"input": {"text": term, "page": 1, "per_page": 5}}},
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            res_json = resp.json()
            data = res_json.get("data") or {}
            qs = data.get("queryScenes") or {}
            scenes = qs.get("scenes") or []
            if scenes:
                first_scene = scenes[0]
                title = first_scene.get("title")
                date = first_scene.get("date")
                st_data = first_scene.get("studio")
                if st_data and isinstance(st_data, dict):
                    studio = st_data.get("name")
                for p in first_scene.get("performers", []):
                    p_name = p.get("performer", {}).get("name")
                    if p_name and p_name not in performers:
                        performers.append(p_name)
                for t in first_scene.get("tags", []):
                    t_name = t.get("name")
                    if t_name and t_name not in tags:
                        tags.append(t_name)
                source = "stashdb"
    except Exception as e:
        logger.warning(f"[StashDB API Error] {term}: {e}")


    metadata = {
        "query_term": term,
        "performers": performers,
        "studio": studio,
        "tags": tags,
        "title": title,
        "date": date,
        "source": source,
    }

    cache[term] = metadata
    save_cache(cache_path, cache)
    return metadata
