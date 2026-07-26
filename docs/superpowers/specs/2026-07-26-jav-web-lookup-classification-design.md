# Design Spec: JAV Web Lookup & Actor Classification in Meridian-X

**Date:** 2026-07-26  
**Status:** Approved  
**Topic:** Automating Actor Identification for JPN Files via Web Lookup  

---

## 1. Overview

Files inside the `JPN/` directory are typically named by maker code numbers (e.g., `ABF-364.mp4`, `FNS-237.mp4`) without explicit actress names in their filenames. To classify these files into `Actors/<ActorName>/` subdirectories, Meridian-X will perform web lookups for JAV codes to identify performing actresses and match them against configured `artist_folders`.

---

## 2. Goals & Non-Goals

### Goals
1. **JAV Lookup Module (`src/meridian_x/jav_lookup.py`):** Provide `lookup_jav_actresses(code: str) -> list[str]` to fetch cast information for JAV codes (e.g. searching OneJAV or web endpoints).
2. **Remote JPN Re-classification (`src/meridian_x/classify.py`):** Add functionality to inspect files in the remote `JPN/` folder, lookup their actresses, and move matched files to `Actors/<ArtistName>/`.
3. **CLI Integration:** Add `--lookup-jav` flag or subcommand to `meridian classify`.
4. **Test Coverage:** Unit test JAV code extraction and actress matching logic.

### Non-Goals
- Modifying non-JPN file rules or non-artist classifications.

---

## 3. Detailed Design

### 3.1 `src/meridian_x/jav_lookup.py`

```python
import re
import requests
from bs4 import BeautifulSoup

def extract_jav_code(filename: str) -> str | None:
    """Extract standard JAV code from filename (e.g., 'ABF-364.mp4' -> 'ABF-364')."""
    match = re.search(r"([A-Z0-9]{3,7}-\d{2,5})", filename, re.IGNORECASE)
    return match.group(1).upper() if match else None

def lookup_jav_actresses(code: str) -> list[str]:
    """Fetch actress names for a given JAV code via web lookup (e.g., OneJAV search)."""
    # Query onejav.com search endpoint
    # Parse HTML for actress tags/links
    # Return list of actress names
```

### 3.2 Classification Logic Integration (`src/meridian_x/classify.py`)

In `classify_remote_jpn_files(config: dict, dry_run: bool = False)`:
- List files in remote `JPN/` directory.
- For each file, extract JAV code.
- Query `lookup_jav_actresses(code)`.
- Compare fetched actress names with `classify.artist_folders` using `_normalize_name()`.
- If matched with artist `Folder`, target destination becomes `Actors/Folder`.
- Move file via SSH `mv`.

---

## 4. Verification & Testing Plan

1. **Unit Testing (`tests/test_jav_lookup.py`):**
   - Test `extract_jav_code("ABF-364.mp4")` returns `"ABF-364"`.
   - Test lookup parsing with mock HTTP response.
2. **Integration / Dry Run Verification:**
   - Execute `uv run meridian classify --lookup-jav --dry-run` to view match proposals.

---
