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

                CREATE TABLE IF NOT EXISTS actresses (
                    name TEXT PRIMARY KEY,
                    name_en TEXT,
                    region TEXT NOT NULL,
                    birthday TEXT,
                    height_cm INTEGER,
                    measurements TEXT,
                    debut TEXT,
                    debut_work TEXT,
                    label TEXT,
                    agency TEXT,
                    concept TEXT,
                    aliases TEXT,
                    source_url TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_actresses_region ON actresses(region);
            """)
            # 구버전 actresses 테이블 마이그레이션 (name_en 컬럼 추가)
            cols = {row[1] for row in conn.execute("PRAGMA table_info(actresses)")}
            if "name_en" not in cols:
                conn.execute("ALTER TABLE actresses ADD COLUMN name_en TEXT")

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
        try:
            path.rename(path.with_suffix(path.suffix + ".bak"))
        except OSError as e:
            logger.warning(f"Failed to rename {path} to .bak: {e}")
        return len(items)

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

    def get_all_jav_metadata(self) -> dict[str, dict]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM jav_metadata").fetchall()
            res = {}
            for row in rows:
                res[row["code"]] = {
                    "code": row["code"],
                    "title": row["title"],
                    "makers": json.loads(row["makers"]) if row["makers"] else [],
                    "actresses": json.loads(row["actresses"]) if row["actresses"] else [],
                    "genres": json.loads(row["genres"]) if row["genres"] else [],
                    "cover_url": row["cover_url"],
                    "source": row["source_api"],
                }
            return res

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

    def get_all_west_metadata(self) -> dict[str, dict]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM west_metadata").fetchall()
            res = {}
            for row in rows:
                res[row["query_term"]] = {
                    "query_term": row["query_term"],
                    "title": row["title"],
                    "studio": row["studio"],
                    "performers": json.loads(row["performers"]) if row["performers"] else [],
                    "tags": json.loads(row["tags"]) if row["tags"] else [],
                    "date": row["release_date"],
                    "source": row["source_api"],
                }
            return res

    def save_actress(self, profile: dict) -> None:
        """즐겨찾기 배우 프로필 upsert. aliases는 JSON으로 저장."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO actresses
                (name, name_en, region, birthday, height_cm, measurements, debut, debut_work,
                 label, agency, concept, aliases, source_url, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    profile["name"],
                    profile.get("name_en"),
                    profile.get("region"),
                    profile.get("birthday"),
                    profile.get("height_cm"),
                    profile.get("measurements"),
                    profile.get("debut"),
                    profile.get("debut_work"),
                    profile.get("label"),
                    profile.get("agency"),
                    profile.get("concept"),
                    json.dumps(profile.get("aliases", []), ensure_ascii=False),
                    profile.get("source_url"),
                ),
            )

    def get_actress(self, name: str) -> dict | None:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM actresses WHERE name = ?", (name,)).fetchone()
            if not row:
                return None
            return {
                "name": row["name"],
                "name_en": row["name_en"],
                "region": row["region"],
                "birthday": row["birthday"],
                "height_cm": row["height_cm"],
                "measurements": row["measurements"],
                "debut": row["debut"],
                "debut_work": row["debut_work"],
                "label": row["label"],
                "agency": row["agency"],
                "concept": row["concept"],
                "aliases": json.loads(row["aliases"]) if row["aliases"] else [],
                "source_url": row["source_url"],
            }

    def get_all_actresses(self, region: str | None = None) -> list[dict]:
        with self.get_connection() as conn:
            if region:
                rows = conn.execute(
                    "SELECT name FROM actresses WHERE region = ? ORDER BY name", (region,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT name FROM actresses ORDER BY name").fetchall()
            return [r for row in rows if (r := self.get_actress(row["name"])) is not None]

    def migrate_json_caches(
        self,
        jav_json: str | Path | None = None,
        west_json: str | Path | None = None,
    ) -> dict:
        jav_count = 0
        west_count = 0
        if jav_json:
            jpath = Path(jav_json)
            if jpath.exists():
                try:
                    with open(jpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            for k, v in data.items():
                                if isinstance(v, dict):
                                    self.save_jav_metadata(k, v)
                                    jav_count += 1
                    jpath.rename(jpath.with_suffix(jpath.suffix + ".bak"))
                except Exception as e:
                    logger.warning(f"Failed to migrate legacy JAV cache from {jav_json}: {e}")

        if west_json:
            wpath = Path(west_json)
            if wpath.exists():
                try:
                    with open(wpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            for k, v in data.items():
                                if isinstance(v, dict):
                                    self.save_west_metadata(k, v)
                                    west_count += 1
                    wpath.rename(wpath.with_suffix(wpath.suffix + ".bak"))
                except Exception as e:
                    logger.warning(f"Failed to migrate legacy West cache from {west_json}: {e}")

        return {"jav_migrated": jav_count, "west_migrated": west_count}


