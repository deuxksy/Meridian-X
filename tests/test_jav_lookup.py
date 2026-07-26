import pytest
from meridian_x.jav_lookup import extract_jav_code, lookup_jav_actresses

def test_extract_jav_code():
    assert extract_jav_code("ABF-364.mp4") == "ABF-364"
    assert extract_jav_code("FNS-158-{FALENO star}-[None].mp4") == "FNS-158"
    assert extract_jav_code("random_western_video.mp4") is None

def test_lookup_jav_actresses_mock(mocker):
    # Mocking _ssh_curl HTML response
    mock_html = '<div class="panel"><a href="/tag/MINAMO">MINAMO</a></div>'
    mocker.patch("meridian_x.jav_lookup._ssh_curl", return_value=mock_html)
    actresses = lookup_jav_actresses("FNS-237")
    assert "MINAMO" in actresses

