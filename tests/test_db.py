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


def test_migrate_json_caches(tmp_path: Path):
    import json
    db = MeridianDB(db_path=tmp_path / "test.db")
    jav_file = tmp_path / "jav_cache.json"
    west_file = tmp_path / "west_cache.json"

    jav_file.write_text(
        json.dumps({
            "SNOS-125": {"code": "SNOS-125", "title": "Legacy JAV", "actresses": ["Act A"]}
        }),
        encoding="utf-8",
    )

    west_file.write_text(
        json.dumps({
            "vixen scene": {"query_term": "vixen scene", "title": "Legacy West", "studio": "Vixen"}
        }),
        encoding="utf-8",
    )

    res = db.migrate_json_caches(jav_json=str(jav_file), west_json=str(west_file))
    assert res == {"jav_migrated": 1, "west_migrated": 1}

    jav_res = db.get_jav_metadata("SNOS-125")
    assert jav_res is not None
    assert jav_res["title"] == "Legacy JAV"

    west_res = db.get_west_metadata("vixen scene")
    assert west_res is not None
    assert west_res["title"] == "Legacy West"


