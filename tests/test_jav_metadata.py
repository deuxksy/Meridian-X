import json
from unittest.mock import MagicMock, patch
from meridian_x.jav_metadata import get_jav_metadata, load_cache, save_cache


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


@patch("meridian_x.jav_metadata.FanzaClient")
def test_get_jav_metadata_fanza_success(mock_fanza_cls, tmp_path):
    mock_client = MagicMock()
    mock_client.fetch_metadata.return_value = {
        "actresses": ["MINAMO"],
        "makers": ["S1 NO.1 STYLE"],
        "genres": ["単体作品"],
    }
    mock_fanza_cls.return_value = mock_client

    cache_file = tmp_path / "cache.json"
    config = {
        "jav_metadata_cache": str(cache_file),
    }

    meta = get_jav_metadata("SONE-446", config=config, api_id="test_id", affiliate_id="test_aff")
    assert meta["code"] == "SONE-446"
    assert meta["actresses"] == ["MINAMO"]
    assert meta["makers"] == ["S1 NO.1 STYLE"]
    assert meta["genres"] == ["単体作品"]
    assert meta["title"] is None
    assert meta["cover_url"] is None
    assert meta["source"] == "fanza"

    # Verify cached
    loaded_cache = load_cache(str(cache_file))
    assert "SONE-446" in loaded_cache


@patch("meridian_x.jav_metadata.lookup_web_jav_metadata")
@patch("meridian_x.jav_metadata.FanzaClient")
def test_get_jav_metadata_web_db_fallback(mock_fanza_cls, mock_web_db, tmp_path):
    mock_client = MagicMock()
    mock_client.fetch_metadata.return_value = None
    mock_fanza_cls.return_value = mock_client
    mock_web_db.return_value = {
        "actresses": ["川越にこ"],
        "makers": ["S1 NO.1 STYLE"],
        "genres": [],
        "title": "Title",
    }

    cache_file = tmp_path / "cache.json"
    config = {
        "jav_metadata_cache": str(cache_file),
    }

    meta = get_jav_metadata("SONE-446", config=config, api_id="test_id", affiliate_id="test_aff")
    assert meta["actresses"] == ["川越にこ"]
    assert meta["makers"] == ["S1 NO.1 STYLE"]
    assert meta["source"] == "web_db"


@patch("meridian_x.jav_metadata.lookup_jav_actresses")
@patch("meridian_x.jav_metadata.lookup_web_jav_metadata")
@patch("meridian_x.jav_metadata.FanzaClient")
def test_get_jav_metadata_onejav_fallback(mock_fanza_cls, mock_web_db, mock_onejav, tmp_path):
    mock_client = MagicMock()
    mock_client.fetch_metadata.return_value = None
    mock_fanza_cls.return_value = mock_client
    mock_web_db.return_value = {"actresses": [], "makers": [], "genres": [], "title": None}
    mock_onejav.return_value = ["MINAMO"]

    cache_file = tmp_path / "cache.json"
    config = {
        "jav_metadata_cache": str(cache_file),
    }

    meta = get_jav_metadata("SONE-446", config=config, api_id="test_id", affiliate_id="test_aff")
    assert meta["actresses"] == ["MINAMO"]
    assert meta["source"] == "onejav"

