import pytest
from unittest.mock import patch, MagicMock
from meridian_x.sources import SOURCES
import meridian_x.sources.torrentgalaxy as tgx

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:torrent="https://torrentgalaxy.to">
  <channel>
    <title>TorrentGalaxy RSS</title>
    <item>
      <title>Vixen 26 08 20 Angela White Passionate Night XXX 1080p MP4-WRB</title>
      <link>https://torrentgalaxy.to/torrent/150001/Vixen-26-08-20-Angela-White</link>
      <enclosure url="magnet:?xt=urn:btih:TGXHASH1&amp;dn=Vixen+Angela+White" length="2500000000" type="application/x-bittorrent" />
      <pubDate>Thu, 20 Aug 2026 12:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Random 720p Video Low Quality</title>
      <link>https://torrentgalaxy.to/torrent/150002/Random-720p</link>
      <enclosure url="magnet:?xt=urn:btih:TGXHASH2" length="1000000000" type="application/x-bittorrent" />
    </item>
  </channel>
</rss>
"""

def test_tgx_registration():
    assert "torrentgalaxy" in SOURCES
    assert "tgx" in SOURCES
    assert SOURCES["torrentgalaxy"] is tgx
    assert SOURCES["tgx"] is tgx

def test_tgx_is_whitelisted_title():
    config = {
        "classify": {
            "artists": {"WEST": {"Angela White": ["angela white"]}},
            "studios": {"WEST": {"Vixen": ["vixen"]}}
        }
    }
    # Whitelisted artist + 1080p -> True
    assert tgx.is_whitelisted_title("Vixen 26 08 20 Angela White XXX 1080p MP4-WRB", config) is True
    # Whitelisted studio + 4K -> True
    assert tgx.is_whitelisted_title("Vixen 4K UHD Special Release", config) is True
    # Low resolution 720p -> False
    assert tgx.is_whitelisted_title("Vixen 720p Angela White", config) is False
    # Non-whitelisted -> False
    assert tgx.is_whitelisted_title("Unknown Actress 1080p Release", config) is False

def test_tgx_discover_and_resolve():
    config = {
        "classify": {
            "artists": {"WEST": {"Angela White": ["angela white"]}},
            "studios": {"WEST": {"Vixen": ["vixen"]}}
        }
    }
    with patch.object(tgx, "_fetch_url", return_value=(True, SAMPLE_RSS)):
        items = tgx.discover(config)
        assert len(items) == 1
        assert items[0]["id"] == "tgx:150001"
        assert "Angela White" in items[0]["title"]
        assert items[0]["magnet_url"].startswith("magnet:?xt=urn:btih:TGXHASH1")

        resolved = tgx.resolve(items[0], config)
        assert resolved is not None
        assert resolved["magnet_url"] == items[0]["magnet_url"]
        assert resolved.get("type") == "magnet"

def test_tgx_remote_config():
    cfg1 = {"sources": {"torrentgalaxy": {"remote": {"ssh_alias": "lt"}}}}
    assert tgx._tgx_remote(cfg1) == {"ssh_alias": "lt"}

    cfg2 = {"sources": {"tgx": {"remote": {"ssh_alias": "lt-tgx"}}}}
    assert tgx._tgx_remote(cfg2) == {"ssh_alias": "lt-tgx"}

    cfg3 = {"remote": {"ssh_alias": "lt-global"}}
    assert tgx._tgx_remote(cfg3) == {"ssh_alias": "lt-global"}

def test_tgx_fetch_url_mirror_fallback():
    config = {
        "sources": {
            "torrentgalaxy": {
                "mirrors": ["https://tgx.rs", "https://torrentgalaxy.mx"]
            }
        }
    }
    # Mock requests.get: primary fails, secondary succeeds
    mock_resp_fail = MagicMock(status_code=500, text="")
    mock_resp_ok = MagicMock(status_code=200, text="<rss></rss>")

    def side_effect(url, **kwargs):
        if "torrentgalaxy.to" in url:
            raise Exception("Connection timeout")
        return mock_resp_ok

    with patch("requests.get", side_effect=side_effect):
        ok, content = tgx._fetch_url("https://torrentgalaxy.to/rss?cat=42", config, candidate_urls=["https://torrentgalaxy.to/rss?cat=42", "https://tgx.rs/rss?cat=42"])
        assert ok is True
        assert content == "<rss></rss>"
