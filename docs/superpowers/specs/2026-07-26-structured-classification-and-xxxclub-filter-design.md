# Design Spec: Structured Classification (WEST/JPN Artists & Studios) and XXXClub Whitelist Filter

**Date:** 2026-07-26  
**Status:** Approved  
**Topic:** Restructuring Classification Config (`artists.WEST/JPN` & `studios.WEST/JPN`), Updating Studio Networks & Adding Actors, and Filtering XXXClub RSS Collection  

---

## 1. Overview

Meridian-X classification and RSS collection config is being restructured for better region-based control and network organization:
1. **Regional Structuring:** `artists` and `studios` in `config/settings.json` are now split into `WEST` and `JPN` sub-objects.
2. **Studio Networks Integration:** Studio aliases are configured for major networks (e.g., `Vixen`, `Nubile`, `TeamSkeet`, `MetArtX`, `FTV`, etc.).
3. **Actor Updates:** `artists.WEST` contains preferred western actors (`Dakota Doll`, `Molli Little`, `Lulu Sweety`, `Kiki Cali`, `Coco Lovelock`, `Remi Raw`, `Lola Valentine`, `Blake Blossom`). `artists.JPN` contains configured Japanese actors.
4. **XXXClub Whitelist Collection Filter:** `sources/xxxclub.py` uses `artists.WEST` + `studios.WEST` keywords to selectively collect only western whitelisted torrents from RSS feeds (excluding Japanese artists/studios).

---

## 2. Goals & Non-Goals

### Goals
1. **Config Restructuring:** Update `config/settings.json` and `config/settings.json.example` to use structured `artists.WEST/JPN` and `studios.WEST/JPN` dicts. Deprecate `genres` (cleared to `{}`).
2. **Classification Logic Adaptation (`src/meridian_x/classify.py`):** Update `classify_filename()`, `classify_folder()`, and `get_artist_folders()` / `get_studio_mappings()` helpers to seamlessly support structured dicts while preserving priority:
   `artists` (`Actors/<ActorName>/`) > `studios` (`<StudioName>/`) > JAV (`JPN/`) > FC2 (`FC2/`) > West (`West/`).
3. **XXXClub Filter (`src/meridian_x/sources/xxxclub.py`):** Update `is_whitelisted_title()` to build matching keywords specifically from `artists.WEST` and `studios.WEST`.
4. **Test Suite Verification:** Update and add unit tests across `tests/test_classify.py` and `tests/test_collect.py`.

### Non-Goals
- Modifying non-XXXClub RSS collection behavior (e.g. `onejav`).

---

## 3. Detailed Design

### 3.1 Configuration Structure (`config/settings.json`)

```json
"classify": {
  "artists": {
    "WEST": [
      "Dakota Doll",
      "Molli Little",
      "Lulu Sweety",
      "Kiki Cali",
      "Coco Lovelock",
      "Remi Raw",
      "Lola Valentine",
      "Blake Blossom"
    ],
    "JPN": [
      "MINAMO",
      "Rena Miyashita",
      "Rima Arai",
      "Umi Yatsugake",
      "佐野葉月",
      "博多彩葉",
      "川越にこ",
      "日向由奈",
      "白花にあ",
      "雛形みくる"
    ]
  },
  "studios": {
    "WEST": {
      "Vixen": ["vixen", "tushy", "blacked", "slayed", "deeper"],
      "Nubile": [
        "nubile",
        "nubilefilms",
        "nubiles",
        "fit18",
        "stepsiblings",
        "sisswap",
        "sheseducedme",
        "mywifeshotfriend",
        "myfriendshotmom",
        "mysistershotfriend",
        "pervtherapy",
        "sweetsinner"
      ],
      "TeamSkeet": ["teamskeet", "teamskeetsingles", "tiny4k", "rim4k", "rkprime", "povmasters"],
      "MetArtX": ["metartx", "metart", "sexart"],
      "X-Art": ["xart", "x-art"],
      "TheLifeErotic": ["thelifeerotic"],
      "JoyMii": ["joymii"],
      "Wowgirls": ["wowgirls"],
      "ExxxtraSmall": ["exxxtrasmall"],
      "AngelsLove": ["angelslove"],
      "UltraFilms": ["ultrafilms"],
      "ALSScan": ["alsscan"],
      "FTV": ["ftv", "ftvgirls", "ftvmilfs"]
    },
    "JPN": {}
  }
},
"genres": {}
```

### 3.2 Classification Helper Updates (`src/meridian_x/classify.py`)

- `get_artist_folders(config, region=None) -> list[str]`:
  If `classify.artists` is a dict, returns artists for `region` (`"WEST"`, `"JPN"`) or all artists if `region is None`. Supports fallback to legacy `artist_folders` list.
- `get_studio_mappings(config, region=None) -> dict[str, list[str]]`:
  If `classify.studios` is a dict, returns `{StudioCanonicalName: [aliases...]}` for specified region or all regions. Supports fallback to legacy `studio_folders` list.

### 3.3 XXXClub Filtering (`src/meridian_x/sources/xxxclub.py`)

- `is_whitelisted_title(title: str, config: dict) -> bool`:
  Builds keywords using `get_artist_folders(config, region="WEST")` and `get_studio_mappings(config, region="WEST")`. Returns `True` if normalized title matches any western artist or studio alias.

---

## 4. Verification Plan

1. **Unit Testing:**
   - Run `uv run pytest` to ensure all tests pass cleanly.
2. **CLI Dry Run Check:**
   - Execute `uv run meridian transmission --source xxxclub --dry-run` to confirm western-only whitelisted RSS items are collected.
   - Execute `uv run meridian classify --dry-run` to confirm correct priority and destination folder routing.

---
