# Design Spec: Artist and Studio Flexible Classification in Meridian-X

**Date:** 2026-07-26  
**Status:** Approved (Reviewed by Codex)  
**Topic:** Flexible Delimiter Matching for Artist and Studio Classification & Adding Dakota Doll  

---

## 1. Overview

Meridian-X media classifier standardizes file organization based on priority rules (`artist` > `studio` > `genre` > `JPN` > `FC2` > `West`). However, filenames frequently use varying delimiter formats (e.g., `dakota.doll`, `dakota_doll`, `dakota-doll`, `Dakota Doll`). Strict string matching misses such files and falls back to broader categories like `JPN/` or `West/`.

This spec introduces **delimiter-flexible string normalization** in the classification matching logic (both filenames and multi-part folders) and appends `"Dakota Doll"` to `artist_folders` in `config/settings.json`.

---

## 2. Goals & Non-Goals

### Goals
1. **Flexible Delimiter Normalization:** Ignore delimiters (`.`, `_`, `-`, spaces) during string comparison in both `classify_filename()` and `classify_folder()` so variants of artist/studio names match correctly.
2. **Configuration Update:** Append `"Dakota Doll"` to `artist_folders` in `config/settings.json` (and `config/settings.json.example` for reference).
3. **Backwards Compatibility & Safety:** Maintain existing matching priorities (`artist` > `studio` > `genre` > `JPN` > `FC2` > `West`) without causing regressions on existing studio or JPN/FC2 patterns.

### Non-Goals
- Changing target folder creation naming format (canonical names configured in `settings.json` like `"Dakota Doll"` are preserved).
- Refactoring collector logic or Transmission RPC components.

---

## 3. Architecture & Detailed Design

### 3.1 Normalization Helper (`src/meridian_x/classify.py`)

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

### 3.2 Matching Rule Update (`classify_filename` & `classify_folder`)

In `classify_filename(filename: str, config: dict) -> str` and `classify_folder(folder_name: str, config: dict) -> str`:

```python
norm_name = _normalize_name(name)

# 1. Artist Matching
for folder in classify.get("artist_folders", []):
    if _normalize_name(folder) in norm_name:
        return folder

# 2. Studio Matching
for folder in classify.get("studio_folders", []):
    if _normalize_name(folder) in norm_name:
        return folder
```

### 3.3 Configuration Update (`config/settings.json`)

Append `"Dakota Doll"` to `artist_folders`:

```json
"classify": {
  "artist_folders": [
    "Dakota Doll"
  ]
}
```

---

## 4. Verification & Testing Plan

1. **New Unit Tests (`tests/test_classify.py`):**
   - Create `tests/test_classify.py` to test `_normalize_name()` and matching functions.
   - Verify `classify_filename("ohmyholes.25.02.13.dakota.doll.mp4", config)` returns `"Dakota Doll"`.
   - Verify `classify_filename("dakota_doll_scene_01.mp4", config)` returns `"Dakota Doll"`.
   - Verify `classify_folder("dakota.doll.collection", config)` returns `"Dakota Doll"`.
   - **Regression Check:** Verify existing Studio matching (`Vixen`, `Wowgirls`), `JPN` patterns (`GVH-864`), `FC2` patterns, and fallback (`West`) operate without disruption.
2. **Dry Run Testing:**
   - Execute `uv run meridian classify --dry-run` and `pytest` to confirm all test suites pass cleanly.

---

