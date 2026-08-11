from unittest.mock import patch, MagicMock
from meridian_x.sources.xxxclub import search, resolve_magnet

MOCK_SEARCH_HTML = """
<html>
<body>
  <table>
    <tr class="torrents-row">
      <td class="name"><a href="/details/12345/test-torrent-1080p">Test Torrent 1080p Title</a></td>
      <td class="size">1.5 GB</td>
      <td class="seeders">25</td>
      <td class="leechers">2</td>
    </tr>
  </table>
</body>
</html>
"""

MOCK_DETAILS_HTML = """
<html>
<body>
  <a href="magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678&dn=Test+Torrent">Download Magnet</a>
</body>
</html>
"""

def test_search_xxxclub():
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = MOCK_SEARCH_HTML
        mock_get.return_value = mock_response

        results = search("test", category="1080p", config={})
        assert len(results) == 1
        assert results[0]["title"] == "Test Torrent 1080p Title"
        assert results[0]["details_url"] == "https://xxxclub.to/details/12345/test-torrent-1080p"
        assert results[0]["size"] == "1.5 GB"
        assert results[0]["seeders"] == "25"
        assert results[0]["leechers"] == "2"

def test_resolve_magnet():
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = MOCK_DETAILS_HTML
        mock_get.return_value = mock_response

        magnet = resolve_magnet("https://xxxclub.to/details/12345/test-torrent-1080p", config={})
        assert magnet.startswith("magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678")


def test_run_search_auto_mode():
    from meridian_x.cli import run_search

    mock_results = [{
        "id": "xxxclub:12345",
        "title": "Dakota Doll 1080p",
        "details_url": "https://xxxclub.to/details/12345",
        "size": "2.0 GB",
        "seeders": "10",
        "leechers": "1"
    }]
    
    with patch("meridian_x.sources.xxxclub.search", return_value=mock_results), \
         patch("meridian_x.sources.xxxclub.resolve_magnet", return_value="magnet:?xt=urn:btih:mockhash"), \
         patch("meridian_x.db.MeridianDB") as mock_db_cls, \
         patch("meridian_x.transmission.TransmissionClient") as mock_tx_cls, \
         patch("time.sleep") as mock_sleep:
        
        mock_db = MagicMock()
        mock_db.is_downloaded.return_value = False
        mock_db_cls.return_value = mock_db
        
        mock_tx = MagicMock()
        mock_tx_cls.return_value = mock_tx
        
        count = run_search(
            query="Dakota",
            category="1080p",
            source="xxxclub",
            auto=True,
            delay=1.0,
            dry_run=False
        )
        
        assert count == 1
        mock_tx.add_torrent.assert_called_once_with("magnet:?xt=urn:btih:mockhash")
        mock_db.add_history.assert_called_once()


def test_parse_selection_indices():
    from meridian_x.cli import parse_selection_indices

    assert parse_selection_indices("all", 5) == [1, 2, 3, 4, 5]
    assert parse_selection_indices("1,3-5", 5) == [1, 3, 4, 5]
    assert parse_selection_indices(" 2 , 4 ", 5) == [2, 4]
    assert parse_selection_indices("10, -1, 0", 5) == []


def test_run_search_interactive_mode():
    from meridian_x.cli import run_search

    mock_results = [{
        "id": "xxxclub:12345",
        "title": "Dakota Doll 1080p",
        "details_url": "https://xxxclub.to/details/12345",
        "size": "2.0 GB",
        "seeders": "10",
        "leechers": "1"
    }]

    with patch("meridian_x.sources.xxxclub.search", return_value=mock_results), \
         patch("meridian_x.sources.xxxclub.resolve_magnet", return_value="magnet:?xt=urn:btih:mockhash"), \
         patch("meridian_x.db.MeridianDB") as mock_db_cls, \
         patch("meridian_x.transmission.TransmissionClient") as mock_tx_cls, \
         patch("builtins.input", return_value="1"):

        mock_db = MagicMock()
        mock_db.is_downloaded.return_value = False
        mock_db_cls.return_value = mock_db

        mock_tx = MagicMock()
        mock_tx_cls.return_value = mock_tx

        count = run_search(
            query="Dakota",
            category="1080p",
            source="xxxclub",
            auto=False,
            dry_run=False
        )

        assert count == 1
        mock_tx.add_torrent.assert_called_once_with("magnet:?xt=urn:btih:mockhash")
        mock_db.add_history.assert_called_once()

