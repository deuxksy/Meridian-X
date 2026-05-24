"""
Meridian-X FANZA API Client
FANZA(DMM) Affiliate API로 JAV 메타데이터 조회
"""

import json
import logging
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

FANZA_API_URL = "https://api.dmm.com/affiliate/v3/ItemList"

# JAV 코드 추출 패턴: "SONE-446.mp4" -> "SONE-446"
JAV_CODE_PATTERN = re.compile(r"^([A-Z]{3,5}-\d{3,5})")

# FC2 코드 패턴: API에 등록되지 않은 경우가 많음
FC2_PATTERN = re.compile(r"^FC2", re.IGNORECASE)


def load_cache(cache_path: str) -> dict:
    """디스크 캐시 로드"""
    path = Path(cache_path)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Cache load failed, starting fresh: {e}")
        return {}


def save_cache(cache_path: str, cache: dict) -> None:
    """디스크 캐시 저장"""
    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def extract_jav_code(filename: str) -> str | None:
    """파일명에서 JAV 코드 추출: 'SONE-446.mp4' -> 'SONE-446'"""
    match = JAV_CODE_PATTERN.match(filename)
    return match.group(1) if match else None


class FanzaClient:
    """FANZA(DMM) Affiliate API 클라이언트"""

    def __init__(
        self,
        api_id: str,
        affiliate_id: str,
        timeout: int = 10,
        rate_limit: float = 1.0,
    ):
        self._api_id = api_id
        self._affiliate_id = affiliate_id
        self._timeout = timeout
        self._rate_limit = rate_limit
        self._last_request_time = 0.0
        self._session = requests.Session()
        self._cache: dict = {}

    def fetch_metadata(self, jav_code: str) -> dict | None:
        """JAV 코드로 메타데이터 조회. 캐시 우선."""
        # FC2 코드 스킵
        if FC2_PATTERN.match(jav_code):
            logger.debug(f"Skipping FC2 code: {jav_code}")
            return None

        # 메모리 캐시 확인
        if jav_code in self._cache:
            logger.debug(f"Cache hit: {jav_code}")
            return self._cache[jav_code]

        # API 조회
        data = self._make_request(jav_code)
        if not data:
            return None

        metadata = self._parse_response(data)
        if metadata:
            self._cache[jav_code] = metadata

        return metadata

    def _make_request(self, keyword: str, max_retries: int = 3) -> dict | None:
        """FANZA API 요청 (지수 백오프 재시도)"""
        params = {
            "api_id": self._api_id,
            "affiliate_id": self._affiliate_id,
            "site": "FANZA",
            "service": "digital",
            "floor": "videoa",
            "keyword": keyword,
            "hits": 1,
            "output": "json",
        }

        for attempt in range(max_retries):
            self._wait_rate_limit()
            try:
                response = self._session.get(
                    FANZA_API_URL, params=params, timeout=self._timeout
                )
                if response.status_code == 429:
                    wait = 2**attempt
                    logger.warning(f"Rate limited, waiting {wait}s...")
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                logger.error(f"FANZA API error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)

        return None

    def _parse_response(self, data: dict) -> dict | None:
        """API 응답에서 배우/메이커/장르 추출"""
        items = data.get("result", {}).get("items", [])
        if not items:
            return None

        iteminfo = items[0].get("iteminfo", {})
        return {
            "actresses": [a["name"] for a in iteminfo.get("actress", [])],
            "makers": [m["name"] for m in iteminfo.get("maker", [])],
            "genres": [g["name"] for g in iteminfo.get("genre", [])],
        }

    def _wait_rate_limit(self) -> None:
        """요청 간격 조절"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit:
            time.sleep(self._rate_limit - elapsed)
        self._last_request_time = time.time()
