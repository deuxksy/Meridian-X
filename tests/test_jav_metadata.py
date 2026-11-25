from unittest.mock import patch
from meridian_x.jav_metadata import get_jav_metadata, load_cache, save_cache


def test_recheck_legacy_cast_on_lookup(tmp_path, mocker):
    from meridian_x.db import MeridianDB

    config = {"db_path": str(tmp_path / "cache.db")}
    db = MeridianDB(config["db_path"])
    db.save_jav_metadata("SNOS-187", {
        "actresses": ["博多彩葉", "白花にあ"], "source": "web_db+onejav", "title": "Existing title"
    })
    web = mocker.patch("meridian_x.jav_metadata.lookup_web_jav_metadata", return_value={})
    mocker.patch("meridian_x.jav_metadata.lookup_jav_actresses", return_value=[])
    result = get_jav_metadata("SNOS-187", config)
    assert result["actresses"] == []
    assert result["title"] == "Existing title"
    web.return_value = {"actresses": ["白花にあ"]}
    assert get_jav_metadata("SNOS-187", config)["actresses"] == ["白花にあ"]
    assert get_jav_metadata("SNOS-187", config)["actresses"] == ["白花にあ"]
    assert web.call_count == 2
    db.save_jav_metadata("SNOS-367", {"actresses": ["manual"], "source": "manual_fix"})
    assert get_jav_metadata("SNOS-367", config)["actresses"] == ["manual"]


def test_jav_metadata_cache(tmp_path):
    cache_file = tmp_path / "cache.json"
    cache_data = {
        "SONE-446": {
            "code": "SONE-446",
            "actresses": ["MINAMO"],
            "makers": ["S1 NO.1 STYLE"],
            "genres": ["ハイビジョン"],
            "title": "Sample Title",
            "cover_url": "https://example.com/cover.jpg",
            "source": "cache",
        }
    }
    save_cache(str(cache_file), cache_data)

    loaded = load_cache(str(cache_file))
    assert loaded["SONE-446"]["actresses"] == ["MINAMO"]


@patch("meridian_x.jav_metadata.lookup_jav_actresses")
@patch("meridian_x.jav_metadata.lookup_web_jav_metadata")
def test_get_jav_metadata_web_db_success(mock_web_db, mock_onejav, tmp_path):
    mock_web_db.return_value = {
        "actresses": ["川越にこ"],
        "makers": ["S1 NO.1 STYLE"],
        "genres": ["単体作品"],
        "title": "Title",
    }

    cache_file = tmp_path / "cache.json"
    config = {"jav_metadata_cache": str(cache_file)}

    meta = get_jav_metadata("SNOS-125", config=config)
    assert meta["actresses"] == ["川越にこ"]
    assert meta["makers"] == ["S1 NO.1 STYLE"]
    assert meta["genres"] == ["単体作品"]
    assert meta["title"] == "Title"
    assert meta["source"] == "web_db"
    mock_onejav.assert_not_called()
    assert "SNOS-125" in load_cache(str(cache_file))


@patch("meridian_x.jav_metadata.lookup_jav_actresses")
@patch("meridian_x.jav_metadata.lookup_web_jav_metadata")
def test_get_jav_metadata_web_db_and_onejav_merging(mock_web_db, mock_onejav, tmp_path):
    mock_web_db.return_value = {
        "actresses": [],
        "makers": ["S1 NO.1 STYLE"],
        "genres": ["ハイビジョン"],
        "title": "Merged Title",
    }
    mock_onejav.return_value = ["MINAMO"]

    cache_file = tmp_path / "cache.json"
    config = {"jav_metadata_cache": str(cache_file)}

    meta = get_jav_metadata("SONE-446", config=config)
    assert meta["actresses"] == ["MINAMO"]
    assert meta["makers"] == ["S1 NO.1 STYLE"]
    assert meta["title"] == "Merged Title"
    assert meta["source"] == "web_db+onejav"


@patch("meridian_x.jav_metadata.lookup_jav_actresses")
@patch("meridian_x.jav_metadata.lookup_web_jav_metadata")
def test_get_jav_metadata_onejav_fallback(mock_web_db, mock_onejav, tmp_path):
    mock_web_db.return_value = {"actresses": [], "makers": [], "genres": [], "title": None}
    mock_onejav.return_value = ["MINAMO"]

    cache_file = tmp_path / "cache.json"
    config = {"jav_metadata_cache": str(cache_file)}

    meta = get_jav_metadata("SONE-446", config=config)
    assert meta["actresses"] == ["MINAMO"]
    assert meta["source"] == "onejav"


@patch("meridian_x.jav_metadata.lookup_jav_actresses")
@patch("meridian_x.jav_metadata.lookup_web_jav_metadata")
def test_get_jav_metadata_skips_fc2(mock_web_db, mock_onejav, tmp_path):
    config = {"jav_metadata_cache": str(tmp_path / "cache.json")}
    meta = get_jav_metadata("FC2-PPV-5000059", config=config)
    assert meta["source"] == "none"
    assert meta["actresses"] == []
    mock_web_db.assert_not_called()
    mock_onejav.assert_not_called()

