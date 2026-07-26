# Design Spec: Subfolder Organization for Actor Classification (`Actors/<ActorName>`)

**Date:** 2026-07-26  
**Status:** Approved  
**Topic:** Nesting Artist Classification Folders under `Actors/` Subdirectory  

---

## 1. Overview

Currently, artist classification places matching video files directly into top-level actor folders (e.g., `Dakota Doll/`). To maintain cleaner directory hierarchy, all artist-matched files should be placed inside an `Actors/` subfolder (e.g., `Actors/Dakota Doll/`).

---

## 2. Goals & Non-Goals

### Goals
1. **Actors Directory Nesting:** Update `classify_filename()` and `classify_folder()` in `src/meridian_x/classify.py` to route artist matches to `Actors/<ArtistName>/`.
2. **Backward Compatibility & Consistency:** Keep studio, genre, JPN, FC2, and West rules unchanged.
3. **Existing Directory Migration:** Migrate existing top-level actor directories (e.g., `Dakota Doll/`) on the remote media storage into `Actors/Dakota Doll/` if present.

### Non-Goals
- Altering studio or genre classification target directory paths.

---

## 3. Detailed Design

### 3.1 `src/meridian_x/classify.py` Changes

In `classify_filename()`:
```python
# 1. 배우
for folder in classify.get("artist_folders", []):
    if _normalize_name(folder) in f_norm:
        return f"Actors/{folder}"
```

In `classify_folder()`:
```python
# 1. 배우
for folder in classify.get("artist_folders", []):
    if _normalize_name(folder) in f_norm:
        return f"Actors/{folder}"
```

---

## 4. Verification & Testing Plan

1. **Unit Testing (`tests/test_classify.py`):**
   - Update assertions for artist matches to expect `"Actors/Dakota Doll"`.
   - Run `uv run pytest`.
2. **Remote Dry Run / Execution Verification:**
   - Execute `uv run meridian classify` to verify destination paths.

---
