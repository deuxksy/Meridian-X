# Update JPN Favorite Actors List Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up and update `classify.artists.JPN` in `config/settings.json` and `config/settings.json.example` to strictly contain the user's 24 favorite Japanese actors and update corresponding tests.

**Architecture:** Update JSON config files (`config/settings.json`, `config/settings.json.example`) and unit tests (`tests/test_classify.py`). Verify with `pytest` and `meridian classify --dry-run`.

**Tech Stack:** Python 3.12, pytest, JSON

## Global Constraints

- Keep existing JSON structure in `config/settings.json` and `config/settings.json.example`.
- Ensure all 24 favorite JPN actors are present in `classify.artists.JPN`.
- Tests must pass via `uv run pytest`.

---

### Task 1: Update Configuration Files (`config/settings.json` & `config/settings.json.example`)

**Files:**
- Modify: `config/settings.json:85-121`
- Modify: `config/settings.json.example:65-76`

**Interfaces:**
- Consumes: 24 favorite JPN actors list from design spec.
- Produces: Updated `classify.artists.JPN` in config files.

- [ ] **Step 1: Write test for updating JPN actors list in settings**

Add `test_japanese_artists_favorite_list` in `tests/test_classify.py`:

```python
def test_japanese_artists_favorite_list():
    config = load_config("config/settings.json")
    expected = [
        "MINAMO",
        "Rena Miyashita",
        "Rima Arai",
        "Umi Yatsugake",
        "佐野葉月",
        "博多彩葉",
        "川越にこ",
        "日向由奈",
        "白花にあ",
        "雛形みくる",
        "白月さとみ",
        "美月結衣",
        "来栖唯希",
        "篠宮るい",
        "彩月七緒",
        "桜ゆの",
        "赤名いと",
        "白石透羽",
        "倉木華",
        "Ranran Fujii",
        "柴崎はる",
        "瀬戸環奈",
        "松永あかり",
        "岬さくら",
    ]
    actual_jpn = config.get("classify", {}).get("artists", {}).get("JPN", [])
    assert actual_jpn == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_classify.py -k test_japanese_artists_favorite_list -v`  
Expected: FAIL (list mismatch).

- [ ] **Step 3: Update `config/settings.json` and `config/settings.json.example`**

Update `classify.artists.JPN` array in `config/settings.json`:

```json
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
        "雛形みくる",
        "白月さとみ",
        "美月結衣",
        "来栖唯希",
        "篠宮るい",
        "彩月七緒",
        "桜ゆの",
        "赤名いと",
        "白石透羽",
        "倉木華",
        "Ranran Fujii",
        "柴崎はる",
        "瀬戸環奈",
        "松永あかり",
        "岬さくら"
      ]
```

And update `config/settings.json.example` to match.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_classify.py -k test_japanese_artists_favorite_list -v`  
Expected: PASS

- [ ] **Step 5: Run full test suite and verify classify CLI dry-run**

Run: `uv run pytest tests/ -v`  
Run: `uv run meridian classify --dry-run`  
Expected: PASS and clean dry-run output.

- [ ] **Step 6: Commit**

```bash
git add config/settings.json config/settings.json.example tests/test_classify.py
git commit -m "feat: update JPN favorite actors list to 24 actors"
```
