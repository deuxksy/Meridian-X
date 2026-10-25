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


class TestOnejavFlareSolverr:
    """FlareSolverr 경유 수집 경로 테스트 (Cloudflare challenge 우회)"""

    # Chromium XML viewer가 RSS를 HTML-escape된 <pre>로 감싸서 반환
    WRAPPED_RSS = (
        '<html><body><pre>&lt;?xml version="1.0"?&gt;\n&lt;rss&gt;&lt;channel&gt;'
        '&lt;item&gt;&lt;title&gt;SONE-446&lt;/title&gt;'
        '&lt;link&gt;http://onejav.com/torrent/sone446&lt;/link&gt;'
        '&lt;description&gt;1.9 GB, A &amp;amp; B&lt;/description&gt;'
        '&lt;/item&gt;&lt;/channel&gt;&lt;/rss&gt;</pre></body></html>'
    )
    FS = {"html": "", "user_agent": "FS-UA/1", "cookies": {"cf_clearance": "abc"}}
    CONFIG = {
        "rss_url": "https://onejav.com/feeds/",
        "proxy": "http://brla.bun-bull.ts.net:8888",
        "flaresolverr": {"url": "http://fs:8191/v1", "proxy": "http://gluetun:8888"},
    }

    def test_discover_unwraps_xml_viewer(self):
        from unittest.mock import patch
        from meridian_x.sources.onejav import discover

        fs = {**self.FS, "html": self.WRAPPED_RSS}
        with patch("meridian_x.sources.onejav.fetch_via_flaresolverr", return_value=fs) as mock_fs:
            items = discover(self.CONFIG)
        assert len(items) == 1
        assert items[0]["id"] == "onejav:SONE446"
        assert items[0]["title"] == "SONE-446"
        assert items[0]["page_url"] == "http://onejav.com/torrent/sone446"
        mock_fs.assert_called_once_with("https://onejav.com/feeds/", self.CONFIG, timeout=30)

    def test_discover_returns_empty_when_flaresolverr_fails(self):
        from unittest.mock import patch
        from meridian_x.sources.onejav import discover

        with patch("meridian_x.sources.onejav.fetch_via_flaresolverr", return_value=None):
            assert discover(self.CONFIG) == []

    def test_resolve_downloads_with_clearance_cookie(self):
        from unittest.mock import patch
        from meridian_x.sources.onejav import resolve

        fs = {**self.FS, "html": '<a href="/torrent/sone446/download/12345/sone446.torrent">DL</a>'}
        item = {"page_url": "http://onejav.com/torrent/sone446"}
        with patch("meridian_x.sources.onejav.fetch_via_flaresolverr", return_value=fs) as mock_fs, \
             patch("meridian_x.sources.onejav.download_via_proxy", return_value=b"d8:announce4:test") as mock_dl:
            res = resolve(item, self.CONFIG)
        assert res == {"type": "metainfo", "data": b"d8:announce4:test"}
        # RSS의 http:// 링크는 https로 승격되어 요청됨
        assert mock_fs.call_args[0][0] == "https://onejav.com/torrent/sone446"
        assert mock_dl.call_args[0][0] == "https://onejav.com/torrent/sone446/download/12345/sone446.torrent"
        assert mock_dl.call_args[1]["cookies"] == {"cf_clearance": "abc"}
        assert mock_dl.call_args[1]["user_agent"] == "FS-UA/1"

    def test_resolve_returns_none_without_download_link(self):
        from unittest.mock import patch
        from meridian_x.sources.onejav import resolve

        fs = {**self.FS, "html": "<html>no link</html>"}
        with patch("meridian_x.sources.onejav.fetch_via_flaresolverr", return_value=fs), \
             patch("meridian_x.sources.onejav.download_via_proxy") as mock_dl:
            assert resolve({"page_url": "https://onejav.com/torrent/x"}, self.CONFIG) is None
        mock_dl.assert_not_called()

    def test_resolve_rejects_non_onejav_url(self):
        from unittest.mock import patch
        from meridian_x.sources.onejav import resolve

        with patch("meridian_x.sources.onejav.fetch_via_flaresolverr") as mock_fs:
            assert resolve({"page_url": "https://evil.com/torrent/x"}, self.CONFIG) is None
        mock_fs.assert_not_called()
