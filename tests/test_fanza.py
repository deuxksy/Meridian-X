from unittest.mock import MagicMock, patch
import requests
import pytest

from meridian_x.fanza import FanzaClient, extract_jav_code


def test_fanza_client_init_session():
    client = FanzaClient(api_id="test_id", affiliate_id="test_aff")
    assert isinstance(client.session, requests.Session)
    assert "User-Agent" in client.session.headers
    assert "Mozilla" in client.session.headers["User-Agent"]


def test_fanza_client_search_item():
    client = FanzaClient(api_id="test_id", affiliate_id="test_aff")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "result": {
            "items": [
                {
                    "title": "Sample Title",
                    "iteminfo": {
                        "actress": [{"name": "MINAMO"}],
                        "maker": [{"name": "S1"}],
                        "genre": [{"name": "HD"}],
                    }
                }
            ]
        }
    }
    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        data = client.search_item("SONE-446")
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert args[0] == client.BASE_URL
        assert kwargs["params"]["keyword"] == "SONE-446"
        assert kwargs["params"]["api_id"] == "test_id"
        assert data["result"]["items"][0]["title"] == "Sample Title"


def test_fanza_client_fetch_metadata():
    client = FanzaClient(api_id="test_id", affiliate_id="test_aff")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "result": {
            "items": [
                {
                    "title": "Sample Title",
                    "iteminfo": {
                        "actress": [{"name": "MINAMO"}],
                        "maker": [{"name": "S1 NO.1 STYLE"}],
                        "genre": [{"name": "単체作品"}],
                    }
                }
            ]
        }
    }
    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        meta = client.fetch_metadata("SONE-446")
        assert meta == {
            "actresses": ["MINAMO"],
            "makers": ["S1 NO.1 STYLE"],
            "genres": ["単체作品"],
        }
        mock_get.assert_called_once()


def test_fanza_client_fetch_metadata_fc2_skipped():
    client = FanzaClient(api_id="test_id", affiliate_id="test_aff")
    meta = client.fetch_metadata("FC2-PPV-1234567")
    assert meta is None
