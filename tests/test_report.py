import subprocess
from unittest.mock import MagicMock, patch
import pytest

from meridian_x import report


def test_report_ssh_calls_run_remote_ssh():
    remote = {"host": "nas.local", "user": "media", "path": "/volume1/Media/complete"}
    with patch("meridian_x.report.run_remote_ssh") as mock_run_ssh:
        mock_run_ssh.return_value = subprocess.CompletedProcess(
            args=["ssh"], returncode=0, stdout="output\n", stderr=""
        )
        ok, out = report._ssh(remote, "df -h")
        assert ok is True
        assert out == "output\n"
        mock_run_ssh.assert_called_once_with(
            host="nas.local",
            command="df -h",
            user="media",
            timeout=60,
        )


def test_report_ssh_error_handling():
    remote = {"host": "nas.local", "user": "media"}
    with patch("meridian_x.report.run_remote_ssh") as mock_run_ssh:
        mock_run_ssh.return_value = subprocess.CompletedProcess(
            args=["ssh"], returncode=1, stdout="", stderr="connection refused"
        )
        ok, out = report._ssh(remote, "df -h")
        assert ok is False
        assert "connection refused" in out


def test_humanize():
    assert report._humanize(500) == "500B"
    assert report._humanize(1024) == "1K"
    assert report._humanize(1024 * 1024 * 5) == "5M"
    assert report._humanize(1024 * 1024 * 1024 * 2) == "2G"


def test_disk_status_success(caplog):
    import logging
    caplog.set_level(logging.INFO)
    remote = {"host": "nas.local", "user": "media", "path": "/volume1/Media/complete"}

    sample_output = (
        "===DF===\n"
        "/dev/sda1 100G 40G 60G 40% /volume1\n"
        "===DU===\n"
        "1048576 10 ./folder1\n"
        "524288 5 ./folder2\n"
    )

    with patch("meridian_x.report._ssh", return_value=(True, sample_output)):
        report.disk_status(remote)

    assert "Filesystem : /dev/sda1" in caplog.text
    assert "folder1" in caplog.text
    assert "folder2" in caplog.text


def test_disk_status_failure(caplog):
    import logging
    caplog.set_level(logging.ERROR)
    remote = {"host": "nas.local", "user": "media", "path": "/volume1/Media/complete"}

    with patch("meridian_x.report._ssh", return_value=(False, "Permission denied")):
        report.disk_status(remote)

    assert "disk 상태 조회 실패" in caplog.text


def test_transmission_status(caplog):
    import logging
    caplog.set_level(logging.INFO)

    mock_client = MagicMock()
    mock_client.get_torrents_status.return_value = [
        {"status": 4, "rateDownload": 1024 * 1024, "rateUpload": 0, "uploadRatio": 1.5},
        {"status": 6, "rateDownload": 0, "rateUpload": 512 * 1024, "uploadRatio": 2.0},
    ]

    report.transmission_status(mock_client)

    assert "총 토렌트: 2" in caplog.text
    assert "downloading" in caplog.text
    assert "seeding" in caplog.text
