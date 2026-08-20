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


SAMPLE_SEARCH_HTML = """
<!DOCTYPE html>
<html>
<body>
<div class="tgxtable">
  <div class="tgxtablerow txlight">
    <div class="tgxtablecell shrink"><a href="/torrents.php?cat=42"><img src="/common/images/cat/42.png" alt="XXX"></a></div>
    <div class="tgxtablecell shrink"><a href="/torrents.php?parent_cat=XXX">XXX</a></div>
    <div class="tgxtablecell" style="text-align:left;">
      <a class="txlight" href="/torrent/160001/Vixen-26-08-20-Angela-White-Passionate-Night-XXX-1080p-MP4" title="Vixen 26 08 20 Angela White Passionate Night XXX 1080p MP4"><b>Vixen 26 08 20 Angela White Passionate Night XXX 1080p MP4</b></a>
    </div>
    <div class="tgxtablecell shrink">
      <a href="magnet:?xt=urn:btih:TGXSEARCHHASH1&amp;dn=Vixen+Angela+White+1080p" role="button"><i class="fa fa-magnet"></i></a>
      <a href="/torrents.php?search=..."><i class="fa fa-download"></i></a>
    </div>
    <div class="tgxtablecell shrink"><span class="badge badge-secondary">2.85 GB</span></div>
    <div class="tgxtablecell shrink"><span style="color:green"><b>150</b></span></div>
    <div class="tgxtablecell shrink"><span style="color:red"><b>12</b></span></div>
    <div class="tgxtablecell shrink"><span>Uploader1</span></div>
  </div>
  <div class="tgxtablerow txlight">
    <div class="tgxtablecell shrink"><a href="/torrents.php?cat=42"><img src="/common/images/cat/42.png" alt="XXX"></a></div>
    <div class="tgxtablecell shrink"><a href="/torrents.php?parent_cat=XXX">XXX</a></div>
    <div class="tgxtablecell" style="text-align:left;">
      <a class="txlight" href="/torrent/160002/Angela-White-Blacked-4K-2160p" title="Angela White Blacked 4K 2160p"><b>Angela White Blacked 4K 2160p</b></a>
    </div>
    <div class="tgxtablecell shrink">
      <a href="magnet:?xt=urn:btih:TGXSEARCHHASH2&amp;dn=Angela+White+4K" role="button"><i class="fa fa-magnet"></i></a>
    </div>
    <div class="tgxtablecell shrink"><span class="badge badge-secondary">6.50 GB</span></div>
    <div class="tgxtablecell shrink"><span style="color: green"><b>300</b></span></div>
    <div class="tgxtablecell shrink"><span style="color: red"><b>25</b></span></div>
  </div>
  <div class="tgxtablerow txlight">
    <div class="tgxtablecell shrink"><a href="/torrents.php?cat=42"><img src="/common/images/cat/42.png" alt="XXX"></a></div>
    <div class="tgxtablecell shrink"><a href="/torrents.php?parent_cat=XXX">XXX</a></div>
    <div class="tgxtablecell" style="text-align:left;">
      <a class="txlight" href="/torrent/160003/Angela-White-Old-Clip-720p" title="Angela White Old Clip 720p"><b>Angela White Old Clip 720p</b></a>
    </div>
    <div class="tgxtablecell shrink">
      <a href="magnet:?xt=urn:btih:TGXSEARCHHASH3&amp;dn=Angela+White+720p" role="button"><i class="fa fa-magnet"></i></a>
    </div>
    <div class="tgxtablecell shrink"><span class="badge badge-secondary">850 MB</span></div>
    <div class="tgxtablecell shrink"><font color="green"><b>40</b></font></div>
    <div class="tgxtablecell shrink"><font color="red"><b>2</b></font></div>
  </div>
</div>
</body>
</html>
"""

SAMPLE_DETAILS_HTML = """
<!DOCTYPE html>
<html>
<body>
<div class="panel-body">
  <h3>Angela White Special 1080p</h3>
  <div class="btn-group">
    <a class="btn btn-danger" href="magnet:?xt=urn:btih:TGXDETAILSHASH99&amp;dn=Angela+White+Special">Magnet</a>
  </div>
</div>
</body>
</html>
"""


def test_tgx_parse_search_html_fhd_filter():
    items = tgx._parse_search_html(SAMPLE_SEARCH_HTML, "https://torrentgalaxy.to")
    # Only 1080p and 4K should pass, 720p filtered
    assert len(items) == 2

    assert items[0]["id"] == "tgx:160001"
    assert items[0]["title"] == "Vixen 26 08 20 Angela White Passionate Night XXX 1080p MP4"
    assert items[0]["details_url"] == "https://torrentgalaxy.to/torrent/160001/Vixen-26-08-20-Angela-White-Passionate-Night-XXX-1080p-MP4"
    assert items[0]["magnet_url"] == "magnet:?xt=urn:btih:TGXSEARCHHASH1&dn=Vixen+Angela+White+1080p"
    assert items[0]["size"] == "2.85 GB"
    assert items[0]["seeders"] == "150"
    assert items[0]["leechers"] == "12"

    assert items[1]["id"] == "tgx:160002"
    assert items[1]["title"] == "Angela White Blacked 4K 2160p"
    assert items[1]["size"] == "6.50 GB"
    assert items[1]["seeders"] == "300"
    assert items[1]["leechers"] == "25"


def test_tgx_parse_search_html_allow_all_quality():
    items = tgx._parse_search_html(SAMPLE_SEARCH_HTML, "https://torrentgalaxy.to", allow_all_quality=True)
    assert len(items) == 3
    assert items[2]["id"] == "tgx:160003"
    assert items[2]["title"] == "Angela White Old Clip 720p"
    assert items[2]["size"] == "850 MB"
    assert items[2]["seeders"] == "40"
    assert items[2]["leechers"] == "2"


def test_tgx_search():
    config = {
        "sources": {
            "torrentgalaxy": {
                "base_url": "https://torrentgalaxy.to",
                "mirrors": ["https://tgx.rs"],
            }
        }
    }
    with patch.object(tgx, "_fetch_url", return_value=(True, SAMPLE_SEARCH_HTML)) as mock_fetch:
        items = tgx.search("Angela White", category="42", config=config)
        assert len(items) == 2
        mock_fetch.assert_called_once()
        called_url = mock_fetch.call_args[0][0]
        assert "torrentgalaxy.to/torrents.php?search=Angela+White&cat=42&sort=seeders&order=desc" in called_url
        candidate_urls = mock_fetch.call_args[1].get("candidate_urls") or mock_fetch.call_args[0][2]
        assert any("tgx.rs" in u for u in candidate_urls)


def test_tgx_resolve_magnet_direct_item():
    item = {"magnet_url": "magnet:?xt=urn:btih:DIRECT123"}
    assert tgx.resolve_magnet(item) == "magnet:?xt=urn:btih:DIRECT123"


def test_tgx_resolve_magnet_direct_string():
    assert tgx.resolve_magnet("magnet:?xt=urn:btih:DIRECT456") == "magnet:?xt=urn:btih:DIRECT456"


def test_tgx_resolve_magnet_details_fetch():
    item = {"details_url": "https://torrentgalaxy.to/torrent/160001/Angela-White"}
    with patch.object(tgx, "_fetch_url", return_value=(True, SAMPLE_DETAILS_HTML)):
        magnet = tgx.resolve_magnet(item)
        assert magnet == "magnet:?xt=urn:btih:TGXDETAILSHASH99&dn=Angela+White+Special"


def test_tgx_resolve_magnet_url_string():
    with patch.object(tgx, "_fetch_url", return_value=(True, SAMPLE_DETAILS_HTML)):
        magnet = tgx.resolve_magnet("https://torrentgalaxy.to/torrent/160001/Angela-White")
        assert magnet == "magnet:?xt=urn:btih:TGXDETAILSHASH99&dn=Angela+White+Special"


def test_tgx_resolve_magnet_failure():
    with patch.object(tgx, "_fetch_url", return_value=(False, "error")):
        assert tgx.resolve_magnet("https://torrentgalaxy.to/torrent/invalid") is None
    assert tgx.resolve_magnet({}) is None
    assert tgx.resolve_magnet("") is None

