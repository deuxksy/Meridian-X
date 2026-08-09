import json
from unittest.mock import MagicMock, patch
from meridian_x.west_metadata import clean_search_term, get_west_metadata, load_cache, save_cache


def test_clean_search_term():
    filename = "Vixen.26.08.05.Cindy.Luna.Fit.Babe.Needs.Cum.XXX.1080p.MP4-P2P.mp4"
    cleaned = clean_search_term(filename)
    assert "1080p" not in cleaned
    assert "MP4" not in cleaned
    assert "26.08.05" not in cleaned
    assert "Cindy Luna Fit Babe Needs Cum" in cleaned


def test_west_metadata_cache(tmp_path):
    cache_file = tmp_path / "cache.json"
    cache_data = {
        "Vixen Lily Love": {
            "query_term": "Vixen Lily Love",
            "performers": ["Lily Love"],
            "studio": "Vixen",
            "tags": ["Lesbian"],
            "title": "Sample Title",
            "date": "2025-01-29",
            "source": "cache",
        }
    }
    save_cache(str(cache_file), cache_data)

    loaded = load_cache(str(cache_file))
    assert loaded["Vixen Lily Love"]["performers"] == ["Lily Love"]


@patch("meridian_x.west_metadata.requests.post")
def test_get_west_metadata_stashdb_success(mock_post, tmp_path):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {
            "queryScenes": {
                "count": 1,
                "scenes": [
                    {
                        "id": "scene123",
                        "title": "Sample Scene",
                        "date": "2025-01-29",
                        "studio": {"name": "Vixen"},
                        "performers": [{"performer": {"name": "Lily Love"}}],
                        "tags": [{"name": "Lesbian"}],
                    }
                ]
            }
        }
    }

    mock_post.return_value = mock_resp

    cache_file = tmp_path / "cache.json"
    config = {"stashdb_metadata_cache": str(cache_file)}

    meta = get_west_metadata("Vixen.Lily.Love.mp4", config=config, api_key="test_token")
    assert meta["performers"] == ["Lily Love"]
    assert meta["studio"] == "Vixen"
    assert meta["tags"] == ["Lesbian"]
    assert meta["source"] == "stashdb"
