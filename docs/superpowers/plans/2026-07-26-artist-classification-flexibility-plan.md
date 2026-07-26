# Artist & Studio Classification Flexibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement delimiter-flexible string normalization (`.`, `_`, `-`, spaces) for artist and studio classification in `src/meridian_x/classify.py`, append `"Dakota Doll"` to `artist_folders` in `config/settings.json`, and ensure full unit test coverage.

**Architecture:** Add a `_normalize_name(name: str) -> str` utility using `re.sub(r'[\._\-\s]+', '', name).lower()` and apply it to `classify_filename()` and `classify_folder()` matching loops.

**Tech Stack:** Python 3.12, `re` module, `pytest`, `uv`.

## Global Constraints

- Preserve classification matching priority (`artist` > `studio` > `genre` > `JPN` > `FC2` > `West`).
- Preserved target folder naming format (canonical configured names like `"Dakota Doll"`).
- Maintain existing codebase conventions and test structure.

---

### Task 1: Add Name Normalization Helper and Update Classification Logic

**Files:**
- Modify: `src/meridian_x/classify.py`
- Create: `tests/test_classify.py`

**Interfaces:**
- Produces: `_normalize_name(name: str) -> str` in `src/meridian_x/classify.py`
- Updates: `classify_filename(filename: str, config: dict) -> str` and `classify_folder(folder_name: str, config: dict) -> str`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_classify.py`:

```python
import pytest
from src.meridian_x.classify import _normalize_name, classify_filename, classify_folder

def test_normalize_name():
    assert _normalize_name("Dakota.Doll") == "dakotadoll"
    assert _normalize_name("dakota_doll") == "dakotadoll"
    assert _normalize_name("Dakota Doll") == "dakotadoll"
    assert _normalize_name("ohmyholes.25.02.13.dakota.doll.mp4") == "ohmyholes250213dakotadollmp4"

def test_classify_filename_with_normalized_artist():
    config = {
        "classify": {
            "artist_folders": ["Dakota Doll"],
            "studio_folders": ["Vixen"]
        }
    }
    assert classify_filename("ohmyholes.25.02.13.dakota.doll.mp4", config) == "Dakota Doll"
    assert classify_filename("dakota_doll_scene_01.mp4", config) == "Dakota Doll"
    assert classify_filename("Vixen.24.01.01.random.scene.mp4", config) == "Vixen"
    assert classify_filename("GVH-864.mp4", config) == "JPN"
    assert classify_filename("FC2-PPV-4930952.mp4", config) == "FC2"
    assert classify_filename("random_western_file.mp4", config) == "West"

def test_classify_folder_with_normalized_artist():
    config = {
        "classify": {
            "artist_folders": ["Dakota Doll"],
            "studio_folders": ["Vixen"]
        }
    }
    assert classify_folder("dakota.doll.collection", config) == "Dakota Doll"
    assert classify_folder("vixen.studio.pack", config) == "Vixen"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/test_classify.py`
Expected: FAIL with `cannot import name '_normalize_name'` or assertion error.

- [ ] **Step 3: Implement `_normalize_name` and update matching in `src/meridian_x/classify.py`**

In `src/meridian_x/classify.py`:

```python
def _normalize_name(name: str) -> str:
    """파일명/폴더명 및 검색 키워드의 구분 기호(점, 밑줄, 하이픈, 공백)를 제거하고 소문자로 변환."""
    return re.sub(r'[\._\-\s]+', '', name).lower()
```

Update `classify_filename()`:
```python
def classify_filename(filename: str, config: dict) -> str:
    f_lower = filename.lower()
    f_norm = _normalize_name(filename)
    classify = config.get("classify", {})

    # 1. 배우
    for folder in classify.get("artist_folders", []):
        if _normalize_name(folder) in f_norm:
            return folder

    # 2. 스튜디오
    for folder in classify.get("studio_folders", []):
        if _normalize_name(folder) in f_norm:
            return folder
    ...
```

Update `classify_folder()`:
```python
def classify_folder(folder_name: str, config: dict) -> str | None:
    f_norm = _normalize_name(folder_name)
    classify = config.get("classify", {})

    # 1. 배우
    for folder in classify.get("artist_folders", []):
        if _normalize_name(folder) in f_norm:
            return folder

    # 2. 스튜디오
    for folder in classify.get("studio_folders", []):
        if _normalize_name(folder) in f_norm:
            return folder
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_classify.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/meridian_x/classify.py tests/test_classify.py
git commit -m "feat: add delimiter-flexible normalization matching for artist and studio classification"
```

---

### Task 2: Update Configuration Settings

**Files:**
- Modify: `config/settings.json`
- Modify: `config/settings.json.example`

- [ ] **Step 1: Write configuration test in `tests/test_classify.py`**

Append to `tests/test_classify.py`:

```python
from meridian_x.core import load_config

def test_dakota_doll_in_settings():
    config = load_config("config/settings.json")
    assert "Dakota Doll" in config.get("classify", {}).get("artist_folders", [])
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/test_classify.py -k test_dakota_doll_in_settings`
Expected: FAIL (`AssertionError`)

- [ ] **Step 3: Update `config/settings.json` and `config/settings.json.example`**

Add `"Dakota Doll"` to `artist_folders` array in `config/settings.json` and `config/settings.json.example`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config/settings.json config/settings.json.example tests/test_classify.py
git commit -m "config: add Dakota Doll to artist_folders"
```
