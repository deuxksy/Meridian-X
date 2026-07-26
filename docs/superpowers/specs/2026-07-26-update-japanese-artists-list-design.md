# Design Spec: Add Japanese Artists to Classification List

**Date:** 2026-07-26  
**Status:** Approved  
**Topic:** Adding Japanese Artists to `artist_folders` Configuration  

---

## 1. Overview

To organize private media collections under actor-specific directories (`Actors/<ActorName>/`), this spec appends specified Japanese artist names to `artist_folders` in `config/settings.json`.

---

## 2. Goals & Non-Goals

### Goals
1. **Configuration Update:** Append Japanese artist names (`MINAMO`, `Rena Miyashita`, `Rima Arai`, `Umi Yatsugake`, `佐野葉月`, `博多彩葉`, `川越にこ`, `日向由奈`, `白花にあ`, `雛形みくる`) to `artist_folders` in `config/settings.json` and `config/settings.json.example`.
2. **Actor Subfolder Routing:** Ensure matched files are automatically routed to `Actors/<ArtistName>/`.
3. **Test Suite Verification:** Add unit tests to `tests/test_classify.py` and ensure `uv run pytest` passes.

### Non-Goals
- Altering existing non-artist classification priorities.

---

## 3. Detailed Design

### 3.1 Configuration Update (`config/settings.json`)

Append the following artist names to `classify.artist_folders`:
- `Dakota Doll` (existing)
- `MINAMO`
- `Rena Miyashita`
- `Rima Arai`
- `Umi Yatsugake`
- `佐野葉月`
- `博多彩葉`
- `川越にこ`
- `日向由奈`
- `白花にあ`
- `雛形みくる`

---

## 4. Verification Plan

1. **Unit Testing (`tests/test_classify.py`):**
   - Verify `classify_filename("MINAMO_scene_01.mp4", config)` returns `"Actors/MINAMO"`.
   - Verify all added artists are present in `artist_folders`.
2. **Execution Check:**
   - Run `uv run pytest`.

---
