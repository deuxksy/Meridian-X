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
