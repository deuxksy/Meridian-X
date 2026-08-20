import json
from unittest.mock import MagicMock, patch
import requests
from meridian_x.west_metadata import (
    StashDBClient,
    clean_search_term,
    get_west_metadata,
    load_cache,
    save_cache,
)


def test_stashdb_client_init_session():
    client = StashDBClient(api_key="test_api_key")
    assert isinstance(client.session, requests.Session)
    assert client.session.headers["ApiKey"] == "test_api_key"
    assert client.session.headers["Content-Type"] == "application/json"


def test_stashdb_client_init_session_no_api_key():
    client = StashDBClient()
    assert isinstance(client.session, requests.Session)
    assert "ApiKey" not in client.session.headers
    assert client.session.headers["Content-Type"] == "application/json"


def test_stashdb_client_query_scene():
    client = StashDBClient(api_key="test_token")
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
    with patch.object(client.session, "post", return_value=mock_resp) as mock_post:
        scene = client.query_scene("Vixen Lily Love")
        mock_post.assert_called_once()
        assert scene["id"] == "scene123"
        assert scene["title"] == "Sample Scene"


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


@patch.object(StashDBClient, "query_scene")
def test_get_west_metadata_stashdb_success(mock_query_scene, tmp_path):
    mock_query_scene.return_value = {
        "id": "scene123",
        "title": "Sample Scene",
        "date": "2025-01-29",
        "studio": {"name": "Vixen"},
        "performers": [{"performer": {"name": "Lily Love"}}],
        "tags": [{"name": "Lesbian"}],
    }

    cache_file = tmp_path / "cache.json"
    config = {"stashdb_metadata_cache": str(cache_file)}

    meta = get_west_metadata("Vixen.Lily.Love.mp4", config=config, api_key="test_token")
    assert meta["performers"] == ["Lily Love"]
    assert meta["studio"] == "Vixen"
    assert meta["tags"] == ["Lesbian"]
    assert meta["source"] == "stashdb"

