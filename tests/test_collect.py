import pytest
from meridian_x.sources.xxxclub import discover, is_whitelisted_title


def test_is_whitelisted_title():
    config = {
        "classify": {
            "artist_folders": ["Dakota Doll"],
            "studio_folders": ["ExxxtraSmall", "Vixen"],
        },
        "genres": {
            "Vixen": {"prefixes": ["tushy"]},
        },
    }
    assert is_whitelisted_title("ExxxtraSmall.26.07.18.Remi.Raw.mp4", config) is True
    assert is_whitelisted_title("Tushy.26.06.28.Alina.Lopez.mp4", config) is True
    assert is_whitelisted_title("Dakota.Doll.OhMyHoles.mp4", config) is True
    assert is_whitelisted_title("UnknownStudio.26.07.18.Random.mp4", config) is False


def test_discover_selective_filtering(mocker):
    rss_xml = """<rss><channel>
    <item><title>ExxxtraSmall.26.07.18.Remi.Raw.mp4</title><link>magnet:?xt=urn:btih:1111111111111111111111111111111111111111</link></item>
    <item><title>UnknownStudio.26.07.18.Random.mp4</title><link>magnet:?xt=urn:btih:2222222222222222222222222222222222222222</link></item>
    </channel></rss>"""
    mock_resp = mocker.Mock()
    mock_resp.text = rss_xml
    mock_resp.raise_for_status = mocker.Mock()
    mocker.patch("requests.get", return_value=mock_resp)

    config = {
        "rss_url": "https://example.com/rss",
        "selective_only": True,
        "classify": {"studio_folders": ["ExxxtraSmall"]},
    }

    items = discover(config)
    assert len(items) == 1
    assert items[0]["title"] == "ExxxtraSmall.26.07.18.Remi.Raw.mp4"

    config["selective_only"] = False
    items_all = discover(config)
    assert len(items_all) == 2
