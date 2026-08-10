# Strict Metadata Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restrict API metadata classification in `classify_filename_with_metadata` so that `Actors/` routing only applies to registered favorited artists, studio routing only applies to registered studios, and unmanaged media falls back to `JPN` or `West`.

**Architecture:** Update `classify_filename_with_metadata` in `src/meridian_x/classify.py` and update unit tests in `tests/test_classify.py`. Verify with `pytest`.

**Tech Stack:** Python 3.12, pytest

## Global Constraints

- Preserve direct filename matching in `classify_filename`.
- Ensure strict checking against `get_artist_folders(config)` and `get_studio_mappings(config)` during metadata lookup.
- Tests must pass via `uv run pytest`.

---

### Task 1: Update Metadata Classification Logic & Unit Tests

**Files:**
- Modify: `src/meridian_x/classify.py:228-262`
- Modify: `tests/test_classify.py`

**Interfaces:**
- Consumes: `get_artist_folders(config)` and `get_studio_mappings(config)` in `classify.py`.
- Produces: Filtered metadata routing in `classify_filename_with_metadata`.

- [ ] **Step 1: Write failing unit test for strict metadata classification**

Add test cases in `tests/test_classify.py`:

```python
def test_strict_metadata_classification_favorited_only(monkeypatch):
    config = {
        "classify": {
            "artists": {
                "JPN": ["MINAMO"],
                "WEST": ["Dakota Doll"]
            },
            "studios": {
                "JPN": {
                    "Moodyz": ["moodyz"]
                },
                "WEST": {
                    "Vixen": ["vixen"]
                }
            }
        }
    }

    # Mock get_jav_metadata for JPN tests
    def mock_get_jav_meta(code, cfg):
        if code == "SSIS-123":
            return {"actresses": ["MINAMO"], "makers": ["Moodyz"]}
        if code == "SSIS-456":
            return {"actresses": ["Unknown Actress"], "makers": ["Moodyz"]}
        if code == "SSIS-789":
            return {"actresses": ["Unknown Actress"], "makers": ["Unknown Studio"]}
        return {}

    import meridian_x.classify
    monkeypatch.setattr(meridian_x.classify, "get_jav_metadata", mock_get_jav_meta)

    # 1. Favorited actress -> Actors/MINAMO
    assert classify_filename_with_metadata("SSIS-123.mp4", config) == "Actors/MINAMO"
    # 2. Unregistered actress + Registered studio -> Moodyz
    assert classify_filename_with_metadata("SSIS-456.mp4", config) == "Moodyz"
    # 3. Unregistered actress + Unregistered studio -> JPN
    assert classify_filename_with_metadata("SSIS-789.mp4", config) == "JPN"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_classify.py -k test_strict_metadata_classification_favorited_only -v`  
Expected: FAIL (`SSIS-456.mp4` returns `Actors/Unknown Actress` instead of `Moodyz`).

- [ ] **Step 3: Update `classify_filename_with_metadata` in `src/meridian_x/classify.py`**

```python
def classify_filename_with_metadata(filename: str, config: dict, use_metadata: bool = True) -> str:
    """
    파일명 → 목적지 폴더 결정 (외부 API 메타데이터 연동).
    우선순위: 명시적 설정(배우/스튜디오/장르) > API 메타데이터(즐겨찾기 배우 > 등록 스튜디오) > JPN > FC2 > West
    """
    dest = classify_filename(filename, config)
    if dest not in ("JPN", "FC2", "West"):
        return dest

    if use_metadata:
        artist_folders = get_artist_folders(config)
        studio_mappings = get_studio_mappings(config)

        if dest == "JPN":
            code = extract_jav_code(filename)
            if code:
                meta = get_jav_metadata(code, config)
                actresses = meta.get("actresses", [])
                makers = meta.get("makers", [])

                # 1. 즐겨찾기 배우 확인
                for actress in actresses:
                    for folder in artist_folders:
                        if _normalize_name(folder) in _normalize_name(actress):
                            return f"Actors/{folder}"

                # 2. 등록 스튜디오 확인
                for maker in makers:
                    m_norm = _normalize_name(maker)
                    for studio, aliases in studio_mappings.items():
                        if _normalize_name(studio) in m_norm or any(_normalize_name(alias) in m_norm for alias in aliases):
                            return studio

        elif dest == "West":
            west_meta = get_west_metadata(filename, config)
            performers = west_meta.get("performers", [])
            studio = west_meta.get("studio")

            # 1. 즐겨찾기 배우 확인
            for performer in performers:
                for folder in artist_folders:
                    if _normalize_name(folder) in _normalize_name(performer):
                        return f"Actors/{folder}"

            # 2. 등록 스튜디오 확인
            if studio:
                s_norm = _normalize_name(studio)
                for st_name, aliases in studio_mappings.items():
                    if _normalize_name(st_name) in s_norm or any(_normalize_name(alias) in s_norm for alias in aliases):
                        return st_name

    return dest
```

- [ ] **Step 4: Update existing metadata test assertions in `tests/test_classify.py` if needed**

Check existing tests `test_classify_filename_with_metadata_*` in `tests/test_classify.py` and ensure their test configs include the tested actresses/studios so they pass cleanly under the new strict rules.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_classify.py -v`  
Expected: PASS (all tests in test_classify.py pass).

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest tests/ -v`  
Expected: PASS (100% test suite green).

- [ ] **Step 7: Commit**

```bash
git add src/meridian_x/classify.py tests/test_classify.py
git commit -m "feat: restrict metadata classification to favorited artists and registered studios"
```
