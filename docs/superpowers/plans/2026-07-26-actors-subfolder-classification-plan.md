# Actors Subfolder Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route artist classification target directories to `Actors/<ArtistName>/` in `src/meridian_x/classify.py`, update unit tests, and verify existing directory migration.

**Architecture:** Modify `classify_filename()` and `classify_folder()` artist return statements to return `f"Actors/{folder}"`, update `tests/test_classify.py`, and run tests.

**Tech Stack:** Python 3.12, `pytest`, `uv`.

## Global Constraints

- Artist matched folders MUST be nested inside `Actors/` (e.g. `Actors/Dakota Doll`).
- Preserve existing studio, genre, JPN, FC2, West rules.

---

### Task 1: Update Artist Target Path Logic and Tests

**Files:**
- Modify: `src/meridian_x/classify.py`
- Modify: `tests/test_classify.py`

- [ ] **Step 1: Update unit test assertions in `tests/test_classify.py`**

In `tests/test_classify.py`, update expected return values for artist matches from `"Dakota Doll"` to `"Actors/Dakota Doll"`.

```python
def test_classify_filename_with_normalized_artist():
    config = {
        "classify": {
            "artist_folders": ["Dakota Doll"],
            "studio_folders": ["Vixen"]
        }
    }
    assert classify_filename("ohmyholes.25.02.13.dakota.doll.mp4", config) == "Actors/Dakota Doll"
    assert classify_filename("dakota_doll_scene_01.mp4", config) == "Actors/Dakota Doll"

def test_classify_folder_with_normalized_artist():
    config = {
        "classify": {
            "artist_folders": ["Dakota Doll"],
            "studio_folders": ["Vixen"]
        }
    }
    assert classify_folder("dakota.doll.collection", config) == "Actors/Dakota Doll"
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/test_classify.py`
Expected: FAIL (`assert 'Dakota Doll' == 'Actors/Dakota Doll'`)

- [ ] **Step 3: Update `src/meridian_x/classify.py` return statements**

In `src/meridian_x/classify.py`:

```python
def classify_filename(filename: str, config: dict) -> str:
    ...
    # 1. 배우
    for folder in classify.get("artist_folders", []):
        if _normalize_name(folder) in f_norm:
            return f"Actors/{folder}"
    ...

def classify_folder(folder_name: str, config: dict) -> str | None:
    ...
    # 1. 배우
    for folder in classify.get("artist_folders", []):
        if _normalize_name(folder) in f_norm:
            return f"Actors/{folder}"
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest`
Expected: PASS (all 20 tests pass)

- [ ] **Step 5: Commit**

```bash
git add src/meridian_x/classify.py tests/test_classify.py
git commit -m "feat: nest artist classification under Actors/ subdirectory"
```
