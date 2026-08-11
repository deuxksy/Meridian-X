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
