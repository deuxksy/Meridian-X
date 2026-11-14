"""
onejav.py 즐겨찾기 페이지 수집 경로 단위 테스트
"""
from meridian_x.sources.onejav import (
    _parse_favorite,
    discover_favorite,
    resolve,
)

FAVORITE_HTML = '''<html><body>
<a href="/torrent/suji325/download/17043913/onejav.com_suji325.torrent">dl</a>
<a href="/torrent/mvsd710_2/download/00891138/onejav.com_mvsd710_2.torrent">dl</a>
</body></html>'''


def test_parse_favorite_extracts_items():
    items = _parse_favorite(FAVORITE_HTML, "https://onejav.com")
    assert items[0]["id"] == "onejav:SUJI325"
    assert items[0]["title"] == "SUJI325"
    assert items[0]["download_url"] == "https://onejav.com/torrent/suji325/download/17043913/onejav.com_suji325.torrent"
    assert items[1]["id"] == "onejav:MVSD710_2"
    assert len(items) == 2


def test_discover_favorite_no_url_returns_empty():
    assert discover_favorite({}) == []


def test_discover_favorite_success(mocker):
    mocker.patch(
        "meridian_x.sources.onejav.fetch_via_flaresolverr",
        return_value={"html": FAVORITE_HTML, "user_agent": "UA", "cookies": {"cf_clearance": "tok"}},
    )
    items = discover_favorite({"favorite_url": "https://onejav.com/favorite/TOKEN"})
    assert items[0]["id"] == "onejav:SUJI325"
    assert items[0]["cookies"] == {"cf_clearance": "tok"}
    assert items[0]["user_agent"] == "UA"


def test_discover_favorite_flaresolverr_fail(mocker):
    mocker.patch("meridian_x.sources.onejav.fetch_via_flaresolverr", return_value=None)
    assert discover_favorite({"favorite_url": "https://onejav.com/favorite/TOKEN"}) == []


def test_discover_favorite_invalid_host_rejected(mocker):
    mocker.patch(
        "meridian_x.sources.onejav.fetch_via_flaresolverr",
        return_value={"html": FAVORITE_HTML, "user_agent": "UA", "cookies": {}},
    )
    items = discover_favorite({"favorite_url": "https://evil.com/fav"})
    assert items == []
    mocker.patch("meridian_x.sources.onejav.fetch_via_flaresolverr").assert_not_called()


def test_resolve_download_url_bypass(mocker):
    fs_mock = mocker.patch("meridian_x.sources.onejav.fetch_via_flaresolverr")
    mocker.patch("meridian_x.sources.onejav.download_via_proxy", return_value=b"BIN")
    item = {
        "id": "onejav:SUJI325",
        "download_url": "https://onejav.com/torrent/suji325/download/1/x.torrent",
        "cookies": {"cf_clearance": "tok"},
        "user_agent": "UA",
    }
    payload = resolve(item, {"proxy": "http://p:8080"})
    assert payload == {"type": "metainfo", "data": b"BIN"}
    fs_mock.assert_not_called()


def test_resolve_download_url_download_fail(mocker):
    # cf_clearance 만료 등으로 download가 None → resolve도 None (crash 없음)
    mocker.patch("meridian_x.sources.onejav.download_via_proxy", return_value=None)
    item = {
        "id": "onejav:SUJI325",
        "download_url": "https://onejav.com/torrent/suji325/download/1/x.torrent",
        "cookies": {"cf_clearance": "tok"},
        "user_agent": "UA",
    }
    assert resolve(item, {"proxy": "http://p:8080"}) is None
