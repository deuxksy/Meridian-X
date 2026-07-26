# Add ExxxtraSmall Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `"ExxxtraSmall"` studio to `studio_folders` in configuration files and verify string-normalized classification with unit tests.

**Architecture:** Update `config/settings.json` and `config/settings.json.example` and add unit test cases in `tests/test_classify.py`.

**Tech Stack:** Python 3.12, `pytest`, `uv`.

## Global Constraints

- Preserve existing matching logic and priority order.
- Maintain test suite integrity.

---

### Task 1: Add ExxxtraSmall to Settings and Write Test Verification

**Files:**
- Modify: `config/settings.json`
- Modify: `config/settings.json.example`
- Modify: `tests/test_classify.py`

- [ ] **Step 1: Write failing test in `tests/test_classify.py`**

Append to `tests/test_classify.py`:

```python
def test_exxxtrasmall_studio_classification():
    config = load_config("config/settings.json")
    filename = "ExxxtraSmall.26.07.18.Remi.Raw.And.Alli.Skye.XXX.1080p.MP4-WRB[XC].mp4"
    assert "ExxxtraSmall" in config.get("classify", {}).get("studio_folders", [])
    assert classify_filename(filename, config) == "ExxxtraSmall"
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/test_classify.py -k test_exxxtrasmall_studio_classification`
Expected: FAIL (`AssertionError`)

- [ ] **Step 3: Update `config/settings.json` and `config/settings.json.example`**

Add `"ExxxtraSmall"` to `classify.studio_folders` in both `config/settings.json` and `config/settings.json.example`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest`
Expected: PASS (all 20+ tests pass)

- [ ] **Step 5: Commit**

```bash
git add config/settings.json config/settings.json.example tests/test_classify.py
git commit -m "feat: add ExxxtraSmall to studio_folders classification"
```
