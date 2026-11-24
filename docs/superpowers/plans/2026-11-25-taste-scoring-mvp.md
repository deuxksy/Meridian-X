# Taste Scoring MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement retention-driven taste scoring (`score_taste`) with DB snapshot storage in `meridian report` and shadow ranking + optional `min_score` cutoff in `meridian transmission`.

**Architecture:** `meridian report` persists per-actor and per-studio kept file counts into a new `retention_stats` SQLite table in `MeridianDB`. `core.score_taste()` computes `(score, reasons)` from `config.classify` (artists/aliases/studios) and `retention_stats` using a log2 bonus formula. `collect._filter_and_send()` loads the snapshot once per run, stably sorts `new_items` by descending score, logs score/reasons, and optionally skips items below `collection.scoring.min_score` (default `0.0`).

**Tech Stack:** Python 3.12+, SQLite (`sqlite3`), pytest (`uv run pytest`).

**Spec:** `docs/superpowers/specs/2026-11-25-taste-scoring-design.md`

## Global Constraints
- `meridian favorite` MUST NOT apply taste scoring or `min_score` cutoff.
- `collect` MUST NOT perform live SSH calls for scoring; read `retention_stats` from `MeridianDB` only.
- Missing or empty `retention_stats` MUST gracefully fall back to base registration scores (`+30.0` actor, `+10.0` studio/FC2) without errors.
- Default `collection.scoring.min_score` is `0.0` (shadow ranking + logging only, zero filtering).

## Review Focus
- Empty or missing `retention_stats` table on first run: `score_taste()` still returns base scores (`30.0` / `10.0`) and `collect` succeeds.
- Tie-breaking in `collect._filter_and_send()`: items with equal score preserve original RSS order (Python stable sort).
- `artist_aliases` matching: Japanese alias in title (e.g. `宮下玲奈`) resolves to canonical actor (`Rena Miyashita`) and looks up `retention_stats["actor"]["Rena Miyashita"]`.
- `min_score > 0` cutoff: items strictly below `min_score` are skipped before `resolve()` and not added to Transmission.
- `scoring.enabled = False`: bypasses sorting and cutoff, preserving original `new_items[:remaining]` behavior.

---

### Task 1: Retention Snapshot Storage (`db.py` + `report.py`)

**Files:**
- Modify: `src/meridian_x/db.py`
- Modify: `src/meridian_x/report.py`
- Test: `tests/test_db.py`, `tests/test_report.py`

**Interfaces:**
- Consumes: `MeridianDB.get_connection()`
- Produces:
  - `MeridianDB.save_retention_stats(self, actor_counts: dict[str, int], studio_counts: dict[str, int]) -> None`
  - `MeridianDB.get_retention_stats(self) -> dict[str, dict[str, int]]` (returns `{"actor": {...}, "studio": {...}}`)

- [ ] **Step 1: Write failing tests in `tests/test_db.py` and `tests/test_report.py`**

```python
# tests/test_db.py
def test_retention_stats_roundtrip(tmp_path):
    db = MeridianDB(tmp_path / "test.db")
    assert db.get_retention_stats() == {"actor": {}, "studio": {}}
    db.save_retention_stats({"Kubera Fortuna": 26}, {"Wowgirls": 58, "FC2": 62})
    assert db.get_retention_stats() == {
        "actor": {"Kubera Fortuna": 26},
        "studio": {"Wowgirls": 58, "FC2": 62},
    }
    # Replace semantics on second save
    db.save_retention_stats({"MINAMO": 8}, {"FC2": 63})
    assert db.get_retention_stats() == {
        "actor": {"MINAMO": 8},
        "studio": {"FC2": 63},
    }
```

And in `tests/test_report.py::test_retention_status`, assert `db.get_retention_stats()` contains `"MINAMO": 1` and `"FC2": 1`.

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/test_db.py::test_retention_stats_roundtrip tests/test_report.py::test_retention_status -v`
Expected: FAIL (`AttributeError: 'MeridianDB' object has no attribute 'get_retention_stats'`)

- [ ] **Step 3: Implement `retention_stats` table & CRUD in `src/meridian_x/db.py` and save hook in `src/meridian_x/report.py`**
- Add `CREATE TABLE IF NOT EXISTS retention_stats (entity_type TEXT NOT NULL, name TEXT NOT NULL, kept_count INTEGER NOT NULL, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (entity_type, name))` in `MeridianDB.init_db()`.
- Implement `save_retention_stats` (DELETE + executemany inside a single transaction) and `get_retention_stats` in `MeridianDB`.
- Call `db.save_retention_stats(dict(actor_counts), dict(studio_counts))` at the end of `report.retention_status()`.

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_db.py tests/test_report.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/meridian_x/db.py src/meridian_x/report.py tests/test_db.py tests/test_report.py
git commit -m "feat(db,report): persist retention stats snapshot in meridian.db"
```

---

### Task 2: Taste Scoring Function (`core.py`)

**Files:**
- Modify: `src/meridian_x/core.py`
- Test: `tests/test_core.py`

**Interfaces:**
- Consumes: `config["classify"]` (`artists`, `artist_aliases`, `studios`), `retention_stats: dict[str, dict[str, int]] | None`
- Produces: `score_taste(item: dict[str, Any], config: dict[str, Any], retention_stats: dict[str, dict[str, int]] | None = None) -> tuple[float, list[str]]`

- [ ] **Step 1: Write failing tests in `tests/test_core.py`**

```python
def test_score_taste_actor_and_studio_with_retention():
    config = {
        "classify": {
            "artists": {"WEST": ["Kubera Fortuna"], "JPN": ["Rena Miyashita"]},
            "artist_aliases": {"Rena Miyashita": ["宮下玲奈"]},
            "studios": {"WEST": {"Wowgirls": ["wowgirls", "ultrafilms"]}},
        }
    }
    stats = {"actor": {"Kubera Fortuna": 25, "Rena Miyashita": 6}, "studio": {"Wowgirls": 58, "FC2": 62}}

    # Actor + studio combined
    score, reasons = score_taste({"title": "UltraFilms.26.11.01.Kubera.Fortuna.1080p.mp4"}, config, stats)
    assert score == round(30.0 + round(math.log2(26) * 10, 1) + 10.0 + round(math.log2(59) * 5, 1), 1)
    assert any("actor:Kubera Fortuna" in r for r in reasons)
    assert any("studio:Wowgirls" in r for r in reasons)

    # Alias resolves to canonical actor stats
    score_jp, reasons_jp = score_taste({"title": "MIDA-559 宮下玲奈"}, config, stats)
    assert score_jp == round(30.0 + round(math.log2(7) * 10, 1), 1)
    assert any("actor:Rena Miyashita" in r for r in reasons_jp)

    # FC2 pattern without explicit studio config
    score_fc2, reasons_fc2 = score_taste({"title": "FC2-PPV-4996405"}, config, stats)
    assert score_fc2 == round(10.0 + round(math.log2(63) * 5, 1), 1)
    assert any("studio:FC2" in r for r in reasons_fc2)

    # Missing stats falls back to base registration score
    score_cold, _ = score_taste({"title": "Kubera.Fortuna.scene.mp4"}, config, None)
    assert score_cold == 30.0

    # Unmatched returns 0.0
    score_none, reasons_none = score_taste({"title": "Random.Unknown.1080p.mp4"}, config, stats)
    assert score_none == 0.0 and reasons_none == []
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/test_core.py::test_score_taste_actor_and_studio_with_retention -v`
Expected: FAIL (`ImportError: cannot import name 'score_taste'`)

- [ ] **Step 3: Implement `score_taste` in `src/meridian_x/core.py`**
- Normalize title (`re.sub(r"[\._\-\s]+", "", text).lower()`).
- Match first canonical actor from `classify.artists` or `classify.artist_aliases`; add `30.0 + round(math.log2(1 + kept) * 10, 1)` where `kept = stats.get("actor", {}).get(canonical, 0)`.
- Match first canonical studio from `classify.studios` (or `^fc2` / `fc2ppv` → `"FC2"`); add `10.0 + round(math.log2(1 + kept) * 5, 1)` where `kept = stats.get("studio", {}).get(studio, 0)`.
- Return `(round(total, 1), reasons)`.

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_core.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/meridian_x/core.py tests/test_core.py
git commit -m "feat(core): add retention-driven score_taste function"
```

---

### Task 3: Integrate Shadow Ranking & Optional Cutoff in `collect.py`

**Files:**
- Modify: `src/meridian_x/collect.py`
- Test: `tests/test_collect.py`

**Interfaces:**
- Consumes: `core.score_taste()`, `MeridianDB.get_retention_stats()`
- Produces: Updated `collect._filter_and_send()` accepting `retention_stats: dict | None = None` (default `None` for backward compatibility).

- [ ] **Step 1: Write failing tests in `tests/test_collect.py`**
- `test_filter_and_send_ranks_by_taste_and_preserves_ties`: with `remaining=2`, verifies high-score item is processed before earlier low-score items, and equal-score items keep original order.
- `test_filter_and_send_min_score_cutoff`: with `collection.scoring.min_score = 20.0`, verifies items with score `< 20.0` are skipped without calling `resolve()`.
- `test_filter_and_send_scoring_disabled`: with `collection.scoring.enabled = False`, preserves original RSS order without cutoff.

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/test_collect.py -k "taste or min_score or scoring_disabled" -v`
Expected: FAIL

- [ ] **Step 3: Update `run_transmission()` and `_filter_and_send()` in `src/meridian_x/collect.py`**
- In `run_transmission()`, load `retention_stats = db.get_retention_stats()` once and pass to `_filter_and_send(..., retention_stats=retention_stats)`.
- In `_filter_and_send()`:
  - Read `scoring_cfg = effective_config.get("scoring", {})` (`enabled` default `True`, `min_score` default `0.0`).
  - When `enabled`: compute `(score, reasons) = score_taste(item, effective_config, retention_stats)` for each `new_item`, stably sort descending by `score`, filter out `score < min_score` when `min_score > 0` (logging skipped count), and log `[Score {score:.1f}]` + reasons per processed item.

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/meridian_x/collect.py tests/test_collect.py
git commit -m "feat(collect): add shadow taste ranking and optional min_score cutoff"
```
