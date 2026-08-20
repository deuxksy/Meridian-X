"""
onejav.py 보안 패치 단위 테스트
"""
from meridian_x.sources.onejav import _validate_url, _safe_timeout


class TestValidateUrl:
    """_validate_url() 함수 테스트"""

    def test_allowed_hosts(self):
        """정상 onejav.com URL 통과"""
        assert _validate_url("https://onejav.com/torrent/SONE446") is True
        assert _validate_url("https://www.onejav.com/feeds/") is True
        assert _validate_url("http://onejav.com/") is True  # http도 허용

    def test_blocked_hosts(self):
        """악의적 도메인 차단"""
        assert _validate_url("https://onejav.com.evil.com/") is False
        assert _validate_url("https://evil.com/onejav.com/") is False
        assert _validate_url("https://onejav@evil.com/") is False

    def test_edge_cases_port_userinfo(self):
        """포트 명시, 대문자 호스트 - 오탐 방지"""
        # hostname은 포트/userinfo 제거 + 소문자 정규화
        assert _validate_url("https://ONEJAV.COM/torrent") is True
        assert _validate_url("https://onejav.com:443/torrent") is True
        assert _validate_url("https://user@onejav.com/torrent") is True  # userinfo 무시하고 hostname만 비교

    def test_malicious_schemes(self):
        """위험한 scheme 차단"""
        assert _validate_url("javascript:alert(1)") is False
        assert _validate_url("file:///etc/passwd") is False
        assert _validate_url("data:text/html,<script>") is False
        assert _validate_url("") is False
        assert _validate_url(None) is False


class TestSafeTimeout:
    """_safe_timeout() 함수 테스트"""

    def test_normal_int(self):
        """정상 int 값"""
        assert _safe_timeout({"request_timeout": 60}) == 60
        assert _safe_timeout({"request_timeout": 30}) == 30

    def test_default_value(self):
        """기본값 30"""
        assert _safe_timeout({}) == 30
        assert _safe_timeout({"request_timeout": None}) == 30

    def test_edge_cases(self):
        """엣지 케이스"""
        assert _safe_timeout({"request_timeout": -5}) == 1  # 음수 → 1로 클램프
        assert _safe_timeout({"request_timeout": 0}) == 1   # 0 → 1로 클램프
        assert _safe_timeout({"request_timeout": "abc"}) == 30  # 문자열 → 기본값
        assert _safe_timeout({"request_timeout": True}) == 1  # bool → int(True)=1 → max(1,1)=1


class TestOnejavRemoteFetch:
    """OneJAV fetch_remote_curl 연동 테스트"""

    def test_fetch_url_remote_alias(self):
        from meridian_x.sources.onejav import fetch_url_remote
        from meridian_x.remote import fetch_remote_curl
        assert fetch_url_remote is fetch_remote_curl

    def test_discover_with_fetch_remote_curl(self):
        from unittest.mock import patch
        from meridian_x.sources.onejav import discover

        sample_rss = """
        <item>
            <title>SONE-446</title>
            <link>https://onejav.com/torrent/SONE446</link>
            <description>Test description</description>
        </item>
        """
        config = {
            "rss_url": "https://onejav.com/feeds/",
            "remote": {"ssh_alias": "lt"},
            "request_timeout": 20,
        }
        with patch("meridian_x.sources.onejav.fetch_remote_curl", return_value=sample_rss) as mock_fetch:
            items = discover(config)
            assert len(items) == 1
            assert items[0]["id"] == "onejav:SONE446"
            assert items[0]["page_url"] == "https://onejav.com/torrent/SONE446"
            mock_fetch.assert_called_once_with("https://onejav.com/feeds/", ssh_alias="lt", timeout=20)

    def test_resolve_page_fetch_with_fetch_remote_curl(self):
        import base64
        from unittest.mock import patch
        from meridian_x.sources.onejav import resolve

        sample_html = '<a href="/torrent/SONE446/download/12345/sone446.torrent">Download</a>'
        config = {
            "remote": {"ssh_alias": "lt"},
            "request_timeout": 20,
        }
        item = {"page_url": "https://onejav.com/torrent/SONE446"}

        with patch("meridian_x.sources.onejav.fetch_remote_curl", return_value=sample_html) as mock_fetch, \
             patch("meridian_x.sources.onejav._ssh", return_value=(True, base64.b64encode(b"d1:ad2:ide").decode("utf-8"))):
            res = resolve(item, config)
            assert res is not None
            assert res["type"] == "metainfo"
            assert res["data"] == b"d1:ad2:ide"
            mock_fetch.assert_called_once_with("https://onejav.com/torrent/SONE446", ssh_alias="lt", timeout=20)

