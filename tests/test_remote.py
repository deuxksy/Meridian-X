import subprocess
from unittest.mock import MagicMock, patch
import pytest
from meridian_x.remote import fetch_remote_curl, run_remote_ssh


def test_fetch_remote_curl_success():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="<html>content</html>", stderr="")
        res = fetch_remote_curl("https://example.com", ssh_alias="lt", timeout=10)
        assert res == "<html>content</html>"

        args = mock_run.call_args[0][0]
        assert "ssh" in args
        assert "lt" in args
        assert "-4" in args[4]
        assert "https://example.com" in args[4]
        assert "--max-time 10" in args[4]
        assert mock_run.call_args[1]["timeout"] == 15


def test_fetch_remote_curl_error_returns_empty():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Connection failed")
        res = fetch_remote_curl("https://example.com", ssh_alias="lt")
        assert res == ""


def test_fetch_remote_curl_timeout():
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ssh", timeout=20)):
        res = fetch_remote_curl("https://example.com", ssh_alias="lt")
        assert res == ""


def test_fetch_remote_curl_exception():
    with patch("subprocess.run", side_effect=OSError("ssh executable not found")):
        res = fetch_remote_curl("https://example.com", ssh_alias="lt")
        assert res == ""


def test_fetch_remote_curl_empty_url():
    with patch("subprocess.run") as mock_run:
        res = fetch_remote_curl("")
        assert res == ""
        mock_run.assert_not_called()


def test_fetch_remote_curl_custom_headers_and_options():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        res = fetch_remote_curl(
            "https://example.com",
            headers={"X-Custom": "Val"},
            follow_redirects=False,
            use_ipv4=False,
        )
        assert res == "ok"
        args = mock_run.call_args[0][0]
        curl_cmd = args[4]
        assert "-H \"X-Custom: Val\"" in curl_cmd or "-H 'X-Custom: Val'" in curl_cmd
        assert "-s" in curl_cmd and "-sL" not in curl_cmd
        assert "-4" not in curl_cmd


def test_run_remote_ssh_dry_run():
    with patch("subprocess.run") as mock_run:
        res = run_remote_ssh("nas.host", "ls -la", user="media", dry_run=True)
        assert res.returncode == 0
        assert res.stdout == "[Dry-run] OK\n"
        assert res.stderr == ""
        assert res.args == ["ssh", "media@nas.host", "ls -la"]
        mock_run.assert_not_called()


def test_run_remote_ssh_execution():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="output\n", stderr="")
        res = run_remote_ssh("nas.host", "ls -la", user="media", connect_timeout=5, timeout=15)
        assert res.returncode == 0
        assert res.stdout == "output\n"
        args = mock_run.call_args[0][0]
        assert args[0] == "ssh"
        assert "-o" in args
        assert "ConnectTimeout=5" in args
        assert "media@nas.host" in args
        assert "ls -la" in args
        assert mock_run.call_args[1]["timeout"] == 15


def test_run_remote_ssh_no_user():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="output\n", stderr="")
        res = run_remote_ssh("nas.host", "uptime")
        assert res.returncode == 0
        args = mock_run.call_args[0][0]
        assert "nas.host" in args
        assert "uptime" in args


def test_run_remote_ssh_exception():
    with patch("subprocess.run", side_effect=RuntimeError("ssh connection dropped")):
        res = run_remote_ssh("nas.host", "ls -la", user="media")
        assert res.returncode == 1
        assert res.stdout == ""
        assert "ssh connection dropped" in res.stderr
