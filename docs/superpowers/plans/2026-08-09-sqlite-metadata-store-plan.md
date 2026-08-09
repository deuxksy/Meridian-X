# SQLite Metadata Store Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate Meridian-X torrent download history and JAV/West metadata caches from flat JSON/TXT files to a unified local SQLite database (`meridian.db`).

**Architecture:** Create a `MeridianDB` DAO class in `src/meridian_x/db.py` using Python's standard `sqlite3` module. Wrap existing functions in `core.py`, `jav_metadata.py`, and `west_metadata.py` so that external callers maintain full backward compatibility while benefiting from SQLite indexing, WAL concurrency, and atomic transactions.

**Tech Stack:** Python 3.10+, `sqlite3` (stdlib), `pytest`

## Global Constraints

- Use Python stdlib `sqlite3` only (no extra external dependencies in `pyproject.toml`).
- Maintain exact signatures for existing public functions in `core.py`, `jav_metadata.py`, and `west_metadata.py`.
- Store default database file at `data/meridian.db` (configurable via `config/settings.json` `db_path`).

---

### Task 1: Create `MeridianDB` DAO class & Database Schema

**Files:**
- Create: `src/meridian_x/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Consumes: None
- Produces: `MeridianDB(db_path: str | Path | None = None)` class with `.init_db()` creating `download_history`, `jav_metadata`, and `west_metadata` tables.

- [ ] **Step 1: Write failing test for MeridianDB initialization and table creation**

```python
# tests/test_db.py
import sqlite3
from pathlib import Path
from meridian_x.db import MeridianDB

def test_db_init_creates_tables(tmp_path: Path):
    db_file = tmp_path / "test_meridian.db"
    db = MeridianDB(db_path=db_file)
    
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    assert "download_history" in tables
    assert "jav_metadata" in tables
    assert "west_metadata" in tables
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/test_db.py -v`
Expected: FAIL with "No module named 'meridian_x.db'" or "ImportError"

- [ ] **Step 3: Implement `MeridianDB` in `src/meridian_x/db.py`**

```python
# src/meridian_x/db.py
import json
import logging
import sqlite3
from pathlib import Path
from typing import Iterable, Set

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "data/meridian.db"


class MeridianDB:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else Path(DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self.get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS download_history (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    downloaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_history_source ON download_history(source);
                CREATE INDEX IF NOT EXISTS idx_history_downloaded_at ON download_history(downloaded_at);

                CREATE TABLE IF NOT EXISTS jav_metadata (
                    code TEXT PRIMARY KEY,
                    title TEXT,
                    makers TEXT,
                    actresses TEXT,
                    genres TEXT,
                    cover_url TEXT,
                    source_api TEXT,
                    raw_json TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_jav_updated ON jav_metadata(updated_at);

                CREATE TABLE IF NOT EXISTS west_metadata (
                    query_term TEXT PRIMARY KEY,
                    title TEXT,
                    studio TEXT,
                    performers TEXT,
                    tags TEXT,
                    release_date TEXT,
                    source_api TEXT,
                    raw_json TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_west_updated ON west_metadata(updated_at);
            """)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_db.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/meridian_x/db.py tests/test_db.py
git commit -m "feat: implement MeridianDB schema initialization"
```

---

### Task 2: Download History CRUD, Legacy Migration & `core.py` Integration

**Files:**
- Modify: `src/meridian_x/db.py`
- Modify: `src/meridian_x/core.py:87-120`
- Test: `tests/test_db.py`

**Interfaces:**
- Consumes: `MeridianDB` connection from Task 1
- Produces:
  - `MeridianDB.get_download_history() -> Set[str]`
  - `MeridianDB.add_download_history(torrent_ids: Iterable[str]) -> None`
  - `MeridianDB.is_downloaded(torrent_id: str) -> bool`
  - `MeridianDB.migrate_history_txt(history_file: str) -> int`

- [ ] **Step 1: Write failing tests for History operations and Migration**

```python
# append to tests/test_db.py
def test_download_history_crud(tmp_path: Path):
    db = MeridianDB(db_path=tmp_path / "test.db")
    
    assert db.get_download_history() == set()
    assert not db.is_downloaded("onejav:SNOS125")

    db.add_download_history(["onejav:SNOS125", "xxxclub:abc12345"])
    assert db.is_downloaded("onejav:SNOS125")
    assert db.get_download_history() == {"onejav:SNOS125", "xxxclub:abc12345"}

def test_migrate_history_txt(tmp_path: Path):
    db = MeridianDB(db_path=tmp_path / "test.db")
    txt_file = tmp_path / "downloaded_history.txt"
    txt_file.write_text("SNOS100\nonejav:SNOS101\nxxxclub:HASH99\n", encoding="utf-8")

    migrated_count = db.migrate_history_txt(str(txt_file))
    assert migrated_count == 3
    history = db.get_download_history()
    assert "onejav:SNOS100" in history
    assert "onejav:SNOS101" in history
    assert "xxxclub:HASH99" in history
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/test_db.py -k test_download_history -v`
Expected: FAIL with "AttributeError: 'MeridianDB' object has no attribute 'get_download_history'"

- [ ] **Step 3: Implement History CRUD and migration in `src/meridian_x/db.py` & update `core.py`**

Add to `src/meridian_x/db.py`:
```python
    def get_download_history(self) -> Set[str]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT id FROM download_history").fetchall()
            return {row["id"] for row in rows}

    def is_downloaded(self, torrent_id: str) -> bool:
        item = f"onejav:{torrent_id}" if ":" not in torrent_id else torrent_id
        with self.get_connection() as conn:
            row = conn.execute("SELECT 1 FROM download_history WHERE id = ?", (item,)).fetchone()
            return row is not None

    def add_download_history(self, torrent_ids: Iterable[str]) -> None:
        to_insert = []
        for tid in torrent_ids:
            item = f"onejav:{tid}" if ":" not in tid else tid
            source = item.split(":", 1)[0]
            to_insert.append((item, source))

        with self.get_connection() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO download_history (id, source) VALUES (?, ?)",
                to_insert,
            )

    def migrate_history_txt(self, history_file: str) -> int:
        path = Path(history_file)
        if not path.exists():
            return 0
        items = set()
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                item = line.strip()
                if item:
                    if ":" not in item:
                        item = "onejav:" + item
                    items.add(item)
        if items:
            self.add_download_history(items)
        return len(items)
```

Update `src/meridian_x/core.py` functions:
```python
def load_downloaded_history(history_file: str = "downloaded_history.txt") -> Set[str]:
    from .db import MeridianDB
    db = MeridianDB()
    if Path(history_file).exists():
        db.migrate_history_txt(history_file)
    return db.get_download_history()


def save_downloaded_history(history_file: str, downloaded: Set[str]) -> None:
    from .db import MeridianDB
    db = MeridianDB()
    db.add_download_history(downloaded)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_db.py tests/test_core.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/meridian_x/db.py src/meridian_x/core.py tests/test_db.py
git commit -m "feat: connect download history to MeridianDB with migration support"
```

---

### Task 3: JAV & West Metadata Cache CRUD, Legacy Migration & Resolver Integration

**Files:**
- Modify: `src/meridian_x/db.py`
- Modify: `src/meridian_x/jav_metadata.py:20-41`
- Modify: `src/meridian_x/west_metadata.py:41-62`
- Test: `tests/test_db.py`
- Test: `tests/test_jav_metadata.py`
- Test: `tests/test_west_metadata.py`

**Interfaces:**
- Consumes: `MeridianDB` from Task 1
- Produces:
  - `MeridianDB.get_jav_metadata(code: str) -> dict | None`
  - `MeridianDB.save_jav_metadata(code: str, metadata: dict) -> None`
  - `MeridianDB.get_west_metadata(term: str) -> dict | None`
  - `MeridianDB.save_west_metadata(term: str, metadata: dict) -> None`
  - `MeridianDB.migrate_json_caches(jav_json: str, west_json: str) -> dict`

- [ ] **Step 1: Write failing tests for JAV/West metadata operations & JSON cache migration**

```python
# append to tests/test_db.py
def test_jav_metadata_crud(tmp_path: Path):
    db = MeridianDB(db_path=tmp_path / "test.db")
    meta = {
        "code": "SNOS-125",
        "title": "Test Title",
        "makers": ["S1"],
        "actresses": ["Actress A"],
        "genres": ["Genre B"],
        "cover_url": "http://example.com/cover.jpg",
        "source": "fanza",
    }
    assert db.get_jav_metadata("SNOS-125") is None
    db.save_jav_metadata("SNOS-125", meta)
    res = db.get_jav_metadata("SNOS-125")
    assert res is not None
    assert res["code"] == "SNOS-125"
    assert res["actresses"] == ["Actress A"]

def test_west_metadata_crud(tmp_path: Path):
    db = MeridianDB(db_path=tmp_path / "test.db")
    meta = {
        "query_term": "vixen test",
        "title": "West Scene",
        "studio": "Vixen",
        "performers": ["Performer X"],
        "tags": ["VR"],
        "date": "2026-01-01",
        "source": "stashdb",
    }
    assert db.get_west_metadata("vixen test") is None
    db.save_west_metadata("vixen test", meta)
    res = db.get_west_metadata("vixen test")
    assert res is not None
    assert res["studio"] == "Vixen"
    assert res["performers"] == ["Performer X"]
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/test_db.py -k "test_jav_metadata_crud or test_west_metadata_crud" -v`
Expected: FAIL with "AttributeError: 'MeridianDB' object has no attribute 'get_jav_metadata'"

- [ ] **Step 3: Implement Metadata CRUD in `db.py` & update `jav_metadata.py`, `west_metadata.py`**

Add to `src/meridian_x/db.py`:
```python
    def get_jav_metadata(self, code: str) -> dict | None:
        code_upper = code.upper()
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM jav_metadata WHERE code = ?", (code_upper,)).fetchone()
            if not row:
                return None
            return {
                "code": row["code"],
                "title": row["title"],
                "makers": json.loads(row["makers"]) if row["makers"] else [],
                "actresses": json.loads(row["actresses"]) if row["actresses"] else [],
                "genres": json.loads(row["genres"]) if row["genres"] else [],
                "cover_url": row["cover_url"],
                "source": row["source_api"],
            }

    def save_jav_metadata(self, code: str, metadata: dict) -> None:
        code_upper = code.upper()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO jav_metadata 
                (code, title, makers, actresses, genres, cover_url, source_api, raw_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    code_upper,
                    metadata.get("title"),
                    json.dumps(metadata.get("makers", []), ensure_ascii=False),
                    json.dumps(metadata.get("actresses", []), ensure_ascii=False),
                    json.dumps(metadata.get("genres", []), ensure_ascii=False),
                    metadata.get("cover_url"),
                    metadata.get("source", "none"),
                    json.dumps(metadata, ensure_ascii=False),
                ),
            )

    def get_west_metadata(self, query_term: str) -> dict | None:
        term = query_term.strip()
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM west_metadata WHERE query_term = ?", (term,)).fetchone()
            if not row:
                return None
            return {
                "query_term": row["query_term"],
                "title": row["title"],
                "studio": row["studio"],
                "performers": json.loads(row["performers"]) if row["performers"] else [],
                "tags": json.loads(row["tags"]) if row["tags"] else [],
                "date": row["release_date"],
                "source": row["source_api"],
            }

    def save_west_metadata(self, query_term: str, metadata: dict) -> None:
        term = query_term.strip()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO west_metadata 
                (query_term, title, studio, performers, tags, release_date, source_api, raw_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    term,
                    metadata.get("title"),
                    metadata.get("studio"),
                    json.dumps(metadata.get("performers", []), ensure_ascii=False),
                    json.dumps(metadata.get("tags", []), ensure_ascii=False),
                    metadata.get("date"),
                    metadata.get("source", "none"),
                    json.dumps(metadata, ensure_ascii=False),
                ),
            )
```

Update `load_cache` and `save_cache` in `jav_metadata.py`:
```python
def load_cache(cache_path: str = DEFAULT_CACHE_PATH) -> dict:
    from .db import MeridianDB
    db = MeridianDB()
    # Migration if legacy file exists
    if Path(cache_path).exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    db.save_jav_metadata(k, v)
        except Exception as e:
            logger.warning(f"Failed to migrate legacy JAV cache: {e}")
    return {} # cache lookups now hit db directly in get_jav_metadata
```
And update `get_jav_metadata` lookup/save logic in `jav_metadata.py`:
```python
    db = MeridianDB()
    cached = db.get_jav_metadata(code_upper)
    if cached:
        logger.debug(f"[JAV Metadata Cache Hit] {code_upper}")
        return cached
    ...
    db.save_jav_metadata(code_upper, metadata)
    return metadata
```

Update `load_cache` and `save_cache` in `west_metadata.py`:
```python
def load_cache(cache_path: str = DEFAULT_CACHE_PATH) -> dict:
    from .db import MeridianDB
    db = MeridianDB()
    if Path(cache_path).exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    db.save_west_metadata(k, v)
        except Exception as e:
            logger.warning(f"Failed to migrate legacy West cache: {e}")
    return {}
```
And update `get_west_metadata` lookup/save logic in `west_metadata.py`:
```python
    db = MeridianDB()
    cached = db.get_west_metadata(term)
    if cached:
        logger.debug(f"[StashDB Cache Hit] {term}")
        return cached
    ...
    db.save_west_metadata(term, metadata)
    return metadata
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_db.py tests/test_jav_metadata.py tests/test_west_metadata.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/meridian_x/db.py src/meridian_x/jav_metadata.py src/meridian_x/west_metadata.py tests/test_db.py
git commit -m "feat: migrate JAV and West metadata caches to MeridianDB"
```

---

### Task 4: `.gitignore` Updates & Full Regression Verification

**Files:**
- Modify: `.gitignore`
- Test: All tests in `tests/`

- [ ] **Step 1: Update `.gitignore` for SQLite files**

Add the following to `.gitignore`:
```gitignore
# SQLite Database Files
data/*.db
data/*.db-wal
data/*.db-shm
logs/*.db
logs/*.db-wal
logs/*.db-shm
```

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 3: Run `--dry-run` CLI commands**

Run: `uv run meridian transmission --dry-run`
Expected: Clean execution without errors

Run: `uv run meridian classify --dry-run`
Expected: Clean execution without errors

- [ ] **Step 4: Commit**

```bash
git add .gitignore
git commit -m "chore: add sqlite db files to gitignore and complete metadata store migration"
```
