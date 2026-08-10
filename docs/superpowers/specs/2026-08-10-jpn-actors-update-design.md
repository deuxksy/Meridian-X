# Design Spec: Update Japanese Artists List to Favorite Artists Only

**Date:** 2026-08-10  
**Status:** Approved  
**Topic:** Clean up `classify.artists.JPN` to contain only user's favorite Japanese actors (15 actors)

---

## 1. Overview

This design specification updates `classify.artists.JPN` in `config/settings.json` and `config/settings.json.example`. The existing configuration contains 35 Japanese artists accumulated over time. The user requested to clean up the list to contain strictly their 15 favorite Japanese actors.

---

## 2. Goals & Non-Goals

### Goals
1. **Configuration Cleanup:** Set `classify.artists.JPN` in `config/settings.json` and `config/settings.json.example` to the exact 15 favorite actors provided by the user.
2. **Verification & Testing:** Ensure tests pass and the updated configuration works cleanly with `meridian classify`.

### Non-Goals
- Modifying `classify.artists.WEST` or studio configurations.

---

## 3. Detailed Design

### 3.1 Updated Artist List (`classify.artists.JPN`)

The updated array in `config/settings.json` and `config/settings.json.example` will contain strictly the following 15 actors:

1. `MINAMO`
2. `Rena Miyashita`
3. `Rima Arai`
4. `Umi Yatsugake`
5. `佐野葉月`
6. `博多彩葉`
7. `川越にこ`
8. `日向由奈`
9. `白花にあ`
10. `雛形みくる`
11. `白月さとみ`
12. `美月結衣`
13. `来栖唯希`
14. `篠宮るい`
15. `彩月七緒`

---

## 4. Verification Plan

1. **Test Suite Execution:**
   - Run `uv run pytest tests/test_classify.py -v`.
   - Run `uv run pytest -v` to ensure full test suite passes.
2. **Dry Run Verification:**
   - Execute `uv run meridian classify --dry-run` to confirm configuration loads without syntax or schema errors.
