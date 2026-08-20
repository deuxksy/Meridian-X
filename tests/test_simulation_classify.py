"""시뮬레이션 기반 classify 로직 단위 테스트"""
import pytest
from unittest.mock import patch, MagicMock
from meridian_x.classify import run as classify_run


def test_simulation_classify_dry_run(caplog):
    simulation_files = [
        "WowGirls/wowgirls.18.08.31.shrima.malati.stefanie.moon.and.elle.rose.incredible.foursome.mp4",
        "WowGirls/wowgirls.18.09.14.cayla.and.alexa.tomas.beautiful.daybreak.mp4",
        "Wowgirls/wowgirls.23.05.02.alissa.foxy.kinky.moods.mp4",
        "Wowgirls/wowgirls.23.05.06.evelin.elle.gorgeous.date.mp4",
    ]

    mock_config = {
        "remote": {"host": "test.host", "path": "/test/media"},
        "classify": {
            "video_extensions": [".mp4", ".mkv"],
            "studios": {"WEST": {"WowGirls": "WowGirls", "Wowgirls": "WowGirls"}},
            "artists": {"WEST": {}, "JPN": {}},
        },
    }

    with patch("meridian_x.classify.load_config", return_value=mock_config):
        with patch("meridian_x.classify._move_file", return_value="moved") as mock_move:
            classify_run(
                dry_run=True,
                refresh=False,
                simulation_files=simulation_files,
                no_lookup=True,
            )
            assert mock_move.call_count == len(simulation_files)