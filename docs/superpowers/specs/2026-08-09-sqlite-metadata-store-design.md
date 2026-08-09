# SQLite Metadata Store Architecture Design

* **Date**: 2026-08-09
* **Status**: Approved
* **Target**: Meridian-X (`download_history`, `jav_metadata_cache`, `stashdb_metadata_cache`)

---

## 1. Overview & Goals

Meridian-X currently stores torrent download history in a flat text file (`downloaded_history.txt`) and metadata caches in monolithic JSON files (`logs/jav_metadata_cache.json`, `logs/stashdb_metadata_cache.json`).

As collection size grows:
1. Re-writing entire JSON files on every new metadata lookup incurs unnecessarily high I/O and risk of file corruption on interruption.
2. Querying metadata by actress, studio, genre, or date requires custom Python filtering code.

This design transitions all history and metadata caching to a single local SQLite database file (`data/meridian.db`) using Python's standard `sqlite3` module (zero external dependencies). It maintains backward compatibility with existing interfaces while providing atomic transactions and relational querying capabilities.

---

## 2. Database Schema Design

### 2.1 File Location
* **Database File Path**: `data/meridian.db` (Default, configurable via `config/settings.json` key `db_path`)
* **Version Control**: Add `data/*.db` and `data/*.db-wal` to `.gitignore`.

### 2.2 Tables and Indexes

#### `download_history`
Stores torrent collection history.

```sql
CREATE TABLE IF NOT EXISTS download_history (
    id TEXT PRIMARY KEY,           -- e.g. 'onejav:SNOS155', 'xxxclub:a1b2c3d4'
    source TEXT NOT NULL,          -- e.g. 'onejav', 'xxxclub'
    downloaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_history_source ON download_history(source);
CREATE INDEX IF NOT EXISTS idx_history_downloaded_at ON download_history(downloaded_at);
```

#### `jav_metadata`
Caches metadata retrieved for Japanese Adult Video (FANZA / Web DB / OneJAV).

```sql
CREATE TABLE IF NOT EXISTS jav_metadata (
    code TEXT PRIMARY KEY,         -- e.g. 'SNOS-125', 'FC2-PPV-4895410' (Uppercase)
    title TEXT,                    -- Video title
    makers TEXT,                   -- JSON array string, e.g. '["S1 NO.1 STYLE"]'
    actresses TEXT,                -- JSON array string, e.g. '["Actress Name"]'
    genres TEXT,                   -- JSON array string, e.g. '["Genre1", "Genre2"]'
    cover_url TEXT,                -- Cover image URL
    source_api TEXT,               -- Source chain, e.g. 'fanza+web_db'
    raw_json TEXT,                 -- Complete metadata JSON dump
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jav_updated ON jav_metadata(updated_at);
```

#### `west_metadata`
Caches metadata retrieved for Western media (StashDB).

```sql
CREATE TABLE IF NOT EXISTS west_metadata (
    query_term TEXT PRIMARY KEY,   -- Cleaned search term, e.g. 'vixen 16 09 06 lily love'
    title TEXT,                    -- Scene title
    studio TEXT,                   -- Studio name
    performers TEXT,               -- JSON array string, e.g. '["Lily Love"]'
    tags TEXT,                     -- JSON array string, e.g. '["VR"]'
    release_date TEXT,             -- Release date string (YYYY-MM-DD)
    source_api TEXT,               -- Source API name, e.g. 'stashdb'
    raw_json TEXT,                 -- Complete metadata JSON dump
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_west_updated ON west_metadata(updated_at);
```

---

## 3. Module & Component Architecture

### 3.1 `src/meridian_x/db.py` (`MeridianDB`)

A central DAO class managing database lifecycle and queries:
* **Pragmas**: Enables `PRAGMA journal_mode=WAL;` and `PRAGMA synchronous=NORMAL;` for optimal concurrency and performance.
* **Auto-Initialization**: Runs `CREATE TABLE` and `CREATE INDEX` on instantiation if not existing.

#### Interface Methods:
* `get_download_history() -> Set[str]`
* `add_download_history(torrent_ids: Iterable[str]) -> None`
* `is_downloaded(torrent_id: str) -> bool`
* `get_jav_metadata(code: str) -> dict | None`
* `save_jav_metadata(code: str, metadata: dict) -> None`
* `get_west_metadata(query_term: str) -> dict | None`
* `save_west_metadata(query_term: str, metadata: dict) -> None`
* `migrate_from_legacy(history_file: str, jav_cache_file: str, west_cache_file: str) -> dict`

### 3.2 Backward Compatibility & Integration
* `src/meridian_x/core.py`: Update `load_downloaded_history()` and `save_downloaded_history()` to instantiate/use `MeridianDB` under the hood.
* `src/meridian_x/jav_metadata.py`: Replace `load_cache()` and `save_cache()` file operations with `MeridianDB` calls while preserving function signatures.
* `src/meridian_x/west_metadata.py`: Replace `load_cache()` and `save_cache()` file operations with `MeridianDB` calls while preserving function signatures.

### 3.3 Data Migration
When `MeridianDB` starts, if legacy files (`downloaded_history.txt`, `logs/jav_metadata_cache.json`, `logs/stashdb_metadata_cache.json`) exist, it automatically imports their content into SQLite tables and renames legacy files to `.bak` files to ensure a seamless transition.

---

## 4. Testing & Verification

1. **Unit Tests (`tests/test_db.py`)**:
   * Verify schema creation in-memory (`:memory:`).
   * Verify history CRUD and prefix normalization.
   * Verify JAV and West metadata CRUD and JSON parsing.
   * Test automatic legacy file migration logic.
2. **Regression Tests**:
   * Run `pytest tests/ -v` across existing test suites (`test_core.py`, `test_jav_metadata.py`, `test_west_metadata.py`).
3. **Pipeline Verification**:
   * Run `uv run meridian transmission --dry-run` and `uv run meridian classify --dry-run` to ensure real-world operation without regressions.
