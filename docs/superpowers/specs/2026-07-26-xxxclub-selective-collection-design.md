# Design Spec: XXXClub Selective Collection Filter in Meridian-X

**Date:** 2026-07-26  
**Status:** Approved  
**Topic:** Whitelist Filtering for XXXClub RSS Collection  

---

## 1. Overview

Currently, XXXClub RSS collection processes all 1080p full HD feeds. Users want to download only videos matching configured artists, studios, or genres (`artist_folders`, `studio_folders`, `genres`).

This spec introduces a whitelist selective collection filter so that XXXClub RSS items are collected only when their title matches a configured artist, studio, or genre keyword.

---

## 2. Goals & Non-Goals

### Goals
1. **Selective Whitelist Filter:** Implement `is_whitelisted_title(title: str, config: dict) -> bool` using delimiter-normalized string matching.
2. **Source Option Support:** Add `"selective_only": true` to `sources.xxxclub` in `config/settings.json` and `config/settings.json.example`.
3. **RSS Filtering:** Filter out non-matching RSS items during `xxxclub` discovery when `selective_only` is enabled.
4. **Test Verification:** Unit test selective filtering logic with test cases.

### Non-Goals
- Modifying Japanese RSS sources (e.g., `onejav` RSS behavior).

---

## 3. Detailed Design

### 3.1 Whitelist Match Helper (`src/meridian_x/collect.py` or `src/meridian_x/sources/xxxclub.py`)

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

### 3.2 Filtering in `xxxclub.py` Discovery

In `discover(config: dict) -> list[dict]`:
```python
if config.get("selective_only", True):
    items = [i for i in items if is_whitelisted_title(i["title"], config)]
```

### 3.3 Configuration Update (`config/settings.json`)

```json
"sources": {
  "xxxclub": {
    "enabled": true,
    "selective_only": true,
    "rss_url": "https://xxxclub.to/feed/1080p.FullHD.xml"
  }
}
```

---

## 4. Verification & Testing Plan

1. **Unit Testing (`tests/test_collect.py`):**
   - Test `is_whitelisted_title("ExxxtraSmall.26.07.18.mp4", config)` returns `True`.
   - Test `is_whitelisted_title("UnknownStudio.26.07.18.mp4", config)` returns `False`.
2. **CLI Dry Run Check:**
   - Execute `uv run meridian transmission --source xxxclub --dry-run` to confirm only whitelisted titles are selected.

---
