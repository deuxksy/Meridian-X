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
