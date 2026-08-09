"""TransmissionClient 도메인 로직 회귀 테스트.

transmission-rpc 마이그레이션 후에도 순수 함수 동작이 보존되는지 검증.
RPC 호출 / 네트워크 / Client 생성은 포함하지 않는다.
(probe 테스트만 예외적으로 소켓을 사용한다.)
"""
import socket
from types import SimpleNamespace

import pytest

from meridian_x.transmission import TransmissionClient


class TestExtractLabelsFromName:
    """_extract_labels_from_name: JAV 메이커 / West 스튜디오+배우 추출."""

    def test_jav_maker_code(self):
        # SNOS-125 → ['snos']
        assert TransmissionClient._extract_labels_from_name("SNOS-125 타이틀") == ["snos"]

    def test_jav_fc2(self):
        # FC2-PPV-4895410 → ['fc2']
        assert TransmissionClient._extract_labels_from_name("FC2-PPV-4895410") == ["fc2"]

    def test_west_studio_and_actress(self):
        # Vixen.16.09.06.Lily.Love.XXX → ['vixen', 'lily love']
        result = TransmissionClient._extract_labels_from_name(
            "Vixen.16.09.06.Lily.Love.XXX.1080p"
        )
        assert result == ["vixen", "lily love"]

    def test_west_studio_only_when_no_actress(self):
        # 배우명 추출 불가 시 스튜디오만
        result = TransmissionClient._extract_labels_from_name(
            "Brazzers.20.10.01.XXX"
        )
        assert result == ["brazzers"]

    def test_no_match_returns_empty(self):
        assert TransmissionClient._extract_labels_from_name("random title no pattern") == []


def _file(name, size):
    """테스트용 File mock (transmission-rpc File 객체의 name/size 호환)."""
    return SimpleNamespace(name=name, size=size)


def _client():
    """__init__ 없이 인스턴스 생성 (RPC 연결 회피)."""
    return TransmissionClient.__new__(TransmissionClient)


class TestFilterFiles:
    """_filter_files: 확장자/키워드/크기 기반 파일 제외 인덱스 반환."""

    FILTERS = {
        "exclude_extensions": [".html", ".url", ".txt"],
        "exclude_keywords": ["sample", "trailer"],
        "min_file_size_mb": 100,
    }

    def test_exclude_by_extension(self):
        files = [_file("ad.html", 1000)]
        assert _client()._filter_files(files, self.FILTERS) == [0]

    def test_exclude_by_keyword(self):
        files = [_file("movie sample.mp4", 500_000_000)]
        assert _client()._filter_files(files, self.FILTERS) == [0]

    def test_exclude_by_min_size(self):
        # 50MB < 100MB min
        files = [_file("small.mp4", 50 * 1024 * 1024)]
        assert _client()._filter_files(files, self.FILTERS) == [0]

    def test_keep_valid_file(self):
        files = [_file("big.mp4", 500 * 1024 * 1024)]
        assert _client()._filter_files(files, self.FILTERS) == []

    def test_mixed_files_correct_indices(self):
        files = [
            _file("ad.html", 1000),               # 0: ext
            _file("main.mp4", 500_000_000),        # 1: keep
            _file("trailer.mp4", 200_000_000),     # 2: keyword
            _file("small.mp4", 10_000_000),        # 3: size
        ]
        assert _client()._filter_files(files, self.FILTERS) == [0, 2, 3]

    def test_empty_filters_excludes_nothing(self):
        files = [_file("ad.html", 1000), _file("main.mp4", 500_000_000)]
        assert _client()._filter_files(files, {}) == []


class TestStopAfterDownloadExisting:
    """stop_after_download_existing: seed ratio 0 소급 적용 로직.

    RPC 호출 대신 change_torrent 호출을 추적하여 적용 대상/중복 skip 검증.
    """

    def _client_with_torrents(self, torrents):
        """get_torrents/change_torrent을 mock한 클라이언트."""
        c = _client()
        c._client = SimpleNamespace(
            get_torrents=lambda arguments=None: torrents,
            change_torrent=lambda tid, **kw: calls.append((tid, kw)),
        )
        calls = []
        return c, calls

    def test_applies_to_unconfigured_torrent(self):
        torrents = [SimpleNamespace(id=1, name="A", seed_ratio_mode=0, seed_ratio_limit=2.0)]
        c, calls = self._client_with_torrents(torrents)
        assert c.stop_after_download_existing() == 1
        assert calls == [(1, {"seed_ratio_mode": 1, "seed_ratio_limit": 0.0})]

    def test_skips_already_configured(self):
        torrents = [SimpleNamespace(id=1, name="A", seed_ratio_mode=1, seed_ratio_limit=0.0)]
        c, calls = self._client_with_torrents(torrents)
        assert c.stop_after_download_existing() == 0
        assert calls == []

    def test_mixed_torrents(self):
        torrents = [
            SimpleNamespace(id=1, name="A", seed_ratio_mode=1, seed_ratio_limit=0.0),
            SimpleNamespace(id=2, name="B", seed_ratio_mode=0, seed_ratio_limit=-1),
            SimpleNamespace(id=3, name="C", seed_ratio_mode=1, seed_ratio_limit=2.0),
        ]
        c, calls = self._client_with_torrents(torrents)
        assert c.stop_after_download_existing() == 2
        assert [tid for tid, _ in calls] == [2, 3]

    def test_dry_run_counts_without_applying(self):
        torrents = [SimpleNamespace(id=1, name="A", seed_ratio_mode=0, seed_ratio_limit=2.0)]
        c, calls = self._client_with_torrents(torrents)
        assert c.stop_after_download_existing(dry_run=True) == 1
        assert calls == []


class TestProbeReachable:
    """__init__ 도달성 probe: tailnet 다운 시 RPC timeout까지 hang 대신 명시적 에러."""

    def test_unreachable_port_raises_connection_error(self):
        # 닫힌 포트 → 즉시 refused → ConnectionError (hang 없음)
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        with pytest.raises(ConnectionError, match=f"127.0.0.1:{port}"):
            TransmissionClient(rpc_url=f"http://127.0.0.1:{port}/transmission/rpc")

    def test_ts_net_host_gets_tailscale_hint(self, mocker):
        # .ts.net 호스트 실패 시 Tailscale 점검 안내 포함
        mocker.patch("socket.create_connection", side_effect=OSError("unreachable"))
        with pytest.raises(ConnectionError, match="tailscale status"):
            TransmissionClient(rpc_url="https://heritage.bun-bull.ts.net/transmission/rpc")

    def test_reachable_host_constructs(self, mocker):
        # 로컬 리스너가 있으면 probe 통과. Client 생성 자체는 lib 영역이라 mock.
        mocker.patch("meridian_x.transmission.Client")
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        try:
            client = TransmissionClient(rpc_url=f"http://127.0.0.1:{port}/transmission/rpc")
            assert client._client is not None
        finally:
            listener.close()
