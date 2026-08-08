# JPN Classification and Metadata Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement API-based JPN video auto-classification into actor/studio directories and rich Jellyfin metadata (Studios, Genres, People, Tags) synchronization using FANZA API as primary source and OneJAV lookup as secondary fallback.

**Architecture:** Create a unified `jav_metadata.py` module with disk caching (`logs/jav_metadata_cache.json`). `classify.py` consumes this metadata to determine remote folder destinations (`Actors/{actress}` or `{maker}`), and `jellyfin.py` consumes it to enrich Jellyfin items via REST API `POST /Items/{id}`.

**Tech Stack:** Python 3.10+, Requests, BeautifulSoup4, Pytest.

## Global Constraints

- Preserve all existing API signatures and fallback logic in `classify.py` and `jellyfin.py`.
- FANZA API is used as primary lookup source for JAV titles; OneJAV SSH scraping is fallback for FC2 or unlisted items.
- All code changes must pass `uv run pytest tests/ -v`.
- Commit after each task.

---

### Task 1: Create `jav_metadata.py` module with hybrid lookup & disk caching

**Files:**
- Create: `src/meridian_x/jav_metadata.py`
- Test: `tests/test_jav_metadata.py`

**Interfaces:**
- Produces: `get_jav_metadata(code: str, config: dict | None = None) -> dict` returning FANZA-standard schema:
  `{"code": str, "actresses": list[str], "makers": list[str], "genres": list[str], "title": str | None, "cover_url": str | None, "source": str}`

- [ ] **Step 1: Write failing test for `jav_metadata.py`**

Create `tests/test_jav_metadata.py`:
```python
import json
from unittest.mock import MagicMock, patch
from meridian_x.jav_metadata import get_jav_metadata, load_cache, save_cache


def test_jav_metadata_cache(tmp_path):
    cache_file = tmp_path / "cache.json"
    cache_data = {
        "SONE-446": {
            "code": "SONE-446",
            "actresses": ["MINAMO"],
            "makers": ["S1 NO.1 STYLE"],
            "genres": ["ハイビジョン"],
            "title": "Sample Title",
            "cover_url": "https://example.com/cover.jpg",
            "source": "cache",
        }
    }
    save_cache(str(cache_file), cache_data)

    loaded = load_cache(str(cache_file))
    assert loaded["SONE-446"]["actresses"] == ["MINAMO"]


@patch("meridian_x.jav_metadata.FanzaClient")
def test_get_jav_metadata_fanza_success(mock_fanza_cls, tmp_path):
    mock_client = MagicMock()
    mock_client.fetch_metadata.return_value = {
        "actresses": ["MINAMO"],
        "makers": ["S1 NO.1 STYLE"],
        "genres": ["単体作品"],
    }
    mock_fanza_cls.return_value = mock_client

    cache_file = tmp_path / "cache.json"
    config = {
        "cache_file": str(cache_file),
    }

    meta = get_jav_metadata("SONE-446", config=config, api_id="test_id", affiliate_id="test_aff")
    assert meta["actresses"] == ["MINAMO"]
    assert meta["makers"] == ["S1 NO.1 STYLE"]
    assert meta["source"] == "fanza"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_jav_metadata.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'meridian_x.jav_metadata'"

- [ ] **Step 3: Implement `jav_metadata.py`**

Create `src/meridian_x/jav_metadata.py`:
```python
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
from .jav_lookup import lookup_jav_actresses

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
    캐시 -> FANZA API -> OneJAV Lookup 순서로 시도.
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

    # 2. OneJAV SSH Lookup Fallback
    if not actresses:
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_jav_metadata.py -v`
Expected: PASS

- [ ] **Step 5: Commit Task 1**

```bash
git add src/meridian_x/jav_metadata.py tests/test_jav_metadata.py
git commit -m "feat: add jav_metadata module with hybrid FANZA API and OneJAV lookup caching"
```

---

### Task 2: Integrate `jav_metadata` into `classify.py` for API-based directory classification

**Files:**
- Modify: `src/meridian_x/classify.py`
- Modify: `tests/test_classify.py`

**Interfaces:**
- Consumes: `jav_metadata.get_jav_metadata(code, config)`
- Modifies: `classify_filename(filename, config)` and `classify_by_actress_lookup(filename, config)` in `classify.py`

- [ ] **Step 1: Write failing test in `test_classify.py` for API metadata classification**

Add to `tests/test_classify.py`:
```python
from unittest.mock import patch
from meridian_x.classify import classify_filename_with_metadata


@patch("meridian_x.classify.get_jav_metadata")
def test_classify_filename_with_metadata_actress(mock_get_meta):
    mock_get_meta.return_value = {
        "code": "SONE-446",
        "actresses": ["MINAMO"],
        "makers": ["S1 NO.1 STYLE"],
        "genres": [],
        "source": "fanza",
    }

    config = {
        "classify": {
            "artists": {"WEST": [], "JPN": []},
            "studios": {"WEST": {}, "JPN": {}},
        }
    }

    dest = classify_filename_with_metadata("SONE-446.mp4", config)
    assert dest == "Actors/MINAMO"


@patch("meridian_x.classify.get_jav_metadata")
def test_classify_filename_with_metadata_maker_fallback(mock_get_meta):
    mock_get_meta.return_value = {
        "code": "SONE-446",
        "actresses": [],
        "makers": ["S1 NO.1 STYLE"],
        "genres": [],
        "source": "fanza",
    }

    config = {
        "classify": {
            "artists": {"WEST": [], "JPN": []},
            "studios": {"WEST": {}, "JPN": {}},
        }
    }

    dest = classify_filename_with_metadata("SONE-446.mp4", config)
    assert dest == "S1 NO.1 STYLE"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_classify.py -k test_classify_filename_with_metadata -v`
Expected: FAIL with "ImportError: cannot import name 'classify_filename_with_metadata'"

- [ ] **Step 3: Implement `classify_filename_with_metadata` in `src/meridian_x/classify.py`**

In `src/meridian_x/classify.py`, import `extract_jav_code` and `get_jav_metadata`, then add:
```python
from .jav_metadata import get_jav_metadata


def classify_filename_with_metadata(filename: str, config: dict, use_metadata: bool = True) -> str:
    """
    파일명 → 목적지 폴더 결정 (외부 API 메타데이터 연동).
    우선순위: 명시적 설정(배우/스튜디오/장르) > API 메타데이터(배우 > 스튜디오) > JPN > FC2 > West
    """
    # 1. 기존 명시적 설정 규칙 우선
    dest = classify_filename(filename, config)
    if dest not in ("JPN", "FC2", "West"):
        return dest

    # 2. JAV 패턴 매칭 시 API 메타데이터 조회
    if use_metadata and dest == "JPN":
        code = extract_jav_code(filename)
        if code:
            meta = get_jav_metadata(code, config)
            actresses = meta.get("actresses", [])
            makers = meta.get("makers", [])

            if actresses:
                return f"Actors/{actresses[0]}"
            if makers:
                return makers[0]

    return dest
```

Update `run()` in `classify.py` to use `classify_filename_with_metadata`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_classify.py -v`
Expected: PASS

- [ ] **Step 5: Commit Task 2**

```bash
git add src/meridian_x/classify.py tests/test_classify.py
git commit -m "feat: integrate jav_metadata into classify module for API-based directory routing"
```

---

### Task 3: Extend `jellyfin.py` for rich JPN metadata & tag synchronization

**Files:**
- Modify: `src/meridian_x/jellyfin.py`
- Modify: `tests/test_jellyfin.py`

**Interfaces:**
- Consumes: `jav_metadata.get_jav_metadata(code, config)`
- Modifies: `JellyfinClient` to add `update_metadata(item_id, metadata_dict)` and extend `sync_tags()` in `jellyfin.py`

- [ ] **Step 1: Write failing test for `update_metadata` in `tests/test_jellyfin.py`**

Add to `tests/test_jellyfin.py`:
```python
from unittest.mock import MagicMock, patch
from meridian_x.jellyfin import JellyfinClient


@patch.object(JellyfinClient, "_post")
@patch.object(JellyfinClient, "get_item")
def test_update_metadata(mock_get_item, mock_post):
    mock_get_item.return_value = {
        "Id": "item123",
        "Name": "SONE-446",
        "Path": "/data/JPN/SONE-446.mp4",
        "Tags": [],
        "Studios": [],
        "Genres": [],
        "People": [],
    }

    client = JellyfinClient("http://localhost:8096", "test_key")
    metadata = {
        "actresses": ["MINAMO"],
        "makers": ["S1 NO.1 STYLE"],
        "genres": ["単体作品"],
    }

    ok = client.update_metadata("item123", metadata)
    assert ok is True
    mock_post.assert_called_once()
    posted_payload = mock_post.call_args[0][1]
    assert posted_payload["Genres"] == ["単体作品"]
    assert posted_payload["Studios"] == [{"Name": "S1 NO.1 STYLE"}]
    assert posted_payload["People"] == [{"Name": "MINAMO", "Type": "Actor"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_jellyfin.py -k test_update_metadata -v`
Expected: FAIL with "AttributeError: 'JellyfinClient' object has no attribute 'update_metadata'"

- [ ] **Step 3: Implement `update_metadata` and update `sync_tags` in `src/meridian_x/jellyfin.py`**

Add `update_metadata` to `JellyfinClient` in `src/meridian_x/jellyfin.py`:
```python
    def update_metadata(self, item_id: str, metadata: dict) -> bool:
        """아이템 Studios, Genres, People, Tags 메타데이터 동기화."""
        try:
            item = self.get_item(item_id)
            if not item:
                return False

            actresses = metadata.get("actresses", [])
            makers = metadata.get("makers", [])
            genres = metadata.get("genres", [])

            if makers:
                item["Studios"] = [{"Name": m} for m in makers]
            if genres:
                item["Genres"] = list(genres)
            if actresses:
                item["People"] = [{"Name": a, "Type": "Actor"} for a in actresses]

            tags = set(item.get("Tags", []))
            for a in actresses:
                tags.add(a.lower())
            for m in makers:
                tags.add(m.lower())
            item["Tags"] = sorted(tags)

            item = {k: v for k, v in item.items() if v is not None}
            self._post(f"/Items/{item_id}", item)
            return True
        except Exception as e:
            logger.error(f"[Jellyfin] Update metadata failed for {item_id}: {e}")
            return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_jellyfin.py -v`
Expected: PASS

- [ ] **Step 5: Run all test suites to confirm no regression**

Run: `uv run pytest tests/ -v`
Expected: PASS (All tests passing cleanly)

- [ ] **Step 6: Commit Task 3**

```bash
git add src/meridian_x/jellyfin.py tests/test_jellyfin.py
git commit -m "feat: extend JellyfinClient to update Studios, Genres, People, and Tags from JAV metadata"
```
