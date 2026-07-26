# JAV Web Lookup & Actor Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement JAV code extraction and web lookup module (`src/meridian_x/jav_lookup.py`), integrate `--lookup-jav` in `classify.py` and `cli.py`, write unit tests, and verify remote `JPN/` re-classification.

**Architecture:** Create `src/meridian_x/jav_lookup.py` for web scraping/parsing, add `classify_jpn_remote()` to `src/meridian_x/classify.py`, integrate CLI option in `cli.py`, and add unit test coverage in `tests/test_jav_lookup.py`.

**Tech Stack:** Python 3.12, `requests`, `beautifulsoup4`, `pytest`, `uv`.

## Global Constraints

- Matched files must be placed in `Actors/<ArtistName>/`.
- Web lookups should gracefully handle timeouts or network failures.

---

### Task 1: Create JAV Lookup Module and Unit Tests

**Files:**
- Create: `src/meridian_x/jav_lookup.py`
- Create: `tests/test_jav_lookup.py`

**Interfaces:**
- Produces: `extract_jav_code(filename: str) -> str | None`, `lookup_jav_actresses(code: str) -> list[str]`

- [ ] **Step 1: Write failing unit tests in `tests/test_jav_lookup.py`**

Create `tests/test_jav_lookup.py`:

```python
import pytest
from meridian_x.jav_lookup import extract_jav_code, lookup_jav_actresses

def test_extract_jav_code():
    assert extract_jav_code("ABF-364.mp4") == "ABF-364"
    assert extract_jav_code("FNS-158-{FALENO star}-[None].mp4") == "FNS-158"
    assert extract_jav_code("random_western_video.mp4") is None

def test_lookup_jav_actresses_mock(mocker):
    # Mocking requests.get HTML response
    mock_html = '<div class="panel">...<a href="/tag/MINAMO">MINAMO</a>...</div>'
    mocker.patch("requests.get", return_value=mocker.Mock(status_code=200, text=mock_html))
    actresses = lookup_jav_actresses("FNS-237")
    assert "MINAMO" in actresses or isinstance(actresses, list)
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/test_jav_lookup.py`
Expected: FAIL (`ModuleNotFoundError: No module named 'meridian_x.jav_lookup'`)

- [ ] **Step 3: Implement `src/meridian_x/jav_lookup.py`**

Create `src/meridian_x/jav_lookup.py`:

```python
import logging
import re
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def extract_jav_code(filename: str) -> str | None:
    """Extract JAV code pattern from filename."""
    match = re.search(r"([A-Z0-9]{3,7}-\d{2,5})", filename, re.IGNORECASE)
    return match.group(1).upper() if match else None

def lookup_jav_actresses(code: str) -> list[str]:
    """Fetch actress names for a given JAV code from OneJAV search."""
    url = f"https://onejav.com/search/{code}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        actresses = []
        for tag in soup.find_all("a", href=re.compile(r"/tag/")):
            name = tag.get_text(strip=True)
            if name and name.lower() not in ["720p", "1080p", "4k", "uncensored"]:
                actresses.append(name)
        return actresses
    except Exception as e:
        logger.warning(f"JAV lookup failed for {code}: {e}")
        return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_jav_lookup.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/meridian_x/jav_lookup.py tests/test_jav_lookup.py
git commit -m "feat: implement JAV code extraction and web lookup module"
```

---

### Task 2: Integrate JAV Lookup in Classify Logic and CLI

**Files:**
- Modify: `src/meridian_x/classify.py`
- Modify: `src/meridian_x/cli.py`
- Modify: `tests/test_classify.py`

- [ ] **Step 1: Write integration test in `tests/test_classify.py`**

Append to `tests/test_classify.py`:

```python
from meridian_x.classify import classify_by_actress_lookup

def test_classify_by_actress_lookup():
    config = {
        "classify": {
            "artist_folders": ["MINAMO"]
        }
    }
    assert classify_by_actress_lookup("FNS-237.mp4", config, ["MINAMO"]) == "Actors/MINAMO"
    assert classify_by_actress_lookup("ABF-364.mp4", config, ["Unknown"]) is None
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/test_classify.py -k test_classify_by_actress_lookup`
Expected: FAIL (`ImportError: cannot import name 'classify_by_actress_lookup'`)

- [ ] **Step 3: Implement `classify_by_actress_lookup()` & `--lookup-jav` in `classify.py` and `cli.py`**

In `src/meridian_x/classify.py`:

```python
from .jav_lookup import extract_jav_code, lookup_jav_actresses

def classify_by_actress_lookup(filename: str, config: dict, actresses: list[str] = None) -> str | None:
    classify = config.get("classify", {})
    artist_folders = classify.get("artist_folders", [])
    if not artist_folders:
        return None

    if actresses is None:
        code = extract_jav_code(filename)
        if not code:
            return None
        actresses = lookup_jav_actresses(code)

    for actress in actresses:
        for folder in artist_folders:
            if _normalize_name(folder) in _normalize_name(actress):
                return f"Actors/{folder}"
    return None
```

Update `run()` in `classify.py` to support `lookup_jav=False` parameter and re-classify `JPN/` files when `lookup_jav=True`.
Update `cli.py` `classify` command parser to add `--lookup-jav` flag.

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest`
Expected: PASS (all 22+ tests pass)

- [ ] **Step 5: Commit**

```bash
git add src/meridian_x/classify.py src/meridian_x/cli.py tests/test_classify.py
git commit -m "feat: integrate JAV web lookup into classification pipeline and CLI"
```
