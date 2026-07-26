# Design Spec: Add ExxxtraSmall to Studio Folders Classification

**Date:** 2026-07-26  
**Status:** Approved  
**Topic:** Adding ExxxtraSmall Studio to Meridian-X Classification  

---

## 1. Overview

Meridian-X uses a priority-based media classification pipeline (`artist` > `studio` > `genre` > `JPN` > `FC2` > `West`). Previously, files from the studio **ExxxtraSmall** fell back to the generic `West/` category due to missing studio configuration.

This spec adds `"ExxxtraSmall"` to `studio_folders` in `config/settings.json`, taking advantage of the recently implemented delimiter-flexible string normalization (`_normalize_name`).

---

## 2. Goals & Non-Goals

### Goals
1. **Studio Classification:** Automatically classify files matching `ExxxtraSmall` (e.g., `ExxxtraSmall.26.07.18...mp4`, `exxxtra.small...`) into `ExxxtraSmall/` folder.
2. **Configuration Sync:** Update `config/settings.json` and `config/settings.json.example`.
3. **Test Verification:** Add unit tests to `tests/test_classify.py` to ensure zero regressions.

### Non-Goals
- Modifying core classification priorities or refactoring SSH remote operations.

---

## 3. Detailed Design

### 3.1 Configuration Update (`config/settings.json`)

Append `"ExxxtraSmall"` to `classify.studio_folders`:

```json
"classify": {
  "studio_folders": [
    "Vixen",
    "Tiny4k",
    "Wowgirls",
    "Vivthomas",
    "ExxxtraSmall"
  ]
}
```

---

## 4. Verification Plan

1. **Unit Testing (`tests/test_classify.py`):**
   - Add test case verifying `classify_filename("ExxxtraSmall.26.07.18.Remi.Raw.And.Alli.Skye.XXX.1080p.MP4-WRB[XC].mp4", config)` returns `"ExxxtraSmall"`.
   - Verify `test_exxxtrasmall_in_settings()` checks `config/settings.json`.
2. **Execution Check:**
   - Run `uv run pytest` to ensure all 20+ tests pass cleanly.

---
