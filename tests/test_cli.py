"""
cli.py 인자 파싱 회귀 테스트
"""
from unittest.mock import patch

import pytest

from meridian_x.cli import main


def test_favorite_flag_removed(capsys, mocker):
    mocker.patch("meridian_x.collect.run_transmission")
    with patch("sys.argv", ["meridian", "transmission", "--source", "onejav", "--favorite", "https://onejav.com/x"]):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 2
        assert "unrecognized arguments" in capsys.readouterr().err


def test_favorite_command_dispatches_run_favorite(mocker):
    rf = mocker.patch("meridian_x.collect.run_favorite")
    with patch("sys.argv", ["meridian", "favorite", "--dry-run"]):
        main()
    rf.assert_called_once()
    assert rf.call_args.kwargs.get("dry_run") is True
