import pytest
from meridian_x.jav_lookup import extract_jav_code, lookup_jav_actresses

def test_extract_jav_code():
    assert extract_jav_code("ABF-364.mp4") == "ABF-364"
    assert extract_jav_code("FNS-158-{FALENO star}-[None].mp4") == "FNS-158"
    assert extract_jav_code("random_western_video.mp4") is None

def test_lookup_jav_actresses_mock(mocker):
    html = """
    <div class="card-content"><h5 class="title"><a href="/torrent/snos188">SNOS188</a></h5>
      <div class="panel"><a href="/actress/iroha">博多彩葉</a></div></div>
    <div class="card-content"><h5 class="title"><a href="/torrent/snos187">SNOS187</a></h5>
      <div class="panel"><a href="/actress/nia">白花にあ</a><a href="/tag/solo">Solo</a></div></div>
    """
    mocker.patch("meridian_x.jav_lookup._ssh_curl", return_value=html)
    assert lookup_jav_actresses("SNOS-187", {}) == ["白花にあ"]
    assert lookup_jav_actresses("SNOS-189", {}) == []
    mocker.patch("meridian_x.jav_lookup._ssh_curl", return_value=html.replace("/actress/", "/tag/"))
    assert lookup_jav_actresses("SNOS-187", {}) == []


def test_fetch_page_via_ssh():
    from unittest.mock import patch
    from meridian_x.jav_lookup import _fetch_page_via_ssh

    config = {"sources": {"onejav": {"remote": {"ssh_alias": "lt-custom"}}}}
    with patch("meridian_x.jav_lookup.fetch_remote_curl", return_value="<html></html>") as mock_fetch:
        res = _fetch_page_via_ssh("https://example.com", config=config, timeout=10)
        assert res == "<html></html>"
        mock_fetch.assert_called_once_with("https://example.com", ssh_alias="lt-custom", timeout=10)


def test_lookup_jav321_via_ssh():
    from unittest.mock import patch
    from meridian_x.jav_lookup import _lookup_jav321_via_ssh

    mock_html = """
    <html>
    <head><title>SONE-446 Special Title sone- bittorrent</title></head>
    <body>
        <a href="/star/recommended">Other performer</a>
        <div class="col-md-9"><b>品番</b>: sone-446<br>
        <b>出演者</b>: MINAMO、<a href="/star/another">Another Performer</a><br>
        <a href="/company/s1">S1 NO.1 STYLE</a>
        <a href="/genre/hd">HD</a>
        <a href="/genre/single">Single</a></div>
    </body>
    </html>
    """
    with patch("meridian_x.jav_lookup.fetch_remote_curl", return_value=mock_html) as mock_fetch:
        res = _lookup_jav321_via_ssh("SONE-446", ssh_alias="lt", timeout=15)
        assert res["title"] == "SONE-446 Special Title"
        assert res["actresses"] == ["MINAMO", "Another Performer"]
        assert res["makers"] == ["S1 NO.1 STYLE"]
        assert "Single" in res["genres"]
        mock_fetch.assert_called_once_with("https://www.jav321.com/video/sone00446", ssh_alias="lt", timeout=15)
        assert not _lookup_jav321_via_ssh("SONE-447")["actresses"]


def test_lookup_javbus_via_ssh():
    from unittest.mock import patch
    from meridian_x.jav_lookup import _lookup_javbus_via_ssh

    mock_html = """
    <html>
    <head><title>SONE-446 JavBus Title - JavBus</title></head>
    <body>
        <a href="/star/other">Recommendation</a>
        <div class="movie"><div class="info"><p><span>識別碼:</span><span>SONE-446</span></p>
        <a href="/star/minamo">MINAMO</a>
        <a href="/studio/s1">S1 NO.1 STYLE</a>
        <a href="/genre/single">Single</a></div></div>
    </body>
    </html>
    """
    with patch("meridian_x.jav_lookup.fetch_remote_curl", return_value=mock_html) as mock_fetch:
        res = _lookup_javbus_via_ssh("SONE-446", ssh_alias="lt", timeout=15)
        assert res["title"] == "SONE-446 JavBus Title"
        assert res["actresses"] == ["MINAMO"]
        assert res["makers"] == ["S1 NO.1 STYLE"]
        assert "Single" in res["genres"]
        mock_fetch.assert_called_once_with("https://www.javbus.com/SONE-446", ssh_alias="lt", timeout=15)
        assert not _lookup_javbus_via_ssh("SONE-44")["actresses"]


def test_lookup_web_jav_metadata_fallback():
    from unittest.mock import patch
    from meridian_x.jav_lookup import lookup_web_jav_metadata

    # Jav321 returns empty, JavBus returns data
    empty_321 = {"actresses": [], "makers": [], "genres": [], "title": None}
    bus_data = {"actresses": ["MINAMO"], "makers": ["S1"], "genres": ["Single"], "title": "Title"}

    with patch("meridian_x.jav_lookup._lookup_jav321_via_ssh", return_value=empty_321) as mock_321, \
         patch("meridian_x.jav_lookup._lookup_javbus_via_ssh", return_value=bus_data) as mock_bus:
        res = lookup_web_jav_metadata("SONE-446", config={})
        assert res == bus_data
        mock_321.assert_called_once()
        mock_bus.assert_called_once()


