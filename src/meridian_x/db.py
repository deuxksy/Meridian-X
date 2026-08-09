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

