# Update Japanese Artists List Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Append Japanese artist list (`MINAMO`, `Rena Miyashita`, `Rima Arai`, `Umi Yatsugake`, `佐野葉月`, `博多彩葉`, `川越にこ`, `日向由奈`, `白花にあ`, `雛形みくる`) to `classify.artist_folders` in configuration files and verify classification with unit tests.

**Architecture:** Update `config/settings.json` and `config/settings.json.example`, add unit tests in `tests/test_classify.py`, and verify with `pytest`.

**Tech Stack:** Python 3.12, `pytest`, `uv`.

## Global Constraints

- Artist matched folders MUST be nested inside `Actors/` (e.g. `Actors/MINAMO`).
- Maintain test suite integrity.

---

### Task 1: Update Configuration and Unit Tests for Japanese Artists

**Files:**
- Modify: `config/settings.json`
- Modify: `config/settings.json.example`
- Modify: `tests/test_classify.py`

- [ ] **Step 1: Write failing test in `tests/test_classify.py`**

Append to `tests/test_classify.py`:

```python
def test_japanese_artists_classification():
    config = load_config("config/settings.json")
    artists = [
        "MINAMO", "Rena Miyashita", "Rima Arai", "Umi Yatsugake",
        "佐野葉月", "博多彩葉", "川越にこ", "日向由奈", "白花にあ", "雛形みくる"
    ]
    for artist in artists:
        assert artist in config.get("classify", {}).get("artist_folders", [])
    assert classify_filename("MINAMO_special_01.mp4", config) == "Actors/MINAMO"
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/test_classify.py -k test_japanese_artists_classification`
Expected: FAIL (`AssertionError`)

- [ ] **Step 3: Update `config/settings.json` and `config/settings.json.example`**

Append the 10 Japanese artist names to `classify.artist_folders` in both `config/settings.json` and `config/settings.json.example`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest`
Expected: PASS (all 20+ tests pass)

- [ ] **Step 5: Commit**

```bash
git add config/settings.json config/settings.json.example tests/test_classify.py
git commit -m "feat: add Japanese artists to artist_folders classification list"
```
