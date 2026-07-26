# Design Spec: Artist and Studio Flexible Classification in Meridian-X

**Date:** 2026-07-26  
**Status:** Draft  
**Topic:** Flexible Delimiter Matching for Artist and Studio Classification & Adding Dakota Doll  

---

## 1. Overview

Meridian-X media classifier standardizes file organization based on priority rules (`artist` > `studio` > `genre` > `JPN` > `FC2` > `West`). However, filenames frequently use varying delimiter formats (e.g., `dakota.doll`, `dakota_doll`, `dakota-doll`, `Dakota Doll`). Strict string matching misses such files and falls back to broader categories like `JPN/` or `West/`.

This spec introduces **delimiter-flexible string normalization** in the classification matching logic and adds `"Dakota Doll"` to the `artist_folders` configuration.

---

## 2. Goals & Non-Goals

### Goals
1. **Flexible Delimiter Normalization:** Ignore delimiters (`.`, `_`, `-`, spaces) during string comparison so variants of artist/studio names match correctly.
2. **Configuration Update:** Add `"Dakota Doll"` to `artist_folders` in `config/settings.json`.
3. **Backwards Compatibility:** Maintain existing matching priorities (`artist` > `studio` > `genre` > `JPN` > `FC2` > `West`).

### Non-Goals
- Changing the folder creation format (target directories will still use the canonical name configured in `settings.json`, e.g., `"Dakota Doll"`).
- Refactoring unrelated collectors or Transmission RPC components.

---

## 3. Architecture & Detailed Design

### 3.1 Normalization Logic (`src/meridian_x/classify.py`)

A helper function `_normalize_name(name: str) -> str` will be implemented:

```python
import re

def _normalize_name(name: str) -> str:
    """
    Remove all delimiters (dots, underscores, hyphens, whitespace) and convert to lowercase.
    Example: 'Dakota.Doll' -> 'dakotadoll'
             'ohmyholes.25.02.13.dakota.doll.mp4' -> 'ohmyholes250213dakotadollmp4'
    """
    return re.sub(r'[\._\-\s]+', '', name).lower()
```

### 3.2 Matching Rule Update

In `classify_filename(filename: str, config: dict) -> str`:

```python
norm_filename = _normalize_name(filename)

# 1. Artist Matching
for folder in classify.get("artist_folders", []):
    if _normalize_name(folder) in norm_filename:
        return folder

# 2. Studio Matching
for folder in classify.get("studio_folders", []):
    if _normalize_name(folder) in norm_filename:
        return folder
```

### 3.3 Configuration Update (`config/settings.json`)

```json
"classify": {
  "artist_folders": [
    "Dakota Doll"
  ]
}
```

---

## 4. Verification & Testing Plan

1. **Unit Testing (`tests/test_classify.py`):**
   - Test `_normalize_name()` with various string patterns.
   - Verify `classify_filename("ohmyholes.25.02.13.dakota.doll.mp4", config)` returns `"Dakota Doll"`.
   - Verify `classify_filename("dakota_doll_scene_01.mp4", config)` returns `"Dakota Doll"`.
2. **Dry Run Testing:**
   - Run `uv run meridian classify --dry-run` to verify simulated/remote files match expected target folders.

---
