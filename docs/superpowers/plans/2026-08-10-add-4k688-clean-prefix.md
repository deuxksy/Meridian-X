# Add `4k688.com@` Clean Prefix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `"4k688.com@"` to `classify.clean_prefixes` in `config/settings.json` and `config/settings.json.example`, and add unit tests to verify filename prefix cleaning.

**Architecture:** Update JSON config files and add tests in `tests/test_tidy.py`. Verify with `pytest` and `meridian tidy --dry-run`.

**Tech Stack:** Python 3.12, pytest, JSON

## Global Constraints

- Preserve existing `clean_prefixes` entries (`hhd800.com@`).
- Ensure `config/settings.json` and `config/settings.json.example` have matching `clean_prefixes`.
- Tests must pass via `uv run pytest`.

---

### Task 1: Update `clean_prefixes` Configuration and Add Tests

**Files:**
- Modify: `config/settings.json`
- Modify: `config/settings.json.example`
- Modify: `tests/test_tidy.py`

**Interfaces:**
- Consumes: `"4k688.com@"` prefix requirement from design spec.
- Produces: Updated `classify.clean_prefixes` in config files and unit test in `test_tidy.py`.

- [ ] **Step 1: Write test for `clean_prefixes` in settings and tidy logic**

Add `test_clean_prefixes_includes_4k688` in `tests/test_tidy.py`:

```python
def test_clean_prefixes_includes_4k688():
    from meridian_x.core import load_config
    config = load_config("config/settings.json")
    prefixes = config.get("classify", {}).get("clean_prefixes", [])
    assert "hhd800.com@" in prefixes
    assert "4k688.com@" in prefixes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tidy.py -k test_clean_prefixes_includes_4k688 -v`  
Expected: FAIL (`4k688.com@` not in `prefixes`).

- [ ] **Step 3: Update `config/settings.json` and `config/settings.json.example`**

Add `"4k688.com@"` to `classify.clean_prefixes` array in `config/settings.json`:

```json
    "clean_prefixes": [
      "hhd800.com@",
      "4k688.com@"
    ]
```

And update `config/settings.json.example` to match.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tidy.py -k test_clean_prefixes_includes_4k688 -v`  
Expected: PASS

- [ ] **Step 5: Run full test suite and verify tidy CLI dry-run**

Run: `uv run pytest tests/ -v`  
Run: `uv run meridian tidy --dry-run`  
Expected: PASS and clean dry-run output.

- [ ] **Step 6: Commit**

```bash
git add config/settings.json.example tests/test_tidy.py
git commit -m "feat: add 4k688.com@ to clean_prefixes configuration"
```
