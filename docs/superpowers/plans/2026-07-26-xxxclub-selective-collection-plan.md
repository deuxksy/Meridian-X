# XXXClub Selective Collection Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement whitelist title matching helper `is_whitelisted_title()`, integrate `selective_only` filtering in `src/meridian_x/sources/xxxclub.py`, update configuration files, and verify with unit tests.

**Architecture:** Create whitelist matching utility, integrate filtering in `xxxclub.py` discovery, add `"selective_only": true` to `config/settings.json`, and add tests in `tests/test_collect.py`.

**Tech Stack:** Python 3.12, `pytest`, `uv`.

## Global Constraints

- Whitelist filter must match against `artist_folders`, `studio_folders`, and `genres` (keywords and prefixes).
- Use normalized string comparison (`_normalize_name`).

---

### Task 1: Add Whitelist Match Helper and XXXClub Filter Integration

**Files:**
- Modify: `src/meridian_x/sources/xxxclub.py`
- Modify: `config/settings.json`
- Modify: `config/settings.json.example`
- Create: `tests/test_collect.py`

- [ ] **Step 1: Write failing unit test in `tests/test_collect.py`**

Create `tests/test_collect.py`:

```python
import pytest
from meridian_x.sources.xxxclub import is_whitelisted_title

def test_is_whitelisted_title():
    config = {
        "classify": {
            "artist_folders": ["Dakota Doll"],
            "studio_folders": ["ExxxtraSmall", "Vixen"]
        },
        "genres": {
            "Vixen": {"prefixes": ["tushy"]}
        }
    }
    assert is_whitelisted_title("ExxxtraSmall.26.07.18.Remi.Raw.mp4", config) is True
    assert is_whitelisted_title("Tushy.26.06.28.Alina.Lopez.mp4", config) is True
    assert is_whitelisted_title("Dakota.Doll.OhMyHoles.mp4", config) is True
    assert is_whitelisted_title("UnknownStudio.26.07.18.Random.mp4", config) is False
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/test_collect.py`
Expected: FAIL (`ImportError: cannot import name 'is_whitelisted_title'`)

- [ ] **Step 3: Implement `is_whitelisted_title()` and filter in `src/meridian_x/sources/xxxclub.py`**

In `src/meridian_x/sources/xxxclub.py`:

```python
from meridian_x.classify import _normalize_name

def is_whitelisted_title(title: str, config: dict) -> bool:
    """Check if title contains any configured artist, studio, or genre keyword."""
    classify = config.get("classify", {})
    genres = config.get("genres", {})

    keywords = set(classify.get("artist_folders", []))
    keywords.update(classify.get("studio_folders", []))

    for genre_name, rules in genres.items():
        keywords.add(genre_name)
        keywords.update(rules.get("keywords", []))
        keywords.update(rules.get("prefixes", []))

    norm_title = _normalize_name(title)
    for kw in keywords:
        if kw and _normalize_name(kw) in norm_title:
            return True
    return False
```

Update `discover(config: dict)` in `src/meridian_x/sources/xxxclub.py`:
```python
def discover(config: dict) -> list[dict]:
    ...
    items = _parse_rss(response.text)
    if config.get("selective_only", True):
        items = [i for i in items if is_whitelisted_title(i["title"], config)]
    return items
```

Add `"selective_only": true` to `sources.xxxclub` in `config/settings.json` and `config/settings.json.example`.

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest`
Expected: PASS (all 25+ tests pass)

- [ ] **Step 5: Commit**

```bash
git add src/meridian_x/sources/xxxclub.py config/settings.json config/settings.json.example tests/test_collect.py
git commit -m "feat: add whitelist selective collection filter for XXXClub RSS"
```
