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
