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


def test_is_whitelisted_title_west_only():
    config = {
        "classify": {
            "artists": {
                "WEST": ["Dakota Doll", "Molli Little"],
                "JPN": ["MINAMO"],
            },
            "studios": {
                "WEST": {
                    "Vixen": ["vixen", "tushy"],
                    "TeamSkeet": ["tiny4k"],
                }
            },
        }
    }
    # Matches WEST artist or WEST studio
    assert is_whitelisted_title("Dakota.Doll.OhMyHoles.mp4", config) is True
    assert is_whitelisted_title("Tushy.26.06.28.Alina.Lopez.mp4", config) is True
    # JPN artist is EXCLUDED from xxxclub whitelist
    assert is_whitelisted_title("MINAMO.FNS-237.mp4", config) is False
    # Unmatched title
    assert is_whitelisted_title("UnknownStudio.26.07.18.Random.mp4", config) is False


def test_is_whitelisted_title_artist_matches_onlyfans():
    config = {
        "classify": {
            "artists": {
                "WEST": ["Dakota Doll"],
            },
            "studios": {
                "WEST": {
                    "Vixen": ["vixen"],
                }
            },
        }
    }
    # OnlyFans with registered artist -> True (matched by artist)
    assert is_whitelisted_title("OnlyFans Dakota Doll Solo 1080p", config) is True
    # OnlyFans without registered artist -> False (not matched)
    assert is_whitelisted_title("OnlyFans Random Creator Solo 1080p", config) is False


# --- run_transmission / run_favorite 테스트 ---

import types

from meridian_x.collect import run_favorite, run_transmission


def _make_fake_source(discover_items, favorite_items):
    calls = {"discover": 0, "discover_favorite": 0}

    def discover(cfg):
        calls["discover"] += 1
        return list(discover_items)

    def discover_favorite(cfg):
        calls["discover_favorite"] += 1
        return list(favorite_items)

    def resolve(item, cfg):
        return {"type": "magnet", "data": f"magnet:?xt=urn:btih:{item['id']}"}

    return types.SimpleNamespace(
        discover=discover, discover_favorite=discover_favorite, resolve=resolve
    ), calls


def _run_collect(mocker, src_config, fake_src):
    config = {
        "sources": {"fakesrc": src_config},
        "transmission": {
            "rpc_url": "http://127.0.0.1:9091/transmission/rpc",
            "stop_after_download": False,
        },
        "collection": {},
    }
    mocker.patch("meridian_x.collect.load_config", return_value=config)
    mocker.patch("meridian_x.collect.SOURCES", {"fakesrc": fake_src})
    db = mocker.patch("meridian_x.collect.MeridianDB").return_value
    db.get_download_history.return_value = set()
    tx = mocker.patch("meridian_x.collect.TransmissionClient").return_value
    tx.add_magnet.return_value = True
    run_transmission(max_count=30, dry_run=False)
    return tx, db


def test_run_transmission_ignores_favorites(mocker):
    # transmission 수집은 RSS 전용 — favorite 자동 병합 없음
    fake_src, calls = _make_fake_source(
        [{"id": "onejav:A", "title": "A"}],
        [{"id": "onejav:B", "title": "B"}],
    )
    tx, _ = _run_collect(mocker, {"enabled": True, "favorite_url": "https://onejav.com/favorite/T"}, fake_src)
    assert calls["discover"] == 1
    assert calls["discover_favorite"] == 0
    assert tx.add_magnet.call_count == 1
    assert tx.add_magnet.call_args.args[0] == "magnet:?xt=urn:btih:onejav:A"


def test_run_favorite_processes_favorites_only(mocker):
    # meridian favorite — discover_favorite만 호출, RSS discover는 호출 안 함
    fake_src, calls = _make_fake_source(
        [{"id": "onejav:A", "title": "A"}],
        [{"id": "onejav:FAV1", "title": "F1"}, {"id": "onejav:FAV2", "title": "F2"}],
    )
    config = {
        "sources": {"fakesrc": {"enabled": True, "favorite_url": "https://onejav.com/favorite/T"}},
        "transmission": {
            "rpc_url": "http://127.0.0.1:9091/transmission/rpc",
            "stop_after_download": False,
        },
        "collection": {},
    }
    mocker.patch("meridian_x.collect.load_config", return_value=config)
    mocker.patch("meridian_x.collect.SOURCES", {"fakesrc": fake_src})
    db = mocker.patch("meridian_x.collect.MeridianDB").return_value
    db.get_download_history.return_value = set()
    tx = mocker.patch("meridian_x.collect.TransmissionClient").return_value
    tx.add_magnet.return_value = True
    run_favorite(dry_run=False)
    assert calls["discover_favorite"] == 1
    assert calls["discover"] == 0
    assert tx.add_magnet.call_count == 2
    assert db.add_download_history.called


def test_run_favorite_skips_history(mocker):
    # 이미 수집된 favorite 항목은 history로 스킵
    fake_src, _ = _make_fake_source(
        [{"id": "onejav:A", "title": "A"}],
        [{"id": "onejav:FAV1", "title": "F1"}],
    )
    config = {
        "sources": {"fakesrc": {"enabled": True, "favorite_url": "https://onejav.com/favorite/T"}},
        "transmission": {
            "rpc_url": "http://127.0.0.1:9091/transmission/rpc",
            "stop_after_download": False,
        },
        "collection": {},
    }
    mocker.patch("meridian_x.collect.load_config", return_value=config)
    mocker.patch("meridian_x.collect.SOURCES", {"fakesrc": fake_src})
    db = mocker.patch("meridian_x.collect.MeridianDB").return_value
    db.get_download_history.return_value = {"onejav:FAV1"}
    tx = mocker.patch("meridian_x.collect.TransmissionClient").return_value
    tx.add_magnet.return_value = True
    run_favorite(dry_run=False)
    assert tx.add_magnet.call_count == 0


def test_run_favorite_no_favorite_url_noop(mocker):
    # favorite_url 미설정 소스는 조용히 스킵
    fake_src, calls = _make_fake_source(
        [{"id": "onejav:A", "title": "A"}],
        [{"id": "onejav:FAV1", "title": "F1"}],
    )
    config = {
        "sources": {"fakesrc": {"enabled": True}},
        "transmission": {
            "rpc_url": "http://127.0.0.1:9091/transmission/rpc",
            "stop_after_download": False,
        },
        "collection": {},
    }
    mocker.patch("meridian_x.collect.load_config", return_value=config)
    mocker.patch("meridian_x.collect.SOURCES", {"fakesrc": fake_src})
    db = mocker.patch("meridian_x.collect.MeridianDB").return_value
    db.get_download_history.return_value = set()
    tx = mocker.patch("meridian_x.collect.TransmissionClient").return_value
    run_favorite(dry_run=False)
    assert calls["discover_favorite"] == 0
    assert tx.add_magnet.call_count == 0


def test_filter_and_send_ranks_by_taste_and_preserves_ties(mocker):
    from meridian_x.collect import _filter_and_send

    resolved_ids = []
    fake_src = mocker.MagicMock()
    fake_src.resolve.side_effect = lambda item, cfg: (resolved_ids.append(item["id"]) or {"type": "magnet", "data": f"magnet:{item['id']}"})
    tx = mocker.MagicMock()
    tx.add_magnet.return_value = True
    db = mocker.MagicMock()

    items = [
        {"id": "s:1", "title": "Random.First.1080p.mp4"},
        {"id": "s:2", "title": "Random.Second.1080p.mp4"},
        {"id": "s:3", "title": "Kubera.Fortuna.Scene.1080p.mp4"},
    ]
    cfg = {"classify": {"artists": {"WEST": ["Kubera Fortuna"]}}, "scoring": {"enabled": True, "min_score": 0.0}}
    stats = {"actor": {"Kubera Fortuna": 25}, "studio": {}}

    sent = _filter_and_send(fake_src, "s", cfg, items, tx, db, set(), {}, None, remaining=2, dry_run=False, retention_stats=stats)
    assert sent == 2
    assert resolved_ids == ["s:3", "s:1"]


def test_filter_and_send_min_score_cutoff(mocker):
    from meridian_x.collect import _filter_and_send

    resolved_ids = []
    fake_src = mocker.MagicMock()
    fake_src.resolve.side_effect = lambda item, cfg: (resolved_ids.append(item["id"]) or {"type": "magnet", "data": f"magnet:{item['id']}"})
    tx = mocker.MagicMock()
    tx.add_magnet.return_value = True
    db = mocker.MagicMock()

    items = [
        {"id": "s:1", "title": "Random.Unknown.1080p.mp4"},
        {"id": "s:2", "title": "Kubera.Fortuna.Scene.1080p.mp4"},
    ]
    cfg = {"classify": {"artists": {"WEST": ["Kubera Fortuna"]}}, "scoring": {"enabled": True, "min_score": 20.0}}

    sent = _filter_and_send(fake_src, "s", cfg, items, tx, db, set(), {}, None, remaining=5, dry_run=False, retention_stats={})
    assert sent == 1
    assert resolved_ids == ["s:2"]


def test_filter_and_send_scoring_disabled(mocker):
    from meridian_x.collect import _filter_and_send

    resolved_ids = []
    fake_src = mocker.MagicMock()
    fake_src.resolve.side_effect = lambda item, cfg: (resolved_ids.append(item["id"]) or {"type": "magnet", "data": f"magnet:{item['id']}"})
    tx = mocker.MagicMock()
    tx.add_magnet.return_value = True
    db = mocker.MagicMock()

    items = [
        {"id": "s:1", "title": "Random.First.1080p.mp4"},
        {"id": "s:2", "title": "Kubera.Fortuna.Scene.1080p.mp4"},
    ]
    cfg = {"classify": {"artists": {"WEST": ["Kubera Fortuna"]}}, "scoring": {"enabled": False, "min_score": 50.0}}

    sent = _filter_and_send(fake_src, "s", cfg, items, tx, db, set(), {}, None, remaining=1, dry_run=False, retention_stats={})
    assert sent == 1
    assert resolved_ids == ["s:1"]



