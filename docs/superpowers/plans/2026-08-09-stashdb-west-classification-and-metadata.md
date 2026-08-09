# StashDB West Media Classification and Metadata Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement StashDB GraphQL API-based West media auto-classification into performer/studio directories and rich Jellyfin metadata (Studios, People, Tags) synchronization with disk caching.

**Architecture:** Create a `west_metadata.py` module with filename cleaning and disk caching (`logs/stashdb_metadata_cache.json`). `classify.py` consumes this metadata to route West files to `Actors/{performer}` or `{studio}`, and `jellyfin.py` consumes it to enrich Jellyfin items via REST API `POST /Items/{id}`.

**Tech Stack:** Python 3.10+, Requests, GraphQL over HTTP, Pytest.

## Global Constraints

- Preserve all existing API signatures and fallback logic in `classify.py` and `jellyfin.py`.
- StashDB GraphQL API Key is read from `os.getenv("STASHDB_API_KEY")` or `config.get("stashdb", {}).get("api_key")`.
- All code changes must pass `uv run pytest tests/ -v`.
- Commit after each task.

---

### Task 1: Create `west_metadata.py` module with filename cleaning & StashDB GraphQL API caching

**Files:**
- Create: `src/meridian_x/west_metadata.py`
- Test: `tests/test_west_metadata.py`

**Interfaces:**
- Produces: `clean_search_term(filename: str) -> str`
- Produces: `get_west_metadata(filename: str, config: dict | None = None, api_key: str | None = None) -> dict` returning standard schema:
  `{"query_term": str, "performers": list[str], "studio": str | None, "tags": list[str], "title": str | None, "date": str | None, "source": str}`

- [ ] **Step 1: Write failing test for `west_metadata.py`**

Create `tests/test_west_metadata.py`:
```python
import json
from unittest.mock import MagicMock, patch
from meridian_x.west_metadata import clean_search_term, get_west_metadata, load_cache, save_cache


def test_clean_search_term():
    filename = "Vixen.26.08.05.Cindy.Luna.Fit.Babe.Needs.Cum.XXX.1080p.MP4-P2P.mp4"
    cleaned = clean_search_term(filename)
    assert "1080p" not in cleaned
    assert "MP4" not in cleaned
    assert "26.08.05" not in cleaned
    assert "Cindy Luna Fit Babe Needs Cum" in cleaned


def test_west_metadata_cache(tmp_path):
    cache_file = tmp_path / "cache.json"
    cache_data = {
        "Vixen Lily Love": {
            "query_term": "Vixen Lily Love",
            "performers": ["Lily Love"],
            "studio": "Vixen",
            "tags": ["Lesbian"],
            "title": "Sample Title",
            "date": "2025-01-29",
            "source": "cache",
        }
    }
    save_cache(str(cache_file), cache_data)

    loaded = load_cache(str(cache_file))
    assert loaded["Vixen Lily Love"]["performers"] == ["Lily Love"]


@patch("meridian_x.west_metadata.requests.post")
def test_get_west_metadata_stashdb_success(mock_post, tmp_path):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {
            "searchScene": [
                {
                    "id": "scene123",
                    "title": "Sample Scene",
                    "date": "2025-01-29",
                    "studio": {"name": "Vixen"},
                    "performers": [{"performer": {"name": "Lily Love"}}],
                    "tags": [{"name": "Lesbian"}],
                }
            ]
        }
    }
    mock_post.return_value = mock_resp

    cache_file = tmp_path / "cache.json"
    config = {"stashdb_metadata_cache": str(cache_file)}

    meta = get_west_metadata("Vixen.Lily.Love.mp4", config=config, api_key="test_token")
    assert meta["performers"] == ["Lily Love"]
    assert meta["studio"] == "Vixen"
    assert meta["tags"] == ["Lesbian"]
    assert meta["source"] == "stashdb"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_west_metadata.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'meridian_x.west_metadata'"

- [ ] **Step 3: Implement `west_metadata.py`**

Create `src/meridian_x/west_metadata.py`:
```python
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
    query SearchScenes($term: String!) {
      searchScene(term: $term) {
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
            json={"query": query, "variables": {"term": term}},
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            scenes = data.get("searchScene", [])
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_west_metadata.py -v`
Expected: PASS

- [ ] **Step 5: Commit Task 1**

```bash
git add src/meridian_x/west_metadata.py tests/test_west_metadata.py
git commit -m "feat: add west_metadata module with filename cleaning and StashDB GraphQL API caching"
```

---

### Task 2: Integrate `west_metadata` into `classify.py` for West directory classification

**Files:**
- Modify: `src/meridian_x/classify.py`
- Modify: `tests/test_classify.py`

**Interfaces:**
- Consumes: `west_metadata.get_west_metadata(filename, config)`
- Modifies: `classify_filename_with_metadata(filename, config, use_metadata)` in `classify.py`

- [ ] **Step 1: Write failing test in `test_classify.py` for StashDB West classification**

Add to `tests/test_classify.py`:
```python
from unittest.mock import patch
from meridian_x.classify import classify_filename_with_metadata


@patch("meridian_x.classify.get_west_metadata")
@patch("meridian_x.classify.get_jav_metadata")
def test_classify_filename_with_metadata_west_stashdb(mock_jav_meta, mock_west_meta):
    mock_jav_meta.return_value = {"actresses": [], "makers": []}
    mock_west_meta.return_value = {
        "query_term": "Lily Love",
        "performers": ["Lily Love"],
        "studio": "Vixen",
        "tags": [],
        "source": "stashdb",
    }

    config = {
        "classify": {
            "artists": {"WEST": [], "JPN": []},
            "studios": {"WEST": {}, "JPN": {}},
        }
    }

    dest = classify_filename_with_metadata("Lily.Love.Sample.mp4", config)
    assert dest == "Actors/Lily Love"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_classify.py -k test_classify_filename_with_metadata_west_stashdb -v`
Expected: FAIL with "AssertionError: assert 'West' == 'Actors/Lily Love'"

- [ ] **Step 3: Update `classify_filename_with_metadata` in `src/meridian_x/classify.py`**

Import `get_west_metadata` and update `classify_filename_with_metadata`:
```python
from .west_metadata import get_west_metadata


def classify_filename_with_metadata(filename: str, config: dict, use_metadata: bool = True) -> str:
    """
    파일명 → 목적지 폴더 결정 (외부 API 메타데이터 연동).
    우선순위: 명시적 설정(배우/스튜디오/장르) > API 메타데이터(JPN: 배우 > 스튜디오, West: StashDB 배우 > 스튜디오) > JPN > FC2 > West
    """
    dest = classify_filename(filename, config)
    if dest not in ("JPN", "FC2", "West"):
        return dest

    if use_metadata:
        # JAV 패턴 매칭 시 JPN 메타데이터 수집
        if dest == "JPN":
            code = extract_jav_code(filename)
            if code:
                meta = get_jav_metadata(code, config)
                actresses = meta.get("actresses", [])
                makers = meta.get("makers", [])
                if actresses:
                    return f"Actors/{actresses[0]}"
                if makers:
                    return makers[0]

        # JAV/FC2가 아닌 West 미디어에 대해 StashDB 메타데이터 수집
        elif dest == "West":
            west_meta = get_west_metadata(filename, config)
            performers = west_meta.get("performers", [])
            studio = west_meta.get("studio")
            if performers:
                return f"Actors/{performers[0]}"
            if studio:
                return studio

    return dest
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_classify.py -v`
Expected: PASS

- [ ] **Step 5: Commit Task 2**

```bash
git add src/meridian_x/classify.py tests/test_classify.py
git commit -m "feat: integrate west_metadata StashDB lookup into classify module for West directory routing"
```

---

### Task 3: Extend `jellyfin.py` for rich West metadata & tag synchronization using StashDB

**Files:**
- Modify: `src/meridian_x/jellyfin.py`
- Modify: `tests/test_jellyfin.py`

**Interfaces:**
- Consumes: `west_metadata.get_west_metadata(filename, config)`
- Modifies: `JellyfinClient.update_metadata` and `sync_tags` in `src/meridian_x/jellyfin.py`

- [ ] **Step 1: Write failing test in `tests/test_jellyfin.py` for StashDB West sync**

Add to `tests/test_jellyfin.py`:
```python
from unittest.mock import MagicMock, patch
from meridian_x.jellyfin import JellyfinClient


@patch.object(JellyfinClient, "_post")
@patch.object(JellyfinClient, "get_item")
def test_update_metadata_west_stashdb(mock_get_item, mock_post):
    mock_get_item.return_value = {
        "Id": "west123",
        "Name": "Vixen.Lily.Love",
        "Path": "/data/West/Vixen.Lily.Love.mp4",
        "Tags": [],
        "Studios": [],
        "Genres": [],
        "People": [],
    }

    client = JellyfinClient("http://localhost:8096", "test_key")
    metadata = {
        "performers": ["Lily Love"],
        "studio": "Vixen",
        "tags": ["Lesbian"],
    }

    ok = client.update_metadata("west123", metadata)
    assert ok is True
    mock_post.assert_called_once()
    posted_payload = mock_post.call_args[0][1]
    assert posted_payload["Studios"] == [{"Name": "Vixen"}]
    assert posted_payload["People"] == [{"Name": "Lily Love", "Type": "Actor"}]
    assert "lily love" in posted_payload["Tags"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_jellyfin.py -k test_update_metadata_west_stashdb -v`
Expected: FAIL (missing handling for `performers` and `studio` keys in `update_metadata`)

- [ ] **Step 3: Update `update_metadata` and `sync_tags` in `src/meridian_x/jellyfin.py`**

In `src/meridian_x/jellyfin.py`, support both JPN schema (`actresses`, `makers`) and West schema (`performers`, `studio`):
```python
    def update_metadata(self, item_id: str, metadata: dict) -> bool:
        """아이템 Studios, Genres, People, Tags 메타데이터 동기화 (JPN 및 West 공통)."""
        try:
            item = self.get_item(item_id)
            if not item:
                return False

            actresses = metadata.get("actresses") or metadata.get("performers") or []
            makers = metadata.get("makers") or ([metadata["studio"]] if metadata.get("studio") else [])
            genres = metadata.get("genres") or metadata.get("tags") or []

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
            for g in genres:
                tags.add(g.lower())
            item["Tags"] = sorted(tags)

            item = {k: v for k, v in item.items() if v is not None}
            self._post(f"/Items/{item_id}", item)
            return True
        except Exception as e:
            logger.error(f"[Jellyfin] Update metadata failed for {item_id}: {e}")
            return False
```

In `sync_tags()`, query `west_metadata.get_west_metadata()` for West items.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_jellyfin.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite to confirm zero regressions**

Run: `uv run pytest tests/ -v`
Expected: PASS (All tests green)

- [ ] **Step 6: Commit Task 3**

```bash
git add src/meridian_x/jellyfin.py tests/test_jellyfin.py
git commit -m "feat: extend JellyfinClient to sync StashDB West metadata (Performers, Studio, Tags)"
```
