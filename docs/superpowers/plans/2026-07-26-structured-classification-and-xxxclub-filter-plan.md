# Structured Classification and XXXClub Whitelist Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure classification settings (`artists.WEST/JPN` & `studios.WEST/JPN`), update `classify.py` helpers and logic to support structured config, update `xxxclub.py` to filter using WEST keywords only, and verify with tests and dry-run CLI executions.

**Architecture:** Update `config/settings.json`, update `src/meridian_x/classify.py`, update `src/meridian_x/sources/xxxclub.py`, and update test suite.

**Tech Stack:** Python 3.12, `pytest`, `uv`.

## Global Constraints

- Artists/studios config format must support structured dicts (`WEST`/`JPN`) as well as legacy list fallbacks.
- Priority must remain: `artists` (`Actors/<ActorName>/`) > `studios` (`<StudioName>/`) > JAV (`JPN/`) > FC2 (`FC2/`) > West (`West/`).
- `xxxclub` selective collection must use `WEST` artists + `WEST` studio keywords.

---

### Task 1: Update Configuration and Classification Module Helper Functions

**Files:**
- Modify: `config/settings.json`
- Modify: `config/settings.json.example`
- Modify: `src/meridian_x/classify.py`
- Modify: `tests/test_classify.py`

- [ ] **Step 1: Write failing unit test in `tests/test_classify.py`**

Add tests to `tests/test_classify.py`:

```python
def test_structured_artists_and_studios_classification():
    config = {
        "classify": {
            "artists": {
                "WEST": ["Dakota Doll", "Molli Little"],
                "JPN": ["MINAMO"]
            },
            "studios": {
                "WEST": {
                    "Vixen": ["vixen", "tushy", "blacked"],
                    "TeamSkeet": ["teamskeet", "tiny4k"]
                }
            }
        }
    }
    # Artist priority
    assert classify_filename("ExxxtraSmall.Dakota.Doll.mp4", config) == "Actors/Dakota Doll"
    # Studio alias matching
    assert classify_filename("tushy.26.07.18.Remi.Raw.mp4", config) == "Vixen"
    assert classify_filename("tiny4k.26.07.18.mp4", config) == "TeamSkeet"
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/test_classify.py -k test_structured_artists_and_studios_classification`
Expected: FAIL

- [ ] **Step 3: Update `config/settings.json` & `config/settings.json.example` and `src/meridian_x/classify.py`**

Update `config/settings.json` and `config/settings.json.example` with structured `artists.WEST/JPN` and `studios.WEST/JPN`.

Update `src/meridian_x/classify.py`:
- Implement `get_artist_folders(config: dict, region: str | None = None) -> list[str]`.
- Implement `get_studio_mappings(config: dict, region: str | None = None) -> dict[str, list[str]]`.
- Update `classify_filename()` and `classify_folder()` to check `artists` first (returning `Actors/<ArtistName>`), then `studios` (checking canonical names and aliases).

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_classify.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/meridian_x/classify.py config/settings.json config/settings.json.example tests/test_classify.py
git commit -m "feat: restructure classification config with WEST/JPN artists and studio network aliases"
```

---

### Task 2: Update XXXClub Filter for WEST-only Whitelist and End-to-End Verification

**Files:**
- Modify: `src/meridian_x/sources/xxxclub.py`
- Modify: `tests/test_collect.py`

- [ ] **Step 1: Write failing unit test in `tests/test_collect.py`**

Update `tests/test_collect.py`:

```python
def test_is_whitelisted_title_west_only():
    config = {
        "classify": {
            "artists": {
                "WEST": ["Dakota Doll", "Molli Little"],
                "JPN": ["MINAMO"]
            },
            "studios": {
                "WEST": {
                    "Vixen": ["vixen", "tushy"],
                    "TeamSkeet": ["tiny4k"]
                }
            }
        }
    }
    # Matches WEST artist or WEST studio
    assert is_whitelisted_title("Dakota.Doll.OhMyHoles.mp4", config) is True
    assert is_whitelisted_title("Tushy.26.06.28.Alina.Lopez.mp4", config) is True
    # JPN artist is EXCLUDED from xxxclub whitelist
    assert is_whitelisted_title("MINAMO.FNS-237.mp4", config) is False
    # Unmatched title
    assert is_whitelisted_title("UnknownStudio.26.07.18.Random.mp4", config) is False
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/test_collect.py -k test_is_whitelisted_title_west_only`
Expected: FAIL

- [ ] **Step 3: Update `is_whitelisted_title()` in `src/meridian_x/sources/xxxclub.py`**

In `src/meridian_x/sources/xxxclub.py`, use `get_artist_folders(config, region="WEST")` and `get_studio_mappings(config, region="WEST")` to build whitelist keywords.

- [ ] **Step 4: Run test suite to verify pass**

Run: `uv run pytest`
Expected: PASS (all tests pass)

- [ ] **Step 5: Commit**

```bash
git add src/meridian_x/sources/xxxclub.py tests/test_collect.py
git commit -m "feat: restrict XXXClub whitelist filter to WEST artists and studios"
```
