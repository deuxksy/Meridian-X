import pytest
from unittest.mock import patch, MagicMock
from meridian_x.sources import sukebei


SAMPLE_SUKEBEI_RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:nyaa="https://nyaa.si/xmlns/nyaa">
  <channel>
    <title>Sukebei - Real Life - Video</title>
    <link>https://sukebei.nyaa.si/</link>
    <description>RSS Feed for Sukebei</description>
    <item>
      <title>[FHD/3.2GB] MIAA-001 MINAMO Special Debut</title>
      <link>https://sukebei.nyaa.si/view/1234567</link>
      <guid isPermaLink="true">https://sukebei.nyaa.si/view/1234567</guid>
      <pubDate>Thu, 20 Aug 2026 00:00:00 +0000</pubDate>
      <nyaa:seeders>25</nyaa:seeders>
      <nyaa:leechers>3</nyaa:leechers>
      <nyaa:downloads>150</nyaa:downloads>
      <nyaa:infoHash>0123456789abcdef0123456789abcdef01234567</nyaa:infoHash>
      <nyaa:size>3.2 GiB</nyaa:size>
    </item>
    <item>
      <title>Unrelated Amateur Clip 9999</title>
      <link>https://sukebei.nyaa.si/view/1234568</link>
      <guid isPermaLink="true">https://sukebei.nyaa.si/view/1234568</guid>
      <pubDate>Thu, 20 Aug 2026 00:00:00 +0000</pubDate>
      <nyaa:seeders>5</nyaa:seeders>
      <nyaa:leechers>1</nyaa:leechers>
      <nyaa:downloads>10</nyaa:downloads>
      <nyaa:infoHash>abcdef0123456789abcdef0123456789abcdef01</nyaa:infoHash>
      <nyaa:size>500 MiB</nyaa:size>
    </item>
  </channel>
</rss>
"""


def test_is_whitelisted_title():
    config = {
        "classify": {
            "artists": {"JPN": ["MINAMO", "Rena Miyashita"]},
            "studios": {"JPN": {"S1": ["s1"]}},
        }
    }
    assert sukebei.is_whitelisted_title("MIAA-001 MINAMO Debut", config) is True
    assert sukebei.is_whitelisted_title("Random Title Without Match", config) is False
    # Studio match
    assert sukebei.is_whitelisted_title("[FHD] S1 NO.1 STYLE Special", config) is True
    # JPN Code pattern match
    assert sukebei.is_whitelisted_title("SSIS-567 Uncensored Leak", config) is True
    assert sukebei.is_whitelisted_title("FC2-PPV-123456 Amateur", config) is True


def test_sukebei_discover_and_resolve():
    config = {
        "rss_url": "https://sukebei.nyaa.si/?page=rss&c=2_2",
        "classify": {
            "artists": {"JPN": ["MINAMO"]},
            "studios": {},
        },
    }

    with patch.object(sukebei, "_fetch_url", return_value=(True, SAMPLE_SUKEBEI_RSS)):
        items = sukebei.discover(config)
        assert len(items) == 1
        item = items[0]
        assert item["id"] == "sukebei:1234567"
        assert "MINAMO" in item["title"]
        assert item["seeders"] == "25"
        assert item["size"] == "3.2 GiB"

        payload = sukebei.resolve(item, config)
        assert payload["type"] == "magnet"
        assert "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567" in payload["data"]


def test_sukebei_fetch_url_remote():
    config = {
        "remote": {"ssh_alias": "lt"},
        "request_timeout": 20,
    }
    with patch.object(sukebei, "_ssh", return_value=(True, "response_text")) as mock_ssh:
        ok, text = sukebei._fetch_url("https://sukebei.nyaa.si/test", config)
        assert ok is True
        assert text == "response_text"
        mock_ssh.assert_called_once()
        assert "curl -4 -sL --max-time 20" in mock_ssh.call_args[0][1]


def test_sukebei_fetch_url_direct_and_proxy():
    config = {
        "proxy": "http://127.0.0.1:8080",
        "request_timeout": 15,
    }
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.text = "rss content"
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        ok, text = sukebei._fetch_url("https://sukebei.nyaa.si/test", config)
        assert ok is True
        assert text == "rss content"
        mock_get.assert_called_once_with(
            "https://sukebei.nyaa.si/test",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            proxies={"http": "http://127.0.0.1:8080", "https": "http://127.0.0.1:8080"},
            timeout=15,
        )


def test_sukebei_resolve_fallbacks():
    config = {}
    # Item without magnet_url but with info_hash
    item_hash = {
        "title": "Sample Title",
        "info_hash": "aabbcc112233",
    }
    res = sukebei.resolve(item_hash, config)
    assert res == {"type": "magnet", "data": "magnet:?xt=urn:btih:aabbcc112233&dn=Sample%20Title"}

    # Item with details_url resolving magnet from page
    item_details = {
        "details_url": "https://sukebei.nyaa.si/view/100",
    }
    with patch.object(sukebei, "resolve_magnet", return_value="magnet:?xt=urn:btih:frompage"):
        res = sukebei.resolve(item_details, config)
        assert res == {"type": "magnet", "data": "magnet:?xt=urn:btih:frompage"}

    # Empty item returns None
    assert sukebei.resolve({}, config) is None


SAMPLE_SUKEBEI_SEARCH_HTML = """
<!DOCTYPE html>
<html>
<body>
<div class="table-responsive">
  <table class="table table-bordered table-hover table-striped torrent-list">
    <thead>
      <tr>
        <th class="hdr-category">Category</th>
        <th class="hdr-name">Name</th>
        <th class="hdr-link">Links</th>
        <th class="hdr-size">Size</th>
        <th class="hdr-date">Date</th>
        <th class="hdr-seeders">Seeders</th>
        <th class="hdr-leechers">Leechers</th>
        <th class="hdr-downloads">Downloads</th>
      </tr>
    </thead>
    <tbody>
      <tr class="default">
        <td><a href="/?c=2_2" title="Real Life - Video"><img src="/static/img/icons/nyaa/2_2.png" alt="Real Life - Video"></a></td>
        <td colspan="2">
          <a href="/view/1234567#comments" class="comments" title="2 comments"><i class="fa fa-comments"></i> 2</a>
          <a href="/view/1234567" title="[FHD/3.2GB] MIAA-001 MINAMO Special Debut">[FHD/3.2GB] MIAA-001 MINAMO Special Debut</a>
        </td>
        <td class="text-center">
          <a href="/download/1234567.torrent"><i class="fa fa-download"></i></a>
          <a href="magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&amp;dn=MIAA-001"><i class="fa fa-magnet"></i></a>
        </td>
        <td class="text-center">3.2 GiB</td>
        <td class="text-center" data-timestamp="1724112000">2026-08-20 00:00</td>
        <td class="text-center" style="color: green;">45</td>
        <td class="text-center" style="color: red;">5</td>
        <td class="text-center">200</td>
      </tr>
      <tr class="success">
        <td><a href="/?c=2_2" title="Real Life - Video"><img src="/static/img/icons/nyaa/2_2.png" alt="Real Life - Video"></a></td>
        <td colspan="2">
          <a href="/view/1234568" title="[4K] SSIS-567 Rena Miyashita">[4K] SSIS-567 Rena Miyashita</a>
        </td>
        <td class="text-center">
          <a href="/download/1234568.torrent"><i class="fa fa-download"></i></a>
          <a href="magnet:?xt=urn:btih:abcdef0123456789abcdef0123456789abcdef01&amp;dn=SSIS-567"><i class="fa fa-magnet"></i></a>
        </td>
        <td class="text-center">5.8 GiB</td>
        <td class="text-center" data-timestamp="1724112000">2026-08-20 00:00</td>
        <td class="text-center" style="color: green;">12</td>
        <td class="text-center" style="color: red;">2</td>
        <td class="text-center">80</td>
      </tr>
    </tbody>
  </table>
</div>
</body>
</html>
"""

SAMPLE_SUKEBEI_DETAILS_HTML = """
<!DOCTYPE html>
<html>
<body>
<div class="panel panel-default">
  <div class="panel-heading">
    <h3 class="panel-title">[FHD/3.2GB] MIAA-001 MINAMO Special Debut</h3>
  </div>
  <div class="panel-body">
    Detailed descriptions here...
  </div>
  <div class="panel-footer clearfix">
    <a href="/download/1234567.torrent" class="card-footer-item"><i class="fa fa-download"></i> Download Torrent</a>
    <a href="magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&amp;dn=MIAA-001" class="card-footer-item"><i class="fa fa-magnet"></i> Magnet Download</a>
  </div>
</div>
</body>
</html>
"""


def test_sukebei_search():
    config = {"request_timeout": 20}
    with patch.object(sukebei, "_fetch_url", return_value=(True, SAMPLE_SUKEBEI_SEARCH_HTML)) as mock_fetch:
        results = sukebei.search("MIAA-001", category="2_2", config=config)
        mock_fetch.assert_called_once_with(
            "https://sukebei.nyaa.si/?f=0&c=2_2&q=MIAA-001&s=seeders&o=desc",
            config,
        )

        assert len(results) == 2

        item1 = results[0]
        assert item1["id"] == "sukebei:1234567"
        assert item1["title"] == "[FHD/3.2GB] MIAA-001 MINAMO Special Debut"
        assert item1["details_url"] == "https://sukebei.nyaa.si/view/1234567"
        assert "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567" in item1["magnet_url"]
        assert item1["size"] == "3.2 GiB"
        assert item1["seeders"] == "45"
        assert item1["leechers"] == "5"

        item2 = results[1]
        assert item2["id"] == "sukebei:1234568"
        assert item2["title"] == "[4K] SSIS-567 Rena Miyashita"
        assert item2["details_url"] == "https://sukebei.nyaa.si/view/1234568"
        assert "magnet:?xt=urn:btih:abcdef0123456789abcdef0123456789abcdef01" in item2["magnet_url"]
        assert item2["size"] == "5.8 GiB"
        assert item2["seeders"] == "12"
        assert item2["leechers"] == "2"


def test_sukebei_search_empty_or_error():
    config = {}
    with patch.object(sukebei, "_fetch_url", return_value=(False, "error message")):
        results = sukebei.search("nonexistent", config=config)
        assert results == []


def test_sukebei_resolve_magnet_from_page():
    config = {}
    with patch.object(sukebei, "_fetch_url", return_value=(True, SAMPLE_SUKEBEI_DETAILS_HTML)):
        magnet = sukebei.resolve_magnet("https://sukebei.nyaa.si/view/1234567", config=config)
        assert magnet == "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=MIAA-001"

    with patch.object(sukebei, "_fetch_url", return_value=(True, "<html><body>No magnet here</body></html>")):
        magnet = sukebei.resolve_magnet("https://sukebei.nyaa.si/view/9999999", config=config)
        assert magnet is None

    with patch.object(sukebei, "_fetch_url", return_value=(False, "network error")):
        magnet = sukebei.resolve_magnet("https://sukebei.nyaa.si/view/1234567", config=config)
        assert magnet is None

