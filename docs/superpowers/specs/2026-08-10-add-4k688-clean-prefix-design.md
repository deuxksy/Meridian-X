# Design Spec: Add `4k688.com@` to Clean Prefixes Config

**Date:** 2026-08-10  
**Status:** Approved  
**Topic:** Adding `4k688.com@` to `classify.clean_prefixes` in configuration

---

## 1. Overview

This design specification adds `"4k688.com@"` to the `classify.clean_prefixes` configuration array in `config/settings.json` and `config/settings.json.example`. This ensures that `meridian tidy` automatically detects and strips `4k688.com@` prefixes from filenames via SSH renaming.

---

## 2. Goals & Non-Goals

### Goals
1. **Configuration Update:** Add `"4k688.com@"` to `classify.clean_prefixes` in `config/settings.json` and `config/settings.json.example`.
2. **Test Suite Verification:** Add unit tests to `tests/test_tidy.py` verifying that `clean_filenames` correctly handles `"4k688.com@"` prefixes.
3. **Execution Verification:** Ensure `uv run pytest` passes.

### Non-Goals
- Changing the `clean_filenames` SSH renaming logic in `src/meridian_x/tidy.py`.

---

## 3. Detailed Design

### 3.1 Configuration Update

Update `classify.clean_prefixes` in `config/settings.json` and `config/settings.json.example`:

```json
"clean_prefixes": [
  "hhd800.com@",
  "4k688.com@"
]
```

---

## 4. Verification Plan

1. **Unit Testing (`tests/test_tidy.py`):**
   - Verify `clean_filenames` handles `"4k688.com@"` prefix as expected.
2. **Test Suite Execution:**
   - Run `uv run pytest tests/test_tidy.py -v`.
   - Run `uv run pytest -v`.
