# Design Spec: Update Japanese Artists List in Classification Config

**Date:** 2026-08-10  
**Status:** Approved  
**Topic:** Adding Japanese Artists (`白月さとみ`, `美月結衣`) to `classify.artists.JPN`  

---

## 1. Overview

This design specification updates the Japanese artist list (`classify.artists.JPN`) in `config/settings.json` and `config/settings.json.example`. The existing list contains 35 Japanese artists, including user-favorite artists (`博多彩葉`, `日向由奈`, `白花にあ`, `雛形みくる`). Two new Japanese artists (`白月さとみ`, `美月結衣`) will be added to bring the total count to 37.

---

## 2. Goals & Non-Goals

### Goals
1. **Configuration Update:** Add `白月さとみ` and `美月結衣` to `classify.artists.JPN` in `config/settings.json` and `config/settings.json.example`.
2. **Verification & Testing:** Ensure tests pass and the updated configuration works cleanly with `meridian classify`.

### Non-Goals
- Removing existing artists from `classify.artists.JPN`.
- Modifying non-JPN classification rules or metadata providers.

---

## 3. Detailed Design

### 3.1 Updated Artist List (`classify.artists.JPN`)

The updated array in `config/settings.json` and `config/settings.json.example` will contain 37 artists:
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
11. `水原みその`
12. `夢乃あいか`
13. `逢見リカ`
14. `夕美しおん`
15. `天音まひな`
16. `水卜さくら`
17. `二葉エマ`
18. `羽咲みはる`
19. `小梅えな`
20. `安達夕莉`
21. `清原みゆう`
22. `田野憂`
23. `姫咲はな`
24. `七沢みあ`
25. `小野六花`
26. `桃乃木かな`
27. `松本いちか`
28. `永瀬ゆい`
29. `渚みつき`
30. `工藤ララ`
31. `横宮七海`
32. `沙月恵奈`
33. `柏木こなつ`
34. `栗山莉緒`
35. `河奈亜依`
36. `白月さとみ` (New)
37. `美月結衣` (New)

---

## 4. Verification Plan

1. **Test Suite Execution:**
   - Run `uv run pytest tests/test_classify.py -v`.
   - Run `uv run pytest -v` to ensure full test suite passes.
2. **Dry Run Verification:**
   - Execute `uv run meridian classify --dry-run` to confirm configuration loads without syntax or schema errors.
