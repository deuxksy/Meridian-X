# Design Spec: Strict Metadata Classification Filtering

**Date:** 2026-08-10  
**Status:** Approved  
**Topic:** Restricting API metadata classification to registered favorite artists and registered studios before defaulting to fallback folders (`JPN` / `West`)

---

## 1. Overview

Currently, `classify_filename_with_metadata` automatically routes any media item with an API-discovered actress/performer to `Actors/<ActressName>`, regardless of whether that actress is in the user's favorited `classify.artists` configuration.

This design specification updates `classify_filename_with_metadata` in `src/meridian_x/classify.py` so that:
1. Media items are routed to `Actors/<ArtistName>` **only if** the API-discovered actress/performer matches an artist in `classify.artists` (or `artist_folders`).
2. If no favorited artist is matched, media items are routed to `<StudioName>` **only if** the API-discovered maker/studio matches a studio in `classify.studios` (or `studio_folders`).
3. If neither a favorited artist nor a registered studio is matched, media items fall back to the default `JPN` or `West` folder without creating new unmanaged actor directories.

---

## 2. Goals & Non-Goals

### Goals
1. **Strict Favorited Artist Check:** Ensure `Actors/` folder routing during metadata lookup applies strictly to registered favorited artists.
2. **Registered Studio Check:** Ensure studio folder routing applies strictly to registered studio mappings.
3. **Fallback Routing:** Unregistered artists and studios default to `JPN` (for JAV media) or `West` (for Western media).
4. **Verification & Unit Tests:** Update and add unit tests in `tests/test_classify.py` to verify strict metadata classification behavior.

### Non-Goals
- Modifying direct filename matching (which already prioritizes registered artists and studios).
- Changing external API metadata fetchers (`fanza.py`, `jav_metadata.py`, `west_metadata.py`).

---

## 3. Detailed Design

### 3.1 Metadata Classification Logic (`src/meridian_x/classify.py`)

Update `classify_filename_with_metadata`:

```python
def classify_filename_with_metadata(filename: str, config: dict, use_metadata: bool = True) -> str:
    dest = classify_filename(filename, config)
    if dest not in ("JPN", "FC2", "West"):
        return dest

    if use_metadata:
        artist_folders = get_artist_folders(config)
        studio_mappings = get_studio_mappings(config)

        if dest == "JPN":
            code = extract_jav_code(filename)
            if code:
                meta = get_jav_metadata(code, config)
                actresses = meta.get("actresses", [])
                makers = meta.get("makers", [])

                # 1. Favorited Actress Check
                for actress in actresses:
                    for folder in artist_folders:
                        if _normalize_name(folder) in _normalize_name(actress):
                            return f"Actors/{folder}"

                # 2. Registered Studio Check
                for maker in makers:
                    m_norm = _normalize_name(maker)
                    for studio, aliases in studio_mappings.items():
                        if _normalize_name(studio) in m_norm or any(_normalize_name(alias) in m_norm for alias in aliases):
                            return studio

        elif dest == "West":
            west_meta = get_west_metadata(filename, config)
            performers = west_meta.get("performers", [])
            studio = west_meta.get("studio")

            # 1. Favorited Performer Check
            for performer in performers:
                for folder in artist_folders:
                    if _normalize_name(folder) in _normalize_name(performer):
                        return f"Actors/{folder}"

            # 2. Registered Studio Check
            if studio:
                s_norm = _normalize_name(studio)
                for st_name, aliases in studio_mappings.items():
                    if _normalize_name(st_name) in s_norm or any(_normalize_name(alias) in s_norm for alias in aliases):
                        return st_name

    return dest
```

---

## 4. Verification Plan

1. **Unit Testing (`tests/test_classify.py`):**
   - Add test `test_classify_filename_with_metadata_favorited_only`:
     - Test that an API-returned favorited actress routes to `Actors/<ArtistName>`.
     - Test that an API-returned non-favorited actress with a registered studio routes to `<StudioName>`.
     - Test that an API-returned non-favorited actress and unregistered studio routes to `JPN` (or `West`).
2. **Test Suite Execution:**
   - Run `uv run pytest tests/test_classify.py -v`.
   - Run `uv run pytest -v`.
