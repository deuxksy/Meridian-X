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


def test_download_history_crud(tmp_path: Path):
    db = MeridianDB(db_path=tmp_path / "test.db")

    assert db.get_download_history() == set()
    assert not db.is_downloaded("onejav:SNOS125")

    db.add_download_history(["onejav:SNOS125", "xxxclub:abc12345"])
    assert db.is_downloaded("onejav:SNOS125")
    assert db.is_downloaded("SNOS125")  # test prefix fallback
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

